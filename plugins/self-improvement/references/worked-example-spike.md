# A worked example: spike, before this skill existed

The pass that became `/spike:loop` is this skill run by hand. The
starting prompt, the prompts it mined, and the edits they became.

## The starting prompt

```
/goal You're a pro at Claude and Codex Skills

This will be for improving: /spike:*, /spike:probe and /spike:bakeoff

study `uvx agentgrep` for prompts i've written w/ `depth:exhaustive`

Are there any things in between that we could use from those prompts
to bring upstream into our skills so prevent overhead and make them
smarter? Either as new defaults, reference examples, new arguments,
or new skills?

Still, while doing this, you want to keep bloat to a minimum. You
will YAGNI-check every line you write.
```

That is `/self-improvement:sweep` scoped to `spike`, plus the YAGNI
check, written before either half of this plugin existed.

## What the corpus showed

### Unnamed procedure: probe, bake off, graft, probe again

Typed instead of an invocation. Hosts that do not slash-invoke
skills wrote it with a sigil; hosts that do wrote the same cycle
as a numbered list.

```
First, do a $spike to try it out for real and surface stumbling
blocks you find, when you do, do a bakeoff of different approaches,
pick the best plus the grafts of others + then $spike, rinse and
repeat - taking planning notes along the way. when you finally have
it perfect, rewrite it all from scratch
```

```
Before final implementation, repeat `/spike:probe` cycles:
1. Inspect what translates directly vs needs redesign.
2. Spike real implementations.
3. When approaches differ, do a /spike:bakeoff, choose the best,
   graft useful ideas from others, then spike again.
4. Keep concise planning notes.
5. Once proven, rewrite cleanly from scratch using what you learned.
```

**Verdict:** Absent. Nothing in the plugin expressed iteration. The
stop condition was "when you finally have it perfect", which cannot
be evaluated. Retypings across language ports dropped different
steps, most often the planning notes.

**Landed as:** `/spike:loop` ([#74](https://github.com/tony/skills/pull/74),
[ced3fd4](https://github.com/tony/skills/commit/ced3fd4)). The
description triggers are the paste itself: "rinse and repeat",
"spike then bakeoff then spike again", "prove it out then rewrite
it from scratch". The stop conditions are converged, capped, or
thrashing. The ledger lives outside the working tree so a round's
own stash cannot swallow the notes.

### Continuation: bake off, then probe the grafted winner

Typed after another skill, session after session, across ports:

```
/spike:bakeoff if you want to try multiple approaches, then
/spike:probe the best pick with any grafts
```

**Verdict:** Absent as a named handoff. Bakeoff judged grafts on
paper; no contender was built with one applied.

**Landed as:** bakeoff marks grafts unproven in combination and
re-proves them
([20ea37d](https://github.com/tony/skills/commit/20ea37d)). Probe
reports stumbling blocks even on a successful path. The loop's next
round is the probe of the grafted winner.

### Paste: reference directories and a quality bar

The same preamble reappeared after the skill name: study corpora,
linters, an adversarial review.

**Verdict:** Present as context for any long task, not
spike-specific.

**Not proposed:** a `--reference` argument. The quality bar stayed
in the prompt.

## What this is showing

The useful output of a sweep is a prompt and the edit it became,
not a count. A finding that cannot name both is not ready to land.
