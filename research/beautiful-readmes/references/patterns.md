# README patterns: inspiration with limits

Start with the reader's job. These patterns describe observed choices in commit-pinned READMEs; they are a menu, not a template or ranking. An example can demonstrate one strong pattern while containing unrelated defects. Source inspection established the text and placement cited here. It did not establish runtime correctness, link availability, visual quality, or measured reading time.

## Thin documentation portal

**Reader and job:** A prospective user needs a precise purpose, fit, and the right maintained documentation destination.

**Observed:** [http4s/http4s](https://github.com/http4s/http4s/blob/f81cb4ac926ffd65d94bb856908de5f11d1ffe22/README.md#L1-L25) presents a small API preview and links to fuller documentation. [hashicorp/terraform-provider-aws](https://github.com/hashicorp/terraform-provider-aws/blob/321c24241d987037578029c61215d4f0352ccb2c/README.md#L20-L26) separates tutorials, contributor guidance, FAQs, and discussion.

**Why it works:** It avoids duplicating a documentation site's setup across multiple release tracks or adapters. The short page is sufficient when readers can identify the project and choose their next action.

**When it backfires:** Generic links such as “learn more” become a dead end when they do not resolve the user's immediate question. A tiny page is not automatically clear if it omits product identity or hides compatibility conditions.

**Preserve or adapt:** Keep a concrete purpose, decisive constraints, and labeled destinations. Add inline setup only when it closes a real gap and has a clear maintenance owner.

## Compact library example

**Reader and job:** A developer wants to recognize the abstraction and try a representative operation.

**Observed:** [serde-rs/serde](https://github.com/serde-rs/serde/blob/fa7da4a93567ed347ad0735c28e439fca688ef26/README.md#L25-L74) combines a serialization round trip, manifest, expected output, and playground. [groue/GRDB.swift](https://github.com/groue/GRDB.swift/blob/0d8cf958b4b66a0473ec6e6986eb9da462171da9/README.md#L64-L130) opens a four-step database workflow and keeps an alternative SQL view expandable.

**Why it works:** A small, connected example shows inputs, API shape, and an observable result. Setup stays available without interrupting readers who already know the ecosystem.

**When it backfires:** A short snippet loses value if it depends on hidden packages, imports, initialization, or credentials. A full application can obscure the library's distinct contribution. A deliberately partial API preview should not be presented as ready to run.

**Preserve or adapt:** Keep dependency versions and feature flags where necessary, meaningful error or output types, and the example's conceptual continuity. Choose an operation that represents the library rather than assembling every feature into one showcase.

## Task-oriented CLI manual

**Reader and job:** A new user wants one successful command; a returning user needs exact behavior for a particular task.

**Observed:** [casey/just](https://github.com/casey/just/blob/e01a6bd7e7a30baf86bc86d2b95b0998ebbdc36f/README.md#L667-L815) progresses from a first recipe to dependencies and defaults. Its [quoting counterexample](https://github.com/casey/just/blob/e01a6bd7e7a30baf86bc86d2b95b0998ebbdc36f/README.md#L1179-L1213) explains a surprising result. [grafana/xk6](https://github.com/grafana/xk6/blob/103897f741839bf710a496ed68ddcafb3b751581/README.md#L36-L45) names the resulting binary and location.

**Why it works:** The opening provides a complete path, while later sections answer actual questions about flags, output, composition, and failure. A long reference remains useful when it has navigable sections and stable anchors.

**When it backfires:** An exhaustive flag dump precedes any purpose, command transcripts omit the command, alternatives look sequential, or examples assume an unstated directory. Long content without a map burdens both new and returning readers.

**Preserve or adapt:** Keep shell and platform differences, working-directory effects, exit-code contracts, version annotations, and behavior-revealing output. Just's [release-versus-main documentation distinction](https://github.com/casey/just/blob/e01a6bd7e7a30baf86bc86d2b95b0998ebbdc36f/README.md#L24-L29) is worth adapting when a repository README tracks unreleased behavior.

## Visual product or interactive demo

**Reader and job:** A user needs to see an interaction, output, or spatial arrangement before deciding whether to try it.

**Observed:** [teoxoy/factorio-blueprint-editor](https://github.com/teoxoy/factorio-blueprint-editor/blob/2bfc95e662cad19e2de89e72016181ca96fdbea6/README.md#L14-L27) links preloaded blueprints and names concrete editing actions. [gelguy/wilder.nvim](https://github.com/gelguy/wilder.nvim/blob/679f348dc90d80ff9ba0e7c470c40a4d038dcecf/README.md#L256-L292) pairs a renderer screenshot with host-specific behavior and configuration.

**Why it works:** A visual or ready-made example can answer questions that prose would describe awkwardly: what the tool produces, what changes on screen, and which controls matter.

**When it backfires:** An image substitutes for installation or a critical requirement, decorative assets consume the opening without communicating product behavior, or text inside an image is the only accessible explanation. Source markup cannot establish whether an image is legible or too large on desktop.

**Preserve or adapt:** Keep useful image identity, captions, alt text, demo inputs, and the code that reproduces the shown state. Verify the rendered desktop page before changing dimensions or replacing assets. A still image, video, diagram, or live sample should be chosen for the interaction it explains.

## Package or service catalog

**Reader and job:** A developer needs to select a component and understand how it relates to the rest of a repository.

**Observed:** [earendil-works/pi](https://github.com/earendil-works/pi/blob/910149912ca29d7ae4eaa945bb2b53eb84c68264/README.md#L72-L84) maps packages to responsibilities. [awslabs/mcp](https://github.com/awslabs/mcp/blob/2bf7c836d87c299e07763b1e1953af4c0c8065cf/README.md#L501) sends component-specific requirements to the owning README. [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills/blob/aeac41d4d005999432bb7312f7ff06383a91d59d/README.md#L26-L36) maps tasks to commands.

**Why it works:** A compact comparison reduces a genuine selection problem. Component pages retain the details that change independently.

**When it backfires:** Every component gets the same generic praise, a wide table becomes a second full manual, or a top-level assertion implies that every service shares the same authentication, runtime, transport, or trust boundary.

**Preserve or adapt:** Keep short responsibility descriptions, meaningful selection criteria, and direct component links. Distinguish common requirements from component-specific requirements. Do not flatten a catalog into a single quickstart that claims to fit every entry.

## Operational quickstart

**Reader and job:** An operator or developer needs to start a service or integration and understand its effects.

**Observed:** [grafana/docker-otel-lgtm](https://github.com/grafana/docker-otel-lgtm/blob/65b3a0510089a7171e4fba3f986cfb2a324d6e4d/README.md#L12-L13) states the intended development scope; its [PID namespace guidance](https://github.com/grafana/docker-otel-lgtm/blob/65b3a0510089a7171e4fba3f986cfb2a324d6e4d/README.md#L140-L144) explains a consequential host interaction. [samleeney/tmux-agent-status](https://github.com/samleeney/tmux-agent-status/blob/c5babfbcb3210809d661ba74db82c176da194686/README.md#L58-L63) states default installation effects and its [key map](https://github.com/samleeney/tmux-agent-status/blob/c5babfbcb3210809d661ba74db82c176da194686/README.md#L308-L314) specifies destructive scope.

**Why it works:** Requirements and consequences are located where users make the relevant decision. Success is something the reader can observe, not merely a claim that setup is easy.

**When it backfires:** The sequence assumes an unmentioned checkout, invents a safe default, mixes optional commands into one script, or omits persistence and cleanup behavior. Repeated unspecific warning boxes can conceal the warning that matters.

**Preserve or adapt:** Keep necessary ports, credentials, permissions, supported environments, data location, persistence semantics, and observable success. Verify omitted prerequisites before polishing the prose. State warnings as condition, consequence, and action when the source supports all three.

## Contributor or source repository README

**Reader and job:** An ecosystem participant needs to find source-build instructions, project governance, reporting routes, and a viable contribution path.

**Observed:** [nodejs/node](https://github.com/nodejs/node/blob/75c198240026aaee2721135cca6df3e9d2df3de1/README.md#L1-L5) immediately routes application users to product information. [elixir-lang/elixir](https://github.com/elixir-lang/elixir/blob/759443e724f55bf58e71c0603644e99058918d52/README.md#L94-L101) explains why contributors need a source build. [hazelcast/hazelcast](https://github.com/hazelcast/hazelcast/blob/3647cd76f35c7c2bab9e2d0577629bfcbd040b51/README.md#L130-L132) scopes local contributor testing.

**Why it works:** It respects the difference between using a released artifact and changing its source. Governance, release verification, and contribution expectations can be the repository's central information rather than extraneous appendices.

**When it backfires:** A source-build path is presented as necessary for every user, contributor instructions dominate a user-facing package page without routing, or a rewrite removes verification and private reporting routes in pursuit of brevity.

**Preserve or adapt:** Retain attribution, governance, contribution standards, security contacts, and artifact-verification instructions where they have an explicit role. Improve routing and labels before relocating these sections. Avoid copying names or personal details into derivative assessment reports.

## Research, data, or asset repository

**Reader and job:** A researcher, experimenter, or asset user needs to understand intended use, obtain the right artifact or environment, and preserve provenance.

**Observed:** [jump-dev/JuMP.jl](https://github.com/jump-dev/JuMP.jl/blob/00f9391664e2e0f2c89acf7a9551c7ee26182284/README.md#L47-L62) supplies a reusable scholarly citation. [NVIDIA-NeMo/RL](https://github.com/NVIDIA-NeMo/RL/blob/3d650392f5d86b34288f5edf3b7173c89ba862b6/README.md#L239-L250) explains environment version selection. [polarsys/b612](https://github.com/polarsys/b612/blob/48ac6ba67ecab8123e8e36d6aa05367db0c7b638/README.md#L5-L24) connects font design criteria with source and release workflow.

**Why it works:** The evidence matches the work: citation for scholarly use, environment context for experiments, and visual design requirements for a font. These are related needs, not one universal layout.

**When it backfires:** A code-oriented template omits the actual asset download or specimen, citation is treated as optional decoration, or reproducibility pins are replaced with “latest” without testing. Research performance claims need conditions and reproduction context.

**Preserve or adapt:** Keep provenance, licensing, citations, environment constraints, data/model assumptions, and limitations. For assets, prioritize previews, formats, acquisition, and usage rights; for experiments, prioritize the supported environment and a representative result.

## Configuration reference with progressive disclosure

**Reader and job:** A user knows the basic feature and needs the configuration relevant to a host, language, or deployment.

**Observed:** [astral-sh/setup-uv](https://github.com/astral-sh/setup-uv/blob/56618cab7a58e3efc9b282dd3de75bbf1075db9b/README.md#L39-L46) labels exhaustive inputs separately from minimal usage. [gelguy/wilder.nvim](https://github.com/gelguy/wilder.nvim/blob/679f348dc90d80ff9ba0e7c470c40a4d038dcecf/README.md#L269-L291) gives separate Vim Script and Lua examples. [groue/GRDB.swift](https://github.com/groue/GRDB.swift/blob/0d8cf958b4b66a0473ec6e6986eb9da462171da9/README.md#L352-L358) recommends a package product and explains the alternative.

**Why it works:** Labels and grouping keep optional detail discoverable. A recommendation resolves a choice when the project can justify a default; parallel examples respect a choice the user has already made.

**When it backfires:** The only required prerequisite is hidden in an unlabeled fold, equivalent examples drift, or a reader must open several sections to assemble a single runnable path.

**Preserve or adapt:** Keep the smallest complete path visible or clearly reachable. Make disclosure labels say what is inside. Preserve host-specific syntax and ordering constraints. Verify both alternatives when editing shared examples.

## Relocation and generated pages

**Reader and job:** A visitor needs the current destination; or an editor needs to identify the authoritative source of generated reference material.

**Observed:** The entire [RubyGems AWS README](https://github.com/rubygems/rubygems-aws/blob/ac03a3e692472abe81934eb59833bcaa20cb877e/README.md#L1-L3) is a relocation notice. The inspected [xk6 CLI reference](https://github.com/grafana/xk6/blob/103897f741839bf710a496ed68ddcafb3b751581/README.md#L449-L513) demonstrates why repetitive command-reference formatting can still expose useful flags and exit codes; its generation ownership was not verified in this review.

**Why it works:** A relocation notice has a small, complete job. Generated content can maintain consistency with a command interface when the source-of-truth pipeline is known.

**When it backfires:** A moved repository retains active-looking instructions, or a prose cleanup edits generated output that will be overwritten. Repetitive formatting alone does not prove content is generated or unnecessary.

**Preserve or adapt:** Keep the replacement destination clear. Before editing generated-looking material, inspect markers, generation instructions, and the owning source. Do not infer its provenance from appearance.

## The same trait can help or hurt

| Trait | Helps when | Hurts when | Editing question |
|---|---|---|---|
| Table | Readers compare the same properties across meaningful choices | Cells contain unrelated essays or empty template categories | What decision does each column support? |
| Long contents list | A substantial manual has distinct lookup tasks | It repeats a tiny page or exposes an arbitrary heading hierarchy | Can a reader name a task and find its section? |
| Exact versions | They express compatibility, reproducibility, or a measured artifact | They duplicate a moving fact without an owner or explanation | What contract does this value represent, and who maintains it? |
| Screenshot or diagram | It shows product behavior, spatial layout, or a data path | It merely decorates or hides essential text | What does the reader learn from the actual rendered image? |
| Philosophy or history | It explains a design tradeoff, constraint, or project identity | It delays the answer without helping a choice | Would removing it obscure why the project behaves this way? |
| Badges | They expose actionable status or a useful destination | Their meaning is unclear or they dominate the opening visually | Which reader decision or route does each badge serve? |
| Installation alternatives | They match different platforms, hosts, or package ecosystems | They look like a sequence or leave a costly choice unexplained | Can the reader select one complete path? |
| Warning | It names a relevant condition and consequence near the action | It repeats generic caution or conceals a precise limitation | Which action changes because of this warning? |
| Output or transcript | It demonstrates success, error semantics, or a teaching point | It is an incidental run log presented as evergreen proof | Which observable behavior does this output establish? |
| Sponsor or contributor material | It supports attribution, project sustainability, and community routing | It makes the primary reader task hard to locate | Can ordering improve access without erasing the project's relationships? |

## Use the patterns without homogenizing the README

Name the current reader job and the facts that must survive. Borrow the smallest useful move: a better label, a direct example, a choice explanation, a reordered warning, or a clearer navigation group. Keep the project's voice and visual identity when they serve it. Trace the intended first action, then inspect the diff for changed commands, claims, anchors, and lost constraints. Verify factual and visual changes in their proper context. Stop when the reader's path is clearer; adopting more patterns is not itself an improvement.
