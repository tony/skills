#!/usr/bin/env python3
"""Deterministic steps of study-deps: scan, vet, plan, resolve, clone, report.

Every command prints one JSON object on stdout. A refusal prints
``{"ok": false, "error": "<reason>"}``, the same reason as one line on stderr,
and exits 2. Run ``deps.py <command> --help`` for each command.
"""

# pyright: reportUnusedCallResult=false

from __future__ import annotations

import argparse
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import typing as t
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

if t.TYPE_CHECKING:
    import http.client
    from collections.abc import Mapping, Sequence

EXIT_REFUSED = 2
FORGES = ("github.com", "gitlab.com", "codeberg.org", "bitbucket.org")
USER_AGENT = "study-deps (+https://github.com/tony/skills)"
JSON_LIMIT = 5_000_000
CRATE_LIMIT = 100_000_000
GIT_TIMEOUT = 600
CATEGORIES = ("dev", "build", "peer", "runtime")
DEV_GROUPS = frozenset({"dev", "test", "tests", "testing", "lint", "docs", "doc", "typing"})

ECOSYSTEMS = {
    "package.json": ("npm", "typescript"),
    "pyproject.toml": ("pypi", "python"),
    "Cargo.toml": ("crates", "rust"),
    "go.mod": ("go", "golang"),
    "Gemfile": ("rubygems", "ruby"),
    "mix.exs": ("hex", "elixir"),
    "build.gradle": ("maven", "java"),
    "build.gradle.kts": ("maven", "java"),
    "pom.xml": ("maven", "java"),
}
LOCKFILES = {
    "npm": ("package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lock"),
    "pypi": (
        "uv.lock",
        "poetry.lock",
        "pdm.lock",
        "pylock.toml",
        "Pipfile.lock",
        "requirements.txt",
    ),
    "crates": ("Cargo.lock",),
    "go": ("go.sum",),
    "rubygems": ("Gemfile.lock",),
    "hex": ("mix.lock",),
    "maven": ("gradle.lockfile",),
}

NAME_RES = {
    "npm": re.compile(r"^(@[A-Za-z0-9._~-]+/)?[A-Za-z0-9._~-]+$"),
    "pypi": re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$"),
    "crates": re.compile(r"^[A-Za-z0-9_-]+$"),
    "go": re.compile(r"^[A-Za-z0-9][A-Za-z0-9._~/-]*$"),
}
PLAIN_NAME_RE = re.compile(r"^[A-Za-z0-9@][A-Za-z0-9._+~:/@-]*$")
VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+~-]*$")
PLAIN_CONSTRAINT_RE = re.compile(r"^[A-Za-z0-9.,<>=!~^*+| -]*$")
NOT_PLAIN_NAME = "name is not a plain package name"
NOT_PLAIN_VERSION = "version is not a plain version string"
SHA_RE = re.compile(r"^[0-9a-f]{7,40}$")
HOST_RE = re.compile(r"^[a-z0-9]([a-z0-9.-]*[a-z0-9])?(:\d{1,5})?$")
PATH_PART_RE = re.compile(r"^[A-Za-z0-9._~-]+$")


class Refusal(Exception):  # noqa: N818
    """A step the script will not take; the message is the one-line reason."""


def load_json(text: str) -> object:
    """Parse JSON into an ``object`` so callers narrow it before use."""
    return t.cast("object", json.loads(text))


def as_dict(value: object) -> dict[str, object]:
    """Return ``value`` as a string-keyed dict, or an empty dict for any other type."""
    if isinstance(value, dict):
        return {str(k): v for k, v in t.cast("dict[object, object]", value).items()}
    return {}


def as_list(value: object) -> list[object]:
    """Return ``value`` as a list, or an empty list for any other type."""
    return list(t.cast("list[object]", value)) if isinstance(value, list) else []


def as_str(value: object) -> str:
    """Return ``value`` when it is a string, else an empty string."""
    return value if isinstance(value, str) else ""


def plain_name(value: str) -> bool:
    """Report whether a name is inert when pasted into a shell word.

    >>> plain_name("@babel/core"), plain_name("x$(id)"), plain_name("a..b")
    (True, False, False)
    """
    return bool(PLAIN_NAME_RE.match(value)) and ".." not in value


def plain_version(value: str) -> bool:
    """Report whether a version is inert when pasted into a shell word.

    >>> plain_version("1.2.3-rc.1+b5"), plain_version("1;id")
    (True, False)
    """
    return bool(VERSION_RE.match(value))


def require_plain(name: str | None = None, version: str | None = None) -> None:
    """Refuse a name or version that is not plain."""
    if name is not None and not plain_name(name):
        msg = f"package name {name!r} is not a plain package name"
        raise Refusal(msg)
    if version is not None and not plain_version(version):
        msg = f"version {version!r} is not a plain version string"
        raise Refusal(msg)


def _put(table: dict[str, str], key: str, value: str) -> None:
    if key not in table:
        table[key] = value


# --- sanitizing and URL vetting -------------------------------------------------


def sanitize(part: str, what: str = "path component") -> str:
    """Return ``part`` with other characters replaced by ``-``, or refuse.

    >>> sanitize("release/5.2")
    'release-5.2'
    >>> sanitize("@scope/pkg@1")
    '-scope-pkg-1'
    >>> sanitize("..")
    Traceback (most recent call last):
    ...
    deps.Refusal: path component '..' is empty, starts with '.', or contains '..'
    """
    clean = re.sub(r"[^A-Za-z0-9._-]", "-", part)
    if not clean or clean.startswith(".") or ".." in clean:
        msg = f"{what} {part!r} is empty, starts with '.', or contains '..'"
        raise Refusal(msg)
    return clean


def normalize_url(raw: str, confirmed_hosts: tuple[str, ...] = ()) -> dict[str, object]:
    """Vet a repository URL: https or git+https only, ``/<owner>/<repo>`` shape.

    >>> normalize_url("git+https://github.com/colinhacks/zod.git")["url"]
    'https://github.com/colinhacks/zod'
    >>> normalize_url("ssh://git@code.example.net/a/b.git")
    Traceback (most recent call last):
    ...
    deps.Refusal: scheme 'ssh' is not https
    """
    text = raw.strip()
    if "://" not in text:
        msg = "not an https:// URL (ssh, scp-style, and local forms are refused)"
        raise Refusal(msg)
    scheme, _, rest = text.partition("://")
    scheme = scheme.lower()
    scheme = scheme.removeprefix("git+")
    if scheme != "https":
        msg = f"scheme {scheme!r} is not https"
        raise Refusal(msg)
    parts = urllib.parse.urlsplit("https://" + rest)
    if parts.username is not None or parts.password is not None or "@" in parts.netloc:
        msg = "URL carries credentials"
        raise Refusal(msg)
    host = (parts.netloc or "").lower()
    if not HOST_RE.match(host):
        msg = f"host {host!r} is not a plain hostname"
        raise Refusal(msg)
    segments = [s for s in parts.path.split("/") if s]
    if len(segments) < 2:  # noqa: PLR2004
        msg = "URL is not of the form https://<host>/<owner>/<repo>"
        raise Refusal(msg)
    segments[-1] = segments[-1].removesuffix(".git")
    if not all(PATH_PART_RE.match(s) and s not in {".", ".."} for s in segments):
        msg = "URL path holds characters outside letters, digits, '.', '_', '~', '-'"
        raise Refusal(msg)
    bare = host.split(":")[0]
    forge = bare in FORGES and host == bare
    confirmed = host in confirmed_hosts
    return {
        "url": f"https://{host}/{'/'.join(segments)}",
        "host": host,
        "repo_name": sanitize(segments[-1], "repository name"),
        "known_forge": forge,
        "needs_confirmation": not (forge or confirmed),
    }


def same_repo(a: str, b: str) -> bool:
    """Compare two repository URLs after normalization.

    >>> same_repo("https://GitHub.com/a/b.git", "git+https://github.com/a/b")
    True
    """
    try:
        return normalize_url(a)["url"] == normalize_url(b)["url"]
    except Refusal:
        return False


# --- git helpers ---------------------------------------------------------------


def git_do(*args: str) -> None:
    """Run git for its effect and discard stdout."""
    _ = git(*args)


def git(*args: str, cwd: Path | None = None) -> str:
    """Run git and return stdout; a failure refuses with git's first stderr line."""
    cmd = ["git", "-c", "protocol.ext.allow=never", *args]
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    try:
        done = subprocess.run(  # noqa: S603
            cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=GIT_TIMEOUT, check=False
        )
    except subprocess.TimeoutExpired as exc:
        msg = f"git {args[0]} timed out"
        raise Refusal(msg) from exc
    if done.returncode != 0:
        first = (done.stderr.strip().splitlines() or [f"git {args[0]} failed"])[0]
        raise Refusal(first)
    return done.stdout


def origin_of(clone: Path) -> str:
    """Return the clone's origin URL, or refuse when the directory is not a clone."""
    if not (clone / ".git").exists():
        msg = "directory exists but is not a git clone"
        raise Refusal(msg)
    return git("-C", str(clone), "config", "--get", "remote.origin.url").strip()


def display(path: Path) -> str:
    """Show ``path`` as ``~/...`` when it is under the home directory."""
    try:
        return "~/" + path.relative_to(Path.home()).as_posix()
    except ValueError:
        return str(path)


# --- manifest and lockfile discovery --------------------------------------------


def toml_tables(text: str) -> tuple[dict[str, dict[str, str]], dict[str, list[dict[str, str]]]]:
    r"""Parse the TOML subset manifests use: tables, array tables, raw values.

    >>> t, a = toml_tables('[a.b]\nx = "1"\n[[p]]\nname = "n"\nversion = "2"\n')
    >>> t["a.b"]["x"], a["p"][0]["version"]
    ('"1"', '"2"')
    """
    tables: dict[str, dict[str, str]] = {"": {}}
    arrays: dict[str, list[dict[str, str]]] = {}
    current = tables[""]
    pending: tuple[str, str] | None = None
    for line in text.splitlines():
        stripped = re.sub(r"\s#.*$", "", line).strip()
        if pending:
            key, acc = pending
            acc += " " + stripped
            if _balanced(acc):
                current[key] = acc
                pending = None
            else:
                pending = (key, acc)
            continue
        if not stripped or stripped.startswith("#"):
            continue
        header = re.match(r"^\[\[\s*([^\]]+?)\s*\]\]$", stripped)
        if header:
            current = dict[str, str]()
            rows = arrays.setdefault(str(header.group(1)), [])
            rows.append(current)
            continue
        header = re.match(r"^\[\s*([^\]]+?)\s*\]$", stripped)
        if header:
            current = tables.setdefault(header.group(1).replace('"', ""), {})
            continue
        pair = re.match(r"^([A-Za-z0-9_.\"-]+)\s*=\s*(.*)$", stripped)
        if pair:
            key, value = pair.group(1).strip('"'), pair.group(2)
            if _balanced(value):
                current[key] = value
            else:
                pending = (key, value)
    return tables, arrays


def _balanced(value: str) -> bool:
    bare = re.sub(r'"[^"]*"|\'[^\']*\'', "", value)
    return bare.count("[") <= bare.count("]") and bare.count("{") <= bare.count("}")


def toml_strings(raw: str) -> list[str]:
    """Return the quoted strings in a raw TOML value."""
    pairs = t.cast("list[tuple[str, str]]", re.findall(r'"([^"]*)"|\'([^\']*)\'', raw))
    return [a or b for a, b in pairs]


def toml_scalar(raw: str) -> str:
    """Return the first quoted string of a raw TOML value, or an empty string."""
    found = toml_strings(raw)
    return found[0] if found else ""


def _norm_py(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _dep(  # noqa: PLR0913, PLR0917
    name: str, constraint: str, category: str, eco: str, manifest: str, language: str
) -> dict[str, object]:
    return {
        "name": name,
        "constraint": constraint,
        "category": category,
        "ecosystem": eco,
        "language": language,
        "manifest": manifest,
        "version": None,
        "lockfile": None,
        "declared": None,
    }


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _npm_deps(path: Path) -> list[dict[str, object]]:
    data = as_dict(load_json(_read(path)))
    kinds = (
        ("dependencies", "runtime"),
        ("optionalDependencies", "runtime"),
        ("devDependencies", "dev"),
        ("peerDependencies", "peer"),
    )
    out: list[dict[str, object]] = []
    for key, cat in kinds:
        for name, rng in as_dict(data.get(key)).items():
            dep = _dep(name, str(rng), cat, "npm", path.name, "typescript")
            dep["declared"] = _npm_declared(str(rng))
            out.append(dep)
    return out


def _npm_declared(rng: str) -> str | None:
    """Return the repository a dependency range names, if it is a git source."""
    short = re.match(r"^(github|gitlab|bitbucket):([^/\s]+/[^/\s#]+)", rng)
    if short:
        forge, repo = short.group(1), short.group(2)
        return f"https://{forge}.{'org' if forge == 'bitbucket' else 'com'}/{repo}"
    return rng.split("#", 1)[0] if re.match(r"^(git\+)?[a-z]+://", rng) else None


def _pep508(spec: str) -> tuple[str, str] | None:
    match = re.match(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(?:\[[^\]]*\])?\s*([^;]*)", spec)
    return (match.group(1), match.group(2).strip()) if match else None


def _py_deps(path: Path) -> list[dict[str, object]]:
    tables, _ = toml_tables(_read(path))
    out: list[dict[str, object]] = []

    def add_specs(raw: str, cat: str) -> None:
        for spec in toml_strings(raw):
            parsed = _pep508(spec)
            if parsed:
                out.append(_dep(parsed[0], parsed[1], cat, "pypi", path.name, "python"))

    project = tables.get("project", {})
    if "dependencies" in project:
        add_specs(project["dependencies"], "runtime")
    for group, raw in tables.get("project.optional-dependencies", {}).items():
        add_specs(raw, "dev" if group.lower() in DEV_GROUPS else "runtime")
    for raw in tables.get("dependency-groups", {}).values():
        add_specs(raw, "dev")
    if "requires" in tables.get("build-system", {}):
        add_specs(tables["build-system"]["requires"], "build")
    for header, entries in tables.items():
        poetry = re.match(r"^tool\.poetry\.(?:group\.([^.]+)\.)?(dev-)?dependencies$", header)
        if poetry:
            cat = "dev" if poetry.group(1) or poetry.group(2) else "runtime"
            for name, raw in entries.items():
                if name.lower() != "python":
                    ver = toml_scalar(raw) if raw.lstrip().startswith('"') else _inline(raw)
                    out.append(_dep(name, ver, cat, "pypi", path.name, "python"))
    return out


def _inline(raw: str) -> str:
    match = re.search(r'version\s*=\s*"([^"]*)"', raw)
    return match.group(1) if match else ""


def _cargo_deps(path: Path) -> list[dict[str, object]]:
    tables, _ = toml_tables(_read(path))
    kinds = {"dependencies": "runtime", "dev-dependencies": "dev", "build-dependencies": "build"}
    out: list[dict[str, object]] = []
    for header, entries in tables.items():
        parts = header.split(".")
        # [target.'cfg(unix)'.dependencies] keeps its kind from the last segment.
        if parts[-1] in kinds:
            for name, raw in entries.items():
                ver = toml_scalar(raw) if raw.lstrip().startswith('"') else _inline(raw)
                dep = _dep(name, ver, kinds[parts[-1]], "crates", path.name, "rust")
                git_url = re.search(r'git\s*=\s*"([^"]*)"', raw)
                dep["declared"] = git_url.group(1) if git_url else None
                out.append(dep)
        elif len(parts) >= 2 and parts[-2] in kinds:  # noqa: PLR2004
            out.append(
                _dep(parts[-1], toml_scalar(entries.get("version", "")), kinds[parts[-2]],
                     "crates", path.name, "rust")
            )  # fmt: skip
    return out


def _go_deps(path: Path) -> list[dict[str, object]]:
    text = _read(path)
    out: list[dict[str, object]] = []
    blocks = t.cast(
        "list[str]", re.findall(r"^require\s*\(\s*\n(.*?)^\)", text, re.MULTILINE | re.DOTALL)
    )
    lines = [ln for block in blocks for ln in block.splitlines()]
    lines += t.cast("list[str]", re.findall(r"^require\s+(\S+\s+\S+.*)$", text, re.MULTILINE))
    for line in lines:
        match = re.match(r"^\s*(\S+)\s+(v\S+)", line)
        if match:
            dep = _dep(match.group(1), match.group(2), "runtime", "go", path.name, "golang")
            dep["version"], dep["lockfile"] = match.group(2), path.name
            dep["declared"] = _go_declared(match.group(1))
            out.append(dep)
    return out


def _go_declared(module: str) -> str | None:
    """Return the repository URL a module path on a known forge implies."""
    parts = module.split("/")
    if len(parts) >= 3 and parts[0] in FORGES:  # noqa: PLR2004
        return "https://" + "/".join(parts[:3])
    return None


def _gem_deps(path: Path) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    group = "runtime"
    for line in _read(path).splitlines():
        grp = re.match(r"^\s*group\s+(.+?)\s+do", line)
        if grp:
            names = set(re.findall(r":(\w+)", grp.group(1)))
            group = "dev" if names & {"development", "test"} else "runtime"
        elif re.match(r"^\s*end\b", line):
            group = "runtime"
        gem = re.match(r"""^\s*gem\s+['"]([^'"]+)['"](?:\s*,\s*['"]([^'"]*)['"])?""", line)
        if gem:
            cat = (
                "dev"
                if re.search(
                    r":group\s*=>\s*:(development|test)|group:\s*:(development|test)", line
                )
                else group
            )
            out.append(_dep(gem.group(1), gem.group(2) or "", cat, "rubygems", path.name, "ruby"))
    return out


def _mix_deps(path: Path) -> list[dict[str, object]]:
    return [
        _dep(m.group(1), m.group(2) or "", "dev" if "only:" in m.group(3) else "runtime",
             "hex", path.name, "elixir")
        for m in re.finditer(r'\{:(\w+)\s*(?:,\s*"([^"]*)")?([^}]*)\}', _read(path))
    ]  # fmt: skip


def _gradle_deps(path: Path) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    configs = (
        r"\w*[Ii]mplementation|api|compileOnly|runtimeOnly|testCompileOnly|testRuntimeOnly"
        r"|annotationProcessor|kapt"
    )
    pat = re.compile(rf"""^\s*({configs})\s*\(?\s*['"]([^:'"]+:[^:'"]+)(?::([^'":@]+))?""")
    for line in _read(path).splitlines():
        match = pat.match(line)
        if match:
            cat = "dev" if match.group(1).lower().startswith("test") else "runtime"
            out.append(_dep(match.group(2), match.group(3) or "", cat, "maven", path.name, "java"))
    return out


def _pom_deps(path: Path) -> list[dict[str, object]]:
    text = _read(path)
    if "<!DOCTYPE" in text:
        msg = "pom.xml declares a DOCTYPE"
        raise Refusal(msg)
    root = ET.fromstring(text)  # noqa: S314
    out: list[dict[str, object]] = []
    for dep in root.iter():
        if dep.tag.rsplit("}", 1)[-1] != "dependency":
            continue
        kids = {k.tag.rsplit("}", 1)[-1]: (k.text or "").strip() for k in dep}
        if "groupId" in kids and "artifactId" in kids:
            cat = "dev" if kids.get("scope") == "test" else "runtime"
            name = f"{kids['groupId']}:{kids['artifactId']}"
            out.append(_dep(name, kids.get("version", ""), cat, "maven", path.name, "java"))
    return out


MANIFEST_PARSERS = {
    "package.json": _npm_deps,
    "pyproject.toml": _py_deps,
    "Cargo.toml": _cargo_deps,
    "go.mod": _go_deps,
    "Gemfile": _gem_deps,
    "mix.exs": _mix_deps,
    "build.gradle": _gradle_deps,
    "build.gradle.kts": _gradle_deps,
    "pom.xml": _pom_deps,
}


def _lock_npm(path: Path) -> dict[str, str]:
    text = _read(path)
    out: dict[str, str] = {}
    if path.name == "package-lock.json":
        data = as_dict(load_json(text))
        for key, entry in as_dict(data.get("packages")).items():
            if key.startswith("node_modules/") and key.count("node_modules/") == 1:
                out[key.removeprefix("node_modules/")] = as_str(as_dict(entry).get("version"))
        for key, entry in as_dict(data.get("dependencies")).items():
            _put(out, key, as_str(as_dict(entry).get("version")))
    elif path.name == "pnpm-lock.yaml":
        for m in re.finditer(
            r"^\s+'?(@?[^\s:'()]+)'?:\n\s+specifier: .+\n\s+version: '?([^\s'(]+)",
            text,
            re.MULTILINE,
        ):
            _put(out, m.group(1), m.group(2))
        for m in re.finditer(r"^\s+'?/?(@?[^\s@'()]+)@(\d[^\s:'()]*)", text, re.MULTILINE):
            _put(out, m.group(1), m.group(2))
    elif path.name == "yarn.lock":
        for block in re.split(r"\n\n+", text):
            ver = re.search(r'^\s+version:? "?([^"\s]+)"?', block, re.MULTILINE)
            head = block.strip().splitlines()[0] if block.strip() else ""
            if ver and head and not head.startswith("#"):
                for name in t.cast("list[str]", re.findall(r'"?(@?[^@\s",]+)@', head)):
                    _put(out, name, ver.group(1))
    elif path.name == "bun.lock":
        for m in re.finditer(r'"([^"]+)":\s*\["(@?[^"@]+)@([^"]+)"', text):
            _put(out, m.group(2), m.group(3))
    return out


def _lock_pypi(path: Path) -> dict[str, str]:
    text = _read(path)
    out: dict[str, str] = {}
    if path.name == "Pipfile.lock":
        data = as_dict(load_json(text))
        for section in ("default", "develop"):
            for name, entry in as_dict(data.get(section)).items():
                _put(out, _norm_py(name), as_str(as_dict(entry).get("version")).lstrip("="))
    elif path.name == "requirements.txt":
        for m in re.finditer(
            r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)(?:\[[^\]]*\])?\s*==\s*([^\s;#\\]+)",
            text,
            re.MULTILINE,
        ):
            _put(out, _norm_py(m.group(1)), m.group(2))
    else:
        _, arrays = toml_tables(text)
        for pkg in arrays.get("package", []):
            if "name" in pkg and "version" in pkg:
                _put(out, _norm_py(toml_scalar(pkg["name"])), toml_scalar(pkg["version"]))
    return out


def _lock_crates(path: Path) -> dict[str, str]:
    _, arrays = toml_tables(_read(path))
    return {
        toml_scalar(p["name"]): toml_scalar(p["version"])
        for p in arrays.get("package", [])
        if "name" in p and "version" in p
    }


def _lock_gems(path: Path) -> dict[str, str]:
    return {
        m.group(1): m.group(2)
        for m in re.finditer(r"^    ([A-Za-z0-9_.-]+) \(([^)\s,]+)\)", _read(path), re.MULTILINE)
    }


def _lock_hex(path: Path) -> dict[str, str]:
    return {
        m.group(1): m.group(2)
        for m in re.finditer(r'"([^"]+)":\s*\{:hex,\s*:[^,]+,\s*"([^"]+)"', _read(path))
    }


def _lock_gradle(path: Path) -> dict[str, str]:
    return {
        f"{m.group(1)}:{m.group(2)}": m.group(3)
        for m in re.finditer(r"^([^:#\s]+):([^:\s]+):([^=\s]+)=", _read(path), re.MULTILINE)
    }


LOCK_PARSERS = {
    "npm": _lock_npm,
    "pypi": _lock_pypi,
    "crates": _lock_crates,
    "rubygems": _lock_gems,
    "hex": _lock_hex,
    "maven": _lock_gradle,
}


def scan(project: Path) -> list[dict[str, object]]:
    """List the dependencies of ``project`` with the exact version a lockfile resolves.

    Only the project directory is read; workspace members are not walked.
    """
    deps: list[dict[str, object]] = []
    for manifest, (eco, _lang) in ECOSYSTEMS.items():
        path = project / manifest
        if not path.is_file():
            continue
        try:
            found = MANIFEST_PARSERS[manifest](path)
        except (ValueError, ET.ParseError) as exc:
            msg = f"{manifest} cannot be parsed: {exc}"
            raise Refusal(msg) from exc
        parser = LOCK_PARSERS.get(eco)
        if parser:
            for lock_name in LOCKFILES[eco]:
                lock = project / lock_name
                if not lock.is_file():
                    continue
                try:
                    pins = parser(lock)
                except ValueError as exc:
                    msg = f"{lock_name} cannot be parsed: {exc}"
                    raise Refusal(msg) from exc
                for dep in found:
                    if dep["version"]:
                        continue
                    key = _norm_py(str(dep["name"])) if eco == "pypi" else str(dep["name"])
                    if pins.get(key):
                        dep["version"], dep["lockfile"] = pins[key], lock_name
        deps.extend(found)
    return deps


def scan_vetted(project: Path) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Split ``scan`` into plain dependencies and skipped ones, with repositories vetted.

    A name or version that is not plain never leaves this function as text: the
    entry carries only a reason, so the model cannot paste it into a command.
    """
    plain: list[dict[str, object]] = []
    skipped: list[dict[str, object]] = []
    for dep in scan(project):
        name, version = str(dep["name"]), dep["version"]
        declared = dep.pop("declared", None)
        constraint = str(dep["constraint"])
        if not PLAIN_CONSTRAINT_RE.match(constraint):
            dep["constraint"] = ""
        reason = None
        if not plain_name(name):
            reason = NOT_PLAIN_NAME
        elif version is not None and not plain_version(str(version)):
            reason = NOT_PLAIN_VERSION
        elif version is None:
            reason = "no resolved version"
        if reason:
            keep = {k: dep[k] for k in ("category", "ecosystem", "manifest")}
            if plain_name(name):
                keep["name"] = name
            skipped.append({**keep, "status": "skipped", "reason": reason})
            continue
        dep["repository"] = _vet_declared(declared)
        plain.append(dep)
    return plain, skipped


def _vet_declared(declared: object) -> dict[str, object] | None:
    if not isinstance(declared, str):
        return None
    try:
        return normalize_url(declared)
    except Refusal as exc:
        return {"url": None, "error": str(exc)}


def filter_deps(deps: list[dict[str, object]], selector: str) -> list[dict[str, object]]:
    """Keep deps matching ``all``, a category, or a package name."""
    if selector == "all":
        return deps
    if selector in CATEGORIES:
        return [d for d in deps if d["category"] == selector]
    return [d for d in deps if d["name"] == selector]


# --- registry lookups -----------------------------------------------------------


def http_get(url: str, limit: int = JSON_LIMIT) -> bytes:
    """GET an https URL with a descriptive user agent, capped at ``limit`` bytes."""
    if not url.startswith("https://"):
        msg = "registry requests are https only"
        raise Refusal(msg)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})  # noqa: S310
    try:
        opened = t.cast("http.client.HTTPResponse", urllib.request.urlopen(req, timeout=30))  # noqa: S310
        with opened as resp:
            data = resp.read(limit + 1)
    except (urllib.error.URLError, TimeoutError) as exc:
        msg = f"registry request failed: {exc}"
        raise Refusal(msg) from exc
    if len(data) > limit:
        msg = "registry response exceeds the size limit"
        raise Refusal(msg)
    return data


def run_cmd(argv: list[str], cwd: str) -> str:
    """Run a read-only registry command and return its stdout."""
    try:
        done = subprocess.run(  # noqa: S603
            argv, cwd=cwd, capture_output=True, text=True, timeout=120, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        msg = f"{argv[0]} failed: {exc}"
        raise Refusal(msg) from exc
    if done.returncode != 0:
        first = (done.stderr.strip().splitlines() or [f"{argv[0]} failed"])[0]
        raise Refusal(first)
    return done.stdout


def lookup_request(eco: str, name: str, version: str) -> dict[str, object]:
    """Return the read-only request for an ecosystem, validated against injection."""
    if eco not in NAME_RES:
        msg = f"no registry lookup for ecosystem {eco!r}"
        raise Refusal(msg)
    require_plain(name, version)
    if not NAME_RES[eco].match(name):
        msg = f"package name {name!r} is not valid for {eco}"
        raise Refusal(msg)
    quoted = urllib.parse.quote(name, safe="")
    if eco == "npm":
        argv = ["npm", "view", "--json", "--", f"{name}@{version}", "repository.url", "gitHead"]
        return {"kind": "command", "argv": argv, "display": " ".join(argv)}
    if eco == "go":
        argv = ["go", "list", "-m", "-json", "--", f"{name}@{version}"]
        return {"kind": "command", "argv": argv, "display": " ".join(argv)}
    if eco == "pypi":
        url = f"https://pypi.org/pypi/{quoted}/{urllib.parse.quote(version, safe='')}/json"
    else:
        url = f"https://crates.io/api/v1/crates/{quoted}"
    return {"kind": "http", "url": url, "display": f"GET {url}"}


PY_URL_KEYS = ("source", "source code", "repository", "code", "github", "gitlab", "homepage")


def parse_lookup(eco: str, payload: str) -> dict[str, object]:
    """Extract ``repository`` and the registry-recorded ``commit`` from a response.

    Registry fields: PyPI ``info.project_urls`` (no commit), npm ``repository.url``
    and ``gitHead``, crates.io ``crate.repository`` (no commit), Go ``Origin.URL``
    and ``Origin.Hash``.

    >>> parse_lookup("npm", '"https://github.com/babel/babel.git"')["repository"]
    'https://github.com/babel/babel.git'
    """
    try:
        data = load_json(payload)
    except ValueError as exc:
        msg = f"{eco} lookup did not return JSON"
        raise Refusal(msg) from exc
    repo: str | None = None
    commit: str | None = None
    fields = as_dict(data)
    if eco == "npm":
        if isinstance(data, str):
            repo = data
        else:
            repo, commit = as_str(fields.get("repository.url")), as_str(fields.get("gitHead"))
    elif eco == "go":
        origin = as_dict(fields.get("Origin"))
        repo, commit = as_str(origin.get("URL")), as_str(origin.get("Hash"))
    elif eco == "crates":
        repo = as_str(as_dict(fields.get("crate")).get("repository"))
    elif eco == "pypi":
        info = as_dict(fields.get("info"))
        urls = {k.lower(): as_str(v) for k, v in as_dict(info.get("project_urls")).items()}
        urls["homepage"] = urls.get("homepage") or as_str(info.get("home_page"))
        repo = next((urls[k] for k in PY_URL_KEYS if k in urls and _is_repo_url(urls[k])), None)
    return {"repository": repo or None, "commit": commit or None}


def _is_repo_url(value: object) -> bool:
    return isinstance(value, str) and same_repo(value, value)


def crate_commit(name: str, version: str) -> str | None:
    """Read ``git.sha1`` from ``.cargo_vcs_info.json`` inside the published .crate."""
    quoted = urllib.parse.quote(name, safe="")
    url = (
        f"https://crates.io/api/v1/crates/{quoted}/{urllib.parse.quote(version, safe='')}/download"
    )
    blob = http_get(url, CRATE_LIMIT)
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tar:
        for member in tar:
            if (
                member.isfile()
                and member.name.count("/") == 1
                and member.name.endswith("/.cargo_vcs_info.json")
            ):
                handle = tar.extractfile(member)
                if handle is None:
                    return None
                info = as_dict(load_json(handle.read(65536).decode("utf-8")))
                return as_str(as_dict(info.get("git")).get("sha1")) or None
    return None


def lookup(eco: str, name: str, version: str, *, crate_vcs: bool) -> dict[str, object]:
    """Run the registry lookup and vet the repository URL it returns."""
    req = lookup_request(eco, name, version)
    if req["kind"] == "command":
        argv = [str(a) for a in t.cast("list[object]", req["argv"])]
        payload = run_cmd(argv, cwd=tempfile.gettempdir())
    else:
        payload = http_get(str(req["url"])).decode("utf-8", errors="replace")
    found = parse_lookup(eco, payload)
    commit = found["commit"]
    if eco == "crates" and crate_vcs:
        commit = crate_commit(name, version)
    out: dict[str, object] = {"command": req["display"], "commit": commit, "commit_source": None}
    if commit:
        out["commit_source"] = {
            "npm": "gitHead",
            "go": "Origin.Hash",
            "crates": ".cargo_vcs_info.json",
        }.get(eco)
    raw = found["repository"]
    if not raw:
        out["repository"] = None
        out["error"] = "registry lists no repository"
        return out
    try:
        out["repository"] = normalize_url(str(raw))
    except Refusal as exc:
        out["repository"] = None
        out["error"] = str(exc)
    return out


# --- version resolution ---------------------------------------------------------


def parse_ls_remote(text: str) -> tuple[dict[str, str], dict[str, str]]:
    r"""Return ``(tags, branches)`` as name to commit from ``git ls-remote`` output.

    Annotated tags use the peeled ``^{}`` commit.

    >>> out = "aaa\trefs/tags/v1\nbbb\trefs/tags/v1^{}\nccc\trefs/heads/main\n"
    >>> parse_ls_remote(out)
    ({'v1': 'bbb'}, {'main': 'ccc'})
    """
    tags: dict[str, str] = {}
    branches: dict[str, str] = {}
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) != 2:  # noqa: PLR2004
            continue
        sha, ref = parts
        if ref.startswith("refs/tags/"):
            name = ref[len("refs/tags/") :]
            if name.endswith("^{}"):
                tags[name[:-3]] = sha
            else:
                tags[name] = tags.get(name, sha)
        elif ref.startswith("refs/heads/"):
            branches[ref[len("refs/heads/") :]] = sha
    return tags, branches


def candidates(package: str, version: str) -> list[tuple[str, str]]:
    """List ``(kind, ref)`` guesses in cascade order for a resolved version."""
    short = package.rsplit("/", 1)[-1]
    parts = version.split(".")
    major = parts[0]
    minor = ".".join(parts[:2])
    out = [("tag", version), ("tag", f"v{version}")]
    out += [("tag", f"{package}@{version}")]
    if short != package:
        out += [("tag", f"{short}@{version}")]
    out += [("tag", f"{short}-v{version}"), ("tag", f"{short}-{version}")]
    out += [("branch", f"release/{minor}"), ("branch", f"{minor}.x")]
    out += [("branch", f"release/{major}.x"), ("branch", f"v{major}")]
    return out


def resolve(package: str, version: str, ls_remote: str) -> dict[str, object]:
    """Pick the first cascade hit: exact tag, ``v`` tag, scoped, crate-style, then branches."""
    require_plain(package, version)
    tags, branches = parse_ls_remote(ls_remote)
    for kind, ref in candidates(package, version):
        pool = tags if kind == "tag" else branches
        if ref in pool:
            return {"match": kind, "ref": ref, "commit": pool[ref]}
    return {"match": "none", "ref": None, "commit": None}


# --- planning, cloning, worktrees ------------------------------------------------


def study_paths(root: Path, lang: str, repo_name: str) -> tuple[Path, Path]:
    """Return the study root and the clone directory, both checked to stay in the root."""
    base = root.expanduser()
    clone = base / sanitize(lang, "language") / sanitize(repo_name, "repository name")
    if base.resolve() not in clone.resolve().parents:
        msg = "target path escapes the study root"
        raise Refusal(msg)
    return base, clone


def plan_entry(
    root: Path, lang: str, url: str, version: str | None, confirmed: tuple[str, ...]
) -> dict[str, object]:
    """Classify one dependency as new, update, or exists and name its paths."""
    if version is not None:
        require_plain(version=version)
    vet = normalize_url(url, confirmed)
    _, clone = study_paths(root, lang, str(vet["repo_name"]))
    worktree: Path | None = None
    if version:
        worktree = clone.parent / f"{clone.name}-{sanitize(version, 'version')}"
    if not clone.exists():
        action = "new"
    else:
        origin = origin_of(clone)
        if not same_repo(origin, str(vet["url"])):
            msg = "directory holds another repository"
            raise Refusal(msg)
        action = "exists" if worktree and worktree.exists() else "update"
    return {
        "action": action,
        "url": vet["url"],
        "host": vet["host"],
        "needs_confirmation": vet["needs_confirmation"],
        "clone": display(clone),
        "worktree": display(worktree) if worktree else None,
        "clone_abs": str(clone),
        "worktree_abs": str(worktree) if worktree else None,
    }


def clone_or_fetch(
    root: Path, lang: str, url: str, confirmed: tuple[str, ...]
) -> dict[str, object]:
    """Clone ``url`` into the study root, or fetch tags into a clone with the same origin."""
    vet = normalize_url(url, confirmed)
    if vet["needs_confirmation"]:
        msg = f"host {vet['host']} is not confirmed"
        raise Refusal(msg)
    _, clone = study_paths(root, lang, str(vet["repo_name"]))
    if clone.exists():
        if not same_repo(origin_of(clone), str(vet["url"])):
            msg = "directory holds another repository"
            raise Refusal(msg)
        git_do("-C", str(clone), "fetch", "--tags", "--force", "origin")
        action = "fetched"
    else:
        clone.parent.mkdir(parents=True, exist_ok=True)
        git_do("clone", "--", str(vet["url"]), str(clone))
        action = "cloned"
    head = git("-C", str(clone), "rev-parse", "HEAD").strip()
    return {"action": action, "clone": display(clone), "head": head, "sha7": head[:7]}


def default_branch(clone: Path) -> str:
    """Return the branch ``origin/HEAD`` points at."""
    ref = git("-C", str(clone), "symbolic-ref", "--short", "refs/remotes/origin/HEAD").strip()
    return ref.split("/", 1)[1] if "/" in ref else ref


def make_worktree(  # noqa: PLR0913
    root: Path,
    lang: str,
    url: str,
    *,
    version: str,
    tag: str | None,
    branch: str | None,
    registry_commit: str | None,
) -> dict[str, object]:
    """Create a detached worktree at a tag (pinned) or a branch tip (unpinned)."""
    require_plain(version=version)
    for ref in (tag, branch):
        if ref is not None:
            require_plain(name=ref)
    vet = normalize_url(url)
    _, clone = study_paths(root, lang, str(vet["repo_name"]))
    if not (clone / ".git").exists():
        msg = "clone is missing"
        raise Refusal(msg)
    name = clone.name
    if tag:
        commit = git(
            "-C", str(clone), "rev-parse", "--verify", f"refs/tags/{tag}^{{commit}}"
        ).strip()
        target = clone.parent / f"{name}-{sanitize(version, 'version')}"
        status, used = "pinned", None
    else:
        used = branch or default_branch(clone)
        commit = git(
            "-C", str(clone), "rev-parse", "--verify", f"refs/remotes/origin/{used}^{{commit}}"
        ).strip()
        target = clone.parent / f"{name}-{sanitize(used, 'branch')}-{commit[:7]}"
        status = "unpinned"
    if target.exists():
        return _worktree_result(target, "skipped", used, "worktree exists", None, None)
    git_do("-C", str(clone), "worktree", "add", "--detach", str(target), commit)
    head = git("-C", str(target), "rev-parse", "HEAD").strip()
    if head != commit:
        msg = "worktree HEAD differs from the requested commit"
        raise Refusal(msg)
    check = None
    if status == "pinned":
        check = _tag_check(commit, registry_commit)
    return _worktree_result(target, status, used, None, check, head)


def _tag_check(tag_commit: str, registry_commit: str | None) -> str:
    if not registry_commit:
        return "unchecked"
    reg = registry_commit.lower()
    short = min(len(reg), len(tag_commit))
    return "matches" if short >= 7 and reg[:short] == tag_commit[:short] else "differs"  # noqa: PLR2004


def _worktree_result(  # noqa: PLR0913, PLR0917
    target: Path,
    status: str,
    branch: str | None,
    reason: str | None,
    check: str | None,
    head: str | None,
) -> dict[str, object]:
    if head is None and (target / ".git").exists():
        head = git("-C", str(target), "rev-parse", "HEAD").strip()
    return {
        "status": status,
        "branch": branch,
        "reason": reason,
        "tag_check": check,
        "worktree": display(target),
        "commit": head,
        "sha7": head[:7] if head else None,
    }


def report(results: Sequence[Mapping[str, object]]) -> dict[str, object]:
    """Assemble the reply: hero line, then one line per package.

    >>> r = report([{"package": "z", "version": "1", "status": "pinned", "sha7": "abc1234",
    ...              "url": "https://github.com/a/z", "path": "~/study/ts/z-1"}])
    >>> r["lines"][0]
    '✓ 1 worktrees ready'
    """
    ready = [r for r in results if _is_ready(r)]
    failed = [r for r in results if r.get("status") == "failed"]
    if failed:
        hero = f"⚠ {len(failed)} failed" + (f", {len(ready)} worktrees ready" if ready else "")
    else:
        hero = f"✓ {len(ready)} worktrees ready"
    lines = [hero, ""]
    for res in results:
        status = str(res.get("status"))
        if status == "unpinned":
            status += f" ({res.get('branch')})"
        elif status in {"skipped", "failed"}:
            status += f": {res.get('reason')}"
        elif res.get("tag_check") in {"differs", "unchecked"}:
            status += f", tag {res['tag_check']}"
        fields = [
            f"{res['package']}@{res.get('version')}"
            if res.get("package")
            else "unnamed dependency",
            status,
            res.get("sha7"),
            res.get("url"),
            res.get("path"),
        ]
        lines.append("- " + " ".join(str(f) for f in fields if f))
    return {"ready": len(ready), "failed": len(failed), "lines": lines, "text": "\n".join(lines)}


def _is_ready(res: Mapping[str, object]) -> bool:
    status = res.get("status")
    return status in {"pinned", "unpinned"} or (
        status == "skipped" and res.get("reason") == "worktree exists"
    )


# --- command line ---------------------------------------------------------------


def emit(obj: dict[str, object]) -> None:
    """Print one JSON object."""
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    top = argparse.ArgumentParser(prog="deps.py", description=__doc__)
    sub = top.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("scan", help="list dependencies with lockfile-resolved versions")
    p.add_argument("--project", type=Path, default=Path())
    p.add_argument("--filter", default="all", help="package name, category, or all")

    p = sub.add_parser("url", help="vet and normalize a repository URL")
    p.add_argument("url")
    p.add_argument("--confirmed-host", action="append", default=[])

    p = sub.add_parser("plan", help="classify one dependency and name its paths")
    p.add_argument("--root", type=Path, default=Path("~/study"))
    p.add_argument("--lang", required=True)
    p.add_argument("--url", required=True)
    p.add_argument("--version")
    p.add_argument("--confirmed-host", action="append", default=[])

    p = sub.add_parser("lookup", help="registry lookup for a repository URL and commit")
    p.add_argument("--ecosystem", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--version", required=True)
    p.add_argument("--plan", action="store_true", help="print the request, run nothing")
    p.add_argument("--crate-commit", action="store_true", help="crates: download the .crate")

    p = sub.add_parser("resolve", help="match a version to a tag or branch")
    p.add_argument("--package", required=True)
    p.add_argument("--version", required=True)
    p.add_argument("--ls-remote", default="-", help="file of 'git ls-remote --tags --heads' output")

    p = sub.add_parser("clone", help="clone or fetch into the study root")
    p.add_argument("--root", type=Path, default=Path("~/study"))
    p.add_argument("--lang", required=True)
    p.add_argument("--url", required=True)
    p.add_argument("--confirmed-host", action="append", default=[])

    p = sub.add_parser("worktree", help="create a detached worktree and read back HEAD")
    p.add_argument("--root", type=Path, default=Path("~/study"))
    p.add_argument("--lang", required=True)
    p.add_argument("--url", required=True)
    p.add_argument("--version", required=True)
    p.add_argument("--tag", help="pinned: tag name from resolve")
    p.add_argument("--branch", help="unpinned: remote branch; default branch when omitted")
    p.add_argument("--registry-commit", help="commit the registry recorded for the release")

    p = sub.add_parser("report", help="assemble the reply from a JSON list of results")
    p.add_argument("--results", default="-", help="file of results, or - for stdin")
    return top


def _read_arg(name: str) -> str:
    return sys.stdin.read() if name == "-" else Path(name).read_text(encoding="utf-8")


class Args(argparse.Namespace):
    """Typed view of every CLI option; options a command lacks keep these defaults."""

    cmd: str = ""
    project: Path = Path()
    filter: str = "all"
    url: str = ""
    confirmed_host: list[str] | None = None
    root: Path = Path("~/study")
    lang: str = ""
    version: str = ""
    ecosystem: str = ""
    name: str = ""
    plan: bool = False
    crate_commit: bool = False
    package: str = ""
    ls_remote: str = "-"
    tag: str | None = None
    branch: str | None = None
    registry_commit: str | None = None
    results: str = "-"


def dispatch(args: Args) -> dict[str, object]:  # noqa: PLR0911
    """Run one parsed command and return its JSON result."""
    confirmed = tuple(args.confirmed_host or ())
    if args.cmd == "scan":
        plain, skipped = scan_vetted(args.project)
        names = {str(d["name"]) for d in filter_deps(plain, args.filter)}
        kept = [d for d in plain if str(d["name"]) in names]
        gone = [d for d in skipped if args.filter in {"all", d["category"], d.get("name")}]
        return {"ok": True, "dependencies": kept, "skipped": gone}
    if args.cmd == "url":
        raw = sys.stdin.readline().strip() if args.url == "-" else args.url
        return {"ok": True, **normalize_url(raw, confirmed)}
    if args.cmd == "plan":
        entry = plan_entry(args.root, args.lang, args.url, args.version or None, confirmed)
        return {"ok": True, **entry}
    if args.cmd == "lookup":
        if args.plan:
            req = lookup_request(args.ecosystem, args.name, args.version)
            return {"ok": True, "command": req["display"]}
        found = lookup(args.ecosystem, args.name, args.version, crate_vcs=args.crate_commit)
        return {"ok": True, **found}
    if args.cmd == "resolve":
        return {"ok": True, **resolve(args.package, args.version, _read_arg(args.ls_remote))}
    if args.cmd == "clone":
        return {"ok": True, **clone_or_fetch(args.root, args.lang, args.url, confirmed)}
    if args.cmd == "worktree":
        if args.tag and args.branch:
            msg = "give --tag or --branch, not both"
            raise Refusal(msg)
        reg = args.registry_commit
        if reg and not SHA_RE.match(reg.lower()):
            msg = "registry commit is not a hex commit id"
            raise Refusal(msg)
        made = make_worktree(
            args.root,
            args.lang,
            args.url,
            version=args.version,
            tag=args.tag,
            branch=args.branch,
            registry_commit=reg,
        )
        return {"ok": True, **made}
    rows = [as_dict(row) for row in as_list(load_json(_read_arg(args.results)))]
    return {"ok": True, **report(rows)}


def main(argv: list[str] | None = None) -> int:
    """Entry point; returns the process exit code."""
    args = build_parser().parse_args(argv, namespace=Args())
    try:
        emit(dispatch(args))
    except (Refusal, ValueError, OSError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        emit({"ok": False, "error": str(exc)})
        return EXIT_REFUSED
    return 0


if __name__ == "__main__":
    sys.exit(main())
