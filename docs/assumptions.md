# Assumptions

What the design stands on, and how we would know each stopped holding. From the
milestone 1 design interview, 2026-11-10.

| Id | Assumption | Area | How we would know it stopped holding |
|----|------------|------|--------------------------------------|
| A1 | About a hundred saves in a row to the deck folder work, and a new conversation opens the deck exactly as it was from its folder, its packed file or its link | Saving | Outcome check 4 fails |
| A2 | A Scryfall search alone tells whether a card is legal in the format and on Arena | Search | Outcome check 8 fails: a card from a shortlist does not import into Arena |
| A3 | Opus 5.5 knows Magic well enough that bare runs behave like the earlier bare Opus 5 runs | Model | Bare runs fail checks the earlier analysis saw passing |
| A4 | A stand-in player can stand in for Mattias | Evals | His first real build fails a check the stand-in runs passed |
| A5 | 35 lands is enough for Brawl | Lands | He is short of mana in play |
| A6 | Deckwright writes scenes and handbook chapters the page can draw from `deck.example.json` alone | Page | The page of a real build shows blank cards in a scene, or a chapter with nothing in it |
| A7 | An artifact page may load the font files the Google Fonts stylesheet names on fonts.gstatic.com; loading the stylesheet itself is documented | Page | A published deck page shows its headings in the fallback serif |
| A8 | Scryfall offers an artwork crop for every card that can be a hero, on its first face for a two-faced card | Page | A hero card's lookup has no `art_crop`, on the card or on its first face |
| A9 | Scryfall's `all_parts` names each token a scene shows, and no two tokens of one deck share a name | Page | A token in a scene shows as a named blank card |
| A10 | Scryfall keeps serving the Magic card back at `https://backs.scryfall.io/normal/0/a/0aeebaf5-8c7d-4636-9e82-8c27447861f7.jpg`, and Deckwright can reach `backs.scryfall.io`, a different host from `cards.scryfall.io`, from where it saves pictures | Page | Fetching it does not answer 200 with a JPEG, or a page shows drawn cards as blank cards |
| A11 | GitHub's `ubuntu-latest` runner can install Chromium for Playwright 1.63.0 with `npx playwright install --with-deps chromium` | CI | The "browser tests" job fails at that install step on a push that changed nothing |

| A12 | Arena imports a Room card, which Scryfall gives the layout `split`, by its full name `A // B`, as it does other split cards | Arena list | An import fails at a Room card's line |
| A13 | Arena imports a card of Scryfall's layout `prepare` by its front face name alone | Arena list | An import fails at such a card's line |
| A14 | A packed deck page of about 10 MB, attached to a message, opens in a project thread's chat on a phone and on a desktop | Page | The player cannot open the attached page of a full deck |
| A15 | Scryfall marks every crossover card so that one search term finds them, and gives the name printed on a card's Arena printing when it differs from the card's name | Search | A crossover card is offered unmarked, or a printed name is missing or wrong |

## Measured facts

- Arena accepts the copy block: Mattias pasted the Vren list (2026-11-10).
- Artifact pages cannot load outside images; files published beside `index.html` load (spike, 2026-11-10).
- A message holding a markdown image link is refused in a project thread.
- An account can publish 200 artifact versions a day; three parallel Brawl runs hit it (2026-11-11), and the refused saves were retried.
- `claude -p --resume` reports the session's running total as `total_cost_usd`.
- Arena imports a modal double-faced, a transform and an adventure card by its front face name alone, and a split card by both halves, `A // B`; a split card's half alone is a known title but not a deck card, and a modal double-faced card's full name is an unknown title. Arena fails the whole import at the first line it rejects. A crossover card imports by its Scryfall name, not by the name printed on its Arena version. Pasted by Mattias, 2026-11-12 (#22). Not pasted: Room cards (A12) and `prepare` cards (A13).
- Arena's crafting view shows the cards of a Brawl deck as not valid in Standard or Alchemy; the import itself raises no warning (Mattias, 2026-11-11 and 2026-11-12).
- An attached page opens in a project thread's chat; card pictures attached one by one show as small file tiles, and links to Scryfall were reported as unusable (Mattias, 2026-11-11 and 2026-11-12, #29).
- Scryfall's `art_crop` is 626 × 457 for modern frames, the widest artwork it offers; the art area of the `normal` picture is about 400 wide (measured on four cards, 2026-11-11).
- A page opened from a `file://` address cannot fetch `deck.json`; the page test serves the folder over HTTP.
- Unverified: whether a published artifact page loads the font files (A7), opens the card dialog's Scryfall link in a new tab, and may write to the clipboard (refused, the page tells the reader to copy the Arena list by hand and scrolls to it). Probe on a published page: after `document.fonts.ready`, count the loaded faces whose family includes "IM Fell" (`document.fonts.check()` answers true with no stylesheet at all), click the link, and press Copy for Arena.
- `https://scryfall.com/card/<scryfall id>` answers 301 to the card's page, a URL form Scryfall does not document; the card dialog's Scryfall link relies on it (2026-11-11).
- Scryfall serves the Magic card back at `https://backs.scryfall.io/normal/0/a/0aeebaf5-8c7d-4636-9e82-8c27447861f7.jpg`: it answered 200 with a JPEG of about 80 KB, twice, fetched from a Claude cloud session container on 2026-11-11. Its API documents `card_back_id` only as "the Scryfall ID for the card back design present on this card" (`0aeebaf5-…` on Sol Ring); the image URL of a card back is undocumented, and `cards/back.jpg` relies on it (A10).
- Behind a proxy set in the environment, urllib connects to the proxy, so a socket-level block sees the proxy's address and not the destination; the offline tests drop the `*_proxy` variables for that reason (2026-11-12).
