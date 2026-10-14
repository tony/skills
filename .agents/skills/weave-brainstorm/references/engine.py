#!/usr/bin/env python3
"""Deterministic machinery shared by weave skills.

Each command prints one JSON object on stdout. Exit codes: 0 success, 1 a
reported failure (the JSON says why), 2 a usage error. Run
``engine.py <command> --help`` for arguments; ``engine.py --help`` lists them.
POSIX only: it needs ``git`` and process groups.

Commands: flags, detect, init, context, prompt, pass-dir, labels, dispatch,
judge-plan, judge-parse, panel-merge, worktrees, participant, claim, write, packet,
capture, adopt, commit, guard, stash-restore, update.
"""

# pyright: reportAny=false, reportExplicitAny=false, reportUnusedCallResult=false
from __future__ import annotations

import argparse
import concurrent.futures
import contextlib
import fcntl
import hashlib
import json
import os
import random
import re
import shlex
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
import typing as t
from datetime import datetime, timezone
from pathlib import Path

import closest_model  # pyright: ignore[reportImplicitRelativeImport]

if t.TYPE_CHECKING:
    from collections.abc import Callable, Collection, Generator, Mapping, Sequence

Json = dict[str, t.Any]

SCHEMA_VERSION = 1
MODES = ("fast", "balanced", "deep")
MODE_TIMEOUT = {"fast": 0.5, "balanced": 1.0, "deep": 1.5}
WORKERS = ("subagents", "model-clis")
MAX_PASSES = 5
MAX_VARIANTS = 3
TIMEOUT_GROWTH = 1.5
RATE_LIMIT_WAIT = 10.0
GUARD_REFS = "refs/weave-guard"
RECOVERY_PREFIX = "pre-reset-"
STATE_DIR = "guard-state"
STATE_LIMIT = 100
STATE_IGNORED_REFS = ("refs/weave-guard/", "refs/stash", "refs/heads/weave/")
CHECK_SCOPE: Json = {
    "checked": [
        "files in the checkout that git does not ignore (content and mode)",
        "HEAD, branches, tags, packed-refs, config, hook names and hashes, the index",
        "targets of tracked symlinks (file hash, or name/size/mtime of a directory's top level)",
        "device, inode and link count of hard-linked tracked files",
        "names of ignored paths, with fully ignored directories counted as one entry",
    ],
    "not_checked": [
        "contents of ignored files and of anything inside an ignored directory",
        "writes outside the repository and outside symlink targets",
        (
            "writes through a relative tracked symlink that leaves the checkout, made from a"
            " participant snapshot: it resolves to a different place there, in directories the"
            " engine itself rewrites, so no stable before/after state exists"
            " (see unverified_symlinks)"
        ),
    ],
}
NEEDS_COMMIT = frozenset({"execute", "prompt", "architecture", "review", "fix-review"})

_DESLOP = ("no-deslop", "quiet-deslop", "verbose-deslop")


class Profile(t.NamedTuple):
    """Per-command flag defaults.

    ``passes`` and ``variants`` hold the fast, balanced, and deep preset values;
    ``None`` means the command has no such flag. ``reserved`` flags are stripped
    and reported instead of applied.
    """

    timeout: int
    passes: tuple[int, int, int] | None = None
    variants: tuple[int, int, int] | None = None
    judges: tuple[str, ...] = ()
    booleans: tuple[str, ...] = ()
    reserved: tuple[str, ...] = ()


PROFILES: dict[str, Profile] = {
    "ask": Profile(450, passes=(1, 1, 2), booleans=("cascade", *_DESLOP)),
    "review": Profile(900, passes=(1, 1, 2), booleans=("cascade", *_DESLOP)),
    "plan": Profile(600, passes=(1, 1, 2), booleans=_DESLOP),
    "architecture": Profile(1200, passes=(1, 1, 2)),
    "execute": Profile(1200, passes=(1, 1, 2)),
    "prompt": Profile(600, passes=(1, 1, 2)),
    "fix-review": Profile(0),
    "brainstorm": Profile(450, variants=(1, 1, 2)),
    "refine": Profile(450, passes=(1, 2, 3), judges=("host", "round-robin"), booleans=_DESLOP),
    "brainstorm-and-refine": Profile(
        450,
        passes=(1, 2, 3),
        variants=(1, 1, 2),
        judges=("host", "round-robin"),
        booleans=_DESLOP,
    ),
    "serene-bliss": Profile(
        450, passes=(1, 2, 3), booleans=_DESLOP, reserved=("variants", "preamble", "judge")
    ),
}

ROLES = {
    "maintainer": (
        "You are the Maintainer. Prioritize correctness, convention adherence, and minimal"
        " scope. Challenge any change that isn't strictly necessary. Enforce all project"
        " conventions from CLAUDE.md/AGENTS.md."
    ),
    "skeptic": (
        "You are the Skeptic. Challenge every assumption. Find edge cases, failure modes,"
        " and unstated requirements. Question whether the proposed approach is even the right"
        " one. Prioritize what could go wrong."
    ),
    "builder": (
        "You are the Builder. Prioritize practical, shippable solutions. Favor simplicity over"
        " abstraction. Focus on what gets the job done with the least complexity. Call out"
        " over-engineering."
    ),
}
LANE_ROLES = {"claude": "maintainer", "agy": "skeptic", "gpt": "builder"}
HOST_LANES = ("claude", *ROLES)

VARIANT_DIRECTIVE = (
    "Think through the problem step-by-step and consider multiple angles before producing"
    " your final response."
)
VARIANT_PREAMBLES = {
    1: "Take the most conventional, well-established approach.",
    2: "Take an unconventional or creative approach. Challenge the obvious solution.",
    3: "Take a contrarian approach. Question the premise itself.",
}

HARDEN_EXTERNAL = (
    "---\nCRITICAL: Do NOT write, edit, create, or delete any files. Do NOT use any\n"
    "file-writing or file-modification tools. This is a READ-ONLY research task.\n"
    "All output must go to stdout. Any file modifications will be detected and\n"
    "reported to the user.\n"
)
HARDEN_HOST = (
    "---\nCRITICAL: Do NOT write, edit, create, or delete any files in the repository.\n"
    "Do NOT use Write, Edit, or Bash commands that modify repository files. All\n"
    "session artifacts are written to the session directory, which is outside the\n"
    "repository. This is a READ-ONLY research task.\n"
)


class Step(t.NamedTuple):
    """One lane step: an executable and how to choose its model.

    ``template`` is a ``closest_model.newest`` template resolved against the
    executable's live listing; ``fallback`` is the pinned model used when the
    listing fails or matches nothing. A step with no template runs the
    executable's default model.
    """

    exe: str
    fallback: str | None
    template: str | None = None
    exclude: tuple[str, ...] = ()
    label: bool = False


# Fallback order per external lane. A step whose executable is missing is
# skipped, so the last entry is the lesser-model fallback.
LANES: dict[str, tuple[Step, ...]] = {
    "agy": (
        Step("agy", "Gemini 3.1 Pro (High)", "gemini-{v}-pro-high", label=True),
        Step("agent", "gemini-3.1-pro", "gemini-{v}-pro"),
        Step("agy", "Gemini 3.8 Flash (High)", "gemini-{v}-flash-high", label=True),
    ),
    "gpt": (
        Step("codex", None),
        Step("agent", "gpt-5.4-high", "gpt-{v}-*high", ("mini", "xhigh")),
        Step("agent", "gpt-5.4-mini-medium", "gpt-{v}-mini-medium"),
    ),
}
LIST_COMMANDS = {"agy": ("agy", "models"), "agent": ("agent", "--list-models")}
LIST_TIMEOUT = 20

CREDIT_PATTERNS = (
    "RESOURCE_EXHAUSTED",
    "quota exceeded",
    "quota_exceeded",
    "insufficient_quota",
    "exceeded your current quota",
    r"billing (?:limit|error|issue)",
    "capacity exhausted",
    r"hit your usage limit|usage limit (?:reached|exceeded)",
    r"(?<![\w:.])429(?![\w:.,]).*daily limit",
)
CREDIT_RE = re.compile("|".join(CREDIT_PATTERNS), re.IGNORECASE)
RATE_RE = re.compile(r"rate.?limit|too many requests|\b429\b", re.IGNORECASE)
_FLAG_RE = re.compile(r"""--([a-z][a-z-]*)(?:=("[^"]*"|'[^']*'|\S*))?(?!\S)""")


class EngineError(Exception):
    """A failure the caller should see as ``{"ok": false, "error": ...}``."""


def stamp() -> str:
    """Return the current UTC time as ``YYYY-MM-DDTHH:MM:SSZ``."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def emit(doc: Json) -> None:
    """Print a JSON document on stdout; escape text that is not valid UTF-8."""
    text = json.dumps(doc, indent=2, ensure_ascii=False)
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        text = json.dumps(doc, indent=2, ensure_ascii=True)
    print(text)


def git_bytes(
    top: str | Path,
    *args: str,
    check: bool = True,
    env: Mapping[str, str] | None = None,
    stdin: bytes | None = None,
) -> bytes:
    """Run ``git -C top ...`` and return raw stdout; no decoding, nothing stripped."""
    proc = subprocess.run(  # noqa: S603
        ["git", "-C", str(top), *args],  # noqa: S607
        capture_output=True,
        input=stdin,
        check=False,
        env={**os.environ, **env} if env else None,
    )
    if check and proc.returncode != 0:
        err = proc.stderr.decode("utf-8", "replace").strip()
        msg = f"git {' '.join(args)}: {err}"
        raise EngineError(msg)
    return proc.stdout


def git(
    top: str | Path, *args: str, check: bool = True, env: Mapping[str, str] | None = None
) -> str:
    """Run ``git -C top ...`` and return stdout minus trailing newlines.

    Undecodable bytes become surrogate escapes, so path names round-trip.

    >>> git(".", "--version").startswith("git version")
    True
    """
    out = git_bytes(top, *args, check=check, env=env)
    return out.decode("utf-8", "surrogateescape").rstrip("\n")


def git_z(top: str | Path, *args: str, env: Mapping[str, str] | None = None) -> list[str]:
    """Run git with ``-z`` output and return its NUL-separated fields."""
    return [p for p in git(top, *args, env=env).split("\0") if p]


def claim_path(path: Path, root: Path | None = None) -> Path:
    """Make ``path`` safe to create without reaching another file.

    A symlink, a hard-linked file, or a special file already at ``path`` is
    removed (what it pointed to is untouched). A symlinked parent is refused,
    checking every parent below ``root`` when ``path`` lies under it.
    """
    parents = [path.parent]
    if root is not None and root in path.parents:
        parents = [p for p in path.parents if root in p.parents]
    for parent in parents:
        if parent.is_symlink():
            msg = f"refusing to write through symlinked directory {str(parent)!r}"
            raise EngineError(msg)
    try:
        info = path.lstat()
    except FileNotFoundError:
        return path
    if stat.S_ISDIR(info.st_mode):
        msg = f"refusing to replace directory {str(path)!r}"
        raise EngineError(msg)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink > 1:
        path.unlink()
    return path


def write_atomic(path: Path, data: str | bytes, root: Path | None = None) -> None:
    """Write ``data`` to ``path`` through a new temporary file and a rename.

    The rename replaces a symlink or hard link at ``path`` instead of writing through it.
    """
    claim_path(path, root)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{random.randbytes(3).hex()}.tmp")
    payload = data.encode("utf-8") if isinstance(data, str) else data
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    with os.fdopen(os.open(tmp, flags, 0o666), "wb") as fh:
        fh.write(payload)
    tmp.replace(path)


def copy_owned(src: Path, dest: Path, root: Path | None = None) -> None:
    """Copy ``src`` to a fresh ``dest`` (a symlink is copied as a symlink)."""
    claim_path(dest, root)
    dest.parent.mkdir(parents=True, exist_ok=True)
    claim_path(dest, root)
    shutil.copy2(src, dest, follow_symlinks=False)


@contextlib.contextmanager
def session_lock(session_dir: Path) -> Generator[None]:
    """Serialize read-modify-write updates of ``session.json`` across processes."""
    session_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    with claim_path(session_dir / ".lock").open("a", encoding="utf-8") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def append_jsonl(path: Path, doc: Json) -> None:
    """Append one JSON line to ``path``."""
    with claim_path(path).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(doc, ensure_ascii=False) + "\n")


def aip_root(env: Mapping[str, str] | None = None, platform: str | None = None) -> Path:
    """Resolve the session storage root.

    >>> print(aip_root({"AI_AIP_ROOT": "/x", "XDG_STATE_HOME": "/s"}, "linux"))
    /x
    >>> print(aip_root({"XDG_STATE_HOME": "/s"}, "darwin"))
    /s/ai-aip
    >>> print(aip_root({"HOME": "/h"}, "darwin"))
    /h/Library/Application Support/ai-aip
    >>> print(aip_root({"HOME": "/h"}, "linux"))
    /h/.local/state/ai-aip
    """
    env = os.environ if env is None else env
    platform = sys.platform if platform is None else platform
    if env.get("AI_AIP_ROOT"):
        return Path(env["AI_AIP_ROOT"])
    if env.get("XDG_STATE_HOME"):
        return Path(env["XDG_STATE_HOME"]) / "ai-aip"
    home = Path(env["HOME"]) if env.get("HOME") else Path.home()
    if platform == "darwin":
        return home / "Library" / "Application Support" / "ai-aip"
    return home / ".local" / "state" / "ai-aip"


def repo_identity(toplevel: str, origin: str) -> tuple[str, str, str]:
    """Return ``(slug, id, dir_name)`` for a repository.

    >>> slug, rid, name = repo_identity("/w/My Repo", "")
    >>> slug, len(rid), name == f"{slug}--{rid}"
    ('my-repo', 12, True)
    >>> repo_identity("/a/x", "u")[1] == repo_identity("/b/x", "u")[1]
    True
    """
    slug = re.sub(r"[^a-z0-9._-]", "-", Path(toplevel).name.lower())
    key = f"{origin}|{slug}" if origin else toplevel
    rid = hashlib.sha256(key.encode()).hexdigest()[:12]
    return slug, rid, f"{slug}--{rid}"


def _extract_flags(text: str, prof: Profile) -> tuple[str, dict[str, str], Json]:
    """Consume the leading block of flags; return prompt, values, and the rest.

    The block ends at the first token that is not one of the command's flags, or
    at a bare ``--``. Everything after it is the prompt, flag-like words included.
    """
    allowed = {"timeout", "mode", "workers"}
    if prof.passes:
        allowed.add("passes")
    if prof.variants:
        allowed |= {"variants", "preamble"}
    if prof.judges:
        allowed.add("judge")
    values: dict[str, str] = {}
    found: Json = {"flags": [], "reserved": [], "errors": []}
    pos = 0
    while True:
        while pos < len(text) and text[pos].isspace():
            pos += 1
        if text.startswith("--", pos) and text[pos + 2 : pos + 3] in ("", " ", "\t", "\n"):
            pos += 2
            break
        m = _FLAG_RE.match(text, pos)
        if not m:
            break
        name, val = m.group(1), m.group(2)
        if val and len(val) >= 2 and val[0] in "\"'" and val[-1] == val[0]:  # noqa: PLR2004
            val = val[1:-1]
        if name in prof.reserved:
            found["reserved"].append(name)
        elif name in allowed:
            if val is None:
                found["errors"].append(f"--{name} needs a value")
            else:
                values[name] = val
        elif name in prof.booleans and val is None:
            found["flags"].append(name)
        else:
            break
        pos = m.end()
    return text[pos:].strip(), values, found


def parse_flags(text: str, command: str, *, default_timeout: int | None = None) -> Json:
    """Split a command's leading ``--name[=value]`` flags from its prompt.

    Only the command's own flags at the start are consumed; the first other
    token, or a bare ``--``, begins the prompt, so flag-like words inside the
    prompt are never touched. A value may be quoted to hold spaces.

    >>> doc = parse_flags("--mode=deep why is it slow", "ask")
    >>> doc["prompt"], doc["passes"], doc["timeout"], doc["mode"]
    ('why is it slow', 2, 675, 'deep')
    >>> parse_flags("tool --mode=fast --timeout=30", "refine")["prompt"]
    'tool --mode=fast --timeout=30'
    >>> parse_flags("-- --mode=fast is a flag", "ask")["prompt"]
    '--mode=fast is a flag'
    >>> doc = parse_flags("--passes=9 --timeout=none --cascade q", "ask")
    >>> doc["prompt"], doc["passes"], doc["timeout"], doc["flags"], doc["notes"]
    ('q', 5, 'none', ['cascade'], ['--passes capped at 5'])
    >>> doc = parse_flags("--passes=3 --mode=fast q", "execute")
    >>> doc["passes"], doc["timeout"], doc["timeout_menu"]
    (3, 600, {'quick': 600, 'default': 1200, 'long': 1800})
    >>> parse_flags("--workers=gpu --passes=x q", "ask")["errors"]
    ['--workers must be subagents or model-clis', '--passes must be an integer >= 1']
    >>> parse_flags("--cascade as-is", "execute")["prompt"]
    '--cascade as-is'
    >>> doc = parse_flags('--variants=2 --preamble="be bold" --judge=round-robin x', "brainstorm-and-refine")
    >>> doc["variants"], doc["preamble"], doc["judge"], doc["passes_recommended"]
    (2, 'be bold', 'round-robin', 2)
    >>> parse_flags("--variants=4 --judge=panel x", "serene-bliss")["reserved"]
    ['variants', 'judge']
    """  # noqa: E501
    if command not in PROFILES:
        msg = f"unknown command {command!r}; known: {', '.join(PROFILES)}"
        raise EngineError(msg)
    prof = PROFILES[command]
    base = default_timeout or prof.timeout
    prompt, values, found = _extract_flags(text, prof)
    errors: list[str] = found["errors"]
    notes: list[str] = []
    if found["reserved"]:
        notes.append("ignored reserved flags: " + ", ".join(f"--{r}" for r in found["reserved"]))

    mode = values.get("mode")
    if mode is not None and mode not in MODES:
        errors.append("--mode must be fast, balanced, or deep")
        mode = None
    workers = values.get("workers")
    if workers is not None and workers not in WORKERS:
        errors.append("--workers must be subagents or model-clis")
        workers = None
    judge = values.get("judge")
    if judge is not None and judge not in prof.judges:
        errors.append(f"--judge must be {' or '.join(prof.judges)}")
        judge = None
    if prof.judges and judge is None:
        judge = "host"

    def counted(name: str, table: tuple[int, int, int] | None, cap: int) -> int | None:
        if not table:
            return None
        if name not in values:
            return table[MODES.index(mode)] if mode else None
        raw = values[name]
        if not (raw.isdecimal() and int(raw) >= 1):
            errors.append(f"--{name} must be an integer >= 1")
            return None
        if int(raw) > cap:
            notes.append(f"--{name} capped at {cap}")
        return min(int(raw), cap)

    timeout: int | str | None = round(base * MODE_TIMEOUT[mode]) if mode else None
    if "timeout" in values:
        if values["timeout"] == "none":
            timeout = "none"
        elif values["timeout"].isdecimal() and int(values["timeout"]) > 0:
            timeout = int(values["timeout"])
        else:
            errors.append("--timeout must be a positive integer or none")

    return {
        "prompt": prompt,
        "passes": counted("passes", prof.passes, MAX_PASSES),
        "variants": counted("variants", prof.variants, MAX_VARIANTS),
        "passes_recommended": prof.passes[1] if prof.passes else None,
        "variants_recommended": prof.variants[1] if prof.variants else None,
        "timeout": timeout,
        "mode": mode,
        "workers": workers,
        "judge": judge,
        "preamble": values.get("preamble"),
        "flags": found["flags"],
        "reserved": found["reserved"],
        "timeout_menu": {
            "quick": round(base * MODE_TIMEOUT["fast"]),
            "default": base,
            "long": round(base * MODE_TIMEOUT["deep"]),
        },
        "notes": notes,
        "errors": errors,
    }


def list_models(exe: str) -> list[str] | None:
    """Return the lines ``exe`` lists its models on, or None when it cannot list them.

    Runs outside the user's checkout so a listing can never touch it.
    """
    argv = LIST_COMMANDS.get(exe)
    if argv is None:
        return None
    try:
        proc = subprocess.Popen(  # noqa: S603
            argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, cwd=tempfile.gettempdir(), start_new_session=True,
        )  # fmt: skip
    except OSError:
        return None
    try:
        out, _ = proc.communicate(timeout=LIST_TIMEOUT)
    except subprocess.TimeoutExpired:
        # A child holding the pipe would outlive a plain kill of the CLI.
        os.killpg(proc.pid, signal.SIGKILL)
        _ = proc.communicate()
        return None
    return out.splitlines() if proc.returncode == 0 else None


def resolve_step(step: Step, listing: Sequence[str] | None) -> tuple[str | None, str]:
    """Return ``(model, source)`` for a step; source is live, pinned, or default.

    >>> resolve_step(Step("agent", "gpt-5.4-high", "gpt-{v}-high"), ["gpt-5.5-high - G"])
    ('gpt-5.5-high', 'live')
    >>> resolve_step(Step("agent", "gpt-5.4-high", "gpt-{v}-high"), [])
    ('gpt-5.4-high', 'pinned')
    >>> resolve_step(Step("codex", None), None)
    (None, 'default')
    """
    if step.template is None:
        return step.fallback, "default"
    picked = closest_model.newest(
        step.template, list(listing or ()), step.exclude, label=step.label
    )
    return (picked, "live") if picked else (step.fallback, "pinned")


def lane_chain(
    lane: str,
    which: Callable[[str], str | None] = shutil.which,
    lister: Callable[[str], list[str] | None] | None = None,
) -> list[tuple[str, str | None, str]]:
    """Return the installed ``(executable, model, source)`` steps for an external lane.

    Without a ``lister`` every step keeps its pinned model; ``detect`` passes
    one so a session resolves each model once from the CLI's live listing.

    >>> agent_only = lambda n: "/bin/agent" if n == "agent" else None
    >>> lane_chain("gpt", agent_only)
    [('agent', 'gpt-5.4-high', 'pinned'), ('agent', 'gpt-5.4-mini-medium', 'pinned')]
    >>> models = ["gpt-5.6-sol-high - S", "gpt-5.7-mini-high - M", "gpt-5.4-mini-medium - M"]
    >>> live = lambda exe: models
    >>> [(m, src) for _, m, src in lane_chain("gpt", agent_only, live)]
    [('gpt-5.6-sol-high', 'live'), ('gpt-5.4-mini-medium', 'live')]
    """
    listings: dict[str, list[str] | None] = {}
    chain: list[tuple[str, str | None, str]] = []
    for step in LANES[lane]:
        if not which(step.exe):
            continue
        if lister is not None and step.template and step.exe not in listings:
            listings[step.exe] = lister(step.exe)
        model, source = resolve_step(step, listings.get(step.exe))
        chain.append((step.exe, model, source))
    return chain


def detect(
    which: Callable[[str], str | None] = shutil.which,
    lister: Callable[[str], list[str] | None] | None = list_models,
) -> Json:
    """Report installed model CLIs, each lane's resolved chain, and the best search tools.

    Each installed CLI is listed once, all at the same time, so a session waits at
    most one ``LIST_TIMEOUT``.
    """
    exes = sorted({s.exe for steps in LANES.values() for s in steps if s.template and which(s.exe)})
    listings: dict[str, list[str] | None] = {}
    if lister is not None and exes:
        with concurrent.futures.ThreadPoolExecutor(len(exes)) as pool:
            listings = dict(zip(exes, pool.map(lister, exes)))
    lanes: Json = {}
    for lane in LANES:
        chain = lane_chain(lane, which, listings.get if lister is not None else None)
        lanes[lane] = (
            {
                "executor": chain[0][0],
                "model": chain[0][1],
                "source": chain[0][2],
                "chain": [list(s) for s in chain],
            }
            if chain
            else None
        )
    return {
        "clis": {exe: bool(which(exe)) for exe in ("agy", "codex", "agent")},
        "lanes": lanes,
        "search": {
            "content": next((x for x in ("rg", "ag", "grep") if which(x)), "grep"),
            "files": next((x for x in ("fd", "find") if which(x)), "find"),
        },
    }


def build_roster(backend: str, detected: Json | None = None) -> tuple[list[str], Json, list[str]]:
    """Return ``(participants, executors, models)`` for a worker backend.

    >>> build_roster("subagents")[0]
    ['maintainer', 'skeptic', 'builder']
    >>> det = {"lanes": {"agy": None, "gpt": {"executor": "codex", "model": None}}}
    >>> build_roster("model-clis", det)
    (['claude', 'gpt'], {'claude': 'host', 'gpt': 'codex'}, ['gpt: default'])
    >>> det = {"lanes": {"agy": None, "gpt": {"executor": "agent", "model": "m", "source": "live"}}}
    >>> build_roster("model-clis", det)[2]
    ['gpt: m [live]']
    """
    if backend == "subagents":
        names = list(ROLES)
        return names, dict.fromkeys(names, "host-native"), []
    detected = detect() if detected is None else detected
    participants = ["claude"]
    executors: Json = {"claude": "host"}
    models: list[str] = []
    for lane in LANES:
        found = detected["lanes"][lane]
        if found:
            participants.append(lane)
            executors[lane] = found["executor"]
            model = found["model"]
            models.append(f"{lane}: {model} [{found['source']}]" if model else f"{lane}: default")
    return participants, executors, models


def load_session(session_dir: str | Path) -> Json:
    """Read ``session.json``."""
    path = Path(session_dir) / "session.json"
    if not path.is_file():
        msg = f"no session.json in {session_dir}"
        raise EngineError(msg)
    return t.cast("Json", json.loads(path.read_text(encoding="utf-8")))


def save_session(session_dir: Path, doc: Json) -> None:
    """Replace ``session.json`` and refresh ``updated_at``."""
    doc["updated_at"] = stamp()
    write_atomic(session_dir / "session.json", json.dumps(doc, indent=2) + "\n")


def pass_name(n: int) -> str:
    """Return the pass directory name.

    >>> pass_name(2)
    'pass-0002'
    """
    return f"pass-{n:04d}"


def make_pass_dir(session_dir: Path, n: int, *, mutating: bool) -> Path:
    """Create ``pass-NNNN`` with its output subdirectories (mode 700)."""
    base = session_dir / pass_name(n)
    subdirs = ["outputs", "stderr", "prompts"] + (["diffs", "files"] if mutating else [])
    for sub in subdirs:
        (base / sub).mkdir(mode=0o700, parents=True, exist_ok=True)
    return base


def detect_trunk(top: str | Path) -> str:
    """Return the trunk branch: ``origin/HEAD``, else ``main``, else ``master``."""
    ref = git(top, "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD", check=False)
    if ref.startswith("origin/"):
        return ref[len("origin/") :]
    for name in ("main", "master"):
        if git(top, "rev-parse", "--verify", "--quiet", f"refs/heads/{name}", check=False):
            return name
    return "main"


def baseline_sha(top: str | Path, trunk: str) -> str:
    """Return the trunk commit used for tone calibration: origin/trunk, trunk, or HEAD."""
    for ref in (f"origin/{trunk}", trunk, "HEAD"):
        sha = git(top, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}", check=False)
        if sha:
            return sha
    return ""


def unsafe_toplevel(top: str | Path, env: Mapping[str, str] | None = None) -> str | None:
    """Say why ``top`` must never be snapshotted, stashed, or given worktrees.

    A checkout rooted at the filesystem root, at ``$HOME``, or at a directory
    that contains ``$HOME`` would pull a whole home tree into the object store.

    >>> unsafe_toplevel("/")
    'the filesystem root'
    >>> unsafe_toplevel("/home/u", {"HOME": "/home/u"})
    'your home directory'
    >>> unsafe_toplevel("/home", {"HOME": "/home/u"})
    'a directory that contains your home directory'
    >>> unsafe_toplevel("/home/u/proj", {"HOME": "/home/u"}) is None
    True
    """
    env = os.environ if env is None else env
    real = Path(top).resolve()
    if real == Path(real.anchor):
        return "the filesystem root"
    try:
        home = (Path(env["HOME"]) if env.get("HOME") else Path.home()).resolve()
    except RuntimeError:
        return None
    if real == home:
        return "your home directory"
    if real in home.parents:
        return "a directory that contains your home directory"
    return None


def require_safe_toplevel(top: str | Path) -> None:
    """Raise unless ``top`` is a toplevel the engine may snapshot or stash."""
    why = unsafe_toplevel(top)
    if why:
        msg = f"refusing to snapshot, stash, or add worktrees to {why}; run from a project checkout"
        raise EngineError(msg)


class RepoInfo(t.NamedTuple):
    """Where a command runs: ``git`` is false when no usable repository exists."""

    top: str
    git: bool
    reason: str | None = None


def resolve_repo(repo: str) -> RepoInfo:
    """Find the repository at ``repo``, or explain why the command runs without one.

    A directory that is not a repository, a repository with no commits, and an
    unsafe toplevel all run in no-repo mode, rooted at the real path of ``repo``.
    """
    here = Path(repo).resolve()
    if not here.is_dir():
        msg = f"{repo} is not a directory"
        raise EngineError(msg)
    top = git(here, "rev-parse", "--show-toplevel", check=False)
    if not top:
        return RepoInfo(str(here), git=False, reason="this directory is not a git repository")
    if not git(top, "rev-parse", "--verify", "--quiet", "HEAD^{commit}", check=False):
        return RepoInfo(str(here), git=False, reason="this repository has no commits")
    why = unsafe_toplevel(top)
    if why:
        return RepoInfo(str(here), git=False, reason=f"the repository toplevel is {why}")
    return RepoInfo(str(Path(top).resolve()), git=True)


def compare_base(top: str | Path, trunk: str) -> str | None:
    """Return the ref to diff against: ``origin/<trunk>``, else the local trunk, else ``None``."""
    for ref in (f"origin/{trunk}", trunk):
        if git(top, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}", check=False):
            return ref
    return None


# --- repo guard -----------------------------------------------------------


def snapshot_tree(top: str | Path, *, paths: Sequence[str] | None = None) -> str:
    """Return the tree of the working directory without touching the user's index.

    Tracked changes, deletions, and untracked non-ignored files are all included.
    Rebuild a temporary index without stat-cache or shortcut flags so live
    edits cannot hide behind assume-unchanged or skip-worktree entries.
    ``paths`` limits observation to literal paths, including their executable bits.
    """
    require_safe_toplevel(top)
    fd, name = tempfile.mkstemp(prefix="weave-index-")
    os.close(fd)
    env = {"GIT_INDEX_FILE": name}
    try:
        pathspec = ["--", *paths] if paths is not None else []
        entries = (
            git_bytes(top, "--literal-pathspecs", "ls-files", "--stage", "-z", *pathspec)
            if paths is None or paths
            else b""
        )
        git(top, "read-tree", "--empty", env=env)
        git_bytes(top, "update-index", "-z", "--index-info", stdin=entries, env=env)
        add_paths = ["."]
        mode_config: list[str] = []
        if paths is not None:
            tracked = {
                item.partition("\t")[2]
                for item in entries.decode("utf-8", "surrogateescape").split("\0")
                if item
            }
            add_paths = [
                path for path in paths
                if path in tracked or (Path(top) / path).is_symlink() or (Path(top) / path).exists()
            ]  # fmt: skip
            mode_config = ["-c", "core.filemode=true"]
        if add_paths:
            git(
                top, "--literal-pathspecs", "-c", "core.sparseCheckout=false", *mode_config,
                "add", "-A", "--", *add_paths, env=env,
            )  # fmt: skip
        return git(top, "write-tree", env=env)
    finally:
        Path(name).unlink(missing_ok=True)


def pin_tree(top: str | Path, session_id: str, name: str, tree: str, parent: str) -> str:
    """Commit ``tree`` over ``parent`` and pin it as ``refs/weave-guard/<session>/<name>``."""
    commit = git(
        top,
        "-c",
        "user.name=weave",
        "-c",
        "user.email=weave@localhost",
        "commit-tree",
        tree,
        "-p",
        parent,
        "-m",
        f"weave guard {name} snapshot",
    )
    git(top, "update-ref", f"{GUARD_REFS}/{session_id}/{name}", commit)
    return commit


def _index_state(top: str | Path) -> str:
    return hashlib.sha256(git_bytes(top, "ls-files", "--stage", "-v", "-z")).hexdigest()


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _target_state(link: Path) -> str:
    """Describe what a symlink currently reaches: a file hash, a directory listing, or nothing."""
    real = os.path.realpath(link)
    try:
        info = Path(real).stat()
    except OSError:
        return f"missing:{real}"
    if stat.S_ISREG(info.st_mode):
        try:
            return f"file:{real}:{_file_digest(Path(real))}"
        except OSError:
            return f"file:{real}:unreadable:{info.st_size}:{info.st_mtime_ns}"
    if stat.S_ISDIR(info.st_mode):
        digest = hashlib.sha256()
        with os.scandir(real) as entries:
            for entry in sorted(entries, key=lambda e: e.name):
                with contextlib.suppress(OSError):
                    st = entry.stat(follow_symlinks=False)
                    digest.update(f"{entry.name}\0{st.st_size}\0{st.st_mtime_ns}\n".encode())
        return f"dir:{real}:{digest.hexdigest()}"
    return f"other:{real}"


def collect_state(top: str | Path) -> Json:
    """Return what a worker can change outside the working-tree snapshot.

    Each category maps a name to a short fingerprint, so two states diff to names.
    """
    refs: dict[str, str] = {}
    fmt = "%(refname)%00%(objectname)%00%(symref)"
    for line in git(top, "for-each-ref", f"--format={fmt}").splitlines():
        name, obj, sym = line.split("\0")
        if not name.startswith(STATE_IGNORED_REFS):
            refs[name] = sym or obj
    names = ("packed-refs", "config", "config.worktree", "hooks")
    where = dict(
        zip(
            names,
            git(top, "rev-parse", *[a for n in names for a in ("--git-path", n)]).splitlines(),
        )
    )
    packed: dict[str, str] = {}
    packed_file = Path(top) / where["packed-refs"]
    if packed_file.is_file():
        for line in packed_file.read_text(encoding="utf-8", errors="replace").splitlines():
            obj, _, name = line.partition(" ")
            if name and not line.startswith(("#", "^")) and not name.startswith(STATE_IGNORED_REFS):
                packed[name] = obj
    config: dict[str, str] = {}
    for name in ("config", "config.worktree"):
        path = Path(top) / where[name]
        if path.is_file():
            config[name] = _file_digest(path)
    hooks: dict[str, str] = {}
    hooks_dir = Path(top) / where["hooks"]
    if hooks_dir.is_dir():
        for hook in sorted(hooks_dir.iterdir()):
            if hook.is_file():
                hooks[hook.name] = _file_digest(hook)
    symlinks: dict[str, str] = {}
    hardlinks: dict[str, str] = {}
    entries = git_bytes(top, "ls-files", "--stage", "-z").decode("utf-8", "surrogateescape")
    for entry in entries.split("\0"):
        meta, _, rel = entry.partition("\t")
        mode = meta.partition(" ")[0]
        if mode == "120000":
            symlinks[rel] = _target_state(Path(top) / rel)
        elif mode in {"100644", "100755"}:
            try:
                info = (Path(top) / rel).lstat()
            except OSError:
                continue
            if stat.S_ISREG(info.st_mode) and info.st_nlink > 1:
                hardlinks[rel] = f"{info.st_dev}:{info.st_ino}:{info.st_nlink}"
    listing = ("ls-files", "--others", "--ignored", "--exclude-standard", "--directory", "-z")
    ignored = dict.fromkeys(git_z(top, *listing), "")
    return {
        "refs": refs, "packed_refs": packed, "config": config, "hooks": hooks,
        "symlinks": symlinks, "hardlinks": hardlinks, "ignored": ignored,
    }  # fmt: skip


def escaping_symlinks(top: str | Path) -> list[str]:
    """List tracked relative symlinks that resolve outside the checkout.

    An absolute link resolves the same from a snapshot, and a link inside the repository
    is covered by the tree; these two resolve elsewhere from a snapshot.
    """
    found: list[str] = []
    entries = git_bytes(top, "ls-files", "--stage", "-z").decode("utf-8", "surrogateescape")
    for entry in entries.split("\0"):
        meta, _, rel = entry.partition("\t")
        if not meta.startswith("120000"):
            continue
        link = os.readlink(Path(top) / rel)  # noqa: PTH115
        if Path(link).is_absolute():
            continue
        reach = os.path.normpath(Path(rel).parent / link)
        if reach == ".." or reach.startswith("../"):
            found.append(rel)
    return found


def _scope(top: str | Path) -> Json:
    return {**CHECK_SCOPE, "unverified_symlinks": escaping_symlinks(top)}


def diff_state(
    pre: Mapping[str, Mapping[str, str]],
    post: Mapping[str, Mapping[str, str]],
    skip: Collection[str] = (),
) -> Json:
    """Return ``{category: [names]}`` for every name added, removed, or changed."""
    found: Json = {}
    for category, before in pre.items():
        after = post.get(category, {})
        names = sorted(
            n for n in {*before, *after} if before.get(n) != after.get(n) and n not in skip
        )
        if names:
            found[category] = names[:STATE_LIMIT] + (
                [f"... and {len(names) - STATE_LIMIT} more"] if len(names) > STATE_LIMIT else []
            )
    return found


def _save_state(session_dir: Path, name: str, state: Json) -> None:
    (session_dir / STATE_DIR).mkdir(mode=0o700, exist_ok=True)
    write_atomic(session_dir / STATE_DIR / f"{name}.json", json.dumps(state) + "\n", session_dir)


def _load_state(session_dir: Path, guard: Json) -> Json | None:
    name = guard.get("state")
    if not name:
        return None
    path = session_dir / STATE_DIR / f"{name}.json"
    return t.cast("Json", json.loads(path.read_text(encoding="utf-8"))) if path.is_file() else None


def _outside_changes(session_dir: Path, top: str, guard: Json, skip: Collection[str] = ()) -> Json:
    """Diff the current outside-the-tree state against the one recorded with ``guard``."""
    before = _load_state(session_dir, guard)
    return {} if before is None else diff_state(before, collect_state(top), skip)


def take_guard_snapshot(
    top: str, session_id: str, name: str = "pre", session_dir: Path | None = None
) -> Json:
    """Record the checkout as ``refs/weave-guard/<session>/pre``."""
    require_safe_toplevel(top)
    head = git(top, "rev-parse", "HEAD")
    tree = snapshot_tree(top)
    commit = pin_tree(top, session_id, name, tree, head)
    doc: Json = {
        "pre": commit,
        "tree": tree,
        "head": head,
        "index": _index_state(top),
        "head_ref": git(top, "symbolic-ref", "-q", "HEAD", check=False),
    }
    if session_dir is not None:
        _save_state(session_dir, name, collect_state(top))
        doc["state"] = name
    return doc


def _touched(top: str, pre_tree: str, post_tree: str) -> dict[str, str]:
    """Return ``{path: status}`` (``A``, ``M``, ``D``) between two trees."""
    fields = git_z(
        top, "diff-tree", "-r", "--no-renames", "--name-status", "-z", pre_tree, post_tree
    )
    return {path: status for status, path in zip(fields[0::2], fields[1::2])}


def _guard_of(session: Json) -> Json:
    guard = session.get("guard")
    if not guard:
        msg = "session has no guard snapshot"
        raise EngineError(msg)
    return t.cast("Json", guard)


def guard_check(session_dir: Path, label: str = "check", *, initial: bool = False) -> Json:
    """Compare the user's checkout with the pre-dispatch snapshot; never modify it.

    A difference is recorded under ``guard/<id>/``: ``touched.json``, ``outside.json``
    (state beyond the working tree, see ``CHECK_SCOPE``), ``violation.patch``,
    ``post-copy/`` (current content of every touched file), and a pinned post ref.
    """
    session = load_session(session_dir)
    if session.get("unguarded"):
        return {"ok": True, "violation": False, "unguarded": True}
    top = session["toplevel"]
    pre = session["initial_guard"] if initial else _guard_of(session)
    post_tree = snapshot_tree(top)
    head = git(top, "rev-parse", "HEAD")
    index = _index_state(top)
    head_ref = git(top, "symbolic-ref", "-q", "HEAD", check=False)
    index_changed = index != pre.get("index", index)
    head_changed = head != pre["head"] or head_ref != pre.get("head_ref", head_ref)
    outside = _outside_changes(session_dir, top, pre)
    if post_tree == pre["tree"] and not head_changed and not index_changed and not outside:
        return {"ok": True, "violation": False}
    current = {
        "tree": post_tree,
        "head": head,
        "index": index,
        "head_ref": head_ref,
        "baseline": pre["pre"],
        "outside": outside,
    }
    gdir = session_dir / "guard"
    gdir.mkdir(mode=0o700, exist_ok=True)
    last = gdir / "last.json"
    if last.is_file():
        seen = json.loads(last.read_text(encoding="utf-8"))
        if all(seen.get(key) == value for key, value in current.items()):
            return {**seen["result"], "repeat": True}
    vid = f"{label}-{datetime.now(timezone.utc).strftime('%H%M%S')}-{random.randbytes(2).hex()}"
    vdir = gdir / vid
    vdir.mkdir(mode=0o700)
    touched = _touched(top, pre["tree"], post_tree)
    write_atomic(vdir / "touched.json", json.dumps(touched, indent=2) + "\n", session_dir)
    write_atomic(vdir / "outside.json", json.dumps(outside, indent=2) + "\n", session_dir)
    patch = git_bytes(top, "diff", "--binary", "--no-renames", pre["tree"], post_tree)
    write_atomic(vdir / "violation.patch", patch, session_dir)
    entries = git_bytes(top, "ls-files", "--stage", "-v", "-z")
    write_atomic(vdir / "index-entries", entries, session_dir)
    for rel, status in touched.items():
        src = Path(top) / rel
        if status != "D" and (src.is_symlink() or src.is_file()):
            copy_owned(src, vdir / "post-copy" / rel, session_dir)
    pin_tree(top, session["session_id"], f"post-{vid}", post_tree, pre["pre"])
    result: Json = {
        "ok": True,
        "violation": True,
        "id": vid,
        "dir": str(vdir),
        "touched": touched,
        "head_changed": head_changed,
        "index_changed": index_changed,
        "outside": outside,
    }
    write_atomic(last, json.dumps({**current, "result": result}) + "\n", session_dir)
    append_jsonl(
        session_dir / "guard-events.jsonl",
        {
            "event": "repo_guard_violation",
            "timestamp": stamp(),
            "label": label,
            "id": vid,
            "touched": sorted(touched),
            "head_changed": head_changed,
            "index_changed": index_changed,
            "outside": outside,
            "reverted": False,
        },
    )
    note = (
        f"weave guard: {len(touched)} path(s) in your checkout"
        f" and {sum(len(v) for v in outside.values())} outside-tree item(s) differ"
        " from the snapshot"
    )
    print(
        f"{note} taken before dispatch (after {label}); nothing was changed. See {vdir}",
        file=sys.stderr,
    )
    return result


def _revert_paths(top: str, pre_tree: str, touched: Mapping[str, str]) -> None:
    """Restore modified and deleted paths from ``pre_tree``; remove paths it lacks."""
    root = Path(top)
    for rel, status in touched.items():
        if status == "A":
            target = root / rel
            if target.is_symlink() or target.is_file():
                target.unlink()
            parent = target.parent
            while parent != root:
                try:
                    parent.rmdir()
                except OSError:
                    break
                parent = parent.parent
    restore = [rel for rel, status in touched.items() if status != "A"]
    if not restore:
        return
    fd, name = tempfile.mkstemp(prefix="weave-index-")
    os.close(fd)
    env = {"GIT_INDEX_FILE": name}
    try:
        git(top, "read-tree", pre_tree, env=env)
        proc = subprocess.run(  # noqa: S603
            ["git", "-C", top, "checkout-index", "-f", "-z", "--stdin"],  # noqa: S607
            input=("\0".join(restore) + "\0").encode("utf-8", "surrogateescape"),
            capture_output=True,
            check=False,
            env={**os.environ, **env},
        )
        if proc.returncode != 0:
            msg = f"git checkout-index: {proc.stderr.decode('utf-8', 'replace').strip()}"
            raise EngineError(msg)
    finally:
        Path(name).unlink(missing_ok=True)


def guard_resolve(session_dir: Path, action: str) -> Json:
    """Apply the user's decision about a recorded checkout difference.

    ``keep`` leaves the tree as it is. ``revert`` restores only the touched
    paths from the pre snapshot and removes only paths absent from it.
    ``quarantine`` stashes everything under a named stash. All three first
    record the difference, so the post-run state stays recoverable.
    """
    session = load_session(session_dir)
    if session.get("unguarded"):
        return {"ok": True, "action": "none", "violation": False, "unguarded": True}
    top = session["toplevel"]
    pre_tree = _guard_of(session)["tree"]
    found = guard_check(session_dir, "resolve")
    if not found["violation"]:
        return {"ok": True, "action": "none", "violation": False}
    touched = found["touched"]
    doc: Json = {"ok": True, "action": action, "violation": True, "id": found["id"]}
    if action == "revert":
        _revert_paths(top, pre_tree, touched)
        doc["restored"] = sorted(p for p, s in touched.items() if s != "A")
        doc["removed"] = sorted(p for p, s in touched.items() if s == "A")
        doc["clean"] = snapshot_tree(top) == pre_tree and not found["outside"]
        if found["outside"]:
            doc["not_reverted"] = found["outside"]
    elif action == "quarantine":
        message = f"weave-guard-{session['session_id']}: quarantine"
        before = git(top, "rev-parse", "--quiet", "--verify", "refs/stash", check=False)
        git(top, "stash", "push", "--include-untracked", "-m", message)
        after = git(top, "rev-parse", "--quiet", "--verify", "refs/stash", check=False)
        if not after or after == before:
            msg = "git stash did not record the checkout; nothing was quarantined"
            raise EngineError(msg)
        doc["stash"] = {"sha": after, "message": message}
    elif action != "keep":
        msg = f"unknown action {action!r}"
        raise EngineError(msg)
    append_jsonl(
        session_dir / "guard-events.jsonl",
        {"event": "repo_guard_resolved", "timestamp": stamp(), "action": action, "id": found["id"]},
    )
    return doc


def require_drift_decision(session_dir: Path, command: str, *, acknowledge: bool) -> None:
    """Refuse ``command`` while a recorded guard violation has no user decision.

    ``acknowledge`` records the decision for the newest violation and lets the
    command run; a later, different violation needs its own acknowledgement.
    """
    last = session_dir / "guard" / "last.json"
    if not last.is_file():
        return
    vid = json.loads(last.read_text(encoding="utf-8"))["result"]["id"]
    ack = session_dir / "guard" / "ack.json"
    if ack.is_file() and json.loads(ack.read_text(encoding="utf-8")).get("id") == vid:
        return
    if not acknowledge:
        msg = (
            f"guard recorded drift {vid}; {command} would discard evidence."
            " Preserve the checkout and worktrees, tell the user, and rerun with --ack-drift"
            " only after they decide"
        )
        raise EngineError(msg)
    doc = {"id": vid, "command": command, "timestamp": stamp()}
    write_atomic(ack, json.dumps(doc) + "\n", session_dir)
    append_jsonl(session_dir / "guard-events.jsonl", {"event": "drift_acknowledged", **doc})


def _drop_session_refs(top: str, session_id: str) -> None:
    """Delete the session's transient pins, preserving existing recovery snapshots."""
    prefix = f"{GUARD_REFS}/{session_id}/"
    for ref in git(top, "for-each-ref", "--format=%(refname)", prefix).splitlines():
        if not ref.startswith(prefix + RECOVERY_PREFIX):
            git(top, "update-ref", "-d", ref)


def _unexpected_after_apply(session_dir: Path, top: str, session: Json) -> Json | None:
    """Return what differs from the original checkout beyond the adopted paths.

    ``None`` means the original state or the adopted paths were not recorded, so
    nothing can be said.
    """
    initial = session.get("initial_guard")
    applied = session.get("applied_paths")
    if not initial or applied is None:
        return None
    touched = _touched(top, initial["tree"], snapshot_tree(top))
    return {
        "touched": {rel: status for rel, status in touched.items() if rel not in applied},
        "outside": _outside_changes(Path(session_dir), top, initial, applied),
        "head_changed": git(top, "rev-parse", "HEAD") != initial["head"]
        or git(top, "symbolic-ref", "-q", "HEAD", check=False) != initial.get("head_ref"),
        "index_changed": _index_state(top) != initial.get("index"),
    }


def guard_finish(session_dir: Path) -> Json:
    """Run the last check, log ``repo_guard_final``, and drop the pinned refs when clean.

    An adopted session is compared with its original state, excluding the adopted paths.
    Existing recovery snapshots are always kept.
    """
    session = load_session(session_dir)
    top = session["toplevel"]
    if session.get("unguarded"):
        append_jsonl(
            session_dir / "events.jsonl",
            {"event": "repo_guard_final", "timestamp": stamp(), "repo_clean": None},
        )
        return {"ok": True, "clean": None, "unguarded": True, "refs_pruned": False, "touched": {}}
    if session.get("applied"):
        unexpected = _unexpected_after_apply(session_dir, top, session)
        clean = None if unexpected is None else not any(unexpected.values())
        event: Json = {"event": "repo_guard_final", "timestamp": stamp(), "repo_clean": clean}
        append_jsonl(session_dir / "events.jsonl", event)
        pruned = not (session_dir / "guard" / "last.json").exists()
        if pruned:
            _drop_session_refs(top, session["session_id"])
        found = unexpected or {"touched": {}}
        return {"ok": True, "clean": clean, "refs_pruned": pruned, **found, "scope": _scope(top)}
    if session.get("mutating") and not session.get("initial_guard"):
        return {
            "ok": False,
            "clean": None,
            "refs_pruned": False,
            "touched": {},
            "error": "no initial checkout snapshot; unchanged state cannot be verified",
        }
    found = guard_check(session_dir, "final", initial=bool(session.get("mutating")))
    clean = not found["violation"]
    event = {"event": "repo_guard_final", "timestamp": stamp(), "repo_clean": clean}
    append_jsonl(session_dir / "guard-events.jsonl", event)
    append_jsonl(session_dir / "events.jsonl", event)
    pruned = clean and not (session_dir / "guard" / "last.json").exists()
    if pruned:
        _drop_session_refs(top, session["session_id"])
    return {
        "ok": clean,
        "clean": clean,
        "refs_pruned": pruned,
        "touched": found.get("touched", {}),
        "head_changed": found.get("head_changed", False),
        "index_changed": found.get("index_changed", False),
        "outside": found.get("outside", {}),
        "scope": _scope(top),
    }


def guard_prune(repo: str, days: float) -> Json:
    """Delete pinned guard refs whose snapshot commit is older than ``days``."""
    top = git(repo, "rev-parse", "--show-toplevel", check=False)
    if not top:
        return {"ok": True, "dropped": []}
    cutoff = time.time() - days * 86400
    dropped: list[str] = []
    for line in git(
        top, "for-each-ref", "--format=%(refname) %(committerdate:unix)", GUARD_REFS
    ).splitlines():
        ref, _, when = line.partition(" ")
        if float(when) < cutoff:
            git(top, "update-ref", "-d", ref)
            dropped.append(ref)
    return {"ok": True, "dropped": dropped}


# --- sessions -------------------------------------------------------------


def stash_user_changes(top: str, command: str) -> Json:
    """Stash tracked and untracked changes; report whether a stash was made."""
    require_safe_toplevel(top)
    if not git(top, "status", "--porcelain"):
        return {"state": "none-needed"}
    message = f"weave-{command}: user-changes stash"
    before = git(top, "rev-parse", "--quiet", "--verify", "refs/stash", check=False)
    git(top, "stash", "push", "--include-untracked", "-m", message)
    after = git(top, "rev-parse", "--quiet", "--verify", "refs/stash", check=False)
    if not after or after == before:
        msg = "git stash did not record the user's changes; refusing to continue"
        raise EngineError(msg)
    return {"state": "stashed", "sha": after, "message": message}


def init_session(  # noqa: PLR0913
    *,
    command: str,
    backend: str | None,
    repo: str,
    prompt_summary: str,
    passes: int,
    timeout: str,
    mutating: bool,
    variants: int | None = None,
    bare: bool = False,
) -> Json:
    """Create a session directory, its metadata files, and the guard snapshot.

    A ``bare`` session has no workers and no guard snapshot, for commands that
    edit the repository themselves. A command that does not need commits runs
    in no-repo mode when the directory has no usable repository: no guard, and
    workers start in an empty scratch directory. A failed init leaves nothing behind.
    """
    if backend is None and not bare:
        msg = "init needs --backend unless --bare"
        raise EngineError(msg)
    info = resolve_repo(repo)
    if not info.git and (mutating or bare or command in NEEDS_COMMIT):
        msg = (
            f"{command} needs a git repository with at least one commit: {info.reason}."
            " Run it from a project checkout."
        )
        raise EngineError(msg)
    top = info.top
    origin = git(top, "remote", "get-url", "origin", check=False) if info.git else ""
    slug, rid, repo_dir = repo_identity(top, origin)
    root = aip_root()
    repo_path = root / "repos" / repo_dir
    session_id = (
        f"{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%SZ')}"
        f"-{os.getpid()}-{random.randbytes(2).hex()}"
    )
    session_dir = repo_path / "sessions" / command / session_id
    new_repo = not repo_path.exists()
    made: Json = {}
    try:
        return _build_session(
            session_dir=session_dir, repo_path=repo_path, info=info, origin=origin,
            slug=slug, rid=rid, repo_dir=repo_dir, root=root, session_id=session_id,
            command=command, backend=backend, prompt_summary=prompt_summary,
            passes=passes, timeout=timeout, mutating=mutating, variants=variants,
            bare=bare, made=made,
        )  # fmt: skip
    except BaseException:
        shutil.rmtree(session_dir, ignore_errors=True)
        if info.git:
            with contextlib.suppress(EngineError):
                _drop_session_refs(top, session_id)
            ref = stash_entry(top, made["sha"]) if "sha" in made else None
            if ref:
                git(top, "stash", "pop", "--quiet", "--index", ref, check=False)
        if new_repo:
            shutil.rmtree(repo_path, ignore_errors=True)
        raise


def _build_session(  # noqa: PLR0913
    *,
    session_dir: Path,
    repo_path: Path,
    info: RepoInfo,
    origin: str,
    slug: str,
    rid: str,
    repo_dir: str,
    root: Path,
    session_id: str,
    command: str,
    backend: str | None,
    prompt_summary: str,
    passes: int,
    timeout: str,
    mutating: bool,
    variants: int | None,
    bare: bool,
    made: Json,
) -> Json:
    top = info.top
    make_pass_dir(session_dir, 1, mutating=mutating)
    if variants:
        for sub in ("outputs", "stderr"):
            (session_dir / sub).mkdir(mode=0o700, exist_ok=True)
    scratch = session_dir / "scratch"
    if not info.git:
        scratch.mkdir(mode=0o700)

    repo_json = repo_path / "repo.json"
    if not repo_json.exists():
        write_atomic(
            repo_json,
            json.dumps(
                {
                    "schema_version": SCHEMA_VERSION,
                    "slug": slug,
                    "id": rid,
                    "toplevel": top,
                    "origin": origin or None,
                    "git": info.git,
                },
                indent=2,
            )
            + "\n",
        )

    initial_guard = (
        take_guard_snapshot(top, session_id, "initial", session_dir)
        if mutating and not bare
        else None
    )
    stash: Json | None = stash_user_changes(top, command) if mutating else None
    if stash and stash.get("sha"):
        made["sha"] = stash["sha"]
    guard = (
        None if bare or not info.git else take_guard_snapshot(top, session_id, "pre", session_dir)
    )
    branch = git(top, "branch", "--show-current") if info.git else ""
    ref = git(top, "rev-parse", "--short", "HEAD") if info.git else ""
    detected = detect() if backend == "model-clis" and not bare else None
    participants, executors, models = (
        ([], {}, []) if bare else build_roster(t.cast("str", backend), detected)
    )
    trunk = detect_trunk(top) if info.git else None
    created = stamp()
    doc: Json = {
        "schema_version": SCHEMA_VERSION,
        "session_id": session_id,
        "command": command,
        "status": "in_progress",
        "toplevel": top,
        "repo_dir": repo_dir,
        "branch": branch,
        "ref": ref,
        "mutating": mutating,
        "worker_backend": None if bare else backend,
        "participants": participants,
        "executors": executors,
        "completed_passes": 0,
        "prompt_summary": prompt_summary[:120],
        "created_at": created,
        "updated_at": created,
    }
    if guard:
        doc["guard"] = guard
    if initial_guard:
        doc["initial_guard"] = initial_guard
    if not info.git:
        doc["unguarded"] = True
        doc["scratch"] = str(scratch)
    if variants:
        doc["variants"] = variants
    if detected is not None and not bare:
        doc["models"] = models
        doc["chains"] = {lane: found["chain"] for lane, found in detected["lanes"].items() if found}
    if stash is not None:
        doc["stash"] = stash
    save_session(session_dir, doc)
    append_jsonl(
        session_dir / "events.jsonl",
        {
            "event": "session_start",
            "timestamp": created,
            "command": command,
            "worker_backend": doc["worker_backend"],
            "participants": participants,
        },
    )
    lines = [
        f"# {command} session {session_id}",
        "",
        f"- Started: {created}",
        f"- Configured passes: {passes}",
        f"- Worker backend: {doc['worker_backend']}",
        f"- Participants: {', '.join(participants)}",
        f"- Executors: {json.dumps(executors)}",
    ]
    if doc.get("models"):
        lines += [f"- Models: {json.dumps(models)}", f"- Timeout: {timeout}"]
    if info.git:
        lines += [f"- Branch: {branch or '(detached)'}", f"- Commit: {ref}"]
    else:
        lines += [f"- No repository: {info.reason}"]
    (session_dir / "metadata.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    result: Json = {
        "ok": True,
        "session_dir": str(session_dir),
        "session_id": session_id,
        "aip_root": str(root),
        "toplevel": top,
        "repo_dir": repo_dir,
        "branch": branch,
        "ref": ref,
        "trunk": trunk,
        "baseline_sha": baseline_sha(top, trunk) if trunk else "",
        "participants": participants,
        "executors": executors,
        "artifacts": [f"{p}-v{n}" for p in participants for n in range(1, variants + 1)]
        if variants
        else participants,
        "stash": stash,
        "repo": info.git,
    }
    if not info.git:
        result["unguarded"] = True
        result["note"] = (
            f"No repository ({info.reason}): workers start in an empty scratch directory"
            " and the repo guard is off."
        )
    return result


def context_sections(top: str, *, full_diff: bool = False, diff_limit: int = 0) -> str:
    """Return the deterministic context-packet sections as Markdown."""
    trunk = detect_trunk(top)
    base = compare_base(top, trunk)
    status = git(top, "status", "--short") or "(clean)"
    if base is None:
        changes = f"(no {trunk} branch to compare against)"
    else:
        changes = git(top, "diff", "--stat", f"{base}...HEAD", check=False) or (
            f"(none against {base})"
        )
    text = (
        f"## Repo state\n\n- Branch: {git(top, 'branch', '--show-current') or '(detached)'}\n"
        f"- HEAD: {git(top, 'rev-parse', '--short', 'HEAD')}\n- Trunk: {trunk}\n\n"
        f"```\n{status}\n```\n\n## Changed files\n\n```\n{changes}\n```\n"
    )
    if full_diff and base is not None:
        body = git(top, "diff", f"{base}...HEAD", check=False)
        lines = body.splitlines()
        if diff_limit and len(lines) > diff_limit:
            lines = [*lines[:diff_limit], f"... truncated at {diff_limit} of {len(lines)} lines"]
        text += "\n## Full diff\n\n```diff\n" + "\n".join(lines or ["(empty)"]) + "\n```\n"
    return text


def compose_prompt(  # noqa: PLR0913
    lane: str,
    body: str,
    *,
    mutating: bool,
    variant: tuple[int, int] | None = None,
    preamble: str | None = None,
    role: bool = True,
) -> str:
    """Assemble a worker prompt: role or variant preamble, body, and the write ban.

    ``variant`` is ``(n, of)``; a variant prompt has no role. A custom
    ``preamble`` is prefixed ``Variant n of m:``; the built-in one is not.

    >>> text = compose_prompt("agy", "Q?", mutating=False)
    >>> text.startswith("You are the Skeptic."), "READ-ONLY research task" in text
    (True, True)
    >>> "CRITICAL" in compose_prompt("gpt", "Q?", mutating=True)
    False
    >>> "session directory" in compose_prompt("claude", "Q?", mutating=False)
    True
    >>> compose_prompt("gpt", "Q", mutating=True, variant=(2, 3)).splitlines()[2]
    'Take an unconventional or creative approach. Challenge the obvious solution.'
    >>> compose_prompt("gpt", "Q", mutating=True, variant=(1, 2), preamble="Go.").splitlines()[2]
    'Variant 1 of 2: Go.'
    >>> compose_prompt("agy", "Q", mutating=True, role=False).startswith("Q")
    True
    """
    parts: list[str] = []
    if variant:
        n, of = variant
        parts.append(VARIANT_DIRECTIVE)
        parts.append(f"Variant {n} of {of}: {preamble}" if preamble else VARIANT_PREAMBLES[n])
    elif role:
        key = LANE_ROLES.get(lane, lane)
        if key not in ROLES:
            msg = f"unknown lane or role {lane!r}"
            raise EngineError(msg)
        parts.append(ROLES[key])
    parts.append(body.strip("\n"))
    if not mutating:
        parts.append((HARDEN_HOST if lane in HOST_LANES else HARDEN_EXTERNAL).rstrip("\n"))
    return "\n\n".join(parts) + "\n"


def make_pass(session_dir: Path, n: int) -> Json:
    """Create ``pass-NNNN`` for a later pass, with diff dirs for mutating sessions."""
    session = load_session(session_dir)
    base = make_pass_dir(session_dir, n, mutating=bool(session.get("mutating")))
    return {"ok": True, "pass_dir": str(base)}


def label_participants(
    session_dir: Path,
    n: int,
    participants: Sequence[str],
    rng: random.Random | None = None,
    outputs: Path | None = None,
) -> Json:
    """Assign random A, B, C labels and write identity-free copies of the outputs.

    >>> import tempfile
    >>> with tempfile.TemporaryDirectory() as d:
    ...     base = Path(d) / "pass-0001"
    ...     (base / "outputs").mkdir(parents=True)
    ...     _ = [(base / "outputs" / f"{p}.md").write_text(p) for p in "xyz"]
    ...     doc = label_participants(Path(d), 1, ["x", "y", "z"], random.Random(1))
    ...     mapped = {k: (base / "blind" / f"response-{k}.md").read_text() for k in "ABC"}
    ...     sorted(doc["labels"]) == ["A", "B", "C"], mapped == doc["labels"]
    (True, True)
    """
    order = list(participants)
    (rng or random).shuffle(order)
    labels = {chr(ord("A") + i): name for i, name in enumerate(order)}
    base = session_dir / pass_name(n)
    blind = base / "blind"
    blind.mkdir(mode=0o700, parents=True, exist_ok=True)
    src_dir = outputs or base / "outputs"
    for label, name in labels.items():
        src = src_dir / f"{name}.md"
        if src.is_file() and not src.is_symlink():
            write_atomic(blind / f"response-{label}.md", src.read_bytes(), session_dir)
    write_atomic(base / "label-map.json", json.dumps(labels, indent=2) + "\n", session_dir)
    return {"ok": True, "labels": labels, "map": str(base / "label-map.json")}


# --- dispatch -------------------------------------------------------------


def classify(*, returncode: int | None, timed_out: bool, output_size: int, stderr: str) -> str:
    """Classify one CLI attempt.

    >>> classify(returncode=0, timed_out=False, output_size=5, stderr="")
    'ok'
    >>> classify(returncode=None, timed_out=True, output_size=0, stderr="")
    'timeout'
    >>> classify(returncode=1, timed_out=False, output_size=0, stderr="Error 429: daily limit")
    'credit'
    >>> classify(returncode=1, timed_out=False, output_size=0, stderr="RESOURCE_EXHAUSTED")
    'credit'
    >>> classify(returncode=1, timed_out=False, output_size=0, stderr="429 Too Many Requests")
    'rate-limit'
    >>> classify(returncode=2, timed_out=False, output_size=0, stderr="boom")
    'crash'
    >>> classify(returncode=0, timed_out=False, output_size=0, stderr="")
    'empty'
    """
    if timed_out:
        return "timeout"
    if returncode == 0 and output_size > 0:
        return "ok"
    if CREDIT_RE.search(stderr) or ("429" in stderr and "daily limit" in stderr.lower()):
        return "credit"
    if RATE_RE.search(stderr):
        return "rate-limit"
    if returncode != 0:
        return "crash"
    return "empty"


def scrub_echo(stderr: str, prompt: str) -> str:
    r"""Remove the prompt a CLI echoed to stderr, so task text cannot pose as an error.

    >>> scrub_echo("billing\nreal error", "Fix billing\nbilling")
    'real error'
    """
    text = stderr.replace(prompt, "") if prompt else stderr
    echoed = {line.strip() for line in prompt.splitlines() if line.strip()}
    kept = [ln for ln in text.splitlines() if ln.strip() not in echoed]
    return "\n".join(kept)


def build_command(
    exe: str, model: str | None, prompt: str, *, mutating: bool, workdir: Path
) -> list[str]:
    """Return the argv for one lane step; every step runs with ``workdir`` as cwd.

    Read-only runs use each CLI's own read-only mode where it has one; ``agy``
    has none. ``workdir`` is always a disposable checkout, never the user's.

    >>> build_command("codex", None, "P", mutating=False, workdir=Path("/w"))[:6]
    ['codex', 'exec', '-s', 'read-only', '-C', '/w']
    >>> build_command("agent", "m", "P", mutating=True, workdir=Path("/w"))[:4]
    ['agent', '-p', '-f', '--model']
    >>> build_command("agy", "M", "P", mutating=False, workdir=Path("/w"))[-2:]
    ['-p', 'P']
    """
    wd = str(workdir)
    if exe == "agy":
        return ["agy", "--model", t.cast("str", model), "--add-dir", wd,
                "--dangerously-skip-permissions", "-p", prompt]  # fmt: skip
    if exe == "codex":
        effort = ["-c", "model_reasoning_effort=medium", prompt]
        if mutating:
            return ["codex", "exec", "--dangerously-bypass-approvals-and-sandbox", *effort]
        return ["codex", "exec", "-s", "read-only", "-C", wd, "--skip-git-repo-check", *effort]
    if mutating:
        return ["agent", "-p", "-f", "--model", t.cast("str", model), prompt]
    argv = ["agent", "-p", "--mode", "plan", "--trust", "--workspace", wd]
    return [*argv, "--model", t.cast("str", model), prompt]


def run_cli(  # noqa: PLR0913
    argv: list[str],
    cwd: Path,
    timeout: float | None,
    out: Path,
    err: Path,
    *,
    prompt: str = "",
) -> Json:
    """Run ``argv`` with a wall-clock limit, killing its whole process group.

    ``prompt`` is removed from stderr before the failure is classified.
    """
    started = time.monotonic()
    err_offset = err.stat().st_size if err.exists() else 0
    timed_out = False
    with out.open("wb") as fo, err.open("ab") as fe:
        proc = subprocess.Popen(  # noqa: S603
            argv,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=fo,
            stderr=fe,
            start_new_session=True,
        )
        try:
            returncode: int | None = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            returncode = None
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
    stderr = scrub_echo(err.read_bytes()[err_offset:].decode("utf-8", "replace"), prompt)
    return {
        "returncode": returncode,
        "elapsed": round(time.monotonic() - started, 1),
        "class": classify(
            returncode=returncode,
            timed_out=timed_out,
            output_size=out.stat().st_size,
            stderr=stderr,
        ),
    }


class Task(t.NamedTuple):
    """What one dispatch produces: its artifact name, output paths, and prompt shape."""

    name: str
    out: Path
    err: Path
    variant: tuple[int, int] | None = None
    preamble: str | None = None
    role: bool = True


def lane_task(  # noqa: PLR0913
    session_dir: Path,
    lane: str,
    *,
    n: int,
    variant: int | None = None,
    of: int | None = None,
    judge: bool = False,
    preamble: str | None = None,
    out: Path | None = None,
    err: Path | None = None,
) -> Task:
    """Resolve artifact names and paths for a dispatch.

    A plain lane writes ``pass-NNNN/outputs/<lane>.md``; a variant writes
    ``outputs/<lane>-v<N>.md`` at the session root; a judge writes
    ``pass-NNNN/judges/<lane>.md``.
    """
    base = session_dir / pass_name(n)
    if judge:
        name, o, e = (
            f"judge-{lane}",
            base / "judges" / f"{lane}.md",
            base / "stderr" / f"judge-{lane}.txt",
        )
    elif variant:
        name = f"{lane}-v{variant}"
        o, e = session_dir / "outputs" / f"{name}.md", session_dir / "stderr" / f"{name}.txt"
    else:
        name, o, e = lane, base / "outputs" / f"{lane}.md", base / "stderr" / f"{lane}.txt"
    pair = (variant, of or variant) if variant else None
    return Task(name, out or o, err or e, pair, preamble, role=not (judge or variant))


def snapshot_worktree(session: Json, session_dir: Path, name: str) -> Path:
    """Create a disposable detached worktree at the pre-dispatch snapshot commit."""
    top = session["toplevel"]
    require_safe_toplevel(top)
    path = session_dir / "worktrees" / f"{name}-ro"
    git(top, "worktree", "remove", "--force", str(path), check=False)
    shutil.rmtree(path, ignore_errors=True)
    git(top, "worktree", "prune", check=False)
    git(top, "worktree", "add", "-q", "--detach", str(path), session["guard"]["pre"])
    return path


def dispatch_lane(  # noqa: PLR0913, PLR0915
    session_dir: Path,
    lane: str,
    *,
    n: int,
    prompt_file: Path,
    timeout: float | None,
    mutating: bool,
    task: Task | None = None,
    rate_wait: float = RATE_LIMIT_WAIT,
    which: Callable[[str], str | None] = shutil.which,
) -> Json:
    """Run one external lane with classification, one retry, and fallback.

    Read-only attempts run in a disposable worktree built from the pre-dispatch
    snapshot, so the CLI sees the user's uncommitted work and cannot write the
    user's checkout; the checkout is compared with the snapshot afterwards.
    Mutating attempts run in the lane's registered worktree.

    A timeout retries at 1.5x the limit, a rate limit retries after ``rate_wait``
    seconds, an empty answer retries once, and a credit or quota error skips the
    retry. A crash ends the lane. After a failed retry the next installed step in the
    lane's chain runs. The chain is the one ``init`` recorded in ``session.json``;
    dispatch never lists models again.
    """
    session = load_session(session_dir)
    task = task or lane_task(session_dir, lane, n=n)
    if mutating and task.name not in session.get("worktrees", {}):
        msg = f"no worktree registered for {task.name}; run worktrees create first"
        raise EngineError(msg)
    # A session recorded before lanes resolved models runs the pinned chain.
    steps = session.get("chains", {}).get(lane) or lane_chain(lane, which)
    chain = [(exe, model) for exe, model, _ in steps if which(exe)]
    if not chain:
        return {"ok": False, "lane": lane, "failure_class": "unavailable", "attempts": []}
    out, err = task.out, task.err
    for path in (out, err):
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        claim_path(path, session_dir)
    prompt = compose_prompt(
        lane,
        prompt_file.read_text(encoding="utf-8"),
        mutating=mutating,
        variant=task.variant,
        preamble=task.preamble,
        role=task.role,
    )
    prompt_out = session_dir / pass_name(n) / "prompts" / f"{task.name}.md"
    prompt_out.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    write_atomic(prompt_out, prompt, session_dir)

    attempts: list[Json] = []
    retries = 0
    current = timeout
    guards: list[str] = []
    for exe, model in chain:
        retried = False
        while True:
            disposable: Path | None = None
            if mutating:
                workdir = Path(session["worktrees"][task.name]["path"])
            elif session.get("unguarded"):
                disposable = workdir = Path(session["scratch"]) / task.name
                shutil.rmtree(workdir, ignore_errors=True)
                workdir.mkdir(mode=0o700, parents=True)
            else:
                try:
                    disposable = workdir = snapshot_worktree(session, session_dir, task.name)
                except EngineError as exc:
                    return {**_failed(lane, "no-worktree", attempts, out, err), "error": str(exc)}
            argv = build_command(exe, model, prompt, mutating=mutating, workdir=workdir)
            with err.open("a", encoding="utf-8") as fe:
                fe.write(f"--- {exe} {model or ''} timeout={current}\n")
            result = run_cli(argv, workdir, current, out, err, prompt=prompt)
            if disposable is not None:
                if session.get("unguarded"):
                    shutil.rmtree(disposable, ignore_errors=True)
                else:
                    git(
                        session["toplevel"],
                        "worktree",
                        "remove",
                        "--force",
                        str(disposable),
                        check=False,
                    )
                found = guard_check(session_dir, task.name)
                if found["violation"] and found.get("id") not in guards:
                    guards.append(found["id"])
            attempts.append({"executor": exe, "model": model, **result})
            cls = result["class"]
            if cls == "ok":
                return {
                    "ok": True,
                    "lane": lane,
                    "executor": exe,
                    "model": model,
                    "output": str(out),
                    "stderr": str(err),
                    "retries": retries,
                    "elapsed": sum(a["elapsed"] for a in attempts),
                    "attempts": attempts,
                    "guard_violations": guards,
                }
            if cls == "crash":
                return {**_failed(lane, cls, attempts, out, err), "guard_violations": guards}
            if cls == "credit" or retried:
                break
            retried = True
            retries += 1
            if cls == "timeout" and current is not None:
                current = current * TIMEOUT_GROWTH
            elif cls == "rate-limit":
                time.sleep(rate_wait)
    return {**_failed(lane, attempts[-1]["class"], attempts, out, err), "guard_violations": guards}


def _failed(lane: str, cls: str, attempts: list[Json], out: Path, err: Path) -> Json:
    return {
        "ok": False,
        "lane": lane,
        "failure_class": cls,
        "output": str(out),
        "stderr": str(err),
        "attempts": attempts,
    }


# --- judging --------------------------------------------------------------


def plan_judges(session_dir: Path, mode: str, n: int) -> Json:
    """Pick the judge or panel for pass ``n``.

    ``host`` judges every pass in the orchestrator. ``round-robin`` rotates
    through the participants in roster order. ``panel`` uses every participant and
    reports whether the panel is full, degraded to one peer, or infeasible.
    Each judge's ``how`` is ``host``, ``native`` (a fresh sub-agent), or
    ``external`` (``dispatch --judge``).
    """
    session = load_session(session_dir)
    people: list[str] = session["participants"]
    native = session["worker_backend"] == "subagents"

    def how(who: str) -> str:
        if who == "claude":
            return "host"
        return "native" if native else "external"

    if mode == "host":
        return {"ok": True, "mode": mode, "judges": [{"judge": "host", "how": "host"}]}
    if mode == "round-robin":
        if len(people) < 2:  # noqa: PLR2004
            return {"ok": True, "mode": "host", "judges": [{"judge": "host", "how": "host"}]}
        who = people[(n - 1) % len(people)]
        return {"ok": True, "mode": mode, "judges": [{"judge": who, "how": how(who)}]}
    if mode == "panel":
        feasibility = (
            "host-fallback" if len(people) < 2 else "degraded" if len(people) == 2 else "full"  # noqa: PLR2004
        )
        if feasibility == "host-fallback":
            return {"ok": True, "mode": "host", "feasibility": feasibility,
                    "judges": [{"judge": "host", "how": "host"}]}  # fmt: skip
        return {
            "ok": True,
            "mode": mode,
            "feasibility": feasibility,
            "judges": [{"judge": who, "how": how(who)} for who in people],
        }
    msg = f"unknown judge mode {mode!r}"
    raise EngineError(msg)


_NUM_RE = re.compile(r"\d+(?:\.\d+)?")
_LABEL_RE = re.compile(r"(?:response[\s_-]*)?([A-Za-z])", re.IGNORECASE)


def _number(cell: str) -> int | float | None:
    """Parse a score cell: ``8`` is an int, ``8.5`` a float, anything else ``None``."""
    if not _NUM_RE.fullmatch(cell):
        return None
    return float(cell) if "." in cell else int(cell)


def normalize_id(raw: str, label_map: Mapping[str, str] | None = None) -> str:
    """Reduce a scores-table column or winner to a participant id.

    Strips emphasis and a trailing role suffix, and maps a blind label through
    ``label_map``.

    >>> normalize_id("**claude (Maintainer)**"), normalize_id("agy-v2 - Skeptic")
    ('claude', 'agy-v2')
    >>> normalize_id("Response B", {"A": "x", "B": "gpt"}), normalize_id("Response B")
    ('gpt', 'Response B')
    """
    name = raw.strip().strip("*_`").strip()
    name = re.sub(r"\s*[(\[][^)\]]*[)\]]\s*$", "", name)
    name = re.sub(r"\s+[-\u2013\u2014:]\s+\S.*$", "", name).strip()
    if label_map:
        found = _LABEL_RE.fullmatch(name)
        if found and found.group(1).upper() in label_map:
            return label_map[found.group(1).upper()]
    return name


def parse_judge(text: str, label_map: Mapping[str, str] | None = None) -> Json:
    """Parse a judge assessment: scores table, totals, winner.

    The table has a header row of participant names, one row per dimension
    whose cells are numbers 0-10 (decimals allowed), and a ``Total`` row.
    Header names may carry a role suffix (``claude (Maintainer)``); blind labels
    map to participants through ``label_map``. Without a Winner section the
    winner is the unique highest total.

    >>> doc = parse_judge('''
    ... | Dimension | claude | agy |
    ... |---|---|---|
    ... | Quality (0-10) | 8 | 7 |
    ... | Coherence (0-10) | 9 | 6 |
    ... | **Total** | 17 | 13 |
    ...
    ... ## Winner
    ...
    ... **claude** with a score of 17/20.
    ... ''')
    >>> doc["ok"], doc["winner"], doc["winner_score"], doc["totals"]
    (True, 'claude', 17, {'claude': 17, 'agy': 13})
    >>> parse_judge("no table")["ok"]
    False
    """
    rows = [
        [c.strip().strip("*").strip() for c in line.strip().strip("|").split("|")]
        for line in text.splitlines()
        if line.strip().startswith("|")
    ]
    rows = [r for r in rows if not all(set(c) <= set("-: ") for c in r)]
    errors: list[str] = []
    if len(rows) < 3:  # noqa: PLR2004
        return {"ok": False, "errors": ["no scores table"]}
    columns = [normalize_id(c, label_map) for c in rows[0][1:]]
    if len(set(columns)) != len(columns):
        return {"ok": False, "errors": ["duplicate participant columns"]}
    scores: dict[str, dict[str, float]] = {c: {} for c in columns}
    totals: dict[str, float] = {}
    for row in rows[1:]:
        label, cells = row[0], row[1:]
        nums = [_number(c) for c in cells]
        if len(cells) != len(columns) or any(n is None for n in nums):
            errors.append(f"unreadable row: {label}")
            continue
        values = t.cast("list[float]", nums)
        if label.lower().startswith("total"):
            totals = dict(zip(columns, values))
            continue
        for col, num in zip(columns, values):
            if num > 10:  # noqa: PLR2004
                errors.append(f"{label} for {col} is above 10")
            scores[col][label] = num
    warnings = [
        f"total for {col} was {totals[col]:g}, recomputed as {sum(scores[col].values()):g}"
        for col in columns
        if col in totals and abs(totals[col] - sum(scores[col].values())) > 1e-6  # noqa: PLR2004
    ]
    totals.update({c: sum(scores[c].values()) for c in columns if c in totals})
    if not totals:
        totals = {c: sum(v.values()) for c, v in scores.items()}
    winner = None
    declared = False
    found = re.search(r"##\s*Winner\b[^\n]*\n+\s*(\S[^\n]*)", text)
    if found:
        line = found.group(1)
        bold = re.search(r"\*\*([^*]+)\*\*", line)
        winner = normalize_id(bold.group(1) if bold else re.split(r"\s+with\b", line)[0], label_map)
        declared = True
        if winner not in columns:
            errors.append(f"winner {winner!r} is not a scored participant")
    elif totals:
        top = max(totals.values())
        leaders = [c for c, v in totals.items() if v == top]
        winner = leaders[0] if len(leaders) == 1 else None
    return {
        "ok": not errors,
        "columns": columns,
        "scores": scores,
        "totals": totals,
        "winner": winner,
        "winner_declared": declared,
        "winner_score": totals.get(winner or ""),
        "errors": errors,
        "warnings": warnings,
    }


def producer_of(original: str) -> str:
    """Return the participant that produced an original.

    >>> producer_of("claude-v2"), producer_of("agy")
    ('claude', 'agy')
    """
    return re.sub(r"-v\d+$", "", original)


def merge_panel(judges: Mapping[str, Path], label_map: Mapping[str, str] | None = None) -> Json:
    """Merge panel judge files by peer-only averaging.

    A judge's scores for originals its own participant produced are excluded.
    A judge whose file does not parse is excluded and reported. ``label_map``
    maps the blind labels the judges scored back to participants.
    """
    parsed: dict[str, Json] = {}
    failed: dict[str, list[str]] = {}
    for judge, path in judges.items():
        doc = (
            parse_judge(path.read_text(encoding="utf-8"), label_map)
            if path.is_file()
            else {"ok": False, "errors": ["missing file"]}
        )
        if doc["ok"]:
            parsed[judge] = doc
        else:
            failed[judge] = t.cast("list[str]", doc["errors"])
    originals = sorted({o for d in parsed.values() for o in d["columns"]})
    merged: dict[str, dict[str, float]] = {}
    used: dict[str, list[str]] = {}
    for original in originals:
        peers = [
            j for j, d in parsed.items() if original in d["columns"] and j != producer_of(original)
        ]
        used[original] = peers
        dims: dict[str, list[int]] = {}
        for j in peers:
            for dim, score in parsed[j]["scores"][original].items():
                dims.setdefault(dim, []).append(score)
        merged[original] = {d: round(sum(v) / len(v), 2) for d, v in dims.items()}
    totals = {o: round(sum(v.values()), 2) for o, v in merged.items()}
    best = max(totals.values(), default=None)
    tied = sorted(o for o, v in totals.items() if v == best) if best is not None else []
    return {
        "ok": bool(parsed),
        "judges_succeeded": sorted(parsed),
        "judges_failed": failed,
        "merged": merged,
        "totals": totals,
        "peers": used,
        "winner": tied[0] if len(tied) == 1 else None,
        "tied": tied if len(tied) > 1 else [],
    }


# --- worktrees, capture, adopt --------------------------------------------


def _worker_root_protocol(path: Path) -> str:
    return (
        f"Assigned worktree root: {str(path)!r}. This does not set your tool cwd.\n"
        "Every Bash or shell call starts from the inherited directory, not your previous cd. "
        f"Start EVERY shell command with this literal prefix: cd -- {shlex.quote(str(path))} && \n"
        "Every Read, Write, Edit, Glob, or Grep path must be absolute under the assigned root "
        "(the supplied prompt file is the only read exception). Never use a relative file path.\n"
        "Leave edits unstaged. Do not commit, reset, restore, checkout, or change Git history.\n"
        "Do not change files outside this root. If you discover an outside write, STOP and report "
        "the exact paths; never move, delete, reset, or restore those files to hide or repair it."
    )


def _safe_participant(name: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", name):
        msg = f"unsafe participant ID {name!r}"
        raise EngineError(msg)
    return name


def create_worktrees(
    session_dir: Path,
    participants: Sequence[str],
    when: str | None = None,
    base: str | None = None,
) -> Json:
    """Create or reuse each participant's registered worktree.

    ``base`` is ``pre`` (the guard snapshot, detached) or ``head`` (a new branch
    ``weave/<name>/<when>``). The default is ``head`` for mutating sessions and
    ``pre`` for read-only ones, so read-only workers see the user's uncommitted work.
    """
    with session_lock(session_dir):
        return _create_worktrees(session_dir, participants, when, base)


def _check_registered_worktree(session: Json, path: Path, entry: Json, base: str | None) -> None:
    if entry["path"] != str(path) or not path.is_dir() or (path / ".git").is_symlink():
        msg = f"registered worktree is missing or replaced: {path}; preserve it and stop"
        raise EngineError(msg)
    if session.get("unguarded"):
        return
    top = Path(session["toplevel"])
    common = (path / git(path, "rev-parse", "--git-common-dir")).resolve()
    expected = (top / git(top, "rev-parse", "--git-common-dir")).resolve()
    branch = git(path, "symbolic-ref", "-q", "--short", "HEAD", check=False) or None
    if (
        git(path, "rev-parse", "--show-toplevel") != str(path.resolve())
        or common != expected
        or branch != entry["branch"]
        or (base is not None and (base == "pre") != (branch is None))
    ):
        msg = f"registered worktree identity/base differs: {path}; preserve it and stop"
        raise EngineError(msg)


def _create_worktrees(
    session_dir: Path, participants: Sequence[str], when: str | None, base: str | None
) -> Json:
    participants = [_safe_participant(name) for name in participants]
    session = load_session(session_dir)
    top = session["toplevel"]
    made: Json = session.setdefault("worktrees", {})
    for name in participants:
        path = session_dir / "worktrees" / name
        if path.is_symlink() or path.parent.is_symlink():
            msg = f"worktree path is a symlink: {path}; preserve it and stop"
            raise EngineError(msg)
        if name in made:
            _check_registered_worktree(session, path, made[name], base)
        elif path.exists():
            msg = f"unregistered worktree path already exists: {path}; preserve it and stop"
            raise EngineError(msg)
    if session.get("unguarded"):
        for name in participants:
            if name in made:
                continue
            path = session_dir / "worktrees" / name
            path.mkdir(mode=0o700, parents=True)
            made[name] = {
                "path": str(path),
                "branch": None,
                "worker_instructions": _worker_root_protocol(path),
            }
        save_session(session_dir, session)
        return {"ok": True, "worktrees": made}
    require_safe_toplevel(top)
    base = base or ("head" if session.get("mutating") else "pre")
    when = when or datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    for name in participants:
        if name in made:
            continue
        path = session_dir / "worktrees" / name
        if base == "pre":
            git(top, "worktree", "add", "-q", "--detach", str(path), session["guard"]["pre"])
            made[name] = {"path": str(path), "branch": None}
        else:
            branch = f"weave/{name}/{when}"
            git(top, "worktree", "add", "-q", str(path), "-b", branch)
            made[name] = {"path": str(path), "branch": branch}
        made[name]["worker_instructions"] = _worker_root_protocol(path)
        made[name]["base"] = git(path, "rev-parse", "HEAD")
        save_session(session_dir, session)
    return {"ok": True, "worktrees": made}


def remove_worktrees(
    session_dir: Path, participants: Sequence[str] | None, *, ack_drift: bool = False
) -> Json:
    """Remove the session's registered worktrees and delete their branches.

    Refused while a recorded guard violation lacks the user's decision (``ack_drift``).
    """
    if participants is not None:
        participants = [_safe_participant(name) for name in participants]
    require_drift_decision(session_dir, "worktrees remove", acknowledge=ack_drift)
    with session_lock(session_dir):
        session = load_session(session_dir)
        top = session["toplevel"]
        made: Json = session.get("worktrees", {})
        removed: list[str] = []
        for name in list(made) if participants is None else participants:
            entry = made.pop(name, None)
            if entry is None:
                continue
            if session.get("unguarded"):
                shutil.rmtree(entry["path"], ignore_errors=True)
            else:
                git(top, "worktree", "remove", "--force", entry["path"], check=False)
            if entry["branch"]:
                git(top, "branch", "-D", entry["branch"], check=False)
            removed.append(name)
        save_session(session_dir, session)
        return {"ok": True, "removed": removed}


def _participant_path(session: Json, session_dir: Path, name: str) -> Path:
    if session.get("unguarded"):
        return Path(session["scratch"]) / name
    return session_dir / "worktrees" / f"{name}-ro"


def start_participant(session_dir: Path, name: str) -> Json:
    """Give a participant with no registered worktree a disposable snapshot to work in.

    Critics, judges, and a skill's session agent use this; the snapshot is the
    one a read-only lane gets, so none of them touches the live checkout.
    """
    name = _safe_participant(name)
    session = load_session(session_dir)
    if name in session["participants"]:
        msg = f"{name!r} is a lane; a participant outside the roster needs its own name"
        raise EngineError(msg)
    if session.get("unguarded"):
        path = _participant_path(session, session_dir, name)
        shutil.rmtree(path, ignore_errors=True)
        path.mkdir(mode=0o700, parents=True)
    else:
        path = snapshot_worktree(session, session_dir, name)
    return {
        "ok": True,
        "participant": name,
        "path": str(path),
        "worker_instructions": _worker_root_protocol(path),
    }


def finish_participant(session_dir: Path, name: str) -> Json:
    """Remove a participant's snapshot, then run the repo guard; a violation fails the result."""
    name = _safe_participant(name)
    session = load_session(session_dir)
    path = _participant_path(session, session_dir, name)
    if not path.is_dir():
        msg = f"no snapshot for {name!r}; run participant start first"
        raise EngineError(msg)
    if session.get("unguarded"):
        shutil.rmtree(path, ignore_errors=True)
    else:
        git(session["toplevel"], "worktree", "remove", "--force", str(path), check=False)
        shutil.rmtree(path, ignore_errors=True)
        git(session["toplevel"], "worktree", "prune", check=False)
    found = guard_check(session_dir, name)
    return {**found, "ok": not found["violation"], "participant": name}


_ENGINE_OWNED = ("session.json", "guard", STATE_DIR)


def claim_session_path(session_dir: Path, rel: str) -> Path:
    """Return the absolute path for ``rel`` under the session after detaching any alias there.

    A symlink or hard link already at the path is removed (its target is untouched);
    a symlinked parent or a directory at the path is refused. Call this just before a
    host tool writes the file.
    """
    rel = _safe_rel(rel)
    if not rel or Path(rel).parts[0] in _ENGINE_OWNED:
        msg = f"{rel!r} is engine-owned or empty; the coordinator does not write it"
        raise EngineError(msg)
    path = session_dir / rel
    claim_path(path, session_dir)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    return claim_path(path, session_dir)


def write_session_file(session_dir: Path, rel: str, data: bytes) -> Json:
    """Write ``data`` to ``rel`` under the session through an alias-safe replace."""
    path = claim_session_path(session_dir, rel)
    write_atomic(path, data, session_dir)
    return {"ok": True, "path": str(path), "bytes": len(data)}


def synthesis_packet(session_dir: Path, n: int, out: Path | None = None) -> Json:
    """Assemble the blind responses of pass ``n`` into one file, by path.

    The coordinator hands this file to the synthesis step instead of retyping
    each reply. Only blind labels appear; a response that is missing or empty is listed.
    """
    base = session_dir / pass_name(n)
    map_path = base / "label-map.json"
    if not map_path.is_file() or map_path.is_symlink():
        msg = f"no label-map.json in {pass_name(n)}; run labels first"
        raise EngineError(msg)
    labels = sorted(json.loads(map_path.read_text(encoding="utf-8")))
    parts = [f"# Responses, {pass_name(n)}", ""]
    present: list[str] = []
    missing: list[str] = []
    for label in labels:
        src = base / "blind" / f"response-{label}.md"
        if src.is_symlink():
            msg = f"refusing to read symlinked response {str(src)!r}"
            raise EngineError(msg)
        text = src.read_text(encoding="utf-8", errors="replace").strip() if src.is_file() else ""
        if not text:
            missing.append(label)
            continue
        present.append(label)
        body = text.replace("</response>", "<\\/response>")
        parts += [f'<response label="{label}">', body, "</response>", ""]
    if not present:
        msg = f"{pass_name(n)} has no blind response to assemble"
        raise EngineError(msg)
    target = out or base / "packet.md"
    claim_path(target, session_dir)
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    text = "\n".join(parts)
    write_atomic(target, text, session_dir)
    return {
        "ok": True,
        "path": str(target),
        "labels": present,
        "missing": missing,
        "words": len(text.split()),
    }


def capture_tree(session_dir: Path, n: int, participant: str, tree: str | None) -> Json:
    """Save a participant's binary patch, changed-file snapshots, and manifest.

    ``tree`` is a path, or ``None`` for the participant's registered worktree.
    The tree's index is not touched. Symlinks are snapshotted as symlinks
    (dangling ones included) and listed under ``links`` in the manifest.
    """
    participant = _safe_participant(participant)
    session = load_session(session_dir)
    entry = session.get("worktrees", {}).get(participant)
    if tree is None and entry is None:
        msg = f"no worktree registered for {participant}; pass --tree or run worktrees create"
        raise EngineError(msg)
    path = tree or entry["path"]
    base = session_dir / pass_name(n)
    baseline = entry.get("base") if entry else None
    baseline = baseline or session["guard"]["head" if session.get("mutating") else "pre"]
    after = snapshot_tree(path)
    patch = git_bytes(path, "diff", "--binary", "--no-renames", baseline, after)
    changed = git_z(
        path, "diff", "--name-only", "-z", "--no-renames", "--diff-filter=d", baseline, after
    )
    deleted = git_z(
        path, "diff", "--name-only", "-z", "--no-renames", "--diff-filter=D", baseline, after
    )
    patch_path = base / "diffs" / f"{participant}.patch"
    patch_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    write_atomic(patch_path, patch, session_dir)
    links: dict[str, str] = {}
    for rel in changed:
        src = Path(path) / rel
        if src.is_symlink():
            links[rel] = os.readlink(src)  # noqa: PTH115
        copy_owned(src, base / "files" / participant / rel, session_dir)
    manifest: Json = {"changed": changed, "deleted": deleted}
    if links:
        manifest["links"] = links
    manifest_text = json.dumps(manifest, indent=2) + "\n"
    write_atomic(base / "diffs" / f"{participant}.json", manifest_text, session_dir)
    return {"ok": True, "participant": participant, "patch": str(patch_path), **manifest}


def _safe_rel(rel: str) -> str:
    """Reject absolute paths and ``..`` segments.

    >>> _safe_rel("a/b.py")
    'a/b.py'
    >>> _safe_rel("../x")
    Traceback (most recent call last):
    ...
    engine.EngineError: unsafe path '../x'
    """
    if Path(rel).is_absolute() or ".." in Path(rel).parts:
        msg = f"unsafe path {rel!r}"
        raise EngineError(msg)
    return rel


def _path_conflicts(top: Path, paths: Sequence[str], *, editing: bool = False) -> dict[str, str]:
    paths = [str(Path(_safe_rel(path))) for path in paths]
    conflicts: dict[str, str] = {}
    for rel in paths:
        target = top / rel
        parents = [p for p in target.parents if p != top and top in p.parents]
        if not Path(rel).parts or any(p.lower() == ".git" for p in Path(rel).parts):
            conflicts[rel] = "repository root or Git metadata"
        elif any(parent.is_symlink() for parent in parents):
            conflicts[rel] = "symlinked parent"
        elif any(parent.exists() and not parent.is_dir() for parent in parents):
            conflicts[rel] = "parent is not a directory"
        elif target.is_symlink():
            if editing:
                conflicts[rel] = "symlink target cannot be edited in place"
        elif target.exists() and not target.is_file():
            conflicts[rel] = "directory or special file"
        elif editing and target.is_file() and target.stat().st_nlink > 1:
            conflicts[rel] = "hard-linked file; an in-place edit also changes its other names"
    paths = [path for path in paths if path not in conflicts]
    if paths:
        env = {"GIT_OPTIONAL_LOCKS": "0"}
        for entry in git_z(
            top, "--literal-pathspecs", "ls-files", "-v", "-z", "--", *paths, env=env
        ):
            if entry[0].islower() or entry[0] == "S":
                conflicts[entry[2:]] = "assume-unchanged or skip-worktree index flag"
        for entry in git_z(
            top, "--literal-pathspecs", "status", "--porcelain", "-z", "--no-renames",
            "--untracked-files=all", "--ignored", "--", *paths, env=env,
        ):  # fmt: skip
            conflicts[entry[3:]] = "uncommitted or ignored path"
    return conflicts


def _adoption_conflicts(top: Path, paths: Sequence[str], session: Json) -> dict[str, str]:
    conflicts = _path_conflicts(top, paths)
    paths = [str(Path(_safe_rel(path))) for path in paths]
    if paths:
        baseline = _guard_of(session)["head"]
        changed = git_z(
            top, "--literal-pathspecs", "diff", "--name-only", "-z", "--no-renames",
            "--no-ext-diff", "--no-textconv", baseline, "HEAD", "--", *paths,
        )  # fmt: skip
        for path in changed:
            conflicts.setdefault(path, "committed path differs from the session base")
        observable = [path for path in paths if path not in conflicts]
        if observable:
            tree = snapshot_tree(top, paths=observable)
            for path in git_z(
                top, "--literal-pathspecs", "diff", "--name-only", "-z", "--no-renames",
                "--no-ext-diff", "--no-textconv", baseline, tree, "--", *observable,
            ):  # fmt: skip
                conflicts[path] = "working path differs from the session base"
    return conflicts


def adopt_files(  # noqa: PLR0913
    session_dir: Path,
    n: int,
    picks: Sequence[str],
    deletes: Sequence[str],
    whole: str | None = None,
    *,
    replace_aliases: bool = False,
) -> Json:
    """Copy chosen ``path=participant`` snapshots into the main checkout; remove deleted paths.

    ``whole`` adopts every change one participant captured in pass ``n``. A
    session may be applied once; every selected path must still match its base.
    A target that is the user's symlink or hard link is refused unless
    ``replace_aliases`` records the user's decision.
    """
    with session_lock(session_dir):
        return _adopt_files(session_dir, n, picks, deletes, whole, replace_aliases=replace_aliases)


def _user_aliases(top: Path, paths: Sequence[str]) -> dict[str, str]:
    found: dict[str, str] = {}
    for rel in paths:
        try:
            info = (top / rel).lstat()
        except OSError:
            continue
        if stat.S_ISLNK(info.st_mode):
            found[rel] = "symlink"
        elif stat.S_ISREG(info.st_mode) and info.st_nlink > 1:
            found[rel] = "hard link"
    return found


def _escaping_link(top: Path, rel: str, src: Path) -> str | None:
    """Return the link text when a snapshot symlink is absolute or leaves the repository."""
    link = os.readlink(src)  # noqa: PTH115
    root = Path(os.path.realpath(top))
    if Path(link).is_absolute():
        return link
    reach = Path(os.path.realpath((top / rel).parent / link))
    return None if reach == root or root in reach.parents else link


def _adopt_files(  # noqa: PLR0913
    session_dir: Path,
    n: int,
    picks: Sequence[str],
    deletes: Sequence[str],
    whole: str | None,
    *,
    replace_aliases: bool = False,
) -> Json:
    session = load_session(session_dir)
    if session.get("applied"):
        msg = "session was already applied; review the checkout instead of applying it again"
        raise EngineError(msg)
    top = Path(session["toplevel"])
    require_safe_toplevel(top)
    if (
        session.get("status") == "in_progress"
        and guard_check(session_dir, "before-adopt")["violation"]
    ):
        msg = (
            "checkout changed during worker dispatch; "
            "preserve the checkout and worktrees, then stop"
        )
        raise EngineError(msg)
    base = session_dir / pass_name(n)
    picks, deletes = list(picks), list(deletes)
    if whole:
        manifest = json.loads(
            (base / "diffs" / f"{_safe_participant(whole)}.json").read_text(encoding="utf-8")
        )
        picks += [f"{rel}={whole}" for rel in manifest["changed"]]
        deletes += manifest["deleted"]
    sources: dict[str, Path] = {}
    for pick in picks:
        rel, _, participant = pick.rpartition("=")
        rel = _safe_rel(rel)
        src = base / "files" / _safe_participant(participant) / rel
        if not (src.is_symlink() or src.is_file()):
            msg = f"no snapshot of {rel} from {participant} in pass {n}"
            raise EngineError(msg)
        sources[rel] = src
    deletes = [_safe_rel(rel) for rel in deletes]
    paths = [*sources, *deletes]
    conflicts = _adoption_conflicts(top, paths, session)
    if conflicts:
        msg = "refusing to overwrite paths: " + "; ".join(
            f"{path!r}: {reason}" for path, reason in conflicts.items()
        )
        raise EngineError(msg)
    for rel, src in sources.items():
        if src.is_symlink():
            link = _escaping_link(top, rel, src)
            if link is not None:
                msg = (
                    f"refusing to adopt symlink {rel!r} -> {link!r}: it is absolute or"
                    " resolves outside the repository"
                )
                raise EngineError(msg)
    aliases = _user_aliases(top, paths)
    if aliases and not replace_aliases:
        msg = (
            "refusing to replace the user's "
            + "; ".join(f"{kind} {path!r}" for path, kind in aliases.items())
            + "; the user decides, then rerun with --replace-aliases"
        )
        raise EngineError(msg)
    if aliases:
        append_jsonl(
            session_dir / "events.jsonl",
            {"event": "aliases_replaced", "timestamp": stamp(), "paths": aliases},
        )
    copied: list[str] = []
    for rel, src in sources.items():
        (top / rel).parent.mkdir(parents=True, exist_ok=True)
        (top / rel).unlink(missing_ok=True)
        shutil.copy2(src, top / rel, follow_symlinks=False)
        copied.append(rel)
    for rel in deletes:
        (top / rel).unlink(missing_ok=True)
    if copied or deletes:
        session["applied"] = True
        session["applied_paths"] = sorted({*copied, *deletes})
        save_session(session_dir, session)
    return {"ok": True, "copied": copied, "deleted": deletes}


_TRAILER = re.compile(r"^(co-authored-by:|.*generated (with|by)\b)", re.IGNORECASE | re.MULTILINE)


def _commit_git(top: Path, *args: str, index: Path | None = None) -> str:
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in {"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_PREFIX", "GIT_COMMON_DIR"}
    }
    if index is not None:
        env["GIT_INDEX_FILE"] = str(index)
    proc = subprocess.run(  # noqa: S603
        ["git", "--literal-pathspecs", "-C", str(top), *args],  # noqa: S607
        env=env,
        capture_output=True,
        check=False,
    )
    if proc.returncode:
        detail = (proc.stderr or proc.stdout).decode("utf-8", "replace").strip()
        msg = f"git {' '.join(args)}: {detail}"
        raise EngineError(msg)
    return os.fsdecode(proc.stdout).rstrip("\n")


def _validate_commit(scratch: Path, candidate: str, expected: str, captured_tree: str) -> None:
    if _commit_git(scratch, "rev-list", "--parents", "-n", "1", candidate).split() != [
        candidate,
        expected,
    ]:
        msg = "hook changed candidate history"
        raise EngineError(msg)
    if _commit_git(scratch, "rev-parse", f"{candidate}^{{tree}}") != captured_tree:
        msg = "hook changed approved bytes; review the retained worktree"
        raise EngineError(msg)
    if _TRAILER.search(_commit_git(scratch, "show", "-s", "--format=%B", candidate)):
        msg = "hook added a prohibited commit-message trailer"
        raise EngineError(msg)
    if _commit_git(scratch, "status", "--porcelain", "--untracked-files=all"):
        msg = "hook left uncommitted changes; review the retained worktree"
        raise EngineError(msg)


def _expect_commit_source(top: Path, index: Path, prior: bytes, head: str, branch: str) -> None:
    if index.read_bytes() != prior:
        msg = "source index changed while hooks ran; nothing was published"
        raise EngineError(msg)
    if (
        _commit_git(top, "rev-parse", "HEAD") != head
        or _commit_git(top, "symbolic-ref", "HEAD") != branch
    ):
        msg = "source HEAD or branch changed while hooks ran; nothing was published"
        raise EngineError(msg)


def commit_paths(repo: str, message_file: str, paths: Sequence[str]) -> Json:  # noqa: PLR0915
    """Commit named bytes through isolated hooks, preserving the source worktree and other staging.

    Hook changes or concurrent index/HEAD changes retain a recovery worktree.
    Publication requires a branch and no Git operation in progress.
    """
    if not paths:
        msg = "commit needs at least one path"
        raise EngineError(msg)
    message = Path(message_file).read_text(encoding="utf-8")
    if _TRAILER.search(message):
        msg = "commit message carries a Co-Authored-By or 'Generated with' trailer"
        raise EngineError(msg)
    top = Path(_commit_git(Path(repo).resolve(), "rev-parse", "--show-toplevel"))
    require_safe_toplevel(top)
    expected = _commit_git(top, "rev-parse", "--verify", "HEAD^{commit}")
    branch = _commit_git(top, "symbolic-ref", "HEAD")
    index = Path(_commit_git(top, "rev-parse", "--git-path", "index"))
    if not index.is_absolute():
        index = top / index
    head_path = top / _commit_git(top, "rev-parse", "--git-path", "HEAD")
    for operation in (
        "MERGE_HEAD",
        "CHERRY_PICK_HEAD",
        "REVERT_HEAD",
        "rebase-apply",
        "rebase-merge",
    ):
        location = Path(_commit_git(top, "rev-parse", "--git-path", operation))
        if (top / location).exists():
            msg = f"finish the Git operation before committing: {operation}"
            raise EngineError(msg)
    if _commit_git(top, "ls-files", "--unmerged"):
        msg = "resolve the unmerged index before committing"
        raise EngineError(msg)
    rels = list(dict.fromkeys(_safe_rel(p) for p in paths))
    for rel in rels:
        target = top / rel
        if target.is_dir() and not target.is_symlink():
            msg = f"commit needs individual files, not directory {rel!r}"
            raise EngineError(msg)
        if any(parent.is_symlink() for parent in target.parents if top in parent.parents):
            msg = f"commit refuses a symlinked parent of {rel!r}"
            raise EngineError(msg)
    prior_index = index.read_bytes()
    root = aip_root().resolve() / "commit-recovery"
    root.mkdir(parents=True, exist_ok=True)
    recovery = Path(tempfile.mkdtemp(prefix="finding-", dir=root))
    scratch = recovery / "worktree"
    reference = f"refs/weave-commit/{recovery.name}"
    stored_message = recovery / "message.txt"
    stored_message.write_text(message, encoding="utf-8")
    metadata: Json = {"source": str(top), "expected": expected, "branch": branch, "paths": rels}
    temporary: Path | None = None
    published = False
    acquired: list[Path] = []
    cleanup_errors: list[str] = []
    locks = (index.with_name(index.name + ".lock"), head_path.with_name("HEAD.lock"))
    try:
        descriptor, name = tempfile.mkstemp(prefix="weave-index-", dir=index.parent)
        os.close(descriptor)
        temporary = Path(name)
        _commit_git(top, "read-tree", expected, index=temporary)
        _commit_git(top, "add", "--", *rels, index=temporary)
        captured_tree = _commit_git(top, "write-tree", index=temporary)
        _commit_git(top, "worktree", "add", "--detach", "--no-checkout", str(scratch), expected)
        _commit_git(scratch, "read-tree", "--reset", "-u", captured_tree)
        approved = _commit_git(
            scratch, "commit-tree", captured_tree, "-p", expected, "-F", str(stored_message)
        )
        _commit_git(scratch, "update-ref", reference, approved, "")
        metadata.update(approved=approved, recovery_ref=reference, captured_tree=captured_tree)
        (recovery / "recovery.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        _commit_git(scratch, "commit", "--quiet", "-F", str(stored_message))
        candidate = _commit_git(scratch, "rev-parse", "HEAD")
        metadata["candidate"] = candidate
        _validate_commit(scratch, candidate, expected, captured_tree)
        with contextlib.ExitStack() as stack:
            for lock in locks:
                stack.enter_context(lock.open("xb"))
                acquired.append(lock)
            _expect_commit_source(top, index, prior_index, expected, branch)
            shutil.copyfile(index, temporary)
            _commit_git(
                top,
                "-c",
                "core.splitIndex=false",
                "update-index",
                "--no-split-index",
                index=temporary,
            )
            _commit_git(
                top, "restore", "--source", candidate, "--staged", "--", *rels, index=temporary
            )
            shutil.copymode(index, temporary)
            shutil.copyfile(temporary, recovery / "index-after")
            (recovery / "recovery.json").write_text(
                json.dumps(metadata, indent=2), encoding="utf-8"
            )
            # Hooks run in scratch; source working files are never rewritten.
            _commit_git(
                scratch, "update-ref", "-m", "weave: apply finding", branch, candidate, expected
            )
            published = True
            temporary.replace(index)
    except (EngineError, OSError) as exc:
        metadata.update(published=published, error=str(exc))
        with contextlib.suppress(OSError):
            (recovery / "recovery.json").write_text(
                json.dumps(metadata, indent=2), encoding="utf-8"
            )
        state = "commit published; source index may need recovery" if published else "not published"
        msg = f"{exc}; {state}; recovery retained at {recovery}"
        raise EngineError(msg) from exc
    finally:
        for owned in ([temporary] if temporary is not None else []) + acquired:
            try:
                owned.unlink(missing_ok=True)
            except OSError as exc:
                cleanup_errors.append(f"could not remove {owned}: {exc}")
                print(f"weave: {cleanup_errors[-1]}", file=sys.stderr)
    result: Json = {
        "ok": True,
        "commit": candidate,
        "committed": [
            p
            for p in _commit_git(
                top,
                "diff-tree",
                "-z",
                "--no-commit-id",
                "--name-only",
                "-r",
                candidate,
            ).split("\0")
            if p
        ],
        "still_staged": [
            p
            for p in _commit_git(
                top,
                "diff",
                "--cached",
                "--name-only",
                "-z",
            ).split("\0")
            if p
        ],
    }
    if cleanup_errors:
        result["warning"] = "; ".join(cleanup_errors) + f"; recovery retained at {recovery}"
        return result
    try:
        _commit_git(scratch, "update-ref", "-d", reference, approved)
        _commit_git(top, "worktree", "remove", "--force", str(scratch))
        for name in ("message.txt", "recovery.json", "index-after"):
            (recovery / name).unlink()
        recovery.rmdir()
    except (EngineError, OSError) as exc:
        result["warning"] = f"commit published; cleanup failed: {exc}; retained at {recovery}"
    return result


def latest_session(repo: str, command: str) -> Json:
    """Describe the newest ``command`` session of ``repo`` and what it captured.

    ``captured`` maps each participant of the last pass that has diffs to its
    manifest; ``dirty`` lists captured paths the checkout has changed since.
    """
    info = resolve_repo(repo)
    if not info.git:
        msg = f"{command} needs a git repository with at least one commit: {info.reason}."
        raise EngineError(msg)
    origin = git(info.top, "remote", "get-url", "origin", check=False)
    _, _, repo_dir = repo_identity(info.top, origin)
    root = aip_root() / "repos" / repo_dir / "sessions" / command
    link = root / "latest"
    if link.is_symlink() and link.resolve().is_dir():
        sdir = link.resolve()
    else:
        found = sorted(d for d in root.glob("*") if d.is_dir() and not d.is_symlink())
        if not found:
            msg = f"no {command} session recorded for this repository"
            raise EngineError(msg)
        sdir = found[-1]
    session = load_session(sdir)
    passes = sorted(d for d in sdir.glob("pass-*") if (d / "diffs").is_dir())
    captured: Json = {}
    if passes:
        for manifest in sorted((passes[-1] / "diffs").glob("*.json")):
            captured[manifest.stem] = json.loads(manifest.read_text(encoding="utf-8"))
    paths = {p for m in captured.values() for p in m["changed"] + m["deleted"]}
    conflicts = _adoption_conflicts(Path(info.top), sorted(paths), session)
    events = sdir / "events.jsonl"
    text = events.read_text(encoding="utf-8") if events.is_file() else ""
    return {
        "ok": True,
        "session_dir": str(sdir),
        "status": session.get("status"),
        "pass": int(passes[-1].name[5:]) if passes else None,
        "captured": captured,
        "dirty": sorted(conflicts),
        "conflicts": conflicts,
        "applied": bool(session.get("applied"))
        or any(f'"{e}"' in text for e in ("synthesis_applied", "adoption_applied")),
    }


def stash_entry(top: str, sha: str) -> str | None:
    """Return the ``stash@{N}`` ref whose commit is ``sha``."""
    for line in git(top, "stash", "list", "--format=%H %gd").splitlines():
        entry_sha, _, ref = line.partition(" ")
        if entry_sha == sha:
            return ref
    return None


def stash_overlap(top: str, sha: str) -> list[str]:
    """Return the paths both the stash and the working tree changed."""
    held = set(git(top, "diff", "--name-only", f"{sha}^1", sha, check=False).splitlines())
    held |= set(git(top, "ls-tree", "-r", "--name-only", f"{sha}^3", check=False).splitlines())
    dirty = {
        line[3:].split(" -> ")[-1]
        for line in git(top, "status", "--porcelain", "--untracked-files=all").splitlines()
    }
    return sorted(held & dirty)


def restore_stash(session_dir: Path, *, ack_drift: bool = False) -> Json:
    """Pop the session's own stash entry, found by commit, never ``stash@{0}`` blindly.

    Refused while a recorded guard violation lacks the user's decision (``ack_drift``).
    """
    require_drift_decision(session_dir, "stash-restore", acknowledge=ack_drift)
    session = load_session(session_dir)
    top = session["toplevel"]
    stash: Json = session.get("stash") or {}
    if stash.get("state") != "stashed":
        return {"ok": True, "restored": False, "reason": "nothing was stashed"}
    ref = stash_entry(top, stash["sha"])
    if ref is None:
        return {"ok": False, "restored": False, "reason": "stash entry not found"}
    proc = subprocess.run(  # noqa: S603
        ["git", "-C", top, "stash", "pop", "--index", ref],  # noqa: S607
        capture_output=True,
        text=True,
        errors="replace",
        check=False,
    )
    if proc.returncode != 0:
        sha = stash["sha"]
        return {
            "ok": False,
            "restored": False,
            "conflict": True,
            "reason": proc.stderr.strip(),
            "stash_kept": True,
            "stash_sha": sha,
            "overlap": stash_overlap(top, sha),
            "inspect": f"git stash show --patch {sha}",
            "apply": f"git stash apply --index {sha}",
            "apply_fallback": {
                "command": f"git stash apply {sha}",
                "when": "only if --index reports a conflict; staged changes then return unstaged",
            },
            "recover": [
                "git stash push --include-untracked --message weave-synthesis",
                f"git stash apply --index {sha}",
                "git stash show --patch stash@{0}",
            ],
        }
    return {"ok": True, "restored": True}


def update_session(  # noqa: PLR0913
    session_dir: Path,
    *,
    status: str | None,
    completed_passes: int | None,
    event: str | None,
    event_json: str | None,
    drop: Sequence[str],
    sets: Sequence[str],
    link_latest: bool,
) -> Json:
    """Apply session changes, then append the event, in that order."""
    with session_lock(session_dir):
        return _update_session(
            session_dir, status=status, completed_passes=completed_passes, event=event,
            event_json=event_json, drop=drop, sets=sets, link_latest=link_latest,
        )  # fmt: skip


def _update_session(  # noqa: PLR0913
    session_dir: Path,
    *,
    status: str | None,
    completed_passes: int | None,
    event: str | None,
    event_json: str | None,
    drop: Sequence[str],
    sets: Sequence[str],
    link_latest: bool,
) -> Json:
    session = load_session(session_dir)
    if status:
        session["status"] = status
    if completed_passes is not None:
        session["completed_passes"] = completed_passes
    for item in sets:
        key, sep, raw = item.partition("=")
        if not sep or not key:
            msg = f"--set needs key=<json>, got {item!r}"
            raise EngineError(msg)
        try:
            session[key] = json.loads(raw)
        except ValueError as exc:
            msg = f"--set {key}: value is not JSON ({exc})"
            raise EngineError(msg) from exc
    for name in drop:
        session["participants"] = [p for p in session["participants"] if p != name]
        session["executors"].pop(name, None)
        if "models" in session:
            session["models"] = [m for m in session["models"] if not m.startswith(f"{name}:")]
        session.get("chains", {}).pop(name, None)
    save_session(session_dir, session)
    if event:
        try:
            extra: Json = json.loads(event_json) if event_json else {}
        except ValueError as exc:
            msg = f"--event-json is not JSON ({exc})"
            raise EngineError(msg) from exc
        append_jsonl(session_dir / "events.jsonl", {"event": event, "timestamp": stamp(), **extra})
    if link_latest:
        link = session_dir.parent / "latest"
        tmp = session_dir.parent / f".latest.{os.getpid()}"
        tmp.unlink(missing_ok=True)
        tmp.symlink_to(session_dir.name)
        tmp.replace(link)
    return {"ok": True}


def _csv(value: str) -> list[str]:
    return [v for v in value.split(",") if v]


def _timeout_arg(value: str) -> float | None:
    """Parse a timeout argument; ``none`` disables the limit.

    >>> _timeout_arg("none") is None, _timeout_arg("90")
    (True, 90.0)
    """
    return None if value == "none" else float(value)


def _lane_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--variant", type=int, help="variant number; names the lane <lane>-v<N>")
    p.add_argument("--of", type=int, help="variant count, for the 'Variant N of M' prefix")
    p.add_argument("--preamble-file", help="custom variant preamble; default is the built-in one")
    p.add_argument("--judge", action="store_true", help="judge prompt: no role preamble")


_ACK_HELP = "the user decided about the recorded checkout drift; allow this command"


def build_parser() -> argparse.ArgumentParser:  # noqa: PLR0915
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("flags", help="parse flags from stdin; print prompt and settings")
    p.add_argument("--command", choices=sorted(PROFILES), required=True)
    p.add_argument("--default-timeout", type=int, help="override the command's default")

    sub.add_parser("detect", help="report installed model CLIs, lane chains, search tools")

    p = sub.add_parser("init", help="create the session directory and guard snapshot")
    p.add_argument("--command", choices=sorted(PROFILES), required=True)
    p.add_argument("--backend", choices=WORKERS)
    p.add_argument("--bare", action="store_true", help="no workers, no guard snapshot")
    p.add_argument("--prompt-stdin", action="store_true", help="read the user prompt from stdin")
    p.add_argument("--passes", type=int, default=1)
    p.add_argument("--variants", type=int)
    p.add_argument("--timeout", default="default")
    p.add_argument("--mutating", action="store_true", help="stash user changes first")
    p.add_argument("--repo", default=".")

    p = sub.add_parser("context", help="print repo-state packet sections")
    p.add_argument("--repo", default=".")
    p.add_argument("--full-diff", action="store_true", help="append the diff against trunk")
    p.add_argument("--diff-limit", type=int, default=0, help="truncate the diff at N lines")

    p = sub.add_parser("prompt", help="write a worker prompt: preamble, body file, write ban")
    p.add_argument("--lane", required=True)
    p.add_argument("--file", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--mutating", action="store_true")
    _lane_args(p)

    p = sub.add_parser("pass-dir", help="create pass-NNNN for a later pass")
    p.add_argument("--session", required=True)
    p.add_argument("--pass", type=int, required=True, dest="n")

    p = sub.add_parser("labels", help="randomize blind labels and write blind copies")
    p.add_argument("--session", required=True)
    p.add_argument("--pass", type=int, default=1, dest="n")
    p.add_argument("--participants", type=_csv, required=True)
    p.add_argument("--outputs-dir", help="read <participant>.md from here, not pass-NNNN/outputs")

    p = sub.add_parser("dispatch", help="run one model-CLI lane with retry and fallback")
    p.add_argument("--session", required=True)
    p.add_argument("--lane", choices=sorted(LANES), required=True)
    p.add_argument("--pass", type=int, default=1, dest="n")
    p.add_argument("--prompt-file", required=True)
    p.add_argument("--timeout", type=_timeout_arg, default=None, help="seconds or none")
    p.add_argument("--mutating", action="store_true")
    p.add_argument("--out", help="output file, overriding the default location")
    p.add_argument("--stderr", help="stderr file, overriding the default location")
    _lane_args(p)

    p = sub.add_parser("judge-plan", help="pick the judge or panel for a pass")
    p.add_argument("--session", required=True)
    p.add_argument("--mode", choices=["host", "round-robin", "panel"], required=True)
    p.add_argument("--pass", type=int, default=1, dest="n")

    p = sub.add_parser("judge-parse", help="parse a judge file: scores, totals, winner")
    p.add_argument("--file", required=True)
    p.add_argument("--prior", help="prior pass's judge file; reports whether the winner improved")
    p.add_argument("--label-map", help="label-map.json; maps blind labels in the table to ids")

    p = sub.add_parser("panel-merge", help="merge panel judge files by peer-only averaging")
    p.add_argument("--judge", action="append", default=[], help="participant=path, repeated")
    p.add_argument("--label-map", help="label-map.json; maps blind labels in the tables to ids")

    p = sub.add_parser("worktrees", help="create or remove participant worktrees")
    p.add_argument("action", choices=["create", "remove"])
    p.add_argument("--session", required=True)
    p.add_argument("--participants", type=_csv)
    p.add_argument("--base", choices=["pre", "head"], help="default: head if mutating, else pre")
    p.add_argument("--ack-drift", action="store_true", help=_ACK_HELP)

    p = sub.add_parser("participant", help="disposable snapshot for a critic, judge, or agent")
    p.add_argument("action", choices=["start", "finish"])
    p.add_argument("--session", required=True)
    p.add_argument("--name", required=True)

    p = sub.add_parser("claim", help="detach aliases at session paths before a host tool writes")
    p.add_argument("--session", required=True)
    p.add_argument("paths", nargs="+", help="paths relative to the session directory")

    p = sub.add_parser("write", help="write stdin to a session path through an alias-safe replace")
    p.add_argument("--session", required=True)
    p.add_argument("path", help="path relative to the session directory")

    p = sub.add_parser("packet", help="assemble a pass's blind responses into one file")
    p.add_argument("--session", required=True)
    p.add_argument("--pass", type=int, default=1, dest="n")
    p.add_argument("--out", help="output file; default pass-NNNN/packet.md")

    p = sub.add_parser("capture", help="save a participant's patch and file snapshots")
    p.add_argument("--session", required=True)
    p.add_argument("--pass", type=int, default=1, dest="n")
    p.add_argument("--participant", required=True)
    p.add_argument("--tree", help="path to capture instead of the participant's worktree")

    p = sub.add_parser("adopt", help="copy chosen snapshots into the main checkout")
    p.add_argument("--session", required=True)
    p.add_argument("--pass", type=int, default=1, dest="n")
    p.add_argument("--pick", action="append", default=[], help="path=participant")
    p.add_argument("--delete", action="append", default=[], help="path to remove")
    p.add_argument("--all", dest="whole", help="adopt everything this participant captured")
    p.add_argument(
        "--replace-aliases",
        action="store_true",
        help="the user decided to replace their symlinks or hard links",
    )

    p = sub.add_parser("check-paths", help="refuse edit targets with user changes or unsafe paths")
    p.add_argument("--repo", default=".")
    p.add_argument("paths", nargs="+", help="paths relative to the checkout top")

    p = sub.add_parser("commit", help="commit only the named paths, leaving other staged files")
    p.add_argument("--message-file", required=True)
    p.add_argument("--repo", default=".")
    p.add_argument("paths", nargs="+", help="paths relative to the checkout top")

    p = sub.add_parser("latest", help="describe the newest session of a command")
    p.add_argument("--command", choices=sorted(PROFILES), required=True)
    p.add_argument("--repo", default=".")

    p = sub.add_parser("guard", help="compare the checkout with the pre-dispatch snapshot")
    p.add_argument("action", choices=["check", "resolve", "finish", "prune"])
    p.add_argument("--session")
    p.add_argument("--label", default="check")
    p.add_argument("--choice", choices=["keep", "revert", "quarantine"], default="keep")
    p.add_argument("--days", type=float, default=14)
    p.add_argument("--repo", default=".")

    p = sub.add_parser("stash-restore", help="pop the session's own stash")
    p.add_argument("--session", required=True)
    p.add_argument("--ack-drift", action="store_true", help=_ACK_HELP)

    p = sub.add_parser("update", help="update session.json and append an event")
    p.add_argument("--session", required=True)
    p.add_argument("--status")
    p.add_argument("--completed-passes", type=int)
    p.add_argument("--event")
    p.add_argument("--event-json")
    p.add_argument("--drop", type=_csv, default=[])
    p.add_argument("--set", action="append", default=[], dest="sets", help="key=<json>")
    p.add_argument("--link-latest", action="store_true")
    return parser


def _read_preamble(args: argparse.Namespace) -> str | None:
    path = getattr(args, "preamble_file", None)
    return " ".join(Path(path).read_text(encoding="utf-8").split()) if path else None


def _guard_command(args: argparse.Namespace) -> Json:
    if args.action == "prune":
        return guard_prune(args.repo, args.days)
    if not args.session:
        msg = "guard needs --session"
        raise EngineError(msg)
    session_dir = Path(args.session)
    if args.action == "check":
        return guard_check(session_dir, args.label)
    if args.action == "resolve":
        return guard_resolve(session_dir, args.choice)
    return guard_finish(session_dir)


def context_doc(repo: str, *, full_diff: bool, diff_limit: int) -> Json:
    """Return the ``context`` command's JSON; no-repo mode reports the reason instead."""
    info = resolve_repo(repo)
    if not info.git:
        note = f"No repository: {info.reason}. There is no repo state or diff to report."
        return {
            "ok": True,
            "repo": False,
            "trunk": None,
            "base": None,
            "branch": "",
            "commits": [],
            "markdown": f"## Repo state\n\n{note}\n",
        }
    top = info.top
    trunk = detect_trunk(top)
    base = compare_base(top, trunk)
    log = git(top, "log", "--oneline", f"{base}..HEAD", check=False) if base else ""
    commits = log.splitlines()
    return {
        "ok": True,
        "repo": True,
        "trunk": trunk,
        "base": base,
        "branch": git(top, "branch", "--show-current"),
        "commits": commits,
        "markdown": context_sections(top, full_diff=full_diff, diff_limit=diff_limit),
    }


def _label_map(path: str | None) -> dict[str, str] | None:
    if not path:
        return None
    return t.cast("dict[str, str]", json.loads(Path(path).read_text(encoding="utf-8")))


def run(args: argparse.Namespace) -> Json:  # noqa: PLR0911, PLR0915
    """Execute a parsed command."""
    cmd = args.cmd
    if cmd == "flags":
        doc = parse_flags(sys.stdin.read(), args.command, default_timeout=args.default_timeout)
        doc["ok"] = not doc["errors"]
        return doc
    if cmd == "detect":
        return {"ok": True, **detect()}
    if cmd == "context":
        return context_doc(args.repo, full_diff=args.full_diff, diff_limit=args.diff_limit)
    if cmd == "init":
        summary = " ".join(sys.stdin.read().split()) if args.prompt_stdin else ""
        return init_session(
            command=args.command, backend=args.backend, repo=args.repo,
            prompt_summary=summary, passes=args.passes, timeout=args.timeout,
            mutating=args.mutating, variants=args.variants, bare=args.bare,
        )  # fmt: skip
    if cmd == "prompt":
        body = Path(args.file).read_text(encoding="utf-8")
        out = Path(args.out)
        out.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        variant = (args.variant, args.of or args.variant) if args.variant else None
        text = compose_prompt(
            args.lane, body, mutating=args.mutating, variant=variant,
            preamble=_read_preamble(args), role=not (args.judge or variant),
        )  # fmt: skip
        write_atomic(out, text)
        return {"ok": True, "path": str(out)}
    if cmd == "commit":
        return commit_paths(args.repo, args.message_file, args.paths)
    if cmd == "check-paths":
        info = resolve_repo(args.repo)
        if not info.git:
            raise EngineError(info.reason or "not a project checkout")
        conflicts = _path_conflicts(Path(info.top), args.paths, editing=True)
        return {"ok": not conflicts, "clean": not conflicts, "conflicts": conflicts}
    if cmd == "latest":
        return latest_session(args.repo, args.command)
    if cmd == "guard":
        return _guard_command(args)
    if cmd == "panel-merge":
        pairs = [j.partition("=") for j in args.judge]
        if any(not sep or not name for name, sep, _ in pairs):
            msg = "--judge needs participant=path"
            raise EngineError(msg)
        return merge_panel(
            {name: Path(path) for name, _, path in pairs}, _label_map(args.label_map)
        )
    if cmd == "judge-parse":
        labels = _label_map(args.label_map)
        doc = parse_judge(Path(args.file).read_text(encoding="utf-8"), labels)
        if args.prior:
            prior = parse_judge(Path(args.prior).read_text(encoding="utf-8"), labels)
            doc["prior_winner_score"] = prior.get("winner_score")
            if doc.get("winner_score") is not None and prior.get("winner_score") is not None:
                doc["not_improved"] = doc["winner_score"] <= prior["winner_score"]
        return doc
    session_dir = Path(args.session)
    if cmd == "pass-dir":
        return make_pass(session_dir, args.n)
    if cmd == "labels":
        outputs = Path(args.outputs_dir) if args.outputs_dir else None
        return label_participants(session_dir, args.n, args.participants, outputs=outputs)
    if cmd == "dispatch":
        task = lane_task(
            session_dir, args.lane, n=args.n, variant=args.variant, of=args.of, judge=args.judge,
            preamble=_read_preamble(args),
            out=Path(args.out) if args.out else None,
            err=Path(args.stderr) if args.stderr else None,
        )  # fmt: skip
        return dispatch_lane(
            session_dir, args.lane, n=args.n, prompt_file=Path(args.prompt_file),
            timeout=args.timeout, mutating=args.mutating, task=task,
        )  # fmt: skip
    if cmd == "judge-plan":
        return plan_judges(session_dir, args.mode, args.n)
    if cmd == "worktrees":
        if args.action == "create":
            return create_worktrees(session_dir, args.participants or [], base=args.base)
        return remove_worktrees(session_dir, args.participants, ack_drift=args.ack_drift)
    if cmd == "participant":
        if args.action == "start":
            return start_participant(session_dir, args.name)
        return finish_participant(session_dir, args.name)
    if cmd == "claim":
        return {
            "ok": True,
            "paths": [str(claim_session_path(session_dir, rel)) for rel in args.paths],
        }
    if cmd == "write":
        return write_session_file(session_dir, args.path, sys.stdin.buffer.read())
    if cmd == "packet":
        return synthesis_packet(session_dir, args.n, Path(args.out) if args.out else None)
    if cmd == "capture":
        return capture_tree(session_dir, args.n, args.participant, args.tree)
    if cmd == "adopt":
        return adopt_files(
            session_dir,
            args.n,
            args.pick,
            args.delete,
            args.whole,
            replace_aliases=args.replace_aliases,
        )
    if cmd == "stash-restore":
        return restore_stash(session_dir, ack_drift=args.ack_drift)
    return update_session(
        session_dir, status=args.status, completed_passes=args.completed_passes,
        event=args.event, event_json=args.event_json, drop=args.drop, sets=args.sets,
        link_latest=args.link_latest,
    )  # fmt: skip


def _describe(exc: Exception) -> str:
    if isinstance(exc, KeyError):
        return f"missing key {exc} in session data or input"
    if isinstance(exc, OSError) and exc.filename:
        return f"{exc.strerror or type(exc).__name__}: {exc.filename}"
    return str(exc) or type(exc).__name__


def main(argv: Sequence[str] | None = None) -> int:
    """Command-line entry point."""
    args = build_parser().parse_args(argv)
    try:
        doc = run(args)
    except (EngineError, OSError, KeyError, ValueError) as exc:
        emit({"ok": False, "error": _describe(exc)})
        return 1
    if doc:
        emit(doc)
    return 0 if doc.get("ok", True) else 1


if __name__ == "__main__":
    sys.exit(main())
