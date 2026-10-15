"""Lint skill and reference markdown for the AGENTS.md rules a script can decide.

Each check returns ``(rule, line, message)`` tuples; ``marketplace.py`` decides
which rules fail the build.
"""

# ruff: noqa: INP001

from __future__ import annotations

import re
import typing as t

if t.TYPE_CHECKING:
    import collections.abc as cabc

Violation = tuple[str, int, str]

SHELL_TAGS = frozenset({"bash", "sh", "shell", "zsh"})
TOOL_PLUGINS = frozenset({"pytest-optimizer", "ruff", "tailwind", "terraform"})

_FENCE_RE = re.compile(r"^(\s*)(`{3,}|~{3,})\s*([\w+-]*)")
_HEREDOC_RE = re.compile(r"<<-?\s*['\"]?(\w+)['\"]?")
_USER_INVOCABLE_RE = re.compile(r"^user-invocable:\s*true\s*$", re.MULTILINE)
_PROSE_RULES_LINK = "../../references/prose-rules.md"

_COMMAND_START = r"(?:^|&&|;|\|)\s*(?:\$ )?(?:uv run |poetry run |python3? -m )?"
_TEST_RUNNER = r"(?:pytest|npm (?:run )?test|cargo test|go test)\b"
_ECOSYSTEM_RE = re.compile(_COMMAND_START + _TEST_RUNNER)

_GNU_ONLY: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (name, re.compile(pattern))
    for name, pattern in (
        ("mapfile", r"(?<![\w-])mapfile(?![\w-])"),
        ("readarray", r"(?<![\w-])readarray(?![\w-])"),
        ("declare -A", r"\bdeclare\s+-A\b"),
        ("${var,,}", r"\$\{\w+(?:,,|\^\^)\}"),
        ("readlink -f", r"\breadlink\s+(?:-\w+\s+)*-\w*f"),
        ("stat -c", r"\bstat\s+(?:-\w+\s+)*-c\b"),
        ("date -d", r"\bdate\s+(?:-\w+\s+)*-d\b"),
        ("find -printf", r"\s-printf\b"),
        ("numfmt", r"(?<![\w-])numfmt(?![\w-])"),
        ("tac", r"(?:^|[\s|;&(])tac(?=\s|$)"),
        ("nproc", r"(?:^|[\s|;&($`])nproc(?=\s|$|\)|`)"),
        ("shuf", r"(?:^|[\s|;&(])shuf(?=\s|$)"),
        ("base64 -w", r"\bbase64\s+(?:-\w+\s+)*-w"),
        ("xargs -a", r"\bxargs\s+(?:-\w+\s+)*-a\b"),
        ("xargs -d", r"\bxargs\s+(?:-\w+\s+)*-d\b"),
    )
)
_SED_I_RE = re.compile(r"\bsed\s+(?:-\w+\s+)*-i(?:\s+(?!['\"]{2}))")
_SED_I_BSD_RE = re.compile(r"\bsed\s+(?:-\w+\s+)*-i\s+(?:''|\"\")")


class Fence(t.NamedTuple):
    """A fenced block: tag, first body line number, body lines, and the line before it."""

    tag: str
    start: int
    lines: list[str]
    before: str


def fences(text: str) -> list[Fence]:
    r"""Return the fenced blocks of ``text``.

    Examples
    --------
    >>> fences("a\n```console\n$ ls\n```\n")
    [Fence(tag='console', start=3, lines=['$ ls'], before='a')]
    """
    out: list[Fence] = []
    marker: str | None = None
    tag = before = last = ""
    indent = 0
    start = 0
    body: list[str] = []
    for number, line in enumerate(text.splitlines(), start=1):
        match = _FENCE_RE.match(line)
        if marker is None:
            if match:
                marker, tag, start, body = match.group(2), match.group(3).lower(), number + 1, []
                indent, before = len(match.group(1)), last
            elif line.strip():
                last = line.strip()
        elif match and match.group(2).startswith(marker[0]) and not match.group(3):
            out.append(Fence(tag, start, body, before))
            marker = None
        else:
            body.append(line[indent:] if line[:indent].isspace() else line.lstrip())
    return out


def _is_counterexample(fence: Fence) -> bool:
    """Report whether prose labels the fence as a deliberate bad example."""
    return fence.before.rstrip(":").lower() in {"bad", "wrong"}


def _outside_heredocs(lines: list[str]) -> cabc.Iterator[tuple[int, str]]:
    """Yield ``(index, line)`` for lines that are not heredoc bodies."""
    terminator: str | None = None
    for index, line in enumerate(lines):
        if terminator is not None:
            if line.strip() == terminator:
                terminator = None
            continue
        yield index, line
        found = _HEREDOC_RE.search(line)
        if found:
            terminator = found.group(1)


def check_user_invocable(text: str) -> list[Violation]:
    r"""Flag ``user-invocable: true`` in frontmatter.

    Examples
    --------
    >>> check_user_invocable("---\nname: a\nuser-invocable: true\n---\nbody")
    [('user-invocable', 3, '`user-invocable: true` is the default; delete it')]
    >>> check_user_invocable("---\nname: a\nuser-invocable: false\n---\n")
    []
    """
    if not text.startswith("---"):
        return []
    end = text.find("\n---", 3)
    head = text[: end if end != -1 else 0]
    found = _USER_INVOCABLE_RE.search(head)
    if not found:
        return []
    line = head.count("\n", 0, found.start()) + 1
    return [("user-invocable", line, "`user-invocable: true` is the default; delete it")]


def check_console_fences(text: str) -> list[Violation]:
    r"""Flag a ``console`` fence that does not open with ``$ `` or holds a ``#`` comment line.

    Examples
    --------
    >>> check_console_fences("```console\n$ ls\n```\n")
    []
    >>> check_console_fences("```console\nls\n```\n")
    [('console-prompt', 2, 'console fence must open with a `$ ` command')]
    >>> check_console_fences("```console\n# list\n$ ls\n```\n")
    [('console-comment', 2, 'comments belong in prose above the fence')]
    """
    out: list[Violation] = []
    for fence in fences(text):
        if fence.tag != "console" or _is_counterexample(fence):
            continue
        body = [(i, line) for i, line in _outside_heredocs(fence.lines) if line.strip()]
        commands = [(i, line) for i, line in body if not line.lstrip().startswith("#")]
        if commands and not commands[0][1].startswith("$ "):
            out.append(
                (
                    "console-prompt",
                    fence.start + commands[0][0],
                    "console fence must open with a `$ ` command",
                )
            )
        out.extend(
            (
                "console-comment",
                fence.start + i,
                "comments belong in prose above the fence",
            )
            for i, line in body
            if line.lstrip().startswith("#")
        )
    return out


def check_shell_fences(text: str) -> list[Violation]:
    r"""Flag a bash/sh/shell fence that is not a script.

    A script opens with a shebang; anything else is a paste-and-run command
    and takes the ``console`` tag.

    Examples
    --------
    >>> check_shell_fences("```bash\ngit status\n```\n")
    [('shell-fence', 2, 'use a `console` fence with `$ ` unless the block is a script')]
    >>> check_shell_fences("```bash\n#!/bin/sh\nset -e\n```\n")
    []
    """
    out: list[Violation] = []
    for fence in fences(text):
        if fence.tag not in SHELL_TAGS:
            continue
        first = next((line for line in fence.lines if line.strip()), "")
        if not first.startswith("#!"):
            out.append(
                (
                    "shell-fence",
                    fence.start,
                    "use a `console` fence with `$ ` unless the block is a script",
                )
            )
    return out


def check_ecosystem_commands(text: str) -> list[Violation]:
    r"""Flag a fenced test-runner command that names one ecosystem.

    Examples
    --------
    >>> check_ecosystem_commands("```console\n$ uv run pytest -q\n```\n")
    [('ecosystem-command', 2, 'hardcoded `uv run pytest`; point to the project gates in AGENTS.md')]
    >>> check_ecosystem_commands("Run `npm test` if present.\n")
    []
    """
    out: list[Violation] = []
    for fence in fences(text):
        for index, line in enumerate(fence.lines):
            found = _ECOSYSTEM_RE.search(line)
            if found:
                command = found.group(0).lstrip(" ;&|$").strip()
                out.append(
                    (
                        "ecosystem-command",
                        fence.start + index,
                        f"hardcoded `{command}`; point to the project gates in AGENTS.md",
                    )
                )
    return out


def check_portable_shell(text: str) -> list[Violation]:
    r"""Flag GNU-only constructs in fenced commands.

    ``sed -i`` passes when the same fence or an adjacent one shows the
    ``sed -i ''`` BSD form.

    Examples
    --------
    >>> check_portable_shell("```console\n$ readlink -f x\n```\n")
    [('gnu-only', 2, '`readlink -f` is GNU-only')]
    >>> check_portable_shell("```console\n$ sed -i 's/a/b/' f\n```\n")
    [('gnu-only', 2, "`sed -i` without the BSD `sed -i ''` form beside it")]
    >>> bsd = "```console\n$ sed -i '' 's/a/b/' f\n```\n"
    >>> check_portable_shell("```console\n$ sed -i 's/a/b/' f\n```\n" + bsd)
    []
    """
    blocks = [f for f in fences(text) if f.tag in SHELL_TAGS | {"console", ""}]
    out: list[Violation] = []
    for position, fence in enumerate(blocks):
        near = blocks[max(position - 1, 0) : position + 2]
        has_bsd = any(_SED_I_BSD_RE.search(line) for f in near for line in f.lines)
        for index, line in enumerate(fence.lines):
            number = fence.start + index
            out.extend(
                ("gnu-only", number, f"`{name}` is GNU-only")
                for name, pattern in _GNU_ONLY
                if pattern.search(line)
            )
            if _SED_I_RE.search(line) and not _SED_I_BSD_RE.search(line) and not has_bsd:
                out.append(
                    (
                        "gnu-only",
                        number,
                        "`sed -i` without the BSD `sed -i ''` form beside it",
                    )
                )
    return out


def lacks_prose_rules_link(text: str) -> bool:
    r"""Report whether a SKILL.md omits the prose-rules link.

    Examples
    --------
    >>> lacks_prose_rules_link("see ../../references/prose-rules.md")
    False
    >>> lacks_prose_rules_link("nothing")
    True
    """
    return _PROSE_RULES_LINK not in text
