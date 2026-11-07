# Evals

The eval suite of the `deckwright` plugin, run with Claude Code's own runner, [`claude plugin eval`](https://code.claude.com/docs/en/plugin-evals). It lives at the repo root rather than inside the plugin, so it never ships with it: the marketplace installs `./plugins/deckwright` and nothing outside it. Each case names the plugin itself, with `plugins: ["../../plugins/deckwright"]` in its frontmatter.

The script's computable parts are checked by the unit tests in [`tests/`](../tests/README.md). These cases check the skill's side: what it asks, says, suggests and records, and that it goes through the script to do it.

## Terms

- **Case**: a directory here with a `prompt.md` and `graders/`. **Run**: one agent session on one case.
- **Scripted player**: each prompt is the player's opening message followed by the player's whole side of the conversation, written in advance, with an instruction to play it through. A run is one turn: the agent asks, takes the answer from the script, and carries on.
- **Trace**: the run's session log, one JSON message per line. Most graders read it, the page `deck.html` the run leaves behind, or both.
- **Grader names** start with the name the spec gives the check (`bracket-push-flagged`). Where one check needs more than one grader, the others add a suffix after `--` (`bracket-push-flagged--on-page`). A check passes on a run when every grader under its name passes. `skill-fired` and `looks-up-before-describing--only-through-the-script` are preconditions without a spec id: a run in which the skill never loaded, or which fetched card facts round the script, says nothing about the checks.

## Run

From the repo root. `--allow-tools` applies to every case in a run, and the cases need different network and shell grants, so each tag has its own command.

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

Not recorded yet. Fill in from the first runs: per-run list-price estimate and wall-clock time per case.

## Reading a result

Results land in `evals/results/<timestamp>/`, which `evals/.gitignore` keeps out of git. Pass `--json result.json` for one file, and `--keep-temp` to keep each run's workspace and trace.

1. **Check for errors first.** A run that hit a usage or rate limit, a turn cap or the timeout usually scores 0 for reasons that are not the plugin's.
2. **Don't go by the exit code.** Compare each case with its Now in the [Cases](#cases) table.
3. **Read a failing run's trace before believing it.** A grader that did not expect how a correct run phrased something fails a correct run; fix the grader, not the skill.

### Known limits of the graders

- **An `llm` grader on the trace sees only its first 12 and last 12 messages.** A whole interview runs to more than that, so a judge asked about the middle of `build-a-deck` (suggestions, critiques, the wrong category) may not see the moment it is asked about. Each such check has a deterministic grader beside it where a pattern can decide part of it. Calibration (below) shows whether the judge holds up; where it does not, the case is split or the grader replaced.
- **Order in the trace is read by pattern.** `looks-up-before-describing--<card>` fails when an assistant message names the card before any `deck.py` lookup of it, except a message that says it is looking, checking or fetching. A mention that is not a description, such as "Meren, good choice", fails it too, which is stricter than the criterion. Read such a failure in the trace.
- **The trace patterns assume Claude Code's session JSON**: compact, a tool call as `"name":"Bash","input":{"command":"…"`, an assistant message carrying `"role":"assistant"` before its content, text blocks as `"type":"text","text":"…"`. If the runner's trace differs, every trace grader fails at once; that is the first thing to check on a first run.
- **The page is read at `deck.html`** in the working folder, where [`tests/README.md`](../tests/README.md) says the skill renders it in Claude Code, and by the `data-section` and `data-category` marks the unit tests also hold the page to.
- **Before the first real run, probe whether the run's sandbox lets Bash write in the workspace.** The script writes `deck.json`, the cache and the page there. The claude-design-skills suite reports that the sandbox mounted its workspace read-only to Bash; if that holds here, every case but `no-code-execution` fails until it is resolved.

## Judge calibration

Each `llm` grader gets one known pass and one known fail in `evals-calibration/<grader>--<pass|fail>-<n>/`, built from the first real run outputs: the pass a real output judged by hand, the fail the same output with one passage changed. The bar is agreement of at least 0.9 and no flips; a grader below it is reworded or replaced by a deterministic one. Not built yet: there are no run outputs.

The `llm` graders: `starts-with-commander`, `walks-template-in-order`, `suggests-per-category`, `critiques-named-card`, `wrong-category-called-out`, `collection-not-yet`, `player-bends-the-template--says-what-changed`, `illegal-commander`, `unknown-card`, `bracket-push-flagged`, `lookup-unavailable`, `no-code-execution`.

## Cases

**Now** is what the case does on the current text of the skill: runs that passed every grader out of runs made, and the known noise to read a drop against. When a change is judged, replace the case's Now.

| Case | Checks | Now |
|---|---|---|
| `build-a-deck` | The interview from "help me build a commander deck" to the page. Commander asked first (AC12); Lands then Ramp with purpose and target (AC13); suggestions with what each does (AC14); a declined suggestion never recorded (AC15); a named card critiqued (AC16); Sign in Blood filed as ramp called out (AC17); every named card looked up through the script before it is described (AC18); a tally after each category (AC20); the page rendered by the script (AC21) from a part-built deck (E8) as an HTML file (E13); a collection mention answered as not supported yet (E14); no price in chat (AC22) | not recorded yet |
| `bend-the-template` | Lands skipped, the Ramp target changed to 8, a jump to Mass disruption: deckwright follows and says what changed, and the later tally and the page use the new target (AC19); no price in chat (AC22) | not recorded yet |
| `card-traps` | Llanowar Elves as commander is refused from the lookup and the player asked (E7); "Vampiric Tutr" is not recorded until confirmed (E1); Lightning Bolt, outside Meren's colours, is kept and flagged on the page (E5); Sol Ring named twice is in once (E6); Vampiric Tutor, a Game Changer, is flagged as pushing past bracket 2 and kept (AC9b); no price in chat (AC22) | not recorded yet |
| `lookup-unavailable` | Scryfall out of reach: deckwright says so, names Sol Ring, asks for its text, describes nothing from memory, uses no web fallback, and the page marks the card as the player's text (E2); no price in chat (AC22) | not recorded yet |
| `no-code-execution` | Without a shell, deckwright says it needs code execution and how to turn it on, and does not start (E4); no price in chat (AC22) | not recorded yet |
