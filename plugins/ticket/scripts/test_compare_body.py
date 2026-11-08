"""Tests for compare_body.py."""

# ruff: noqa: S101, S603, INP001, D103, PLR2004
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).with_name("compare_body.py")

WRITTEN = """### Summary

Retries hammer the **payment** service when it is down.

- Open the breaker after 5 failures
- See [the runbook](https://example.com/run?id=1&x=2)

<details>
<summary>Trace</summary>

```
KeyError: tenant_id
```

</details>
"""

# jira.md's documented plain-text conversion of WRITTEN.
JIRA_PLAIN = """Summary

Retries hammer the payment service when it is down.

- Open the breaker after 5 failures
- See the runbook (https://example.com/run?id=1&x=2)

Trace
    KeyError: tenant_id
"""

AZURE_HTML = (
    "<h3>Summary</h3><p>Retries hammer the <strong>payment</strong> service when it is"
    " down.</p><ul><li>Open the breaker after 5 failures</li><li>See"
    ' <a href="https://example.com/run?id=1&amp;x=2">the runbook</a></li></ul>'
    "<details><summary>Trace</summary><pre>KeyError: tenant_id</pre></details>"
)


def adf(text: str) -> dict[str, object]:
    return {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": line}]}
            for line in text.splitlines()
            if line
        ],
    }


def compare(tmp_path: Path, fetched: str, *extra: str) -> subprocess.CompletedProcess[str]:
    (tmp_path / "body.md").write_text(WRITTEN)
    (tmp_path / "fetched").write_text(fetched)
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(tmp_path / "body.md"), str(tmp_path / "fetched"), *extra],
        capture_output=True,
        text=True,
        check=False,
    )


def test_markdown_inside_plain_view_output(tmp_path: Path) -> None:
    result = compare(tmp_path, f"WIDGET-482\nTitle: Breaker\nBody:\n{WRITTEN}\nComments: none\n")
    assert result.returncode == 0, result.stdout


def test_jira_plain_text_conversion(tmp_path: Path) -> None:
    assert compare(tmp_path, JIRA_PLAIN).returncode == 0


def test_azure_html_inside_json(tmp_path: Path) -> None:
    fetched = json.dumps(
        {"id": 7, "fields": {"System.Title": "x", "System.Description": AZURE_HTML}}
    )
    assert compare(tmp_path, fetched).returncode == 0


def test_jira_adf_inside_json(tmp_path: Path) -> None:
    fetched = json.dumps({"key": "WIDGET-1", "fields": {"description": adf(JIRA_PLAIN)}})
    assert compare(tmp_path, fetched).returncode == 0


def test_dropped_line_is_a_mismatch(tmp_path: Path) -> None:
    result = compare(tmp_path, JIRA_PLAIN.replace("- Open the breaker after 5 failures\n", ""))
    assert result.returncode == 1
    assert "open the breaker" in result.stdout


def test_unreadable_file_exits_2(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(tmp_path / "missing"), str(tmp_path / "missing")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2


def test_appended_line_in_json_is_a_mismatch(tmp_path: Path) -> None:
    edited = JIRA_PLAIN + "- maria: the cap is 60 seconds now\n"
    result = compare(tmp_path, json.dumps({"fields": {"description": edited}}))
    assert result.returncode == 1


def test_plain_output_says_containment_only(tmp_path: Path) -> None:
    result = compare(tmp_path, f"Body:\n{JIRA_PLAIN}\n- an extra line\n")
    assert result.returncode == 0
    assert "containment" in result.stdout


def test_title_must_read_back(tmp_path: Path) -> None:
    fetched = json.dumps({"fields": {"summary": "Add a breaker!", "description": WRITTEN}})
    assert compare(tmp_path, fetched, "--title", "add a breaker").returncode == 0
    result = compare(tmp_path, fetched, "--title", "Add a circuit breaker")
    assert result.returncode == 1
    assert "title mismatch" in result.stdout


def same(tmp_path: Path, before: str, after: str, *extra: str) -> int:
    (tmp_path / "a").write_text(before)
    (tmp_path / "b").write_text(after)
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--same", str(tmp_path / "a"), str(tmp_path / "b"), *extra],
        capture_output=True,
        text=True,
        check=False,
    ).returncode


def test_same_catches_a_link_only_edit(tmp_path: Path) -> None:
    before = json.dumps({"fields": {"description": "See [runbook](https://x.io/a)."}})
    after = json.dumps({"fields": {"description": "See [runbook](https://x.io/b)."}})
    assert same(tmp_path, before, after, "--field", "fields/description") == 1
    assert same(tmp_path, before, before, "--field", "fields/description") == 0


def test_same_ignores_other_fields_and_whitespace(tmp_path: Path) -> None:
    before = json.dumps({"fields": {"description": "a b", "updated": "1"}})
    after = json.dumps({"fields": {"description": "a b", "updated": "2"}})
    assert same(tmp_path, before, after, "--field", "fields/description") == 0
    assert (
        same(
            tmp_path,
            "Body:\n a  b\n",
            "Body: a b",
        )
        == 0
    )
    assert same(tmp_path, "Body: a b", "Body: a, b") == 1


def test_same_ignores_new_comments_under_a_top_level_body(tmp_path: Path) -> None:
    before = json.dumps({"body": "text", "comments": []})
    after = json.dumps({"body": "text", "comments": [{"body": "new"}]})
    assert same(tmp_path, before, after, "--field", "body") == 0
    assert (
        same(tmp_path, before, json.dumps({"body": "edit", "comments": []}), "--field", "body") == 1
    )


def exact(
    tmp_path: Path, written: str, fetched: dict[str, str], *extra: str
) -> subprocess.CompletedProcess[str]:
    (tmp_path / "w").write_text(written)
    (tmp_path / "f").write_text(json.dumps(fetched))
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--exact",
            str(tmp_path / "w"),
            str(tmp_path / "f"),
            "--field",
            "body",
            *extra,
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def test_exact_keeps_case_and_punctuation(tmp_path: Path) -> None:
    fetched = {"title": "Fix It", "body": "See [Runbook](https://x.io/a).\n\nDone."}
    assert exact(tmp_path, "See [Runbook](https://x.io/a).\nDone.", fetched).returncode == 0
    assert exact(tmp_path, "See [runbook](https://x.io/a). Done.", fetched).returncode == 1
    assert exact(tmp_path, "See [Runbook](https://x.io/a). Done", fetched).returncode == 1


def test_exact_checks_the_title(tmp_path: Path) -> None:
    fetched = {"title": "Fix It", "body": "text"}
    assert exact(tmp_path, "text", fetched, "--title", "fix it").returncode == 0
    assert exact(tmp_path, "text", fetched, "--title", "Other").returncode == 1
