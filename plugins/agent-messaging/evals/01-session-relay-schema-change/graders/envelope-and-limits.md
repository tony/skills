---
type: llm
---
The reply composes the message as a single line in a bracketed relay envelope format (something like "[relay/1 from=... to=... id=... hop=... want=...] <body>"), not spread across multiple lines.
When no target or own address resolves, the envelope uses `want=none` or an explicit unknown address and invents none.
The reply claims delivery only with receiver-side evidence: the exact payload in the receiver's turn or an acknowledgment carrying the relay id. A successful send command or a consumed queue row alone leaves delivery unconfirmed. If no route worked, it says the message was not sent and why.
The composed message does not start with "/", "!", "#", or "@".
