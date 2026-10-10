# Pin sites and resolver gating

Raising a linter's version floor fails two ways: a pin site is missed, so CI keeps running the old version, or the resolver refuses the new release and the diagnosis targets the wrong layer.

## Every place a linter version can be pinned

A repository frequently pins the same tool in more than one file, and they drift. Find all of them before editing any of them. Search the whole tree for the tool's name, skipping `.git`, `.venv`, and `node_modules`, then check each hit against this list:

**Python project metadata.** `pyproject.toml`: dependency groups (`[dependency-groups]`), extras (`[project.optional-dependencies]`), and legacy tool-specific sections. A repo often lists the linter in both a broad `dev` group and a narrow `lint` group; both need raising or CI and local development diverge.

**Requirements files.** `requirements*.txt`, `requirements/*.txt`, constraints files. Frequently the file CI actually installs from, even when `pyproject.toml` looks authoritative.

**Pre-commit configuration.** `.pre-commit-config.yaml` pins the linter by git tag under a `rev:` key, entirely independently of the Python dependency graph. A hook pin is easy to miss: the project metadata says the new version, pre-commit keeps running the old one, and the two disagree about what is clean. Read the tag spelling from `git ls-remote --tags` of the hook's repository; it may or may not carry a `v` prefix.

**Runtime and tool-version managers.** `.tool-versions`, `mise.toml`/`.mise.toml`, `.python-version`-adjacent tool pins, `flake.nix`, `Dockerfile` install lines.

**CI workflow files.** A workflow that installs the linter directly, rather than through the project's dependency graph, pins it in the workflow itself, sometimes as a bare version string in a `with:` block or an install command.

**Node-side wrappers.** Some polyglot repos install the linter through a JavaScript package manager as well; `package.json` will carry its own pin.

**Editor and container configuration.** `.vscode/`, `.devcontainer/`, and similar. Not load-bearing for CI, but a stale pin here makes a contributor's editor disagree with the build.

Raise every site in the same commit. A partial bump leaves two tools disagreeing about what "clean" means.

## Keep the constraint style

Raise each site within its own style: `>=` stays a floor, `==` stays exact, and pre-commit's `rev:` is a single tag by design. A floor leans on the lockfile to reproduce one exact version, so loosening an exact pin to a floor in a repository without a tracked lock makes the next resolve drift. Loosening is a policy change: offer it in the plan and make it only when approved.

## When the resolver cannot see the release

A newly published version can be invisible to the resolver for reasons that have nothing to do with your constraint. Diagnose which one before working around it:

**Publication cooldown.** Some resolvers hide releases younger than a configured threshold. A release inside the window does not exist as far as resolution is concerned, though the package index shows it. For uv, a cooldown can live in the user config, a `uv.toml`, a `[tool.uv]` table in any `pyproject.toml` (workspace members included), or the `UV_EXCLUDE_NEWER` environment variable, and per-package forms (`exclude-newer-package`) match the same search. Search the tree and the user config in one command; a missing file is not an error:

```console
$ grep -rIiH --exclude-dir=.git --exclude-dir=.venv --exclude-dir=node_modules --include=uv.toml --include=pyproject.toml exclude-newer . "${UV_CONFIG_FILE:-${XDG_CONFIG_HOME:-$HOME/.config}/uv/uv.toml}" 2>/dev/null
```

Then check `UV_EXCLUDE_NEWER` in the environment. Settings merge, so the search shows candidates, not the effective value. Run `uv lock --dry-run` and read the refusal: the cause is a cooldown only when the refusal names the release as excluded by date and one setting found above matches it. A search that finds a setting, a failed run, or a refusal that is silent about the date leaves the cause unconfirmed; report it as unconfirmed and write no exemption.

uv compares the upload time of each distribution file, not the release date, so take times from the package index (`releases.<version>[].upload_time_iso_8601`), never from a GitHub release page. The release becomes visible when the latest file the platform needs passes the window.

Other resolvers (pip, poetry, pdm) have their own cooldown settings; find them in the resolver's documentation. The same exemption rules apply.

**Index lag.** A private mirror or proxy has not synchronized yet. Nothing to work around; wait or repoint the index.

**Constraint conflict.** A transitive dependency or a constraints file caps the version. The resolver usually says so, but the message can be buried.

**Platform gaps.** The release exists but has no wheel for a platform in the resolution matrix.
