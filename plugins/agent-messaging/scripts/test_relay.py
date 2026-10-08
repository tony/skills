"""Run relay.sh's selftest and its transport-failure mapping under pytest."""

# ruff: noqa: S101, S603, INP001, D103, PLR2004
# pyright: reportUnusedCallResult=false

from __future__ import annotations

import os
import pathlib
import shutil
import socket
import subprocess
import tempfile

import pytest

RELAY = pathlib.Path(__file__).with_name("relay.sh")

needs_tools = pytest.mark.skipif(
    shutil.which("jq") is None or shutil.which("bash") is None,
    reason="relay.sh needs bash and jq",
)


@needs_tools
def test_selftest() -> None:
    result = subprocess.run(
        [str(RELAY), "selftest"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "selftest ok" in result.stdout


@needs_tools
def test_socket_send_maps_nc_failure_to_exit_6() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        stub = pathlib.Path(tmp, "bin")
        stub.mkdir()
        nc = stub / "nc"
        nc.write_text("#!/bin/sh\nexit 1\n")
        nc.chmod(0o755)
        sock_path = pathlib.Path(tmp, "s.sock")
        srv = socket.socket(socket.AF_UNIX)
        srv.bind(str(sock_path))
        try:
            env = {**os.environ, "PATH": f"{stub}{os.pathsep}{os.environ['PATH']}"}
            env.pop("CODEX_SANDBOX_NETWORK_DISABLED", None)
            result = subprocess.run(
                [str(RELAY), "socket-send", "--socket", str(sock_path), "--line", "x"],
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
        finally:
            srv.close()
    assert result.returncode == 6, result.stderr


@needs_tools
def test_socket_send_adds_n_when_help_exits_nonzero() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        stub = pathlib.Path(tmp, "bin")
        stub.mkdir()
        log = pathlib.Path(tmp, "args")
        nc = stub / "nc"
        script = (
            '#!/bin/sh\nif [ "$1" = -h ]; then echo "usage: nc [-N]"; exit 1; fi\n',
            f'echo "$@" >{log}\ncat >/dev/null\n',
        )
        nc.write_text("".join(script))
        nc.chmod(0o755)
        sock_path = pathlib.Path(tmp, "s.sock")
        srv = socket.socket(socket.AF_UNIX)
        srv.bind(str(sock_path))
        try:
            env = {**os.environ, "PATH": f"{stub}{os.pathsep}{os.environ['PATH']}"}
            env.pop("CODEX_SANDBOX_NETWORK_DISABLED", None)
            result = subprocess.run(
                [str(RELAY), "socket-send", "--socket", str(sock_path), "--line", "x"],
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
        finally:
            srv.close()
        assert result.returncode == 0, result.stderr
        assert "-N" in log.read_text()


@needs_tools
@pytest.mark.parametrize(
    "extra",
    [["--seq", "1 hop=0"], ["--to", "r\nhop=0"], ["--from", "p:c@s\nx"]],
)
def test_envelope_rejects_header_injection(extra: list[str]) -> None:
    args = {"--from": "p:c@s", "--to": "r", "--hop": "0", "--body": "hi"}
    args.update(dict(zip(extra[::2], extra[1::2])))
    cmd = [str(RELAY), "envelope", *[x for kv in args.items() for x in kv]]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert result.returncode == 2, result.stdout
    assert result.stdout == ""
