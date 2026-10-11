# Private security path

Read this when the report may be a security defect, or the repository has
a security policy (`isSecurityPolicyEnabled` from the Phase 2 query, which
covers `SECURITY.md` wherever the project keeps it). Stop-and-reply shapes
are in "Replies" in `create-issue`.

## Is it a security defect

This definition is the skill's own; GitHub's
[security policy docs](https://docs.github.com/en/code-security/getting-started/adding-a-security-policy-to-your-repository)
leave scope to each project.

It is one when someone could exploit it to bypass authentication or
authorization, inject code, commands, queries, or script, read or write
files or data they should not reach (path traversal, request forgery),
obtain secrets or credentials, escalate privileges, corrupt memory
(out-of-bounds, use-after-free), or crash the service from remote or
untrusted input. An ordinary crash on the user's own input is a defect.
When unsure whether a crash is reachable that way, ask once.

## Follow the policy

With a policy, read it from the API. If it routes this report privately,
follow that path and stop:

```console
$ gh api repos/OWNER/REPO/contents/SECURITY.md \
    -H 'Accept: application/vnd.github.raw'
```

On a 404, try the same path under `.github/` and `docs/`, then in the
owner's `OWNER/.github` repository, where an organization keeps its
default policy. When none reads, give the user `securityPolicyUrl`.

With no policy, check private vulnerability reporting:

```console
$ gh api repos/OWNER/REPO/private-vulnerability-reporting --jq .enabled
```

`true` means the user reports through the repository's Security tab
("Report a vulnerability"). Otherwise look for a maintainer contact in the
README or `CONTRIBUTING.md`. With no private channel at all, the only
public issue allowed asks for a security contact and names no endpoint,
parameter, or exploit.

## Primary sources

- [Adding a security policy](https://docs.github.com/en/code-security/getting-started/adding-a-security-policy-to-your-repository)
- [REST: private vulnerability reporting](https://docs.github.com/en/rest/repos/repos#check-if-private-vulnerability-reporting-is-enabled-for-a-repository)
