# Judged checks

The criteria no test or eval decides. A fresh reviewer, who did not build the change, applies each rubric to the files it names and records PASS or FAIL with the quoted evidence. Every item in a rubric must hold for a PASS.

## AC3: the skill and the script take categories and targets from the template file only

**Read:** `plugins/deckwright/skills/interview/SKILL.md`, `plugins/deckwright/skills/interview/deck.py`, `plugins/deckwright/skills/interview/templates/commander.toml`.

**Rubric:** a new template file is the only change a new format needs.

1. Neither `SKILL.md` nor `deck.py` names a category of the Commander template (Lands, Ramp, Card advantage, Targeted disruption, Mass disruption, Plan) as data: no list of them, no `if category == "Ramp"`, no table of them in the skill's text. Naming one in an example the skill clearly marks as an example of the template's content, such as "for example, Ramp's target", is a FAIL too: the skill reads what to say from the template.
2. Neither names a target (38, 10, 12, 6, 30), the deck size (100) or the bracket target (2) as data.
3. The rule that Lands counts from the type line is stated in the template, not in the script: the script reads from the template which category is counted from the type line, and what the type line must include.
4. The skill tells the agent to take each category's purpose, target and "counts when" from the template the script loaded, and to pick the template by the format the player names.
5. Imagining a `templates/<format>.toml` for another format, with its own deck size, bracket target and categories: nothing in `SKILL.md` or `deck.py` would need to change for the interview, the tally, the checks or the page to use it. (The unit test `commander_template` checks the tally side of this; the reviewer checks the rest.)

FAIL names the line in either file that would need changing.

## AC23: no name in the plugin uses a game trademark term

**Read:** `.claude-plugin/marketplace.json`, `plugins/deckwright/.claude-plugin/plugin.json`, every folder and file name under `plugins/deckwright/` and `.claude-plugin/`, and every Markdown heading (`#` lines) and HTML heading (`<h1>`–`<h6>`, `<title>`) in the plugin's files.

**Rubric:** no "Magic", "MTG", "Gathering", "EDH" or Wizards marks (for example "Wizards of the Coast", "WotC" as a name, "Planeswalker" as a brand) in:

1. the marketplace's name and the plugin's `name`, `description` and `keywords` fields;
2. any folder or file name;
3. any heading, including the page skeleton's `<title>` and the headings the script renders;
4. the skill's `name` and `description` frontmatter.

Body text may say what the plugin is for in plain words, and `brackets.toml` names WotC's document as its source: that is a citation, not a name, and passes. Match case-insensitively and as a whole word ("magical" is not "Magic"; "edh" inside another word is not "EDH").

FAIL quotes the name or heading and its file.

## AC24: every criterion with an eval check has its case in `evals/`

**Read:** `evals/*/prompt.md`, `evals/*/graders/*.md`, `evals/README.md`, and the spec's tables.

**Rubric:**

1. For each eval named in the spec (`starts-with-commander`, `walks-template-in-order`, `suggests-per-category`, `suggestion-is-not-choice`, `critiques-named-card`, `wrong-category-called-out`, `looks-up-before-describing`, `player-bends-the-template`, `tally-after-category`, `ends-with-deck-page`, `bracket-push-flagged`, `unknown-card`, `lookup-unavailable`, `no-code-execution`, `colour-identity-flagged`, `singleton-duplicate`, `illegal-commander`, `ends-early`, `page-without-artifacts`, `collection-not-yet`, and `no-prices` in every case), a grader file of that name exists under `evals/<case>/graders/`.
2. Each grader checks its own criterion: read its rubric or pattern against the criterion's wording, not just its name. A grader that would pass a run violating its criterion is a FAIL.
3. The case's `prompt.md` contains the trap the grader needs: the player's script sets up the situation the criterion is about (for example, `card-traps` names Llanowar Elves as commander for `illegal-commander`).
4. Every case carries a `no-prices` grader.
5. `evals/README.md`'s Cases table lists every case, what it checks with the spec ids, and its Now.

FAIL names the eval and what is missing.

## AC25: the README says how to install, in plain steps

**Read:** `README.md` at the repo root.

**Rubric:** it has all three, each in numbered or otherwise plain steps a player can follow without knowing Claude Code:

1. How to add the deckwright marketplace and the deckwright plugin in the Claude app's settings, and that this one install makes the plugin available on every surface the account uses (web, desktop, mobile).
2. How to add them in the Claude Code CLI: the exact commands (`/plugin marketplace add …`, `/plugin install deckwright@…`, or their `claude plugin` equivalents), with the repository's real address.
3. That code execution is required, and where to turn it on.

A step that says what to do without saying where (for example "enable code execution" with no hint of the setting) is a FAIL. No price, no game trademark term in a heading (AC23).

## AC26: the skill runs an interview in claude.ai mobile chat, script included

**Who:** Mattias, by hand, on his phone. The evidence stage asks him.

**Rubric:** in the claude.ai mobile app, with the plugin installed through the app's settings and code execution on, in a new chat:

1. Typing "help me build a commander deck" triggers the deckwright interview skill.
2. The script runs: a lookup of the commander he names returns its colour identity and commander legality, stated in the chat.
3. Before that, deckwright asks for the commander, before any category.

Record: the date, the app version, whether each of the three held, and a screenshot of the first exchange. A FAIL on any of them fails the criterion.
