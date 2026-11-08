#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.15"
# dependencies = [
#     "pydantic>=2.0",
#     "rich>=13.0",
#     "typer>=0.15",
#     "pyyaml>=6.0",
# ]
#
# [tool.ty.environment]
# extra-paths = ["."]
# ///
"""Marketplace management CLI for tony/skills.

Validates marketplace manifests, plugin structures, and skill frontmatter.
Syncs the marketplace manifest with discovered plugin directories.
"""

import ast
import asyncio
import json
import os
import posixpath
import re
import shutil
import stat
import subprocess
import tempfile
import tomllib
import typing as t
from pathlib import Path

import _doc_lint
import pydantic
import rich.console
import rich.markup
import typer
from _portable_render import (
    OPENAI_YAML_REL,
    RESOURCE_DIRS,
    SPEC_FRONTMATTER_KEYS,
    TOKEN_RE,
    VENDOR_MARKER,
    BuiltSkill,
    OutputSkill,
    PortableIndex,
    SkillBuilder,
    SourceComponent,
    fenced_blocks,
    has_verbatim_fences,
    imported_modules,
    render_openai_yaml,
    sibling_module,
    strip_frontmatter,
)
from _private_path import PrivatePath
lazy import yaml
lazy from rich.table import Table

RESERVED_MARKETPLACE_NAMES = frozenset(
    {
        "claude-code-marketplace",
        "claude-code-plugins",
        "claude-plugins-official",
        "anthropic-marketplace",
        "anthropic-plugins",
        "agent-skills",
        "life-sciences",
    }
)
"""Names explicitly reserved by the Claude Code plugin system."""

_PLUGIN_RELATED_WORDS = frozenset(
    {
        "plugin",
        "plugins",
        "marketplace",
        "tools",
        "extensions",
    }
)

REPO_ROOT = Path(__file__).resolve().parent.parent
MARKETPLACE_PATH = REPO_ROOT / ".claude-plugin" / "marketplace.json"
PLUGINS_DIR = REPO_ROOT / "plugins"
README_PATH = REPO_ROOT / "README.md"

README_ROW_RE = re.compile(
    r"^\| \[(?P<name>[^\]]+)\]\(plugins/[^)]*\) \| (?P<desc>.+?) \|[ \t]*\r?$",
    re.MULTILINE,
)
"""A plugin row in the README table. The table is hand-maintained, so it
drifts from the manifest unless something compares the two.

Trailing whitespace and a carriage return are tolerated because neither
changes what the row says. ``$`` matches before ``\\n``, so a CRLF checkout
puts ``\\r`` where the pattern would otherwise demand ``|`` — without the
``\\r?`` every row fails to match at once, and each plugin is reported
missing rather than the line endings being reported."""


app = typer.Typer(
    help="Marketplace management CLI for tony/skills.",
    invoke_without_command=True,
)
console = rich.console.Console()


@app.callback()
def _main(ctx: typer.Context) -> None:
    """Marketplace management CLI for tony/skills."""
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())


class Author(pydantic.BaseModel):
    """Author metadata for a plugin or marketplace.

    Examples
    --------
    >>> Author(name="Test", email="test@example.com")
    Author(name='Test', email='test@example.com', url=None)
    """

    name: str
    email: str | None = None
    url: str | None = None


type Category = t.Literal[
    "database",
    "deployment",
    "design",
    "development",
    "learning",
    "monitoring",
    "productivity",
    "security",
    "testing",
]


class PluginEntry(pydantic.BaseModel):
    """A plugin entry in the marketplace manifest.

    Examples
    --------
    >>> entry = PluginEntry(
    ...     name="test",
    ...     description="A test plugin",
    ...     version="1.0.0",
    ...     author=Author(name="Test"),
    ...     source="./plugins/test",
    ...     category="development",
    ... )
    >>> entry.name
    'test'

    Invalid categories are rejected:

    >>> try:
    ...     PluginEntry(
    ...         name="bad",
    ...         description="Bad",
    ...         version="1.0.0",
    ...         author=Author(name="Test"),
    ...         source="./plugins/bad",
    ...         category="invalid-category",
    ...     )
    ... except pydantic.ValidationError:
    ...     print("rejected")
    rejected
    """

    name: str
    description: str
    version: str
    author: Author
    source: str
    category: Category
    tags: list[str] | None = None
    homepage: str | None = None
    repository: str | None = None
    license: str | None = None
    keywords: list[str] | None = None
    strict: bool | None = None


class MarketplaceMetadata(pydantic.BaseModel):
    """Marketplace metadata block (required by ``claude plugin validate``).

    ``pluginRoot`` is the base path Claude Code applies to relative plugin
    sources. It must be declared here so ``sync --write`` round-trips it
    instead of dropping it: third-party skill installers key off its exact
    spelling to decide whether to walk ``plugins/*/skills``.

    Examples
    --------
    >>> MarketplaceMetadata(description="Test marketplace")
    MarketplaceMetadata(description='Test marketplace', pluginRoot=None)

    >>> MarketplaceMetadata(description="Test", pluginRoot=".").pluginRoot
    '.'
    """

    description: str
    pluginRoot: str | None = None  # noqa: N815


class MarketplaceManifest(pydantic.BaseModel):
    """Top-level marketplace manifest schema.

    Examples
    --------
    >>> manifest = MarketplaceManifest(
    ...     name="test-marketplace",
    ...     metadata=MarketplaceMetadata(description="Test"),
    ...     owner=Author(name="Test"),
    ...     plugins=[],
    ... )
    >>> manifest.name
    'test-marketplace'
    """

    name: str
    description: str | None = None
    metadata: MarketplaceMetadata
    owner: Author
    plugins: list[PluginEntry]


class PluginJson(pydantic.BaseModel):
    """Individual plugin.json schema.

    Examples
    --------
    >>> pj = PluginJson(name="test", description="A test plugin")
    >>> pj.name
    'test'
    """

    name: str
    description: str
    author: Author | None = None
    version: str | None = None
    homepage: str | None = None
    repository: str | None = None
    license: str | None = None
    keywords: list[str] | None = None


class CodexPluginInterface(pydantic.BaseModel):
    """The ``interface`` block Codex shows in its plugin directory.

    Every field is derived from the Claude manifest and marketplace entry;
    capabilities, legal URLs, icons and screenshots have no source here and
    are omitted.
    """

    displayName: str  # noqa: N815
    shortDescription: str  # noqa: N815
    longDescription: str  # noqa: N815
    developerName: str | None = None  # noqa: N815
    category: str | None = None
    websiteURL: str | None = None  # noqa: N815


class CodexPluginJson(pydantic.BaseModel):
    """A plugin's ``.codex-plugin/plugin.json``, Codex's required entry point.

    ``skills`` names the default location rather than relying on it, so the
    manifest states where Codex looks instead of leaving it implicit.

    Examples
    --------
    >>> CodexPluginJson(name="commit", version="0.0.1", description="d").skills
    './skills/'
    """

    name: str
    version: str
    description: str
    author: Author | None = None
    homepage: str | None = None
    repository: str | None = None
    license: str | None = None
    keywords: list[str] | None = None
    skills: str = "./skills/"
    interface: CodexPluginInterface | None = None


def _first_sentence(text: str) -> str:
    """Return the first sentence of *text*, for a one-line summary.

    Examples
    --------
    >>> _first_sentence("Rebase onto trunk. Then verify.")
    'Rebase onto trunk.'
    >>> _first_sentence("No period here")
    'No period here'
    """
    flat = " ".join(text.split())
    head, sep, _ = flat.partition(". ")
    return head + sep.strip() if sep else flat


class CodexSource(pydantic.BaseModel):
    """A local plugin source in Codex's marketplace format."""

    source: t.Literal["local"] = "local"
    path: str


class CodexPolicy(pydantic.BaseModel):
    """Install and authentication policy for one Codex marketplace entry."""

    installation: t.Literal["AVAILABLE", "INSTALLED_BY_DEFAULT", "NOT_AVAILABLE"] = "AVAILABLE"
    authentication: t.Literal["ON_INSTALL", "ON_FIRST_USE"] = "ON_INSTALL"


class CodexPluginEntry(pydantic.BaseModel):
    """One plugin in Codex's marketplace manifest."""

    name: str
    source: CodexSource
    policy: CodexPolicy
    category: str


class CodexInterface(pydantic.BaseModel):
    """Install-surface metadata for a Codex marketplace."""

    displayName: str  # noqa: N815


class CodexMarketplace(pydantic.BaseModel):
    """Top-level schema for ``.agents/plugins/marketplace.json``."""

    name: str
    interface: CodexInterface
    plugins: list[CodexPluginEntry]


def load_marketplace() -> MarketplaceManifest:
    """Load and validate the marketplace manifest.

    Returns
    -------
    MarketplaceManifest
        The parsed and validated manifest.

    Raises
    ------
    SystemExit
        If the manifest file is missing or invalid.
    """
    if not MARKETPLACE_PATH.exists():
        console.print(f"[red]Error:[/red] {PrivatePath(MARKETPLACE_PATH)} not found")
        raise SystemExit(1)
    raw = t.cast("dict[str, t.Any]", json.loads(MARKETPLACE_PATH.read_text(encoding="utf-8")))
    return MarketplaceManifest.model_validate(raw)


def validate_marketplace_name(name: str) -> list[str]:
    """Check a marketplace name against reserved name restrictions.

    Returns a list of error messages (empty if the name is valid).

    Parameters
    ----------
    name : str
        The marketplace name to validate.

    Returns
    -------
    list[str]
        Error messages for any violations found.

    Examples
    --------
    Reserved names are rejected:

    >>> validate_marketplace_name("claude-plugins-official")
    ["Marketplace name 'claude-plugins-official' is reserved"]

    Names containing 'claude' with plugin-related words are rejected:

    >>> errs = validate_marketplace_name("claude-plugins")
    >>> len(errs) == 1 and "impersonates" in errs[0]
    True

    Names containing 'anthropic' are rejected:

    >>> errs = validate_marketplace_name("anthropic-tools-v2")
    >>> len(errs) == 1 and "anthropic" in errs[0]
    True

    Non-reserved names pass:

    >>> validate_marketplace_name("skills")
    []
    """
    errors: list[str] = []

    if name in RESERVED_MARKETPLACE_NAMES:
        errors.append(f"Marketplace name '{name}' is reserved")
        return errors

    if "anthropic" in name:
        errors.append(
            f"Marketplace name '{name}' impersonates an official marketplace (contains 'anthropic')"
        )
        return errors

    if "official" in name:
        errors.append(
            f"Marketplace name '{name}' impersonates an official marketplace (contains 'official')"
        )
        return errors

    if "claude" in name:
        for word in _PLUGIN_RELATED_WORDS:
            if word in name:
                msg = (
                    f"Marketplace name '{name}' impersonates an official"
                    f" marketplace (contains 'claude' with '{word}')"
                )
                errors.append(msg)
                return errors

    return errors


def discover_plugins() -> list[Path]:
    """Find all plugin directories under plugins/.

    Returns
    -------
    list[Path]
        Sorted list of directories containing .claude-plugin/plugin.json.
    """
    if not PLUGINS_DIR.exists():
        return []
    return sorted(
        d
        for d in PLUGINS_DIR.iterdir()
        if d.is_dir() and (d / ".claude-plugin" / "plugin.json").exists()
    )


def parse_frontmatter(path: Path) -> dict[str, t.Any] | None:
    r"""Parse YAML frontmatter from a markdown file.

    Parameters
    ----------
    path : Path
        Path to the markdown file.

    Returns
    -------
    dict[str, Any] or None
        Parsed frontmatter dict, or None if no frontmatter found.

    Examples
    --------
    >>> from pathlib import Path
    >>> import tempfile, os
    >>> d = tempfile.mkdtemp()
    >>> p = Path(d) / "test.md"
    >>> _ = p.write_text("---\ndescription: hello\n---\n# Title\n")
    >>> result = parse_frontmatter(p)
    >>> result["description"]
    'hello'
    >>> p2 = Path(d) / "no_fm.md"
    >>> _ = p2.write_text("# No frontmatter\n")
    >>> parse_frontmatter(p2) is None
    True
    """
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None
    end = text.find("---", 3)
    if end == -1:
        return None
    fm_text = text[3:end].strip()
    try:
        loaded = t.cast("object", yaml.safe_load(fm_text))
    except yaml.YAMLError:
        return None
    if isinstance(loaded, dict):
        return t.cast("dict[str, t.Any]", loaded)
    return None


def _validate_agents_dir(plugin_name: str, agents_dir: Path) -> list[str]:
    """Validate agents/*.md frontmatter in a plugin directory."""
    errors: list[str] = []
    for md_file in sorted(agents_dir.glob("*.md")):
        fm = parse_frontmatter(md_file)
        if fm is None:
            errors.append(f"[{plugin_name}] agents/{md_file.name}: Missing YAML frontmatter")
        else:
            errors.extend(
                f"[{plugin_name}] agents/{md_file.name}: Frontmatter missing '{field}'"
                for field in ("name", "description")
                if field not in fm
            )
    return errors


def _validate_skills_dir(plugin_name: str, skills_dir: Path) -> list[str]:
    """Validate skills/*/SKILL.md frontmatter in a plugin directory."""
    errors: list[str] = []
    for skill_subdir in sorted(d for d in skills_dir.iterdir() if d.is_dir()):
        skill_md = skill_subdir / "SKILL.md"
        if not skill_md.exists():
            errors.append(f"[{plugin_name}] skills/{skill_subdir.name}/: Missing SKILL.md")
            continue
        fm = parse_frontmatter(skill_md)
        if fm is None:
            errors.append(
                f"[{plugin_name}] skills/{skill_subdir.name}/SKILL.md: Missing YAML frontmatter"
            )
        else:
            prefix = f"[{plugin_name}] skills/{skill_subdir.name}/SKILL.md"
            errors.extend(
                f"{prefix}: Frontmatter missing '{field}'"
                for field in ("name", "description")
                if field not in fm
            )
            # Claude Code invokes a plugin skill by directory, Codex by name.
            if "name" in fm and fm["name"] != skill_subdir.name:
                errors.append(f"{prefix}: name '{fm['name']}' differs from its directory")
    return errors


def _validate_mcp_json(plugin_name: str, path: Path) -> list[str]:
    """Validate .mcp.json structural requirements.

    Parameters
    ----------
    plugin_name : str
        Plugin name for error messages.
    path : Path
        Path to the .mcp.json file.

    Returns
    -------
    list[str]
        Error messages (empty if valid).

    Examples
    --------
    >>> from pathlib import Path
    >>> import tempfile
    >>> d = tempfile.mkdtemp()
    >>> p = Path(d) / ".mcp.json"
    >>> _ = p.write_text('{"server": {"type": "http", "url": "http://localhost"}}')
    >>> _validate_mcp_json("test", p)
    []

    Non-dict top-level is rejected:

    >>> _ = p.write_text('[]')
    >>> _validate_mcp_json("test", p)
    ['[test] .mcp.json: top-level value must be an object']

    Non-dict server entries are rejected:

    >>> _ = p.write_text('{"server": "bad"}')
    >>> _validate_mcp_json("test", p)
    ["[test] .mcp.json: server entry 'server' must be an object"]
    """
    errors: list[str] = []
    try:
        data = t.cast("object", json.loads(path.read_text(encoding="utf-8")))
    except json.JSONDecodeError as exc:
        errors.append(f"[{plugin_name}] .mcp.json: invalid JSON: {exc}")
        return errors

    if not isinstance(data, dict):
        errors.append(f"[{plugin_name}] .mcp.json: top-level value must be an object")
        return errors

    servers = t.cast("dict[str, object]", data)
    for key, value in servers.items():
        if not isinstance(value, dict):
            errors.append(f"[{plugin_name}] .mcp.json: server entry '{key}' must be an object")
    return errors


def _validate_lsp_json(plugin_name: str, path: Path) -> list[str]:
    """Validate .lsp.json structural requirements.

    Parameters
    ----------
    plugin_name : str
        Plugin name for error messages.
    path : Path
        Path to the .lsp.json file.

    Returns
    -------
    list[str]
        Error messages (empty if valid).

    Examples
    --------
    >>> from pathlib import Path
    >>> import tempfile
    >>> d = tempfile.mkdtemp()
    >>> p = Path(d) / ".lsp.json"
    >>> data = '{"pyright": {"command": "pyright-langserver",'
    >>> data += ' "extensionToLanguage": {".py": "python"}}}'
    >>> _ = p.write_text(data)
    >>> _validate_lsp_json("test", p)
    []

    Non-dict top-level is rejected:

    >>> _ = p.write_text('[]')
    >>> _validate_lsp_json("test", p)
    ['[test] .lsp.json: top-level value must be an object']

    Missing required fields are reported:

    >>> _ = p.write_text('{"pyright": {"command": "pyright-langserver"}}')
    >>> _validate_lsp_json("test", p)
    ["[test] .lsp.json: server 'pyright' missing required field 'extensionToLanguage'"]

    >>> _ = p.write_text('{"pyright": {"extensionToLanguage": {".py": "python"}}}')
    >>> _validate_lsp_json("test", p)
    ["[test] .lsp.json: server 'pyright' missing required field 'command'"]
    """
    errors: list[str] = []
    try:
        data = t.cast("object", json.loads(path.read_text(encoding="utf-8")))
    except json.JSONDecodeError as exc:
        errors.append(f"[{plugin_name}] .lsp.json: invalid JSON: {exc}")
        return errors

    if not isinstance(data, dict):
        errors.append(f"[{plugin_name}] .lsp.json: top-level value must be an object")
        return errors

    servers = t.cast("dict[str, object]", data)
    for key, value in servers.items():
        if not isinstance(value, dict):
            errors.append(f"[{plugin_name}] .lsp.json: server entry '{key}' must be an object")
            continue
        errors.extend(
            f"[{plugin_name}] .lsp.json: server '{key}' missing required field '{field}'"
            for field in ("command", "extensionToLanguage")
            if field not in value
        )
    return errors


def _is_runtime_instruction(rel: Path) -> bool:
    """Whether a plugin-relative file is loaded into a host's context at runtime.

    Instruction text is read with the *user's* project as the working directory,
    so a repo-relative path in it addresses nothing. A plugin's ``README.md`` and
    its dated design specs are read on GitHub instead, where a repo-relative path
    is the correct address and rewriting it would break the link.

    Parameters
    ----------
    rel : Path
        Path relative to the plugin directory.

    Returns
    -------
    bool
        True when the file ships as instructions rather than as repo prose.

    Examples
    --------
    >>> from pathlib import Path
    >>> _is_runtime_instruction(Path("references/deslop.md"))
    True
    >>> _is_runtime_instruction(Path("README.md"))
    False

    A spec under ``docs/specs/`` describes the repo's own layout, so its
    ``plugins/...`` coordinates are the subject matter:

    >>> _is_runtime_instruction(Path("docs/specs/2026-05-17-plan-handoff.md"))
    False

    A doc a skill loads at runtime is not exempt just for living in ``docs/``:

    >>> _is_runtime_instruction(Path("docs/protocol.md"))
    True
    """
    if rel.parts == ("README.md",):
        return False
    return rel.parts[:2] != ("docs", "specs")


# The split is by name, not reachability: a spec a skill loads goes unchecked.


def _citation_error(owner: str, token: str, *, exists: bool, runtime: bool) -> str | None:
    """Report why a repo-relative plugin citation is wrong, or None if it is fine.

    Parameters
    ----------
    owner : str
        Name of the plugin whose file contains the citation.
    token : str
        The cited path, without any trailing ``:line`` suffix.
    exists : bool
        Whether the cited path resolves in this repo.
    runtime : bool
        Whether the citing file ships as instructions (see
        :func:`_is_runtime_instruction`).

    Returns
    -------
    str or None
        Error text, or None when the citation is legitimate.

    Examples
    --------
    A file citing its own plugin by repo path breaks on install, because the host
    resolves the path against the user's project:

    >>> _citation_error("pr", "plugins/pr/references/review.md", exists=True, runtime=True)
    "cites its own plugin by repo path; climb out of the skill with '../../references/review.md'"

    A citation into a *different* plugin has no climbing spelling, since each
    plugin installs alone, so it is left alone:

    >>> _citation_error("weave", "plugins/pr/references/x.md", exists=True, runtime=True) is None
    True

    Repo prose may address its own plugin, since it is read in the repo:

    >>> _citation_error("weave", "plugins/weave/README.md", exists=True, runtime=False) is None
    True

    A path that resolves nowhere is an error in any file, in any direction:

    >>> _citation_error("slop", "plugins/pr/references/gone.md", exists=False, runtime=True)
    'cites a path that does not exist'
    """
    if not exists:
        return "cites a path that does not exist"
    _, _, remainder = token.partition("/")
    cited, _, rel = remainder.partition("/")
    if runtime and cited == owner:
        return f"cites its own plugin by repo path; climb out of the skill with '../../{rel}'"
    return None


def _validate_path_citations(plugin_name: str, plugin_dir: Path) -> list[str]:
    """Check every ``plugins/...`` path a plugin's files cite.

    Two failures, both invisible until someone installs the plugin: a file
    pointing into its own plugin by repo path, and a path that resolves nowhere.

    Parameters
    ----------
    plugin_name : str
        Plugin name for error messages.
    plugin_dir : Path
        Path to the plugin directory.

    Returns
    -------
    list[str]
        Error messages (empty if valid).
    """
    errors: list[str] = []
    for path in sorted(plugin_dir.rglob("*")):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        rel = path.relative_to(plugin_dir)
        runtime = _is_runtime_instruction(rel)
        for lineno, line in enumerate(text.splitlines(), 1):
            for match in TOKEN_RE.finditer(line):
                token = match.group("repo")
                if token is None:
                    continue
                trimmed = token.rstrip(".,;:")
                exists = (REPO_ROOT / token).exists() or (REPO_ROOT / trimmed).exists()
                problem = _citation_error(plugin_name, trimmed, exists=exists, runtime=runtime)
                if problem is not None:
                    errors.append(f"[{plugin_name}] {rel}:{lineno}: '{token}' {problem}")
    return errors


_BANG_CONTEXT_RE = re.compile(r"`![a-z]|(?:^|\s)!`[a-z]")
_RELATIVE_LINK_RE = re.compile(r"(?:\.\./)+[A-Za-z0-9._/-]+")
_CONTENTS_RE = re.compile(r"^(?:#{1,3} |\*\*)?Contents\b", re.MULTILINE)
_LINTED_SUFFIXES = frozenset({".md", ".yml", ".yaml", ".sh", ".py", ".json", ".tmpl", ".txt"})
SKILL_BODY_MAX_LINES = 500
REFERENCE_CONTENTS_MIN_LINES = 100


def _prose_lines(text: str) -> list[tuple[int, str]]:
    r"""Return ``(line number, line)`` pairs that sit outside fenced code blocks.

    Examples
    --------
    >>> _prose_lines("a\n```\nb\n```\nc\n")
    [(1, 'a'), (5, 'c')]
    """
    out: list[tuple[int, str]] = []
    fenced = False
    for number, line in enumerate(text.splitlines(), start=1):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if not fenced:
            out.append((number, line))
    return out


def _escapes_plugin(source: Path, link: str, plugin_dir: Path) -> bool:
    """Return True when ``link``, relative to ``source``, resolves outside ``plugin_dir``.

    Examples
    --------
    >>> root = Path("/r/plugins/p")
    >>> _escapes_plugin(root / "skills/s/SKILL.md", "../../references/x.md", root)
    False
    >>> _escapes_plugin(root / "skills/s/SKILL.md", "../../../q/references/x.md", root)
    True
    """
    target = (source.parent / link).resolve()
    return not target.is_relative_to(plugin_dir.resolve())


def _bundled_links(text: str) -> list[str]:
    """Return relative links into a plugin's bundled directories, fences included.

    Examples
    --------
    >>> _bundled_links("Run `python3 ../scripts/x.py` and read ../../references/y.md.")
    ['../scripts/x.py', '../../references/y.md']
    >>> _bundled_links("See ../../docs/z.md; a reference writes ../scripts/.")
    []
    """
    return [
        link.rstrip(".,;:")
        for link in t.cast("list[str]", _RELATIVE_LINK_RE.findall(text))
        if re.match(r"(?:\.\./)+(?:scripts|references|skills)/[^/.]", link)
    ]


PLAN_PRELUDE = (
    "Enter plan mode before the first edit. In Claude Code call `EnterPlanMode`; "
    "in Cursor, Codex, or Gemini use `/plan` or `Shift+Tab`. "
    "Where plan mode is unavailable, present the plan as text."
)
"""Verbatim opening AGENTS.md requires under an Orchestration Plan heading."""


def _plan_prelude_missing(text: str) -> bool:
    r"""Report whether an Orchestration Plan heading lacks the required prelude.

    Whitespace is collapsed first, so the prelude may wrap across lines.

    Examples
    --------
    >>> _plan_prelude_missing("# T\n\n## Orchestration Plan\n\nPlan it.\n")
    True
    >>> wrapped = PLAN_PRELUDE.replace(". ", ".\n")
    >>> _plan_prelude_missing(f"## Orchestration Plan\n\n{wrapped}\n")
    False
    >>> _plan_prelude_missing("## Steps\n\nNo plan section here.\n")
    False
    >>> _plan_prelude_missing("## Orchestration plan\n\nPlan it.\n")
    True
    """
    if not re.search(r"^#+ .*Orchestration Plan", text, re.MULTILINE | re.IGNORECASE):
        return False
    return PLAN_PRELUDE not in " ".join(text.split())


def _check_estate_rules(plugin_dir: Path) -> list[str]:
    """Enforce the skill-library rules that keep plugins standalone and lean.

    - No ``!`` context expansion: it never expands on Codex, and on Claude Code a
      failing or ungranted command empties the whole skill without an error.
    - No relative link that resolves outside the plugin; installs are standalone.
    - Skill bodies stay within ``SKILL_BODY_MAX_LINES``.
    - A markdown resource longer than ``REFERENCE_CONTENTS_MIN_LINES`` opens
      with a contents list.
    - Every resource file is named by some other file in the plugin.
    - A skill or reference running a bundled script says how its path resolves.
    - Every eval grader declares its ``type``.
    - An Orchestration Plan section carries the verbatim plan-mode prelude.
    """
    name = plugin_dir.name
    errors: list[str] = []
    texts = {
        path: path.read_text(encoding="utf-8", errors="replace")
        for path in sorted(plugin_dir.rglob("*"))
        if path.is_file()
        and path.suffix in _LINTED_SUFFIXES
        and path.relative_to(plugin_dir).parts[0]
        not in {"evals", ".claude-plugin", ".codex-plugin"}
    }

    for path, text in texts.items():
        rel = path.relative_to(plugin_dir)
        if path.suffix != ".md" or path.name == "README.md":
            continue
        for number, line in _prose_lines(text):
            if _BANG_CONTEXT_RE.search(line):
                errors.append(f"[{name}] {rel}:{number}: '!' context expansion is not allowed")
            links = t.cast("list[str]", _RELATIVE_LINK_RE.findall(line))
            errors.extend(
                f"[{name}] {rel}:{number}: '{link}' leaves the plugin"
                for link in links
                if _escapes_plugin(path, link, plugin_dir)
            )
        errors.extend(
            f"[{name}] {rel}: '{link}' does not resolve from this file"
            for link in _bundled_links(text)
            if not _escapes_plugin(path, link, plugin_dir) and not (path.parent / link).exists()
        )
        # The agent's shell runs in the user's project, not the skill directory.
        script_ref = "../../scripts/" if path.name == "SKILL.md" else "../scripts/"
        if script_ref in text and not re.search(
            r"(skill|file)'s (own |base )?director|absolute path", text, re.IGNORECASE
        ):
            errors.append(f"[{name}] {rel}: runs {script_ref} with no path-resolution note")
        if _plan_prelude_missing(text):
            errors.append(f"[{name}] {rel}: Orchestration Plan lacks the plan-mode prelude")
        if path.name == "SKILL.md":
            body_lines = strip_frontmatter(text).count("\n")
            if body_lines > SKILL_BODY_MAX_LINES:
                errors.append(
                    f"[{name}] {rel}: body is {body_lines} lines (max {SKILL_BODY_MAX_LINES})"
                )
        elif text.count("\n") > REFERENCE_CONTENTS_MIN_LINES and not _CONTENTS_RE.search(
            "\n".join(text.splitlines()[:40])
        ):
            errors.append(
                f"[{name}] {rel}: over {REFERENCE_CONTENTS_MIN_LINES} lines and no Contents list"
            )

    for path in texts:
        rel = path.relative_to(plugin_dir)
        if rel.parts[0] not in (*RESOURCE_DIRS, "scripts") or path.name.startswith("test_"):
            continue
        # A README may name a contributor file, but a vendored copy must be
        # read by some skill or imported by a script, or it ships unused.
        vendored = any(VENDOR_MARKER in line for line in texts[path].splitlines()[:2])
        named = any(
            path.name in other_text
            or (other.suffix == ".py" and path.stem in imported_modules(other_text))
            for other, other_text in texts.items()
            if other != path and not (vendored and other.name == "README.md")
        )
        if not named:
            errors.append(f"[{name}] {rel}: no skill or resource in the plugin names it")

    # The eval runner rejects the whole case when one grader lacks a type.
    for grader in sorted(plugin_dir.glob("evals/*/graders/*.md")):
        if not (parse_frontmatter(grader) or {}).get("type"):
            rel = grader.relative_to(plugin_dir)
            errors.append(f"[{name}] {rel}: grader frontmatter has no 'type'")
    return errors


def _python_dirs_missing(testpaths: list[str], python_dirs: list[str]) -> list[str]:
    """Return the directories that hold shipped Python but no pytest test path covers.

    Examples
    --------
    >>> _python_dirs_missing(["scripts", "plugins/a/scripts"], ["plugins/a/scripts", "plugins/b"])
    ['plugins/b']
    >>> _python_dirs_missing(["plugins"], ["plugins/a/scripts"])
    []
    """
    return [
        d for d in python_dirs if not any(d == tp or d.startswith(f"{tp}/") for tp in testpaths)
    ]


def _check_testpaths() -> list[str]:
    """Fail when a plugin ships Python whose doctests pytest would never collect."""
    config = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    tool = t.cast("dict[str, object]", config.get("tool", {}))
    pytest_config = t.cast("dict[str, object]", tool.get("pytest", {}))
    ini_options = t.cast("dict[str, object]", pytest_config.get("ini_options", {}))
    testpaths = t.cast("list[str]", ini_options.get("testpaths", []))
    python_dirs = sorted(
        {
            path.parent.relative_to(REPO_ROOT).as_posix()
            for path in PLUGINS_DIR.rglob("*.py")
            if not {"evals", "templates", "__pycache__"} & set(path.relative_to(PLUGINS_DIR).parts)
        }
    )
    return [
        f"pyproject.toml: pytest testpaths omits '{d}', which ships Python"
        for d in _python_dirs_missing(testpaths, python_dirs)
    ]


# Agents assign `G=<path>` and call `python3 $G sub` in one command, so only a
# script name followed by an adjacency requirement (` sub`, `\s+sub`) misses it.
SCRIPT_VAR_FORM = r"\$\{?[A-Za-z_]\w*\}?"
_VAR_REF_RE = re.compile(r"\\\$(?:\\\{\?)?(?:\\w|\[A-Za-z_\])")
_OPTIONAL_QUOTE_RE = re.compile(
    r"""(?:\[[^\]]*(?:"|'|\\x27)[^\]]*\]|\(\?:[^()]*(?:"|')[^()]*\))\?"""
)
_SPAN_OR_END_RE = re.compile(r"$|\||\)|\.[*+]|\[\\s\\S\][*+]|\[\^\\r\\n\][*+]")


def _lacks_script_var_form(pattern: str, scripts: list[str]) -> bool:
    r"""Return whether a grader pattern names a bundled script but no shell-variable form.

    A name offends only when an adjacency requirement follows it (past one optional
    quote); the end, `|`, `)`, or a `.*`-style span means a variable call still matches.

    Examples
    --------
    >>> _lacks_script_var_form(r"branch_gate\.py\s+series", ["branch_gate.py"])
    True
    >>> form = r"(?:branch_gate\.py|python3?\s+\$\{?[A-Za-z_]\w*\}?)\s+series"
    >>> _lacks_script_var_form(form, ["branch_gate.py"])
    False
    >>> _lacks_script_var_form(r"(?:merge_pr\.py merge|\$\{?\w+\}? merge)", ["merge_pr.py"])
    False
    >>> _lacks_script_var_form(r"git push", ["branch_gate.py"])
    False
    >>> _lacks_script_var_form(r"pr_backup\.py", ["pr_backup.py"])
    False
    >>> _lacks_script_var_form(r"pr_backup\.py save", ["pr_backup.py"])
    True
    >>> _lacks_script_var_form(r"scan_body\.py.*--media", ["scan_body.py"])
    False
    >>> _lacks_script_var_form(r"replay\.py[\"\x27]?\s+start\b", ["replay.py"])
    True
    >>> _lacks_script_var_form(r"term_metrics\.py[^\r\n]*--check-brief", ["term_metrics.py"])
    False
    >>> _lacks_script_var_form(r"autosquash\.py|git rebase", ["autosquash.py"])
    False
    """
    if _VAR_REF_RE.search(pattern):
        return False
    for name in scripts:
        for spelling in {name.replace(".", r"\."), name}:
            for match in re.finditer(re.escape(spelling), pattern):
                rest = pattern[match.end() :]
                quote = _OPTIONAL_QUOTE_RE.match(rest)
                if quote:
                    rest = rest[quote.end() :]
                if not _SPAN_OR_END_RE.match(rest):
                    return True
    return False


def _script_var_offenders() -> set[str]:
    """Return `plugin/case:grader` for each Bash matcher that lacks the variable form."""
    offenders: set[str] = set()
    for case in sorted(PLUGINS_DIR.glob("*/evals/*/case.yaml")):
        plugin_dir = case.parents[2]
        scripts = [
            p.name
            for p in (plugin_dir / "scripts").glob("*")
            if p.suffix in {".py", ".sh"} and not p.name.startswith("test_")
        ]
        if not scripts:
            continue
        data = t.cast("dict[str, object]", yaml.safe_load(case.read_text(encoding="utf-8")) or {})
        for grader in t.cast("list[dict[str, object]]", data.get("graders") or []):
            matchers = [grader] if grader.get("type") == "tool_used" else []
            if grader.get("type") == "tool_order":
                matchers = [m for m in (grader.get("before"), grader.get("after")) if m]
            for matcher in t.cast("list[dict[str, object]]", matchers):
                pattern = matcher.get("input_match")
                bash = matcher.get("tool") == "Bash" and isinstance(pattern, str)
                if bash and _lacks_script_var_form(pattern, scripts):
                    offenders.add(f"{plugin_dir.name}/{case.parent.name}:{grader.get('name')}")
    return offenders


def _check_script_var_graders() -> list[str]:
    """Fail on each Bash grader that names a bundled script but not a shell-variable call."""
    return [
        f"{o}: names a bundled script but not `python3 $VAR`; add `{SCRIPT_VAR_FORM}`"
        for o in sorted(_script_var_offenders())
    ]


def _engine_strings(source: str, *, models: bool = True) -> list[str]:
    """Return the model IDs and credit-exhaustion patterns the weave engine hard-codes.

    Examples
    --------
    >>> src = 'LANES = {"x": (("agy", "Pro"), ("codex", None))}; CREDIT_PATTERNS = ("quota",)'
    >>> _engine_strings(src)
    ['Pro', 'quota']
    >>> _engine_strings(src, models=False)
    ['quota']
    """
    ids: list[str] = []
    patterns: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            name, value = node.target.id, node.value
        elif isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            name, value = node.targets[0].id, node.value
        else:
            continue
        if value is None:
            continue
        if name == "LANES":
            for pair in ast.walk(value):
                if isinstance(pair, ast.Tuple) and len(pair.elts) > 1:
                    model = pair.elts[1]
                    if isinstance(model, ast.Constant) and isinstance(model.value, str):
                        ids.append(model.value)
        elif name == "CREDIT_PATTERNS":
            patterns.extend(
                c.value
                for c in ast.walk(value)
                if isinstance(c, ast.Constant) and isinstance(c.value, str)
            )
    return [*dict.fromkeys(ids), *patterns] if models else patterns


def _check_engine_parity() -> list[str]:
    """Fail when the weave engine names a credit pattern model-cli never mentions.

    Model IDs are exempt: model-cli picks them from the live listing at run time.
    """
    engine = PLUGINS_DIR / "weave" / "scripts" / "engine.py"
    model_cli = PLUGINS_DIR / "model-cli"
    if not engine.exists() or not model_cli.exists():
        return []
    haystack = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [
            model_cli / "references" / "dispatch.md",
            *model_cli.glob("skills/*/SKILL.md"),
            *model_cli.glob("scripts/[!t]*.py"),
        ]
    )
    return [
        f"weave engine.py: '{s}' appears in neither model-cli's dispatch.md, skills, nor scripts"
        for s in _engine_strings(engine.read_text(encoding="utf-8"), models=False)
        if s not in haystack
    ]


def _verifier_prose_constraint(text: str) -> str:
    r"""Read the shared verifier constraint without quote indentation or wrapping.

    >>> _verifier_prose_constraint('> Do not introduce slop.\n> Use concrete text.\n')
    'Do not introduce slop. Use concrete text.'
    >>> _verifier_prose_constraint('  > Do not introduce slop. Use concrete text.\n')
    'Do not introduce slop. Use concrete text.'
    >>> _verifier_prose_constraint('No verifier here.')
    ''
    """
    match = re.search(
        r"^[ \t]*> Do not introduce slop[^\n]*(?:\n[ \t]*>[^\n]*)*", text, re.MULTILINE
    )
    if match is None:
        return ""
    return " ".join(re.sub(r"^[ \t]*>[ \t]?", "", match[0], flags=re.MULTILINE).split())


def _check_verifier_parity() -> list[str]:
    """Keep weave's embedded verifier constraint equal to slop's owning protocol."""
    owner = PLUGINS_DIR / "slop/references/detect-pipeline.md"
    copy = PLUGINS_DIR / "weave/references/deslop-pass.md"
    expected = _verifier_prose_constraint(owner.read_text(encoding="utf-8"))
    actual = _verifier_prose_constraint(copy.read_text(encoding="utf-8"))
    if expected and actual == expected:
        return []
    return ["weave deslop-pass.md: verifier prose constraint differs from slop detect-pipeline.md"]


PLUGIN_LAYOUT = frozenset(
    {
        ".claude-plugin",
        ".codex-plugin",
        "README.md",
        "skills",
        "references",
        "scripts",
        "evals",
        "templates",
    }
)


def unexpected_entries(plugin_dir: Path) -> list[str]:
    """Return top-level entries outside the AGENTS.md plugin layout.

    Every entry installs with the plugin, so maintainer notes belong elsewhere.

    >>> import tempfile
    >>> d = Path(tempfile.mkdtemp())
    >>> for n in ("skills", "docs", "__pycache__"):
    ...     (d / n).mkdir()
    >>> unexpected_entries(d)
    ['docs']
    """
    return sorted(
        e.name
        for e in plugin_dir.iterdir()
        if e.name not in PLUGIN_LAYOUT and e.name != "__pycache__"
    )


def validate_plugin_dir(plugin_dir: Path) -> list[str]:
    """Validate a single plugin directory structure.

    Parameters
    ----------
    plugin_dir : Path
        Path to the plugin directory.

    Returns
    -------
    list[str]
        List of error messages (empty if valid).
    """
    errors: list[str] = []
    name = plugin_dir.name
    errors.extend(
        f"[{name}] '{entry}' is outside the plugin layout in AGENTS.md"
        for entry in unexpected_entries(plugin_dir)
    )

    plugin_json_path = plugin_dir / ".claude-plugin" / "plugin.json"
    if not plugin_json_path.exists():
        errors.append(f"[{name}] Missing .claude-plugin/plugin.json")
    else:
        try:
            raw = t.cast(
                "dict[str, t.Any]",
                json.loads(plugin_json_path.read_text(encoding="utf-8")),
            )
            pj = PluginJson.model_validate(raw)
            if pj.name != name:
                errors.append(
                    f"[{name}] plugin.json name '{pj.name}' does not match directory name '{name}'"
                )
        except (json.JSONDecodeError, pydantic.ValidationError) as exc:
            errors.append(f"[{name}] Invalid plugin.json: {exc}")

    readme_path = plugin_dir / "README.md"
    if not readme_path.exists():
        errors.append(f"[{name}] Missing README.md")

    # Check for at least one component directory or config file
    component_dirs = ["agents", "skills", "hooks"]
    config_files = [".mcp.json", ".lsp.json"]
    has_component = any((plugin_dir / d).exists() for d in component_dirs) or any(
        (plugin_dir / f).exists() for f in config_files
    )
    if not has_component:
        msg = f"[{name}] No component directory or config file found"
        errors.append(msg)

    if (plugin_dir / "commands").exists():
        errors.append(f"[{name}] commands/: every workflow is a skill; move it under skills/")

    # Validate agents/*.md and skills/*/SKILL.md frontmatter
    agents_dir = plugin_dir / "agents"
    if agents_dir.exists():
        errors.extend(_validate_agents_dir(name, agents_dir))

    skills_dir = plugin_dir / "skills"
    if skills_dir.exists():
        errors.extend(_validate_skills_dir(name, skills_dir))

    errors.extend(_check_estate_rules(plugin_dir))

    # Validate hooks/hooks.json exists when hooks/ is present
    hooks_dir = plugin_dir / "hooks"
    if hooks_dir.exists():
        hooks_json = hooks_dir / "hooks.json"
        if not hooks_json.exists():
            errors.append(f"[{name}] hooks/ exists but missing hooks.json")

    # Validate .mcp.json structure
    mcp_json_path = plugin_dir / ".mcp.json"
    if mcp_json_path.exists():
        errors.extend(_validate_mcp_json(name, mcp_json_path))

    # Validate .lsp.json structure
    lsp_json_path = plugin_dir / ".lsp.json"
    if lsp_json_path.exists():
        errors.extend(_validate_lsp_json(name, lsp_json_path))

    errors.extend(_validate_path_citations(name, plugin_dir))
    errors.extend(_check_readme_skills(plugin_dir))

    return errors


VALIDATE_TIMEOUT_S = 30
VALIDATE_WORKERS = min(8, os.cpu_count() or 1)


def _parse_validate_output(stdout: str, returncode: int) -> tuple[list[str], list[str]]:
    r"""Split ``claude plugin validate`` output into (errors, warnings).

    Examples
    --------
    >>> _parse_validate_output("\u276f bad\nnoise\n", 1)
    (['claude validate: bad'], [])
    >>> _parse_validate_output("\u276f meh\n", 0)
    ([], ['claude validate: meh'])
    >>> _parse_validate_output("", 0)
    ([], [])
    """
    marker = "\u276f"
    findings = [
        f"claude validate: {line.strip().removeprefix(marker).strip()}"
        for line in stdout.splitlines()
        if marker in line
    ]
    return (findings, []) if returncode != 0 else ([], findings)


async def _run_claude_validate(path: Path, gate: asyncio.Semaphore) -> tuple[list[str], list[str]]:
    """Run ``claude plugin validate`` and return (errors, warnings).

    Returns empty lists if the CLI is not available. ``gate`` bounds how many
    validations run at once.

    Parameters
    ----------
    path : Path
        Path to validate (marketplace root or plugin directory).
    gate : asyncio.Semaphore
        Concurrency limit shared by every call in one run.

    Returns
    -------
    tuple[list[str], list[str]]
        (errors, warnings) extracted from validate output.
    """
    if shutil.which("claude") is None:
        return [], []
    async with gate:
        proc = await asyncio.create_subprocess_exec(
            "claude",
            "plugin",
            "validate",
            "--strict",
            str(path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        try:
            async with asyncio.timeout(VALIDATE_TIMEOUT_S):
                stdout, _ = await proc.communicate()
        except TimeoutError:
            proc.kill()
            _ = await proc.wait()
            return [f"claude validate: {path.name} timed out after {VALIDATE_TIMEOUT_S}s"], []
    return _parse_validate_output(
        stdout.decode(errors="replace"),
        proc.returncode if proc.returncode is not None else 1,
    )


async def _validate_all(paths: list[Path]) -> list[tuple[list[str], list[str]]]:
    """Validate every path concurrently, returning results in ``paths`` order."""
    gate = asyncio.Semaphore(VALIDATE_WORKERS)
    async with asyncio.TaskGroup() as group:
        tasks = [group.create_task(_run_claude_validate(path, gate)) for path in paths]
    return [task.result() for task in tasks]


def _lint_claude_validate() -> tuple[list[str], list[str]]:
    """Run ``claude plugin validate`` on the repo and each plugin, printing status.

    A missing CLI is a skip locally and an error under CI. Skipping silently in
    CI turns the only schema-level check into a no-op while the job still
    reports zero errors, which is how a manifest that fails validation reached
    the default branch unnoticed.
    """
    if shutil.which("claude") is None:
        if os.environ.get("CI"):
            return ["claude validate: CLI not found (required under CI)"], []
        console.print("\n[dim]Skipping claude plugin validate (CLI not found)[/dim]")
        return [], []

    console.print("\n[bold]Running claude plugin validate...[/bold]")
    all_errors: list[str] = []
    all_warnings: list[str] = []
    for ve, vw in asyncio.run(_validate_all([REPO_ROOT, *discover_plugins()])):
        all_errors.extend(ve)
        all_warnings.extend(vw)
    if not all_errors:
        console.print("  [green]OK[/green]")
    return all_errors, all_warnings


def _readme_names_skill(plugin: str, skill: str, readme: str) -> bool:
    r"""Report whether *readme* names *skill* as a heading, code span, or ``plugin:skill``.

    Examples
    --------
    >>> _readme_names_skill("pkg", "up", "- `up`: bump it")
    True
    >>> _readme_names_skill("pkg", "up", "### up\n")
    True
    >>> _readme_names_skill("pkg", "up", "Run /pkg:up now")
    True
    >>> _readme_names_skill("pkg", "up", "Update everything; `update-all` too")
    False
    """
    plug, name = re.escape(plugin), re.escape(skill)
    pattern = (
        rf"^#{{1,6}}\s+`?/?(?:{plug}:)?{name}(?![\w-])"
        rf"|`/?(?:{plug}:)?{name}(?![\w-])"
        rf"|(?<![\w/:-])/?{plug}:{name}(?![\w-])"
    )
    return re.search(pattern, readme, re.MULTILINE) is not None


def _check_readme_skills(plugin_dir: Path) -> list[str]:
    """List the skills a plugin's README never names."""
    readme_path = plugin_dir / "README.md"
    skills_dir = plugin_dir / "skills"
    if not readme_path.is_file() or not skills_dir.is_dir():
        return []
    readme = readme_path.read_text(encoding="utf-8")
    return [
        f"[{plugin_dir.name}] README.md does not name skill '{d.name}'"
        for d in sorted(skills_dir.iterdir())
        if (d / "SKILL.md").is_file() and not _readme_names_skill(plugin_dir.name, d.name, readme)
    ]


def check_readme_table(manifest: MarketplaceManifest, readme: str) -> list[str]:
    r"""Compare the README plugin table against the manifest.

    The manifest is the source of truth and the table is written by hand, so
    the table silently under-reports what the marketplace ships. Nothing else
    in CI reads it.

    Rows are matched on name, then on the description a reader acts on. A
    row that disagrees is worse than a missing one, because it looks
    authoritative. The table may be split across several grouped tables.

    Examples
    --------
    >>> def _manifest(*entries: PluginEntry) -> MarketplaceManifest:
    ...     return MarketplaceManifest(
    ...         name="m",
    ...         metadata=MarketplaceMetadata(description="d"),
    ...         owner=Author(name="T"),
    ...         plugins=list(entries),
    ...     )
    >>> entry = PluginEntry(
    ...     name="commit",
    ...     description="Create git commits",
    ...     version="1.0.0",
    ...     author=Author(name="T"),
    ...     source="./plugins/commit",
    ...     category="development",
    ... )
    >>> row = "| [commit](plugins/commit/) | Create git commits |"
    >>> check_readme_table(_manifest(entry), row)
    []

    A plugin with no row is reported:

    >>> check_readme_table(_manifest(entry), "no table here")
    ["README plugin table is missing a row for 'commit'"]

    So is a row whose description drifted from the manifest:

    >>> stale = "| [commit](plugins/commit/) | Old blurb |"
    >>> check_readme_table(_manifest(entry), stale)
    ["README row 'commit': description does not match marketplace.json"]

    And a row naming a plugin the marketplace does not list:

    >>> ghost = "| [gone](plugins/gone/) | Removed |"
    >>> check_readme_table(_manifest(entry), ghost + "\n" + row)
    ["README row 'gone' names a plugin that is not in marketplace.json"]

    A plugin listed twice is reported rather than deduplicated. Keying rows
    by name alone would let the second row mask the first, so a table
    carrying two contradictory rows could report nothing at all:

    >>> check_readme_table(_manifest(entry), row + "\n" + row)
    ["README plugin table lists 'commit' more than once"]

    Trailing whitespace and CRLF endings do not change what a row says, so
    neither may fail the match. A CRLF checkout would otherwise report every
    plugin missing at once, naming the wrong cause for all of them:

    >>> check_readme_table(_manifest(entry), row + "  ")
    []
    >>> check_readme_table(_manifest(entry), row + "\r\n")
    []
    """
    rows: dict[str, re.Match[str]] = {}
    duplicates: list[str] = []
    for match in README_ROW_RE.finditer(readme):
        if match["name"] in rows:
            duplicates.append(match["name"])
        else:
            rows[match["name"]] = match

    errors = [
        f"README plugin table lists '{name}' more than once" for name in sorted(set(duplicates))
    ]
    errors.extend(
        f"README plugin table is missing a row for '{entry.name}'"
        for entry in manifest.plugins
        if entry.name not in rows
    )
    errors.extend(
        f"README row '{name}' names a plugin that is not in marketplace.json"
        for name in sorted(rows.keys() - {entry.name for entry in manifest.plugins})
    )
    for entry in manifest.plugins:
        row = rows.get(entry.name)
        if row is None:
            continue
        if row["desc"].strip() != entry.description.strip():
            errors.append(f"README row '{entry.name}': description does not match marketplace.json")
    return errors


def rewrite_readme_rows(manifest: MarketplaceManifest, readme: str) -> str:
    """Return ``readme`` with each plugin row's description set from ``manifest``.

    Rows for plugins the manifest does not list are left alone; ``lint`` reports
    them.

    Examples
    --------
    >>> entry = PluginEntry(
    ...     name="commit",
    ...     description="Create git commits",
    ...     version="1.0.0",
    ...     author=Author(name="T"),
    ...     source="./plugins/commit",
    ...     category="development",
    ... )
    >>> manifest = MarketplaceManifest(
    ...     name="m",
    ...     metadata=MarketplaceMetadata(description="d"),
    ...     owner=Author(name="T"),
    ...     plugins=[entry],
    ... )
    >>> rewrite_readme_rows(manifest, "| [commit](plugins/commit/) | Old blurb |")
    '| [commit](plugins/commit/) | Create git commits |'
    """
    descriptions = {entry.name: entry.description.strip() for entry in manifest.plugins}

    def replace(match: re.Match[str]) -> str:
        new = descriptions.get(match["name"])
        if new is None:
            return match.group(0)
        start = match.start("desc") - match.start(0)
        end = match.end("desc") - match.start(0)
        row = match.group(0)
        return row[:start] + new + row[end:]

    return README_ROW_RE.sub(replace, readme)


DOC_RULES = (
    "user-invocable",
    "console-prompt",
    "console-comment",
    "shell-fence",
    "ecosystem-command",
    "gnu-only",
    "prose-rules-link",
    "console-multi",
    "comment-run",
)
ENFORCED_DOC_RULES: frozenset[str] = frozenset(DOC_RULES)
"""Doc rules that fail ``lint``; the rest are reported by ``doc-report``."""
DOC_FILE_EXEMPT: dict[str, str] = {
    "skill-style/references/example-bloated.md": "quotes a sample skill as data",
    "skill-style/references/example-ideal.md": "quotes a sample skill as data",
    "disk/references/virtual-disks.md": "WSL-only commands, stated beside each fence",
}
"""``plugin/path`` files whose fences are exempt from the shell-fence and gnu-only rules."""
PROSE_RULES_EXEMPT: dict[str, str] = {
    **dict.fromkeys(
        (
            f"research/{name}"
            for name in ("assess", "continue", "release", "report", "status", "verify")
        ),
        "thin wrapper; foray writes the prose and links the rules",
    ),
    "release/bump": "writes no prose of its own; cut writes the changelog and commit message",
    "disk/disk": "router; usage and reclaim write the reply and link the rules",
}
"""``plugin/skill`` names that write no human-facing prose, each with the reason."""


class DocViolation(t.NamedTuple):
    """One doc-rule violation."""

    rule: str
    plugin: str
    path: str
    line: int
    message: str


def _doc_violations_in(plugin: str, rel: Path, text: str) -> list[DocViolation]:
    """Run the doc checks that apply to one markdown file."""
    found: list[_doc_lint.Violation] = [
        *_doc_lint.check_console_fences(text),
        *_doc_lint.check_shell_fences(text),
        *_doc_lint.check_portable_shell(text),
        *_doc_lint.check_sed_bre(text),
        *_doc_lint.check_one_command(text),
    ]
    if rel.name == "SKILL.md":
        found.extend(_doc_lint.check_user_invocable(text))
    if plugin not in _doc_lint.TOOL_PLUGINS | {"(root)"}:
        found.extend(_doc_lint.check_ecosystem_commands(text))
    return [DocViolation(rule, plugin, rel.as_posix(), line, msg) for rule, line, msg in found]


def doc_violations() -> list[DocViolation]:
    """Collect every doc-rule violation under ``plugins/`` and the root docs."""
    out: list[DocViolation] = []
    for plugin_dir in discover_plugins():
        for path in sorted(plugin_dir.rglob("*.md")):
            rel = path.relative_to(plugin_dir)
            if rel.parts[0] in {"evals", ".claude-plugin", ".codex-plugin"}:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            found = _doc_violations_in(plugin_dir.name, rel, text)
            if f"{plugin_dir.name}/{rel.as_posix()}" in DOC_FILE_EXEMPT:
                found = [v for v in found if v.rule not in {"shell-fence", "gnu-only"}]
            out.extend(found)
            skill = f"{plugin_dir.name}/{rel.parts[1] if len(rel.parts) > 1 else ''}"
            if (
                path.name == "SKILL.md"
                and skill not in PROSE_RULES_EXEMPT
                and _doc_lint.lacks_prose_rules_link(text)
            ):
                out.append(
                    DocViolation(
                        "prose-rules-link",
                        plugin_dir.name,
                        rel.as_posix(),
                        1,
                        "no link to ../../references/prose-rules.md",
                    )
                )
    scripts = [
        *sorted((REPO_ROOT / "scripts").glob("*.[ps][yh]")),
        *sorted(PLUGINS_DIR.glob("*/scripts/*.[ps][yh]")),
    ]
    for path in scripts:
        rel = path.relative_to(REPO_ROOT)
        plugin = rel.parts[1] if rel.parts[0] == "plugins" else "(root)"
        out.extend(
            DocViolation(rule, plugin, rel.as_posix(), line, msg)
            for rule, line, msg in _doc_lint.check_comment_runs(
                path.read_text(encoding="utf-8", errors="replace")
            )
        )
    root_docs = [
        REPO_ROOT / "AGENTS.md",
        REPO_ROOT / "README.md",
        *sorted((REPO_ROOT / ".github").glob("*.md")),
    ]
    for path in root_docs:
        if path.exists():
            rel = path.relative_to(REPO_ROOT)
            out.extend(_doc_violations_in("(root)", rel, path.read_text(encoding="utf-8")))
    return out


def _check_doc_rules() -> list[str]:
    """Return errors for the doc rules listed in ``ENFORCED_DOC_RULES``."""
    return [
        f"[{v.plugin}] {v.path}:{v.line}: {v.message}"
        for v in doc_violations()
        if v.rule in ENFORCED_DOC_RULES
    ]


@app.command(name="doc-report")
def doc_report(*, files: bool = False) -> None:
    """Count doc-rule violations per rule and plugin without failing the build."""
    found = doc_violations()
    for rule in DOC_RULES:
        hits = [v for v in found if v.rule == rule]
        live = "enforced" if rule in ENFORCED_DOC_RULES else "report only"
        print(f"{rule}: {len(hits)} ({live})")
        by_plugin: dict[str, list[DocViolation]] = {}
        for v in hits:
            by_plugin.setdefault(v.plugin, []).append(v)
        for plugin, group in sorted(by_plugin.items()):
            print(f"  {plugin}: {len(group)}")
            if files:
                per_file: dict[str, int] = {}
                for v in group:
                    per_file[v.path] = per_file.get(v.path, 0) + 1
                for path, count in sorted(per_file.items()):
                    print(f"    {path}: {count}")


@app.command()
def lint() -> None:
    """Validate the marketplace manifest and all plugin directories."""
    errors: list[str] = []
    warnings: list[str] = []

    # Validate marketplace manifest
    console.print("[bold]Validating marketplace manifest...[/bold]")
    try:
        manifest = load_marketplace()
        console.print(f"  Manifest: [green]OK[/green] ({len(manifest.plugins)} plugins)")
    except SystemExit:
        errors.append("Marketplace manifest not found or invalid")
        manifest = None

    if manifest is not None:
        # Validate marketplace name against reserved names
        name_errors = validate_marketplace_name(manifest.name)
        errors.extend(name_errors)

        # Validate each plugin entry's source path
        for entry in manifest.plugins:
            source_path = REPO_ROOT / entry.source
            if not source_path.exists():
                errors.append(
                    f"Marketplace entry '{entry.name}': source path '{entry.source}' does not exist"
                )

        # Check for duplicate plugin names
        seen_names: dict[str, int] = {}
        for entry in manifest.plugins:
            seen_names[entry.name] = seen_names.get(entry.name, 0) + 1
        for dup_name, count in sorted(seen_names.items()):
            if count > 1:
                errors.append(
                    f"Duplicate plugin name '{dup_name}' appears {count} times in marketplace.json"
                )

        # Validate each plugin directory
        console.print("\n[bold]Validating plugin directories...[/bold]")
        discovered = discover_plugins()
        for plugin_dir in discovered:
            plugin_errors = validate_plugin_dir(plugin_dir)
            if plugin_errors:
                errors.extend(plugin_errors)
            else:
                console.print(f"  {plugin_dir.name}: [green]OK[/green]")

        # Check for plugins not in marketplace
        manifest_names = {e.name for e in manifest.plugins}
        discovered_names = {d.name for d in discovered}
        undiscovered = discovered_names - manifest_names
        warnings.extend(
            f"Plugin '{name}' exists in plugins/ but is not listed in marketplace.json"
            for name in sorted(undiscovered)
        )

        # Check the README table, which nothing else in CI reads
        console.print("\n[bold]Validating README plugin table...[/bold]")
        readme_errors = check_readme_table(manifest, README_PATH.read_text(encoding="utf-8"))
        errors.extend(readme_errors)
        if not readme_errors:
            console.print(f"  Table: [green]OK[/green] ({len(manifest.plugins)} rows)")

    for repo_check in (
        _check_testpaths,
        _check_engine_parity,
        _check_verifier_parity,
        _check_script_var_graders,
        _check_doc_rules,
    ):
        errors.extend(repo_check())

    # Run claude plugin validate if CLI is available
    cli_errors, cli_warnings = _lint_claude_validate()
    errors.extend(cli_errors)
    warnings.extend(cli_warnings)

    # Report results
    console.print()
    if warnings:
        for warning in warnings:
            console.print(f"[yellow]Warning:[/yellow] {rich.markup.escape(warning)}")

    if errors:
        for error in errors:
            console.print(f"[red]Error:[/red] {rich.markup.escape(error)}")
        console.print(f"\n[red bold]{len(errors)} error(s) found.[/red bold]")
        raise SystemExit(1)

    console.print("[green bold]0 errors found.[/green bold]")


def _serialize_manifest(manifest: MarketplaceManifest) -> str:
    """Render *manifest* as the JSON text ``sync --write`` puts on disk.

    Unset optional fields are omitted rather than written as ``null``.
    ``claude plugin validate`` rejects a null wherever the schema expects a
    concrete type, so serializing them makes ``lint`` fail on this writer's
    own output. Dropping them loses nothing: every optional is declared
    ``... | None = None``, and the validator refuses null for all of them, so
    no field can carry a null worth round-tripping.

    Non-ASCII is written through instead of escaped, keeping em dashes in
    descriptions readable rather than rewriting every one of them.

    Examples
    --------
    >>> manifest = MarketplaceManifest(
    ...     name="test-marketplace",
    ...     metadata=MarketplaceMetadata(description="One — two"),
    ...     owner=Author(name="Test"),
    ...     plugins=[],
    ... )
    >>> text = _serialize_manifest(manifest)

    Unset optionals are absent, not null:

    >>> "null" in text
    False
    >>> '"pluginRoot"' in text
    False

    Set values survive, with the em dash written through rather than escaped:

    >>> "One — two" in text
    True

    A set optional round-trips, ``pluginRoot`` above all: third-party skill
    installers key off its exact spelling, so dropping it would break them.

    >>> manifest.metadata.pluginRoot = "."
    >>> '"pluginRoot": "."' in _serialize_manifest(manifest)
    True

    No root-level ``$schema`` is written. ``claude plugin validate`` rejected
    unknown root keys in Claude Code v2.1.76 and broke CI for four days; the
    key was dropped from the manifest then, and emitting it here would put it
    back on the next write. Current versions tolerate it again, but the
    validator's strictness is upstream and not ours to depend on.

    >>> "$schema" in _serialize_manifest(manifest)
    False
    """
    raw_out: dict[str, t.Any] = manifest.model_dump(mode="json", exclude_none=True)
    return json.dumps(raw_out, indent=2, ensure_ascii=False) + "\n"


def _load_plugin_json(plugin_dir: Path) -> PluginJson:
    """Read and validate one plugin's manifest.

    Parameters
    ----------
    plugin_dir : Path
        A directory under ``plugins/`` holding ``.claude-plugin/plugin.json``.

    Returns
    -------
    PluginJson
        The parsed manifest.

    Examples
    --------
    >>> plugin_dir = discover_plugins()[0]
    >>> _load_plugin_json(plugin_dir).name == plugin_dir.name
    True
    """
    raw = t.cast(
        "dict[str, t.Any]",
        json.loads((plugin_dir / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")),
    )
    return PluginJson.model_validate(raw)


def _homepage_prefix(manifest: MarketplaceManifest) -> str | None:
    """Learn the homepage prefix the manifest's existing entries agree on.

    Returns the text preceding ``/plugins/<name>``, so a new entry can be
    given the same shape. Disagreement returns None rather than a guess: a
    wrong homepage is worse than an absent one, and the entry stays valid
    either way.

    Examples
    --------
    >>> def _entry(name: str, homepage: str | None) -> PluginEntry:
    ...     return PluginEntry(
    ...         name=name,
    ...         description="d",
    ...         version="1.0.0",
    ...         author=Author(name="T"),
    ...         source=f"./plugins/{name}",
    ...         category="development",
    ...         homepage=homepage,
    ...     )
    >>> def _manifest(*entries: PluginEntry) -> MarketplaceManifest:
    ...     return MarketplaceManifest(
    ...         name="m",
    ...         metadata=MarketplaceMetadata(description="d"),
    ...         owner=Author(name="T"),
    ...         plugins=list(entries),
    ...     )
    >>> _homepage_prefix(_manifest(_entry("a", "https://x/tree/main/plugins/a")))
    'https://x/tree/main'

    Entries that disagree yield nothing:

    >>> _homepage_prefix(
    ...     _manifest(
    ...         _entry("a", "https://x/tree/main/plugins/a"),
    ...         _entry("b", "https://y/tree/main/plugins/b"),
    ...     )
    ... ) is None
    True

    So does a manifest whose entries set no homepage:

    >>> _homepage_prefix(_manifest(_entry("a", None))) is None
    True
    """
    prefixes = {
        entry.homepage[: -len(suffix)]
        for entry in manifest.plugins
        if entry.homepage and entry.homepage.endswith(suffix := f"/plugins/{entry.name}")
    }
    return prefixes.pop() if len(prefixes) == 1 else None


def _common_license(manifest: MarketplaceManifest) -> str | None:
    """Return the license every entry that declares one agrees on.

    Examples
    --------
    >>> def _entry(name: str, lic: str | None) -> PluginEntry:
    ...     return PluginEntry(
    ...         name=name,
    ...         description="d",
    ...         version="1.0.0",
    ...         author=Author(name="T"),
    ...         source=f"./plugins/{name}",
    ...         category="development",
    ...         license=lic,
    ...     )
    >>> def _manifest(*entries: PluginEntry) -> MarketplaceManifest:
    ...     return MarketplaceManifest(
    ...         name="m",
    ...         metadata=MarketplaceMetadata(description="d"),
    ...         owner=Author(name="T"),
    ...         plugins=list(entries),
    ...     )
    >>> _common_license(_manifest(_entry("a", "MIT"), _entry("b", "MIT")))
    'MIT'
    >>> _common_license(_manifest(_entry("a", "MIT"), _entry("b", "Apache-2.0"))) is None
    True
    """
    licenses = {entry.license for entry in manifest.plugins if entry.license}
    return licenses.pop() if len(licenses) == 1 else None


def _new_entry(name: str, plugin_meta: PluginJson, manifest: MarketplaceManifest) -> PluginEntry:
    """Build the entry ``sync --write`` adds for a newly discovered plugin.

    Split out of the write loop so what the writer emits can be asserted.
    CI runs ``sync --check`` and never ``sync --write``, so the writer and
    the linter have twice disagreed unnoticed — once emitting ``null`` for
    every unset optional, once re-adding a ``$schema`` key that had been
    deliberately removed. Both reached trunk.

    Examples
    --------
    >>> manifest = MarketplaceManifest(
    ...     name="m",
    ...     metadata=MarketplaceMetadata(description="d"),
    ...     owner=Author(name="Owner"),
    ...     plugins=[
    ...         PluginEntry(
    ...             name="existing",
    ...             description="d",
    ...             version="1.0.0",
    ...             author=Author(name="Owner"),
    ...             source="./plugins/existing",
    ...             category="development",
    ...             homepage="https://example.test/tree/main/plugins/existing",
    ...             license="MIT",
    ...         )
    ...     ],
    ... )
    >>> meta = PluginJson(name="fresh", description="A fresh plugin")
    >>> entry = _new_entry("fresh", meta, manifest)

    The fields no gate checks are the ones that go missing, so assert them:

    >>> entry.homepage
    'https://example.test/tree/main/plugins/fresh'
    >>> entry.license
    'MIT'

    The author falls back to the marketplace owner when the plugin sets none:

    >>> entry.author.name
    'Owner'

    What the writer emits must survive serialization without nulls, which is
    what ``claude plugin validate`` rejects:

    >>> manifest.plugins.append(entry)
    >>> text = _serialize_manifest(manifest)
    >>> "null" in text
    False
    >>> '"license": "MIT"' in text
    True
    >>> '"homepage": "https://example.test/tree/main/plugins/fresh"' in text
    True

    A marketplace with no convention yet gets neither field rather than a
    guess, and still serializes cleanly:

    >>> bare = MarketplaceManifest(
    ...     name="m",
    ...     metadata=MarketplaceMetadata(description="d"),
    ...     owner=Author(name="Owner"),
    ...     plugins=[],
    ... )
    >>> first = _new_entry("first", meta, bare)
    >>> (first.homepage, first.license)
    (None, None)
    >>> bare.plugins.append(first)
    >>> "null" in _serialize_manifest(bare)
    False
    """
    prefix = _homepage_prefix(manifest)
    return PluginEntry(
        name=plugin_meta.name,
        description=plugin_meta.description,
        tags=plugin_meta.keywords,
        version=plugin_meta.version or "1.0.0",
        author=plugin_meta.author or manifest.owner,
        source=f"./plugins/{name}",
        category="development",
        homepage=f"{prefix}/plugins/{name}" if prefix is not None else None,
        license=_common_license(manifest),
    )


def _drifted(entry: PluginEntry, meta: PluginJson) -> bool:
    """Report whether a marketplace entry disagrees with its ``plugin.json``.

    Examples
    --------
    >>> entry = PluginEntry(
    ...     name="p",
    ...     description="d",
    ...     version="0.1.0",
    ...     author=Author(name="o"),
    ...     source="./plugins/p",
    ...     category="development",
    ... )
    >>> _drifted(entry, PluginJson(name="p", description="d", version="0.1.0"))
    False
    >>> _drifted(entry, PluginJson(name="p", description="d", version="0.2.0"))
    True
    """
    return (
        entry.description != meta.description
        or entry.tags != meta.keywords
        or (meta.version is not None and entry.version != meta.version)
    )


_MIN_PLUGIN_PARTS = 2
"""Index of the path part after ``plugins/<name>``."""


def _git_out(*args: str) -> str | None:
    """Return stdout of ``git`` run in the repository, or None when it fails."""
    result = subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout if result.returncode == 0 else None


def _manifest_version(text: str | None) -> str | None:
    """Return the ``version`` in plugin.json ``text``, or None when absent or malformed.

    Examples
    --------
    >>> _manifest_version('{"name": "p", "version": "0.2.0"}')
    '0.2.0'
    >>> _manifest_version("not json") is None
    True
    >>> _manifest_version(None) is None
    True
    """
    if text is None:
        return None
    try:
        version = t.cast("dict[str, t.Any]", json.loads(text)).get("version")
    except json.JSONDecodeError, AttributeError:
        return None
    return version if isinstance(version, str) else None


@app.command()
def versions(
    base: t.Annotated[str, typer.Option(help="Git ref to compare the working tree against")],
) -> None:
    """Fail when a plugin's files changed since ``base`` but its version did not.

    Generated ``.codex-plugin/`` files do not count as a change on their own.
    A plugin absent from ``base`` is new and needs no bump.
    """
    changed = _git_out("diff", "--name-only", base, "--", "plugins")
    if changed is None:
        console.print(f"[red]Error:[/red] cannot diff against '{base}'")
        raise SystemExit(1)
    touched = {
        parts[1]
        for line in changed.splitlines()
        if len(parts := line.split("/")) > _MIN_PLUGIN_PARTS
        and parts[_MIN_PLUGIN_PARTS] != ".codex-plugin"
    }
    stale: list[str] = []
    for name in sorted(touched):
        rel = f"plugins/{name}/.claude-plugin/plugin.json"
        old = _manifest_version(_git_out("show", f"{base}:{rel}"))
        path = REPO_ROOT / rel
        new = _manifest_version(path.read_text(encoding="utf-8") if path.exists() else None)
        if old is not None and new is not None and old == new:
            stale.append(f"{name}: files changed but version is still {new}")
    if stale:
        for line in stale:
            console.print(f"[red]Error:[/red] {rich.markup.escape(line)}")
        raise SystemExit(1)
    console.print("[green]Every changed plugin carries a new version.[/green]")


@app.command()
def sync(*, write: bool = False, check: bool = False) -> None:
    """Compare discovered plugins with marketplace manifest.

    Drift is a plugin present on one side only, or an entry whose description,
    ``tags``, or ``version`` no longer match its ``plugin.json`` (``keywords``
    for tags). Descriptions are the listing users read, and nothing else in CI
    compares them.

    Parameters
    ----------
    write : bool
        If True, update marketplace.json with discovered plugins.
    check : bool
        If True, exit with code 1 when drift is detected (for CI).

    Examples
    --------
    The ``--check`` flag is designed for CI pipelines:

    >>> import subprocess
    >>> result = subprocess.run(
    ...     ["python", "scripts/marketplace.py", "sync", "--check"],
    ...     capture_output=True,
    ...     text=True,
    ...     cwd=REPO_ROOT,
    ... )
    >>> result.returncode == 0  # 0 means in sync
    True
    """
    manifest = load_marketplace()
    discovered = discover_plugins()

    manifest_names = {e.name for e in manifest.plugins}
    discovered_names = {d.name for d in discovered}

    additions = sorted(discovered_names - manifest_names)
    removals = sorted(manifest_names - discovered_names)
    stale = sorted(
        entry.name
        for entry in manifest.plugins
        if entry.name in discovered_names
        and _drifted(entry, _load_plugin_json(PLUGINS_DIR / entry.name))
    )

    if not additions and not removals and not stale:
        if write:
            _write_readme_rows(manifest)
        console.print("[green]Marketplace manifest is in sync with plugins/.[/green]")
        return

    table = Table(title="Sync Report")
    table.add_column("Status", style="bold")
    table.add_column("Plugin")

    for name in additions:
        table.add_row("[green]+ Add[/green]", name)
    for name in removals:
        table.add_row("[red]- Remove[/red]", name)
    for name in stale:
        table.add_row("[yellow]~ Description, tags, or version[/yellow]", name)

    console.print(table)

    if check:
        msg = (
            "\n[red bold]Marketplace manifest is out of sync.[/red bold]"
            " Run 'sync --write' to update."
        )
        console.print(msg)
        raise SystemExit(1)

    if not write:
        console.print("\nRun with [bold]--write[/bold] to update marketplace.json.")
        return

    # Add new plugins
    for name in additions:
        new_entry = _new_entry(name, _load_plugin_json(PLUGINS_DIR / name), manifest)
        manifest.plugins.append(new_entry)
        msg = (
            f"[yellow]Warning:[/yellow] Plugin '{name}' defaulting to"
            " category='development' — update marketplace.json if needed"
        )
        console.print(msg)

    # Remove missing plugins
    manifest.plugins = [e for e in manifest.plugins if e.name not in removals]

    for entry in manifest.plugins:
        if entry.name in stale:
            meta = _load_plugin_json(PLUGINS_DIR / entry.name)
            entry.description = meta.description
            entry.tags = meta.keywords
            entry.version = meta.version or entry.version

    # Write updated manifest
    _ = MARKETPLACE_PATH.write_text(_serialize_manifest(manifest), encoding="utf-8")
    console.print(f"\n[green]Updated {PrivatePath(MARKETPLACE_PATH)}[/green]")
    _write_readme_rows(manifest)


def _write_readme_rows(manifest: MarketplaceManifest) -> None:
    """Rewrite README plugin rows whose description drifted from the manifest."""
    readme = README_PATH.read_text(encoding="utf-8")
    updated = rewrite_readme_rows(manifest, readme)
    if updated != readme:
        _ = README_PATH.write_text(updated, encoding="utf-8")
        console.print(f"[green]Updated {PrivatePath(README_PATH)}[/green]")


@app.command(name="check-outdated")
def check_outdated() -> None:
    """Compare versions between plugin.json and marketplace entries."""
    manifest = load_marketplace()

    table = Table(title="Version Comparison")
    table.add_column("Plugin")
    table.add_column("Marketplace Version")
    table.add_column("plugin.json Version")
    table.add_column("Status")

    has_mismatch = False

    for entry in manifest.plugins:
        plugin_dir = PLUGINS_DIR / entry.name
        plugin_json_path = plugin_dir / ".claude-plugin" / "plugin.json"

        if not plugin_json_path.exists():
            table.add_row(entry.name, entry.version, "[red]missing[/red]", "[red]ERROR[/red]")
            has_mismatch = True
            continue

        raw = t.cast(
            "dict[str, t.Any]",
            json.loads(plugin_json_path.read_text(encoding="utf-8")),
        )
        plugin_meta = PluginJson.model_validate(raw)
        local_version = plugin_meta.version or "(not set)"

        if plugin_meta.version != entry.version:
            table.add_row(
                entry.name,
                entry.version,
                local_version,
                "[yellow]MISMATCH[/yellow]",
            )
            has_mismatch = True
        else:
            table.add_row(entry.name, entry.version, local_version, "[green]OK[/green]")

    console.print(table)

    if has_mismatch:
        console.print("\n[yellow]Version mismatches found.[/yellow]")
    else:
        console.print("\n[green]All versions match.[/green]")


AGENTS_DIR = REPO_ROOT / ".agents"
PORTABLE_SKILLS_DIR = AGENTS_DIR / "skills"
PORTABLE_MANIFEST_PATH = AGENTS_DIR / "portable-manifest.json"

CODEX_MARKETPLACE_PATH = AGENTS_DIR / "plugins" / "marketplace.json"
"""Codex's native marketplace manifest.

Codex prefers this over ``.claude-plugin/marketplace.json``, which it accepts
only as a legacy fallback. Both ship so neither host depends on the other's
spelling.
"""

CODEX_MANIFEST_REL = Path(".codex-plugin") / "plugin.json"

CODEX_MARKETPLACE_DISPLAY_NAME = "Skills from Tony"
"""Label Codex shows in its marketplace picker.

Names the owner because the manifest name alone is generic in a picker listing
several marketplaces; the manifest description is a full sentence, too long for
a picker row.
"""


def _collect_sources() -> list[SourceComponent]:
    """Collect every skill in the source tree.

    Each component carries its parsed frontmatter, which is the only YAML the
    render layer needs from the source tree.

    Returns
    -------
    list[SourceComponent]
        Deterministically ordered components.
    """
    found: list[SourceComponent] = []
    for plugin in discover_plugins():
        skills_dir = plugin / "skills"
        if skills_dir.exists():
            for skill_dir in sorted(d for d in skills_dir.iterdir() if d.is_dir()):
                md = skill_dir / "SKILL.md"
                if not md.exists():
                    continue
                fm = parse_frontmatter(md) or {}
                raw = str(fm.get("name") or skill_dir.name)
                found.append(SourceComponent(plugin, md, raw, skill_dir, fm))
    return found


def _qualify(plugin: str, raw_name: str) -> str:
    """Namespace an output name with the plugin that owns it.

    Portable skills install into a directory shared with every other pack a
    user has, so a bare name such as ``this`` or ``scan`` is unsafe there.
    Names that already lead with the plugin keep their form rather than
    doubling it.

    Parameters
    ----------
    plugin : str
        Owning plugin name.
    raw_name : str
        Component name before namespacing.

    Returns
    -------
    str
        The namespaced output name.

    Examples
    --------
    >>> _qualify("merge-pr", "this")
    'merge-pr-this'
    >>> _qualify("pytest-optimizer", "00-scan")
    'pytest-optimizer-00-scan'
    >>> _qualify("commit", "commit")
    'commit'
    >>> _qualify("changelog", "changelog-rewrite-aggressively")
    'changelog-rewrite-aggressively'
    """
    if raw_name == plugin or raw_name.startswith(f"{plugin}-"):
        return raw_name
    return f"{plugin}-{raw_name}"


def _assign_names(sources: list[SourceComponent]) -> tuple[list[OutputSkill], PortableIndex]:
    """Resolve output names and build the peer lookup index.

    Parameters
    ----------
    sources : list[SourceComponent]
        Every discovered component.

    Returns
    -------
    tuple[list[OutputSkill], PortableIndex]
        Output skills and the shared lookup index.
    """
    groups: dict[str, list[SourceComponent]] = {}
    for component in sources:
        groups.setdefault(component.raw_name, []).append(component)

    skills: list[OutputSkill] = []
    index = PortableIndex(by_path={}, by_invocation={})
    for raw_name in sorted(groups):
        for body in groups[raw_name]:
            name = _qualify(body.plugin.name, raw_name)
            skills.append(OutputSkill(name, body))
            index.by_path[body.path] = name
            index.by_invocation[(body.plugin.name, body.raw_name)] = name
            index.by_invocation[(body.plugin.name, body.base.name)] = name
    skills.sort(key=lambda s: s.name)
    return skills, index


def _build_portable() -> list[BuiltSkill]:
    """Render every output skill in memory.

    Returns
    -------
    list[BuiltSkill]
        One entry per emitted ``.agents/skills/<name>/`` directory.
    """
    sources = _collect_sources()
    skills, index = _assign_names(sources)
    return [SkillBuilder(skill, index).build() for skill in skills]


def _external_paths(built: list[BuiltSkill]) -> dict[str, list[str]]:
    """Map each path left verbatim to the skills that mention it."""
    external: dict[str, list[str]] = {}
    for skill in built:
        for token in skill.external:
            external.setdefault(token, []).append(skill.name)
    return dict(sorted(external.items()))


def _portable_manifest(built: list[BuiltSkill]) -> dict[str, t.Any]:
    """Summarize provenance, bundling, and duplication for the emitted tree."""
    duplication: dict[str, int] = {}
    unresolved: dict[str, list[str]] = {}
    for skill in built:
        for source in skill.vendored.values():
            duplication[source] = duplication.get(source, 0) + 1
        for token in skill.unresolved:
            unresolved.setdefault(token, []).append(skill.name)
    return {
        "generator": "scripts/marketplace.py portable",
        "skills": [
            {
                "name": s.name,
                "sources": s.sources,
                "bundled": dict(sorted(s.vendored.items())),
                "bytes": sum(len(content) for content, _ in s.files.values()),
            }
            for s in built
        ],
        "duplication": dict(sorted(duplication.items(), key=lambda kv: (-kv[1], kv[0]))),
        "external_paths": _external_paths(built),
        "unresolved_host_commands": dict(sorted(unresolved.items())),
    }


def _write_portable(built: list[BuiltSkill], dest: Path, manifest_path: Path) -> None:
    """Write the emitted tree, replacing any previous contents."""
    if dest.exists():
        shutil.rmtree(dest)
    for skill in built:
        skill_dir = dest / skill.name
        for rel, (content, mode) in sorted(skill.files.items()):
            path = skill_dir / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            _ = path.write_bytes(content)
            path.chmod(mode)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    _ = manifest_path.write_text(
        json.dumps(_portable_manifest(built), indent=2) + "\n", encoding="utf-8"
    )


def _check_drift(built: list[BuiltSkill]) -> list[str]:
    """Compare the on-disk tree with a fresh render, including permission bits."""
    errors: list[str] = []
    expected: dict[str, tuple[bytes, int]] = {
        f"{skill.name}/{rel}": payload for skill in built for rel, payload in skill.files.items()
    }
    if not PORTABLE_SKILLS_DIR.exists():
        return ["portable: .agents/skills/ has not been generated (run 'portable')"]
    actual = sorted(p for p in PORTABLE_SKILLS_DIR.rglob("*") if p.is_file())
    actual_rel = {str(p.relative_to(PORTABLE_SKILLS_DIR)) for p in actual}
    errors.extend(
        f"portable: stale output file '{rel}'" for rel in sorted(actual_rel - set(expected))
    )
    for rel, (content, mode) in sorted(expected.items()):
        path = PORTABLE_SKILLS_DIR / rel
        if not path.is_file():
            errors.append(f"portable: missing output file '{rel}'")
        elif path.read_bytes() != content:
            errors.append(f"portable: '{rel}' differs from a fresh render")
        elif path.stat().st_mode & 0o777 != mode:
            errors.append(
                f"portable: '{rel}' has mode {path.stat().st_mode & 0o777:o}, want {mode:o}"
            )
    return errors


def _check_invariants(built: list[BuiltSkill], sources: list[SourceComponent]) -> list[str]:
    """Verify the portable-tree contract against the rendered output."""
    errors: list[str] = []
    covered = {source for skill in built for source in skill.sources}
    errors.extend(
        f"portable: source component '{c.path.relative_to(REPO_ROOT)}' has no output skill"
        for c in sources
        if str(c.path.relative_to(REPO_ROOT)) not in covered
    )
    seen: set[str] = set()
    for skill in built:
        if skill.name in seen:
            errors.append(f"portable: duplicate output skill name '{skill.name}'")
        seen.add(skill.name)
        errors.extend(_check_one_skill(skill))
    return errors


def _check_one_skill(skill: BuiltSkill) -> list[str]:
    """Verify frontmatter, forbidden tokens, and bundled-path resolution."""
    errors: list[str] = []
    text = skill.files["SKILL.md"][0].decode("utf-8")
    for rel, (content, _mode) in sorted(skill.files.items()):
        body = strip_frontmatter(content.decode("utf-8", errors="replace"))
        if "CLAUDE_PLUGIN_ROOT" in body:
            errors.append(f"portable: [{skill.name}] '{rel}' still references CLAUDE_PLUGIN_ROOT")
        if "`!" in body:
            errors.append(f"portable: [{skill.name}] '{rel}' still contains an inline-bash span")
        if re.search(r"(?<![A-Za-z0-9._/-])plugins/[a-z]", body):
            errors.append(f"portable: [{skill.name}] '{rel}' still contains an in-repo path")
    errors.extend(_check_frontmatter(skill, text))
    errors.extend(
        f"portable: [{skill.name}] bundled path '{rel}' was not emitted"
        for rel in sorted(skill.vendored)
        if rel not in skill.files
    )
    errors.extend(_check_paths(skill))
    errors.extend(_check_verbatim_fences(skill))
    errors.extend(_check_sibling_imports(skill))
    return errors


def _check_sibling_imports(skill: BuiltSkill) -> list[str]:
    """Verify each emitted script ships the sibling modules it imports."""
    errors: list[str] = []
    for rel, src_rel in sorted(skill.vendored.items()):
        if not rel.endswith(".py") or rel not in skill.files:
            continue
        scripts_dir = (REPO_ROOT / src_rel).parent
        if scripts_dir.name != "scripts":
            continue
        out_dir = posixpath.dirname(rel)
        for name in sorted(imported_modules(skill.files[rel][0].decode("utf-8", "replace"))):
            sibling = sibling_module(scripts_dir, name)
            if sibling is None:
                continue
            want = str(sibling.relative_to(REPO_ROOT))
            if skill.vendored.get(f"{out_dir}/{name}.py") != want:
                errors.append(f"portable: [{skill.name}] '{rel}' imports '{name}', not emitted")
    return errors


def _check_verbatim_fences(skill: BuiltSkill) -> list[str]:
    """Verify a verbatim source's fenced blocks shipped byte-identical.

    Nothing else catches a regression here. A rewritten quote is still valid
    markdown, still resolves every path, and still passes every other
    invariant — it is simply no longer what the person typed, which is the
    one property the marker exists to hold.
    """
    errors: list[str] = []
    for rel, src_rel in sorted(skill.vendored.items()):
        source = REPO_ROOT / src_rel
        if source.suffix != ".md" or rel not in skill.files:
            continue
        try:
            raw = source.read_text(encoding="utf-8")
        except OSError, UnicodeDecodeError:
            continue
        if not has_verbatim_fences(raw):
            continue
        shipped = skill.files[rel][0].decode("utf-8", errors="replace")
        if fenced_blocks(raw) != fenced_blocks(shipped):
            altered = "is marked verbatim but its fenced blocks were altered on export"
            errors.append(f"portable: [{skill.name}] '{rel}' {altered}")
    return errors


def _check_frontmatter(skill: BuiltSkill, text: str) -> list[str]:
    """Verify the emitted frontmatter carries only spec keys and the right name."""
    errors: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        temp = Path(tmp) / "SKILL.md"
        _ = temp.write_text(text, encoding="utf-8")
        fm = parse_frontmatter(temp)
    if fm is None:
        return [f"portable: [{skill.name}] SKILL.md has no parseable frontmatter"]
    emitted = t.cast("str | None", fm.get("name"))
    if emitted != skill.name:
        errors.append(f"portable: [{skill.name}] frontmatter name is '{emitted}'")
    emitted_description = " ".join(t.cast("str", fm.get("description", "")).split())
    if not emitted_description:
        errors.append(f"portable: [{skill.name}] frontmatter has no description")
    elif emitted_description != skill.description:
        errors.append(f"portable: [{skill.name}] description does not survive a YAML round trip")
    errors.extend(
        f"portable: [{skill.name}] frontmatter carries non-spec key '{key}'"
        for key in sorted(fm)
        if key not in SPEC_FRONTMATTER_KEYS
    )
    return errors


_PATH_RE = re.compile(
    r"(?<![A-Za-z0-9._/-])(?:(?:\.\./)+[A-Za-z0-9._/-]*[A-Za-z0-9_]|(?:"
    + "|".join(RESOURCE_DIRS)
    + r")/[A-Za-z0-9._/-]+)"
)


def _check_paths(skill: BuiltSkill) -> list[str]:
    """Resolve every relative path in every emitted file from its own directory.

    Each rewritten path is checked against the file the builder meant, so a
    sibling link that lands on a different file fails; any other bundle-shaped
    path must name an emitted file. ``docs/`` is the one ambiguous prefix: slop and
    pr quote ``docs/install.md`` as a file in the *user's* project, so an
    unresolved ``docs/`` token the builder left verbatim is not reported. A
    ``..`` climb toward a name outside the resource directories is a
    user-project path and survives.
    """
    errors: list[str] = []
    files = set(skill.files)
    external = set(skill.external)
    errors.extend(
        f"portable: [{skill.name}] '{path}' collides with another source of the same name"
        for path in skill.collisions
    )
    for emitted, spelled, intended in skill.links:
        landed = posixpath.normpath(posixpath.join(posixpath.dirname(emitted), spelled))
        if landed != intended:
            errors.append(
                f"portable: [{skill.name}] '{emitted}' '{spelled}' -> '{landed}', not '{intended}'"
            )
    for rel, (content, _mode) in sorted(skill.files.items()):
        body = strip_frontmatter(content.decode("utf-8", errors="replace"))
        here = posixpath.dirname(rel)
        for match in _PATH_RE.finditer(body):
            token = match.group(0).rstrip(".,;:")
            if posixpath.normpath(posixpath.join(here, token)) in files:
                continue
            if token.startswith("docs/") and token in external:
                continue
            first = next((p for p in token.split("/") if p != ".."), "")
            if token.startswith("../") and first not in RESOURCE_DIRS:
                continue
            errors.append(f"portable: [{skill.name}] '{rel}' path '{token}' does not resolve")
    return errors


def _dump_json(model: pydantic.BaseModel) -> str:
    """Serialize a generated manifest the way it is written to disk."""
    raw: dict[str, t.Any] = model.model_dump(mode="json", exclude_none=True)
    return json.dumps(raw, indent=2, ensure_ascii=False) + "\n"


def _plugin_openai_files(plugin_dir: Path) -> dict[str, bytes]:
    """Lay out ``agents/openai.yaml`` for each skill under *plugin_dir*.

    Codex installs a plugin from ``plugins/<name>/skills/`` in place, so the
    presentation file and invocation policy must sit beside each source skill
    as well as in the flattened ``.agents/skills/`` export.
    """
    out: dict[str, bytes] = {}
    skills_dir = plugin_dir / "skills"
    if not skills_dir.is_dir():
        return out
    for skill_dir in sorted(d for d in skills_dir.iterdir() if d.is_dir()):
        md = skill_dir / "SKILL.md"
        if not md.is_file():
            continue
        fm = parse_frontmatter(md) or {}
        text = render_openai_yaml(
            _qualify(plugin_dir.name, str(fm.get("name") or skill_dir.name)),
            t.cast("str", fm.get("description", "")),
            model_invocable=not t.cast("object", fm.get("disable-model-invocation", False)),
        )
        rel = skill_dir.relative_to(REPO_ROOT) / OPENAI_YAML_REL
        out[str(rel)] = text.encode("utf-8")
    return out


def _codex_files() -> dict[str, bytes]:
    """Lay out every generated Codex manifest, keyed by repo-relative path.

    Identity mirrors ``.claude-plugin/plugin.json`` so the two manifests cannot
    describe one plugin differently; ``homepage`` and ``license`` live only on
    the marketplace entry and are read from there.

    Returning the whole set as bytes lets the writer and the drift check work
    from one description, so they cannot disagree about what belongs on disk.
    """
    manifest = load_marketplace()
    entries = {entry.name: entry for entry in manifest.plugins}
    codex_marketplace = CodexMarketplace(
        name=manifest.name,
        interface=CodexInterface(displayName=CODEX_MARKETPLACE_DISPLAY_NAME),
        plugins=[
            CodexPluginEntry(
                name=entry.name,
                source=CodexSource(path=entry.source),
                policy=CodexPolicy(),
                # Codex documents its categories capitalized; the value is the
                # same one the Claude manifest already validates.
                category=entry.category.title(),
            )
            for entry in manifest.plugins
        ],
    )
    files = {
        str(CODEX_MARKETPLACE_PATH.relative_to(REPO_ROOT)): _dump_json(codex_marketplace).encode(
            "utf-8"
        )
    }
    for plugin_dir in discover_plugins():
        meta = _load_plugin_json(plugin_dir)
        entry = entries.get(plugin_dir.name)
        author = meta.author or (entry.author if entry is not None else None)
        homepage = meta.homepage or (entry.homepage if entry is not None else None)
        codex_json = CodexPluginJson(
            name=meta.name,
            # Codex keys its install cache on the version, so one is required
            # even where the Claude manifest leaves it unset.
            version=meta.version or "0.0.0",
            description=meta.description,
            author=author,
            homepage=homepage,
            repository=meta.repository,
            license=meta.license or (entry.license if entry is not None else None),
            keywords=meta.keywords,
            interface=CodexPluginInterface(
                displayName=meta.name.replace("-", " ").title(),
                shortDescription=_first_sentence(meta.description),
                longDescription=meta.description,
                developerName=author.name if author is not None else None,
                category=entry.category.title() if entry is not None else None,
                websiteURL=homepage,
            ),
        )
        rel = plugin_dir.relative_to(REPO_ROOT) / CODEX_MANIFEST_REL
        files[str(rel)] = _dump_json(codex_json).encode("utf-8")
        files.update(_plugin_openai_files(plugin_dir))
    return files


def _existing_codex_files(root: Path) -> set[str]:
    """Include orphaned manifests whose source plugin or skill was removed."""
    plugins = root / "plugins"
    return {
        str(p.relative_to(root))
        for p in [
            *plugins.glob(f"*/{CODEX_MANIFEST_REL}"),
            *plugins.glob(f"*/skills/*/{OPENAI_YAML_REL}"),
            root / CODEX_MARKETPLACE_PATH.relative_to(REPO_ROOT),
        ]
        if p.is_file()
    }


def _remove_stale_codex(files: dict[str, bytes], root: Path) -> None:
    """Remove generated manifests left by deleted sources, retaining other files.

    >>> with tempfile.TemporaryDirectory() as tmp:
    ...     root = Path(tmp)
    ...     stale = root / "plugins/p/skills/removed/agents/openai.yaml"
    ...     stale.parent.mkdir(parents=True)
    ...     _ = stale.write_text("old")
    ...     keep = stale.parent / "notes.md"
    ...     _ = keep.write_text("user data")
    ...     _remove_stale_codex({}, root)
    ...     assert not stale.exists() and keep.read_text() == "user data"
    ...     keep.unlink()
    ...     _ = stale.write_text("old")
    ...     _remove_stale_codex({}, root)
    ...     assert not (root / "plugins/p").exists()
    ...     assert (root / "plugins").is_dir()
    >>> with tempfile.TemporaryDirectory() as tmp:
    ...     root = Path(tmp) / "repo"
    ...     external = Path(tmp) / "external"
    ...     external.mkdir()
    ...     keep = external / "openai.yaml"
    ...     _ = keep.write_text("user data")
    ...     skill = root / "plugins/p/skills/removed"
    ...     skill.mkdir(parents=True)
    ...     (skill / "agents").symlink_to(external, target_is_directory=True)
    ...     try:
    ...         _remove_stale_codex({}, root)
    ...     except ValueError as error:
    ...         assert "symlink" in str(error)
    ...     else:
    ...         raise AssertionError("followed a symlinked parent")
    ...     assert keep.read_text() == "user data"
    """
    stale = [root / rel for rel in sorted(_existing_codex_files(root) - set(files))]
    for path in stale:
        if any(parent.is_symlink() for parent in path.parents if parent.is_relative_to(root)):
            msg = f"refusing generated cleanup through a symlink: {path.relative_to(root)}"
            raise ValueError(msg)
    for path in stale:
        path.unlink()
        directory = path.parent
        while directory.is_relative_to(root / "plugins") and directory != root / "plugins":
            if any(directory.iterdir()):
                break
            directory.rmdir()
            directory = directory.parent


def _check_codex_drift(files: dict[str, bytes]) -> list[str]:
    """Compare the committed Codex manifests against a fresh generation."""
    errors: list[str] = []
    actual = _existing_codex_files(REPO_ROOT)
    errors.extend(f"codex: stale manifest '{rel}'" for rel in sorted(actual - set(files)))
    for rel, content in sorted(files.items()):
        path = REPO_ROOT / rel
        if not path.is_file():
            errors.append(f"codex: missing manifest '{rel}'")
        elif path.read_bytes() != content:
            errors.append(f"codex: '{rel}' differs from a fresh render")
    return errors


SHARED_DIR = REPO_ROOT / "shared"
VENDOR_MANIFEST_PATH = SHARED_DIR / "vendor.yml"


def _vendor_banner(name: str) -> str:
    """Return the first line a plugin's copy of ``shared/<name>`` carries.

    Examples
    --------
    >>> _vendor_banner("a.md").startswith("<!-- Vendored from shared/a.md;")
    True
    >>> _vendor_banner("a.yml").startswith("# Vendored from shared/a.yml;")
    True
    """
    text = f"{VENDOR_MARKER}{name}; edit that file, then run 'scripts/marketplace.py portable'."
    return f"<!-- {text} -->\n" if name.endswith(".md") else f"# {text}\n"


def _vendor_render(name: str, source: str) -> str:
    r"""Return a plugin's copy of a shared file: the banner on line 1, or line 2 under a shebang.

    >>> _vendor_render("a.py", "#!/usr/bin/env python3\nx = 1\n").splitlines()[0]
    '#!/usr/bin/env python3'
    >>> _vendor_render("a.py", "#!/usr/bin/env python3\nx = 1\n").splitlines()[1][:10]
    '# Vendored'
    """
    banner = _vendor_banner(name)
    if source.startswith("#!"):
        shebang, _, rest = source.partition("\n")
        return f"{shebang}\n{banner}{rest}"
    return banner + source


def _vendor_dest(plugin: str, name: str) -> Path:
    """Return where a plugin keeps its copy: scripts/ for code, references/ otherwise."""
    folder = "scripts" if name.endswith(".py") else "references"
    return PLUGINS_DIR / plugin / folder / name


def _vendor_plan() -> tuple[dict[Path, str], list[str]]:
    """Map each vendored destination to its fresh render, plus manifest errors.

    ``shared/vendor.yml`` maps a file name under ``shared/`` to the plugins that
    ship it. Each plugin carries its own copy, in ``scripts/`` for a ``.py`` file
    and ``references/`` otherwise, so it installs standalone.
    """
    if not VENDOR_MANIFEST_PATH.is_file():
        return {}, []
    try:
        loaded = t.cast("object", yaml.safe_load(VENDOR_MANIFEST_PATH.read_text(encoding="utf-8")))
    except yaml.YAMLError as exc:
        return {}, [f"vendor: cannot parse shared/vendor.yml: {exc}"]
    if not isinstance(loaded, dict):
        return {}, ["vendor: shared/vendor.yml must map file names to plugin lists"]
    errors: list[str] = []
    plan: dict[Path, str] = {}
    for name, plugins in sorted(t.cast("dict[str, list[str]]", loaded).items()):
        source = SHARED_DIR / name
        if not source.is_file():
            errors.append(f"vendor: shared/{name} is listed in vendor.yml but missing")
            continue
        text = _vendor_render(name, source.read_text(encoding="utf-8"))
        for plugin in plugins:
            if not (PLUGINS_DIR / plugin).is_dir():
                errors.append(f"vendor: shared/{name} names unknown plugin '{plugin}'")
                continue
            plan[_vendor_dest(plugin, name)] = text
    return plan, errors


def _check_vendor(plan: dict[Path, str]) -> list[str]:
    """Compare vendored copies with a fresh render; flag stray banners."""
    errors: list[str] = []
    for dest, content in sorted(plan.items()):
        rel = dest.relative_to(REPO_ROOT)
        source = f"shared/{dest.name}"
        if not dest.is_file():
            errors.append(f"vendor: '{rel}' is missing; run 'scripts/marketplace.py portable'")
        elif dest.read_text(encoding="utf-8") != content:
            fix = f"edit {source}, not the copy, then run 'scripts/marketplace.py portable'"
            errors.append(f"vendor: '{rel}' differs from {source}; {fix}")
        elif dest.suffix == ".py" and not dest.stat().st_mode & stat.S_IXUSR:
            errors.append(
                f"vendor: '{rel}' lost its exec bit; run 'scripts/marketplace.py portable'"
            )
    for path in sorted([*PLUGINS_DIR.glob("*/references/*"), *PLUGINS_DIR.glob("*/scripts/*")]):
        if path.is_file() and path not in plan:
            head = path.read_text(encoding="utf-8", errors="replace").splitlines()[:2]
            if any(VENDOR_MARKER in line for line in head):
                rel = path.relative_to(REPO_ROOT)
                errors.append(f"vendor: '{rel}' carries a banner but shared/vendor.yml omits it")
    return errors


@app.command()
def portable(*, check: bool = False) -> None:
    """Emit ``.agents/skills/`` and the Codex manifests this repo ships.

    Each skill becomes one portable skill directory. Files a skill reaches by
    climbing out of its own directory are copied in and the links rewritten, so
    each output skill is self-contained. Copies are deliberate: the manifest at
    ``.agents/portable-manifest.json`` records how many times each source is
    duplicated.

    The Codex side needs no such copy. Codex reads ``skills/`` in place, so all
    it takes is a ``.codex-plugin/plugin.json`` per plugin naming that directory
    and a marketplace manifest in Codex's own format. Each skill, in place and
    exported, also gets an ``agents/openai.yaml`` carrying Codex's presentation
    and its spelling of ``disable-model-invocation``.

    Files under ``shared/`` are written into each plugin listed for them in
    ``shared/vendor.yml`` before anything is rendered.

    Parameters
    ----------
    check : bool
        If True, verify the committed tree matches a fresh render and satisfies
        the portable contract; exit 1 on any finding.
    """
    vendor_plan, vendor_errors = _vendor_plan()
    if not check and not vendor_errors:
        for dest, content in sorted(vendor_plan.items()):
            dest.parent.mkdir(parents=True, exist_ok=True)
            _ = dest.write_text(content, encoding="utf-8")
            if dest.suffix == ".py":
                dest.chmod(dest.stat().st_mode | 0o111)
    sources = _collect_sources()
    built = _build_portable()
    codex_files = _codex_files()
    if not check:
        if vendor_errors:
            for error in vendor_errors:
                console.print(f"[red]Error:[/red] {rich.markup.escape(error)}")
            raise SystemExit(1)
        _write_portable(built, PORTABLE_SKILLS_DIR, PORTABLE_MANIFEST_PATH)
        _remove_stale_codex(codex_files, REPO_ROOT)
        for rel, content in sorted(codex_files.items()):
            path = REPO_ROOT / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            _ = path.write_bytes(content)
        console.print(f"[green]Wrote {len(codex_files)} Codex manifests[/green]")
        total = sum(len(c) for s in built for c, _ in s.files.values())
        files = sum(len(s.files) for s in built)
        summary = (
            f"[green]Wrote {len(built)} skills, {files} files, {total:,} bytes"
            f" to {PrivatePath(PORTABLE_SKILLS_DIR)}[/green]"
        )
        console.print(summary)
        return

    errors = vendor_errors + _check_vendor(vendor_plan)
    errors += _check_invariants(built, sources) + _check_drift(built)
    errors.extend(_check_codex_drift(codex_files))
    manifest = json.dumps(_portable_manifest(built), indent=2) + "\n"
    if not PORTABLE_MANIFEST_PATH.exists():
        errors.append("portable: .agents/portable-manifest.json is missing")
    elif PORTABLE_MANIFEST_PATH.read_text(encoding="utf-8") != manifest:
        errors.append("portable: .agents/portable-manifest.json is stale")

    if errors:
        for error in errors:
            console.print(f"[red]Error:[/red] {rich.markup.escape(error)}")
        console.print(f"\n[red bold]{len(errors)} error(s) found.[/red bold]")
        raise SystemExit(1)
    for token, users in _external_paths(built).items():
        note = (
            f"[yellow]Note:[/yellow] '{rich.markup.escape(token)}' names a file in the"
            f" user's project, not in the bundle; left verbatim in {len(users)} skill(s)"
        )
        console.print(note)
    clean = (
        f"[green bold]0 errors found.[/green bold] {len(built)} portable skills,"
        f" {sum(len(s.files) for s in built)} files."
    )
    console.print(clean)


if __name__ == "__main__":
    app()
