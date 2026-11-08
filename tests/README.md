# Tests

Unit tests for `plugins/deckwright/skills/interview/deck.py`, the script that does every computable part of the interview. Each test named in the plan's checks is selected by its name:

```sh
uv run pytest                      # all of them
uv run pytest -k lookup_fields     # one check, with any companion tests named after it
```

Until the repo has its dev `pyproject.toml`, `uv run --no-project --with pytest pytest` does the same.

## How the tests drive the script

**By subprocess**, never by import: each test runs `python deck.py <command> …` with the interpreter running pytest, in a fresh working folder under pytest's `tmp_path`, and reads only its exit code, its stdout, and the files it writes. That is the same command line the skill uses through `uv run`; the tests skip `uv run` only to save its start-up time per call.

**Scryfall is a local stand-in** (`conftest.py`), two servers: the API, which answers `/bulk-data` with a listing whose `default_cards` entry points at the second server, and `cards/named` from the recordings (what S1's script asked, so the same harness runs the S1 tests at 017a7a0); and the data host, which serves the Default Cards file: gzip-compressed JSON Lines, one card object per line, built from every recorded card and printing in `fixtures/scryfall/` (`bulk_cards()`, narrowed by a test through `scryfall.bulk`). It adds `prices`, `purchase_uris` and `image_uris` back onto every card it serves, as the real hosts do, so the price tests prove the script drops them. A request it has no recording for gets a 500. Out of reach is a closed local port; a blocking proxy is the stand-in answering 403 with an HTML body; Scryfall's rate limit is the stand-in answering 429 (its `limit` flag); `cards_refused` makes every `/cards/…` request a 500; `cut_off` makes the data host send half the file under the whole file's `Content-Length` and hang up; `delay` makes it pause halfway through the file, so commands run side by side (`spawn`) download at once; `huge` makes it send 3 GiB of zeros as fast as they are read, with no `Content-Length`, then hold the connection to 30 s; `claims_over_cap` makes it claim a `Content-Length` of 100 GiB and send a byte every 0.1 s; `redirect` makes a request that reaches a Scryfall host by name answer 302 to that address, while any other host serves the file.

**Scryfall's real hosts, through a proxy** (`test_bulk_hosts.py`): a test that needs the script's own base, `https://api.scryfall.com`, runs with no `DECKWRIGHT_SCRYFALL_API` and with `HTTPS_PROXY` pointing at a local proxy. The proxy answers `CONNECT` for `api.scryfall.com`, `data.scryfall.io` and two hostile hosts by terminating TLS with a certificate made by `openssl` for the test, under a CA the script trusts through `SSL_CERT_FILE`, and hands the request to the stand-in's own handlers; a plain `http://` request through it is answered with a good bulk file, so a script that followed one would be seen. `refuse_connect` makes it answer every `CONNECT` with a 403, as a proxy that blocks Scryfall does, which the script sees as a `URLError`, not an HTTP answer. With the stand-in's `redirect`, `data.scryfall.io` sends the script to a hostile host that serves a good file. Nothing leaves the machine.

**Out of reach, for the S1 tests**, is a Scryfall that was never reached: a call given another Scryfall URL with `api=` runs with an empty cache folder of its own (through `$DECKWRIGHT_CACHE`) unless the test names one. At S1 every card those tests add offline had never been looked up; at head the first lookup caches the bulk file, which would otherwise answer for Scryfall. A test that wants Scryfall out of reach with the cache as it is runs through `deck.offline(url)`.

**The eval scaffolds' bulk file** (`test_evals_tools.py`): `evals/tools/bulk-cache.sh DEST` runs with a stand-in `curl` first on `PATH`, which prints a listing whose `default_cards` address the test chose and logs every other call. It copies the host's file to `DEST/default-cards.jsonl.gz` (each network case's scaffold calls it with `deckwright-cache`), downloads only an `https` address on a `scryfall.io` or `scryfall.com` host, and exits non-zero, having fetched and kept nothing, for any other.

**The player's files** are written to a folder outside the working folder (`player`), and handed over by path, as a player names a file they exported.

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
| `Lim-Dul's Vault`, `Smuggler’s Copter`, `smugglers copter` (each an exact 200) | queries that are the card once accents, punctuation and spaces are normalised away |
| Seven Dwarves | its text allows up to seven copies |
| Journey to Eternity // Atzal, Cave of Eternity | a double-faced card whose back face, not its front, is a Land |
| Elbrus, the Binding Blade // Withengar Unbound | a double-faced card whose front is a Legendary Artifact and whose back, a Legendary Creature, has no mana cost |
| `稲妻` (exact 404, fuzzy → Lightning Bolt), `Молния` (exact 404, fuzzy 404) | queries with no ASCII key, for the cache's hashed key |

`fixtures/scryfall/printing-<set>-<collector number>.json` is one card object as `cards/<id>` returned it on 2026-11-08, for each printing in `fixtures/collection/manabox.csv` and for Cultivate (`trc-460`), stripped the same way. The bulk file holds them beside the recorded cards, so it has what the real one has: several printings of one card (Vampiric Tutor, Uncharted Haven), and token printings that share a card's name (`tblb-15` Starscape Cleric, `tblb-8` Splash Lasher). Nine more, fetched the same way on 2026-11-08, are printings that share a card's name, or a face's name, and are not that card, or are it in another shape:

| Printing | Why it is here |
|---|---|
| `8ed-196` Inferno | the card: an Instant, legal |
| `ffdn-8` Inferno | a Jumpstart theme card in a memorabilia set: layout `front_card`, type `Card`, not legal; not a card |
| `acmm-64` Demonic Tutor // Demonic Tutor | an art-series card whose faces carry the card's name: type `Card // Card`, not legal; not a card |
| `rna-34` Clear the Mind | the card: a Sorcery, legal |
| `unk-UU11a` Clear, the Mind | an Un-set card of its own whose name is Clear the Mind's once normalised: not legal |
| `sld-1512` Sol Ring // Sol Ring | a `reversible_card` printing of Sol Ring: no type line or text of its own, only its faces' |
| `ema-248` Wasteland | the card: a Land, legal |
| `cmb2-121` Waste Land | a playtest card of its own whose name is Wasteland's once normalised: not legal |
| `sos-80` Emeritus of Woe // Demonic Tutor | a card of its own with a face named Demonic Tutor: legal |

`fixtures/collection/manabox.csv` is 35 real rows of the owner's ManaBox export, CRLF as exported, every `Purchase price` blank; `test_no_prices_in_fixtures` holds every CSV fixture to that. Its one binder is a `binder`. The collections with deck binders, bad quantities or unmatched names are built in the tests from recorded printings (`manabox_row`), in the export's own column order.

`fixtures/s1/` is a deck built by the script at 017a7a0, with every kind of entry S1 records (a looked-up card, basics, two categories, a Game Changer, a flagged card, a double-faced card, a card from the player's text, a changed target and bracket): its `deck.json`, and the `tally` stdout and the page bytes 017a7a0 gave for it.

## The contract the build must meet

The plan's checks leave these details open; the tests and the eval scaffolds fix them as below. Anything not listed is the builder's.

### Running and locating files

- `deck.py` finds `templates/<name>.toml`, `brackets.toml` and `page.html` beside itself, so a copy of the skill folder works on its own (`commander_template` copies it).
- Every deck command (`add`, `remove`, `target`, `bracket`, `tally`, `page`, `read`, `judge`, `theme`, `plan`) reads and writes `./deck.json` in the working folder unless `--deck PATH` is given after the command. A named deck is `decks/<file name>.json` (below), given as `--deck decks/<file name>.json`.
- The Scryfall base URL is `https://api.scryfall.com`, overridden by the environment variable `DECKWRIGHT_SCRYFALL_API` (the tests set it to `http://127.0.0.1:<port>`). The script asks it for `<base>/bulk-data` and nothing else: never `<base>/cards/…`. The Default Cards file is fetched from the `jsonl_download_uri` that listing gives for `default_cards`, wherever it points.

### Exit codes

| Code | When |
|---|---|
| 0 | the command did its work. A `lookup` is 0 even when a name was not found or only nearly matched: the entry says which. |
| 2 | usage error (argparse's default), and: no deck file; an unreadable deck file (not JSON, or JSON that is not a deck: a commander or card missing a field, a target that is not a number); an unknown template, or a template file missing a required key; an unknown category (in `add`, `target` or `judge`); `remove` of a card not in the deck; an out-of-range number (`bracket N` outside 1–5, `target C N` below 0, `remove --count` below 1); `page --out` into a folder that does not exist; `new --name` of a name whose file exists; a collection file that cannot be read (below); `available`, `read` or `judge` with no collection kept; `available --include` or `--exclude` of a binder the collection does not have, with a message that lists the collection's binders; `available --default` beside `--include` or `--exclude`; `not-owned` with an answer other than `yes` or `no`. A plain message says why, with no `Traceback` on stderr, and the deck file is unchanged. |
| 3 | Scryfall could not be reached for a card in neither cache: no per-card file, no readable bulk file, and the bulk file could not be fetched: connection refused, timeout, a download cut off, or any answer that is not a 200 (a proxy's 403, a 429, a 5xx), a proxy that refuses `CONNECT`, a listing with no `default_cards`, a `jsonl_download_uri` the script refuses (below), a redirect from it to a host the script would refuse, or a download over the cap. A plain message on stdout or stderr names the card, says Scryfall could not be reached and says nothing was recorded. After a 429 it says the script was rate-limited and to wait; after a download cut short of its `Content-Length` it says the download was cut off (not that the file is not a bulk file). Nothing is written to the deck, and nothing is kept as the bulk file. From `new --commander` the message does not offer `--from-player`, which cannot record a commander. |
| 4 | `add` (or `new --commander`) was given a name that is not found, or that only nearly matches another card. Nothing is written to the deck: a misspelling is recorded only once the player confirms the real name and it is added by that name. |

### The cache

- The folder is `$DECKWRIGHT_CACHE` if set, else `deckwright-cache/` in the working folder, the one the commands run from. A named deck in `decks/` shares it; the S1 eval fixtures put it there.
- One file per looked-up query: `<key>.json`. The *ASCII key* is the query lowercased, every run of characters outside `a-z0-9` replaced by one `-`, and leading and trailing `-` removed. `Meren of Clan Nel Toth` → `meren-of-clan-nel-toth.json`; `Vampiric Tutr` → `vampiric-tutr.json`.
- When the query has any non-ASCII character, or its ASCII key is empty, `<key>` is the ASCII key, `-`, and the first 12 hex digits of the SHA-256 of the casefolded query in UTF-8; with an empty ASCII key, the hash alone. So `稲妻` and `Молния` get different files, and `Lim-Dûl's Vault` is `lim-d-l-s-vault-<hash>.json`. An ASCII-only query's key is unchanged.
- The file holds one Scryfall card object, as `cards/named` returns it, with every price, purchase and image key removed. A misspelling's file holds the card its fuzzy match returned. The eval scaffolds pre-fill the cache in exactly this form. Whether a bulk lookup writes such a file is the builder's.
- The per-card cache is read first: a query with a file is answered from it, with no bulk file and no request, as the S1 eval fixtures need.
- A cache file that is not a card object (not JSON, or JSON but not a card) is treated as missing: the bulk file answers.

### The bulk file

- It is `default-cards.jsonl.gz` in the cache folder: the Default Cards file as downloaded, gzip-compressed JSON Lines, one Scryfall card object per line. The eval scaffolds put one there in exactly this form.
- A lookup the per-card cache does not answer reads it. When there is none, or its modification time is 7 days ago or more, the script fetches `<base>/bulk-data` and then the `jsonl_download_uri` of its `default_cards` entry, each once, with `User-Agent: deckwright/<version>` and an `Accept` header (`application/json` for the listing). Younger than 7 days, it is used as it is, with no request. `collection` refreshes it the same way, for a CSV as for a list of lines.
- When that fetch fails (out of reach, a proxy, a 429), a readable bulk file already there, however old, answers instead: exit 3 only when there is none.
- A file 7 days old or more, with no saved index of its own, is not read before its replacement is downloaded: it is read only if the download fails. (Reading one takes seconds.)
- A command that only counts or renders (`tally`, `page`, `target`, `bracket`, `remove`, `theme`, `plan`) never downloads, however old the file: it reads the file there, and with none it prints no `ownership` (and the page no ownership section) rather than reach the network. A `new` that fails for want of the file writes no deck file.
- On the real base (no `DECKWRIGHT_SCRYFALL_API`), a `jsonl_download_uri` is fetched only when it is `https` on a `scryfall.io` or `scryfall.com` host: `http:`, `file:`, another host and a look-alike (`data.scryfall.io.evil.example`) are refused, and nothing is fetched from them. Against another base (the tests' stand-in) the listing's address is followed as given. A redirect from an address it follows is held to the same rule: a 302 from `data.scryfall.io` to another host, a look-alike or plain `http` is refused, exit 3, and nothing is kept.
- A download is capped (the cap is the builder's, under 2 GiB): one past it, or whose `Content-Length` says it will be, is refused, exit 3, and nothing is kept. A `Content-Length` past the cap is refused from the header, before the body is read, so at once. The message says the file is larger than the cap, not that it was cut off.
- Commands run side by side in one folder never share a temporary file: two first downloads at once, or two commands reading a new bulk file at once, both succeed, and the file kept is whole.
- It is written whole or not at all: a download cut off part way leaves no `default-cards.jsonl.gz` (download to another name and rename), and the next lookup downloads again.
- One that cannot be read (not gzip, cut short, not JSON lines, empty) is treated as absent: downloaded again and replaced.
- Prices and links in it are never output; whether the kept file still holds them is the builder's.

### `lookup NAME…`

Stdout is a JSON array with one entry per `NAME`, in argument order:

```json
[{"query": "Vampiric Tutr", "result": "closest_match", "card": {…}}]
```

- `result` is `found` when the query equals a card's `name` or one of its faces' names, both sides *normalised*: NFKD, combining marks dropped, casefolded, every character outside `a-z0-9` dropped. So `Lim-Dul's Vault`, `Smuggler’s Copter`, `smugglers copter` and `lord of lineage` are `found`; `closest_match` when no card is found but one is near, and then `card` is that other card (`Vampiric Tutr` → Vampiric Tutor; how near is the builder's beyond that); `not_found` when there is none (`Xyzzy Plover Quux`), and then `card` is absent. All of it is computed from the bulk file.
- A token printing never answers a lookup: `Starscape Cleric` is the card (`Creature — Bat Cleric`), not the token lot of the same name.
- Where printings share a name, or a name once normalised, the card is the playable one, wherever the others come in the file: a memorabilia printing, a `front_card` (Jumpstart theme card, type `Card`), an art-series card and an Un-set card never answer for it. `Inferno` is the Instant, `Demonic Tutor` the Sorcery, `Clear the Mind` the Sorcery, never Clear, the Mind.
- A `reversible_card` printing is its card, read through its faces: `Sol Ring // Sol Ring` is Sol Ring (`Artifact`), even as the card's only printing in the file.
- `card` has exactly these keys, the *fixed fields*:

| Key | From Scryfall |
|---|---|
| `name` | `name` (a double-faced card's full `A // B` name) |
| `mana_cost` | `mana_cost`; for a card with faces, the mana cost of every face that has one, front first, in one string: a back face with no cost adds nothing, so Bloodline Keeper's is `{2}{B}{B}` |
| `type_line` | `type_line` |
| `oracle_text` | `oracle_text`; for a card with faces, every face's oracle text, front first, in one string |
| `color_identity` | `color_identity`, a list of the letters `W U B R G` |
| `commander_legality` | `legalities.commander`, as Scryfall spells it (`legal`, `not_legal`, `banned`, `restricted`) |
| `game_changer` | `game_changer`, a boolean |

### `new`, `add`, `remove`, `target`, `bracket`

- `new --template commander --commander NAME` writes a new `deck.json` (or `--deck PATH`, making any folders in the path that do not exist), as at S1. With `--name DECK`, it writes `decks/<file name>.json` instead (named decks, below).
- `add NAME [--count N] [--category C …]`: with no `--category`, a card judged in this deck's read is recorded under the read's categories (`judge`, below); `--category` given records it under those instead. `--count` defaults to 1; adding a name already in the deck adds to its copies (so a card named twice is held twice, for the checks to report). `--category` takes one or more category names exactly as the template spells them, may be given more than once (`--category A --category B` records under both), and may be left out. Lands come from the type line whatever is recorded, and from the front face's only: for a card shown with " // " in its type line, the part before it. Journey to Eternity // Atzal, Cave of Eternity, a Legendary Enchantment whose back is a Legendary Land, does not count in Lands.
- `add` records the card by Scryfall's name, whatever the query's spelling.
- `add NAME --from-player "TEXT" [--type-line LINE] [--count N] [--category C …]` records a card from the player's text with no lookup and no network, marked as such. The type line, when given, is used for the Lands category and the basic-land singleton exemption, read without regard to case: `add Forest --count 20 --from-player "({T}: Add {G}.)" --type-line "Basic Land — Forest"` counts 20 in Lands and is not flagged.
- A looked-up `add` of a name already recorded from the player's text replaces that entry's card with the lookup and drops the player-text mark; its copies and categories are kept, and the new copies are added. The entry is matched as `remove` matches, so a player-text `Bloodline Keeper` is replaced by the looked-up `Bloodline Keeper // Lord of Lineage`.
- `remove NAME [--count N]` matches the card's full name or a face name, normalised as `found` is (`remove "Bloodline Keeper"` removes the double-faced card). A name whose normalised form is empty, such as `Молния`, is matched by its casefolded name instead, never by the empty key, so `稲妻` and `Молния` from the player's text are two entries and `remove "Молния"` removes only Молния. `--count` is at least 1.
- `target CATEGORY N` (N ≥ 0) and `bracket N` (1–5) change the deck's target for one category and its bracket target.

### Deck files

The tests read only this of them: they are JSON; one changes on a recorded change (a card, a target, a judgement, a theme, a plan, a binder filter) and not on a lookup, a refused command or a read; and no key in one matches `price`, `purchase`, `image`, `tcgplayer` or `cardmarket`, at any depth. Their layout is otherwise the builder's. A deck file written at 017a7a0 (`fixtures/s1/deck.json`: no name, theme, plan, judgements or filter) opens: `tally` gives the same stdout, and `page` the same bytes, as at 017a7a0.

### `tally`

Stdout is one JSON object with at least:

```json
{
  "deck_size": 100,
  "total": 39,
  "categories": [{"name": "Lands", "target": 38, "count": 36, "cards": ["Command Tower", "Forest", "Swamp"]}, …],
  "checks": {"singleton": [], "color_identity": [], "commander_legality": [], "commander": []},
  "bracket": {"target": 2, "lowest": 2, "game_changers": [], "over": false, "game_changers_allowed": 0}
}
```

- `categories` is in template order. `count` counts copies (18 Swamp count 18); `cards` lists each card's name once, sorted.
- `total` counts the commander and every copy of every card, a card in two categories once.
- `name` is the deck's name, present only for a named deck.
- `ownership` is present only when a collection is kept (below), so an S1 deck's tally is unchanged: `{"owned": X, "not_owned": Y, "cards": [{"name", "owned", "not_owned"}, …]}`, one entry per recorded card, the commander apart, sorted as `cards` are. A card's `owned` is its copies up to the copies of it available to this deck, `not_owned` the rest; so removing copies takes the not-owned ones first, and a new collection or binder filter moves the marks at the next command. `owned` and `not_owned` at the top are the sums.
- `checks` lists, sorted, the names of the cards failing each check: more than one copy (except basic lands, cards whose text allows any number, and cards whose text says "A deck can have up to N cards named …", N in digits or a word from one to ten, which are flagged only above N), colour identity outside the commander's, `commander_legality` other than `legal`. A card from the player's text is held to the copies check, by the count and type line given, but never to colour identity or legality, which its text cannot settle.
- `checks.commander` is `[<commander>]` when the front face's type line (the whole type line, for a card with one face) lacks "Legendary" or "Creature" and its oracle text lacks "can be your commander"; otherwise `[]`. So Elbrus, the Binding Blade, a Legendary Artifact whose back is a Legendary Creature, is flagged.
- `bracket.lowest` is 2 with no Game Changers, 3 with one to three, 4 with four or more, counted once per name with the commander included; `game_changers` is sorted. `bracket.over` is true when `lowest > max(target, 2)`. `bracket.game_changers_allowed` is how many Game Changers `brackets.toml` allows at the target, a target of 1 read as 2 (1 or 2 → 0, 3 → 3), and is absent when the target has no limit (4, 5).
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
| `data-section="checks"` | the name of every flagged card, the commander when `checks.commander` flags it, and the words "not checked" when the deck has cards from the player's text |
| `data-section="bracket"` | the word "target" before the bracket target, the word "lowest" before the lowest bracket the deck fits (each within 40 characters), every Game Changer, and the word "over" exactly when `bracket.over` is true |
| `data-section="player-text"` | the name of every card recorded from the player's text, and no other card |
| `data-section="decklist"` | the decklist, as plain text: no element inside it, so it appears in the source as one escaped run |
| `data-section="name"` | a named deck's name, exactly as given; absent for a deck without one |
| `data-section="theme"` | the theme, when one is set |
| `data-section="plan"` | the plan sentence, when one is set |
| `data-section="ownership"` | only with a collection kept: for each card with copies not owned, its name and then `N owned` and `M not owned` (within 40 characters of each other), and `Total` with the deck's `X owned` and `Y not owned` |

- A named deck's page is titled by its name: `<title>` holds it, as given, escaped.
- With no `--out`, `page` writes `<the deck file's name without .json>.html` beside the deck file: `decks/rat-pack.html` for `decks/rat-pack.json`, `deck.html` for `./deck.json`.

- The decklist is `// COMMANDER`, `1 <commander>`, a blank line, `// MAINBOARD`, then `count Name` rows sorted by name ignoring case, one row per name with its copies summed (basics included), no set codes, no other lines.
- The page has a copy button, at most one `<script>` element, none with `src`, and uses the clipboard.
- The same deck file gives the same bytes, from any folder, at any time: no timestamps and no paths. `page` never touches the network.

### Named decks

- `new --template T --commander NAME --name DECK` writes `decks/<file name>.json` in the working folder, making `decks/` if there is none. The *file name* is DECK under the cache's key rule: `Rat Pack` → `rat-pack`, `Rats: "The/Pack" <3?*|` → `rats-the-pack-3`, a name with a character outside ASCII keyed with its hash (`Råttornas kväll` → `r-ttornas-kv-ll-<12 hex>`). So any name makes a file. A name too long for a file name (300 characters, say) still makes one, of `a-z0-9-` and at most 255 bytes with `.json`: how it is shortened is the builder's, and `new` prints it. Its page still shows the whole name.
- `new` prints one JSON object holding `file`, the deck file's path relative to the working folder (`decks/rat-pack.json`, `decks/r-ttornas-kv-ll-<12 hex>.json`): the path every later command takes as `--deck`.
- A name whose file exists is refused, exit 2, with a message saying the name is taken; the file is unchanged and no other file is written. `rat pack`, `Rat-Pack!` and `RAT  PACK` all take `Rat Pack`'s file.
- `decks` prints a JSON array, one entry per `decks/*.json` sorted by file: `{"name", "file", "commander"}`, `file` relative to the working folder (`decks/rat-pack.json`). A deck file with no name (S1's) is listed under its file's name without `.json`.

### The collection

- `collection FILE` reads the player's collection, keeps the file in the working folder byte for byte (where is the builder's), and prints a report. Handing over another replaces the one kept, and every later command reads the new one. The collection belongs to the working folder: every deck in it shares it.
- A file is a **ManaBox CSV export** when its first line, split on commas, holds two or more of ManaBox's column names (`Binder Name`, `Binder Type`, `Name`, `Set code`, `Set name`, `Collector number`, `Foil`, `Rarity`, `Quantity`, `ManaBox ID`, `Scryfall ID`, `Misprint`, `Altered`, `Condition`, `Language`, `Added`, …). It must then have `Scryfall ID`, `Name` and `Quantity`; one missing is exit 2 naming each missing column. Quoted cells (`"Zoraline, Cosmos Caller"`) and CRLF are read as the export writes them.
- Any other text is a **list of lines**, each `N Name`: a whole number, spaces, a name. Blank lines are skipped.
- A file that is not text (not UTF-8; a BOM is allowed) is exit 2. Exit 2 keeps nothing of that file, and the collection kept before it stays.
- A CSV row is matched by its `Scryfall ID` against the bulk file: a token's printing counts as that token, never as the card of the same name, and a token is not a card, so manabox.csv's Starscape Cleric is 6 copies of the card and its row 27, a token lot of 2, is reported in `not_a_card`. So is a theme card or an art card (layout `front_card` or `art_series`). An Un-card's or a playtest card's printing is its own card, never the card whose name it shares once normalised: a collection holding only Clear, the Mind (`unk-UU11a`) or Waste Land (`cmb2-121`) holds no Clear the Mind or Wasteland, and neither `available` nor `read` lists it under that name; a `reversible_card` printing is its card. A row whose ID is not in the bulk file is matched by its `Name`, as `found` matches. A line is matched by its name, as `found` matches, a face's name included (`1 Lord of Lineage`).
- Copies are summed per card across rows, printings, finishes and binders; basic lands count what the rows say. Each copy keeps its binder.
- The report is one JSON object: `{"entries", "matched", "near_miss", "not_a_card", "unknown", "needs_quantity", …}`. `entries` counts the CSV's rows after the header, or the list's non-blank lines. Every entry that matches no card is in exactly one of `near_miss` (with `"card"`, the card it nearly names: `Cultivat` → Cultivate), `not_a_card` (a token lot, a theme card, an art card) or `unknown`; a token lot is never `matched`, so manabox.csv is 33 matched and 2 not cards (rows 23 and 27). An entry with no quantity, 0, or one that is not a whole number in ASCII digits (`three`, `²`, `３`) is in `needs_quantity` and counts nothing, or the file is refused with exit 2; never a traceback. Each reported entry is `{"name", "row"}` for a CSV, rows numbered as a spreadsheet shows them (the header is row 1, and a blank line is a row too, so a row after one keeps its number), or `{"name", "line"}` for a list (the file's line number, blank lines counted). `matched` + every reported entry = `entries`.

### `available [--deck PATH] [--include BINDER …] [--exclude BINDER …] [--default]`

- Prints `{"cards": [{"name", "owned", "available"}, …], "held_back": [{"binder", "copies"}, …]}`. `cards` lists every card in the collection (never a token) once, by Scryfall's name, sorted as the tally sorts; `owned` is every copy, `available` those this deck may use. `held_back` lists each binder with copies not available and how many, sorted by binder name; `[]` for a list of lines.
- By default every copy is available except those in a binder whose `Binder Type` is `deck`.
- `--include BINDER` makes that binder's copies available ("use the cards in my Vren deck too"); `--exclude BINDER` holds back that binder's copies, whatever its type. Binder names are matched as the export spells them. A binder the collection does not have is exit 2, the message listing the binders it has, and nothing of that call is kept.
- With `--deck`, a filter given is kept in that deck's file, replacing any kept before, and every later command for that deck (`available`, `read`, `tally`, `page`) uses it. Without `--deck`, a filter is that call's only. `--default` with `--deck` drops the deck's kept filter: every copy outside a deck binder is available again. `--default` is given alone: beside `--include` or `--exclude` it is exit 2, and nothing of that call is kept.

### Ownership and `not-owned yes|no`

- A looked-up card's copies are joined to the collection's by its own name only: a card with a face of another card's name is not that card. Owning Emeritus of Woe // Demonic Tutor (`sos-80`), a looked-up Demonic Tutor is not owned, nor the other way round. A looked-up Honorbound Page // Forum's Favor is owned when the collection lists `1 Forum's Favor`, because that line is matched as `found` matches, a face's name included, and so is the card.
- A card recorded from the player's text is joined by its name first, then by any spelling of it, normalised as `found` is, then by a face's name: one recorded as `smugglers copter`, `Lim-Dul's Vault` or `Lord of Lineage` is owned when the collection holds Smuggler's Copter, Lim-Dûl's Vault or Bloodline Keeper // Lord of Lineage. A card of its own that shares another's name once normalised (Clear, the Mind) is joined by its own name only.
- `not-owned yes` and `not-owned no` (a deck command, taking `--deck`) record the player's answer to building with cards they do not own in that deck's file. The tally carries it as a top-level `not_owned`, `true` or `false`, the latest answer; absent until one is recorded.

### The read: `read`, `judge`, `theme`, `plan`

- `read` prints `{"unjudged": N, "cards": [...]}`, `unjudged` the first key, so a cut-off output still shows it. `cards` is the *narrowing*: every card with a copy available to this deck whose colour identity is within the commander's and whose `commander_legality` is `legal`, lands and nonlands alike, never a token, sorted as the tally sorts; whether the commander itself is listed is the builder's. Each entry is `{"name", "available", "card"}`, `card` the fixed fields, plus `"categories"` and `"serves_theme"` once judged, each absent until then. `unjudged` counts the entries with no judgement.
- `judge JSON` records judgements in the deck's file: JSON is an array of `{"name", "categories": [...], "serves_theme": true|false}`, `categories` the template's names (none to several), `categories` and `serves_theme` each optional. A judgement's `name` is matched against the read's cards by whole name first, normalised as `found` is, and by a face's name only where no card has the whole name: with Demonic Tutor and Emeritus of Woe // Demonic Tutor both in the read, `"Demonic Tutor"` is Demonic Tutor. A card judged again has each field it is given replaced, and keeps each it is not: `{"name": "Starscape Cleric", "serves_theme": false}` after a new theme keeps the categories recorded before (B-18), and one with only `categories` keeps the theme fit. An unknown category is exit 2, and nothing of that call is recorded. A judgement records no card. It prints `{"unjudged": N, …}`, `unjudged` first.
- `theme TEXT` and `plan TEXT` set the deck's theme and its plan sentence; the page shows them. Neither changes a category, a target, the deck size or the bracket target, whatever the text says.

### What the skill must do that the eval graders read

- The cache folder is `deckwright-cache/` in the working folder, and the graders read it there.
- A deck is started with `new … --name`. When the player takes none of the names offered (they answer "carry on", or anything that is not a name), the deck is named after its commander as Scryfall spells it: Meren's is `Meren of Clan Nel Toth`, so its page is `decks/meren-of-clan-nel-toth.html`.
- The page is rendered with `page` and no `--out`, to `decks/<file name>.html`, wherever the interface has no artifacts (Claude Code). The graders read it there.
- The player's collection is handed to `collection` by the path they name; `available --deck … --include 'BINDER'` follows "use the cards in my … deck too".
- The read is done with `read` and `judge` before the first suggestion from the collection, and a `read` or `judge` whose output shows `"unjudged": 0` comes before it.
- A yes to a collection card whose critique did not move it is recorded with `add 'NAME'` and no `--category`, so the read's categories are used.
- The theme is set with `theme` and the plan sentence with `plan`; a change of theme is a new `theme`, then `judge` again, giving `serves_theme` alone so the categories recorded are kept.
- Every deck command is given `--deck` with the `file` that `new` (or `decks`) printed.
- The player's answer to building with cards they do not own is recorded with `not-owned yes` or `not-owned no`, and asked only while the tally has no `not_owned`.
