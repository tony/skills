---
type: llm
---
The reply composes the message as a single line in a bracketed relay envelope format (something like "[relay/1 from=... to=... id=... hop=... want=...] <body>"), not spread across multiple lines.
The reply claims the message was delivered only if it names the target pane or session it found and the delivery command that succeeded; otherwise it says the message was not sent and why.
The composed message does not start with "/", "!", "#", or "@".
