<!-- Vendored from shared/authenticated-sources.md; edit that file, then run 'scripts/marketplace.py portable'. -->
# Sources behind an account

A Slack thread, a Linear or Jira ticket, a Datadog monitor, a private
repository, or a cloud resource answers an anonymous request with a
sign-in page, a 401 or 403, or a 404 (GitHub hides a private repository
that way), never the content. Read such a source through a tool that
already holds the user's session.

1. List what is connected before reading: the session's MCP tools,
   including any listed by name only until loaded (Claude Code's
   ToolSearch loads them); CLIs on `PATH` that hold a login
   (`gh auth status`; likewise `glab`, `aws`, `wrangler`, a tracker's
   CLI); and skills the project's AGENTS.md or CLAUDE.md names.
   `claude mcp list` and `codex mcp list` show the configured servers
   and which need sign-in.
2. Read through the matching tool (`gh api`, a tracker's MCP read tool).
   Read only, unless the skill says to write.
3. Do not query the service with `curl`, a script, or a web-fetch tool
   instead. Raw HTTP fits only a provider API this plugin's references
   document, with a credential already in the environment; never paste
   a token or cookie into a command.
4. With no logged-in tool for the service, or the tool denied, name the
   source left unread and the export or connector that would read it.
   Never guess its content or route around the denial.

Direct HTTP stays right for public pages and for a localhost or
development server the session controls.
