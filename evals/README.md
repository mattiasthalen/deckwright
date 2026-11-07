# Evals

The eval suite of the `deckwright` plugin, run with Claude Code's own runner, [`claude plugin eval`](https://code.claude.com/docs/en/plugin-evals). It lives at the repo root rather than inside the plugin, so it never ships with it: the marketplace installs `./plugins/deckwright` and nothing outside it. Each case names the plugin itself, with `plugins: ["../../plugins/deckwright"]` in its frontmatter.

The script's computable parts are checked by the unit tests in [`tests/`](../tests/README.md). These cases check the skill's side: what it asks, says, suggests and records, and that it goes through the script to do it.

## Terms

- **Case**: a directory here with a `prompt.md` and `graders/`. **Run**: one agent session on one case.
- **Scripted player**: each prompt is the player's opening message followed by the player's whole side of the conversation, written in advance, with an instruction to play it through. A run is one turn: the agent asks, takes the answer from the script, and carries on. The four scripted cases also carry the same `append_system_prompt` in their frontmatter: the player's whole side is already in the first message, the agent says and asks everything it would to a live player but takes each reply from the script instead of ending its turn, it ends its turn only after the script's last line that applies, and it does not write the player's lines out. It is there because runs ended early: in the first `--runs 8` pass, 6 of 24 network runs ended after 4 or 5 turns with no `deck.py` call, and kept probes ended mid-script right after a question to the player, or after writing the player's answer out themselves. It is scaffolding only and says nothing about what the skill should do. With it, 1 of 32 network runs has ended early since (the `--runs 8` judge passes of `build-a-deck`, `bend-the-template` and `card-traps` on its current wording), against 1 of 6 under a first wording that told the agent to carry on "as if you had just received" each reply. That wording also had one run record a card it should have asked about first, so the prompt now says to ask everything a live player would be asked. Runs still write the player's lines out, about one echo per message, despite the instruction; the graders allow for it (see Known limits).
- **Trace**: the run's session log, one JSON message per line. Most graders read it, the page `deck.html` the run leaves behind, or both.
- **Grader names** start with the name the spec gives the check (`bracket-push-flagged`). Where one check needs more than one grader, the others add a suffix after `--` (`bracket-push-flagged--on-page`). A check passes on a run when every grader under its name passes. `skill-fired` and `looks-up-before-describing--only-through-the-script` are preconditions without a spec id: a run in which the skill never loaded, or which fetched card facts round the script, says nothing about the checks.

## Run

From the repo root. `--allow-tools` applies to every case in a run, and the cases need different network and shell grants, so each tag has its own command.

### On a Linux host such as a cloud container

The run's OS sandbox needs `bubblewrap` and `socat` (`apt-get install -y bubblewrap socat`), and `TMPDIR` must point at a folder outside `/tmp`:

```sh
mkdir -p ~/evaltmp && TMPDIR=~/evaltmp claude plugin eval . …
```

Each run's own settings deny writes to `//tmp`, and the runner makes the run's workspace under `TMPDIR`; left at `/tmp`, the workspace is read-only to Bash, `deck.py` cannot write `deck.json` or the page, and every case but `no-code-execution` fails.

| What | Arguments after `claude plugin eval . --model claude-opus-5 --judge-model claude-opus-5 --ablation none` |
|---|---|
| `build-a-deck`, `bend-the-template`, `card-traps` (Scryfall reachable) | `--tag network --scaffold --allow-tools Bash Write Edit "WebFetch(domain:api.scryfall.com)"` |
| `lookup-unavailable` (Scryfall blocked) | `--tag offline --scaffold --allow-tools Bash Write Edit` |
| `no-code-execution` (no shell) | `--tag no-bash` |
| One case, once, while iterating | its tag's arguments with `--case <name> --runs 1` in place of `--tag` |
| While working | its tag's arguments with `--runs 3` |
| Judging a change | its tag's arguments with `--runs 8 --json result.json` |

Add `--trust-plugin` when the run cannot stop to ask, such as under `--json` or in CI.

Why the grants differ:

- **Network.** A shell command runs under the run's OS sandbox, which reaches only the domains granted with `WebFetch(domain:…)`. The three `network` cases need `api.scryfall.com`, because the skill looks up every card it suggests and nobody can know those cards in advance. Each case's scaffold still pre-fills the lookup cache (`deckwright-cache/`, laid out as [`tests/README.md`](../tests/README.md) fixes) with every card the scripted player names, so the cards the graders depend on never wait on the network. The same grant would let the agent call WebFetch itself, which is why those cases carry `looks-up-before-describing--only-through-the-script`.
- **Offline.** `lookup-unavailable` is run without the grant, so the script cannot reach Scryfall. Its cache holds only the commander, since a deck cannot be started without one.
- **No shell.** `no-code-execution` is run with no `Bash` grant, which is how a Claude Code session looks without code execution.

### Pinned settings

| Setting | Value | Why |
|---|---|---|
| `--model` | `claude-opus-5` | Whether a skill triggers depends on the model, so it is pinned and a model rollout is not read as a plugin regression. |
| `--judge-model` | `claude-opus-5` | The default judge is a small fast model; several rubrics here ask what a critique said and why. |
| `--ablation` | `none` | Without the plugin there is no script and no template, so a baseline arm scores 0 by construction and doubles the cost. |
| `--runs` | 1 while iterating, 3 while working, 8 to judge | The spec judges each eval check at `--runs 8`: it passes when it passes every run. |
| `--max-cost-usd` | none | Runs are bounded by each case's `max_turns` and `timeout_seconds`. |

### Cost and time

From the latest `--runs 8` pass of each case on 2026-11-07, as the runner reported it: the mean list-price estimate per run (the agent run, plus the judge where a case has one) and the median wall-clock time.

| Case | Per run | `--runs 8` | Median run | Pass |
|---|---|---|---|---|
| `build-a-deck` | 0.65 USD | 5.18 USD | 88 s | judge6 |
| `card-traps` | 0.69 USD | 5.52 USD | 117 s | judge7 |
| `bend-the-template` | 0.60 USD | 4.78 USD | 87 s | judge7 |
| `lookup-unavailable` | 0.42 USD | 3.34 USD | 65 s | judge3 |
| `no-code-execution` | 0.17 USD, of which the judge 0.01 | 1.33 USD | 20 s | judge2 |

A judging pass over all five is about 20 USD.

## Reading a result

Results land in `evals/results/<timestamp>/`, which `evals/.gitignore` keeps out of git. Pass `--json result.json` for one file, and `--keep-temp` to keep each run's workspace and trace.

1. **Check for errors first.** A run that hit a usage or rate limit, a turn cap or the timeout usually scores 0 for reasons that are not the plugin's.
2. **Don't go by the exit code.** Compare each case with its Now in the [Cases](#cases) table.
3. **Read a failing run's trace before believing it.** A grader that did not expect how a correct run phrased something fails a correct run; fix the grader, not the skill.

### Known limits of the graders

- **An `llm` grader with `focus: trace` cannot judge an interview, so none is used.** Measured on the first runs (2026-11-07): the judge gets the trace's first 12 and last 12 lines, and the trace is mostly streaming fragments. A `build-a-deck` run is 813 lines, 670 of them `content_block_delta`; both ends are the init line, deltas and the result line, so no assistant message from the interview reached the judge, and all ten such graders failed 3 of 3 votes on runs whose behaviour was correct. Every check they held is now decided by `regex` over the assistant messages, beside the `tool_used` and page graders it already had. The one `llm` grader left, `no-code-execution`, uses `focus: last_message`, which a run of one reply fills.
- **The judgement checks are read by wording.** `starts-with-commander`, `walks-template-in-order`, `suggests-per-category`, `critiques-named-card`, `wrong-category-called-out`, `collection-not-yet`, `illegal-commander`, `unknown-card`, `bracket-push-flagged`, `lookup-unavailable` and `player-bends-the-template--says-what-changed` each require every part of the criterion in one assistant message, near the card or category it is about, and each part as one of a set of phrasings: the purpose from `counts_when`, "taps for {C}{C}", "makes no mana", "not supported yet", "not legendary", a question mark where the criterion says *asks*. Each grader's comment says what it requires and in what window. The sets are taken from four real runs and widened beyond them, but a correct run that says it some other way fails, which is stricter than the criterion; read such a failure in the trace and widen the set, never the window. A list of suggestions passes `suggests-per-category` when two of its items carry a line of 15 characters or more after the name: the grader sees that each says something, not that it is true.
- **A run plays both sides in one message**, echoing the player's answers ("You said: card advantage", "(Taking your answer: …)"). A window that runs past the question handing the choice back would read the player's words as the assistant's, so the windows of `wrong-category-called-out` stop at the first question mark after the card, and `lookup-unavailable--nothing-said-before-the-text` stops at the question asking for the text. The `looks-up-before-describing--<card>` graders do not count a mention inside an echo: on a quoted line (`> *"Add Sign in Blood as ramp."*`), inside "(Taking your answer: …)", or straight after "You said:". A description written into the same line after the echo is not seen.
- **Order in the trace is read by pattern.** `looks-up-before-describing--<card>` fails when an assistant message names the card before any `deck.py` lookup of it, except a message that says it is looking, checking or fetching. A mention that is not a description, such as "Meren, good choice", fails it too, which is stricter than the criterion. Read such a failure in the trace.
- **A tally counts only as a Bash call of its own.** `tally-after-category--after-lands` and `--after-ramp` want `tally` in a later Bash call than the `add` before it, as the skill tells it to run; a run that chains `add … && tally` in one command fails them though the tally ran. `tally-after-category--no-count-before-a-tally` and `player-bends-the-template--later-tally-uses-it` count `new` and `add` as tally runs too, since both print the tally: a run that shows Lands at 0 / 38 straight after `new` is showing the script's count.
- **The trace patterns assume Claude Code's session JSON**: compact, a tool call as `"name":"Bash","input":{"command":"…"`, an assistant message carrying `"role":"assistant"` before its content, text blocks as `"type":"text","text":"…"`. The trace carries every text twice, once as that `assistant` line and once as stream deltas; the patterns anchor on the `assistant` line. A line break inside a text is the two characters `\n`, so `\b` does not hold before a word that starts a line (`\nKeep` has no boundary); the patterns write a word start as `(?:\b|(?<=\\n))`. If the runner's trace changes, every trace grader fails at once; that is the first thing to check.
- **The runner's regexes run on JavaScriptCore, which gives up where V8 does not.** `claude` is a Bun binary, and a regex that backtracks past JavaScriptCore's limit reports no match rather than an error. So a `contains` grader fails a run that has the match, and a `not_contains` grader passes a run that has it. Measured on the final `build-a-deck` pass (2026-11-07): `starts-with-commander` failed 6 of 8 runs in the runner and passed all 8 under node. Each lazy walk of the form `(?:(?!guard)[\s\S])*?` takes one step per character. Before the commander question, the six failing runs had 10,900 to 12,300 characters on assistant lines, where the guard is tried at every character, against 9,400 to 9,500 in the two that passed. The six were also the runs whose Skill call carried `"args":"commander deck"`; nothing else about them differed. The generated walks now pass a whole trace line in one step when the line holds neither `"name":"Bash"` nor `"role":"assistant"`, the two places every guard and every pattern after a walk can start. A line is passed either whole or one character at a time, never both, or a failing match would retry every split. On every kept trace, and on each final-pass trace repeated four times, Bun and node now agree on every regex grader. [`tools/grade-trace.mjs`](tools/grade-trace.mjs) runs itself under `bun` when it can and marks `ENGINES DIFFER` on any grader where V8 disagrees: such a grader is near the limit and needs a cheaper pattern.
- **The page is read at `deck.html`** in the working folder, where [`tests/README.md`](../tests/README.md) says the skill renders it in Claude Code, and by the `data-section` and `data-category` marks the unit tests also hold the page to.

## Judge calibration

Each `llm` grader gets one known pass and one known fail in `evals-calibration/<grader>--<pass|fail>-<n>/`, built from real run outputs: the pass a real output judged by hand, the fail the same output with one passage changed. The bar is agreement of at least 0.9 and no flips; a grader below it is reworded or replaced by a deterministic one. The one `llm` grader is `no-code-execution`; its calibration is not built yet.

The ten trace `llm` graders were replaced, not calibrated, since they never saw what they judged. Their replacements were held to the same pairs without a judge: each passes on the real traces of `build-a-deck`, `card-traps`, `lookup-unavailable` and `bend-the-template` from 2026-11-07 (and the `build-a-deck` ones on the other three traces too, where those runs reached the same moment), and fails on a copy of the trace with one passage changed: the category's target or purpose removed, the suggestions cut to names, the critique cut to "recording it", the reason or the category dropped from the call-out, the question removed. [`tools/grade-trace.mjs`](tools/grade-trace.mjs) applies a case's deterministic graders to a kept trace, so a grader change can be checked this way without a run. It gives the runner's verdicts when `bun` is on the PATH (or named by `$BUN`); without it, it warns that V8's verdicts can pass what the runner fails.

## Cases

**Now** is what the case does on the current text of the skill: runs that passed every grader out of runs made, and the known noise to read a drop against. When a change is judged, replace the case's Now.

| Case | Checks | Now |
|---|---|---|
| `build-a-deck` | The interview from "help me build a commander deck" to the page. Commander asked first, before any category or script call (AC12); Lands then Ramp, each with its purpose and target (AC13); Ramp suggestions, each with what it does (AC14); a declined suggestion never recorded (AC15); Sol Ring critiqued with what it does and that it is Ramp (AC16); Sign in Blood filed as ramp called out as not ramp, with why and where it counts, before it is recorded (AC17); every named card looked up through the script before it is described (AC18); a tally after each category (AC20); the page rendered by the script (AC21) from a part-built deck (E8) as an HTML file (E13); a collection mention answered as not supported yet, without asking for the collection (E14); no price in chat (AC22). All by pattern and page | 2 of 8 at `--runs 8` (final pass, 2026-11-07, skill at 36268c3), 8 of 8 regraded: all six misses were `starts-with-commander` past JavaScriptCore's backtracking limit (see [Known limits](#known-limits-of-the-graders)), not the skill. Then 2 of 3 at `--runs 3` on the fixed graders, in the runner: the miss is a real failure, Sol Ring recorded with no critique and Sign in Blood filed under Card advantage with no word that it is not ramp (AC16, AC17). Earlier: 7 of 8 (judge6), the miss `starts-with-commander` on "First thing I need is your commander. Who's leading the deck?", since accepted. |
| `bend-the-template` | Lands skipped, the Ramp target changed to 8, a jump to Mass disruption: deckwright follows and says Ramp's target is now 8, and the later tally and the page use the new target (AC19); no price in chat (AC22). All by pattern and page | 7 of 8 at `--runs 8` (judge7, 2026-11-07, current skill text), 8 of 8 regraded: the miss was `player-bends-the-template--later-tally-uses-it` on a run that showed Ramp at 1 / 8 from `add`'s printed tally and ran no separate `tally`, a correct run that is now accepted. |
| `card-traps` | Llanowar Elves as commander: looked up, said not to be legendary and unable to lead, the player asked, no deck started with it (E7); "Vampiric Tutr": not found said, Vampiric Tutor named and asked about, nothing recorded until then (E1); Lightning Bolt, outside Meren's colours, kept and flagged on the page (E5); Sol Ring named twice is in once (E6); Vampiric Tutor, a Game Changer, said to push the deck past its bracket and asked about before it is recorded, and named under the bracket on the page (AC9b); no price in chat (AC22). All by pattern and page | 6 of 8 at `--runs 8` (final pass, 2026-11-07, skill at 36268c3), 8 of 8 regraded: the misses were correct replies the patterns did not accept, `bracket-push-flagged--says-game-changer` on "It's a Game Changer" 530 characters after the card's name and `unknown-card` on "Scryfall didn't have \"Vampiric Tutr\"", both now accepted. Earlier: 7 of 8 (judge7), the miss an early end: the run stopped after writing out the player's "Keep it anyway." at Lightning Bolt, so the second Sol Ring and the page never came. Known real failure, seen once under the scripted-player prompt's first wording: Vampiric Tutor recorded before it was flagged. |
| `lookup-unavailable` | Scryfall out of reach: deckwright says it could not look Sol Ring up, names it and asks for its text; nothing about it is said before that question; no web fallback; the page marks the card as the player's text (E2); no price in chat (AC22). All by pattern and page | 8 of 8 at `--runs 8` (judge3, 2026-11-07). |
| `no-code-execution` | Without a shell, deckwright says it needs code execution and how to turn it on, and does not start (E4, judged on the last message); no price in chat (AC22) | 8 of 8 at `--runs 8` (judge2, 2026-11-07), on the reworded rubric. The skill text has changed since (a critique before every card is recorded, one script command per shell call, the per-card order), so this is a figure on an earlier skill text. |
