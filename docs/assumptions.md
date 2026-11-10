# Assumptions

What the design stands on, and how we would know each stopped holding. From the
milestone 1 design interview, 2026-11-10.

| Id | Assumption | Area | How we would know it stopped holding |
|----|------------|------|--------------------------------------|
| A1 | About a hundred saves in a row work, and a new conversation opens the deck exactly as it was | Saving | Outcome check 4 fails |
| A2 | A Scryfall search alone tells whether a card is legal in the format and on Arena | Search | Outcome check 8 fails: a card from a shortlist does not import into Arena |
| A3 | Opus 5.5 knows Magic well enough that bare runs behave like the earlier bare Opus 5 runs | Model | Bare runs fail checks the earlier analysis saw passing |
| A4 | A stand-in player can stand in for Mattias | Evals | His first real build fails a check the stand-in runs passed |
| A5 | 35 lands is enough for Brawl | Lands | He is short of mana in play |

## Measured facts

- Arena accepts the copy block: Mattias pasted the Vren list (2026-11-10).
- Artifact pages cannot load outside images; files published beside `index.html` load (spike, 2026-11-10).
- Card images attached as files render in a project thread's chat; markdown image links do not.
