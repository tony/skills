---
max_turns: 10
timeout_seconds: 300
allowed_tools: [Read, Glob, Grep, Skill]
---
Clone the source of this dependency at its installed version so I can read it. The lockfile fragment:

```toml
[[package]]
name = "fastframe"
version = "1.4.2"
source = { registry = "https://pypi.org/simple" }
```

And its pyproject metadata says the repository is `ssh://git@code.example.net/fastframe/fastframe.git`.
