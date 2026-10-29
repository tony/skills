# Choose a form for the reader's job

These pinned examples demonstrate particular choices, not whole-project ratings.
Borrow their function, not their wording or branding. Source inspection establishes
the cited structure; it does not prove runtime success or measured reading speed.

## Route to maintained documentation

[http4s](https://github.com/http4s/http4s/blob/f81cb4ac926ffd65d94bb856908de5f11d1ffe22/README.md#L1-L25)
uses a small API preview and links to fuller docs. A short portal works when readers
can identify the project and reach the task they need. Add inline setup only when
the destination leaves a real gap; generic "learn more" links can conceal one.

## Show a complete representative operation

[Serde](https://github.com/serde-rs/serde/blob/fa7da4a93567ed347ad0735c28e439fca688ef26/README.md#L25-L74)
combines a round trip, dependency setup and expected output. Preserve the imports,
input and observable result that make the example useful. A short fragment with
unexplained fixtures or resources is a preview, not a runnable quickstart.

## Keep a manual useful for returning users

[just](https://github.com/casey/just/blob/e01a6bd7e7a30baf86bc86d2b95b0998ebbdc36f/README.md#L667-L815)
organizes recipes, dependencies and defaults for lookup. A long README can be the
right manual. Preserve stable task headings and contents links; shorten sections
only when the reader loses nothing. A contents list earns space through navigation,
not its position relative to the first command.

## Label real alternatives

[wilder.nvim](https://github.com/gelguy/wilder.nvim/blob/679f348dc90d80ff9ba0e7c470c40a4d038dcecf/README.md#L269-L291)
shows distinct Vim Script and Lua routes. Similar-looking instructions can serve
different hosts or clients. Help readers select one complete path; never make a
copy button execute alternatives together. Recommend a default only when supported.

## Match the repository's distribution model

[Node.js](https://github.com/nodejs/node/blob/75c198240026aaee2721135cca6df3e9d2df3de1/README.md#L1-L5)
routes application users away from its source-facing README.
[B612](https://github.com/polarsys/b612/blob/48ac6ba67ecab8123e8e36d6aa05367db0c7b638/README.md#L5-L24)
explains a font's design and release workflow. A contributor build or asset specimen
can be the next action; do not impose a package-install quickstart on every project.

## Preserve meaningful presentation

Tables help compare shared properties; prose explains a tradeoff. Screenshots can
demonstrate behavior, while text must still expose essential facts. Preserve useful
branding and sponsorship; assess placement and scale by the task they obstruct or
support. A desktop comparison needing horizontal scrolling on a phone does not,
by itself, need replacement. Measure the actual rendered article before judging it.
