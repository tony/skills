"""Tests for pins.py with ``gh`` replaced by a stub on PATH."""

# ruff: noqa: S101, INP001, S603, S607, SLF001
# pyright: reportAny=false, reportUnusedCallResult=false, reportPrivateUsage=false
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, unquote, urlsplit

import pins  # pyright: ignore[reportImplicitRelativeImport]
import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

SCRIPT = Path(__file__).with_name("pins.py")
EXIT_UNCHECKED = 3
COMMIT_SHA = "a" * 40
TREE_SHA = "b" * 40
WORKFLOW_NAMES = (
    ".github/workflows/space name.yml",
    '.github/workflows/quote"name.yaml',
    ".github/workflows/back\\slash.yml",
    ".github/workflows/tab\tname.yml",
    ".github/workflows/line\nname.yml",
    ".github/workflows/line\rname.yml",
    ".github/workflows/line\r\nname.yml",
    ".github/workflows/caf\u00e9.yml",
    ".github/workflows/separator\u2028name.yml",
    ".github/workflows/hash#query?percent%25.yml",
    ".github/actions/nested\naction/action.yaml",
)


def _wf(*refs: str) -> str:
    """Return a workflow whose single job runs ``uses`` steps for each ref."""
    steps = "".join(f"      - uses: {ref}\n" for ref in refs)
    return f"on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n{steps}"


GH_STUB = """#!/bin/sh
if [ "$1" = api ]; then
  [ "$2" = --hostname ] && [ "$3" = github.com ] || exit 1
  shift 3
  set -- api "$@"
fi
case "$*" in
  "repo view https://github.com/acme/one"*) echo main ;;
  "repo view https://github.com/acme/two"*) echo trunk ;;
  "api repos/acme/one/commits/heads%2Fmain")
    printf '%s\\n' '{"sha":"COMMIT_SHA","commit":{"tree":{"sha":"TREE_SHA"}}}' ;;
  "api repos/acme/one/git/trees/TREE_SHA?recursive=1"*)
    printf '%s\\n' '{"sha":"TREE_SHA","truncated":false,"tree":[
      {"type":"blob","path":".github/workflows/ci.yml"},
      {"type":"blob","path":".github/README.md"}]}' ;;
  "api -H "*" repos/acme/one/contents/.github/workflows/ci.yml?ref=COMMIT_SHA")
    printf 'jobs:\\n  b:\\n    steps:\\n      - uses: actions/checkout@v4\\n' ;;
  "api -H "*" repos/acme/one/contents/.github/dependabot.y"*)
    echo "gh: Not Found (HTTP 404)" >&2; exit 1 ;;
  "api repos/actions/checkout/tags --paginate --jq .[].name")
    printf 'v4.2.2\\nv4.0.0\\nv3.0.0\\nv5.1.0\\nv5.0.0\\n' ;;
  "api repos/actions/checkout") echo '{}' ;;
  "api repos/actions/checkout/git/ref/tags/v4") echo '{}' ;;
  "api repos/actions/checkout/git/ref/tags/v99")
    echo "gh: Not Found (HTTP 404)" >&2; exit 1 ;;
  "api repos/hidden/action/git/ref/tags/v1"|"api repos/hidden/action")
    echo "gh: Not Found (HTTP 404)" >&2; exit 1 ;;
  "api repos/actions/checkout/git/ref/tags/v77")
    echo "gh: Bad credentials (HTTP 401)" >&2; exit 1 ;;
  *) echo "unsupported: $*" >&2; exit 1 ;;
esac
""".replace("COMMIT_SHA", COMMIT_SHA).replace("TREE_SHA", TREE_SHA)


@pytest.mark.parametrize(
    ("url", "slug"),
    [
        ("https://github.com/acme/one.git", "acme/one"),
        ("https://GITHUB.COM/acme/one/", "acme/one"),
        ("https://github.com:443/acme/repo.name.git", "acme/repo.name"),
        ("git@github.com:acme/one.git", "acme/one"),
        ("git@GITHUB.COM:acme/one.git", "acme/one"),
        ("github.com:acme/one", "acme/one"),
        ("ssh://git@github.com/acme/one.git", "acme/one"),
        ("ssh://git@github.com:22/acme/one.git", "acme/one"),
        ("https://notgithub.com/acme/one.git", None),
        ("https://github.com.evil.invalid/github.com/acme/one.git", None),
        ("https://evil.invalid/github.com/acme/one.git", None),
        ("https://github.com@evil.invalid/acme/one.git", None),
        ("git@notgithub.com:acme/one.git", None),
        ("git@g\u0131thub.com:acme/one.git", None),
        ("git@g\u0130thub.com:acme/one.git", None),
        ("file:///github.com/acme/one.git", None),
        ("http://github.com/acme/one.git", None),
        ("https://github.com:wrong/acme/one.git", None),
        ("https://[github.com/acme/one.git", None),
        ("https://github.com/acme/one.git?ref=main", None),
        ("https://github.com/acme/one.git#main", None),
        ("https://github.com/acme/../one.git", None),
        ("https://github.com/../one.git", None),
        ("https://github.com/acme/..", None),
        ("https://github.com/acme/one.git/extra", None),
        (" https://github.com/acme/one.git", None),
        ("https://git\thub.com/acme/one.git", None),
        ("https://github.com/acme/one.git\n", None),
        ("https://notgithub.com/acme/one.git\nhttps://github.com/acme/one.git", None),
    ],
)
def test_declared_remote_identity(
    url: str, slug: str | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only supported URLs with an exact GitHub host yield a repository identity."""

    def config_value(*_args: str) -> str:
        return url + "\n"

    monkeypatch.setattr(pins, "_out", config_value)
    if slug is None:
        with pytest.raises(SystemExit, match=r"not a github\.com URL"):
            pins._slug_from_remote("checkout", "origin")
    else:
        assert pins._slug_from_remote("checkout", "origin") == slug


def _fake_gh(monkeypatch: pytest.MonkeyPatch, api: Callable[..., str]) -> None:
    """Route every subprocess call through ``api``; SystemExit means a failed call."""

    def run(*args: str) -> subprocess.CompletedProcess[str]:
        try:
            out = api(*args)
        except SystemExit as error:
            return subprocess.CompletedProcess(args, 1, "", str(error.code))
        return subprocess.CompletedProcess(args, 0, out, "")

    monkeypatch.setattr(pins, "_run", run)


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _make_repo(root: Path, slug: str, branch: str, ref: str) -> Path:
    """Create a clone of a bare remote pinning checkout at ``ref``."""
    name = slug.split("/")[1]
    bare = root / f"{name}-bare.git"
    _git("init", "-q", "--bare", str(bare), cwd=root)
    work = root / name
    work.mkdir()
    _git("init", "-q", "-b", branch, cwd=work)
    _git("remote", "add", "origin", f"https://github.com/{slug}.git", cwd=work)
    wf = work / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "ci.yml").write_text(
        _wf(f"actions/checkout@{ref}", "./local"),
    )
    (work / ".github" / "README.md").write_text("  - uses: not/a-workflow@v1\n")
    _git("add", ".", cwd=work)
    _git(
        "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "ci",
        cwd=work,
    )  # fmt: skip
    _git(
        "config", f"url.{bare}.insteadOf", f"https://github.com/{slug}.git",
        cwd=work,
    )  # fmt: skip
    _git("push", "-q", "origin", branch, cwd=work)
    _git("fetch", "-q", "origin", cwd=work)
    return work


@pytest.fixture
def stub_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Put a gh stub first on PATH."""
    stub_bin = tmp_path / "bin"
    stub_bin.mkdir()
    gh = stub_bin / "gh"
    gh.write_text(GH_STUB)
    gh.chmod(0o755)
    monkeypatch.setenv("PATH", f"{stub_bin}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("GH_HOST", "elsewhere.invalid")
    monkeypatch.setenv("GH_REPO", "elsewhere.invalid/unrelated/repo")


def _run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd, capture_output=True, text=True, check=False,
    )  # fmt: skip


@pytest.mark.integration
@pytest.mark.usefixtures("stub_path")
def test_inventory_reads_each_repo_by_its_own_path(
    tmp_path: Path,
) -> None:
    """Two clones with different default branches are read from their own trees."""
    one = _make_repo(tmp_path, "acme/one", "main", "v3")
    two = _make_repo(tmp_path, "acme/two", "trunk", "v2")
    done = _run("inventory", str(one), str(two), cwd=tmp_path)
    assert done.returncode == 0, done.stderr
    first, second = (json.loads(x) for x in done.stdout.splitlines())
    assert (first["slug"], first["default"]) == ("acme/one", "main")
    assert (second["slug"], second["default"]) == ("acme/two", "trunk")
    for rec, ref in ((first, "v3"), (second, "v2")):
        actions = [p for p in rec["pins"] if p["kind"] == "action"]
        assert [(p["action"], p["ref"]) for p in actions] == [("actions/checkout", ref)]
        assert rec["files"] == [".github/workflows/ci.yml"]
    assert [p["kind"] for p in first["pins"]] == ["action", "local"]


@pytest.mark.integration
@pytest.mark.usefixtures("stub_path")
@pytest.mark.skipif(os.name != "posix", reason="native byte filenames require POSIX")
@pytest.mark.parametrize("quote_path", ["true", "false"])
def test_clone_inventory_preserves_filename_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, quote_path: str
) -> None:
    """Native Git paths survive quoting, framing and the CLI JSON round trip."""
    for name in tuple(os.environ):
        if name.startswith("GIT_"):
            monkeypatch.delenv(name)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_ALLOW_PROTOCOL", "file")
    repo = _make_repo(tmp_path, "acme/one", "main", "v3")
    expected = {".github/workflows/ci.yml": "v3"}
    for i, name in enumerate((*WORKFLOW_NAMES, ".github/workflows/byte-\udcff.yml")):
        target = repo / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(_wf(f"actions/checkout@v{i + 10}"))
        expected[name] = f"v{i + 10}"
    (repo / ".github/workflows/excluded.yml\n").write_text("uses: wrong/action@v1\n")
    _git("add", ".github", cwd=repo)
    _git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "paths", cwd=repo)
    _git("push", "-q", "origin", "main", cwd=repo)
    _git("config", "core.quotePath", quote_path, cwd=repo)

    done = _run("inventory", str(repo), cwd=tmp_path)

    assert done.returncode == 0, done.stderr
    record = json.loads(done.stdout)
    assert record["files"] == sorted(expected)
    assert {p["file"]: p["ref"] for p in record["pins"] if p["kind"] == "action"} == expected
    with pytest.raises(SystemExit):
        pins._read_clone(str(repo), "origin/absent-branch")


@pytest.mark.parametrize("default", ["main", "release/#ready&tested%"])
def test_slug_inventory_preserves_json_paths(monkeypatch: pytest.MonkeyPatch, default: str) -> None:
    """API paths remain JSON data and reserved characters cannot alter a lookup."""
    expected = {name: _wf(f"actions/checkout@v{i}") for i, name in enumerate(WORKFLOW_NAMES)}
    paths = [*expected, ".github/workflows/excluded.yml\n", ".github/README.md"]
    observed: list[str] = []

    def api(*args: str) -> str:
        assert args[:4] == ("gh", "api", "--hostname", "github.com")
        endpoint = next(arg for arg in args if arg.startswith("repos/"))
        url = urlsplit(endpoint)
        if "/commits/" in url.path:
            assert unquote(url.path.removeprefix("repos/acme/one/commits/")) == f"heads/{default}"
            assert not url.query
            assert not url.fragment
            return json.dumps({"sha": COMMIT_SHA, "commit": {"tree": {"sha": TREE_SHA}}})
        if "/git/trees/" in url.path:
            assert url.path == f"repos/acme/one/git/trees/{TREE_SHA}"
            assert parse_qs(url.query) == {"recursive": ["1"]}
            assert "--jq" not in args
            return json.dumps(
                {
                    "sha": TREE_SHA,
                    "truncated": False,
                    "tree": [
                        *({"type": "blob", "path": name} for name in paths),
                        {"type": "tree", "path": ".github/workflows/directory.yml"},
                    ],
                }
            )
        assert args[4:6] == ("-H", "Accept: application/vnd.github.raw+json")
        name = unquote(url.path.removeprefix("repos/acme/one/contents/"))
        assert parse_qs(url.query) == {"ref": [COMMIT_SHA]}
        assert not url.fragment
        assert name in expected, repr(name)
        observed.append(name)
        return expected[name]

    _fake_gh(monkeypatch, api)

    assert pins._read_slug("acme/one", default) == (expected, COMMIT_SHA, TREE_SHA)
    assert sorted(observed) == sorted(expected)


@pytest.mark.parametrize("empty", [False, True])
def test_slug_inventory_recovers_recursive_truncation(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], empty: bool
) -> None:
    """Complete immutable subtrees recover every selected path, including an empty set."""
    github, workflows, nested = "c" * 40, "d" * 40, "e" * 40
    selected = {
        ".github/workflows/ci.yml": "v3",
        ".github/workflows/nested #/caf\u00e9.yaml": "v4",
    }
    trees = {
        TREE_SHA: [] if empty else [("tree", ".github", github), ("tree", "vendor", "f" * 40)],
        github: [("tree", "workflows", workflows)],
        workflows: [("blob", "ci.yml", "1" * 40), ("tree", "nested #", nested)],
        nested: [("blob", "caf\u00e9.yaml", "2" * 40)],
    }
    observed: list[str] = []

    def api(*args: str) -> str:
        if args[1] == "repo":
            assert args[2:4] == ("view", "https://github.com/acme/one")
            return "main\n"
        assert args[:4] == ("gh", "api", "--hostname", "github.com")
        endpoint = next(arg for arg in args if arg.startswith("repos/"))
        url = urlsplit(endpoint)
        if "/commits/" in url.path:
            assert unquote(url.path) == "repos/acme/one/commits/heads/main"
            return json.dumps({"sha": COMMIT_SHA, "commit": {"tree": {"sha": TREE_SHA}}})
        if "/git/trees/" in url.path:
            sha = url.path.removeprefix("repos/acme/one/git/trees/")
            if url.query:
                assert sha == TREE_SHA
                assert parse_qs(url.query) == {"recursive": ["1"]}
                return json.dumps({"sha": sha, "truncated": True, "tree": []})
            observed.append(sha)
            return json.dumps(
                {
                    "sha": sha,
                    "truncated": False,
                    "tree": [
                        {"type": kind, "path": name, "sha": oid} for kind, name, oid in trees[sha]
                    ],
                }
            )
        assert args[4:6] == ("-H", "Accept: application/vnd.github.raw+json")
        assert parse_qs(url.query) == {"ref": [COMMIT_SHA]}
        name = unquote(url.path.removeprefix("repos/acme/one/contents/"))
        if name not in selected:
            not_found = "gh: Not Found (HTTP 404)"
            raise SystemExit(not_found)
        return _wf(f"actions/checkout@{selected[name]}")

    _fake_gh(monkeypatch, api)
    assert pins.main(["inventory", "acme/one"]) == 0
    result = json.loads(capsys.readouterr().out)
    expected = {} if empty else selected
    assert result["files"] == sorted(expected)
    assert {pin["file"]: pin["ref"] for pin in result["pins"]} == expected
    assert (result["commit"], result["tree"]) == (COMMIT_SHA, TREE_SHA)
    assert set(observed) == ({TREE_SHA} if empty else {TREE_SHA, github, workflows, nested})


@pytest.mark.parametrize("failure", ["tree", "content"])
def test_slug_inventory_refuses_partial_json(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], failure: str
) -> None:
    """An incomplete nonrecursive tree or failed content read cannot print success."""

    def api(*args: str) -> str:
        if args[1] == "repo":
            return "main\n"
        assert args[:4] == ("gh", "api", "--hostname", "github.com")
        endpoint = next(arg for arg in args if arg.startswith("repos/"))
        if "/commits/" in endpoint:
            return json.dumps({"sha": COMMIT_SHA, "commit": {"tree": {"sha": TREE_SHA}}})
        if "/git/trees/" in endpoint:
            return json.dumps(
                {
                    "sha": TREE_SHA,
                    "truncated": failure == "tree",
                    "tree": []
                    if failure == "tree"
                    else [{"type": "blob", "path": ".github/workflows/ci.yml"}],
                }
            )
        message = "content read failed"
        raise SystemExit(message)

    _fake_gh(monkeypatch, api)
    reason = "incomplete non-recursive tree" if failure == "tree" else "content read failed"
    with pytest.raises(SystemExit) as stopped:
        pins.main(["inventory", "acme/one"])
    captured = capsys.readouterr()
    assert captured.out == ""
    assert reason in f"{stopped.value.code}{captured.err}"


@pytest.mark.integration
@pytest.mark.parametrize("add_github_url", [False, True])
def test_inventory_refuses_wrong_host_before_fetch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, add_github_url: bool
) -> None:
    """An owned Git config is rejected before any fetch or API command."""
    _git("init", "-q", cwd=tmp_path)
    url = "https://fixture-user:fixture-password@notgithub.com/acme/one.git"
    _git("remote", "add", "origin", url, cwd=tmp_path)
    if add_github_url:
        _git(
            "config", "--add", "remote.origin.url", "https://github.com/acme/one.git", cwd=tmp_path
        )
    observed: list[tuple[str, ...]] = []
    original = pins._out

    def read_config(*args: str) -> str:
        observed.append(args)
        assert args[:3] == ("git", "-C", str(tmp_path))
        assert args[3] in {"remote", "config"}, "fetch/API reached before refusal"
        return original(*args)

    monkeypatch.setattr(pins, "_out", read_config)
    with pytest.raises(SystemExit, match=r"not a github\.com URL") as error:
        pins.inventory(str(tmp_path))
    assert [args[3] for args in observed] == ["remote", "config"]
    assert "fixture-user" not in str(error.value)
    assert "fixture-password" not in str(error.value)


@pytest.mark.integration
@pytest.mark.usefixtures("stub_path")
def test_slug_inventory_binds_github_host(tmp_path: Path) -> None:
    """CLI inventory names GitHub for both repository and file API reads."""
    done = _run("inventory", "acme/one", cwd=tmp_path)
    assert done.returncode == 0, done.stderr
    record = json.loads(done.stdout)
    assert (record["slug"], record["default"]) == ("acme/one", "main")
    assert (record["commit"], record["tree"]) == (COMMIT_SHA, TREE_SHA)
    assert record["files"] == [".github/workflows/ci.yml"]
    assert [(pin["action"], pin["ref"]) for pin in record["pins"]] == [("actions/checkout", "v4")]


@pytest.mark.integration
@pytest.mark.usefixtures("stub_path")
def test_majors_lists_first_release_of_each_major(
    tmp_path: Path,
) -> None:
    """Majors above the pin and at or below the target print in order."""
    done = _run("majors", "actions/checkout", "v3", "v5", cwd=tmp_path)
    assert done.stdout.split() == ["v4.0.0", "v5.0.0"]


@pytest.mark.integration
@pytest.mark.usefixtures("stub_path")
def test_tag_exit_status(
    tmp_path: Path,
) -> None:
    """Exists exits 0, a 404 exits 1, and any other failure exits 3."""
    assert _run("tag", "actions/checkout", "v4", cwd=tmp_path).returncode == 0
    missing = _run("tag", "actions/checkout", "v99", cwd=tmp_path)
    assert (missing.returncode, missing.stdout.strip()) == (1, "missing")
    failed = _run("tag", "actions/checkout", "v77", cwd=tmp_path)
    assert failed.returncode == EXIT_UNCHECKED
    assert "could not be checked" in failed.stderr
    assert "missing" not in failed.stdout


@pytest.mark.integration
def test_closeout_comment_keeps_branch_literal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A valid Git branch containing shell syntax remains comment data."""
    branch = "release$(printf${IFS}OWNED_MARKER)"
    _git("check-ref-format", "--branch", branch, cwd=tmp_path)
    reference = (SCRIPT.parent.parent / "references" / "dependabot-closeout.md").read_text()
    command = re.findall(r"```console\n\$ (gh pr comment.*?)\n```", reference, re.DOTALL)[0]
    values = {
        "<n>": "41",
        "<slug>": "acme/widgets",
        "<sha12>": "a" * 12,
        "<sha>": "a" * 40,
        "<trunk>": branch,
        "<action>": "actions/checkout",
        "<comment-file>": "comment body.md",
    }
    for placeholder, value in values.items():
        command = command.replace(placeholder, value)
    body = f"Superseded on `{branch}`.\n"
    (tmp_path / "comment body.md").write_text(body)
    gh = tmp_path / "gh"
    gh.write_text(
        f"""#!{sys.executable}
import json, sys
from pathlib import Path
args = sys.argv[1:]
if '--body-file' in args:
    body = Path(args[args.index('--body-file') + 1]).read_text()
else:
    body = args[args.index('--body') + 1]
print(json.dumps({{"body": body}}))
"""
    )
    gh.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")

    done = subprocess.run(
        ["sh", "-c", command], cwd=tmp_path, capture_output=True, text=True, check=False
    )

    assert done.returncode == 0, done.stderr
    assert branch in json.loads(done.stdout)["body"]
    assert json.loads(done.stdout)["body"] == body
    assert (tmp_path / "comment body.md").read_text() == body


HEREDOC_AND_FORMS = """\
jobs:
  call:
    uses: acme/shared/.github/workflows/ci.yml@v2
  build:
    steps:
      - run: |
          cat <<'EXAMPLE'
          uses: acme/example-only@v9
          EXAMPLE
      - run: echo "uses: acme/also-text@v1" # uses: acme/comment@v1
      - "uses": actions/checkout@v3 # v3.6.0
      - {name: node, uses: 'actions/setup-node@v4'}
      - uses:
          actions/cache@v4
      - name: inputs are not pins
        uses: acme/real@v5
        with: {uses: acme/input-only@v1}
        env:
          uses: acme/env-only@v1
  matrix:
    steps: [{uses: "a/one@v1"}, {uses: a/two@v2,
      }, {run: x}]
"""


def test_scan_reads_structure_not_text() -> None:
    """Every pin form is found; shell text and input names are not pins."""
    result = pins._scan({".github/workflows/ci.yml": HEREDOC_AND_FORMS}, lambda _name: None)
    assert [(p["uses"], p["version"]) for p in result["pins"]] == [
        ("acme/shared/.github/workflows/ci.yml@v2", "2"),
        ("actions/checkout@v3", "3"),
        ("actions/setup-node@v4", "4"),
        ("actions/cache@v4", "4"),
        ("acme/real@v5", "5"),
        ("a/one@v1", "1"),
        ("a/two@v2", "2"),
    ]
    assert result["complete"] is True


@pytest.mark.parametrize(
    "text",
    [
        "jobs:\n  b:\n    steps:\n      - uses: *checkout\n",
        "base: &base\n  uses: x/y@v1\njobs:\n  b:\n    steps:\n      - *base\n",
        "jobs:\n  b:\n    <<: *defaults\n",
        "jobs:\n  b:\n    steps:\n      - uses: |\n          a/b@v1\n",
        "jobs:\n  b:\n    steps:\n      - uses: [a/b@v1]\n",
        "jobs:\n  b:\n    steps:\n      - {uses: 'a/b@v1\n",
        "jobs:\n  b:\n\tsteps: []\n",
        "? complex\n: key\n",
    ],
)
def test_unreadable_yaml_marks_inventory_incomplete(text: str) -> None:
    """A construct the reader cannot interpret is reported, never skipped."""
    result = pins._scan({".github/workflows/ci.yml": text}, lambda _name: None)
    assert result["complete"] is False
    assert [u["file"] for u in result["unparsed"]] == [".github/workflows/ci.yml"]


def test_scan_follows_local_composites_anywhere() -> None:
    """Local actions outside .github/actions are read; missing or escaping ones are listed."""
    tree = {
        "tools/ci/setup/action.yaml": (
            "runs:\n  using: composite\n  steps:\n"
            "    - uses: actions/cache@v4\n    - uses: ./tools/ci/setup\n"
        ),
        "release.yml": "jobs:\n  b:\n    steps:\n      - uses: actions/stale@v9\n",
    }
    workflow = _wf("./tools/ci/setup/", "./missing", "./../outside", "./release.yml")
    result = pins._scan({".github/workflows/ci.yml": workflow}, tree.get)
    assert result["files"] == [
        ".github/workflows/ci.yml",
        "release.yml",
        "tools/ci/setup/action.yaml",
    ]
    actions = [p["uses"] for p in result["pins"] if p["kind"] == "action"]
    assert actions == ["actions/stale@v9", "actions/cache@v4"]
    reasons = {u["uses"]: u["reason"] for u in result["unresolved"]}
    assert reasons == {
        "./missing": "no action file found",
        "./../outside": "outside repository",
    }
    assert result["complete"] is False


def test_majors_includes_tag_only_and_non_zero_first_releases(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Tags, not release objects, decide coverage; a missing major exits 4 after printing."""

    def tags(*_args: str) -> str:
        return "v5.0.0\nv4.1.0\nv4\nv3.9.0\nv7.0.0\n"

    monkeypatch.setattr(pins, "_out", tags)
    assert pins.main(["majors", "acme/x", "v3", "v7"]) == pins.EXIT_INCOMPLETE
    done = capsys.readouterr()
    assert done.out.split() == ["v4.1.0", "v5.0.0", "v7.0.0"]
    assert "major 6" in done.err
    assert pins.main(["majors", "acme/x", "v3", "v5"]) == 0


@pytest.mark.integration
@pytest.mark.usefixtures("stub_path")
def test_unreadable_repository_404_is_not_a_missing_tag(tmp_path: Path) -> None:
    """A 404 for a repository this login cannot read leaves the tag unchecked."""
    done = _run("tag", "hidden/action", "v1", cwd=tmp_path)
    assert done.returncode == EXIT_UNCHECKED
    assert "not readable" in done.stderr
    assert done.stdout == ""


PROPOSAL_DIFF = """\
diff --git a/.github/workflows/ci.yml b/.github/workflows/ci.yml
index 1..2 100644
--- a/.github/workflows/ci.yml
+++ b/.github/workflows/ci.yml
@@ -5,3 +5,3 @@
     steps:
-      - uses: actions/checkout@v3
+      - uses: actions/checkout@v5
-      - uses: actions/cache@abc123 # v3.0.0
+      - uses: actions/cache@def456 # v4.1.0
@@ -20,2 +20,3 @@
-      - uses: actions/setup-node@v3
+      - uses: other/node@v3
+      - run: curl evil
diff --git a/pyproject.toml b/pyproject.toml
--- a/pyproject.toml
+++ b/pyproject.toml
@@ -1 +1 @@
-x = 1
+x = 2
"""


def test_proposal_separates_pin_changes_from_everything_else(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only same-action uses edits count as pin changes; other lines are counted."""

    def diff(*_args: str) -> str:
        return PROPOSAL_DIFF

    monkeypatch.setattr(pins, "_out", diff)
    got = pins.proposal("acme/one", "7")
    assert got["files"] == [".github/workflows/ci.yml", "pyproject.toml"]
    assert [(c["action"], c["from_version"], c["to_version"]) for c in got["changes"]] == [
        ("actions/checkout", "3", "5"),
        ("actions/cache", "3.0.0", "4.1.0"),
    ]
    assert got["other"] == 2 + 1 + 2
