# Evals

Outcome checks for Deckwright, run with and without the skill (ADR-0002). A run is
one whole conversation between Deckwright and a stand-in player playing a brief.

```sh
python3 evals/run.py evals/briefs/*.md --arm bare --runs 3 -j 3   # or --arm skill
python3 evals/checks.py evals/runs/<stamp>/*
python3 evals/run.py evals/briefs/*.md --arm bare --runs 3 -j 3 --resume <stamp>
```

A background command in a cloud session is cut off after two hours. Resume the
round with the same briefs, `--arm` and `--runs`: finished runs are skipped, and a
run cut off mid-way (no `run.json`) or stopped by the publish budget is cleared and
played again from its start. Never resume a round that is still running, because
its unfinished runs' folders are cleared.

- **Deckwright** is headless Claude Code on Opus 5.5 in a workspace of its own. It
  may publish real, private pages; sending files into the person's chat is blocked.
  The bare arm gets only the brief's opening line; the skill arm loads the plugin.
- **The stand-in** is Sonnet 5.5 with no tools. It sees only Deckwright's replies.
- **Each run has its own empty memory.** Runs that shared the project's memory
  wrote stand-in decks into it as the owner's and read them back (2026-11-10).
- **Some briefs start half-built** (`## Start`): the runner copies a deck from
  `starts/` into the workspace, so the run skips the interview and the first card
  rounds, which cost most of a run and are exercised by the briefs that start from
  nothing. `starts/build.py` regenerates those decks from Scryfall. Their cards
  count as confirmed, and C9 is n/a there. The bare round ran before starts existed,
  so it began every brief from nothing.
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
| C9 | One question at a time, what is left said after each answer, no card search before the criteria, no question about strength or price | AC1, AC2, AC3 |
| C10 | Creature type first, broader only on the player's word, narrowing said, nonbasics offered, tagless gaps warned | AC14, AC15, AC16, AC24 |
| C11 | No step unasked; every departure from the template said, reasoned and confirmed | AC11, AC26, the intent's "never assume what the player wants next" |
| C12 | A published page with `deck.json`, `LEDGER.md` and card images; the template's land count and number of categories; no creature-type category | AC8, AC9, AC10, AC23, AC27, AC30 |

Free-text outcomes (which cards the player confirmed, what a review counted) are
extracted once per run by a reader model into `reader.json`, and code decides C1 to
C8 and C12. C9 to C11 are the reader's yes or no on a stated fact, with quoted
evidence. Read a failing run's conversation before believing a check.

`python3 evals/test_checks.py` tests the checks and the runner offline. The blind
judge (`python3 evals/judge.py --bare <stamps> --skill <stamps>`) pairs runs of
the same brief and asks fixed teaching questions in both orders; the skill wins a
question only when picked both times (AC17, AC41, AC45).

A brief may end early (`## Ends`, such as `template`): C8 and C12's land count are
then n/a. A run that dies still writes `run.json`; the checks list one without it
as DIED. A started run copies its start into `start/`, which the checks read.

## Known limits

- C5 compares a review's counts with the final list, so a review made before a
  later swap can fail on a count that was right when it was written.
- C6's tolerance of two basics is an inference; the design set none.
- No brief takes Scryfall down, so "an unchecked card blocks approval" (C7) is not
  exercised yet, and the skill says nothing about it (ADR-0002).
- C7 on "fill in the rest" is C1: it cannot see whether the player took cards one
  word per category (AC42).
- AC18 (offered cards shown as pictures in chat) is not run: runs may not send files
  into chat.
- The judge is blind by label only: the skill arm's saved page files show which
  arm is which, so "page explains" cannot be blind. It reads the last 150,000
  characters of a long conversation, which can drop the intent interview.
- Runs share the account's artifact gallery; `checks.py` flags a run that reads a
  page it did not publish. The account may publish 200 pages a day, reset at
  midnight UTC. A round stops starting exchanges and runs once its accepted
  publishes reach `--publish-budget` (default 150, leaving the owner 50). A run
  stopped this way ends as `publish budget` in `run.json`, and `--resume` plays it
  again from its start; one never started has no folder, so `--resume` plays it.
  The budget is per start of `run.py`, so rounds run side by side or one after
  another on the same day must split the day's allowance between them by hand.
  Turns in flight when the budget is reached may publish a few more.
- `run.json` costs before 2026-11-11 summed running totals; they were recalculated
  from the traces.
- Runs `checks.py` flags as CONTAMINATED reached outside their own folder.
- Every brief builds one deck, so the checks read one page a run: a run that
  publishes two decks has their files merged. Fix it when a brief builds two.
- The Arena check searches `!"name"`, which breaks on a name holding a quote
  mark. Only joke-set cards, none of them on Arena, have one.
