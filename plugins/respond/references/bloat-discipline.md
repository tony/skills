# Bloat Discipline

What a fix is allowed to add. Screening decides *whether* a finding is
worth acting on; this decides what the action costs once it is.

The premise is that this loop runs constantly. A project that reviews
every branch with humans and machines accumulates fixes at a rate no
single reviewer sees, and every one of them leaves behind a guard, a
test, or a comment. Individually each is defensible. In aggregate they
are the reason a codebase becomes hard to read without anyone having
written anything bad.

## Why now, why this

Two questions before the first edit, answered per finding:

**Why now** — what makes this branch the place? Either this branch
caused it, or shipping the branch without it breaks something. A fix
that would have been equally welcome last month and will be equally
welcome next month is a backlog item, and the honest response is a
follow-up, not a commit stapled to unrelated work.

**Why this** — what is the smallest change that removes the defect?
Not the change the reviewer proposed; reviewers propose mechanisms
where a condition would do. Cost the smaller fix, and say so in the
reply when the difference matters.

## Test bloat

Add a test when it pins behavior that this branch got wrong, or could
plausibly get wrong again, **and** no existing test would catch the
regression. Both halves are required. A test that duplicates coverage
already present buys nothing and costs a name, a fixture, and a
maintenance obligation on every future refactor.

Extend an existing test before adding a new one. A case appended to a
parametrized list is free to read; a new file with its own setup is
not.

A test that only proves the reviewer's hypothetical can be constructed
is testing the test. If the scenario needs the test to build a state no
caller can produce, the finding failed the odds gate and this fix
should not exist.

Never assert the implementation's shape — mock call counts, internal
ordering, private attribute values — in place of its behavior. Those
tests fail on refactors that broke nothing and pass through changes
that broke everything.

## Comment bloat

The test for a comment: **would a reader three years from now, with no
memory of this review and no access to it, be worse off without this
line?**

Keep the ones that survive it. Invariants that the code cannot state
itself, protocol and platform constraints, security boundaries, an
upstream bug the workaround exists for, and the reason the obvious
implementation is wrong here — that reason is the single most valuable
comment class and the one most often missing.

Delete, or never write:

- Comments restating the code the reader is already looking at.
- Change narration — "now also handles empty input", "moved from the
  parser" — which describes a diff the reader does not have.
- Review breadcrumbs: "per review feedback", "as discussed", the
  reviewer's name, a link back to the thread.
- **Ticket, issue, and pull request numbers.** A number is a pointer to
  a system the reader may not have, holding a discussion that assumes
  context they lack, about a decision that may have been superseded.
  Where the context matters, state the constraint itself — that is what
  the number was standing in for. A pinned upstream link explaining a
  workaround in someone else's code is different: that is evidence for
  a reader who would otherwise delete the workaround, and it stays.

The concision rule for comment findings runs the same direction: when a
reviewer asks for a comment to be clearer, the rewrite is shorter than
what it replaces. A finding that grows the comment block has been
misread.

## Complexity bloat

Each of these is a fix that costs more than the defect:

- A guard for a state the type system or the caller already excludes.
- A `try`/`except` around code with no reachable failure mode, which
  converts a loud bug into a silent one.
- An abstraction, indirection, or helper with exactly one caller.
- A configuration knob nobody asked for, which is a promise to support
  both settings forever.
- An early return duplicating a check the caller just made.
- A new dependency for something the standard library does adequately.

When a finding's only available fix is one of these, the finding is
answered in the reply, not in the code — and the reply says which
scenario would change the answer.

## Commit shape

One finding, one commit. Two findings share a commit only when they
edit the same lines, and the plan says so before it happens.

The commit message uses the project's own format and describes the
defect and the fix in the project's terms. It does not cite the finding
id, the reviewer, or the review — a future reader wants to know what
was wrong, not who noticed. The ledger holds the mapping from finding
to commit for as long as anyone needs it.
