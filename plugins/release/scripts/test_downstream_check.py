"""Index and lockfile checks against a local stand-in index."""

# ruff: noqa: S101, INP001, D103
import io
import json
import threading
from contextlib import redirect_stderr, redirect_stdout
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import TYPE_CHECKING, override

import downstream_check as check
import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

ROUTES: dict[str, object] = {
    "/pypi/libvcs/0.38.0/json": {
        "info": {"version": "0.38.0"},
        "urls": [{"yanked": False, "upload_time_iso_8601": "2026-10-01T00:00:00Z"}],
    },
    "/pypi/libvcs/0.37.0/json": {
        "info": {"version": "0.37.0"},
        "urls": [{"yanked": True, "upload_time_iso_8601": "2026-09-01T00:00:00Z"}],
    },
    "/pypi/libvcs/json": {
        "info": {"version": "0.38.0"},
        "urls": [{"yanked": False, "upload_time_iso_8601": "2026-10-01T00:00:00Z"}],
    },
    "/@acme%2Fwidget/1.5.0": {"version": "1.5.0", "deprecated": "use gadget"},
    "/widget/latest": {"version": "2.0.0"},
}


@pytest.fixture
def index_url() -> Iterator[str]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            body = ROUTES.get(self.path)
            self.send_response(200 if body is not None else 404)
            self.end_headers()
            self.wfile.write(json.dumps(body or {}).encode())

        @override
        def log_message(self, format: str, *args: object) -> None:
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
    )
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()
    thread.join()


def cli(*argv: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        status = check.main(list(argv))
    return status, out.getvalue(), err.getvalue()


def test_index_confirms_a_published_release_and_the_latest(index_url: str) -> None:
    status, out, _ = cli("index", "pypi", "LibVCS", "0.38.0", "--index-url", index_url)
    assert status == 0
    assert json.loads(out)["uploaded"] == "2026-10-01T00:00:00Z"
    status, out, _ = cli("index", "pypi", "libvcs", "--index-url", index_url)
    assert (status, json.loads(out)["version"]) == (0, "0.38.0")
    status, out, _ = cli("index", "npm", "widget", "--index-url", index_url)
    assert (status, json.loads(out)["version"]) == (0, "2.0.0")


def test_index_refuses_a_yanked_or_absent_release(index_url: str) -> None:
    status, out, err = cli("index", "pypi", "libvcs", "0.37.0", "--index-url", index_url)
    assert (status, out) == (1, "")
    assert err == "refused: libvcs 0.37.0 is yanked on the index\n"
    status, _, err = cli("index", "pypi", "libvcs", "9.9.9", "--index-url", index_url)
    assert status == 1
    assert "answered HTTP 404" in err
    status, _, err = cli("index", "crates", "serde", "1.0.0")
    assert status == 1
    assert "not supported; use pypi or npm" in err


def test_index_reports_an_npm_deprecation_and_encodes_scopes(index_url: str) -> None:
    status, out, _ = cli("index", "npm", "@acme/widget", "1.5.0", "--index-url", index_url)
    assert (status, json.loads(out)["deprecated"]) == (0, "use gadget")


UV_LOCK = """version = 1

[[package]]
name = "libvcs"
version = "0.38.0"
source = { registry = "https://pypi.org/simple" }

[[package]]
name = "demo"
version = "0.1.0"
source = { editable = "." }
"""


def test_uv_lock_must_hold_the_version_from_a_registry(tmp_path: Path) -> None:
    lock = tmp_path / "uv.lock"
    lock.write_text(UV_LOCK)
    assert cli("lock", str(lock), "LibVCS", "0.38.0")[0] == 0
    status, _, err = cli("lock", str(lock), "libvcs", "0.37.0")
    assert status == 1
    assert "locks libvcs at 0.38.0 from registry, not 0.37.0 from a registry" in err
    lock.write_text(UV_LOCK.replace('registry = "https://pypi.org/simple"', 'path = "../libvcs"'))
    status, _, err = cli("lock", str(lock), "libvcs", "0.38.0")
    assert status == 1
    assert "0.38.0 from path" in err
    assert (
        cli("lock", str(lock), "absent", "1.0.0")[2] == "refused: uv.lock has no entry for absent\n"
    )


def test_package_lock_rejects_links_and_git_sources(tmp_path: Path) -> None:
    lock = tmp_path / "package-lock.json"
    packages: dict[str, dict[str, object]] = {
        "": {"name": "demo"},
        "node_modules/widget": {
            "version": "1.5.0",
            "resolved": "https://registry.npmjs.org/widget/-/widget-1.5.0.tgz",
        },
    }
    lock.write_text(json.dumps({"lockfileVersion": 3, "packages": packages}))
    assert cli("lock", str(lock), "widget", "1.5.0")[0] == 0
    packages["node_modules/widget"] = {"version": "1.5.0", "resolved": "../widget", "link": True}
    lock.write_text(json.dumps({"lockfileVersion": 3, "packages": packages}))
    status, _, err = cli("lock", str(lock), "widget", "1.5.0")
    assert status == 1
    assert "1.5.0 from other" in err
    other = tmp_path / "Cargo.lock"
    other.write_text("")
    assert "Cargo.lock is not supported" in cli("lock", str(other), "serde", "1.0.0")[2]
