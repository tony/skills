#!/usr/bin/env python3
r"""Print the reference form a provider's rules prescribe for a target.

Usage: ref_form.py PROVIDER SCOPE (--notify | --quiet) [--id ID] [--url URL] [--title TEXT]
                   [--path NAMESPACE/PROJECT]

PROVIDER is github, gitlab, jira, linear, azure, shortcut, trello, or asana.
SCOPE is `same` (the container the body lands in) or `cross` (any other
container, site, or workspace). --notify means the target should show a
backreference; --quiet means it must not. The model picks the intent and this
script applies the provider rules. It exits 1, printing the reason, when the
provider documents no form for that intent, and 2 on bad input.

>>> form("github", "same", notify=True, id="12")
'#12'
>>> form("github", "cross", notify=False, url="https://github.com/o/r/issues/3", title="Plan")
'[Plan](https://redirect.github.com/o/r/issues/3)'
>>> form("jira", "same", notify=False, id="ENG-7")
'ENG-7'
"""

import sys
from urllib.parse import urlsplit, urlunsplit


class NoForm(Exception):  # noqa: N818
    """The provider documents no form for the requested intent."""


def _need(**given: str | None) -> None:
    missing = [name for name, value in given.items() if not value]
    if missing:
        message = f"missing --{', --'.join(missing)}"
        raise ValueError(message)


def _github(scope: str, *, notify: bool, id: str | None, url: str | None, title: str | None) -> str:  # noqa: A002
    if scope == "same" and notify:
        _need(id=id)
        return f"#{id}"
    _need(url=url)
    parts = urlsplit(url or "")
    if not notify:
        if parts.hostname and parts.hostname.endswith(".ghe.com"):
            message = (
                "the redirect host is unsupported on GitHub Enterprise Cloud with data residency"
            )
            raise NoForm(message)
        url = urlunsplit(parts._replace(netloc="redirect.github.com"))
    if scope == "same":
        return url or ""
    _need(title=title)
    return f"[{title}]({url})"


def _gitlab(scope: str, *, notify: bool, id: str | None, path: str | None) -> str:  # noqa: A002
    _need(id=id)
    if scope == "cross":
        _need(path=path)
    body = f"{path}#{id}" if scope == "cross" else f"#{id}"
    return body if notify else (f"`{body}`" if scope == "cross" else f"\\#{id}")


def _titled(url: str | None, title: str | None) -> str:
    _need(url=url, title=title)
    return f"[{title}]({url})"


def form(  # noqa: PLR0911, PLR0913
    provider: str,
    scope: str,
    *,
    notify: bool,
    id: str | None = None,  # noqa: A002
    url: str | None = None,
    title: str | None = None,
    path: str | None = None,
) -> str:
    """Return the reference text, or raise NoForm."""
    if provider == "github":
        return _github(scope, notify=notify, id=id, url=url, title=title)
    if provider == "gitlab":
        return _gitlab(scope, notify=notify, id=id, path=path)
    if provider == "jira":
        if scope == "same" and id:
            return id
        return _titled(url, title)
    if provider in ("linear", "azure"):
        if not notify:
            message = f"{provider} documents no way to reference without a backreference"
            raise NoForm(message)
        if scope == "same":
            _need(id=id)
            return f"#{id}" if provider == "azure" else id or ""
        return _titled(url, title)
    if provider == "shortcut":
        if scope == "same":
            _need(id=id)
            return f"sc-{id}"
        return _titled(url, title)
    if provider == "trello":
        if notify:
            message = (
                "Trello writes a backreference only through a Card attachment, not the description"
            )
            raise NoForm(message)
        return _titled(url, title)
    if provider == "asana":
        _need(id=id)
        return f'<a data-asana-gid="{id}"/>'
    message = f"unknown provider {provider!r}"
    raise ValueError(message)


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and print the form."""
    args = sys.argv[1:] if argv is None else argv
    opts: dict[str, str | None] = {"--id": None, "--url": None, "--title": None, "--path": None}
    pos: list[str] = []
    notify: bool | None = None
    i = 0
    while i < len(args):
        a = args[i]
        if a in opts and i + 1 < len(args):
            opts[a] = args[i + 1]
            i += 2
            continue
        if a in ("--notify", "--quiet"):
            notify = a == "--notify"
        else:
            pos.append(a)
        i += 1
    if len(pos) != 2 or notify is None or pos[1] not in ("same", "cross"):  # noqa: PLR2004
        _ = sys.stderr.write("\n\n".join(__doc__.split("\n\n")[1:3]) + "\n" if __doc__ else "")
        return 2
    try:
        print(
            form(
                pos[0],
                pos[1],
                notify=notify,
                id=opts["--id"],
                url=opts["--url"],
                title=opts["--title"],
                path=opts["--path"],
            )
        )
    except NoForm as exc:
        print(f"no form: {exc}")
        return 1
    except ValueError as exc:
        _ = sys.stderr.write(f"{exc}\n")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
