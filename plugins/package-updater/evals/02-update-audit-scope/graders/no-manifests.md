---
type: llm
---
The reply names a package, version, or toolchain pin as outdated only when it read that pin from a file or command output in this run; it never invents one.
The reply reports what it found, or that it found nothing to audit, rather than a clean "0 outdated" result.
When there is nothing to audit, the reply says so as a stop and asks for or states which repository to audit.
