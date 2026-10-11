"""Rendering layer for the portable skill export.

``marketplace.py`` decides *which* components become portable skills and what
each one is named; this module decides *what each one says*. It takes a named
:class:`OutputSkill` plus the :class:`PortableIndex` of peer names and returns a
:class:`BuiltSkill` — the finished bytes for one ``.agents/skills/<name>/``
directory — without touching the output tree, the manifest, or the drift check.

The split follows the dependency direction: everything here is downstream of
discovery and upstream of writing, it reads only the source tree, and it needs
no third-party package. Frontmatter arrives already parsed on
:class:`SourceComponent`, so the caller owns YAML and this module owns markdown.
"""

# ruff: noqa: INP001

from __future__ import annotations

import ast
import dataclasses
import json
import posixpath
import re
import typing as t
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
"""Repository root, derived from this module's own location.

``marketplace.py`` derives the same value independently, so the render layer
imports nothing from its caller.
"""
PLUGINS_DIR = REPO_ROOT / "plugins"

SPEC_FRONTMATTER_KEYS = (
    "name",
    "description",
    "allowed-tools",
    "disable-model-invocation",
    "metadata",
)
"""Frontmatter keys the portable export is allowed to emit, in output order."""

RESOURCE_DIRS = ("references", "templates", "docs", "assets")
"""Plugin subdirectories whose files are vendored into an output skill."""

VENDOR_MARKER = "Vendored from shared/"
"""Text in the first line of a plugin file copied from the repo's ``shared/``."""

_MARKDOWN_SUFFIX = ".md"
_VENDOR_ROOT = "references"
_COMPONENT_DEPTH = 2
"""Segments in a plugin-relative component path, as in ``skills/<name>``."""
_DESCRIPTION_WRAP = 76

_ASK_TOKEN = "ask-user-choice"  # noqa: S105
"""Host-neutral stand-in for the Claude-only ``AskUserQuestion`` tool."""

_HEADLESS_DEFAULT_MARKER = "<!-- portable: ask-user-choice=headless-default -->"
"""Source marker allowing a command's documented choice default in headless mode."""

_VERBATIM_FENCES_MARKER = "<!-- portable: verbatim-fences -->"
"""Source marker exempting a file's fenced blocks from the host rewrites.

A fence normally holds a usage example, so a slash invocation inside one is
rewritten to the bare skill name a Codex user would type. A file carrying this
marker quotes evidence instead — prompts somebody actually typed, hunks that
actually landed — and rewriting a quote makes it a false one.

It exempts fences from rewriting, not from the emitted-tree invariants the
export checks afterwards. A quote holding an in-repo path or an inline-bash
span still fails ``portable --check``, because those checks describe what may
ship rather than what may be rewritten. Such a quote has to be trimmed to the
part that carries the point.
"""

_VERBATIM_FENCES_RE = re.compile(
    r"^[ \t]*" + re.escape(_VERBATIM_FENCES_MARKER) + r"[ \t]*\n?", re.MULTILINE
)
"""The marker on a line of its own, so prose quoting it does not arm it."""

_BASH_PROSE = "run this command and read the output:"

REPO_PATH_PATTERN = r"(?<![A-Za-z0-9._/-])plugins/[a-z][a-z0-9-]*/[A-Za-z0-9._/-]*"
"""A repo-relative path into a plugin, as written in prose or a code span.

Shared with the citation lint in ``marketplace.py`` so the rewriter and the
check cannot disagree about what counts as one. The lookbehind keeps this
project's own name inside a URL from reading as a citation.
"""

TOKEN_RE = re.compile(
    r"""
      (?<=\]\()(?P<link>(?!/)[A-Za-z0-9._/-]+)(?=[)#\s])
    | (?P<root>\$\{CLAUDE_PLUGIN_ROOT\}(?P<root_path>/[A-Za-z0-9._/-]+)?)
    | (?P<repo>"""
    + REPO_PATH_PATTERN
    + r""")(?::\d+(?:-\d+)?)?
    | (?P<rel>(?<![A-Za-z0-9._/-])\.\./[A-Za-z0-9._/-]+)
    | (?P<res>(?<![A-Za-z0-9._/-])(?:references|templates|docs|assets)/[A-Za-z0-9._/-]+)
    | (?P<slash>(?<![A-Za-z0-9/])/[a-z][a-z0-9-]*:[a-z0-9][a-z0-9-]*)
    """,
    re.VERBOSE,
)
_SKILL_PHRASE = r"(this skill|the `[^`]+` skill)"
_PHRASE_FIXES = (
    (re.compile(r"\bthe (?=this skill\b)"), ""),
    (re.compile(r"\bthe (?=the `[^`]+` skill\b)"), ""),
    (re.compile(_SKILL_PHRASE + r"(?:[ \t]+slash)?(?:[ \t]+|[ \t]*\n[ \t]*)command\b"), r"\1"),
)
"""Repairs for the article and noun left behind when a slash command becomes a skill."""
# Covers only the phrasings this corpus uses ("the /p:c command", "the /p:c");
# a new phrasing passes through unrepaired and undetected.

_BASH_LINE_RE = re.compile(r"^`!(?P<cmd>.+)`\s*$")
_INLINE_BANG_RE = re.compile(r"`!([^`\n]*)`")
_ASK_RE = re.compile(r"\bAskUserQuestion\b")
_FENCE_RE = re.compile(r"^\s*(```|~~~)")
# An open/close toggle that ignores fence length, so a nested fence desynchronizes it.


@dataclasses.dataclass(frozen=True)
class SourceComponent:
    """A skill in the source tree, before portable naming.

    Attributes
    ----------
    plugin : Path
        Plugin directory that owns the component.
    path : Path
        The ``SKILL.md`` file.
    raw_name : str
        Undisambiguated component name.
    base : Path
        Directory that bare relative paths in the body resolve against.
    frontmatter : dict[str, Any]
        The file's parsed frontmatter, empty when absent or unparseable. Held
        here so the render layer never has to parse YAML itself; excluded from
        equality and hashing, for which ``path`` is the identity.
    """

    plugin: Path
    path: Path
    raw_name: str
    base: Path
    frontmatter: dict[str, t.Any] = dataclasses.field(compare=False)


@dataclasses.dataclass(frozen=True)
class OutputSkill:
    """One emitted ``.agents/skills/<name>/`` directory.

    Attributes
    ----------
    name : str
        Output directory name, also the emitted ``name`` frontmatter value.
    body : SourceComponent
        Component whose body becomes ``SKILL.md``.
    """

    name: str
    body: SourceComponent


@dataclasses.dataclass
class PortableIndex:
    """Lookup tables shared by every skill build.

    Attributes
    ----------
    by_path : dict[Path, str]
        Source component file to output skill name.
    by_invocation : dict[tuple[str, str], str]
        ``(plugin name, component name)`` to output skill name.
    """

    by_path: dict[Path, str]
    by_invocation: dict[tuple[str, str], str]


@dataclasses.dataclass
class BuiltSkill:
    """A rendered output skill held in memory before it touches disk.

    Attributes
    ----------
    name : str
        Output directory name.
    files : dict[str, tuple[bytes, int]]
        Output-relative path to ``(content, permission bits)``.
    sources : list[str]
        Repo-relative paths of the components this skill was built from.
    vendored : dict[str, str]
        Output-relative bundled path to its repo-relative source path.
    external : list[str]
        Path-shaped tokens left verbatim because they name the user's project.
    unresolved : list[str]
        Host command references with no counterpart in the export.
    links : list[tuple[str, str, str]]
        ``(emitting file, spelled path, intended file)`` for every bundled
        path rewritten into the output, all output-relative. The spelled path
        must resolve from the emitting file's directory to the intended file.
    collisions : list[str]
        Output-relative paths that two different sources both wanted.
    description : str
        Description the builder intended to emit, for round-trip verification.
    """

    name: str
    files: dict[str, tuple[bytes, int]]
    sources: list[str]
    vendored: dict[str, str]
    external: list[str]
    unresolved: list[str]
    links: list[tuple[str, str, str]]
    collisions: list[str]
    description: str


def strip_frontmatter(text: str) -> str:
    r"""Return ``text`` without a leading YAML frontmatter block.

    Examples
    --------
    >>> strip_frontmatter("---\nname: a\n---\nbody\n")
    'body\n'
    >>> strip_frontmatter("body\n")
    'body\n'
    """
    if not text.startswith("---"):
        return text
    end = text.find("---", 3)
    return text if end == -1 else text[end + 3 :].lstrip("\n")


def strip_vendor_banner(text: str) -> str:
    r"""Drop the editor banner a plugin's copy of a ``shared/`` file opens with.

    The banner tells a repo contributor where to edit; a bundled skill has no
    ``shared/`` directory, so the line would point nowhere.

    Examples
    --------
    >>> strip_vendor_banner("<!-- Vendored from shared/a.md; edit that -->\n# A\n")
    '# A\n'
    >>> strip_vendor_banner("# A\n")
    '# A\n'
    """
    first, sep, rest = text.partition("\n")
    return rest if sep and VENDOR_MARKER in first else text


def _read_body(path: Path) -> str:
    """Read a markdown file and return its body without frontmatter."""
    return strip_frontmatter(path.read_text(encoding="utf-8"))


def _fold_description(text: str) -> list[str]:
    r"""Wrap description text into the lines of a YAML folded block scalar.

    Parameters
    ----------
    text : str
        Description text; interior whitespace is collapsed to single spaces.

    Returns
    -------
    list[str]
        Indented lines to place under a ``>-`` scalar header.

    Examples
    --------
    >>> _fold_description("a  b\nc")
    ['  a b c']
    >>> len(_fold_description("word " * 40)) > 1
    True
    """
    words = text.split()
    lines: list[str] = []
    current = "  "
    for word in words:
        candidate = f"{current} {word}" if current.strip() else f"  {word}"
        if len(candidate) > _DESCRIPTION_WRAP and current.strip():
            lines.append(current)
            current = f"  {word}"
        else:
            current = candidate
    if current.strip():
        lines.append(current)
    return lines


OPENAI_YAML_REL = "agents/openai.yaml"
"""Path of a skill's Codex presentation file, relative to the skill directory."""

_SHORT_DESCRIPTION_MAX = 100
_OPENAI_YAML_BANNER = (
    "# Generated by 'scripts/marketplace.py portable'; edit the skill's SKILL.md, then run it.\n"
)


def _short_description(description: str) -> str:
    r"""Trim a skill description to one line for a picker row.

    Examples
    --------
    >>> _short_description("Use when  a\nb.")
    'Use when a b.'
    >>> out = _short_description("word " * 40)
    >>> len(out) <= 100 and out.endswith("...")
    True
    """
    text = " ".join(description.split())
    if len(text) <= _SHORT_DESCRIPTION_MAX:
        return text
    cut = text[: _SHORT_DESCRIPTION_MAX - 3].rsplit(" ", 1)[0].rstrip(",;:")
    return f"{cut}..."


def render_openai_yaml(name: str, description: str, *, model_invocable: bool = True) -> str:
    """Render a skill's ``agents/openai.yaml`` for Codex.

    Codex ignores ``disable-model-invocation``; ``policy.allow_implicit_invocation``
    is its spelling of the same switch.

    Parameters
    ----------
    name : str
        Skill name, hyphenated; becomes the display name.
    description : str
        Skill description; trimmed into ``short_description``.
    model_invocable : bool
        False writes ``allow_implicit_invocation: false``.

    Examples
    --------
    >>> print(
    ...     render_openai_yaml("ruff-bump", "Raise the floor.", model_invocable=False)
    ... )
    # Generated by 'scripts/marketplace.py portable'; edit the skill's SKILL.md, then run it.
    interface:
      display_name: "Ruff Bump"
      short_description: "Raise the floor."
    policy:
      allow_implicit_invocation: false
    <BLANKLINE>
    >>> "policy" in render_openai_yaml("a", "d")
    False
    """
    lines = [
        "interface:",
        f"  display_name: {json.dumps(name.replace('-', ' ').title())}",
        f"  short_description: {json.dumps(_short_description(description))}",
    ]
    if not model_invocable:
        lines += ["policy:", "  allow_implicit_invocation: false"]
    return _OPENAI_YAML_BANNER + "\n".join(lines) + "\n"


def _render_frontmatter(
    name: str,
    description: str,
    tools: object,
    meta: dict[str, str],
    *,
    model_invocable: bool = True,
) -> str:
    """Render the portable frontmatter block, spec keys only.

    Parameters
    ----------
    name : str
        Output skill name.
    description : str
        Skill description.
    tools : object
        ``allowed-tools`` value carried over from the source, or None.
    meta : dict[str, str]
        ``metadata`` string map (provenance and the original argument hint).
    model_invocable : bool
        False when the source forbids the router firing this skill. Dropping
        that on export would publish a name-only workflow into a routing
        corpus, which is the one thing the source said not to do.

    Returns
    -------
    str
        The frontmatter block including its delimiters.
    """
    lines = ["---", f"name: {name}", "description: >-", *_fold_description(description)]
    if not model_invocable:
        lines.append("disable-model-invocation: true")
    if tools is not None:
        lines.append(f"allowed-tools: {json.dumps(tools)}")
    if meta:
        lines.append("metadata:")
        lines.extend(f"  {key}: {json.dumps(value)}" for key, value in sorted(meta.items()))
    lines.append("---")
    return "\n".join(lines) + "\n\n"


def _convert_bash_lines(text: str) -> str:
    r"""Turn whole-line ``\`!cmd\``` blocks into prose plus a fenced command.

    Parameters
    ----------
    text : str
        Markdown body.

    Returns
    -------
    str
        Body with every inline-bash line replaced.

    Examples
    --------
    >>> print(_convert_bash_lines("Branch:\n`!git branch`\n"), end="")
    Branch — run this command and read the output:
    <BLANKLINE>
    ```bash
    git branch
    ```

    Without a preceding label the prose stands on its own line:

    >>> print(_convert_bash_lines("Intro text\n`!git status`\n"), end="")
    Intro text
    Run this command and read the output:
    <BLANKLINE>
    ```bash
    git status
    ```
    """
    out: list[str] = []
    fenced = False
    for line in text.split("\n"):
        if _FENCE_RE.match(line):
            fenced = not fenced
            out.append(line)
            continue
        match = None if fenced else _BASH_LINE_RE.match(line)
        if match is None:
            out.append(line)
            continue
        _attach_bash_prose(out)
        out.extend(["```bash", match.group("cmd"), "```"])
    return "\n".join(out)


def _attach_bash_prose(out: list[str]) -> None:
    """Attach the run-this-command prose to the label preceding a bash block."""
    index = len(out) - 1
    while index >= 0 and not out[index].strip():
        index -= 1
    if index >= 0 and out[index].rstrip().endswith(":"):
        out[index] = f"{out[index].rstrip().removesuffix(':')} — {_BASH_PROSE}"
    else:
        out.append("Run this command and read the output:")
    if out and out[-1].strip():
        out.append("")


def _widen_inline_bang(text: str) -> str:
    r"""Re-fence leftover inline ``\`!x\``` spans so backtick and bang never touch.

    Parameters
    ----------
    text : str
        Markdown body.

    Returns
    -------
    str
        Body where each remaining span uses padded double backticks, which
        CommonMark renders identically.

    Examples
    --------
    >>> _widen_inline_bang("a `!` glyph")
    'a `` ! `` glyph'
    """
    out: list[str] = []
    fenced = False
    for line in text.split("\n"):
        if _FENCE_RE.match(line):
            fenced = not fenced
            out.append(line)
            continue
        out.append(line if fenced else _INLINE_BANG_RE.sub(r"`` !\1 ``", line))
    return "\n".join(out)


def _describe_source_path(plugin_name: str, rel: str) -> str:
    """Describe an in-repo source coordinate as prose carrying no path token.

    Parameters
    ----------
    plugin_name : str
        Owning plugin.
    rel : str
        Path inside that plugin.

    Returns
    -------
    str
        Prose replacement.

    Examples
    --------
    >>> _describe_source_path("pr", "references/quality-gates.md")
    "the pr plugin's quality-gates reference"
    >>> _describe_source_path("commit", "hooks/")
    "the commit plugin's hooks/ directory"

    A path deeper than ``<kind>/<name>`` describes its leaf, so a stale
    coordinate cannot be laundered into a confident claim about a component
    that does not exist:

    >>> _describe_source_path("pr", "skills/deslop/references/quality-gates.md")
    "the pr plugin's quality-gates reference"
    """
    parts = [p for p in rel.split("/") if p]
    if not parts:
        return f"the {plugin_name} plugin"
    if rel.endswith("/"):
        return f"the {plugin_name} plugin's {parts[-1]}/ directory"
    kinds = {
        "references": "reference",
        "templates": "template",
        "docs": "doc",
        "skills": "skill",
        "hooks": "hook",
    }
    if len(parts) == _COMPONENT_DEPTH and parts[0] == "skills":
        return f"the {plugin_name} plugin's {parts[1]} skill"
    stem = parts[-1].split(".")[0]
    kind = kinds.get(parts[-2] if len(parts) > 1 else parts[0], "file")
    return f"the {plugin_name} plugin's {stem} {kind}"


def _fix_phrases(text: str) -> str:
    """Repair the article and noun a slash-to-skill rewrite leaves behind.

    Examples
    --------
    >>> _fix_phrases("Run the this skill command with your prompt.")
    'Run this skill with your prompt.'
    >>> _fix_phrases("See the the `refine` skill command.")
    'See the `refine` skill.'
    """
    for pattern, repl in _PHRASE_FIXES:
        text = pattern.sub(repl, text)
    return text


def fenced_blocks(text: str) -> list[str]:
    r"""Return the lines inside ``text``'s code fences, fence markers excluded.

    Exported for the export check, which compares a verbatim source against
    what shipped. Uses the same open/close toggle as the renderer, so both
    agree on where a fence starts even where that toggle is wrong.

    Examples
    --------
    >>> fenced_blocks("a\n```\nkept\n```\nb")
    ['kept']
    """
    inside: list[str] = []
    in_code = False
    for line in text.split("\n"):
        if _FENCE_RE.match(line):
            in_code = not in_code
            continue
        if in_code:
            inside.append(line)
    return inside


def has_verbatim_fences(text: str) -> bool:
    """Report whether ``text`` carries the verbatim-fences marker."""
    return _VERBATIM_FENCES_RE.search(text) is not None


def _plugin_of(path: Path) -> Path | None:
    """Return the plugin directory containing ``path``, or None."""
    try:
        rel = path.relative_to(PLUGINS_DIR)
    except ValueError:
        return None
    if not rel.parts:
        return None
    return PLUGINS_DIR / rel.parts[0]


def imported_modules(source: str) -> set[str]:
    r"""Return the top-level names of absolute imports anywhere in ``source``.

    Examples
    --------
    >>> sorted(imported_modules("import a.b\nfrom c import d\nfrom . import e"))
    ['a', 'c']
    >>> sorted(imported_modules("def f():\n    import g"))
    ['g']
    >>> imported_modules("def (")
    set()
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


def sibling_module(scripts_dir: Path, name: str) -> Path | None:
    """Return ``scripts_dir/name.py`` when it is a bundleable sibling module."""
    path = scripts_dir / f"{name}.py"
    return path if not name.startswith("test_") and path.is_file() else None


class SkillBuilder:
    """Render one output skill, vendoring every resource it reaches.

    Resources (``references/``, ``templates/``, ``docs/``, ``assets/``) are
    copied into the output directory and their links rewritten to plain
    relative paths. Peer components (other skills) are not
    copied; they are named, because the export emits them as sibling skills.
    """

    def __init__(self, skill: OutputSkill, index: PortableIndex) -> None:
        self._skill: OutputSkill = skill
        self._index: PortableIndex = index
        self._in_code: bool = False
        self._files: dict[str, tuple[bytes, int]] = {}
        self._vendored: dict[Path, str] = {}
        self._pending: list[tuple[Path, Path]] = []
        self._external: set[str] = set()
        self._unresolved: set[str] = set()
        self._links: list[tuple[str, str, str]] = []
        self._collisions: list[str] = []
        self._emitting: str = "SKILL.md"
        self._notes: set[str] = set()
        self._description: str = ""

    def build(self) -> BuiltSkill:
        """Render the skill and everything it bundles.

        Returns
        -------
        BuiltSkill
            In-memory output, ready to be written or compared.
        """
        body_src = self._skill.body
        fm = body_src.frontmatter
        body = _read_body(body_src.path)
        sources = [str(body_src.path.relative_to(REPO_ROOT))]
        body = self._transform_markdown(body, body_src.plugin, body_src.base)
        has_headless_default = _HEADLESS_DEFAULT_MARKER in body
        body = body.replace(_HEADLESS_DEFAULT_MARKER, "")
        text = self._render(
            fm,
            body + self._portability_notes(body, has_headless_default=has_headless_default),
        )
        self._files["SKILL.md"] = (text.encode("utf-8"), 0o644)
        openai_yaml = render_openai_yaml(
            self._skill.name,
            self._description,
            model_invocable=not fm.get("disable-model-invocation", False),
        )
        self._files[OPENAI_YAML_REL] = (openai_yaml.encode("utf-8"), 0o644)
        self._drain()
        return BuiltSkill(
            name=self._skill.name,
            files=self._files,
            sources=sources,
            vendored={rel: str(src.relative_to(REPO_ROOT)) for src, rel in self._vendored.items()},
            external=sorted(self._external),
            unresolved=sorted(self._unresolved),
            links=sorted(set(self._links)),
            collisions=sorted(self._collisions),
            description=" ".join(self._description.split()),
        )

    def _render(self, fm: dict[str, t.Any], body: str) -> str:
        """Render frontmatter plus body for the skill's ``SKILL.md``."""
        raw_description = t.cast("str", fm.get("description", "")).strip()
        origin = self._skill.body
        description = self._rewrite_tokens(raw_description, origin.plugin, origin.base)
        self._description = description
        meta = {"source": ", ".join(self._source_paths())}
        hint = t.cast("str | None", fm.get("argument-hint"))
        if hint is not None:
            meta["argument-hint"] = hint
        header = _render_frontmatter(
            self._skill.name,
            description,
            fm.get("allowed-tools"),
            meta,
            model_invocable=not fm.get("disable-model-invocation", False),
        )
        return header + body

    def _source_paths(self) -> list[str]:
        """List the repo-relative sources feeding this skill."""
        return [str(self._skill.body.path.relative_to(REPO_ROOT))]

    def _drain(self) -> None:
        """Transform and store every queued resource, following links onward."""
        while self._pending:
            src, plugin = self._pending.pop(0)
            rel = self._vendored[src]
            self._emitting = rel
            mode = src.stat().st_mode & 0o777
            try:
                raw = src.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                # An assets/ image or font carries no paths to rewrite; copy it
                # through untouched rather than failing the whole export.
                self._files[rel] = (src.read_bytes(), mode)
                continue
            raw = strip_vendor_banner(raw)
            # A resource resolves its own relative links from where it sits, not
            # from the plugin root. ``_resolve`` still falls back to the plugin
            # root, so a root-relative link in the same file keeps working.
            base = src.parent
            if src.suffix == _MARKDOWN_SUFFIX:
                text = self._transform_markdown(raw, plugin, base)
            else:
                # Path rewriting only; the emitted-file check fails on any inline
                # bash or choice prompt a non-markdown payload carries.
                text = self._rewrite_tokens(raw, plugin, base)
            self._files[rel] = (text.encode("utf-8"), mode)
            if src.suffix == ".py" and src.parent == plugin / "scripts":
                for name in sorted(imported_modules(raw)):
                    sibling = sibling_module(src.parent, name)
                    if sibling is not None:
                        _ = self._vendor(sibling, plugin)

    def _transform_markdown(self, text: str, plugin: Path, base: Path) -> str:
        """Apply every portability transform to a markdown body."""
        verbatim = _VERBATIM_FENCES_RE.search(text) is not None
        if verbatim:
            text = _VERBATIM_FENCES_RE.sub("", text, count=1)
        text = _convert_bash_lines(text)
        text = _widen_inline_bang(text)
        return self._rewrite_fenced(text, plugin, base, verbatim=verbatim)

    def _portability_notes(self, body: str, *, has_headless_default: bool) -> str:
        """Build the trailing notes block for whatever degraded forms were used."""
        if has_headless_default:
            ask_note = (
                f"- `{_ASK_TOKEN}` — follow the source's choice contract. Hosts with a"
                " structured multiple-choice tool (Claude Code's `AskUserQuestion`) should"
                " use it. Honor a documented headless default when the source defines one;"
                " otherwise print a numbered list and wait for a numbered reply. Never"
                " invent a choice."
            )
        else:
            ask_note = (
                f"- `{_ASK_TOKEN}` — present the listed options and wait for the user to"
                " pick one. Hosts with a structured multiple-choice tool (Claude Code's"
                " `AskUserQuestion`) should use it; otherwise print a numbered list and wait"
                " for a numbered reply. Never proceed on an assumed answer."
            )
        args_note = (
            "- `$ARGUMENTS` — the text the user passed when invoking this skill. If"
            " your host does not substitute it, read it as the user's request in the"
            " current turn, and ask when there is none."
        )
        bundle_note = (
            "- Bundled files — every relative path in this skill points at a file"
            " shipped inside this skill directory. Read them from here, not from the"
            " host's plugin tree."
        )
        bullets: list[str] = []
        if "ask" in self._notes:
            bullets.append(ask_note)
        if "$ARGUMENTS" in body:
            bullets.append(args_note)
        if self._vendored:
            bullets.append(bundle_note)
        if not bullets:
            return ""
        return "\n\n## Portability notes\n\n" + "\n".join(bullets) + "\n"

    def _vendor(self, src: Path, plugin: Path) -> str:
        """Queue a resource for copying and return its output-relative path.

        Two different sources with one basename in one output directory are
        recorded as a collision; the later one is renamed so the build
        completes, and ``portable --check`` fails on the record.
        """
        known = self._vendored.get(src)
        if known is not None:
            return known
        rel_in_plugin = src.relative_to(plugin)
        top = rel_in_plugin.parts[0] if rel_in_plugin.parts[0] in RESOURCE_DIRS else _VENDOR_ROOT
        rel = f"{top}/{src.name}"
        if rel in self._vendored.values() or rel in self._files:
            self._collisions.append(rel)
            counter = 2
            while f"{top}/{counter}-{src.name}" in self._vendored.values():
                counter += 1
            rel = f"{top}/{counter}-{src.name}"
        self._vendored[src] = rel
        self._pending.append((src, plugin))
        return rel

    def _spell(self, target: str) -> str:
        """Spell an output-relative path from the file being emitted."""
        start = posixpath.dirname(self._emitting)
        if not start:
            return target
        spelled = posixpath.relpath(target, start)
        return spelled if spelled.startswith("..") else f"./{spelled}"

    def _rewrite_fenced(
        self, text: str, plugin: Path, base: Path, *, verbatim: bool = False
    ) -> str:
        """Rewrite tokens line by line, tracking fenced blocks.

        Inside a fence a slash invocation is a usage example, so it becomes the
        bare skill name rather than a prose phrase. Under ``verbatim`` the
        fences are left exactly as written; prose outside them still rewrites,
        so a worked example reads in the host's own vocabulary while its quoted
        evidence stays quotable.
        """
        lines: list[str] = []
        self._in_code = False
        for line in text.split("\n"):
            if _FENCE_RE.match(line):
                self._in_code = not self._in_code
                lines.append(line)
                continue
            if verbatim and self._in_code:
                lines.append(line)
                continue
            rewritten = self._rewrite_tokens(line, plugin, base)
            # Neutralizing the Claude-only choice tool rides this pass rather
            # than a second one, so it inherits the same fence state: a note
            # promising the token is only earned where the token was written.
            if _ASK_RE.search(rewritten):
                self._notes.add("ask")
                rewritten = _ASK_RE.sub(_ASK_TOKEN, rewritten)
            lines.append(rewritten)
        self._in_code = False
        joined = "\n".join(lines)
        return joined if verbatim else _fix_phrases(joined)

    def _rewrite_tokens(self, text: str, plugin: Path, base: Path) -> str:
        """Rewrite every host-specific path or slash token in ``text``."""
        out: list[str] = []
        pos = 0
        for match in TOKEN_RE.finditer(text):
            start, end = match.start(), match.end()
            quoted = start > 0 and text[start - 1] == "`" and text[end : end + 1] == "`"
            replacement, drop_quotes = self._replace(match, plugin, base)
            if replacement is None:
                continue
            if drop_quotes and quoted and pos <= start - 1:
                out.append(text[pos : start - 1])
                pos = end + 1
            else:
                out.append(text[pos:start])
                pos = end
            out.append(replacement)
        out.append(text[pos:])
        return _fix_phrases("".join(out))

    def _replace(self, match: re.Match[str], plugin: Path, base: Path) -> tuple[str | None, bool]:
        """Resolve one matched token to its replacement text."""
        if match.group("slash") is not None:
            return self._replace_slash(match.group("slash"))
        if match.group("repo") is not None:
            return self._replace_repo(match.group("repo"))
        if match.group("root") is not None:
            raw = match.group("root_path")
            if raw is None:
                return "the plugin root", False
            return self._replace_path(raw.lstrip("/"), plugin, plugin)
        link = match.group("link")
        if match.group("rel") is not None or link is not None:
            # A skill addresses its plugin's shared resources by climbing out of
            # its own directory, the spelling both hosts resolve without
            # substitution. Flattening the export severs that climb, so the
            # target is vendored exactly as a ${CLAUDE_PLUGIN_ROOT} path was.
            return self._replace_path(
                link or match.group("rel"), plugin, base, link=link is not None
            )
        return self._replace_path(match.group("res"), plugin, base)

    def _replace_slash(self, token: str) -> tuple[str | None, bool]:
        """Rewrite a ``/plugin:name`` host invocation to a portable skill name."""
        plugin_name, _, component = token.lstrip("/").partition(":")
        name = self._index.by_invocation.get((plugin_name, component))
        if name is None:
            self._unresolved.add(token)
            return None, False
        if self._in_code:
            return name, False
        if name == self._skill.name:
            return "this skill", True
        return f"the `{name}` skill", True

    def _replace_repo(self, token: str) -> tuple[str | None, bool]:
        """Rewrite an in-repo source coordinate; never vendor through one."""
        _, _, remainder = token.partition("/")
        plugin_name, _, rel = remainder.partition("/")
        target = REPO_ROOT / token
        name = self._index.by_path.get(target)
        if name is not None:
            return (
                ("this skill", True) if name == self._skill.name else (f"the `{name}` skill", True)
            )
        return _describe_source_path(plugin_name, rel), True

    def _replace_path(
        self, raw: str, plugin: Path, base: Path, *, link: bool = False
    ) -> tuple[str | None, bool]:
        """Vendor a resource path, name a peer component, or leave it verbatim.

        A Markdown link target that names no bundled file is a plain link, not
        a project path, and is left alone without being recorded as external.
        """
        for candidate in (raw, raw.rstrip(".,;:")):
            resolved = self._resolve(candidate, plugin, base)
            if resolved is None:
                continue
            target, owner = resolved
            name = self._index.by_path.get(target)
            if name is not None:
                if name == self._skill.name:
                    return "this skill", True
                return f"the `{name}` skill", True
            suffix = raw[len(candidate) :]
            key = self._vendor(target, owner)
            spelled = self._spell(key)
            self._links.append((self._emitting, spelled, key))
            return spelled + suffix, False
        if not link or raw.startswith(("../", *RESOURCE_DIRS)):
            self._external.add(raw)
        return None, False

    def _resolve(self, raw: str, plugin: Path, base: Path) -> tuple[Path, Path] | None:
        """Resolve a relative reference to an existing file and its owning plugin."""
        for root in (base, plugin):
            target = (root / raw).resolve()
            if not target.is_file():
                continue
            owner = _plugin_of(target)
            if owner is None:
                continue
            return target, owner
        return None


__all__ = [
    "REPO_PATH_PATTERN",
    "RESOURCE_DIRS",
    "SPEC_FRONTMATTER_KEYS",
    "TOKEN_RE",
    "BuiltSkill",
    "OutputSkill",
    "PortableIndex",
    "SkillBuilder",
    "SourceComponent",
    "imported_modules",
    "sibling_module",
    "strip_frontmatter",
]
