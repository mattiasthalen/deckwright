# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Everything in a deckwright interview that can be computed: lookups, the collection, the deck, the tally, the page.

The skill judges; this script counts, checks and renders. Run it as `uv run deck.py <command>`;
`uv run deck.py --help` lists the commands. Card facts come from Scryfall's Default Cards bulk file
and nowhere else.
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import difflib
import gzip
import hashlib
import html
import http.client
import io
import json
import os
import re
import shutil
import sys
import tempfile
import time
import tomllib
import unicodedata
import urllib.error
import urllib.request
import zlib
from pathlib import Path

VERSION = "0.2.0"
HERE = Path(__file__).resolve().parent
SCRYFALL = "https://api.scryfall.com"
ANY_NUMBER = "a deck can have any number of cards named"
UP_TO = re.compile(r"a deck can have up to (\w+) cards named")
NUMBER_WORDS = {w: n for n, w in enumerate("one two three four five six seven eight nine ten".split(), 1)}

EXIT_UNREACHABLE = 3
EXIT_NOT_RECORDED = 4

BULK_FILE = "default-cards.jsonl.gz"
BULK_INDEX = "default-cards.index.json"
# Bumped whenever index_bulk changes what it keeps, so an index built by an older script is rebuilt.
INDEX_FORMAT = 1
# Scryfall publishes Default Cards daily and asks clients to cache it; a week keeps card facts current.
BULK_MAX_AGE = 7 * 24 * 3600
# How near a name must be to another card's to be named as its closest match.
NEAR = 0.85
NOT_CARDS = {"token", "double_faced_token", "emblem", "art_series", "front_card"}
# Playtest and souvenir sets reprint real names (and near names) as cards no deck plays.
SIDE_SETS = {"funny", "memorabilia"}
# Default Cards is about 81 MB; anything far past that is not it.
BULK_MAX_BYTES = 1 << 30
BULK_HOST = re.compile(r"https://[a-z0-9.-]+\.scryfall\.(?:io|com)/")

# Past this a file name risks the file system's limit; a longer name keeps a hash of the whole.
MAX_KEY = 100
DECKS = Path("decks")
COLLECTION = Path("deckwright-collection")
MANABOX_COLUMNS = {
    "Binder Name", "Binder Type", "Name", "Set code", "Set name", "Collector number", "Foil", "Rarity",
    "Quantity", "ManaBox ID", "Scryfall ID", "Misprint", "Altered", "Condition", "Language", "Added",
}  # fmt: skip
LINE = re.compile(r"^\s*([0-9]+)\s+(.+?)\s*$")
WHOLE_NUMBER = re.compile(r"[0-9]+")


class Failure(Exception):
    def __init__(self, message: str, code: int):
        super().__init__(message)
        self.code = code


class Unreachable(Failure):
    def __init__(self, what: str, reason: str):
        super().__init__(
            f"Scryfall could not be reached to look up {what} ({reason}). Nothing was recorded.", EXIT_UNREACHABLE
        )


class BulkUnreadable(Exception):
    pass


def comparable(name: str) -> str:
    """A name as Scryfall matches it: case, accents and punctuation ignored."""
    decomposed = unicodedata.normalize("NFKD", name.casefold())
    return "".join(c for c in decomposed if c.isascii() and c.isalnum())


def matching_key(name: str) -> str:
    """The comparable name, or the casefolded name where nothing comparable is left (a name in another script)."""
    return comparable(name) or name.casefold()


def file_key(name: str) -> str:
    """A name as a file name: lowercase ASCII and dashes, with a hash where the name is not plain ASCII."""
    key = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if len(key) > MAX_KEY:
        key = key[:MAX_KEY].rstrip("-") + "-" + hashlib.sha256(name.casefold().encode("utf-8")).hexdigest()[:12]
    elif not key or not name.isascii():
        digest = hashlib.sha256(name.casefold().encode("utf-8")).hexdigest()[:12]
        key = f"{key}-{digest}" if key else digest
    return key


def names_of(card: dict) -> list[str]:
    return [card["name"], *card["name"].split(" // ")]


def by_name(name: str):
    return (name.casefold(), name)


# Card facts ----------------------------------------------------------------------------


def fixed_fields(card: dict) -> dict:
    faces = card.get("card_faces") or []

    def joined(key: str, between: str) -> str:
        if key in card:
            return card[key]
        return between.join(face[key] for face in faces if face.get(key))

    return {
        "name": card["name"],
        "mana_cost": joined("mana_cost", " // "),
        "type_line": card.get("type_line", ""),
        "oracle_text": joined("oracle_text", "\n//\n"),
        "color_identity": list(card.get("color_identity", [])),
        "commander_legality": card.get("legalities", {}).get("commander", "not_legal"),
        "game_changer": bool(card.get("game_changer", False)),
    }


def is_card(card: dict) -> bool:
    """Whether a printing is a card a deck can hold; a token printing is a token whatever its name."""
    return card.get("layout") not in NOT_CARDS and card.get("set_type") != "token"


def rank(card: dict) -> int:
    """Which printing speaks for a card when several share its name: an ordinary one before a playtest or
    souvenir printing, so "Clear the Mind" is the real card and not the playtest "Clear, the Mind"."""
    return 1 if card.get("set_type") in SIDE_SETS else 0


def index_bulk(path: Path) -> dict:
    """What the script needs from a bulk file, read line by line so the file is never held whole.

    `cards` holds each card's fixed fields under its comparable name, `faces` each face's comparable
    name and the card it names, `printings` every printing's Scryfall ID and the comparable name of the
    card it is ("" for a token or other non-card), `not_cards` the comparable names of non-cards.
    """
    cards: dict[str, dict] = {}
    ranks: dict[str, int] = {}
    faces: dict[str, str] = {}
    printings: dict[str, str] = {}
    reversible: dict[str, str] = {}
    not_cards: set[str] = set()
    try:
        with gzip.open(path, "rt", encoding="utf-8") as lines:
            for line in lines:
                if not line.strip():
                    continue
                card = json.loads(line)
                if not isinstance(card, dict) or "id" not in card or "name" not in card:
                    raise BulkUnreadable(f"a line is not a card: {line[:60]!r}")
                key = comparable(card["name"])
                if not is_card(card):
                    printings[card["id"]] = ""
                    not_cards.add(key)
                    continue
                if card.get("layout") == "reversible_card":
                    # Both faces of a reversible printing are one card printed twice ("Sol Ring // Sol Ring"),
                    # which other printings carry under its own name; face 0 may name only its front.
                    reversible[card["id"]] = comparable(card["card_faces"][0]["name"])
                    continue
                printings[card["id"]] = key
                if key and (key not in cards or rank(card) < ranks[key]):
                    cards[key], ranks[key] = fixed_fields(card), rank(card)
                    for face in card.get("card_faces", []):
                        faces.setdefault(comparable(face.get("name", "")), key)
    except (OSError, EOFError, zlib.error, ValueError, UnicodeDecodeError) as error:
        raise BulkUnreadable(str(error)) from None
    if not printings and not reversible:
        raise BulkUnreadable("it holds no cards")
    faces.pop("", None)
    for scryfall_id, key in reversible.items():
        printings[scryfall_id] = key if key in cards else faces.get(key, "")
    return {"cards": cards, "faces": faces, "printings": printings, "not_cards": sorted(not_cards)}


class Scryfall:
    """Card facts from the per-card cache first, then from the Default Cards bulk file it keeps beside it.

    `fresh` downloads a file a week old or more before answering: lookups and a collection handed
    over want current facts. Without it, any readable file serves, and with `download` off there is
    no network at all: the deck commands that only count never wait on one.
    """

    def __init__(self, cache: Path, fresh: bool, download: bool):
        self.cache = cache
        self.base = os.environ.get("DECKWRIGHT_SCRYFALL_API") or SCRYFALL
        self.fresh = fresh
        self.download = download
        self._index: dict | None = None

    def lookup(self, query: str) -> dict:
        """One `{"query", "result", "card"}` entry. Raises Unreachable when no source can answer."""
        cached = self._cached(query)
        if cached is not None:
            card = fixed_fields(cached)
            found = comparable(query) in (comparable(n) for n in names_of(card))
            return {"query": query, "result": "found" if found else "closest_match", "card": card}
        what = repr(query)
        card = self.by_name(query, what)
        if card is not None:
            return {"query": query, "result": "found", "card": card}
        close = self.closest(query, what)
        if close is None:
            return {"query": query, "result": "not_found"}
        return {"query": query, "result": "closest_match", "card": close}

    def by_name(self, name: str, what: str) -> dict | None:
        """The card whose name, or a face's name, is this one, normalised."""
        key = comparable(name)
        if not key:
            return None
        index = self.index(what)
        return index["cards"].get(key) or index["cards"].get(index["faces"].get(key, ""))

    def by_printing(self, scryfall_id: str, what: str) -> tuple[bool, dict | None]:
        """Whether the bulk file has this printing, and its card (None for a token or other non-card)."""
        index = self.index(what)
        if scryfall_id not in index["printings"]:
            return False, None
        return True, index["cards"].get(index["printings"][scryfall_id])

    def closest(self, name: str, what: str) -> dict | None:
        key = comparable(name)
        if not key:
            return None
        index = self.index(what)
        close = difflib.get_close_matches(key, [*index["cards"], *index["faces"]], n=1, cutoff=NEAR)
        if not close:
            return None
        return index["cards"].get(close[0]) or index["cards"][index["faces"][close[0]]]

    def is_not_a_card(self, name: str, what: str) -> bool:
        key = comparable(name)
        return not key or key in self.index(what)["not_cards"]

    def readable(self) -> bool:
        """Whether a readable bulk file is at hand, so a collection can be read with no network."""
        try:
            self.index("the collection's cards")
        except Unreachable:
            return False
        return True

    def index(self, what: str) -> dict:
        """The bulk file's index, downloading the file when there is none readable (or, fresh, a week old).

        A stale file that reads still answers when the download fails, so a week offline loses nothing.
        """
        if self._index is None:
            bulk = self.cache / BULK_FILE
            on_disk = self._read_index(bulk) if bulk.is_file() else None
            stale = on_disk is None or (self.fresh and time.time() - bulk.stat().st_mtime >= BULK_MAX_AGE)
            if stale and self.download:
                try:
                    on_disk = self._download(what)
                except Unreachable:
                    if on_disk is None:
                        raise
            if on_disk is None:
                raise Unreachable(what, "no card data is kept and none was downloaded")
            on_disk["not_cards"] = set(on_disk["not_cards"])
            self._index = on_disk
        return self._index

    def _read_index(self, bulk: Path) -> dict | None:
        saved = self.cache / BULK_INDEX
        try:
            kept = json.loads(saved.read_text(encoding="utf-8"))
            if kept.get("source") == index_source(bulk):
                return kept
        except (OSError, ValueError, UnicodeDecodeError, AttributeError, KeyError, TypeError):
            pass
        try:
            index = index_bulk(bulk)
        except BulkUnreadable:
            return None
        self._save_index(index, bulk)
        return index

    def _save_index(self, index: dict, bulk: Path) -> None:
        saved = self.cache / BULK_INDEX
        with side_file(saved) as partial:
            partial.write_text(json.dumps({"source": index_source(bulk), **index}, ensure_ascii=False), "utf-8")
            os.replace(partial, saved)

    def _get(self, url: str, what: str, accept: str):
        request = urllib.request.Request(url, headers={"User-Agent": f"deckwright/{VERSION}", "Accept": accept})
        try:
            return urllib.request.urlopen(request, timeout=60)
        except urllib.error.HTTPError as error:
            if error.code == 429:
                raise Unreachable(what, "HTTP 429: rate-limited; wait 30 seconds before looking anything up") from None
            raise Unreachable(what, f"HTTP {error.code}") from None
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise Unreachable(what, str(getattr(error, "reason", error))) from None

    def _download(self, what: str) -> dict:
        """Downloads Default Cards whole to a side file, and keeps it only once it reads as a bulk file."""
        try:
            with self._get(f"{self.base}/bulk-data", what, "application/json") as response:
                listing = json.loads(response.read().decode("utf-8"))
            uri = next(b["jsonl_download_uri"] for b in listing["data"] if b.get("type") == "default_cards")
        except (ValueError, UnicodeDecodeError, KeyError, TypeError, StopIteration):
            raise Unreachable(what, "the bulk data listing has no default_cards") from None
        except (http.client.HTTPException, OSError) as error:
            raise Unreachable(what, type(error).__name__) from None
        if self.base == SCRYFALL and not BULK_HOST.match(str(uri)):
            raise Unreachable(what, f"the listing points outside Scryfall: {str(uri)[:80]}")

        self.cache.mkdir(parents=True, exist_ok=True)
        bulk = self.cache / BULK_FILE
        with side_file(bulk) as partial:
            try:
                with self._get(uri, what, "application/gzip, */*") as response, partial.open("wb") as out:
                    expected = int(response.headers.get("Content-Length") or 0)
                    received = copy_at_most(response, out, BULK_MAX_BYTES)
                if expected and received != expected:
                    raise Unreachable(what, f"the download was cut off at {received} of {expected} bytes")
                index = index_bulk(partial)
                os.replace(partial, bulk)
            except (http.client.HTTPException, OSError) as error:
                raise Unreachable(what, f"the download was cut off: {type(error).__name__}") from None
            except BulkUnreadable:
                raise Unreachable(what, "the download was not a bulk file") from None
        self._save_index(index, bulk)
        return index

    def _cached(self, query: str) -> dict | None:
        """The per-card cache's card, or None when there is none or the file does not hold a card."""
        path = self.cache / f"{file_key(query)}.json"
        if not path.is_file():
            return None
        try:
            card = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None
        return card if isinstance(card, dict) and card.get("object") == "card" and "name" in card else None


def index_source(bulk: Path) -> list[int]:
    """What the saved index was built from: an index for another file, or by an older script, is rebuilt."""
    return [INDEX_FORMAT, bulk.stat().st_size, bulk.stat().st_mtime_ns]


@contextlib.contextmanager
def side_file(final: Path):
    """A side file of its own beside `final`, so two commands writing at once never share one; removed
    unless it was moved into place."""
    handle, name = tempfile.mkstemp(dir=final.parent, prefix=final.name + ".", suffix=".part")
    os.close(handle)
    partial = Path(name)
    try:
        yield partial
    finally:
        partial.unlink(missing_ok=True)


def copy_at_most(source, out, limit: int) -> int:
    copied = 0
    while chunk := source.read(1 << 20):
        copied += len(chunk)
        if copied > limit:
            raise OSError(f"more than {limit} bytes")
        out.write(chunk)
    return copied


# The collection ------------------------------------------------------------------------


def kept_collection() -> Path | None:
    files = sorted(COLLECTION.glob("*")) if COLLECTION.is_dir() else []
    return files[0] if files else None


def read_collection(data: bytes, scryfall: Scryfall) -> tuple[list[dict], dict]:
    """The collection's copies, `[{name, copies, binder, binder_type}]`, and the report on every entry."""
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = None
    if text is None or "\x00" in text:
        raise Failure("The collection file is not text: hand over a ManaBox CSV export or a list of N Name lines.", 2)
    what = "the collection's cards"
    report = {"entries": 0, "matched": 0, "near_miss": [], "not_a_card": [], "unknown": [], "needs_quantity": []}
    copies: list[dict] = []

    def unmatched(name: str, where: dict) -> None:
        if scryfall.is_not_a_card(name, what):
            report["not_a_card"].append({"name": name, **where})
            return
        close = scryfall.closest(name, what)
        if close is not None:
            report["near_miss"].append({"name": name, **where, "card": close["name"]})
        else:
            report["unknown"].append({"name": name, **where})

    def count(card: dict, quantity: int, binder: str = "", binder_type: str = "") -> None:
        report["matched"] += 1
        copies.append({"name": card["name"], "copies": quantity, "binder": binder, "binder_type": binder_type})

    lines = text.splitlines()
    header = [c.strip() for c in next(csv.reader(lines[:1]), [])]
    if len(MANABOX_COLUMNS & set(header)) >= 2:
        missing = [c for c in ("Scryfall ID", "Name", "Quantity") if c not in header]
        if missing:
            raise Failure(
                f"The CSV export has no {', '.join(missing)} column. Export the collection from ManaBox again.", 2
            )
        rows = csv.DictReader(io.StringIO(text, newline=""))
        for row in rows:
            if not any((value or "").strip() for value in row.values() if isinstance(value, str)):
                continue
            report["entries"] += 1
            # line_num counts the lines read so far, blank ones included, as a spreadsheet numbers its rows.
            name, where = row["Name"] or "", {"row": rows.line_num}
            quantity = (row["Quantity"] or "").strip()
            if not WHOLE_NUMBER.fullmatch(quantity) or int(quantity) < 1:
                report["needs_quantity"].append({"name": name, **where})
                continue
            listed, card = scryfall.by_printing((row["Scryfall ID"] or "").strip(), what)
            if listed and card is None:
                report["not_a_card"].append({"name": name, **where})
                continue
            card = card or scryfall.by_name(name, what)
            if card is None:
                unmatched(name, where)
                continue
            count(card, int(quantity), row.get("Binder Name") or "", (row.get("Binder Type") or "").casefold())
    else:
        for line_number, line in enumerate(lines, 1):
            if not line.strip():
                continue
            report["entries"] += 1
            match = LINE.match(line)
            name = match.group(2) if match else line.strip()
            if not match or int(match.group(1)) < 1:
                report["needs_quantity"].append({"name": name, "line": line_number})
                continue
            card = scryfall.by_name(name, what)
            if card is None:
                unmatched(name, {"line": line_number})
                continue
            count(card, int(match.group(1)))
    return copies, report


def availability(copies: list[dict], binders: dict) -> dict:
    """Owned and available copies per card, and the copies held back per binder.

    Copies in a deck binder are held back unless `binders["include"]` names it; `binders["exclude"]`
    holds a binder back whatever its type.
    """
    include, exclude = set(binders.get("include", [])), set(binders.get("exclude", []))
    owned: dict[str, int] = {}
    available: dict[str, int] = {}
    held: dict[str, int] = {}
    for c in copies:
        owned[c["name"]] = owned.get(c["name"], 0) + c["copies"]
        available.setdefault(c["name"], 0)
        if c["binder"] in exclude or (c["binder_type"] == "deck" and c["binder"] not in include):
            held[c["binder"]] = held.get(c["binder"], 0) + c["copies"]
        else:
            available[c["name"]] += c["copies"]
    return {
        "cards": [{"name": n, "owned": owned[n], "available": available[n]} for n in sorted(owned, key=by_name)],
        "held_back": [{"binder": b, "copies": held[b]} for b in sorted(held)],
    }


def deck_availability(deck: dict | None, scryfall: Scryfall) -> dict | None:
    """What the kept collection makes available to this deck, under its binder filter.

    None with no collection, and None when no card data is at hand to read it with and this command
    may not download it: a tally then carries no ownership rather than waiting on the network.
    """
    path = kept_collection()
    if path is None or (not scryfall.download and not scryfall.readable()):
        return None
    copies, _ = read_collection(path.read_bytes(), scryfall)
    return availability(copies, (deck or {}).get("binders", {}))


def narrowing(deck: dict, scryfall: Scryfall) -> dict:
    """The read: every available card within the commander's colours and legal in Commander, with its judgement."""
    available = deck_availability(deck, scryfall)
    if available is None:
        raise Failure("No collection is kept: hand one over with collection FILE.", 2)
    identity = set(deck["commander"]["color_identity"])
    judgements = deck.get("judgements", {})
    cards = []
    for c in available["cards"]:
        if c["available"] < 1:
            continue
        card = scryfall.by_name(c["name"], "the collection's cards")
        if card is None or not set(card["color_identity"]) <= identity or card["commander_legality"] != "legal":
            continue
        cards.append({"name": c["name"], "available": c["available"], "card": card, **judgements.get(c["name"], {})})
    return {"unjudged": sum(1 for e in cards if e["name"] not in judgements), "cards": cards}


# The deck file -------------------------------------------------------------------------


def load_template(name: str) -> dict:
    path = HERE / "templates" / f"{name}.toml"
    if not path.is_file():
        known = sorted(p.stem for p in (HERE / "templates").glob("*.toml"))
        raise Failure(f"No template {name!r}. Templates: {', '.join(known)}.", 2)
    try:
        template = tomllib.loads(path.read_text(encoding="utf-8"))
        checked = {
            "name": template.get("name", name),
            "deck_size": template["deck_size"],
            "bracket_target": template["bracket_target"],
            "categories": template["categories"],
        }
        for category in checked["categories"]:
            category["name"], category["target"], category["counts_when"]
    except (tomllib.TOMLDecodeError, UnicodeDecodeError, KeyError, TypeError) as error:
        raise Failure(f"The template {name!r} is not readable or lacks a key ({error}).", 2) from None
    return checked


def read_deck(path: Path) -> dict:
    if not path.is_file():
        raise Failure(f"No deck file at {path}. Start one with: new --template <name> --commander NAME", 2)
    try:
        deck = json.loads(path.read_text(encoding="utf-8"))
        deck["commander"]["name"], deck["cards"]
        targets = [c["target"] for c in deck["template"]["categories"]] + [deck["template"]["bracket_target"]]
        if not all(type(n) is int for n in targets):
            raise TypeError("a target is not a whole number")
    except (json.JSONDecodeError, UnicodeDecodeError, KeyError, TypeError) as error:
        raise Failure(f"The deck file {path} is not a readable deck ({error}). Start a new one with new.", 2) from None
    return deck


def write_deck(path: Path, deck: dict) -> None:
    path.write_text(json.dumps(deck, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def category_names(deck: dict, asked: list[str]) -> list[str]:
    known = [c["name"] for c in deck["template"]["categories"]]
    unknown = [c for c in asked if c not in known]
    if unknown:
        raise Failure(f"Unknown category {unknown[0]!r}. Categories: {', '.join(known)}.", 2)
    return [c for c in known if c in asked]


def looked_up(scryfall: Scryfall, name: str) -> dict:
    """The fixed fields of the card named exactly so; anything less is not recorded."""
    entry = scryfall.lookup(name)
    if entry["result"] == "not_found":
        raise Failure(f"No card named {name!r}. Nothing was recorded.", EXIT_NOT_RECORDED)
    if entry["result"] == "closest_match":
        raise Failure(
            f"No card named {name!r}; the closest match is {entry['card']['name']!r}. "
            "Nothing was recorded: add it by that name once the player confirms it.",
            EXIT_NOT_RECORDED,
        )
    return entry["card"]


def player_card(name: str, text: str, type_line: str) -> dict:
    return {
        "name": name,
        "mana_cost": "",
        "type_line": type_line,
        "oracle_text": text,
        "color_identity": [],
        "commander_legality": "unknown",
        "game_changer": False,
    }


def recorded(deck: dict, name: str) -> dict | None:
    """The deck's entry for a card, matched by its full name or a face name as Scryfall matches names."""
    wanted = matching_key(name)
    return next((e for e in deck["cards"] if wanted in map(matching_key, names_of(e["card"]))), None)


# The tally -----------------------------------------------------------------------------


def counts_in(entry: dict, category: dict) -> bool:
    word = category.get("from_type_line")
    if word:
        front = entry["card"]["type_line"].split(" // ")[0]
        return re.search(rf"\b{re.escape(word)}\b", front, re.I) is not None
    return category["name"] in entry["categories"]


def tally(deck: dict, available: dict | None = None) -> dict:
    """The deck counted against its template; `ownership` only when a collection is kept."""
    commander = deck["commander"]
    entries = deck["cards"]
    categories = []
    for category in deck["template"]["categories"]:
        counted = [e for e in entries if counts_in(e, category)]
        categories.append(
            {
                "name": category["name"],
                "counts_when": category["counts_when"],
                "target": category["target"],
                "count": sum(e["count"] for e in counted),
                "cards": sorted((e["card"]["name"] for e in counted), key=by_name),
            }
        )

    looked = [e for e in entries if not e.get("from_player")]
    identity = set(commander["color_identity"])

    def copies_allowed(card: dict) -> float:
        text = card["oracle_text"].casefold()
        if "basic" in card["type_line"].casefold() or ANY_NUMBER in text:
            return float("inf")
        up_to = UP_TO.search(text)
        if up_to:
            word = up_to.group(1)
            return int(word) if word.isdigit() else NUMBER_WORDS.get(word, 1)
        return 1

    front = commander["type_line"].split(" // ")[0]
    can_lead = ("Legendary" in front and "Creature" in front) or ("can be your commander" in commander["oracle_text"])
    checks = {
        "singleton": [
            e["card"]["name"]
            for e in entries
            if e["count"] > copies_allowed(e["card"]) or e["card"]["name"] == commander["name"]
        ],
        "color_identity": [e["card"]["name"] for e in looked if set(e["card"]["color_identity"]) - identity],
        "commander_legality": [
            card["name"] for card in [commander, *(e["card"] for e in looked)] if card["commander_legality"] != "legal"
        ],
        "commander": [] if can_lead else [commander["name"]],
    }
    game_changers = {card["name"] for card in [commander, *(e["card"] for e in looked)] if card["game_changer"]}
    target = deck["template"]["bracket_target"]
    lowest = lowest_bracket(len(game_changers))
    # Bracket 1 differs from 2 by intent, not by count, so a target of 1 is judged as 2.
    judged = max(target, 2)
    allowed = bracket_rules()[judged].get("max_game_changers")
    counted = {
        "template": deck["template"]["name"],
        "commander": commander["name"],
        "deck_size": deck["template"]["deck_size"],
        "total": 1 + sum(e["count"] for e in entries),
        "categories": categories,
        "checks": {k: sorted(set(v), key=by_name) for k, v in checks.items()},
        "bracket": {
            "target": target,
            "lowest": lowest,
            "game_changers": sorted(game_changers, key=by_name),
            "over": lowest > judged,
            **({} if allowed is None else {"game_changers_allowed": allowed}),
        },
        "player_text": sorted((e["card"]["name"] for e in entries if e.get("from_player")), key=by_name),
    }
    if deck.get("name"):
        counted["name"] = deck["name"]
    if "not_owned" in deck:
        counted["not_owned"] = deck["not_owned"]
    if available is not None:
        counted["ownership"] = ownership(deck, available)
    return counted


def ownership(deck: dict, available: dict) -> dict:
    """Each recorded card's copies owned, up to those available to this deck, and not owned, the rest.

    The marks are computed, never stored, so removing copies takes the not-owned ones first and a new
    collection or binder filter moves them at the next command.
    """
    have = {matching_key(c["name"]): c["available"] for c in available["cards"]}
    cards = []
    for e in sorted(deck["cards"], key=lambda e: by_name(e["card"]["name"])):
        # A card from the player's text may be recorded under a face name or another spelling.
        available_copies = max((have.get(matching_key(n), 0) for n in names_of(e["card"])), default=0)
        owned = min(e["count"], available_copies)
        cards.append({"name": e["card"]["name"], "owned": owned, "not_owned": e["count"] - owned})
    return {"owned": sum(c["owned"] for c in cards), "not_owned": sum(c["not_owned"] for c in cards), "cards": cards}


def bracket_rules() -> dict[int, dict]:
    """Each bracket's rule from brackets.toml; a bracket the file does not list follows the next lower one."""
    rules = tomllib.loads((HERE / "brackets.toml").read_text(encoding="utf-8"))
    listed = {b["bracket"]: b for b in rules["brackets"]}
    by_bracket, last = {}, listed[min(listed)]
    for bracket in range(1, 6):
        last = listed.get(bracket, last)
        by_bracket[bracket] = last
    return by_bracket


def lowest_bracket(game_changers: int) -> int:
    rules = bracket_rules()
    return next(b for b in range(2, 6) if game_changers <= rules[b].get("max_game_changers", game_changers))


# The page ------------------------------------------------------------------------------


def text(value) -> str:
    return html.escape(str(value), quote=False)


def decklist(deck: dict) -> str:
    rows = [
        f"{e['count']} {e['card']['name']}" for e in sorted(deck["cards"], key=lambda e: by_name(e["card"]["name"]))
    ]
    return "\n".join(["// COMMANDER", f"1 {deck['commander']['name']}", "", "// MAINBOARD", *rows])


def render_page(deck: dict, available: dict | None = None) -> str:
    counted = tally(deck, available)
    copies = {e["card"]["name"]: e["count"] for e in deck["cards"]}
    flagged = {name for names in counted["checks"].values() for name in names} | set(
        counted["bracket"]["game_changers"]
    )
    player_text = set(counted["player_text"])

    def card_row(name: str) -> str:
        marks = []
        if name in flagged:
            marks.append('<span class="mark flag">flagged</span>')
        if name in player_text:
            marks.append('<span class="mark own">player text</span>')
        return f'<li><span class="n">{copies[name]}</span> {text(name)} {"".join(marks)}</li>'

    categories = []
    for row in counted["categories"]:
        state = "done" if row["count"] >= row["target"] else "open"
        filled = min(100, 100 * row["count"] // max(1, row["target"]))
        cards = "".join(card_row(name) for name in row["cards"]) or '<li class="empty">No cards yet</li>'
        categories.append(
            f'<section class="category {state}" data-category="{html.escape(row["name"])}">'
            f'<h3>{text(row["name"])} <span class="count">{row["count"]} / {row["target"]}</span></h3>'
            f'<p class="when">Counts when {text(row["counts_when"])}.</p>'
            f'<div class="bar"><span style="width:{filled}%"></span></div>'
            f"<ul>{cards}</ul></section>"
        )

    size, total = counted["deck_size"], counted["total"]
    if total > size:
        standing = f"{total - size} over the deck size"
    elif total < size:
        standing = f"{size - total} to go"
    else:
        standing = "complete"

    labels = {
        "singleton": "More than one copy",
        "color_identity": "Outside the commander's colour identity",
        "commander_legality": "Not legal in this format",
        "commander": "Cannot be a commander",
    }
    checks = [
        f"<li><strong>{labels[key]}:</strong> {text(', '.join(names))}</li>"
        for key, names in counted["checks"].items()
        if names
    ]
    if counted["player_text"]:
        unchecked = text(", ".join(counted["player_text"]))
        checks.append(f"<li><strong>From the player's text, not checked:</strong> {unchecked}</li>")
    bracket = counted["bracket"]
    changers = text(", ".join(bracket["game_changers"])) if bracket["game_changers"] else "none"
    from_player = ", ".join(counted["player_text"])

    theme = "".join(
        f'<section class="card"><h2>{heading}</h2><p data-section="{key}">{text(deck[key])}</p></section>'
        for key, heading in (("theme", "Theme"), ("plan", "Plan"))
        if deck.get(key)
    )
    owned = ""
    if "ownership" in counted:
        o = counted["ownership"]
        rows = "".join(
            f"<li>{text(c['name'])}: {c['owned']} owned, {c['not_owned']} not owned</li>"
            for c in o["cards"]
            if c["not_owned"]
        )
        owned = (
            f'<section class="card" data-section="ownership"><h2>Owned and not owned</h2><ul>{rows}'
            f"<li><strong>Total:</strong> {o['owned']} owned, {o['not_owned']} not owned</li></ul></section>"
        )

    fills = {
        "name_section": f'<p class="sub" data-section="name">{text(deck["name"])}</p>' if deck.get("name") else "",
        "theme_section": theme,
        "ownership_section": owned,
        "title": text(deck["name"] if deck.get("name") else f"{counted['commander']} · {counted['template']}"),
        "commander": text(counted["commander"]),
        "identity": text("".join(deck["commander"]["color_identity"]) or "colourless"),
        "template": text(counted["template"]),
        "total": f"{total} / {size}",
        "standing": text(standing),
        "categories": "".join(categories),
        "checks": "".join(checks) or "<li>Every card passes.</li>",
        "bracket_over": " · over the target" if bracket["over"] else "",
        "bracket_target": str(bracket["target"]),
        "bracket_lowest": str(bracket["lowest"]),
        "bracket_state": "over" if bracket["over"] else "within",
        "game_changers": changers,
        "player_text": text(from_player) if from_player else "None: every card was looked up.",
        "decklist": text(decklist(deck)),
    }
    page = (HERE / "page.html").read_text(encoding="utf-8")
    return re.sub(r"\{\{(\w+)\}\}", lambda m: fills[m.group(1)], page)


# Commands ------------------------------------------------------------------------------


def run(args) -> str | None:
    deck_path = Path(args.deck or "deck.json")
    looks_up = args.command in ("lookup", "new", "collection") or (args.command == "add" and args.from_player is None)
    # The cache, the collection and the decks belong to the working folder, so every deck shares them.
    scryfall = Scryfall(
        Path(os.environ.get("DECKWRIGHT_CACHE") or "deckwright-cache"),
        fresh=looks_up,
        download=looks_up or args.command in ("read", "judge", "available"),
    )

    if args.command == "lookup":
        try:
            return as_json([scryfall.lookup(name) for name in args.names])
        except Unreachable as failure:
            raise Failure(f"{failure} Ask the player for the card's type line and text.", failure.code) from None

    if args.command == "new":
        if args.name is not None:
            deck_path = DECKS / f"{file_key(args.name)}.json"
            if deck_path.exists():
                raise Failure(
                    f"The name {args.name!r} is taken: {deck_path} already exists. "
                    "Carry on with that deck, or choose another name.",
                    2,
                )
        deck = {"template": load_template(args.template), "commander": looked_up(scryfall, args.commander), "cards": []}
        if args.name is not None:
            deck = {"name": args.name, **deck}
        counted = tally(deck, deck_availability(deck, scryfall))
        deck_path.parent.mkdir(exist_ok=True)
        write_deck(deck_path, deck)
        return as_json({"file": deck_path.as_posix(), **counted})

    if args.command == "decks":
        listed = []
        for path in sorted(DECKS.glob("*.json")):
            deck = read_deck(path)
            listed.append(
                {"name": deck.get("name") or path.stem, "file": path.as_posix(), "commander": deck["commander"]["name"]}
            )
        return as_json(listed)

    if args.command == "collection":
        handed = Path(args.file)
        try:
            data = handed.read_bytes()
        except OSError as error:
            raise Failure(f"The collection file cannot be read: {error.strerror or error}.", 2) from None
        _, report = read_collection(data, scryfall)
        shutil.rmtree(COLLECTION, ignore_errors=True)
        COLLECTION.mkdir()
        (COLLECTION / handed.name).write_bytes(data)
        return as_json(report)

    if args.command == "available":
        deck = read_deck(deck_path) if args.deck else None
        if kept_collection() is None:
            raise Failure("No collection is kept: hand one over with collection FILE.", 2)
        if args.default or args.include or args.exclude:
            binders = {} if args.default else {"include": args.include or [], "exclude": args.exclude or []}
            copies, _ = read_collection(kept_collection().read_bytes(), scryfall)
            known = sorted({c["binder"] for c in copies if c["binder"]})
            unknown = [b for b in [*binders.get("include", []), *binders.get("exclude", [])] if b not in known]
            if unknown:
                listed = ", ".join(known) or "none: a list of lines has no binders"
                raise Failure(f"The collection has no binder {unknown[0]!r}. Its binders: {listed}.", 2)
            if deck is None:
                deck = {"binders": binders}
            else:
                deck["binders"] = binders
                write_deck(deck_path, deck)
        return as_json(deck_availability(deck, scryfall))

    deck = read_deck(deck_path)
    try:
        return changed(args, deck, deck_path, scryfall)
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        raise Failure(
            f"The deck file {deck_path} is not a readable deck ({error!r}). Start a new one with new.", 2
        ) from None


def changed(args, deck: dict, deck_path: Path, scryfall: Scryfall) -> str | None:
    """Runs a command on a read deck, writing the deck only when the command and its tally succeed."""
    if args.command == "tally":
        return as_json(tally(deck, deck_availability(deck, scryfall)))
    if args.command == "page":
        out = Path(args.out) if args.out else deck_path.with_suffix(".html")
        if not out.parent.is_dir():
            raise Failure(f"There is no folder {out.parent} to write the page to.", 2)
        out.write_text(render_page(deck, deck_availability(deck, scryfall)), encoding="utf-8")
        return f"Wrote {out}\n"
    if args.command == "read":
        return as_json(narrowing(deck, scryfall))
    if args.command == "judge":
        return judge(deck, deck_path, scryfall, args.judgements)

    if args.command in ("theme", "plan"):
        deck[args.command] = args.text
    elif args.command == "not-owned":
        deck["not_owned"] = args.answer == "yes"
    elif args.command == "add":
        add(deck, scryfall, args)
    elif args.command == "remove":
        if args.count is not None:
            at_least(1, args.count, "--count")
        entry = recorded(deck, args.name)
        if entry is None:
            raise Failure(f"{args.name!r} is not in the deck.", 2)
        entry["count"] -= entry["count"] if args.count is None else args.count
        if entry["count"] <= 0:
            deck["cards"].remove(entry)
    elif args.command == "target":
        (name,) = category_names(deck, [args.category])
        at_least(0, args.n, "A target")
        next(c for c in deck["template"]["categories"] if c["name"] == name)["target"] = args.n
    elif args.command == "bracket":
        if not 1 <= args.n <= 5:
            raise Failure("A bracket is 1 to 5.", 2)
        deck["template"]["bracket_target"] = args.n

    counted = as_json(tally(deck, deck_availability(deck, scryfall)))
    write_deck(deck_path, deck)
    return counted


def add(deck: dict, scryfall: Scryfall, args) -> None:
    categories = category_names(deck, args.category or [])
    at_least(1, args.count, "--count")
    if args.from_player is not None:
        card = player_card(args.name, args.from_player, args.type_line or "")
    else:
        try:
            card = looked_up(scryfall, args.name)
        except Unreachable as failure:
            raise Failure(
                f"{failure} Ask the player for the card's type line and text, and add it with "
                "--from-player TEXT --type-line LINE.",
                failure.code,
            ) from None
        if args.category is None:
            categories = deck.get("judgements", {}).get(card["name"], {}).get("categories", [])
    entry = next((e for name in names_of(card) if (e := recorded(deck, name))), None)
    if entry is None:
        entry = {"card": card, "count": 0, "categories": []}
        deck["cards"].append(entry)
    if args.from_player is not None:
        entry.setdefault("from_player", entry["count"] == 0)
    elif entry.pop("from_player", False):
        entry["card"] = card
    entry["count"] += args.count
    entry["categories"] = category_names(deck, [*entry["categories"], *categories])
    deck["cards"].sort(key=lambda e: by_name(e["card"]["name"]))


def judge(deck: dict, deck_path: Path, scryfall: Scryfall, given: str) -> str:
    """Records the read's judgements for cards in this deck's narrowing; one bad entry records none."""
    try:
        judgements = json.loads(given)
        if not isinstance(judgements, list) or not all(isinstance(j, dict) and "name" in j for j in judgements):
            raise ValueError("expected a list of {name, categories, serves_theme}")
    except ValueError as error:
        raise Failure(f"The judgements are not readable ({error}).", 2) from None
    cards = narrowing(deck, scryfall)["cards"]
    read = {matching_key(n): e["name"] for e in cards for n in names_of(e["card"])}
    kept = deck.setdefault("judgements", {})
    for j in judgements:
        name = read.get(matching_key(j["name"]))
        if name is None:
            raise Failure(f"{j['name']!r} is not in this deck's read. Nothing was recorded.", 2)
        # A field left out keeps what was judged before, so a new theme is judged without the categories.
        judgement = kept.get(name, {}) | {"categories": kept.get(name, {}).get("categories", [])}
        if "categories" in j:
            judgement["categories"] = category_names(deck, j["categories"] or [])
        if "serves_theme" in j:
            judgement["serves_theme"] = bool(j["serves_theme"])
        kept[name] = judgement
    write_deck(deck_path, deck)
    return as_json({"unjudged": sum(1 for e in cards if e["name"] not in kept), "judged": len(kept)})


def at_least(lowest: int, n: int, what: str) -> None:
    if n < lowest:
        raise Failure(f"{what} must be at least {lowest}.", 2)


def as_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def parser() -> argparse.ArgumentParser:
    top = argparse.ArgumentParser(prog="deck.py", description=__doc__.splitlines()[0])
    commands = top.add_subparsers(dest="command", required=True)

    def command(name: str, help: str) -> argparse.ArgumentParser:
        sub = commands.add_parser(name, help=help, description=help)
        sub.add_argument(
            "--deck", default=None, help="the deck file (default ./deck.json; a named deck is decks/<name>.json)"
        )
        return sub

    lookup = command("lookup", "Look cards up; prints each card's fixed fields as JSON.")
    lookup.add_argument("names", nargs="+", metavar="NAME")

    new = command("new", "Start a deck file from a template, with its commander.")
    new.add_argument("--template", required=True)
    new.add_argument("--commander", required=True)
    new.add_argument("--name", help="the deck's name: writes decks/<name>.json, and never over a deck that exists")

    command("decks", "List the named decks in decks/, with their commanders.")

    collection = command(
        "collection", "Keep the player's collection (a ManaBox CSV export or N Name lines); prints a report."
    )
    collection.add_argument("file", metavar="FILE")

    available = command("available", "Print the copies owned and available, and those held back per binder.")
    available.add_argument("--include", action="append", metavar="BINDER", help="make a deck binder's copies available")
    available.add_argument("--exclude", action="append", metavar="BINDER", help="hold a binder's copies back")
    available.add_argument("--default", action="store_true", help="drop the deck's filter: only deck binders held back")

    command("read", "Print the narrowing: available cards this deck can use, with their judgements.")
    judge_command = command("judge", "Record the read's judgements: a JSON list of {name, categories, serves_theme}.")
    judge_command.add_argument("judgements", metavar="JSON")
    command("theme", "Set the deck's theme, in the player's words.").add_argument("text", metavar="TEXT")
    command("plan", "Set the deck's plan, one sentence.").add_argument("text", metavar="TEXT")
    command("not-owned", "Record the player's answer: build this deck with cards they don't own?").add_argument(
        "answer", choices=["yes", "no"]
    )

    add_command = command("add", "Record a card the player said yes to.")
    add_command.add_argument("name", metavar="NAME")
    add_command.add_argument("--count", type=int, default=1)
    add_command.add_argument(
        "--category", nargs="+", action="extend", metavar="C", help="where it counts (default: the read's categories)"
    )
    add_command.add_argument("--from-player", metavar="TEXT", help="the card's text as the player gave it; no lookup")
    add_command.add_argument(
        "--type-line", metavar="LINE", help="with --from-player: the card's type line as the player gave it"
    )

    remove = command("remove", "Take copies of a card out (all of them unless --count).")
    remove.add_argument("name", metavar="NAME")
    remove.add_argument("--count", type=int)

    target = command("target", "Change one category's target.")
    target.add_argument("category", metavar="CATEGORY")
    target.add_argument("n", type=int, metavar="N")

    bracket = command("bracket", "Change the deck's bracket target.")
    bracket.add_argument("n", type=int, metavar="N")

    command("tally", "Count the deck against the template; prints JSON.")

    page = command("page", "Render the deck page.")
    page.add_argument("--out", metavar="FILE", help="where to write it (default: beside the deck file, named after it)")
    return top


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    args = parser().parse_args()
    try:
        output = run(args)
    except Failure as failure:
        print(failure, file=sys.stderr)
        return failure.code
    if output:
        sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
