"""Version order, tag namespaces, changelog sections and leftover scans."""

# ruff: noqa: S101, INP001, D103, S603, S607
import doctest
import importlib.util
import io
import json
import subprocess
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest
import release_plan as plan


def cli(*argv: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        status = plan.main(list(argv))
    return status, out.getvalue(), err.getvalue()


def test_doctests() -> None:
    # Copies of this vendored module share a basename, so pytest collects none.
    script = Path(__file__).with_name("release_plan.py")
    spec = importlib.util.spec_from_file_location("release_plan_doctests", script)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = doctest.testmod(module)
    assert result.attempted > 0
    assert result.failed == 0


def test_compare_orders_prerelease_below_its_final_in_both_schemes() -> None:
    assert plan.compare("0.1.9a2", "0.1.9")["order"] == "after"
    assert plan.compare("1.0.0-rc.1", "1.0.0")["scheme"] == "semver"
    assert plan.compare("0.1.0-next.9", "0.1.0-next.10")["order"] == "after"
    assert plan.compare("0.1.9", "0.2.0a0")["order"] == "after"


@pytest.mark.parametrize(
    ("old", "new", "reason"),
    [
        ("0.1.9", "0.1.9a2", "0.1.9a2 does not sort after 0.1.9"),
        ("0.1.9", "0.1.9.0", "equal to"),
        ("0.1.9a1", "0.2.0-next.0", "mix SemVer prerelease and PEP 440"),
        ("0.1.9", "v0.1.10", "not a SemVer, PEP 440 or plain dotted version"),
    ],
)
def test_compare_refuses_with_a_one_line_reason(old: str, new: str, reason: str) -> None:
    status, out, err = cli("compare", old, new)
    assert (status, out) == (1, "")
    assert reason in err
    assert err.count("\n") == 1


def test_candidates_cover_each_track() -> None:
    def versions(current: str, style: str | None = None) -> list[str]:
        found, _ = plan.candidates_for(current, style, ["rc"])
        return [c.version for c in found]

    assert versions("0.1.9a1") == ["0.1.9a2", "0.1.9"]
    assert versions("0.1.9b1") == ["0.1.9b2", "0.1.9", "0.1.9rc0"]
    assert versions("0.1.0-next.11") == ["0.1.0-next.12", "0.1.0"]
    assert versions("0.1.9", "pep440:a") == [
        "0.1.10",
        "0.2.0",
        "1.0.0",
        "0.1.10a0",
        "0.2.0a0",
    ]
    assert versions("0.1.9")[-1] == "1.0.0"


def test_candidates_kind_filter_flags_an_ambiguous_prerelease() -> None:
    status, out, _ = cli(
        "candidates", "--current", "0.1.9", "--kind", "prerelease", "--pre-style", "semver:next"
    )
    record = json.loads(out)
    assert status == 0
    assert record["ambiguous"] is True
    assert [c["version"] for c in record["candidates"]] == ["0.1.10-next.0", "0.2.0-next.0"]
    status, _, err = cli("candidates", "--current", "0.1.9", "--kind", "final")
    assert status == 1
    assert "no final candidate" in err


def test_tags_rank_a_final_above_its_prerelease() -> None:
    names = ["v1.0.0-rc.1", "v1.0.0", "v0.9.0", "pkg@0.1.9", "pkg@0.1.10", "nightly"]
    tags, skipped = plan.parse_tags(names)
    by_prefix = {n["prefix"]: n for n in plan.namespaces(tags)}
    assert skipped == 1
    assert by_prefix["v"]["latest_tag"] == "v1.0.0"
    assert by_prefix["pkg@"]["latest_tag"] == "pkg@0.1.10"


def test_a_namespace_that_mixes_schemes_still_ranks_finals_first() -> None:
    names = ["v1.0.0-rc.1", "v1.0.0", "v0.2.0-next.2", "v0.2.0", "v0.1.9a2", "v0.1.9"]
    (record,) = plan.namespaces(plan.parse_tags(names)[0])
    assert (record["mixed"], record["latest_tag"]) == (True, "v1.0.0")


def test_tag_prefix_matches_the_whole_version_only() -> None:
    tags, _ = plan.parse_tags(["v10.1.9", "pkg@0.1.9"])
    assert plan.resolve_prefix(tags, "0.1.9") == ("pkg@", "current-version", ["pkg@"])
    assert plan.resolve_prefix(tags, "0.5.0")[:2] == (None, "ambiguous")
    assert plan.resolve_prefix([], "0.1.0")[:2] == ("v", "default")


@pytest.mark.integration
def test_tags_command_reads_a_repository(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main", str(tmp_path)], check=True)
    for name in ("v0.1.9", "v0.2.0a1"):
        subprocess.run(
            [
                "git",
                "-C",
                str(tmp_path),
                "-c",
                "user.name=t",
                "-c",
                "user.email=t@e.invalid",
                "commit",
                "-q",
                "--allow-empty",
                "-m",
                name,
            ],
            check=True,
        )
        subprocess.run(["git", "-C", str(tmp_path), "tag", name], check=True)
    status, out, _ = cli("tags", "--repo", str(tmp_path), "--version", "0.1.9", "--new", "0.2.0a1")
    record = json.loads(out)
    assert status == 0
    assert (record["tag_prefix"], record["new_tag"], record["new_tag_exists"]) == (
        "v",
        "v0.2.0a1",
        True,
    )
    assert record["namespaces"][0]["latest_tag"] == "v0.2.0a1"
    assert record["namespaces"][0]["pre_style"] == "pep440:a"


CHANGES = """# Changelog

## demo 0.63.x (Yet to be released)

<!-- To maintainers: add notes below -->

<!-- KEEP THIS PLACEHOLDER - DO NOT REMOVE OR MODIFY THIS LINE -->
_Notes on the upcoming release will go here._
<!-- END PLACEHOLDER -->

### Fixes

## demo 0.62.0 (2026-01-01)

- Something shipped
"""


def test_unreleased_section_with_only_placeholders_is_empty(tmp_path: Path) -> None:
    path = tmp_path / "CHANGES.md"
    path.write_text(CHANGES)
    record = plan.unreleased_command(path, [])
    assert (record["empty"], record["entry_lines"], record["subheadings"]) == (True, 0, 1)
    assert (record["heading_line"], record["end_line"]) == (3, 12)


def test_unreleased_prose_and_unknown_placeholders_count_as_entries(tmp_path: Path) -> None:
    path = tmp_path / "CHANGES.md"
    path.write_text(CHANGES.replace("### Fixes\n", "Prose note.\n"))
    assert plan.unreleased_command(path, [])["entry_lines"] == 1
    path.write_text(CHANGES.replace("### Fixes\n", "_Nothing yet._\n"))
    assert plan.unreleased_command(path, [])["empty"] is False
    assert plan.unreleased_command(path, ["Nothing yet."])["empty"] is True


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("# Changelog\n\n## 1.0.0 (2026-01-01)\n", "0 unreleased headings"),
        ("## Unreleased\n\n## [Unreleased]\n", "2 unreleased headings"),
        ("## Unreleased\n\n<!-- open\n", "unterminated comment"),
    ],
)
def test_unreleased_refuses_ambiguous_files(tmp_path: Path, text: str, reason: str) -> None:
    path = tmp_path / "CHANGES.md"
    path.write_text(text)
    status, out, err = cli("unreleased", str(path))
    assert (status, out) == (1, "")
    assert reason in err


@pytest.mark.integration
def test_leftover_ignores_lockfiles_changelogs_and_longer_versions(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main", str(tmp_path)], check=True)
    files = {
        "pkg/__about__.py": '__version__ = "0.1.9"\n',
        "uv.lock": 'version = "0.1.9"\n',
        "CHANGES.md": "## 0.1.9\n",
        "docs/index.md": "see 10.1.9, 0.1.90, 0.1.9a1 and 0.1.9.1\n",
    }
    for name, text in files.items():
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text(text)
    status, out, err = cli("leftover", "--repo", str(tmp_path), "--old", "0.1.9")
    record = json.loads(out)
    assert status == 1
    assert record["occurrences"] == [{"path": "pkg/__about__.py", "line": 1}]
    assert "1 occurrence(s) of 0.1.9 remain" in err
    (tmp_path / "pkg/__about__.py").write_text('__version__ = "0.2.0"\n')
    assert cli("leftover", "--repo", str(tmp_path), "--old", "0.1.9")[0] == 0


def test_compare_refuses_a_semver_suffix_in_a_pep440_project() -> None:
    assert plan.compare("0.1.9", "0.2.0-next.1")["order"] == "after"
    with pytest.raises(
        plan.Refusal, match=r"0\.2\.0-next\.1 is a semver version in a pep440 project"
    ):
        plan.compare("0.1.9", "0.2.0-next.1", "pep440")
    assert plan.compare("0.1.9", "0.2.0a1", "pep440")["scheme"] == "pep440"
    status, _, err = cli("compare", "0.1.9", "0.2.0-next.1", "--scheme", "pep440")
    assert status == 1
    assert "semver version in a pep440 project" in err


@pytest.mark.integration
def test_compare_reads_the_project_scheme_from_tags(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main", str(tmp_path)], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "-c", "user.name=t", "-c", "user.email=t@e.invalid",
         "commit", "-q", "--allow-empty", "-m", "x"],
        check=True,
    )  # fmt: skip
    for name in ("v0.1.8a1", "v0.1.9"):
        subprocess.run(["git", "-C", str(tmp_path), "tag", name], check=True)
    status, _, err = cli("compare", "0.1.9", "0.2.0-next.1", "--repo", str(tmp_path))
    assert (status, "pep440 project" in err) == (1, True)
    assert cli("compare", "0.1.9", "0.2.0a0", "--repo", str(tmp_path))[0] == 0


def test_next_target_advances_the_series_or_the_prerelease() -> None:
    assert plan.next_target("1.70.1")["target"] == "1.71.x"
    assert plan.next_target("0.63.0")["target"] == "0.64.x"
    assert plan.next_target("0.0.1a35")["target"] == "0.0.1a36"
    assert plan.next_target("0.1.0-next.11")["target"] == "0.1.0-next.12"
    status, out, _ = cli("next-target", "1.70.1")
    assert (status, json.loads(out)["track"]) == (0, "stable")
    assert cli("next-target", "7")[0] == 1
