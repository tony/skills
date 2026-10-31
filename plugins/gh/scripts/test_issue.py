"""Tests for issue.py."""

# ruff: noqa: S101, INP001, S603, S607, D103, PLR2004
# pyright: reportAny=false, reportUnusedCallResult=false
import json
import os
import subprocess
import sys
from pathlib import Path

import issue  # pyright: ignore[reportImplicitRelativeImport]
import pytest

SCRIPT = Path(__file__).with_name("issue.py")

FORM = """\
name: Bug
description: Report a bug
title: "[Bug]: "
labels: ["bug", needs-triage]
assignees:
  - octocat
body:
- type: markdown
  attributes:
    value: |
      Thanks!
- type: checkboxes
  attributes:
    label: Checks
    description: The Code of Conduct helps create a safe space for everyone. We require
      that everyone agrees to it.
    options:
      - label: I searched existing issues
        required: true
- type: dropdown
  id: version
  attributes:
    label: Version
    options:
      - 1.0.2 (Default)
      - 1.0.3
  validations:
    required: true
- type: textarea
  attributes:
    label: Logs
    render: shell
"""


def _run(
    *args: str, cwd: Path | None = None, stdin: str | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
        cwd=cwd,
        input=stdin,
    )


def test_form_skeleton_and_metadata() -> None:
    form = issue.form_from_yaml(issue.parse_yaml(FORM))
    assert form["labels"] == ["bug", "needs-triage"]
    assert form["assignees"] == ["octocat"]
    assert form["title"] == "[Bug]: "
    assert [f["label"] for f in form["fields"]] == ["Checks", "Version", "Logs"]
    assert form["fields"][1]["required"] is True
    assert form["body"] == (
        "### Checks\n\n- [ ] I searched existing issues\n\n"
        "### Version\n\n<CHOOSE>\n\n"
        "### Logs\n\n```shell\n<ANSWER>\n```\n"
    )


@pytest.mark.parametrize(
    "text",
    [
        "name: a\ndescription: b\nbody:\n- type: upload\n  attributes:\n    label: x\n",
        "name: a\ndescription: b\nbody:\n- type: input\n  attributes:\n    label: &x y\n",
        "name: a\ndescription: b\nbody:\n- type: input\n  attributes: {label: x}\n",
        "name: a\nbody: []\n",
        "name: a\n\tdescription: b\nbody: []\n",
        "name: a\ndescription: b\nbody:\n- type: dropdown\n  attributes:\n    label: x\n",
    ],
)
def test_refuses_what_it_cannot_parse(text: str) -> None:
    done = _run("template", "f.yml", stdin=text)
    assert done.returncode == 2
    assert done.stderr.startswith("unsupported:")
    assert done.stdout == ""


def test_template_cli_markdown_and_form(tmp_path: Path) -> None:
    md = tmp_path / "bug.md"
    md.write_text("---\nname: Bug\ntitle: 'BUG: '\nlabels: a, b\nassignees: ''\n---\n### Steps\n")
    out = json.loads(_run("template", "bug.md", str(md)).stdout)
    assert (out["kind"], out["labels"], out["assignees"], out["body"]) == (
        "markdown",
        ["a", "b"],
        [],
        "### Steps\n",
    )
    assert json.loads(_run("template", "bug.yml", stdin=FORM).stdout)["kind"] == "form"


def test_repo_from_remotes(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    for name, url in (
        ("origin", "git@github.com:me/widgets.git"),
        ("upstream", "https://github.com/example/widgets"),
        ("alias", "git@work:me/x.git"),
    ):
        subprocess.run(["git", "remote", "add", name, url], cwd=tmp_path, check=True)
    done = _run("repo", cwd=tmp_path)
    rows = dict(line.split("\t") for line in done.stdout.splitlines())
    assert rows == {"origin": "me/widgets", "upstream": "example/widgets", "alias": "-"}
    assert done.returncode == 0


def test_repo_arguments_and_host() -> None:
    assert _run("repo", "https://github.com/o/r/pull/9", "x/y").stdout == "o/r\nx/y\n"
    ghe = _run("repo", "--host", "ghe.example", "git@ghe.example:o/r.git")
    assert ghe.stdout == "o/r\n"
    assert _run("repo", "git@elsewhere:o/r").returncode == 1


def test_scan_reports_line_and_category_only(tmp_path: Path) -> None:
    path = tmp_path / "b.md"
    secret = "ghp_" + "a" * 36
    path.write_text(f"clean\nat /home/ann/src with {secret}\nhost db1.corp ok\n")
    done = _run("scan", str(path))
    assert done.returncode == 1
    assert secret not in done.stdout
    assert done.stdout.splitlines() == ["2\tlocal-path", "2\ttoken", "3\tinternal-host"]


def test_scan_clean(tmp_path: Path) -> None:
    path = tmp_path / "b.md"
    path.write_text("### Summary\n\nversion 2.4.1 fails.\n")
    assert _run("scan", str(path)).returncode == 0


def test_placeholders_block_outside_fences_only(tmp_path: Path) -> None:
    path = tmp_path / "b.md"
    path.write_text("```text\n<DEBUG> trace\n```\n")
    fenced = _run("placeholders", str(path))
    assert (fenced.returncode, fenced.stdout) == (0, "2\tfenced\n")
    path.write_text("`Vec<T>` and `HashMap<K, V>`\n")
    assert _run("placeholders", str(path)).returncode == 0
    path.write_text("`Vec<T>` link blob/<SHA>/x\n\nCONTACT\n")
    blocked = _run("placeholders", str(path))
    assert blocked.returncode == 1
    assert blocked.stdout == "1\tblocking\n3\tblocking\n"


def test_usage_exit_code() -> None:
    assert _run("nope").returncode == 64


def test_pick_needs_exactly_one_match() -> None:
    one = _run("pick", "defect", stdin="config.yml\nbug_report.yml\nfeature.yml\n")
    assert (one.returncode, one.stdout) == (0, "bug_report.yml\n")
    none = _run("pick", "defect", stdin="crash.yml\nperformance.yml\n")
    assert none.returncode == 1
    assert "crash.yml" in none.stderr
    two = _run("pick", "defect", stdin="bug.yml\n2-bug.md\n")
    assert two.returncode == 1


def test_labels_keeps_repository_spelling() -> None:
    have = json.dumps([{"name": "Bug"}, {"name": "help wanted"}])
    done = _run("labels", "bug", "nope", stdin=have)
    assert done.stdout == "Bug\n"


def test_readback_compares_title() -> None:
    body = json.dumps({"title": "T"})
    assert _run("readback", "T", stdin=body).stdout == "ok\n"
    assert _run("readback", "U", stdin=body).returncode == 1
    assert _run("readback", "T", stdin="").stdout == "unreadable\n"


def test_scan_addresses_skip_versions_and_flag_hosts(tmp_path: Path) -> None:
    path = tmp_path / "b.md"
    path.write_text("widgets v1.2.3.4\nserver 10.1.2.3\nbad 300.1.1.1\n")
    assert _run("scan", str(path)).stdout == "2\tip-address\n"
    path.write_text("x" * 65537)
    assert _run("scan", str(path)).stdout == "0\tlength\n"


REQUIRED_FORM = """\
# comment
name: 'Bug: it''s broken'
description: >
  Report a
  bug
body:
  - type: input
    attributes:
      label: Version   # inline comment
    validations:
      required: true
  - type: textarea
    attributes:
      label: Notes
  - type: dropdown
    attributes:
      label: OS
      multiple: false
      default: 0
      options: [Linux, macOS]
    validations:
      required: false
  - type: checkboxes
    attributes:
      label: Confirm
      options:
        - label: I read the guide
          required: true
        - label: Optional box
"""


def test_required_flags_and_option_shapes() -> None:
    form = issue.form_from_yaml(issue.parse_yaml(REQUIRED_FORM))
    assert form["name"] == "Bug: it's broken"
    fields = {f["label"]: f for f in form["fields"]}
    assert fields["Version"]["required"] is True
    assert fields["Notes"]["required"] is False
    assert fields["OS"]["options"] == ["Linux", "macOS"]
    assert fields["OS"]["required"] is False
    assert fields["Confirm"]["options"] == [
        {"label": "I read the guide", "required": True},
        {"label": "Optional box", "required": False},
    ]
    assert "- [ ] Optional box" in form["body"]
    assert form["body"].count("<ANSWER>") == 2


def test_duplicate_key_and_bad_checkbox_option_refused() -> None:
    with pytest.raises(issue.UnsupportedError):
        issue.parse_yaml("a: 1\na: 2\n")
    bad = (
        "name: n\ndescription: d\nbody:\n- type: checkboxes\n"
        "  attributes:\n    label: x\n    options:\n    - plain\n"
    )
    with pytest.raises(issue.UnsupportedError):
        issue.form_from_yaml(issue.parse_yaml(bad))


def test_scan_flags_mentions_and_xrefs_outside_code(tmp_path: Path) -> None:
    path = tmp_path / "b.md"
    path.write_text(
        "\n".join(  # noqa: FLY002
            [
                "ping @alice and fix #12",
                "`@lit` and `#13`",
                "```",
                "@fence #14",
                "```",
                "see o/r#15 mail a@b.co url x/#16",
                "",
            ]
        )
    )
    rows = _run("scan", str(path)).stdout.splitlines()
    assert rows == ["1\tmention", "1\txref", "6\temail", "6\txref"]


def test_lint_leads(tmp_path: Path) -> None:
    path = tmp_path / "b.md"
    wrapped = [
        "This line is wrapped at roughly seventy columns so that it looks",
        "like a hard wrapped paragraph that GitHub renders as ragged stubs",
        "and ends here.",
    ]
    lines = ["# Title", "", "#### Deep", "", *wrapped, ""]
    lines += ["<details>", "<summary>Log</summary>", "```", "x", "```", "</details>", ""]
    lines += ["| a | b |", "|---|---|", ""]
    path.write_text("\n".join(lines))
    done = _run("lint", str(path))
    assert done.returncode == 1
    assert done.stdout.splitlines() == [
        "1\theading-start",
        "3\theading-jump",
        "5\thard-wrap",
        "10\tdetails-blank",
    ]
    tabled = _run("lint", "--tables", str(path)).stdout.splitlines()
    assert tabled[-1].endswith("table")
    assert "heading-start" not in _run("lint", "--file", str(path)).stdout
    path.write_text("### Ok\n\nOne long line.\n")
    assert _run("lint", str(path)).returncode == 0


def test_scan_title_rows_are_labelled(tmp_path: Path) -> None:
    path = tmp_path / "b.md"
    path.write_text("clean body\n")
    done = _run("scan", "--title", "crash in /home/ann/src", str(path))
    assert (done.returncode, done.stdout) == (1, "title\tlocal-path\n")


def test_lint_flags_open_and_oddly_closed_fences(tmp_path: Path) -> None:
    path = tmp_path / "b.md"
    path.write_text("### A\n\n```sh\nx\n")
    assert _run("lint", str(path)).stdout == "3\tfence-open\n"
    path.write_text("### A\n\n````\n```\nx\n````\n")
    assert _run("lint", str(path)).stdout == "3\tfence-open\n"
    path.write_text("### A\n\n````\n```sh\nx\n```\n````\n")
    assert _run("lint", str(path)).returncode == 0


def test_scan_catches_secrets_in_urls_headers_and_paths(tmp_path: Path) -> None:
    path = tmp_path / "b.md"
    lines = [
        "cd ~/work/api",
        "DB=postgres://u:p@db.example/x",
        "Cookie: session=abc",
        "GET /f?X-Amz-Signature=abc&x=1",
        "peer fe80::1ff:fe23:4567:890a",
        "ok ::1 and 12:30:45 and https://example.com/a?b=1 and ~ alone",
        "",
    ]
    path.write_text("\n".join(lines))
    assert _run("scan", str(path)).stdout.splitlines() == [
        "1\tlocal-path",
        "2\turl-userinfo",
        "2\temail",
        "3\tcookie",
        "4\tsigned-url",
        "5\tip-address",
    ]


def test_lint_flags_markdown_in_summary(tmp_path: Path) -> None:
    path = tmp_path / "b.md"
    path.write_text("### A\n\n<details>\n<summary>**Big** log</summary>\n\nx\n</details>\n")
    assert _run("lint", str(path)).stdout == "4\tsummary-markdown\n"
    path.write_text("### A\n\n<details>\n<summary><b>Big</b> log</summary>\n\nx\n</details>\n")
    assert _run("lint", str(path)).returncode == 0


def test_scan_windows_unc_and_bare_secret(tmp_path: Path) -> None:
    path = tmp_path / "b.md"
    secret = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"  # noqa: S105
    lines = [
        r"open C:\Work\app\x.log",
        r"see \\fileserver\share\a",
        f"AWS_SECRET_ACCESS_KEY {secret}",
        "ok",
    ]
    path.write_text("\n".join(lines))
    rows = _run("scan", str(path)).stdout.splitlines()
    assert rows == ["1\tlocal-path", "2\tlocal-path", "3\tcredential"]


def test_pick_ignores_support_request_and_goencode() -> None:
    names = "support_request.yml\nfeature_request.yml\n"
    assert _run("pick", "proposal", stdin=names).stdout == "feature_request.yml\n"
    assert _run("pick", "proposal", stdin="support_request.yml\n").returncode == 1
    assert _run("goencode", "github.com/Azure/X").stdout == "github.com/!azure/!x\n"


def test_body_check_order_kind_and_summary(tmp_path: Path) -> None:
    path = tmp_path / "b.md"
    heads = ["Summary", "Evidence", "Reproduction", "Summary", "Motivation", "Notes"]
    path.write_text("\n\n".join(f"### {h}" for h in heads) + "\n")
    done = _run("body-check", "defect", str(path))
    assert done.returncode == 1
    assert done.stdout.splitlines() == [
        "5\tout-of-order",
        "7\tduplicate",
        "9\tnot-for-kind",
        "9\tout-of-order",
        "11\tunknown",
    ]
    path.write_text("### Summary\n\n### Reproduction\n\n### Expected\n")
    assert _run("body-check", "defect", str(path)).returncode == 0
    path.write_text("text only\n")
    assert _run("body-check", "task", str(path)).stdout == "0\tmissing-summary\n"


def test_fetch_uses_gh_and_passes_errors_through(tmp_path: Path) -> None:
    gh = tmp_path / "gh"
    gh.write_text('#!/bin/sh\necho "args: $* host: $GH_HOST"\n')
    gh.chmod(0o755)
    env = {**os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}"}

    def run(url: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), "fetch", url],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )

    issue_done = run("https://ghe.example/o/r/issues/7")
    assert issue_done.stdout == (
        "args: issue view 7 --repo o/r --json body --jq .body host: ghe.example\n"
    )
    comment = run("https://github.com/o/r/pull/7#issuecomment-55")
    assert "api repos/o/r/issues/comments/55 --jq .body" in comment.stdout
    review = run("https://github.com/o/r/pull/7#discussion_r12")
    assert "repos/o/r/pulls/comments/12" in review.stdout
    assert run("https://github.com/o/r").returncode == 2
    gh.write_text('#!/bin/sh\necho "Body is too long" >&2\nexit 1\n')
    failed = run("https://github.com/o/r/issues/1")
    assert (failed.returncode, failed.stderr) == (1, "Body is too long\n")


def test_unfilled_skeleton_blocks_even_inside_a_render_fence(tmp_path: Path) -> None:
    form = (
        "name: n\ndescription: d\nbody:\n- type: textarea\n  attributes:\n"
        "    label: Logs\n    render: shell\n  validations:\n    required: true\n"
    )
    skeleton = json.loads(_run("template", "f.yml", stdin=form).stdout)["body"]
    path = tmp_path / "b.md"
    path.write_text(skeleton)
    done = _run("placeholders", str(path))
    assert (done.returncode, done.stdout) == (1, "4\tblocking\n")
    path.write_text("```text\n<DEBUG> trace\n```\n")
    assert _run("placeholders", str(path)).returncode == 0


def test_scan_vendor_token_prefixes(tmp_path: Path) -> None:
    path = tmp_path / "b.md"
    tokens = [
        "sk-proj-" + "a1B2" * 8,
        "AIza" + "x" * 35,
        "npm_" + "a" * 36,
        "sk_live_" + "a" * 24,
        "rk_live_" + "b" * 24,
        "pypi-" + "c" * 40,
    ]
    path.write_text("\n".join(tokens) + "\nplain desk-chair text\n")
    rows = _run("scan", str(path)).stdout.splitlines()
    assert rows == [f"{i}\ttoken" for i in range(1, 7)]
