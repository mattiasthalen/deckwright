# Evals

Outcome checks for Deckwright, run with and without the skill (ADR-0002). A run is
one whole conversation between Deckwright and a stand-in player playing a brief.

```sh
python3 evals/run.py evals/briefs/*.md --arm bare --runs 3 -j 3   # or --arm skill
python3 evals/checks.py evals/runs/<stamp>/*
```

- **Deckwright** is headless Claude Code on Opus 5.5 in a workspace of its own. It
  may publish real, private pages; sending files into the person's chat is blocked.
  The bare arm gets only the brief's opening line; the skill arm loads the plugin.
- **The stand-in** is Sonnet 5.5 with no tools. It sees only Deckwright's replies.
- **Each run has its own empty memory.** Runs that shared the project's memory
  wrote stand-in decks into it as the owner's and read them back (2026-11-10).
- **Scryfall** is shared by every run and the checks: keep `-j` at 3 or below.

## Checks

C1 to C8 are the design's counted checks. C1, C2 and C7 must pass in every run;
the rest are counts. C9 to C12 were added after the first bare round, one per
group of acceptance criteria the bare runs failed; a criterion the bare runs met
got no check.

| Check | Holds when | Criteria |
|---|---|---|
| C1 | Every card in the final list was confirmed by the player | AC12, AC20, AC38, AC42 |
| C2 | Every card shown is real, legal, on Arena, in colour, not already picked | AC5, AC6, AC19, AC21 |
| C3 | Every card shown was looked up on Scryfall earlier in that conversation | AC13, AC22 |
| C4 | Every pick is saved to the page in the exchange it is made | AC28, AC29, AC32 |
| C5 | The review's type counts match Scryfall's type lines | AC34 |
| C6 | The basic split is within two of each colour's share of mana symbols | AC25 |
| C7 | The brief's pressure holds (illegal card out, no blind fill, change recorded, dismissal kept) | AC19, AC37, AC42, AC43 |
| C8 | The final list is the right size, with a commander for Brawl, and every card is on Arena | AC40 |
| C9 | One question at a time, what is left said after each answer, no card search before the criteria | AC1, AC2, AC3 |
| C10 | Creature type first, broader only on the player's word, narrowing said, nonbasics offered, tagless gaps warned | AC14, AC15, AC16, AC24 |
| C11 | No step unasked; every departure from the template said, reasoned and confirmed | AC11, AC26, the intent's "never assume what the player wants next" |
| C12 | A published page with `deck.json`, `LEDGER.md` and card images; the template's land count and category shape; no creature-type category | AC8, AC9, AC10, AC23, AC27, AC30 |

Free-text outcomes (which cards the player confirmed, what a review counted) are
extracted once per run by a reader model into `reader.json`; code decides. Read a
failing run's conversation before believing a check.

## Known limits

- C5 compares a review's counts with the final list, so a review made before a
  later swap can fail on a count that was right when it was written.
- C6's tolerance of two basics is an inference; the design set none.
- No brief takes Scryfall down, so "an unchecked card blocks approval" (C7) is not
  exercised yet.
- Runs `checks.py` flags as CONTAMINATED reached outside their own folder.
