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
| A6 | Deckwright writes scenes and handbook chapters the page can draw from `deck.example.json` alone | Page | The page of a real build shows blank cards in a scene, or a chapter with nothing in it |
| A7 | An artifact page may load the font files the Google Fonts stylesheet names on fonts.gstatic.com; loading the stylesheet itself is documented | Page | A published deck page shows its headings in the fallback serif |
| A8 | Scryfall offers an artwork crop for every card that can be a hero, on its first face for a two-faced card | Page | A hero card's lookup has no `art_crop`, on the card or on its first face |
| A9 | Scryfall's `all_parts` names each token a scene shows, and no two tokens of one deck share a name | Page | A token in a scene shows as a named blank card |
| A10 | Scryfall keeps serving the Magic card back at `https://backs.scryfall.io/normal/0/a/0aeebaf5-8c7d-4636-9e82-8c27447861f7.jpg`, and Deckwright can reach `backs.scryfall.io`, a different host from `cards.scryfall.io`, from where it saves pictures | Page | Fetching it does not answer 200 with a JPEG, or a page shows drawn cards as blank cards |
| A11 | GitHub's `ubuntu-latest` runner can install Chromium for Playwright 1.63.0 with `npx playwright install --with-deps chromium` | CI | The "browser tests" job fails at that install step on a push that changed nothing |

## Measured facts

- Arena accepts the copy block: Mattias pasted the Vren list (2026-11-10).
- Artifact pages cannot load outside images; files published beside `index.html` load (spike, 2026-11-10).
- Card images attached as files render in a project thread's chat; markdown image links do not.
- An account can publish 200 artifact versions a day; three parallel Brawl runs hit it (2026-11-11), and the refused saves were retried.
- `claude -p --resume` reports the session's running total as `total_cost_usd`.
- Unverified: whether Arena imports a two-faced card written in full (`A // B`), as the page's copy block writes it. Probe: paste one modal, one transform, one adventure and one split card each way.
- Scryfall's `art_crop` is 626 × 457 for modern frames, the widest artwork it offers; the art area of the `normal` picture is about 400 wide (measured on four cards, 2026-11-11).
- A page opened from a `file://` address cannot fetch `deck.json`; the page test serves the folder over HTTP.
- Unverified: whether a published artifact page loads the font files (A7), opens the card dialog's Scryfall link in a new tab, and may write to the clipboard (refused, the page tells the reader to copy the Arena list by hand and scrolls to it). Probe on a published page: after `document.fonts.ready`, count the loaded faces whose family includes "IM Fell" (`document.fonts.check()` answers true with no stylesheet at all), click the link, and press Copy for Arena.
- `https://scryfall.com/card/<scryfall id>` answers 301 to the card's page, a URL form Scryfall does not document; the card dialog's Scryfall link relies on it (2026-11-11).
- Scryfall serves the Magic card back at `https://backs.scryfall.io/normal/0/a/0aeebaf5-8c7d-4636-9e82-8c27447861f7.jpg`: it answered 200 with a JPEG of about 80 KB, twice, fetched from a Claude cloud session container on 2026-11-11. Its API documents `card_back_id` only as "the Scryfall ID for the card back design present on this card" (`0aeebaf5-…` on Sol Ring); the image URL of a card back is undocumented, and `cards/back.jpg` relies on it (A10).
- Behind a proxy set in the environment, urllib connects to the proxy, so a socket-level block sees the proxy's address and not the destination; the offline tests drop the `*_proxy` variables for that reason (2026-11-12).
