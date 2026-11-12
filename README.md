# deckwright

A deckbuilding tutor for Claude. AI-assisted, not AI-generated: you choose every card.

Deckwright walks you through building a Magic: The Gathering deck for MTG Arena,
Brawl (100 cards with a commander) or Standard (60 cards). It looks every card up on
Scryfall, offers a short list per category with reasons, and keeps the deck as a
private page you can reopen from its link.

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

The first version is in this repository's history, up to commit `03a235f`.
