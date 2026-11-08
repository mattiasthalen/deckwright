# ADR-0003 — Read every available card in the commander's colours once per deck

**Status:** Accepted (2026-11-08)

## Context

ADR-0001 puts the judgement of which category a card serves in the skill. S2 asks for
each owned card to be classified into the template's categories, and S3 asks which
cards serve the deck's theme. A card can serve several categories, and only its text
says which. Measured on the owner's collection (661 distinct cards, 631 of them
nonlands), the name, type line and text of every nonland within a colour identity come
to about 7k tokens for mono-green (145 cards), 12k for two colours (252), 18k for three
(354) and 32k for all five (631). Scryfall's Tagger publishes `oracle_tags` (6.1 MB):
community tags such as `ramp` (2,493 cards), `card-advantage` (6,676) and `sweeper`
(994). Those tags do not follow the Commander template's own tests. Its card advantage,
for instance, is narrower.

## Decision

Once the commander and the deck's plan are settled, the script narrows the collection
to the cards available to this deck: within the commander's colour identity, legal in
the format, with available copies. Claude then reads every one of them, in batches, and
records for each card which categories it counts in (none, one or several) and whether
it serves the theme. The judgements are stored in that deck's file. Categories counted
from the type line, such as Lands, are left to the script. Searching the collection by
text or type is a way to find cards during a category, not a way to classify them.

Rejected:

- Searching by text per category, then judging only what the search returns: a card
  whose wording the search did not anticipate is missed, and nobody learns of it.
- Fixed text patterns per category in the script: deterministic, but it moves the
  judgement ADR-0001 gives the skill into code.
- Scryfall's `oracle_tags`: someone else's judgement, against tests that are not the
  template's. Making categorization deterministic and global is filed as later work.
- One classification per card shared by every deck: the plan category and theme fit
  belong to one deck, and the read is cheap enough to repeat.

## Consequences

Every card that could go in the deck has been read before anything is suggested from
it, so a card serving several categories is known to. Each deck costs a read of
roughly 7k to 32k tokens on a collection this size, more for a larger collection, and a
read that outgrows a conversation is where this decision stops holding. A change of
theme redoes only the theme judgements.
