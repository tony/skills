"""Tests for evidence.py: history parsing, transcript filtering, and linking."""

# ruff: noqa: S101, S603, S607, INP001, PLR2004
# pyright: reportAny=false, reportUnusedCallResult=false, reportPrivateUsage=false
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import evidence  # pyright: ignore[reportImplicitRelativeImport]
import pytest


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.email=t@example.com", "-c", "user.name=t", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _repo(path: Path, origin: str = "git@github.com:o/site.git") -> Path:
    path.mkdir(parents=True)
    _git(path, "init", "-q", "-b", "main")
    _git(path, "remote", "add", "origin", origin)
    (path / "README.md").write_text("x\n", encoding="utf-8")
    _git(path, "add", ".")
    _git(path, "commit", "-q", "-m", "docs(readme) start")
    return path


def test_zsh_continuation_lines_join_one_command() -> None:
    """A trailing backslash joins the next line into the same command."""
    text = ": 1:0;git commit -m 'a' \\\n  --amend\n: 2:0;ls\n"
    assert evidence.parse_zsh(text) == [(1, "git commit -m 'a' \\\n  --amend"), (2, "ls")]


def test_zsh_mixed_plain_and_extended_lines() -> None:
    """Plain and extended zsh lines parse in one file."""
    text = "plain one\n: 5:0;extended\nplain two\n"
    assert evidence.parse_zsh(text) == [(None, "plain one"), (5, "extended"), (None, "plain two")]


def test_zsh_metafied_bytes_decode_to_utf8() -> None:
    """Metafied non-ASCII bytes decode back to UTF-8."""
    encoded = "cd ~/wörk".encode()
    metafied = bytearray()
    for byte in encoded:
        if byte >= 0x83:
            metafied += bytes([0x83, byte ^ 0x20])
        else:
            metafied.append(byte)
    assert evidence.unmetafy(bytes(metafied)).decode() == "cd ~/wörk"


def test_attribution_matches_absolute_and_tilde_forms() -> None:
    """A repository path matches in both its absolute and its ~ form."""
    home = str(Path.home())
    entries: list[tuple[int | None, str]] = [
        (1, f"cd {home}/w/site && make"),
        (2, "make test"),
        (3, "cd -"),
        (4, "make test"),
        (5, "tmuxp load ~/w/site"),
    ]
    kept = [c for _, c in evidence.attribute(entries, ["~/w/site"])]
    assert kept == [f"cd {home}/w/site && make", "make test", "tmuxp load ~/w/site"]


def test_unstamped_lines_in_a_stamped_history_do_not_inherit_the_directory() -> None:
    """Harness lines sharing the history file are not credited to the repository."""
    entries: list[tuple[int | None, str]] = [
        (1, "cd ~/w/site"),
        (None, "theirs=kept; trap 'x' EXIT"),
        (None, "cd /tmp/harness"),
        (2, "make test"),
        (None, "cat ~/w/site/README.md"),
    ]
    kept = [c for _, c in evidence.attribute(entries, ["~/w/site"])]
    assert kept == ["cd ~/w/site", "make test", "cat ~/w/site/README.md"]


def test_attribution_ignores_other_repositories_with_the_same_prefix() -> None:
    """A sibling checkout whose name extends the path is not attributed."""
    entries: list[tuple[int | None, str]] = [(1, "cd ~/w/site-old"), (2, "make")]
    assert evidence.attribute(entries, ["~/w/site"]) == []


def test_transcripts_keep_typed_prompts_and_drop_tool_output(tmp_path: Path) -> None:
    """Typed prompts survive; tool output and malformed lines do not."""
    home = str(Path.home())
    rows = [
        {
            "store": "claude.history",
            "text": "update packages",
            "timestamp": "2026-09-01T00:00:00Z",
            "agent": "claude",
            "session_id": "a",
            "origin": {"cwd": f"{home}/w/site/"},
        },
        {
            "store": "claude.projects",
            "text": "Shell cwd was reset to /x",
            "agent": "claude",
            "timestamp": "2026-09-02T00:00:00Z",
            "session_id": "a",
            "origin": {"cwd": f"{home}/w/site"},
        },
        {
            "store": "claude.projects",
            "text": "port that from the sibling repo",
            "agent": "claude",
            "timestamp": "2026-08-01T00:00:00Z",
            "session_id": "b",
            "metadata": {"project": f"{home}/w/old-site/"},
        },
        {"store": "claude.projects", "agent": "claude"},
    ]
    export = tmp_path / "export.ndjson"
    export.write_text("\n".join(json.dumps(r) for r in rows) + "\nnot json\n", encoding="utf-8")

    report = evidence.cmd_transcripts(export, limit=10)

    assert report["records"] == 3
    assert report["by_cwd"] == [
        {
            "cwd": "~/w/site",
            "records": 2,
            "sessions": 1,
            "first": "2026-09-01",
            "last": "2026-09-02",
        },
        {
            "cwd": "~/w/old-site",
            "records": 1,
            "sessions": 1,
            "first": "2026-08-01",
            "last": "2026-08-01",
        },
    ]
    assert [p["text"] for p in report["prompts"]] == [
        "port that from the sibling repo",
        "update packages",
    ]


def test_link_state_classifies_each_layout(tmp_path: Path) -> None:
    """Each .claude/skills layout gets its own state."""
    skills = tmp_path / ".claude" / "skills"
    assert evidence.link_state(skills) == ("absent", [])

    skills.mkdir(parents=True)
    (skills / "a").symlink_to("../../.agents/skills/a")
    assert evidence.link_state(skills) == ("per-skill-links", ["a"])

    (skills / "b").symlink_to("/elsewhere/b")
    assert evidence.link_state(skills) == ("foreign-links", ["b"])

    (skills / "c").mkdir()
    assert evidence.link_state(skills) == ("real-skills", ["c"])


@pytest.mark.integration(reason="executes native Git repository queries")
def test_git_summary_counts_direct_and_semi_linear_merges(tmp_path: Path) -> None:
    """Direct commits, merges, merge shape, and agent-file commits are counted."""
    repo = _repo(tmp_path / "site")
    (repo / "pkg").mkdir()
    (repo / "pkg" / "lib").mkdir()
    (repo / "pkg" / "lib" / "a.py").write_text("a\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "feat(lib) add a")
    _git(repo, "switch", "-q", "-c", "topic")
    (repo / "AGENTS.md").write_text("rules\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "ai(rules) add AGENTS.md")
    _git(repo, "switch", "-q", "main")
    _git(repo, "merge", "-q", "--no-ff", "-m", "ai(rules) add AGENTS.md (#1)", "topic")

    report = evidence.cmd_git(repo, since="10 years ago", top_n=5)

    assert report["trunk"] == "main"
    assert report["commits"] == 3
    assert report["first_parent_direct"] == 2
    assert report["first_parent_merges"] == 1
    assert report["merges_semi_linear"] == 1
    assert report["merges_numbered"] == 1
    assert ("pkg/lib", 1) in report["hot_paths"]
    assert len(report["agent_file_commits"]) == 1


@pytest.mark.integration(reason="executes native Git repository queries")
def test_paths_finds_sibling_checkouts_of_the_same_origin(tmp_path: Path) -> None:
    """A sibling clone of the same origin is found; another origin is not."""
    repo = _repo(tmp_path / "work" / "site")
    _repo(tmp_path / "work" / "site-old", origin="https://github.com/O/site")
    _repo(tmp_path / "work" / "other", origin="git@github.com:o/other.git")

    report = evidence.cmd_paths(repo, [tmp_path / "work"])

    names = sorted(Path(p).name for p in report["checkouts"])
    assert names == ["site", "site-old"]
    assert report["cwd_globs"] == ["*site*"]


@pytest.mark.integration(reason="executes native Git repository queries")
def test_link_replaces_per_skill_links_and_stages_one_link(tmp_path: Path) -> None:
    """Per-skill links become one staged directory link, idempotently."""
    repo = _repo(tmp_path / "site")
    (repo / ".agents" / "skills" / "a").mkdir(parents=True)
    (repo / ".agents" / "skills" / "a" / "SKILL.md").write_text("---\n", encoding="utf-8")
    links = repo / ".claude" / "skills"
    links.mkdir(parents=True)
    (links / "a").symlink_to("../../.agents/skills/a")
    _git(repo, "add", "--force", ".")
    _git(repo, "commit", "-q", "-m", "chore(skills) add a")

    assert evidence.cmd_link(repo, check=True)["changed"] is False
    report = evidence.cmd_link(repo, check=False)

    assert report == {"state": "per-skill-links", "entries": ["a"], "changed": True}
    assert str(links.readlink()) == "../.agents/skills"
    assert (links / "a" / "SKILL.md").is_file()
    staged = _git(repo, "diff", "--cached", "--name-status").split("\n")
    assert sorted(line for line in staged if line) == [
        "A\t.claude/skills",
        "D\t.claude/skills/a",
    ]
    assert evidence.cmd_link(repo, check=False)["changed"] is False


@pytest.mark.integration(reason="executes native Git repository queries")
def test_link_refuses_real_skill_directories(tmp_path: Path) -> None:
    """Real skill directories under .claude/skills stop the link untouched."""
    repo = _repo(tmp_path / "site")
    (repo / ".agents" / "skills").mkdir(parents=True)
    (repo / ".claude" / "skills" / "local").mkdir(parents=True)

    with pytest.raises(evidence.UsageError, match="real-skills"):
        evidence.cmd_link(repo, check=False)
    assert (repo / ".claude" / "skills" / "local").is_dir()


@pytest.mark.integration(reason="executes native Git repository queries")
def test_main_exits_2_outside_a_repository(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Outside a repository the CLI exits 2 with a message."""
    assert evidence.main(["--repo", str(tmp_path), "git"]) == 2
    assert capsys.readouterr().err


def test_transcripts_keep_only_records_under_named_directories(tmp_path: Path) -> None:
    """Records outside the kept directories drop out of every count."""
    home = str(Path.home())
    rows = [
        {"store": "claude.history", "text": "a", "origin": {"cwd": f"{home}/w/cv"}},
        {"store": "claude.history", "text": "b", "origin": {"cwd": f"{home}/w/cv-panda"}},
        {"store": "claude.history", "text": "c", "origin": {"cwd": f"{home}/w/cv/pkg"}},
    ]
    export = tmp_path / "export.ndjson"
    export.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")

    report = evidence.cmd_transcripts(export, limit=10, keep=["~/w/cv"])

    assert report["records"] == 2
    assert sorted(row["cwd"] for row in report["by_cwd"]) == ["~/w/cv", "~/w/cv/pkg"]


@pytest.mark.integration(reason="executes native Git repository queries")
def test_link_check_reports_state_before_any_skill_exists(tmp_path: Path) -> None:
    """The precondition check works before commit 1 creates .agents/skills."""
    repo = _repo(tmp_path / "site")

    assert evidence.cmd_link(repo, check=True) == {
        "state": "absent",
        "entries": [],
        "changed": False,
    }
    with pytest.raises(evidence.UsageError, match="write the skills first"):
        evidence.cmd_link(repo, check=False)
