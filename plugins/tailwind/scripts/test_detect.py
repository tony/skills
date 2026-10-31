"""Positive and negative fixtures for each detect pattern."""

# ruff: noqa: S101, S603, INP001, D103, PLR2004
# pyright: reportUnusedCallResult=false

import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest
from detect import (  # pyright: ignore[reportImplicitRelativeImport]
    PATTERNS,
    find,
    tailwind_version,
)

SCRIPT = Path(__file__).with_name("detect.py")

CASES: list[tuple[str, str, bool]] = [
    ("margin", '<a className="px-2 me-4">', True),
    ("margin", '<a className="-ml-2 px-2">', True),
    ("margin", '<a class="ms-[3px]">', True),
    ("margin", '<a className="ml-px">', True),
    ("margin", '<a className="!me-4">', True),
    ("margin", '<a className="mx-auto px-2">', False),
    ("margin", '<a className="m-4">', True),
    ("margin", '<a className="-m-2">', True),
    ("margin", '<a className="m-[10px]">', True),
    ("margin", '<a className="mt-4 my-2 m-auto">', False),
    ("margin-in-gap", '<div className="flex gap-2"><a className="m-4">', True),
    ("vmargin", '<div className="flex flex-col gap-3"><p className="mt-4">', True),
    ("vmargin", '<ul className="md:grid grid-cols-2"><li className="-mb-2">', True),
    ("vmargin", '<div className="flex gap-3"><p className="mt-4">', False),
    ("vmargin", '<div className="flex-col"><p className="mt-auto my-auto">', False),
    ("vmargin", '<div className="grid-cols-2"><p className="mt-4">', False),
    ("margin-in-gap", '<div className="flex gap-3"><a className="me-4">', True),
    ("margin-in-gap", '<div className="flex-col gap-3"><a className="my-2">', True),
    ("margin-in-gap", '<div className="flex gap-3"><a className="my-2">', False),
    ("margin-in-gap", '<div className="flex"><a className="me-4">', False),
    ("margin", '<a className="some-ml-2">', False),
    ("gap", '<div className="flex gap-3">', True),
    ("gap", '<div className="flex gap-x-[3px]">', True),
    ("gap", '<div className="flex gap-px">', True),
    ("gap", '<div className="flex">', False),
    ("gap", '<div className="biggap-3">', False),
    ("width", '<button className="h-8 w-24">', True),
    ("width", '<button className="w-[10rem]">', True),
    ("width", '<button className="min-w-24 max-w-24">', False),
    ("width", '<button className="w-full w-auto">', False),
    ("interactive", '<button className="px-2">', True),
    ("interactive", '<button\n  onClick={() => x()}\n  className="px-4"\n>', True),
    ("interactive", '<IconButton className="px-2">', True),
    ("interactive", '<article className="px-2">', False),
    ("interactive", '<Action className="px-2">', False),
    ("wrapper", '<div className="flex h-full items-center">', True),
    ("wrapper", '<div className="items-center flex">', True),
    ("wrapper", '<div className={cn("flex items-center", x)}>', True),
    ("wrapper", '<div className="inline-flex items-center">', False),
    ("wrapper", '<div className="flex flex-col place-items-center">', False),
    ("space-gap", '<div className="flex gap-2 space-x-3">', True),
    ("space-gap", '<div className="space-y-2 flex gap-y-1">', True),
    ("space-gap", "<div className={`flex gap-2 ${a} space-x-3`}>", True),
    ("space-gap", '<div className="flex gap-2">', False),
    ("space-gap", '<div className="space-x-3">', False),
    ("space-gap", 'cn("flex gap-2", "space-x-3")', False),
    ("space", '<div className="space-x-3">', True),
    ("space", 'cn("flex gap-2", "space-y-[3px]")', True),
    ("space", '<div className="flex gap-2">', False),
    ("space", '<div className="space-x-reverse">', False),
    ("margin", '<a className="me-(--gap)">', True),
    ("margin", '<a className="-ms-(--gap)">', True),
    ("margin", '<a className="m-(foo)">', False),
    ("gap", '<div className="flex gap-(--g)">', True),
    ("gap", '<div className="flex gap-x-(--g)">', True),
    ("width", '<button className="w-(--w)">', True),
    ("width", '<button className="!w-24">', True),
    ("space", '<div className="space-x-(--s)">', True),
    ("space-gap", '<div className="flex gap-(--g) space-x-(--s)">', True),
]


@pytest.mark.parametrize(("pattern", "text", "hit"), CASES)
def test_fixture(pattern: str, text: str, hit: bool) -> None:
    assert bool(find(pattern, text)) is hit


def test_line_number_counts_multiline_tag() -> None:
    text = 'x\n<button\n  onClick={() => y()}\n  className="px-2"\n>'
    assert find("interactive", text)[0][0] == 2


@pytest.mark.parametrize(
    "text",
    [
        '<div className="' + "flex gap-2 space-x-2 " * 5000,
        "<div " * 20000,
        "<a " * 33000,
    ],
)
def test_long_input_scans_fast(text: str) -> None:
    start = time.perf_counter()
    for pattern in PATTERNS:
        find(pattern, text)
    # Backtracking on these inputs runs for minutes; the slack absorbs CI load.
    assert time.perf_counter() - start < 5.0


def test_missing_path_exits_two(tmp_path: Path) -> None:
    script = SCRIPT
    run = subprocess.run(
        [sys.executable, str(script), "margin", str(tmp_path / "nope")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 2
    assert "no such path" in run.stderr


def test_cli_exit_codes(tmp_path: Path) -> None:
    (tmp_path / "a.tsx").write_text('<a className="me-4">')
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "b.tsx").write_text('<a className="me-4">')
    script = SCRIPT
    hit = subprocess.run(
        [sys.executable, str(script), "margin", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert hit.returncode == 0
    assert hit.stdout.count("\n") == 1
    miss = subprocess.run(
        [sys.executable, str(script), "gap", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert miss.returncode == 1


def test_margin_in_gap_caps_hits(tmp_path: Path) -> None:
    (tmp_path / "a.tsx").write_text('<div className="flex gap-2">' + '<a className="me-4"/>\n' * 80)
    script = SCRIPT
    run = subprocess.run(
        [sys.executable, str(script), "margin-in-gap", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 0
    assert run.stdout.count("\n") == 50
    assert "stopped at 50 hits" in run.stderr
    assert "a.tsx: 50" in run.stderr


@pytest.mark.parametrize(
    "ext",
    [
        ".tsx",
        ".jsx",
        ".vue",
        ".svelte",
        ".astro",
        ".html",
        ".erb",
        ".blade.php",
        ".php",
        ".twig",
        ".njk",
        ".hbs",
        ".heex",
        ".mdx",
        ".liquid",
    ],
)
def test_every_extension_is_scanned(tmp_path: Path, ext: str) -> None:
    (tmp_path / f"page{ext}").write_text('<a class="me-4">')
    run = subprocess.run(
        [sys.executable, str(SCRIPT), "margin", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 0
    assert f"page{ext}:1:me-4" in run.stdout


@pytest.mark.parametrize(
    "skipped", ["node_modules", ".git", "dist", "build", ".next", ".nuxt", "vendor"]
)
def test_skip_dir_below_root_is_skipped(tmp_path: Path, skipped: str) -> None:
    (tmp_path / skipped / "deep").mkdir(parents=True)
    (tmp_path / skipped / "deep" / "a.tsx").write_text('<a className="me-4">')
    run = subprocess.run(
        [sys.executable, str(SCRIPT), "margin", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 1


@pytest.mark.parametrize("ancestor", ["build", "dist", "node_modules", "vendor"])
def test_skip_dir_named_ancestor_of_root_is_scanned(tmp_path: Path, ancestor: str) -> None:
    root = tmp_path / ancestor / "src"
    root.mkdir(parents=True)
    (root / "a.tsx").write_text('<a className="me-4">')
    run = subprocess.run(
        [sys.executable, str(SCRIPT), "margin", str(root)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 0
    assert "a.tsx:1:me-4" in run.stdout


PNPM_IMPORTER = "importers:\n  .:\n    dependencies:\n      tailwindcss:\n        specifier: ^3.4.0\n        version: 3.4.17\n"  # noqa: E501
VERSION_FIXTURES: list[tuple[dict[str, str], str]] = [
    (
        {"package-lock.json": '{"packages":{"node_modules/tailwindcss":{"version":"3.4.1"}}}'},
        "version: 3 (package-lock.json)",
    ),
    (
        {"pnpm-lock.yaml": "packages:\n  tailwindcss@4.0.2:\n    resolution: {}\n"},
        "version: 4 (pnpm-lock.yaml)",
    ),
    (
        {"pnpm-lock.yaml": PNPM_IMPORTER},
        "version: 3 (pnpm-lock.yaml)",
    ),
    (
        {"yarn.lock": 'tailwindcss@^3.0.0:\n  version "3.4.3"\n'},
        "version: 3 (yarn.lock)",
    ),
    (
        {"bun.lock": '"tailwindcss": ["tailwindcss@4.1.0", "", {}]'},
        "version: 4 (bun.lock)",
    ),
    (
        {"package.json": '{"devDependencies":{"tailwindcss":"^3.4.0"}}'},
        "version: 3 (package.json)",
    ),
    (
        {"package.json": '{"dependencies":{"tailwindcss":"~4"}}'},
        "version: 4 (package.json)",
    ),
    ({"app.css": '@import "tailwindcss";'}, "version: 4 (app.css)"),
    ({"app.css": "@tailwind base;\n@tailwind utilities;"}, "version: 3 (app.css)"),
    (
        {
            "package-lock.json": '{"packages":{"node_modules/tailwindcss":{"version":"4.0.0"}}}',
            "package.json": '{"dependencies":{"tailwindcss":"^3"}}',
        },
        "version: 4 (package-lock.json)",
    ),
    (
        {"tailwind.config.js": "module.exports = {}", "package.json": "{}"},
        "version: unknown",
    ),
    ({"package.json": '{"dependencies":{"tailwindcss":"latest"}}'}, "version: unknown"),
]


@pytest.mark.parametrize(("files", "expected"), VERSION_FIXTURES)
def test_version_mode(tmp_path: Path, files: dict[str, str], expected: str) -> None:
    for name, body in files.items():
        (tmp_path / name).write_text(body)
    run = subprocess.run(
        [sys.executable, str(SCRIPT), "version", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.stdout.strip() == expected
    assert run.returncode == (1 if expected.endswith("unknown") else 0)


def test_version_config_file_is_not_a_signal(tmp_path: Path) -> None:
    (tmp_path / "tailwind.config.ts").write_text("export default {}")
    assert tailwind_version(tmp_path) is None


def test_version_missing_directory_exits_two(tmp_path: Path) -> None:
    run = subprocess.run(
        [sys.executable, str(SCRIPT), "version", str(tmp_path / "nope")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 2
    assert "no such directory" in run.stderr


PATTERNS_MD = Path(__file__).parents[1] / "skills" / "spacing-audit" / "references" / "patterns.md"
FALLBACK_BLOCK = re.compile(
    r"detect\.py> \\\n\s+(\S+) \\\n.*?```\n.*?```console\n(\$ rg.*?)```", re.DOTALL
)
FALLBACK_REGEX = re.compile(r"-e '([^\n]*)' \\\n")


@pytest.mark.skipif(shutil.which("rg") is None, reason="needs ripgrep")
@pytest.mark.parametrize("name", ["margin", "width", "space"])
def test_rg_fallback_matches_script(tmp_path: Path, name: str) -> None:
    blocks = {m.group(1): m.group(2) for m in FALLBACK_BLOCK.finditer(PATTERNS_MD.read_text())}
    regexes: list[str] = FALLBACK_REGEX.findall(blocks[name])
    texts = [t for p, t, _ in CASES if p == name] + [
        '<a className="!me-4">',
        '<a className="md:-ms-(--x)">',
        '<a className="m-(--x)">',
        '<a className="!w-24">',
        '<a className="w-(--w)">',
        '<a className="!space-x-3">',
        '<a className="space-x-(--s)">',
        '<a className="plain">',
    ]
    sample = tmp_path / "a.tsx"
    sample.write_text("\n".join(texts) + "\n")
    rg = subprocess.run(
        [
            str(shutil.which("rg")),
            "--line-number",
            "--no-heading",
            *[a for r in regexes for a in ("-e", r)],
            str(sample),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    rg_lines = {int(line.split(":", 1)[0]) for line in rg.stdout.splitlines()}
    script_lines = {i + 1 for i, t in enumerate(texts) if find(name, t)}
    assert rg_lines == script_lines
