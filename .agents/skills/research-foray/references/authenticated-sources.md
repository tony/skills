# Sources behind an account

A Slack thread, a Linear or Jira ticket, a Datadog monitor, a private
repository, or a cloud resource answers an anonymous request with a
sign-in page, a 401 or 403, or a 404 (GitHub hides a private repository
that way), never the content. Read such a source through a tool that
already holds the user's session.

1. List what is connected before reading: the MCP tools the client
   exposes (`claude mcp list` in Claude Code and `codex mcp list` in
   Codex list the configured servers), CLIs on `PATH` (`gh`, `glab`,
   `aws`, `wrangler`, a tracker's CLI), and skills the project's
   AGENTS.md or CLAUDE.md names. Never assume one is there.
2. Read through the matching tool: `gh` or `glab` for its forge
   (`gh issue view`, `gh api`), the tracker's, chat's, or monitor's MCP
   read tools or CLI, and the cloud provider's CLI. Read only, unless
   the skill says to write.
3. Do not query the service with `curl`, a script, or a web-fetch tool
   instead. Raw HTTP fits only a provider API that a skill documents,
   with a credential the user configured; never paste a token or cookie
   into a command.
4. With no tool connected for the service, or the tool denied, name the
   source left unread and ask for an export or the connector. Never
   guess its content or route around the denial.

Direct HTTP stays right for public pages and for a localhost or
development server the session controls.
