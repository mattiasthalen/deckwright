# deckwright

A deckbuilding tutor for Claude. AI-assisted, not AI-generated: you choose every card.

Deckwright walks you through building a Magic: The Gathering deck for MTG Arena,
Brawl (100 cards with a commander) or Standard (60 cards). It looks every card up on
Scryfall, offers a short list per category with reasons, and keeps the deck as a
folder of plain files, shown to you as one packed file, a page you open from the chat. You get
a link to a private page only when you ask for one.

```
/plugin marketplace add mattiasthalen/deckwright
/plugin install deckwright@deckwright
```

How it is tested: [`evals/README.md`](evals/README.md). Decisions: [`docs/adr/`](docs/adr/).
The deck page is tested in a browser, with Node and Playwright's Chromium. Playwright's
version is fixed in `package.json`; to run the tests at it:

```
npm ci
npx playwright install chromium
node --test tests/*.test.cjs
```

`pack.py`, which packs a deck folder into one page, is tested offline with `python3 tests/test_pack.py`.
The repository's upkeep (the ruleset file, the lint command, the CI jobs) is tested offline with `python3 tests/test_repo.py`.

Lint runs ruff and ESLint at the versions `package.json` fixes; ruff comes through `uvx`, so it needs
[uv](https://docs.astral.sh/uv/):

```
npm run lint
```

The rules that guard `main` are kept in `.github/rulesets/main-needs-tests.json`. To apply a change to them,
go to the repository's Settings, Rules, Rulesets: rename the old ruleset, then New ruleset, Import a ruleset,
with the file, then delete the renamed one. A branch cut before the `lint` job existed needs `main` merged in
to get the `lint` check.

The first version is in this repository's history, up to commit `03a235f`.
