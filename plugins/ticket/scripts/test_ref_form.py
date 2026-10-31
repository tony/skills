"""Tests for ref_form.py."""

# ruff: noqa: S101, S603, INP001, D103, PLR2004
# pyright: reportUnusedCallResult=false
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).with_name("ref_form.py")


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True, check=False
    )


def test_github_forms() -> None:
    assert run("github", "same", "--notify", "--id", "12").stdout == "#12\n"
    url = "https://github.com/o/r/issues/3"
    assert run("github", "cross", "--notify", "--url", url, "--title", "Plan").stdout == (
        "[Plan](https://github.com/o/r/issues/3)\n"
    )
    quiet = run("github", "cross", "--quiet", "--url", url, "--title", "Plan")
    assert quiet.stdout == "[Plan](https://redirect.github.com/o/r/issues/3)\n"
    assert run("github", "same", "--quiet", "--url", url).stdout == (
        "https://redirect.github.com/o/r/issues/3\n"
    )


def test_github_redirect_host_is_refused_on_data_residency() -> None:
    result = run("github", "same", "--quiet", "--url", "https://acme.ghe.com/o/r/issues/3")
    assert result.returncode == 1
    assert "no form" in result.stdout


def test_gitlab_forms() -> None:
    assert run("gitlab", "same", "--notify", "--id", "5").stdout == "#5\n"
    assert run("gitlab", "same", "--quiet", "--id", "5").stdout == "\\#5\n"
    assert (
        run("gitlab", "cross", "--notify", "--id", "5", "--path", "ns/app").stdout == "ns/app#5\n"
    )
    assert (
        run("gitlab", "cross", "--quiet", "--id", "5", "--path", "ns/app").stdout == "`ns/app#5`\n"
    )


def test_jira_key_is_the_same_for_both_intents() -> None:
    assert run("jira", "same", "--quiet", "--id", "ENG-7").stdout == "ENG-7\n"
    assert run("jira", "same", "--notify", "--id", "ENG-7").stdout == "ENG-7\n"
    other = run(
        "jira", "cross", "--quiet", "--url", "https://x.atlassian.net/browse/A-1", "--title", "A"
    )
    assert other.stdout == "[A](https://x.atlassian.net/browse/A-1)\n"


def test_providers_without_a_documented_quiet_form_exit_1() -> None:
    for provider in ("linear", "azure"):
        result = run(provider, "same", "--quiet", "--id", "9")
        assert result.returncode == 1, provider
    assert run("trello", "cross", "--notify", "--url", "u", "--title", "t").returncode == 1


def test_other_providers() -> None:
    assert run("linear", "same", "--notify", "--id", "ENG-9").stdout == "ENG-9\n"
    assert run("azure", "same", "--notify", "--id", "9").stdout == "#9\n"
    assert run("shortcut", "same", "--quiet", "--id", "123").stdout == "sc-123\n"
    assert run("asana", "cross", "--quiet", "--id", "42").stdout == '<a data-asana-gid="42"/>\n'


def test_bad_input_exits_2() -> None:
    assert run("github", "same", "--notify").returncode == 2
    assert run("nowhere", "same", "--notify", "--id", "1").returncode == 2
    assert run("github", "same").returncode == 2


def test_bad_scope_lists_valid_values() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "github", "same-repo", "--quiet"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "`same`" in result.stderr
    assert "github, gitlab" in result.stderr
