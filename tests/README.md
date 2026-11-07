# Tests

Unit tests for `plugins/deckwright/skills/interview/deck.py`, the script that does every computable part of the interview. Each test named in the plan's checks is selected by its name:

```sh
uv run pytest                      # all of them
uv run pytest -k lookup_fields     # one check, with any companion tests named after it
```

Until the repo has its dev `pyproject.toml`, `uv run --no-project --with pytest pytest` does the same.

## How the tests drive the script

**By subprocess**, never by import: each test runs `python deck.py <command> …` with the interpreter running pytest, in a fresh working folder under pytest's `tmp_path`, and reads only its exit code, its stdout, and the files it writes. That is the same command line the skill uses through `uv run`; the tests skip `uv run` only to save its start-up time per call.

**Scryfall is a local stand-in** (`conftest.py`), serving the recorded responses in `fixtures/scryfall/` and nothing else. It adds `prices`, `purchase_uris` and `image_uris` back onto every card it serves, as the real API does, so the price tests prove the script drops them. A request it has no recording for gets a 500. Out of reach is a closed local port; a blocking proxy is the stand-in answering 403 with an HTML body.

`DECKWRIGHT_SKILL_DIR` points the suite at another copy of the skill folder, such as a candidate build outside the repo. By default it is the skill in this repo.

## Recorded responses

`fixtures/scryfall/named-<mode>-<query>.json` is one real `cards/named` request, fetched on 2026-11-07 with `User-Agent: deckwright-tests/0.1` and `Accept: application/json`: `{"mode", "q", "status", "body"}`. Every key matching `price`, `purchase`, `image`, `tcgplayer` or `cardmarket` was removed from the body, at every depth; `test_no_prices_in_fixtures` keeps it that way. Card facts in the tests come from these files.

| Card | Why it is here |
|---|---|
| Sol Ring | colourless ramp; not a Game Changer |
| Vampiric Tutor | a Game Changer, black |
| Bloodline Keeper // Lord of Lineage | a double-faced (transform) card |
| Forest, Swamp | basic lands |
| Meren of Clan Nel Toth | the commander throughout: a legendary creature, black-green |
| Llanowar Elves | a creature that is not legendary, so cannot be a commander |
| Lightning Bolt | red: outside Meren's colour identity |
| Black Lotus | banned in Commander |
| Relentless Rats | its text allows any number of copies |
| Command Tower | a nonbasic land |
| Ravenous Chupacabra | a card the tests record in two categories |
| Demonic Tutor, Ancient Tomb, Mana Vault, Grim Monolith | Game Changers, for three and four |
| Sign in Blood, Pernicious Deed | card advantage and mass disruption for the evals |
| `Vampiric Tutr` (exact 404, fuzzy → Vampiric Tutor) | a misspelling with a closest match |
| `Xyzzy Plover Quux` (exact 404, fuzzy 404) | a card that does not exist |

## The contract the build must meet

The plan's checks leave these details open; the tests and the eval scaffolds fix them as below. Anything not listed is the builder's.

### Running and locating files

- `deck.py` finds `templates/<name>.toml`, `brackets.toml` and `page.html` beside itself, so a copy of the skill folder works on its own (`commander_template` copies it).
- Every deck command reads and writes `./deck.json` in the working folder unless `--deck PATH` is given after the command.
- The Scryfall base URL is `https://api.scryfall.com`, overridden by the environment variable `DECKWRIGHT_SCRYFALL_API` (the tests set it to `http://127.0.0.1:<port>`). Requests go to `<base>/cards/named?exact=<name>`, and only on a 404 to `<base>/cards/named?fuzzy=<name>`.

### Exit codes

| Code | When |
|---|---|
| 0 | the command did its work. A `lookup` that Scryfall answered is 0 even when a name was not found or only fuzzy-matched: the entry says which. |
| 2 | usage error (argparse's default) |
| 3 | Scryfall could not be reached for a card not in the cache: connection refused, timeout, or any answer that is neither a 200 card nor a 404 from Scryfall (a proxy's 403, a 5xx). A plain message on stdout or stderr names the card. Nothing is written to the deck, and nothing is cached. |
| 4 | `add` (or `new --commander`) was given a name that is not found, or that only fuzzy-matches another card. Nothing is written to the deck: a misspelling is recorded only once the player confirms the real name and it is added by that name. |

### The cache

- The folder is `$DECKWRIGHT_CACHE` if set, else `deckwright-cache/` beside the deck file (so `./deckwright-cache/` by default).
- One file per looked-up query: `<key>.json`, where `<key>` is the query lowercased, every run of characters outside `a-z0-9` replaced by one `-`, and leading and trailing `-` removed. `Meren of Clan Nel Toth` → `meren-of-clan-nel-toth.json`; `Vampiric Tutr` → `vampiric-tutr.json`.
- The file holds one Scryfall card object, as `cards/named` returns it, with every price, purchase and image key removed. A misspelling's file holds the card its fuzzy match returned. The eval scaffolds pre-fill the cache in exactly this form.
- The cache is read before the network: a cached query makes no request.

### `lookup NAME…`

Stdout is a JSON array with one entry per `NAME`, in argument order:

```json
[{"query": "Vampiric Tutr", "result": "closest_match", "card": {…}}]
```

- `result` is `found` when the query equals, ignoring case, the card's `name` or one of its faces' names; `closest_match` when Scryfall's answer is another card (the fuzzy match); `not_found` when there is none, and then `card` is absent.
- `card` has exactly these keys, the *fixed fields*:

| Key | From Scryfall |
|---|---|
| `name` | `name` (a double-faced card's full `A // B` name) |
| `mana_cost` | `mana_cost`; for a card with faces, every face's mana cost, front first, in one string |
| `type_line` | `type_line` |
| `oracle_text` | `oracle_text`; for a card with faces, every face's oracle text, front first, in one string |
| `color_identity` | `color_identity`, a list of the letters `W U B R G` |
| `commander_legality` | `legalities.commander`, as Scryfall spells it (`legal`, `not_legal`, `banned`, `restricted`) |
| `game_changer` | `game_changer`, a boolean |

### `new`, `add`, `remove`, `target`, `bracket`

- `new --template commander --commander NAME` writes a new `deck.json`.
- `add NAME [--count N] [--category C …]`: `--count` defaults to 1; adding a name already in the deck adds to its copies (so a card named twice is held twice, for the checks to report). `--category` takes one or more category names exactly as the template spells them and may be left out. Lands come from the type line whatever is recorded.
- `add NAME --from-player "TEXT" [--count N] [--category C …]` records a card from the player's text with no lookup and no network, marked as such.
- `target CATEGORY N`, `bracket N` change the deck's target for one category and its bracket target.

### `deck.json`

The tests read only this of it: it is JSON; it changes on a recorded change and not on a lookup or a refused `add`; and no key in it matches `price`, `purchase`, `image`, `tcgplayer` or `cardmarket`, at any depth. Its layout is otherwise the builder's.

### `tally`

Stdout is one JSON object with at least:

```json
{
  "deck_size": 100,
  "total": 39,
  "categories": [{"name": "Lands", "target": 38, "count": 36, "cards": ["Command Tower", "Forest", "Swamp"]}, …],
  "checks": {"singleton": [], "color_identity": [], "commander_legality": []},
  "bracket": {"target": 2, "lowest": 2, "game_changers": []}
}
```

- `categories` is in template order. `count` counts copies (18 Swamp count 18); `cards` lists each card's name once, sorted.
- `total` counts the commander and every copy of every card, a card in two categories once.
- `checks` lists, sorted, the names of the cards failing each check: more than one copy (except basic lands and cards whose text allows any number), colour identity outside the commander's, `commander_legality` other than `legal`.
- `bracket.lowest` is 2 with no Game Changers, 3 with one to three, 4 with four or more; `game_changers` is sorted.
- The same deck file gives the same stdout, byte for byte, and `tally` never touches the network.

### `templates/commander.toml` and `brackets.toml`

```toml
# commander.toml
deck_size = 100
bracket_target = 2

[[categories]]
name = "Lands"
target = 38
counts_when = "the card's type line includes Land"
# … five more, in interview order
```

Other keys may be added, such as how the template marks the category counted from the type line. A file `templates/<name>.toml` of the same shape is a new format: `new --template <name>` takes it with no other change.

`brackets.toml` has a top-level `source` (a string naming WotC's document) and `date` (a TOML date or a `YYYY-MM-DD` string). How it states the mapping is the builder's.

### `page --out FILE`

The page is HTML. The tests and the eval graders find its parts by these attributes; the styling around them is free.

| Element marked | Holds, as text |
|---|---|
| `data-section="commander"` | the commander's name |
| `data-category="<name>"`, one per category | `count / target` (spaces optional, as in `36 / 38`) and the name of every card counting in it |
| `data-section="total"` | `total / deck size`, and the word "over" when the total is over the deck size |
| `data-section="checks"` | the name of every flagged card |
| `data-section="bracket"` | the word "target" before the bracket target, the word "lowest" before the lowest bracket the deck fits (each within 40 characters), and every Game Changer |
| `data-section="player-text"` | the name of every card recorded from the player's text, and no other card |
| `data-section="decklist"` | the decklist, as plain text: no element inside it, so it appears in the source as one escaped run |

- The decklist is `// COMMANDER`, `1 <commander>`, a blank line, `// MAINBOARD`, then `count Name` rows sorted by name ignoring case, one row per name with its copies summed (basics included), no set codes, no other lines.
- The page has a copy button, at most one `<script>` element, none with `src`, and uses the clipboard.
- The same deck file gives the same bytes, from any folder, at any time: no timestamps and no paths. `page` never touches the network.

### What the skill must do that the eval graders read

- The page is rendered to `deck.html` beside `deck.json`, in the working folder, wherever the interface has no artifacts (Claude Code). The graders read `deck.html` and `deckwright-cache/` by those paths.
