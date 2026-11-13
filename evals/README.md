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
  wrote stand-in decks into it as the owner's and read them back (2026-11-10). The
  reader and the judge are started the same way, with an empty memory of their own.
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
| C4 | Every pick is written to `deck.json` in the exchange it is made | AC28, AC29, AC32 |
| C5 | The review's type counts match Scryfall's type lines | AC34 |
| C6 | The basic split is within two of each colour's share of mana symbols | AC25 |
| C7 | The brief's pressure holds (illegal card out, no blind fill, change recorded, dismissal kept) | AC19, AC37, AC42, AC43 |
| C8 | The final list is the right size, with a commander for Brawl, and every card is on Arena | AC40 |
| C9 | One question at a time, what is left said after each answer, no card search before the criteria, no question about strength or price | AC1, AC2, AC3 |
| C10 | Narrowing said, nonbasics offered, tagless gaps warned; the ladder is S3's | AC14, AC15, AC16, AC24 |
| C11 | No step unasked; every departure from the template said, reasoned and confirmed | AC11, AC26, the intent's "never assume what the player wants next" |
| C12 | A deck folder with `index.html`, `deck.json`, `LEDGER.md` and card images; the template's land count and number of categories; no creature-type category | AC8, AC9, AC10, AC23, AC27, AC30 |

Free-text outcomes (which cards the player confirmed, what a review counted) are
extracted once per run by a reader model into `reader.json`, and code decides C1 to
C8 and C12. C9 to C11 are the reader's yes or no on a stated fact, with quoted
evidence. Read a failing run's conversation before believing a check.

`python3 evals/test_checks.py` tests the checks and the runner offline, and CI runs
it on every push and pull request. The blind
judge (`python3 evals/judge.py --bare <stamps> --skill <stamps>`) pairs runs of
the same brief and asks fixed teaching questions in both orders; the skill wins a
question only when picked both times (AC17, AC41, AC45).

S1 to S13 are the skill's close-out criteria (ADR-0011 to ADR-0013 and the first real
build's tickets), one check each, read off the deck folders and the trace, with the
reader's facts where only the conversation says.

**What a run saved is read from the runner's record, never from the commands.** After
each exchange the runner copies every `deck.json` and `LEDGER.md` in the workspace,
at its path, into `after/<exchange>/` (exchanges counted from 0, as in the trace),
and a start as copied in into `after/start/`. The checks read these as `Run.states`:

- a **save** is an exchange that changed a `deck.json` or made a new deck folder,
  not a publish (C4); S2 needs every save, as every exchange that offers cards, to
  run `pack.py` and name the packed file in its reply, a link beside it or not. The
  packed file is `<deck folder name>.html` as `pack.py` prints it: the printed page
  of the folder argument's name, else the last printed page that is not `index.html`;
- a **pick** is saved when its card is in `deck.json` after its exchange and was not
  before (or its count rose), and the ledger gained a line naming it (S1);
- a **round** is each distinct `offer` the states hold; S2 needs one after every
  exchange that offers cards, or review swaps the maybeboard gained in it (entries
  of `kind: "swap"`); S3 and S4 judge the rounds of the deck's categories other
  than Commander (S3 only when a creature type was wanted, and holds a round as
  first shown to 6 to 14 cards: an offer whose cards were all in the previous offer
  of its category is that round shrinking, and the Lands round is exempt; S4 needs
  a card marked `suggested` and a `reason` on every card, and the reader judges
  only that the reply marks them), and S5 judges every offered card;
- a **review** is judged against the deck as it stood after the review's exchange
  (C5), and against the final list in a run with no record;
- the **name** must be absent from every state before the first complete one, and be
  said by the player after it (S10);
- a **rename** is a deck folder gone while a new one's ledger starts with its lines,
  and needs a `name` line (S12), which records it as `old → new`: the folder after
  the last line's `→` must be the deck's, numbered or not. The deck's name comes only
  from `deck.json`, so while it is null the folder is judged by the theme. A run
  from a start is judged for its folder only once its ledger gains a `name` line
  that `after/start` lacks; until then the folder is the runner's, and S12 is n/a.

S7 is the reader's alone: a set limit is saved as a criterion of kind `limit`, like
any other, so no saved field says a set was named.

Publishes, `pack.py` runs and the python3 commands behind a stated count (S8) are
read from the trace. A run recorded before the record began has no `after/`: what only the
record shows is n/a there, saying "this run has no record of the deck folder after
each exchange", and what the trace or the replies show is still judged. The deck
is the last state's most recently changed one.

A brief may end early (`## Ends`, such as `template`): C8 and C12's land count are
then n/a, and so is C1 when no card was picked. A run that dies still writes
`run.json`; the checks list one without it as DIED. A started run copies its start
into `start/`, which the checks read.

## Known limits

- In a run with no record, C5 compares a review's counts with the final list, so a
  review made before a later swap can fail on a count that was right when it was
  written.
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
  midnight UTC. A round stops starting exchanges and runs once the day's accepted
  publishes reach `--publish-budget` (default 150, leaving the owner 50). A run
  stopped this way ends as `publish budget` in `run.json`, and `--resume` plays it
  again from its start; one never started has no folder, so `--resume` plays it.
  The budget is for the UTC day and shared by every start of `run.py` on this
  machine, counted in `evals/runs/publishes/`. Runs started from another machine or
  session do not see it, and neither does publishing done outside the evals. Turns
  in flight when the budget is reached may publish a few more.
- `run.json` costs before 2026-11-11 summed running totals; they were recalculated
  from the traces.
- Runs `checks.py` flags as CONTAMINATED reached outside their own folder.
- Every brief builds one deck, so the checks read one deck folder a run, the
  last state's most recently changed one; a run that builds two decks is checked
  on that one.
- The record is taken once an exchange ends: an offer written and removed within
  one exchange, or a save undone in it, is not seen. It holds only `deck.json` and
  `LEDGER.md`; C12's page and pictures are read from the workspace as the run left it.
- S8 reads the trace: a count must be printed, as a whole number, by a python3
  command in its exchange, whether or not the command names `deck.json` (a script
  may import a helper that holds the path), so it cannot tell a count of the deck
  from another number the command printed. Tracebacks and the `Exit code` line hold
  no count. A count said without digits is not judged, and a stated 0 passes when
  any python3 command printed in that exchange, since a count by category leaves out
  the category that has none.
- When several rounds are shown in one exchange, only the last `offer` is on
  record, so S3, S4 and S5 see only that round.
- S2 cannot see a file sent into the chat, since runs may not send one; it checks
  that the reply names the packed file `pack.py` printed.
- The Arena check searches `!"name"`, which breaks on a name holding a quote
  mark. Only joke-set cards, none of them on Arena, have one.
