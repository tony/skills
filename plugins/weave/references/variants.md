# Weave variants

For commands that generate several originals per participant. Shared by `brainstorm`, `brainstorm-and-refine`, and `serene-bliss`; `<engine>` and `<session_dir>` are as in `ensemble-core.md`. The skill
supplies the prompt body, the preamble (if any), and what to show.

1. Resolve `variants` from the flags result (`variants`, `variants_recommended`,
   `preamble`); a skill that fixes the count skips the question. When it is
   null, ask with `AskUserQuestion`: "How many variants per participant? Each
   gets a distinct creative direction." Options: 1 (recommended), 2, 3. Without
   `AskUserQuestion`, use `variants_recommended`. Pass `--variants <variants>`
   to `init`.
2. Write the body to `<session_dir>/pass-0001/prompt.md`, as in `ensemble-core.md` (Dispatch lanes).
   A custom `preamble` goes to `<session_dir>/preamble.md`.
3. Every lane runs once per variant N of M, as its own invocation; combining
   variants in one call would anchor them. Compose each prompt with
   `--variant <N> --of <M>` into
   `<session_dir>/pass-0001/prompts/<lane>-v<N>.md`, adding
   `--preamble-file "<session_dir>/preamble.md"` when a preamble is set. The
   engine supplies a distinct direction per variant and no role preamble.
4. Sub-agents deliver `<session_dir>/outputs/<lane>-v<N>.md` by `ensemble-core.md` (Dispatch lanes, Reply delivery).
   `dispatch` takes the same `--variant <N> --of <M>` (and `--preamble-file`)
   and writes that path. Launch every lane and variant in the same turn.
5. Show the originals when the skill says to, after the repo guard closes:
   each under its participant name, with `Variant N` and its direction
   (Conventional, Creative, Contrarian) when there is more than one variant and
   no custom preamble. A failed variant becomes a note with its failure class.
   Never deslop originals; their diversity is the product.
