# Comment policy

The shared reference for `lean-writing` and the `lean-trim-comments` skill.
Governs code comments and docstrings; for prose slop see
`./lean-rubric.md`.

## The three gates

A comment ships only if it passes all three. Fail any: delete or
rewrite. Borderline: delete — borderline means the information is
reconstructible, which is what makes deletion cheap.

**Loss.** Three years from now, would losing this cost a maintainer
real time rediscovering intent, an invariant, a constraint, or a
failure mode the code and tests do not already make obvious?

**Elite.** Would SQLite, Redis, the Go standard library, or CPython
write this comment, at this length? Those projects state the
constraint and stop. They do not argue with an imagined objector.

**Upkeep.** Will it stay true without maintenance? A comment that
hand-syncs a value the code owns — a count, an offset, a line
reference, a duplicated constant — is false the first time that value
moves.

## Ceiling

One or two lines. A comment reaching four is either carrying several
facts, in which case split it, or arguing, in which case cut it to the
fact.

Rationale, alternatives weighed, and the story of how the code got
here belong in the commit message: timestamped, attached to the exact
diff, and free to maintain.

## Exemptions

Doctests, minimal usage examples, and param, return, and raises lines
on public API are exempt from the loss gate — they serve the caller,
not the maintainer. They are exempt from nothing else. Ceiling: a good
man page entry.

Doctests are the one comment form with built-in upkeep. They execute,
so they cannot silently lie.

## Keep

- Why over how: upstream quirks, protocol and compatibility
  constraints, performance tradeoffs still part of the contract.
- Invariants, preconditions, ordering, lifetime, and concurrency
  requirements that types and tests cannot express.
- Code that looks wrong but is not, so a later cleanup does not
  reintroduce the bug.
- A high-level sketch of an algorithm whose local operations do not
  reveal the whole.

## Delete

- Narration of the next lines; code translated into English.
- Restated names, types, defaults, or control flow.
- Values duplicated from the code and hand-synced.
- Justification, hedging, or apology for a choice.
- Speculation about future requirements.
- History version control already holds, including commented-out code.
- Ticket and issue numbers. They say nothing to a reader without
  tracker access, and they rot when the tracker moves. Unfinished work
  goes in the tracker, not the source.
- Transient observations — "currently", "for now", "the latest
  release" — that go stale with no nearby edit.

## Validation order

Run these in order on every comment, new or existing.

1. Recoverable from names, types, tests, and layout? Delete.
2. Transient observation rather than a durable fact? Delete.
3. Justifying rather than documenting? Move it to the commit message.
4. Needs hand-maintenance to stay true? Move the fact into code, or
   delete.
5. Better carried by a name, constant, assertion, or test? Do that,
   and keep only what remains unsaid.
6. Cut every sentence that does not change a reader's decision or risk
   assessment.
7. Compress. "Prevents the API timeout." not "We do it this way
   because otherwise the API will time out."
8. Re-run the three gates.

## Calibration

Delete — fully recoverable:

```python
# Increment the retry count.
retry_count += 1
```

Delete — two hand-synced values, stale the first time either moves:

```python
# Handles all 4 retry states (see line 212).
```

Delete — an unfinished thought, and it belongs in the commit:

```python
# Went with a dict over a class for now, may revisit.
```

Keep — a durable constraint, invisible in the code, nothing to sync:

```python
# Monotonic: wall-clock adjustments must not shorten the lease.
deadline = monotonic() + timeout
```

Keep — what the loss gate exists to protect. `tmux < 3.2` is a frozen
external fact, not a value tracking your own code:

```python
# tmux < 3.2 reports the pane ID only after the command completes,
# so this query must stay separate.
```

Keep — exempt from the loss gate, passes concision:

```python
:param timeout: Maximum seconds to wait for the tmux command.
```

Rewrite — the same fact, with the argument cut away:

```cpp
// By value, though the answer is cached and a reference would be
// valid. The default argument builds a temporary `path`, and a
// function that takes a reference and returns one is
// indistinguishable — to GCC's `-Wdangling-reference`, and to a
// reader — from one that hands back a reference into that temporary.
// `Version` is four scalars; copying it costs nothing next to being
// obviously correct.
```

```cpp
// By value: the default argument is a temporary `path`, which GCC's
// `-Wdangling-reference` cannot tell apart from a borrow.
```

## Why this does not backfire

The loss gate is the safety valve: deletion bias fires only on
reconstructible information, and anything irreplaceable passes it. The
upkeep gate targets values that track your own code, never frozen
external facts, so it cannot reach the tmux comment above. Relocating
justification to the commit message loses nothing; it lands somewhere
better.

Do not read "explain why, not what" as absolute — a dense algorithm
earns a description of what it does. Do not invent an abstraction to
retire one precise comment. Do not treat a test as a substitute for
rationale; a test pins behavior without saying why that behavior
matters. Do not measure the result by comment count.
