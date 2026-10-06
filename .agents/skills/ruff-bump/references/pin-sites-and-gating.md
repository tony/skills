# Pin sites and resolver gating

Raising a linter's version floor fails two ways: a pin site is missed, so CI keeps running the old version, or the resolver refuses the new release and the diagnosis targets the wrong layer.

## Every place a linter version can be pinned

A repository frequently pins the same tool in more than one file, and they drift. Find all of them before editing any of them. Search the whole tree for the tool's name, then check each hit against this list:

**Python project metadata.** `pyproject.toml` — dependency groups (`[dependency-groups]`), extras (`[project.optional-dependencies]`), and legacy tool-specific sections. A repo often lists the linter in both a broad `dev` group and a narrow `lint` group; both need raising or CI and local development diverge.

**Requirements files.** `requirements*.txt`, `requirements/*.txt`, constraints files. Frequently the file CI actually installs from, even when `pyproject.toml` looks authoritative.

**Pre-commit configuration.** `.pre-commit-config.yaml` pins the linter by git tag under a `rev:` key, entirely independently of the Python dependency graph. This is the single most commonly missed site: the project metadata says the new version, pre-commit keeps running the old one, and the two disagree about what is clean. The tag convention is usually `v`-prefixed even when the package version is not.

**Runtime and tool-version managers.** `.tool-versions`, `mise.toml`/`.mise.toml`, `.python-version`-adjacent tool pins, `flake.nix`, `Dockerfile` install lines.

**CI workflow files.** A workflow that installs the linter directly — rather than through the project's dependency graph — pins it in the workflow itself, sometimes as a bare version string in a `with:` block or an install command.

**Node-side wrappers.** Some polyglot repos install the linter through a JavaScript package manager as well; `package.json` will carry its own pin.

**Editor and container configuration.** `.vscode/`, `.devcontainer/`, and similar. Not load-bearing for CI, but a stale pin here makes a contributor's editor disagree with the build.

Raise every site in the same commit. A partial bump leaves two tools disagreeing about what "clean" means.

## Prefer a floor to an exact pin

Write `>=` rather than `==` for the version constraint. The lockfile already reproduces one exact version for anyone using the lock; the constraint exists to stop a contributor whose environment resolved something older from producing a locally-clean run that fails CI. An exact pin in the constraint duplicates the lockfile's job and turns every future bump into a wider diff.

Pre-commit is the exception — its `rev:` is a single tag by design, so it takes an exact tag.

## When the resolver cannot see the release

A newly published version can be invisible to the resolver for reasons that have nothing to do with your constraint. Diagnose which one before working around it:

**Publication cooldown.** Some resolvers hide releases younger than a configured threshold. A release inside the window does not exist as far as resolution is concerned, though the package index shows it. This is the most common cause. For uv, a cooldown can live in the user config, a `uv.toml`, a `[tool.uv]` table in any `pyproject.toml` (workspace members included), or the `UV_EXCLUDE_NEWER` environment variable, and per-package forms (`exclude-newer-package`) match the same search. Search the tree and the user config in one command; a missing file is not an error:

```console
$ grep -rIiH --include=uv.toml --include=pyproject.toml exclude-newer . "${UV_CONFIG_FILE:-${XDG_CONFIG_HOME:-$HOME/.config}/uv/uv.toml}" 2>/dev/null
```

Then check `UV_EXCLUDE_NEWER` in the environment. Settings merge, so the search shows candidates, not the effective value. Run `uv lock --dry-run` and read the refusal for the effective cause.

Other resolvers (pip, poetry, pdm) have their own cooldown settings; find them in the resolver's documentation. The same exemption rules apply.

**Index lag.** A private mirror or proxy has not synchronized yet. Nothing to work around; wait or repoint the index.

**Constraint conflict.** A transitive dependency or a constraints file caps the version. The resolver usually says so, but the message can be buried.

**Platform gaps.** The release exists but has no wheel for a platform in the resolution matrix.
