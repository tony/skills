"""Tests for deps.py: scan, URL vetting, planning, resolution, clone, worktree, report.

Runs offline; clones come from local repositories in tmp_path that stand in for an
https remote through git's url.<base>.insteadOf rewrite.
"""

# ruff: noqa: S101, S603, INP001, D101, D102, D103, D105, ARG001, PLR2004, SLF001, EM101, ANN401, PYI034

import gzip
import io
import json
import subprocess
import sys
import tarfile
import typing as t

import deps
import pytest

if t.TYPE_CHECKING:
    from pathlib import Path

REMOTE = "https://github.com/o/r"
GIT_ENV = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.com",
}


def cli(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, dict[str, t.Any], str]:
    code = deps.main(list(argv))
    captured = capsys.readouterr()
    return code, json.loads(captured.out), captured.err


def sh(cwd: Path, *argv: str) -> str:
    done = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, check=True)
    return done.stdout.strip()


@pytest.fixture
def source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Build a repository with an annotated tag v1.0.0 on the first commit and a second on main."""
    for key, value in GIT_ENV.items():
        monkeypatch.setenv(key, value)
    src = tmp_path / "src"
    src.mkdir()
    sh(src, "git", "init", "-q", "-b", "main")
    (src / "a.txt").write_text("1")
    sh(src, "git", "add", ".")
    sh(src, "git", "commit", "-q", "-m", "one")
    sh(src, "git", "tag", "-a", "v1.0.0", "-m", "v1.0.0")
    (src / "a.txt").write_text("2")
    sh(src, "git", "commit", "-q", "-am", "two")
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", f"url.{src}.insteadOf")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", REMOTE)
    return src


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return tmp_path / "study"


# --- URL vetting ---------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        "git+https://github.com/colinhacks/zod.git",
        "https://github.com/colinhacks/zod.git",
        "https://GitHub.com/colinhacks/zod/",
    ],
)
def test_url_accepts_https_and_git_plus_https(raw: str, capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = cli(capsys, "url", raw)
    assert code == 0
    assert out["url"] == "https://github.com/colinhacks/zod"
    assert out["repo_name"] == "zod"
    assert out["needs_confirmation"] is False


@pytest.mark.parametrize(
    ("raw", "reason"),
    [
        ("ssh://git@code.example.net/fastframe/fastframe.git", "scheme 'ssh' is not https"),
        ("git+ssh://git@github.com/stevemao/left-pad.git", "scheme 'ssh' is not https"),
        ("git://github.com/a/b.git", "scheme 'git' is not https"),
        ("file:///srv/repo", "scheme 'file' is not https"),
        ("ext::sh -c id", "not an https:// URL"),
        ("git@github.com:a/b.git", "not an https:// URL"),
        ("https://user:pw@github.com/a/b", "URL carries credentials"),
        ("https://github.com/onlyowner", "not of the form"),
        ("https://github.com/a/b%0a", "characters outside"),
    ],
)
def test_url_refuses_with_reason(raw: str, reason: str, capsys: pytest.CaptureFixture[str]) -> None:
    code, out, err = cli(capsys, "url", raw)
    assert code == deps.EXIT_REFUSED
    assert out["ok"] is False
    assert reason in out["error"]
    assert err.strip() == f"refused: {out['error']}"


def test_url_unknown_host_needs_confirmation(capsys: pytest.CaptureFixture[str]) -> None:
    _, out, _ = cli(capsys, "url", "https://git.example.net/a/b.git")
    assert out["needs_confirmation"] is True
    _, out, _ = cli(
        capsys, "url", "https://git.example.net/a/b", "--confirmed-host", "git.example.net"
    )
    assert out["needs_confirmation"] is False


# --- sanitizing and planning -----------------------------------------------------


@pytest.mark.parametrize("lang", ["../..", "..", ".hidden", "a..b", ""])
def test_plan_refuses_unsafe_language(
    lang: str, root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out, _ = cli(capsys, "plan", "--root", str(root), "--lang", lang, "--url", REMOTE)
    assert code == deps.EXIT_REFUSED
    assert "language" in out["error"]


def test_plan_refuses_unplain_version(root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    args = ("--root", str(root), "--lang", "python", "--url", REMOTE, "--version=1.0/x")
    code, out, _ = cli(capsys, "plan", *args)
    assert code == deps.EXIT_REFUSED
    assert out["error"] == "version '1.0/x' is not a plain version string"


def test_plan_classifies_new_update_exists_and_rejects_foreign_origin(
    source: Path, root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    args = ("--root", str(root), "--lang", "python", "--url", REMOTE, "--version", "1.0.0")
    assert cli(capsys, "plan", *args)[1]["action"] == "new"
    assert cli(capsys, "clone", "--root", str(root), "--lang", "python", "--url", REMOTE)[0] == 0
    assert cli(capsys, "plan", *args)[1]["action"] == "update"
    (root / "python" / "r-1.0.0").mkdir()
    assert cli(capsys, "plan", *args)[1]["action"] == "exists"
    other = ("--root", str(root), "--lang", "python", "--url", "https://github.com/x/r")
    code, out, _ = cli(capsys, "plan", *other)
    assert code == deps.EXIT_REFUSED
    assert out["error"] == "directory holds another repository"


# --- clone, resolve, worktree ------------------------------------------------------


def test_clone_then_fetch_reports_head(
    source: Path, root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    args = ("--root", str(root), "--lang", "python", "--url", REMOTE)
    code, out, _ = cli(capsys, "clone", *args)
    assert code == 0
    assert out["action"] == "cloned"
    assert out["head"] == sh(source, "git", "rev-parse", "HEAD")
    assert cli(capsys, "clone", *args)[1]["action"] == "fetched"


def test_clone_refuses_unconfirmed_host(root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    args = ("--root", str(root), "--lang", "go", "--url", "https://git.example.net/a/b")
    code, out, _ = cli(capsys, "clone", *args)
    assert code == deps.EXIT_REFUSED
    assert out["error"] == "host git.example.net is not confirmed"
    assert not root.exists()


LS_REMOTE = (
    "a1\trefs/heads/main\n"
    "a2\trefs/heads/release/5.2\n"
    "a3\trefs/tags/v5.2.0\n"
    "a4\trefs/tags/5.2.0\n"
    "a5\trefs/tags/@scope/pkg@5.2.0\n"
    "a6\trefs/tags/pkg-v5.2.0\n"
    "t1\trefs/tags/v9.0.0\n"
    "t2\trefs/tags/v9.0.0^{}\n"
)


@pytest.mark.parametrize(
    ("package", "version", "match", "ref", "commit"),
    [
        ("@scope/pkg", "5.2.0", "tag", "5.2.0", "a4"),
        ("pkg", "9.0.0", "tag", "v9.0.0", "t2"),
        ("pkg", "5.2.1", "branch", "release/5.2", "a2"),
        ("@scope/pkg", "7.0.0", "none", None, None),
    ],
)
def test_resolve_cascade(  # noqa: PLR0913, PLR0917
    package: str,
    version: str,
    match: str,
    ref: str | None,
    commit: str | None,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    refs = tmp_path / "refs.txt"
    refs.write_text(LS_REMOTE)
    _, out, _ = cli(
        capsys, "resolve", "--package", package, "--version", version, "--ls-remote", str(refs)
    )
    assert (out["match"], out["ref"], out["commit"]) == (match, ref, commit)


def test_resolve_prefers_exact_over_v_prefix_and_scoped_forms() -> None:
    assert deps.resolve("pkg", "5.2.0", LS_REMOTE)["ref"] == "5.2.0"
    without_exact = LS_REMOTE.replace("refs/tags/5.2.0", "refs/tags/x")
    assert deps.resolve("pkg", "5.2.0", without_exact)["ref"] == "v5.2.0"
    only_crate = "c1\trefs/tags/pkg-v5.2.0\nc2\trefs/tags/pkg-5.2.0\n"
    assert deps.resolve("pkg", "5.2.0", only_crate)["ref"] == "pkg-v5.2.0"


def worktree_args(root: Path, *extra: str) -> tuple[str, ...]:
    return ("worktree", "--root", str(root), "--lang", "python", "--url", REMOTE, *extra)


def test_pinned_worktree_reads_back_tag_commit(
    source: Path, root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cli(capsys, "clone", "--root", str(root), "--lang", "python", "--url", REMOTE)
    tag_commit = sh(source, "git", "rev-parse", "v1.0.0^{commit}")
    code, out, _ = cli(capsys, *worktree_args(root, "--version", "1.0.0", "--tag", "v1.0.0"))
    assert code == 0
    assert (out["status"], out["commit"], out["tag_check"]) == ("pinned", tag_commit, "unchecked")
    assert (root / "python" / "r-1.0.0" / "a.txt").read_text() == "1"
    code, again, _ = cli(capsys, *worktree_args(root, "--version", "1.0.0", "--tag", "v1.0.0"))
    assert (again["status"], again["reason"], again["commit"]) == (
        "skipped",
        "worktree exists",
        tag_commit,
    )


@pytest.mark.parametrize(
    ("registry", "expected"),
    [("{tag}", "matches"), ("{tag7}", "matches"), ("0" * 40, "differs")],
)
def test_tag_check_compares_registry_commit(
    registry: str,
    expected: str,
    source: Path,
    root: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cli(capsys, "clone", "--root", str(root), "--lang", "python", "--url", REMOTE)
    tag = sh(source, "git", "rev-parse", "v1.0.0^{commit}")
    value = registry.format(tag=tag, tag7=tag[:7])
    _, out, _ = cli(
        capsys,
        *worktree_args(root, "--version", "1.0.0", "--tag", "v1.0.0", "--registry-commit", value),
    )
    assert out["tag_check"] == expected


def test_unpinned_default_branch_worktree_is_named_for_branch_and_sha(
    source: Path, root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cli(capsys, "clone", "--root", str(root), "--lang", "python", "--url", REMOTE)
    head = sh(source, "git", "rev-parse", "HEAD")
    _, out, _ = cli(capsys, *worktree_args(root, "--version", "9.9.9"))
    assert (out["status"], out["branch"], out["commit"]) == ("unpinned", "main", head)
    assert out["worktree"].endswith(f"/python/r-main-{head[:7]}")
    assert out["tag_check"] is None


def test_worktree_refuses_tag_and_branch_together_and_bad_registry_commit(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    both = worktree_args(root, "--version", "1", "--tag", "a", "--branch", "b")
    assert cli(capsys, *both)[1]["error"] == "give --tag or --branch, not both"
    bad = worktree_args(root, "--version", "1", "--tag", "a", "--registry-commit", "$(id)")
    assert cli(capsys, *bad)[1]["error"] == "registry commit is not a hex commit id"


# --- scan ---------------------------------------------------------------------------


def names(found: list[dict[str, t.Any]]) -> dict[str, tuple[t.Any, ...]]:
    return {d["name"]: (d["category"], d["constraint"], d["version"]) for d in found}


def test_scan_npm_prefers_lockfile_version(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "package.json").write_text(
        json.dumps({"dependencies": {"zod": "^3.22.0"}, "devDependencies": {"vite": "^5.0.0"}})
    )
    (tmp_path / "package-lock.json").write_text(
        json.dumps({"packages": {"node_modules/zod": {"version": "3.23.8"}}})
    )
    _, out, _ = cli(capsys, "scan", "--project", str(tmp_path))
    assert names(out["dependencies"]) == {"zod": ("runtime", "^3.22.0", "3.23.8")}
    assert out["skipped"] == [
        {
            "category": "dev",
            "ecosystem": "npm",
            "manifest": "package.json",
            "name": "vite",
            "status": "skipped",
            "reason": "no resolved version",
        }
    ]
    _, only, _ = cli(capsys, "scan", "--project", str(tmp_path), "--filter", "dev")
    assert only["dependencies"] == []
    assert [d["name"] for d in only["skipped"]] == ["vite"]


INJECTION = "x$(touch${IFS}Z)"


def test_scan_never_offers_unplain_names_or_versions(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "package.json").write_text(
        json.dumps(
            {
                "dependencies": {INJECTION: "1.0.0", "`id`": "1", "ok": "1", "bad-ver": "1"},
                "devDependencies": {"-rf": "1", "a;b": "1"},
            }
        )
    )
    (tmp_path / "package-lock.json").write_text(
        json.dumps(
            {
                "packages": {
                    f"node_modules/{INJECTION}": {"version": "1.0.0"},
                    "node_modules/ok": {"version": "1.0.0"},
                    "node_modules/bad-ver": {"version": "1.0.0;id"},
                }
            }
        )
    )
    code, out, _ = cli(capsys, "scan", "--project", str(tmp_path))
    assert code == 0
    assert [d["name"] for d in out["dependencies"]] == ["ok"]
    reasons = sorted(str(d["reason"]) for d in out["skipped"])
    assert reasons.count(deps.NOT_PLAIN_NAME) == 4
    assert reasons.count(deps.NOT_PLAIN_VERSION) == 1
    text = json.dumps(out)
    for raw in ("touch", "IFS", "`id`", "-rf", "a;b", "1.0.0;id"):
        assert raw not in text


def test_scan_blanks_a_constraint_with_shell_syntax(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "package.json").write_text(json.dumps({"dependencies": {"ok": "$(id)"}}))
    (tmp_path / "package-lock.json").write_text(
        json.dumps({"packages": {"node_modules/ok": {"version": "1.0.0"}}})
    )
    _, out, _ = cli(capsys, "scan", "--project", str(tmp_path))
    assert out["dependencies"][0]["constraint"] == ""


def test_scan_returns_declared_repositories_vetted(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    deps_in = {
        "a": "git+https://github.com/o/a.git#v1",
        "b": "git+ssh://git@github.com/o/b.git",
        "c": "github:o/c#main",
        "d": "git+https://evil.example.com/o/d$(id).git",
        "e": "^1.0.0",
    }
    (tmp_path / "package.json").write_text(json.dumps({"dependencies": deps_in}))
    (tmp_path / "package-lock.json").write_text(
        json.dumps({"packages": {f"node_modules/{n}": {"version": "1.0.0"} for n in deps_in}})
    )
    (tmp_path / "go.mod").write_text("require github.com/google/uuid v1.6.0\n")
    _, out, _ = cli(capsys, "scan", "--project", str(tmp_path))
    repos = {d["name"]: d["repository"] for d in out["dependencies"]}
    assert repos["a"]["url"] == "https://github.com/o/a"
    assert repos["b"] == {"url": None, "error": "scheme 'ssh' is not https"}
    assert repos["c"]["url"] == "https://github.com/o/c"
    assert repos["d"]["url"] is None
    assert "$(id)" not in json.dumps(out)
    assert repos["e"] is None
    assert repos["github.com/google/uuid"]["url"] == "https://github.com/google/uuid"


def test_scan_python_normalizes_names_and_groups(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\ndependencies = [\n  "Typing_Extensions>=4",\n'
        "  \"requests[socks]>=2.30; python_version>'3'\",\n]\n"
        '[dependency-groups]\ndev = ["pytest>=8"]\n'
        '[build-system]\nrequires = ["hatchling"]\n'
    )
    (tmp_path / "uv.lock").write_text(
        '[[package]]\nname = "typing-extensions"\nversion = "4.12.2"\n\n'
        '[[package]]\nname = "pytest"\nversion = "8.3.3"\n'
    )
    _, out, _ = cli(capsys, "scan", "--project", str(tmp_path))
    found = names(out["dependencies"])
    assert found["Typing_Extensions"] == ("runtime", ">=4", "4.12.2")
    assert found["pytest"] == ("dev", ">=8", "8.3.3")
    unpinned = {d["name"]: d["category"] for d in out["skipped"]}
    assert unpinned == {"requests": "runtime", "hatchling": "build"}


def test_scan_cargo_go_ruby_elixir_java(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "Cargo.toml").write_text(
        '[dependencies]\nserde = { version = "1", features = ["derive"] }\ntokio = "1.30"\n'
        '[dev-dependencies]\ncriterion = "0.5"\n'
    )
    (tmp_path / "Cargo.lock").write_text(
        '[[package]]\nname = "serde"\nversion = "1.0.200"\n'
        '[[package]]\nname = "tokio"\nversion = "1.38.0"\n'
    )
    (tmp_path / "go.mod").write_text(
        "module m\n\nrequire (\n\tgithub.com/google/uuid v1.6.0\n"
        "\tgolang.org/x/text v0.14.0 // indirect\n)\n"
    )
    (tmp_path / "Gemfile").write_text(
        "gem 'rails', '~> 7.1'\ngroup :development, :test do\n  gem 'rspec'\nend\n"
    )
    (tmp_path / "Gemfile.lock").write_text("GEM\n  specs:\n    rails (7.1.3)\n    rspec (3.13.0)\n")
    (tmp_path / "mix.exs").write_text(
        'defp deps do\n  [{:plug, "~> 1.15"}, {:credo, "~> 1.7", only: :dev}]\nend\n'
    )
    (tmp_path / "mix.lock").write_text('%{\n  "plug": {:hex, :plug, "1.15.3", "abc"},\n}\n')
    (tmp_path / "build.gradle").write_text(
        "dependencies {\n  implementation 'com.google.guava:guava:33.0.0-jre'\n"
        '  testImplementation("junit:junit:4.13.2")\n}\n'
    )
    (tmp_path / "pom.xml").write_text(
        "<project><dependencies><dependency><groupId>org.x</groupId><artifactId>y</artifactId>"
        "<version>2.0</version><scope>test</scope></dependency></dependencies></project>"
    )
    _, out, _ = cli(capsys, "scan", "--project", str(tmp_path))
    found = names(out["dependencies"])
    assert found["serde"] == ("runtime", "1", "1.0.200")
    assert {d["name"] for d in out["skipped"]} >= {"criterion", "credo", "org.x:y"}
    assert found["github.com/google/uuid"] == ("runtime", "v1.6.0", "v1.6.0")
    assert found["rspec"] == ("dev", "", "3.13.0")
    assert found["plug"] == ("runtime", "~> 1.15", "1.15.3")
    assert "credo" not in found
    assert "com.google.guava:guava" not in found


def test_scan_refuses_broken_manifest(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "package.json").write_text("{")
    code, out, _ = cli(capsys, "scan", "--project", str(tmp_path))
    assert code == deps.EXIT_REFUSED
    assert out["error"].startswith("package.json cannot be parsed")


# --- registry lookups -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("eco", "name", "version", "reason"),
    [
        ("npm", "--registry=evil", "1.0.0", "is not a plain package name"),
        ("npm", "x$(id)", "1.0.0", "is not a plain package name"),
        ("npm", "zod", "1.0.0;id", "not a plain version"),
        ("npm", "zod", "1.0.0 --foo", "not a plain version"),
        ("go", "../x", "v1.0.0", "is not a plain package name"),
        ("pypi", "a/b", "1.0.0", "is not valid for pypi"),
        ("rubygems", "rails", "7.1.3", "no registry lookup"),
    ],
)
def test_lookup_refuses_unsafe_input(
    eco: str, name: str, version: str, reason: str, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out, _ = cli(
        capsys, "lookup", "--plan", "--ecosystem", eco, f"--name={name}", f"--version={version}"
    )
    assert code == deps.EXIT_REFUSED
    assert reason in out["error"]


def test_lookup_plan_names_the_command_without_running_it(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def boom(*_a: object, **_k: object) -> str:
        raise AssertionError

    monkeypatch.setattr(deps, "run_cmd", boom)
    monkeypatch.setattr(deps, "http_get", boom)
    shown = {
        "npm": "npm view --json -- zod@3.23.8 repository.url gitHead",
        "pypi": "GET https://pypi.org/pypi/zod/3.23.8/json",
        "crates": "GET https://crates.io/api/v1/crates/zod",
        "go": "go list -m -json -- zod@3.23.8",
    }
    for eco, display in shown.items():
        _, out, _ = cli(
            capsys, "lookup", "--plan", "--ecosystem", eco, "--name", "zod", "--version", "3.23.8"
        )
        assert out["command"] == display


def fake_run(payload: str) -> t.Callable[[list[str], str], str]:
    def run(_argv: list[str], cwd: str) -> str:
        return payload

    return run


def test_lookup_npm_git_plus_https_is_normalized_and_git_head_returned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = json.dumps(
        {"repository.url": "git+https://github.com/colinhacks/zod.git", "gitHead": "ca42"}
    )
    monkeypatch.setattr(deps, "run_cmd", fake_run(payload))
    out = deps.lookup("npm", "zod", "3.23.8", crate_vcs=False)
    repository = t.cast("dict[str, str]", out["repository"])
    assert repository["url"] == "https://github.com/colinhacks/zod"
    assert (out["commit"], out["commit_source"]) == ("ca42", "gitHead")


def test_lookup_npm_ssh_repository_is_recorded_as_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = json.dumps({"repository.url": "git+ssh://git@github.com/a/b.git", "gitHead": "ff"})
    monkeypatch.setattr(deps, "run_cmd", fake_run(payload))
    out = deps.lookup("npm", "left-pad", "1.3.0", crate_vcs=False)
    assert out["repository"] is None
    assert out["error"] == "scheme 'ssh' is not https"


def test_parse_lookup_for_each_registry() -> None:
    assert deps.parse_lookup("npm", '"https://github.com/babel/babel.git"') == {
        "repository": "https://github.com/babel/babel.git",
        "commit": None,
    }
    go = {"Origin": {"URL": "https://github.com/google/uuid", "Hash": "0f11"}}
    assert deps.parse_lookup("go", json.dumps(go)) == {
        "repository": "https://github.com/google/uuid",
        "commit": "0f11",
    }
    crate = {"crate": {"repository": "https://github.com/serde-rs/serde"}}
    assert deps.parse_lookup("crates", json.dumps(crate))["commit"] is None
    pypi = {
        "info": {
            "home_page": "",
            "project_urls": {
                "Documentation": "https://requests.readthedocs.io",
                "Source": "https://github.com/psf/requests",
            },
        }
    }
    parsed = deps.parse_lookup("pypi", json.dumps(pypi))
    assert parsed == {"repository": "https://github.com/psf/requests", "commit": None}


def test_crate_commit_reads_only_the_top_level_vcs_info(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w") as tar:
        for name, body in (
            ("serde-1.0.200/vendored/.cargo_vcs_info.json", b'{"git": {"sha1": "bad"}}'),
            ("serde-1.0.200/.cargo_vcs_info.json", b'{"git": {"sha1": "cc86"}}'),
        ):
            info = tarfile.TarInfo(name)
            info.size = len(body)
            tar.addfile(info, io.BytesIO(body))
    blob = gzip.compress(raw.getvalue())

    def fake_get(_url: str, _limit: int = 0) -> bytes:
        return blob

    monkeypatch.setattr(deps, "http_get", fake_get)
    assert deps.crate_commit("serde", "1.0.200") == "cc86"


# --- report -----------------------------------------------------------------------------


def test_report_uses_one_status_vocabulary() -> None:
    results: list[dict[str, object]] = [
        {"package": "zod", "version": "3.23.8", "status": "pinned", "sha7": "1a2b3c4",
         "url": "https://github.com/colinhacks/zod", "path": "~/study/typescript/zod-3.23.8",
         "tag_check": "differs"},
        {"package": "vite", "version": "5.2.0", "status": "unpinned", "branch": "release/5.2",
         "sha7": "9f8e7d6", "url": "https://github.com/vitejs/vite", "path": "~/study/ts/v"},
        {"package": "left-pad", "version": "1.3.0", "status": "failed",
         "reason": "no usable repository"},
        {"package": "old", "version": "1", "status": "skipped", "reason": "worktree exists"},
    ]  # fmt: skip
    lines = t.cast("list[str]", deps.report(results)["lines"])
    assert lines[0] == "⚠ 1 failed, 3 worktrees ready"
    assert lines[2] == (
        "- zod@3.23.8 pinned, tag differs 1a2b3c4 https://github.com/colinhacks/zod "
        "~/study/typescript/zod-3.23.8"
    )
    assert lines[3].startswith("- vite@5.2.0 unpinned (release/5.2) 9f8e7d6 ")
    assert lines[4] == "- left-pad@1.3.0 failed: no usable repository"
    assert lines[5] == "- old@1 skipped: worktree exists"


def test_report_reads_results_from_a_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "r.json"
    path.write_text(
        json.dumps([{"package": "a", "version": "1", "status": "failed", "reason": "x"}])
    )
    _, out, _ = cli(capsys, "report", "--results", str(path))
    assert out["text"].startswith("⚠ 1 failed\n")


# --- shell-bound values and input refusals -------------------------------------------


def test_url_reads_stdin_through_a_quoted_heredoc_form(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("git+https://github.com/o/r.git$(id)\n"))
    code, out, _ = cli(capsys, "url", "-")
    assert code == deps.EXIT_REFUSED
    assert "characters outside" in out["error"]
    monkeypatch.setattr("sys.stdin", io.StringIO("git+https://github.com/o/r.git\n"))
    assert cli(capsys, "url", "-")[1]["url"] == "https://github.com/o/r"


def test_resolve_and_worktree_refuse_unplain_values(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    resolve = ("resolve", "--package", INJECTION, "--version", "1.0.0", "--ls-remote")
    empty = root.parent / "empty.txt"
    empty.write_text("")
    code, out, _ = cli(capsys, *resolve, str(empty))
    assert code == deps.EXIT_REFUSED
    assert out["error"] == f"package name {INJECTION!r} is not a plain package name"
    bad_tag = worktree_args(root, "--version", "1", "--tag=v1;id")
    assert cli(capsys, *bad_tag)[1]["error"] == "package name 'v1;id' is not a plain package name"
    bad_version = worktree_args(root, "--version=1;id", "--tag", "v1")
    assert cli(capsys, *bad_version)[1]["error"] == "version '1;id' is not a plain version string"


def test_report_labels_a_dependency_skipped_for_its_name(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rows = [{"status": "skipped", "reason": deps.NOT_PLAIN_NAME}]
    lines = t.cast("list[str]", deps.report(rows)["lines"])
    assert lines[2] == f"- unnamed dependency skipped: {deps.NOT_PLAIN_NAME}"


# --- network and process wrappers ---------------------------------------------------


class FakeResponse:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def read(self, limit: int) -> bytes:
        return self.body[:limit]


def stub_urlopen(monkeypatch: pytest.MonkeyPatch, body: bytes) -> list[str]:
    seen: list[str] = []

    def fake(req: t.Any, timeout: int) -> FakeResponse:
        seen.append(f"{req.full_url} {req.get_header('User-agent')} {timeout}")
        return FakeResponse(body)

    monkeypatch.setattr(deps.urllib.request, "urlopen", fake)
    return seen


def test_http_get_sends_identifying_agent_and_returns_body(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = stub_urlopen(monkeypatch, b"{}")
    assert deps.http_get("https://pypi.org/pypi/x/1/json") == b"{}"
    assert seen == [f"https://pypi.org/pypi/x/1/json {deps.USER_AGENT} 30"]


def test_http_get_refuses_http_oversize_and_network_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(deps.Refusal, match=r"registry requests are https only"):
        deps.http_get("http://pypi.org/x")
    stub_urlopen(monkeypatch, b"x" * 11)
    with pytest.raises(deps.Refusal, match=r"registry response exceeds the size limit"):
        deps.http_get("https://pypi.org/x", 10)

    def down(_req: object, timeout: int) -> None:
        raise deps.urllib.error.URLError("offline")

    monkeypatch.setattr(deps.urllib.request, "urlopen", down)
    with pytest.raises(deps.Refusal, match=r"registry request failed: .*offline"):
        deps.http_get("https://pypi.org/x")


def test_run_cmd_returns_stdout_and_refuses_with_first_stderr_line() -> None:
    assert deps.run_cmd([sys.executable, "-c", "print('ok')"], ".").strip() == "ok"
    fail = "import sys; sys.stderr.write('boom\\nmore'); sys.exit(3)"
    with pytest.raises(deps.Refusal, match=r"^boom$"):
        deps.run_cmd([sys.executable, "-c", fail], ".")
    with pytest.raises(deps.Refusal, match=r"no-such-binary-xyz failed"):
        deps.run_cmd(["no-such-binary-xyz"], ".")


def test_run_cmd_refuses_on_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    def slow(*_a: object, **_k: object) -> None:
        raise subprocess.TimeoutExpired("npm", 1)

    monkeypatch.setattr(deps.subprocess, "run", slow)
    with pytest.raises(deps.Refusal, match=r"npm failed"):
        deps.run_cmd(["npm"], ".")


def lock(tmp_path: Path, name: str, text: str) -> dict[str, str]:
    path = tmp_path / name
    path.write_text(text)
    return deps._lock_npm(path)


def test_lock_npm_reads_each_lockfile_format(tmp_path: Path) -> None:
    v3 = json.dumps(
        {
            "packages": {
                "": {},
                "node_modules/zod": {"version": "3.23.8"},
                "node_modules/@babel/core": {"version": "7.24.0"},
                "node_modules/a/node_modules/zod": {"version": "1.0.0"},
            }
        }
    )
    assert lock(tmp_path, "package-lock.json", v3) == {"zod": "3.23.8", "@babel/core": "7.24.0"}
    v1 = json.dumps({"dependencies": {"zod": {"version": "3.0.0"}}})
    assert lock(tmp_path, "package-lock.json", v1) == {"zod": "3.0.0"}
    pnpm = (
        "importers:\n  .:\n    dependencies:\n      zod:\n        specifier: ^3.22.0\n"
        "        version: 3.23.8(peer@1)\n"
    )
    assert lock(tmp_path, "pnpm-lock.yaml", pnpm)["zod"] == "3.23.8"
    pnpm_packages = "packages:\n  /vite@5.2.0:\n    resolution: {}\n"
    assert lock(tmp_path, "pnpm-lock.yaml", pnpm_packages)["vite"] == "5.2.0"
    yarn1 = 'zod@^3.22.0, zod@^3.0.0:\n  version "3.23.8"\n  resolved "x"\n'
    assert lock(tmp_path, "yarn.lock", yarn1) == {"zod": "3.23.8"}
    berry = '"@babel/core@npm:^7.0.0":\n  version: 7.24.0\n'
    assert lock(tmp_path, "yarn.lock", berry) == {"@babel/core": "7.24.0"}
    bun = '{"packages": {"zod": ["zod@3.23.8", "", {}, "sha"]}}'
    assert lock(tmp_path, "bun.lock", bun) == {"zod": "3.23.8"}


# --- coverage: PyPI locks, worktree refusals, lookup and crate paths -----------------------


def crate_blob(members: dict[str, bytes]) -> bytes:
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w") as tar:
        for name, body in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(body)
            tar.addfile(info, io.BytesIO(body))
    return gzip.compress(raw.getvalue())


def test_lock_pypi_reads_pipfile_requirements_and_toml_locks(tmp_path: Path) -> None:
    (tmp_path / "Pipfile.lock").write_text(
        json.dumps(
            {
                "default": {"Requests": {"version": "==2.31.0"}},
                "develop": {"py_test": {"version": "==8.0.0"}},
            }
        )
    )
    assert deps._lock_pypi(tmp_path / "Pipfile.lock") == {"requests": "2.31.0", "py-test": "8.0.0"}
    (tmp_path / "requirements.txt").write_text(
        "requests[socks]==2.31.0 ; python_version > '3'\nFlask == 3.0.0  # web\nnumpy>=1.0\n"
    )
    assert deps._lock_pypi(tmp_path / "requirements.txt") == {
        "requests": "2.31.0",
        "flask": "3.0.0",
    }
    for name in ("poetry.lock", "uv.lock"):
        (tmp_path / name).write_text('[[package]]\nname = "Jinja2"\nversion = "3.1.2"\n')
        assert deps._lock_pypi(tmp_path / name) == {"jinja2": "3.1.2"}


def test_scan_refuses_an_unreadable_lockfile(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "requirements.txt").write_text("requests\n")
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\ndependencies = ["requests"]\n')
    (tmp_path / "Pipfile.lock").write_text("{")
    code, out, _ = cli(capsys, "scan", "--project", str(tmp_path))
    assert code != 0
    assert "Pipfile.lock cannot be parsed" in out["error"]


def test_worktree_refuses_a_missing_clone(root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = cli(capsys, *worktree_args(root, "--version", "1.0.0", "--tag", "v1.0.0"))
    assert (code, out["error"]) == (2, "clone is missing")


def test_worktree_refuses_a_head_that_differs_from_the_commit(
    source: Path, root: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    cli(capsys, "clone", "--root", str(root), "--lang", "python", "--url", REMOTE)
    real = deps.git

    def lying(*args: str, cwd: Path | None = None) -> str:
        if args[-2:] == ("rev-parse", "HEAD") and "r-1.0.0" in args[1]:
            return "0" * 40
        return real(*args, cwd=cwd)

    monkeypatch.setattr(deps, "git", lying)
    code, out, _ = cli(capsys, *worktree_args(root, "--version", "1.0.0", "--tag", "v1.0.0"))
    assert (code, out["error"]) == (2, "worktree HEAD differs from the requested commit")


def test_unpinned_worktree_takes_a_named_branch(
    source: Path, root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cli(capsys, "clone", "--root", str(root), "--lang", "python", "--url", REMOTE)
    _, out, _ = cli(capsys, *worktree_args(root, "--version", "9.9.9", "--branch", "main"))
    assert (out["status"], out["branch"]) == ("unpinned", "main")


def test_parse_lookup_refuses_a_body_that_is_not_json() -> None:
    with pytest.raises(deps.Refusal, match="pypi lookup did not return JSON"):
        deps.parse_lookup("pypi", "<html>")


def test_lookup_records_a_registry_with_no_repository(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(deps, "run_cmd", fake_run(json.dumps({"gitHead": "ff"})))
    out = deps.lookup("npm", "left-pad", "1.3.0", crate_vcs=False)
    assert out["repository"] is None
    assert out["error"] == "registry lists no repository"
    assert (out["commit"], out["commit_source"]) == ("ff", "gitHead")


def test_lookup_reads_the_crate_commit_only_when_asked(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    meta = json.dumps({"crate": {"repository": "https://github.com/serde-rs/serde"}}).encode()
    blob = crate_blob({"serde-1/.cargo_vcs_info.json": b'{"git": {"sha1": "cc86"}}'})
    asked: list[str] = []

    def fake_get(url: str, _limit: int = 0) -> bytes:
        asked.append(url)
        return blob if url.endswith("/download") else meta

    monkeypatch.setattr(deps, "http_get", fake_get)
    plain = deps.lookup("crates", "serde", "1.0.200", crate_vcs=False)
    assert (plain["commit"], plain["commit_source"], len(asked)) == (None, None, 1)
    code, out, _ = cli(
        capsys, "lookup", "--ecosystem", "crates", "--name", "serde", "--version", "1.0.200",
        "--crate-commit",
    )  # fmt: skip
    assert code == 0
    assert (out["commit"], out["commit_source"]) == ("cc86", ".cargo_vcs_info.json")


def fake_blob(blob: bytes) -> t.Callable[[str, int], bytes]:
    def get(_url: str, _limit: int = 0) -> bytes:
        return blob

    return get


def test_crate_commit_is_none_without_a_usable_vcs_info(monkeypatch: pytest.MonkeyPatch) -> None:
    bodies = [
        {"serde-1/Cargo.toml": b"x"},
        {"serde-1/.cargo_vcs_info.json": b'{"dirty": true}'},
        {},
    ]
    for members in bodies:
        blob = crate_blob(members)
        monkeypatch.setattr(deps, "http_get", fake_blob(blob))
        assert deps.crate_commit("serde", "1.0.200") is None


def test_parse_ls_remote_skips_lines_that_are_not_two_fields() -> None:
    assert deps.parse_ls_remote("aaa refs/tags/v1\nbbb\trefs/heads/main\n\n") == (
        {},
        {"main": "bbb"},
    )
