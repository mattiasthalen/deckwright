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

1. For each eval named in the spec (`starts-with-commander`, `walks-template-in-order`, `suggests-per-category`, `suggestion-is-not-choice`, `critiques-named-card`, `wrong-category-called-out`, `looks-up-before-describing`, `player-bends-the-template`, `tally-after-category`, `ends-with-deck-page`, `bracket-push-flagged`, `unknown-card`, `lookup-unavailable`, `no-code-execution`, `colour-identity-flagged`, `singleton-duplicate`, `illegal-commander`, `ends-early`, `page-without-artifacts`, `asks-for-collection` (which replaced `collection-not-yet` when C33 was amended on 2026-11-08), and `no-prices` in every case), a grader file of that name exists under `evals/<case>/graders/`.
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

## C36: the skill's collection steps replace the S1 collection paragraph, and nothing else of S1 goes

**Read:** `git diff 017a7a0 -- plugins/deckwright/skills/interview/SKILL.md`, beside `brief/s2-s3-brief.md` (B-5 to B-26), the spec's C36 and the lexicon (`docs/lexicon.md`).

**Who says what.** The brief's B-n are behaviours of the whole change, and some are the script's alone. The skill must say the ones the interview carries out; the script's are held by unit tests, and the skill may refer to them but need not say them.

| B-n | Said by | Held by |
|---|---|---|
| B-5, B-6, B-8, B-9, B-10, B-11, B-14 to B-24, B-26 | `SKILL.md`: the interview's steps | this rubric, and the evals the spec names |
| B-7 (rows matched by Scryfall ID, tokens by printing, copies summed) | the script | `collection_token_by_printing`, `collection_csv_quantities` |
| B-12 (an S1 deck file opens as one with no collection and no theme) | the script; S1's line asking whether to carry on with `deck.json` stays | `s1_deck_file_opens` |
| B-13 (which folders outlive the conversation) | neither: a fact of the platform, recorded as assumption A6 | the evidence stage |
| B-25 (the tally and the page show owned and not owned) | the script | `not_owned_marked` |

Where a B-n has a script half and an interview half (B-6 keeps the file as handed over, B-10 titles the page, B-11 refuses a taken name), the skill says the interview half.

**Rubric:** all four hold.

1. Every B-n the table gives to `SKILL.md` is said in the added lines, once: a behaviour said in two steps, in different words or in two places that could drift apart, is a FAIL for that B-n. The command table's line for a command says what the script does, not what the interview does, so a B-n whose command a table line describes and whose step the interview gives is said once, by the step (the table's "Refuses (exit 2) a name whose file exists" and the start step's "ask whether to carry on with that deck or choose another name" are B-11 said once). List each B-n with the added line that says it. A script-only B-n the skill says anyway passes when the line does not contradict the script's contract in `tests/README.md`.
2. The added lines use the lexicon's word for each concept the lexicon defines, and no synonym for it: *template*, *category*, *target*, *bracket target*, *tally*, *interview*, *suggestion*, *critique*, *lookup*, *deck page*, *available*, *theme*, *plan*. So "available", not "free" or "usable" (the player's own words, quoted as theirs, such as "only use the free cards", are not the skill's); "deck page", not "deck sheet"; *plan* only for the one sentence, never for the template's category of that name. Words the lexicon does not hold (collection, binder, the read, not owned, deck name) are plain words: item 2 does not judge them.
3. The removed S1 lines are only: the paragraph saying building from the player's own cards is not supported yet; the lines telling the skill to look cards up through `cards/named`, and the parts of lines that held only because each lookup asked Scryfall one card at a time. Any other removed S1 instruction is a FAIL, named with its line. An S1 instruction moved but kept word for word is not removed.
4. Each S1 step that still applies is kept word for word. A line changed only in the deck file's or the deck page's path (`deck.json` to `decks/<file name>.json`, `deck.html` to `decks/<file name>.html`, `--deck` given with the `file` that `new` printed), as named decks require and as C33 allows for the graders, is kept. Any other rewording of an S1 line counts as removed, under item 3.

The steps the unit tests and evals rely on are fixed in [`tests/README.md`](README.md), "What the skill must do"; a B-n the skill says in a way that contradicts that section is a FAIL for that B-n.

FAIL names the B-n or the S1 line, and what is wrong with it.
