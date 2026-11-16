# Check the context before prescribing setup

A language does not determine the reader: a Rust project can be a library, CLI,
Python extension or contributor portal. Apply only the relevant checks below.
They are questions to verify, not mandatory README sections.

## Package consumers and contributors

- Python: distinguish distribution/import names, wheels/source builds and consumer
  dependencies/test fixtures. Do not require a compiler for supported wheel users.
- JavaScript/TypeScript: verify runtime, module/import form and framework binding.
  Separate package-manager alternatives instead of running them in sequence.
- Rust: distinguish a Cargo dependency from binary installation; retain features,
  toolchain limits and terminal cleanup when the example requires them.
- C/C++: verify standard, compiler, ABI/linkage and build-system requirements that
  affect this integration. A tested CI matrix is not proof of every supported host.
- JVM, .NET and Swift: verify artifact/product/module identifiers, target/runtime
  requirements and required backends. Consumer installation and source builds differ.
- Ruby, BEAM and Julia: retain dependency environments and registry-specific rules.
  Test-only dependencies, OS-managed tools and registry procedures are contextual.

Exact pins may define a compatibility or reproduction contract. Verify a stale
value against its owner instead of replacing it with "latest". Historical release
notes describe their own version; age alone does not make them wrong.

## Services, plugins and client integrations

State host prerequisites, activation order, credentials, port direction, persistence
and cleanup only when the supported route needs them. Preserve distinct client
configuration routes. A contributor acceptance test can have external effects.

[Testcontainers for Go](https://github.com/testcontainers/testcontainers-go/blob/00988b99f644ec5907b79c46910f39a7d89d1b63/README.md#L13-L21)
states a creation/cleanup contract and routes setup to its guide. Verify who owns
each resource before describing teardown as temporary or isolated. Include context
creation and cancellation when omitting them would change the example's behavior.

For refusals, verify the exact operation withheld, exception and version range.
A probe can occur before a mutation is refused; a captured-version path may perform
no I/O. A bounded defect range and a minimum supported version are different claims.
Generated API prose should be corrected in its source and checked in the output.

## Assets, research and operational tools

For fonts, models or datasets, prioritize acquisition, formats, provenance, license
distinctions and compatibility. Keep citations, tested environments and benchmark
conditions when they affect interpretation; do not invent a code installation path.
Generated specimens are not proof that every renderer or asset was tested.

For migration, recovery or diagnostic tools, retain actual file effects, rollback
limits and relevant data transmission. Warnings belong near the decision they
change, including above installation. A relocation notice can be a complete README.
