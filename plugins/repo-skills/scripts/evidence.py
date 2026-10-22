#!/usr/bin/env python3
"""Gather repository evidence for ``/repo-skills:derive`` and link its skills.

Every subcommand prints one JSON document on stdout. Paths under the home
directory are written with ``~``.

``paths``
    Checkouts sharing this repository's origin, its worktrees, earlier
    session directories, and the transcript ``cwd`` globs covering them.
``git``
    Commit-subject heads, direct versus merged trunk commits, merge shape,
    the most-touched paths, and commits to agent instruction files.
``shell``
    Shell-history commands attributed to the repository by ``cd`` tracking
    or by naming one of its paths.
``transcripts``
    An agentgrep NDJSON export grouped by working directory, keeping the
    human-typed prompts and dropping tool output.
``link``
    Replace per-skill links under ``.claude/skills`` with one link to
    ``../.agents/skills`` and stage it; ``--check`` only reports.

Exits 2 with a message on stderr on a usage or repository error.
"""

# ruff: noqa: S603, S607
# pyright: reportAny=false, reportUnusedCallResult=false
from __future__ import annotations

import argparse
import collections
import json
import os
import posixpath
import re
import subprocess
import sys
import typing as t
from pathlib import Path

_AGENT_FILES = (
    ":(glob)**/AGENTS.md",
    ":(glob)**/CLAUDE.md",
    ":(glob)**/GEMINI.md",
    ":(glob)**/.agents/**",
    ":(glob)**/.claude/**",
    ":(glob)**/.codex/**",
    ":(glob)**/.cursor/**",
    ".github/copilot-instructions.md",
)
_TOOL_OUTPUT_PREFIXES = (
    r"Shell cwd was reset",
    r"File created successfully",
    r"The file \S+ has been ",
    r"Exit code \d",
    r"total \d",
    r"Launching skill",
    r"Async agent launched",
    r"Command running in background",
    r"Todos have",
    r"Web search results",
    r"Found \d+ files",
    r"No files found",
    r"Applied \d+ edit",
    r"Base directory for this skill",
    r"This session is being continued",
    r"Caveat:",
    r"<system-reminder",
    r"<local-command",
    r"<command-",
    r"<task-notification",
    r"<bash-",
    r"\[Request interrupted",
    r"Review this change for security",
)
_TOOL_OUTPUT = re.compile("^(?:" + "|".join(_TOOL_OUTPUT_PREFIXES) + ")")
_STRUCTURED = re.compile(r"(?:-{3}|={3}|#{3,}|\$ |[{<\[]|@@ |diff --git|\+{3} |[0-9a-f]{7,40}\s)")
_VALUE = r"(?:\"[^\"]*\"|'[^']*'|\S+)"
_TOKEN_SHAPES = (
    r"\bgh[pousr]_[A-Za-z0-9]{20,}",
    r"\bgithub_pat_\w{20,}",
    r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b",
    r"\bxox[abposr]-[A-Za-z0-9-]{10,}",
    r"\bsk-[A-Za-z0-9_-]{20,}",
    r"\bglpat-[\w-]{20,}",
    r"\bAIza[\w-]{35}\b",
)
_CREDENTIAL_NAME = r"[A-Z0-9_]*(?:token|secret|passw(?:or)?d|api_?key|credential)[A-Z0-9_]*"
_REDACTIONS = (
    (
        re.compile(r"(?i)\b(" + _CREDENTIAL_NAME + r")\s*=\s*" + _VALUE),
        r"\1=…",
    ),
    (re.compile(r"((?:^|\s)(?:-u|--user)[ =]?[^\s:]+:)\S+"), r"\1…"),
    (re.compile(r"(\bmysql(?:admin|dump)?\b[^|;&\n]*\s-p)(?=\S)\S+"), r"\1…"),
    (
        re.compile(r"(?i)(--(?:token|password|passwd|secret|api-key|apikey)(?:=|\s+))" + _VALUE),
        r"\1…",
    ),
    (re.compile(r"(?i)\b(authorization:\s*(?:bearer|basic|token)\s+)[^\s'\"]+"), r"\1…"),
    (re.compile(r"\b([a-z][a-z0-9+.-]*://[^/\s:@]+:)[^@\s/]+@"), r"\1…@"),
    (re.compile("|".join(_TOKEN_SHAPES)), "…"),
)
_CD_TARGET = r"(\"[^\"]*\"|'[^']*'|[^\s;&|]*)"
_CD = re.compile(r"(?:^|[;&|]\s*)(?:cd|pushd)(?=\s|$|[;&|])[ \t]*(?:--[ \t]+)?" + _CD_TARGET)
_ZSH_EXTENDED = re.compile(r"^: (\d+):\d+;(.*)$")
_ZSH_META = 0x83
_NESTED_DEPTH = 3
_PROMPT_MAX_CHARS = 1500
_PROMPT_MAX_LINES = 12
_MERGES_CHECKED = 50
_PR_NUMBER = re.compile(r"\(#\d+\)$")


class UsageError(Exception):
    """A request the script refuses; the message goes to stderr with exit 2."""


class PathsReport(t.TypedDict):
    """Known locations of the repository."""

    root_name: str
    origin: str | None
    checkouts: list[str]
    session_dirs: list[str]
    other_session_dirs: list[str]
    cwd_globs: list[str]


class GitReport(t.TypedDict):
    """Commit history on the trunk since a date."""

    trunk: str
    since: str
    commits: int
    first_parent_direct: int
    direct_numbered: int
    first_parent_merges: int
    merges_checked: int
    merges_semi_linear: int
    merges_numbered: int
    subject_heads: list[tuple[str, int]]
    hot_paths: list[tuple[str, int]]
    agent_file_commits: list[str]


class ShellSource(t.TypedDict):
    """One shell's history, attributed to the repository."""

    shell: str
    file: str
    entries: int
    attributed: int
    heads: list[tuple[str, int]]
    recent: list[str]


class ShellReport(t.TypedDict):
    """Every shell history found."""

    repo_paths: list[str]
    sources: list[ShellSource]
    unreadable: list[str]


class CwdRow(t.TypedDict):
    """Transcript records from one working directory."""

    cwd: str
    records: int
    sessions: int
    first: str
    last: str


class Prompt(t.TypedDict):
    """One human-typed prompt."""

    date: str
    agent: str
    cwd: str
    text: str


class Scan(t.TypedDict):
    """How far agentgrep's search got, from the export's summary record."""

    state: str
    reason: str | None
    effort_requested: str | None
    effort_completed: str | None
    sources_failed: int
    sources_bounded: int
    sources_skipped: int


class TranscriptReport(t.TypedDict):
    """A transcript export grouped by directory, with its typed prompts."""

    scan: Scan | None
    records: int
    by_cwd: list[CwdRow]
    history_agents: list[str]
    prompts_total: int
    prompts: list[Prompt]


class LinkReport(t.TypedDict):
    """What ``link`` found and whether it changed anything."""

    state: str
    entries: list[str]
    changed: bool


def tilde(path: str) -> str:
    """Write a path under the home directory with ``~``.

    >>> home = str(Path.home())
    >>> tilde(home + "/work/x")
    '~/work/x'
    >>> tilde("/opt/x")
    '/opt/x'
    """
    home = str(Path.home())
    if path == home:
        return "~"
    if path.startswith(home + os.sep):
        return "~" + path[len(home) :]
    return path


def normalize_remote(url: str) -> str:
    """Reduce a git remote URL to ``host/owner/name`` for comparison.

    >>> normalize_remote("git@github.com:Tony/Site.git")
    'github.com/tony/site'
    >>> normalize_remote("https://github.com/tony/site")
    'github.com/tony/site'
    >>> normalize_remote("ssh://git@github.com/tony/site.git/")
    'github.com/tony/site'
    >>> normalize_remote("ssh://git@github.com:22/tony/site.git")
    'github.com/tony/site'
    """
    text = url.strip().rstrip("/")
    text = re.sub(r"\.git$", "", text)
    has_scheme = bool(re.match(r"[a-z+]+://", text))
    text = re.sub(r"^[a-z+]+://", "", text)
    text = re.sub(r"^[^@/]+@", "", text)
    if has_scheme:
        return re.sub(r"^([^/:]+):\d+/", r"\1/", text).lower()
    return text.replace(":", "/", 1).lower()


def covering_globs(root_name: str, checkouts: list[str]) -> list[str]:
    """Return the fewest ``*name*`` globs that match every checkout path.

    The repository's own name comes first. A checkout whose path already
    contains a kept name adds nothing, so a worktree under a directory
    named for the repository needs no glob. Any other checkout is matched
    on its last two path components, never on a bare generated basename.

    >>> covering_globs("site", ["~/w/site", "~/w/site-oxc", "~/.wt/site__x/esk",
    ...                         "~/.wt/esk", "~/w/renamed", "~/top"])
    ['*.wt/esk*', '*/top*', '*site*', '*w/renamed*']
    """
    kept = [root_name]
    for path in sorted(set(checkouts), key=len):
        if not any(name in path for name in kept):
            parent, _, name = path.rstrip("/").rpartition("/")
            tail = Path(parent).name
            kept.append(f"{tail}/{name}" if tail not in {"", "~"} else f"/{name}")
    return sorted(f"*{name}*" for name in kept)


def encode_session_dir(name: str) -> str:
    """Encode a path or name the way Claude Code names its project folders.

    >>> encode_session_dir("tony.nl")
    'tony-nl'
    >>> encode_session_dir("/home/d/w/tony.nl")
    '-home-d-w-tony-nl'
    """
    return re.sub(r"[^A-Za-z0-9]", "-", name)


def subject_head(subject: str) -> str:
    """Return a commit subject's first token: its type, scope, or file form.

    >>> subject_head("js(deps[dev]) oxfmt 0.72.0 -> 0.73.0")
    'js(deps[dev])'
    >>> subject_head("biome.jsonc: Update to 2.5.9")
    'biome.jsonc:'
    >>> subject_head("")
    ''
    """
    parts = subject.split(maxsplit=1)
    return parts[0] if parts else ""


def path_bucket(path: str) -> str:
    """Bucket a changed path by its first two components when it is nested.

    >>> path_bucket("packages/react/src/App.tsx")
    'packages/react'
    >>> path_bucket("src/app.py")
    'src'
    >>> path_bucket("README.md")
    'README.md'
    """
    parts = path.split("/")
    if len(parts) >= _NESTED_DEPTH:
        return "/".join(parts[:2])
    return parts[0]


def unmetafy(data: bytes) -> bytes:
    r"""Undo zsh's history metafication of bytes at or above 0x83.

    >>> unmetafy(bytes([0x61, 0x83, 0xA3, 0x62]))
    b'a\x83b'
    """
    out = bytearray()
    meta = False
    for byte in data:
        if meta:
            out.append(byte ^ 0x20)
            meta = False
        elif byte == _ZSH_META:
            meta = True
        else:
            out.append(byte)
    return bytes(out)


def parse_zsh(text: str) -> list[tuple[int | None, str]]:
    r"""Parse zsh history in extended, plain, or mixed form.

    A line ending in a backslash continues the command on the next line.

    >>> parse_zsh(": 10:0;ls\nplain cmd\n")
    [(10, 'ls'), (None, 'plain cmd')]
    """
    entries: list[tuple[int | None, str]] = []
    continuing = False
    for line in text.split("\n"):
        match = _ZSH_EXTENDED.match(line)
        if match:
            entries.append((int(match.group(1)), match.group(2)))
        elif continuing and entries:
            stamp, command = entries[-1]
            entries[-1] = (stamp, command + "\n" + line)
        elif line.strip():
            entries.append((None, line))
        else:
            continuing = False
            continue
        continuing = entries[-1][1].endswith("\\")
    return entries


def parse_bash(text: str) -> list[tuple[int | None, str]]:
    r"""Parse bash history, reading ``#<epoch>`` lines as timestamps.

    >>> parse_bash("#100\ngit status\nls\n")
    [(100, 'git status'), (None, 'ls')]
    """
    entries: list[tuple[int | None, str]] = []
    stamp: int | None = None
    for line in text.split("\n"):
        if re.fullmatch(r"#\d+", line):
            stamp = int(line[1:])
        elif line.strip():
            entries.append((stamp, line))
            stamp = None
    return entries


def parse_fish(text: str) -> list[tuple[int | None, str]]:
    r"""Parse fish history's ``- cmd:`` and ``when:`` records.

    >>> parse_fish("- cmd: cd ~/x\n  when: 5\n- cmd: ls\n")
    [(5, 'cd ~/x'), (None, 'ls')]
    """
    entries: list[tuple[int | None, str]] = []
    for line in text.split("\n"):
        if line.startswith("- cmd: "):
            entries.append((None, line[len("- cmd: ") :].replace("\\n", "\n")))
        elif line.startswith("  when: ") and entries and entries[-1][0] is None:
            entries[-1] = (int(line.split(":", 1)[1]), entries[-1][1])
    return entries


def next_cwd(cwd: str | None, target: str) -> str | None:
    """Return the tracked directory after ``cd <target>``.

    Quotes are stripped, ``$HOME`` becomes ``~``, and ``.`` and ``..`` are
    resolved. ``cd -``, a relative target from an unknown directory, and a
    target that still holds a variable or command substitution leave the
    directory unknown.

    >>> next_cwd(None, "~/w")
    '~/w'
    >>> next_cwd("~/w", "site")
    '~/w/site'
    >>> next_cwd("~/w/site", "..")
    '~/w'
    >>> next_cwd(None, '"$HOME/w/site"')
    '~/w/site'
    >>> next_cwd(None, "~/w/site/..")
    '~/w'
    >>> next_cwd("/tmp", "")
    '~'
    >>> next_cwd(None, "..") is None
    True
    >>> next_cwd("~/w/site", "$OTHER") is None
    True
    """
    target = target.strip("\"'")
    target = re.sub(r"^\$(?:HOME\b|\{HOME\})", "~", target)
    if not target:
        return "~"
    if target == "-" or "$" in target or "`" in target:
        return None
    if not target.startswith(("/", "~")):
        if cwd is None:
            return None
        target = cwd.rstrip("/") + "/" + target
    return posixpath.normpath(target)


def attribute(
    entries: list[tuple[int | None, str]],
    repo_paths: list[str],
) -> list[tuple[int | None, str]]:
    """Keep commands run inside, or naming, one of the repository's paths.

    ``cd`` and ``pushd`` move the tracked directory as ``next_cwd``
    describes. A line counts when the directory is inside the repository
    before or after it, so a command run there before a ``cd`` away is
    kept. The tracking is approximate across shell sessions.

    When some entries carry timestamps, an unstamped entry was written by
    something other than the interactive shell, such as a test harness
    sharing the history file. It neither moves nor inherits the tracked
    directory, and counts only when it names a repository path.

    >>> entries = [(1, "cd ~/w/site"), (2, "make test"), (3, "cd docs"),
    ...            (4, "ls"), (5, "cd /tmp"), (6, "vim ~/w/site/README.md")]
    >>> [c for _, c in attribute(entries, ["~/w/site"])]
    ['cd ~/w/site', 'make test', 'cd docs', 'ls', 'cd /tmp', 'vim ~/w/site/README.md']
    """
    home = str(Path.home())
    forms: list[str] = []
    for path in repo_paths:
        forms.append(path)
        if path.startswith("~"):
            forms.append(home + path[1:])
        elif path.startswith(home):
            forms.append("~" + path[len(home) :])
    mention = re.compile(
        "(?:" + "|".join(re.escape(f.rstrip("/")) for f in forms) + r")(?=$|[/\s'\";&|)])"
    )
    stamped = any(stamp is not None for stamp, _ in entries)
    cwd: str | None = None
    kept: list[tuple[int | None, str]] = []
    for stamp, command in entries:
        tracked = stamp is not None or not stamped
        before = tracked and cwd is not None and bool(mention.match(cwd))
        if tracked:
            for target in _CD.findall(command):
                cwd = next_cwd(cwd, target)
        inside = before or (tracked and cwd is not None and bool(mention.match(cwd)))
        if inside or mention.search(command):
            kept.append((stamp, command))
    return kept


def command_head(command: str) -> str:
    """Return the first two words of a command, or one for a bare word.

    >>> command_head("pnpm run test --watch")
    'pnpm run'
    >>> command_head("ls")
    'ls'
    """
    return " ".join(command.split()[:2])


def redact(text: str) -> str:
    """Mask credentials: assigned or flagged values, auth headers, URL passwords, tokens.

    >>> redact('GH_TOKEN=abc123 gh pr list')
    'GH_TOKEN=… gh pr list'
    >>> redact('export TOKEN="abc def" && run')
    'export TOKEN=… && run'
    >>> redact("gh auth --token ghp_abc")
    'gh auth --token …'
    >>> redact("curl -H 'Authorization: Bearer abc.def'")
    "curl -H 'Authorization: Bearer …'"
    >>> redact("psql postgres://u:pw@host/db")
    'psql postgres://u:…@host/db'
    >>> redact("curl -u admin:hunter2 https://x")
    'curl -u admin:… https://x'
    >>> redact("mysql -uroot -phunter2 db; mkdir -p out")
    'mysql -uroot -p… db; mkdir -p out'
    >>> redact("SECRET_KEY = abc")
    'SECRET_KEY=…'
    >>> redact("echo ghp_" + "a" * 36 + " | gh auth login --with-token")
    'echo … | gh auth login --with-token'
    """
    for pattern, replacement in _REDACTIONS:
        text = pattern.sub(replacement, text)
    return text


def is_human_prompt(store: str, text: str) -> bool:
    """Decide whether a transcript record is a human-typed prompt.

    Prompt-history stores hold only typed prompts. Conversation stores also
    record tool results under the user role, and sub-agent stores hold
    prompts one agent wrote for another. These rules screen a conversation
    store; ``cmd_transcripts`` uses them only for an agent that has no
    prompt-history store.

    >>> is_human_prompt("claude.history", "anything at all")
    True
    >>> is_human_prompt("claude.projects_subagents", "Review the diff for bugs")
    False
    >>> is_human_prompt("claude.projects", "fix the flaky test please")
    True
    >>> is_human_prompt("claude.projects", "Shell cwd was reset to /x")
    False
    >>> is_human_prompt("claude.projects", "--- branch --- main")
    False
    >>> [is_human_prompt("cursor.state", t) for t in
    ...  ['"quote" this', "1. fix it", "#123 fix", "日本語で説明して", "The file upload fails"]]
    [True, True, True, True, True]
    """
    if "subagent" in store:
        return False
    if store.endswith(".history"):
        return bool(text.strip())
    stripped = text.strip()
    if (
        not stripped
        or len(stripped) > _PROMPT_MAX_CHARS
        or stripped.count("\n") > _PROMPT_MAX_LINES
    ):
        return False
    return not (_TOOL_OUTPUT.match(stripped) or _STRUCTURED.match(stripped))


def _git(repo: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", "-c", "core.quotepath=off", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise UsageError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout


def toplevel(path: Path) -> Path:
    """Return the repository's top-level directory, or raise ``UsageError``."""
    return Path(_git(path, "rev-parse", "--show-toplevel").strip())


def trunk_ref(repo: Path) -> str:
    """Return the trunk: ``origin``'s default branch, then ``main`` or ``master``.

    Remote branches come before local ones, and a name that no longer
    resolves, such as a stale ``origin/HEAD``, is skipped. Only a repository
    with none of them falls back to the current branch.
    """
    head = _git(repo, "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD", check=False)
    named = head.strip().replace("refs/remotes/", "", 1)
    for ref in (named, "origin/main", "origin/master", "main", "master"):
        if ref and _git(repo, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}", check=False):
            return ref
    return _git(repo, "rev-parse", "--abbrev-ref", "HEAD").strip()


def _checkout_remote(path: Path) -> str | None:
    try:
        if not (path.is_dir() and (path / ".git").exists()):
            return None
    except OSError:
        return None
    url = _git(path, "config", "--get", "remote.origin.url", check=False).strip()
    return normalize_remote(url) if url else None


def cmd_paths(repo: Path, roots: list[Path]) -> PathsReport:
    """Collect every known location of the repository."""
    top = toplevel(repo)
    origin_url = _git(top, "config", "--get", "remote.origin.url", check=False).strip()
    origin = normalize_remote(origin_url) if origin_url else None
    worktrees = [
        line[len("worktree ") :]
        for line in _git(top, "worktree", "list", "--porcelain").splitlines()
        if line.startswith("worktree ")
    ]
    primary = Path(worktrees[0]) if worktrees and (Path(worktrees[0]) / ".git").exists() else top
    found: set[str] = {str(top), *worktrees}
    if origin:
        for root in roots or [primary.parent, primary.parent.parent]:
            try:
                children = list(root.iterdir())
            except OSError:
                continue
            found.update(str(c) for c in children if _checkout_remote(c) == origin)
    projects = Path.home() / ".claude" / "projects"
    suffix = "-" + encode_session_dir(primary.name)
    own = {encode_session_dir(p) for p in found}
    try:
        names = sorted(p.name for p in projects.iterdir())
    except OSError:
        names = []
    checkouts = sorted(tilde(p) for p in found)
    return {
        "root_name": primary.name,
        "origin": origin,
        "checkouts": checkouts,
        "session_dirs": [n for n in names if n in own],
        "other_session_dirs": [n for n in names if n.endswith(suffix) and n not in own],
        "cwd_globs": covering_globs(primary.name, checkouts),
    }


def cmd_git(repo: Path, since: str, top_n: int) -> GitReport:
    """Summarise commit history on the trunk since a date."""
    top = toplevel(repo)
    trunk = trunk_ref(top)
    window = [f"--since={since}", trunk]
    subjects = _git(top, "log", "--no-merges", "--format=%s", *window).splitlines()
    heads = collections.Counter(subject_head(s) for s in subjects)
    direct = 0
    direct_numbered = 0
    merges: list[tuple[list[str], str]] = []
    for line in _git(top, "log", "--first-parent", "--format=%P%x00%s", *window).splitlines():
        parents, _, subject = line.partition("\x00")
        if len(parents.split()) > 1:
            merges.append((parents.split(), subject))
        else:
            direct += 1
            direct_numbered += bool(_PR_NUMBER.search(subject))
    checked = merges[:_MERGES_CHECKED]
    semi_linear = 0
    for parents, _ in checked:
        base = _git(top, "merge-base", parents[0], parents[1], check=False).strip()
        semi_linear += base == parents[0]
    numbered = sum(bool(_PR_NUMBER.search(subject)) for _, subject in checked)
    changed = _git(top, "log", "--no-merges", "--name-only", "--format=", *window).splitlines()
    buckets = collections.Counter(path_bucket(p) for p in changed if p)
    agent_log = _git(
        top, "log", "--no-merges", "--format=%as %s", *window, "--", *_AGENT_FILES
    ).splitlines()
    return {
        "trunk": trunk,
        "since": since,
        "commits": len(subjects),
        "first_parent_direct": direct,
        "direct_numbered": direct_numbered,
        "first_parent_merges": len(merges),
        "merges_checked": len(checked),
        "merges_semi_linear": semi_linear,
        "merges_numbered": numbered,
        "subject_heads": heads.most_common(top_n),
        "hot_paths": buckets.most_common(top_n),
        "agent_file_commits": agent_log[:top_n],
    }


def _history_sources() -> list[tuple[str | None, Path]]:
    zsh = os.environ.get("HISTFILE") or str(Path.home() / ".zsh_history")
    return [
        ("zsh", Path(zsh)),
        ("bash", Path.home() / ".bash_history"),
        ("fish", Path.home() / ".local" / "share" / "fish" / "fish_history"),
    ]


def history_kind(path: Path, head: bytes) -> str:
    """Name a history file's shell from its name, else from its first bytes.

    >>> history_kind(Path("fish_history"), b"")
    'fish'
    >>> history_kind(Path("saved.txt"), b": 1700000000:0;ls")
    'zsh'
    >>> history_kind(Path("saved.txt"), b"- cmd: ls")
    'fish'
    >>> history_kind(Path("saved.txt"), b"ls -la")
    'bash'
    """
    for kind in ("fish", "zsh", "bash"):
        if kind in path.name:
            return kind
    if head.startswith(b"- cmd: "):
        return "fish"
    if _ZSH_EXTENDED.match(head.split(b"\n", 1)[0].decode("utf-8", "replace")):
        return "zsh"
    return "bash"


def cmd_shell(
    repo_paths: list[str], top_n: int, histories: list[Path] | None = None
) -> ShellReport:
    """Attribute shell-history commands to the repository.

    ``histories`` replaces the default zsh, bash, and fish locations; each
    file's shell is inferred by ``history_kind``.
    """
    parsers = {"zsh": parse_zsh, "bash": parse_bash, "fish": parse_fish}
    report: list[ShellSource] = []
    unreadable: list[str] = []
    sources = [(None, h) for h in histories] if histories else _history_sources()
    for named, path in sources:
        if not path.is_file():
            continue
        try:
            raw = path.read_bytes()
        except OSError:
            unreadable.append(tilde(str(path)))
            continue
        kind = named or history_kind(path, raw[:200])
        text = (unmetafy(raw) if kind == "zsh" else raw).decode("utf-8", "replace")
        entries = parsers[kind](text)
        kept = attribute(entries, repo_paths)
        heads = collections.Counter(command_head(redact(c)) for _, c in kept)
        samples: list[str] = []
        for _, command in reversed(kept):
            line = redact(command.split("\n")[0])[:160]
            if line not in samples:
                samples.append(line)
            if len(samples) >= top_n:
                break
        report.append(
            {
                "shell": kind,
                "file": tilde(str(path)),
                "entries": len(entries),
                "attributed": len(kept),
                "heads": heads.most_common(top_n),
                "recent": samples,
            }
        )
    return {"repo_paths": repo_paths, "sources": report, "unreadable": unreadable}


def _field(record: dict[str, object], outer: str, inner: str) -> str | None:
    value = record.get(outer)
    if not isinstance(value, dict):
        return None
    found = t.cast("dict[str, object]", value).get(inner)
    return found if isinstance(found, str) else None


def _scan(data: dict[str, object]) -> Scan:
    def part(name: str) -> dict[str, object]:
        value = data.get(name)
        return t.cast("dict[str, object]", value) if isinstance(value, dict) else {}

    def text(source: dict[str, object], key: str) -> str | None:
        value = source.get(key)
        return value if isinstance(value, str) else None

    def count(key: str) -> int:
        value = part("coverage").get(key)
        return value if isinstance(value, int) else 0

    return {
        "state": text(part("status"), "state") or "unknown",
        "reason": text(part("status"), "reason"),
        "effort_requested": text(part("effort"), "requested"),
        "effort_completed": text(part("effort"), "completed"),
        "sources_failed": count("sources_failed"),
        "sources_bounded": count("sources_bounded"),
        "sources_skipped": count("sources_skipped"),
    }


def _record_cwd(record: dict[str, object]) -> str:
    cwd = _field(record, "origin", "cwd") or _field(record, "metadata", "project")
    return (tilde(cwd).rstrip("/") or "?") if cwd else "?"


def under(cwd: str, prefixes: list[str]) -> bool:
    """Report whether a directory is one of the prefixes or inside one.

    An empty prefix list keeps everything.

    >>> under("~/w/site/packages", ["~/w/site"])
    True
    >>> under("~/w/site-old", ["~/w/site"])
    False
    >>> under("~/anything", [])
    True
    """
    if not prefixes:
        return True
    return any(cwd == p.rstrip("/") or cwd.startswith(p.rstrip("/") + "/") for p in prefixes)


def cmd_transcripts(path: Path, limit: int, keep: list[str] | None = None) -> TranscriptReport:
    """Group an agentgrep NDJSON export by directory and keep human prompts.

    Prompts come from prompt-history stores. An agent with none, named
    outside ``history_agents``, falls back to its conversation records as
    screened by ``is_human_prompt``. ``keep`` limits the report to records
    under those directories; ``limit`` caps the newest prompts returned.
    """
    prefixes = [tilde(str(Path(k).expanduser())) for k in keep or []]
    records = 0
    scan: Scan | None = None
    sessions: dict[str, set[str]] = collections.defaultdict(set)
    counts: collections.Counter[str] = collections.Counter()
    spans: dict[str, list[str]] = {}
    prompts: dict[str, Prompt] = {}
    stamps: dict[str, str] = {}
    history_agents: set[str] = set()
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                parsed: object = json.loads(line)
            except ValueError:
                continue
            if not isinstance(parsed, dict):
                continue
            record = t.cast("dict[str, object]", parsed)
            if record.get("type") == "summary" and isinstance(record.get("data"), dict):
                scan = _scan(t.cast("dict[str, object]", record["data"]))
                continue
            if not isinstance(record.get("text"), str):
                continue
            cwd = _record_cwd(record)
            if not under(cwd, prefixes):
                continue
            records += 1
            stamp = str(record.get("timestamp") or "")
            counts[cwd] += 1
            sessions[cwd].add(str(record.get("session_id") or record.get("path") or ""))
            if stamp:
                span = spans.setdefault(cwd, [stamp, stamp])
                span[0] = min(span[0], stamp)
                span[1] = max(span[1], stamp)
            text = str(record["text"]).strip()
            store = str(record.get("store") or "")
            agent = str(record.get("agent") or "?")
            if store.endswith(".history"):
                history_agents.add(agent)
            if is_human_prompt(store, text):
                key = f"{agent}\x00{store.endswith('.history')}\x00{' '.join(text.split())}"
                known = stamps.get(key)
                if known is None or (stamp and (not known or stamp < known)):
                    stamps[key] = stamp
                    prompts[key] = {
                        "date": stamp[:10],
                        "agent": agent,
                        "cwd": cwd,
                        "text": redact(text).replace("\n", " ⏎ ")[:300],
                    }
    by_cwd: list[CwdRow] = [
        {
            "cwd": cwd,
            "records": n,
            "sessions": len(sessions[cwd]),
            "first": spans.get(cwd, ["", ""])[0][:10],
            "last": spans.get(cwd, ["", ""])[1][:10],
        }
        for cwd, n in counts.most_common()
    ]
    kept = [
        (stamps[key], prompt)
        for key, prompt in prompts.items()
        if key.split("\x00")[1] == "True" or prompt["agent"] not in history_agents
    ]
    ordered = [prompt for _, prompt in sorted(kept, key=lambda pair: pair[0])]
    return {
        "scan": scan,
        "records": records,
        "by_cwd": by_cwd,
        "history_agents": sorted(history_agents),
        "prompts_total": len(ordered),
        "prompts": ordered[-limit:] if limit > 0 else [],
    }


def link_state(skills: Path) -> tuple[str, list[str]]:
    """Classify ``.claude/skills`` and name the entries that decide it."""
    if skills.is_symlink():
        target = str(skills.readlink())
        state = "linked" if target.rstrip("/") == "../.agents/skills" else "other-link"
        return state, [target]
    if not skills.exists():
        return "absent", []
    if not skills.is_dir():
        return "other", [skills.name]
    real = [e.name for e in skills.iterdir() if not e.is_symlink()]
    if real:
        return "real-skills", sorted(real)
    foreign = [
        e.name
        for e in skills.iterdir()
        if not str(e.readlink()).startswith("../../.agents/skills/")
    ]
    if foreign:
        return "foreign-links", sorted(foreign)
    return "per-skill-links", sorted(e.name for e in skills.iterdir())


def cmd_link(repo: Path, *, check: bool) -> LinkReport:
    """Point ``.claude/skills`` at ``../.agents/skills`` and stage the change."""
    top = toplevel(repo)
    skills = top / ".claude" / "skills"
    state, entries = link_state(skills)
    if state in {"real-skills", "foreign-links", "other-link", "other"}:
        msg = f".claude/skills is {state} ({', '.join(entries)}); move or remove these first"
        raise UsageError(msg)
    if state == "linked":
        committed = bool(_git(top, "ls-tree", "HEAD", "--", ".claude/skills", check=False).strip())
        if not check and not committed:
            _git(top, "add", "--force", "--", ".claude/skills")
        return {"state": state, "entries": entries, "changed": not check and not committed}
    if check:
        return {"state": state, "entries": entries, "changed": False}
    if not (top / ".agents" / "skills").is_dir():
        msg = ".agents/skills does not exist; write the skills first"
        raise UsageError(msg)
    tracked = set(_git(top, "ls-files", "--", ".claude/skills").splitlines())
    for name in entries:
        rel = f".claude/skills/{name}"
        if rel in tracked:
            _git(top, "rm", "-q", "--cached", "--", rel)
        (skills / name).unlink()
    if skills.is_dir():
        skills.rmdir()
    skills.parent.mkdir(exist_ok=True)
    skills.symlink_to("../.agents/skills")
    _git(top, "add", "--force", "--", ".claude/skills")
    return {"state": state, "entries": entries, "changed": True}


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(description="Gather evidence for /repo-skills:derive.")
    parser.add_argument("--repo", default=".", help="any path inside the repository")
    sub = parser.add_subparsers(dest="command", required=True)
    paths = sub.add_parser("paths", help="known locations of this repository")
    paths.add_argument("--root", action="append", default=[], help="directory to scan")
    history = sub.add_parser("git", help="commit history summary")
    history.add_argument("--since", default="12 months ago")
    history.add_argument("--top", type=int, default=25)
    shell = sub.add_parser("shell", help="shell history attributed to the repository")
    shell.add_argument("--path", action="append", default=[], help="a repository path")
    shell.add_argument("--top", type=int, default=30)
    shell.add_argument(
        "--history", action="append", default=[], help="a history file to read instead"
    )
    transcripts = sub.add_parser("transcripts", help="summarise an agentgrep NDJSON file")
    transcripts.add_argument("file")
    transcripts.add_argument("--limit", type=int, default=300)
    transcripts.add_argument(
        "--cwd", action="append", default=[], help="keep records under this directory"
    )
    link = sub.add_parser("link", help="link .claude/skills to .agents/skills")
    link.add_argument("--check", action="store_true", help="report without changing")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run one subcommand and print its JSON report."""
    args = build_parser().parse_args(argv)
    repo = Path(str(args.repo)).expanduser()
    result: PathsReport | GitReport | ShellReport | TranscriptReport | LinkReport
    try:
        command = str(args.command)
        if command == "paths":
            roots = [Path(str(r)).expanduser() for r in args.root]
            result = cmd_paths(repo, roots)
        elif command == "git":
            result = cmd_git(repo, str(args.since), int(args.top))
        elif command == "shell":
            paths = [str(p) for p in args.path] or [tilde(str(toplevel(repo)))]
            histories = [Path(str(h)).expanduser() for h in args.history]
            result = cmd_shell(paths, int(args.top), histories)
        elif command == "transcripts":
            keep = [str(c) for c in args.cwd]
            result = cmd_transcripts(Path(str(args.file)).expanduser(), int(args.limit), keep)
        else:
            result = cmd_link(repo, check=bool(args.check))
    except (UsageError, OSError) as error:
        print(str(error), file=sys.stderr)
        return 2
    text = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    sys.stdout.buffer.write(text.encode("utf-8", "replace"))
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
