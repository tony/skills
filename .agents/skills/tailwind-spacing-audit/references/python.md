# Python for bundled scripts

This plugin's scripts need Python 3.14 or newer, and its commands run them
with `python3`. Follow this file when `python3` is missing, when
`python3 --version` is older than 3.14, or when a bundled script fails with
`SyntaxError` before doing anything: that error means an older Python read
syntax it does not know, not that the script is broken. Never edit a script
to make it run on an older Python.

## Find an installed Python

Stop at the first interpreter that reports 3.14 or newer. None of these
commands downloads anything.

1. A versioned name on `PATH`, such as `python3.15` or `python3.14`:

   ```console
   $ command -v python3.15 python3.14
   ```

2. uv, which also finds interpreters it installed:

   ```console
   $ uv python find --no-python-downloads '>=3.14'
   ```

3. A version manager. List its Pythons, then print the install directory of
   one at 3.14 or newer; the interpreter is `bin/python3` inside it:
   - mise: `mise ls --installed python`, then `mise where python@<version>`
   - asdf: `asdf list python`, then `asdf where python <version>`
   - pyenv: `pyenv versions --bare`, then `pyenv prefix <version>`
4. On Windows, `py -3 --version` reports the newest Python 3 the launcher
   knows.

Confirm the pick with `<interpreter> --version`. Then write its absolute
path wherever this plugin's commands write `python3`, and in front of any
script a command runs directly by its path.

## When none is installed

Each command below downloads Python 3.14 and runs a script with it. Offer
the ones whose tool is on `PATH` and ask the user which to use; in a
headless run, stop and list them. Write the chosen command where the
commands write `python3`:

- `uvx python@3.14`
- `uv run --no-project --python 3.14`
- `pipx run --fetch-python missing --python 3.14 --path`
- `mise exec python@3.14 -- python3`

With none of those tools, ask the user to install Python 3.14 or newer.
