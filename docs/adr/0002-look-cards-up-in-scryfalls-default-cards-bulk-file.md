# ADR-0002 — Look every card up in Scryfall's Default Cards bulk file

**Status:** Accepted (2026-11-08)

## Context

S1 looked each card up with Scryfall's `cards/named`: exact, then fuzzy, one name per
request, 2 requests a second. S2 hands deckwright a whole collection. The owner's has
661 distinct cards in 1,438 copies, and a ManaBox CSV row names a printing by its
Scryfall ID. Scryfall's documentation asks clients that look up many cards to use its
bulk data files, and to cache what they download (scryfall.com/docs/api/rate-limits,
read 2026-11-08). The bulk files are served from `data.scryfall.io`, which has no rate
limit. In 2026-11-08 listings, Oracle Cards was 25.4 MB gzipped (one entry per card,
no printing IDs), Default Cards 81.0 MB (every printing in English, or in its only
language) and All Cards 404 MB. Each `/bulk-data` entry gives a `jsonl_download_uri`:
gzipped JSONL, one card per line. claude.ai chat on the owner's account reached
`data.scryfall.io` and streamed Oracle Cards (2026-11-08). In this collection, eight
token lots share a card's name: Starscape Cleric is six copies of the card and two of a
token.

## Decision

Every lookup, single cards and collections alike, reads Scryfall's Default Cards bulk
file. The script downloads it once and keeps it in its cache folder. It reuses the file
while it is under a week old, and downloads it again after that. A collection row is
matched by its printing's Scryfall ID, so a token printing is a token whatever its
name. A card looked up once is kept in the per-card cache S1 already had, and answered from there first. A name is matched the way `cards/named` matched it: case, accents and punctuation
ignored. A near miss names the closest card and records nothing. `cards/named` is no
longer called.

Rejected:

- `cards/named` per card: about 330 seconds of requests for this collection, and the
  load Scryfall asks big lookups not to make.
- `/cards/collection` (75 identifiers per request, 2 a second): about 9 requests for
  this collection, but Scryfall points large lookups at bulk data instead.
- Oracle Cards bulk, matching rows by name: a third of the download, but it carries no
  printing IDs. Telling a token from its card would rest on how ManaBox names token
  sets.
- Bulk for collections and `cards/named` for single lookups: two sources of card facts,
  and two code paths, where one serves both.

## Consequences

Card facts no longer depend on per-request rate limits. A lookup after the first
download costs no network at all, and in a folder that outlives the conversation the
download happens once a week. "Did you mean" is now computed by the script, and S1's
found, closest-match and not-found results have to hold with it. The first lookup in a
conversation waits for an 81 MB download. Where `data.scryfall.io` is out of reach,
there are no lookups at all: a single card falls back to the player's text (ADR-0001),
and a collection cannot be read. A card already in the per-card cache needs neither the
bulk file nor the network, so S1's recorded eval fixtures keep working; an eval that
looks up a card they do not hold needs `data.scryfall.io`.
