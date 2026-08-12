<!-- portable: verbatim-fences -->

# A worked example: spike, before this skill existed

The pass that became `/spike:loop` is this skill run by hand, months of
prompts read in one sitting. Every fenced block below is quoted from the
corpus or from the diff it produced, character for character. Nothing in
one is paraphrased, because the point of the example is what the
evidence actually looked like.

The outcome is
[pull request #74](https://github.com/tony/skills/pull/74), merged as
[`00e6215`](https://github.com/tony/skills/commit/00e6215).

## The ask that started it

```
/goal You're a pro at Claude and Codex Skills

This will be for improving: /spike:*, /spike:probe and /spike:bakeoff

study `uvx agentgrep` for prompts i've written w/ `depth:exhaustive` if you want to go deep

Are there any things in between that we could use from those prompts to bring upstream into our skills so prevent overhead and make them smarter? Either as new defaults, reference examples, new arguments, or new skills?

Still, while doing this, you want to keep bloat to a minimum. You will YAGNI-check every line you write.
```

That is `/self-improvement:sweep` scoped to one plugin, plus a YAGNI
check, written before either half of this plugin existed. "Things in
between" is the whole thesis: the text people type *around* an
invocation is the skill's gap, stated by the person who hit it.

## What the corpus held

One procedure, retyped seven times, never the same way twice.

Four times as a sentence:

```
do a $spike  to try it out for real and surface stumbling blocks you find, when you do, do a $bakeoff of different approaches, pick the best plus the grafts of others + then $spike, rinse and repeat - taking planning notes along the way
```

```
do a $spike to try it out for real and surface stumbling blocks you find, when you do, do a bakeoff of different approaches, pick the best plus the grafts of others + then $spike , rinse and repeat - taking planning notes
```

The other two vary only in whether `bakeoff` carries the sigil and
whether "along the way" survives. Three more times as a numbered list:

```
Before final implementation, repeat `$spike` cycles:
1. Inspect Python libtmux and identify what translates directly vs needs redesign.
2. Spike real implementations against real tmux.
3. Where approaches differ, do a bakeoff, select the best, graft useful ideas from alternatives, then spike again.
4. Keep concise planning notes.
5. Once proven, rewrite cleanly from scratch using everything learned.
```

```
3. Where approaches compete, do a bakeoff, choose the best, graft useful ideas, then spike again.
```

```
1. Inspect Python libtmux and classify what translates directly vs needs redesign.
```

Seven retypings, no two identical, each drifting a step. Step 4 — the
planning notes — is the one that goes missing most often, and it is the
reason to run rounds at all.

Both shapes carry `$spike` and `$bakeoff`. Not one of the seven names a
skill the way either host actually invokes one — which is what "typed
instead of an invocation" means in practice. A count of `/spike:` finds
zero of them. The procedure with the strongest case for becoming a
skill is precisely the one that invocation counting cannot see.

Every genuine retyping is a Codex record. That is not a fact about
Codex; it is a fact about where this particular exploration happened,
and it is only visible because the Claude side turned out to be the
sweep's own reflection. A per-host count taken without that subtraction
would have reported the cycle as evenly split and hidden both facts.

## Reading it wrong, first

The first search looked complete and was not:

```console
uvx agentgrep --color never search --exhaustive '"rinse and repeat"' --limit 40 --no-progress --json
```

```
{"state":"bounded","reason":"result_limit","conditions":["result_limit"]}
matches_seen: 69
```

Forty results returned against sixty-nine matches. `state` reads
`bounded`, not `complete` — but a reader who checks only the result
count sees forty findings and no error.

Re-running at `--limit 2000` returned `complete`, seventy matches, and
forty-eight records. Three numbers, three meanings: seventy is every
occurrence, forty-eight is what survives deduplication, and the extra
match over the first run's sixty-nine was created *by the sweep* — the
session running it had written the phrase down in between.

Spread then misled in the opposite direction. Project attribution came
back twenty-five occurrences in a single repository, which reads as a
pattern confined to one project and therefore not a finding at all.
Every one of those twenty-five was this repository, and every one was a
session working on the sweep, quoting the prompt back.

Strip them and the genuine evidence is entirely Codex: twenty-three
records, which carry no project field at all. So the spread that
mattered was never countable from the result — it had to be read off
the prompts themselves, which name the ports they were written for. A
sweep that had trusted the attribution would have scored this finding
one project and dropped it.

Host attribution held up. Once the sweep's own noise came out, the
cycle sat in twenty-three Codex records and twenty-five Claude records
— genuinely both, not an artifact.

## Finding one: the cycle had no name

**Category:** unnamed procedure — typed instead of an invocation.

**Verdict:** absent. Nothing in the plugin expressed iteration at all.
Probe answered whether one path works and bakeoff answered which of
several is best; neither settled what the design should be.

The stop condition in every retyping was *"when you finally have it
perfect"*, which cannot be evaluated, which is why every retyping
needed a human to decide when to quit.

**Landed as** a new skill, `/spike:loop`, whose stop conditions are
falsifiable and ordered:

```
- **Thrashing** — the round surfaced stumbling blocks, but every one
  was already recorded and decided in an earlier round. Repetition is
  evidence that more spiking cannot settle the question; stop and
  surface it rather than spending another round.
- **Converged** — the round surfaced no stumbling block at all.
- **Capped** — `--rounds` is exhausted.
```

Thrashing is the one the retypings could never express: it reports
that more spiking *cannot* settle the question, rather than spending
another round discovering that.

The dropped planning notes became a ledger with a load-bearing
location, since a round stashes its own working tree:

```
The ledger lives at `<that path>/spike/<goal-slug>.md`. That location
is load-bearing, not a preference: a ledger kept in the working tree
gets swallowed by the round's own `git stash push -u`, erased by
`git clean -xdf`, and shows up as an untracked file in every
`git status` the user reads.
```

`/spike:probe` also gained the thing the cycle branched on. Before,
stumbling blocks were not a concept; after:

```diff
+- Record **stumbling blocks** — the places the approach itself fought
+  back: an API that will not compose, a type that cannot be expressed,
+  a constraint that surfaced too late to design around. A stumbling
+  block is neither a `SPIKE:` marker (a shortcut you chose) nor an
+  adjacent problem (out of scope); it is evidence the *approach* may be
+  wrong, which makes it the reason to reach for `/spike:bakeoff` and
+  the input the next probe sharpens against.
```

And it reports them even on success, because the old contract buried
the case for a bakeoff whenever the probe happened to work:

```diff
-2. `## Spike findings` — what was proven, `SPIKE:` markers, observed-
-   not-addressed list.
+2. `## Spike findings` — what was proven, stumbling blocks, `SPIKE:`
+   markers, observed-not-addressed list. State the stumbling blocks
+   even when the probe succeeded: a path that worked while fighting
+   you the whole way is the case for `/spike:bakeoff` or
+   `/spike:loop`, and reporting only the success buries it.
```

## Finding two: grafts landed without ever being run

**Category:** continuation — typed *after* an invocation, session after
session.

```
Once you have a graft selected, then go ahead and do the graft in a spike:probe
```

```
/spike:probe Double check 1-8 work without any hitches - without committing, and confirm the winning + grafted approach works:
```

And the defect named outright, in a prompt that was not about skills at
all:

```
The exception's provenance fields (over, env_var, env_value) came in as a graft from a losing contender — nobody has confirmed a user wants them.
```

**Verdict:** absent as a named handoff, and worse than absent as a
mechanic. A bakeoff judged grafts on paper. The winner's stash was
proven *without* them, no contender was ever built *with* them, and
`--replay` would land the combination anyway.

**Landed as** an explicit unproven marking with a re-probe exit:

```diff
 - **Grafts**: plan items that pull specific hunks from runner-up
   stashes (identified by SHA and file), stated as recommendations.
+  Mark them **unproven in combination**: the winner's stash was proven
+  without them and no contender was ever built with them, so a graft
+  is a hypothesis judged on paper until the shared proving check runs
+  on the combined tree. When the grafts are substantial enough that
+  landing them blind is the wrong call, recommend re-probing instead:
+  apply the winner's stash and the graft hunks, then run
+  `/spike:probe` on that tree, answering its dirty-tree halt with
+  *probe on top of it* — the seeded tree is the intended starting
+  point, not stray work.
```

Plus per-item re-proving during replay, which is the fix the second
prompt was asking for:

```diff
+Grafts get their one real test here: re-run the shared proving check
+before committing **each** plan item that carries a graft, not once
+after the last one — a graft that lands in an early item is already
+history by the time a later check fails, and dropping it would mean
+rewriting commits this phase never authorizes.
```

The panel gained the exit the user had been typing by hand:

```diff
-7. End with an `AskUserQuestion` panel: replay the winner / keep
-   stashes and stop / discard all
+7. End with an `AskUserQuestion` panel: replay the winner / probe the
+   grafted winner (`/spike:probe`, still zero commits) / keep stashes
+   and stop / discard all
```

## What was rejected

The same preamble kept reappearing after the skill name: study
directories, linters, an adversarial reviewer.

**Verdict:** present as context for any long task, not spike-specific.

**Not proposed:** a `--reference` argument. The quality bar stayed in
the prompt, where it belongs, and the sweep said so rather than growing
the skill an argument it would have to explain forever.

One more constraint was retyped often enough to look like a finding:

```
yes the whole point of it is probe AND bakeoff WILL mutate code, the whole point of spike is its mutating code to try it, but stashing it, NOT committing it in any way
```

That one was already written into both skills and already binding.
Repetition alone did not make it a gap; it made it an invariant the new
skill had to preserve, which is a different thing and produced no edit
of its own.

## What the sweep cost

One exhaustive query reads every store on disk. Measured on one machine
on one day, that was around 960 sources and 420,000 records in well
under two minutes — the unit cost of a *single* query, which is why the
run saved its JSON and re-sliced it locally for every question after
the first.

## What this is showing

The useful output of a sweep is a prompt and the edit it became, side
by side. Seven retypings justified one new skill. One sentence about
provenance fields justified three hunks in an existing one. A preamble
that recurred just as often justified nothing, and saying so is what
kept the plugin from growing an argument nobody needed.

A finding that cannot show both halves is not ready to land.
