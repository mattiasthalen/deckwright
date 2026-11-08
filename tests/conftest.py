"""Harness for the deck.py tests: a stand-in Scryfall, a runner for the script, and a reader for the page.

The tests treat deck.py as a black box behind its command line. tests/README.md is the
contract they hold it to; every name used here that the plan leaves open is fixed there.
The stand-in serves both what S1's script asked for (`cards/named`) and what the bulk lookups
ask for (`/bulk-data` and the Default Cards file it lists), so the same harness runs the S1
tests at 017a7a0 and every test at head.
"""

from __future__ import annotations

import copy
import gzip
import hashlib
import html
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

ROOT = Path(__file__).resolve().parent.parent
# DECKWRIGHT_SKILL_DIR points the suite at another copy of the skill, such as a candidate build
# kept outside the repo; by default it is the skill in this repo.
SKILL_DIR = Path(os.environ.get("DECKWRIGHT_SKILL_DIR") or ROOT / "plugins" / "deckwright" / "skills" / "interview")
SCRIPT = SKILL_DIR / "deck.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
RECORDED = FIXTURES / "scryfall"

COMMANDER = "Meren of Clan Nel Toth"
CATEGORIES = [
    ("Lands", 38),
    ("Ramp", 10),
    ("Card advantage", 12),
    ("Targeted disruption", 12),
    ("Mass disruption", 6),
    ("Plan", 30),
]
CARD_FIELDS = {
    "name",
    "mana_cost",
    "type_line",
    "oracle_text",
    "color_identity",
    "commander_legality",
    "game_changer",
}

EXIT_USAGE = 2
EXIT_UNREACHABLE = 3
EXIT_NOT_RECORDED = 4

# Where the bulk file lives, as tests/README.md fixes it.
BULK_FILE = "default-cards.jsonl.gz"
WEEK = 7 * 24 * 3600
# The Default Cards file as the stand-in's /bulk-data lists it, and the Oracle Cards file listed
# before it, which a script that took the first entry would fetch instead.
BULK_PATH = "/default-cards/default-cards-20261108100757.jsonl.gz"
DECOY_PATH = "/oracle-cards/oracle-cards-20261108100316.jsonl.gz"

# Real Scryfall answers carry these; the recordings had them stripped, so the stand-in puts
# them back to prove the script drops them.
PRICE_KEYS = {
    "prices": {"usd": "987.65", "usd_foil": "1234.56", "eur": "876.54", "tix": "12.34"},
    "purchase_uris": {"tcgplayer": "https://shop.example/purchase/1"},
    "image_uris": {"normal": "https://img.example/card.jpg"},
}


def load_recorded() -> dict[tuple[str, str], tuple[int, dict]]:
    """Every recorded `cards/named` request, keyed by (mode, query casefolded)."""
    recorded = {}
    for path in sorted(RECORDED.glob("named-*.json")):
        rec = json.loads(path.read_text(encoding="utf-8"))
        recorded[(rec["mode"], rec["q"].casefold())] = (rec["status"], rec["body"])
    return recorded


def scryfall_card(name: str) -> dict:
    """The recorded Scryfall card object for an exact-name request."""
    status, body = load_recorded()[("exact", name.casefold())]
    assert status == 200, f"no recorded card for {name!r}"
    return body


def bulk_cards() -> list[dict]:
    """Every card object the stand-in's Default Cards file holds: each recorded `cards/named` card,
    and each printing in `printing-*.json`, once per Scryfall ID. Like the real file, it holds every
    printing it has, tokens included."""
    by_id: dict[str, dict] = {}
    for status, body in load_recorded().values():
        if status == 200:
            by_id[body["id"]] = body
    for path in sorted(RECORDED.glob("printing-*.json")):
        card = json.loads(path.read_text(encoding="utf-8"))
        by_id[card["id"]] = card
    return list(by_id.values())


def printing(set_code: str, collector_number: str) -> dict:
    """One printing's card object, from `printing-<set>-<collector number>.json`."""
    return json.loads((RECORDED / f"printing-{set_code}-{collector_number}.json").read_text(encoding="utf-8"))


def jsonl_gz(cards: list[dict]) -> bytes:
    """A Default Cards file as Scryfall serves it: gzip-compressed JSON Lines, prices included."""
    lines = "".join(json.dumps(with_prices(card), ensure_ascii=False) + "\n" for card in cards)
    return gzip.compress(lines.encode("utf-8"), mtime=0)


def place_bulk(cache: Path, cards: list[dict] | None = None, age: float = 0.0) -> Path:
    """Puts a Default Cards file in a cache folder, `age` seconds old by its modification time."""
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / BULK_FILE
    path.write_bytes(jsonl_gz(bulk_cards() if cards is None else cards))
    if age:
        then = time.time() - age
        os.utime(path, (then, then))
    return path


def file_key(name: str) -> str:
    """The cache's key rule (tests/README.md), which also names a deck's files."""
    key = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if not key or not name.isascii():
        digest = hashlib.sha256(name.casefold().encode("utf-8")).hexdigest()[:12]
        key = f"{key}-{digest}" if key else digest
    return key


def with_prices(card: dict) -> dict:
    priced = copy.deepcopy(card)
    priced.update(copy.deepcopy(PRICE_KEYS))
    for face in priced.get("card_faces", []):
        face["image_uris"] = copy.deepcopy(PRICE_KEYS["image_uris"])
    return priced


@dataclass
class Request:
    at: float
    path: str
    query: dict[str, list[str]]
    headers: dict[str, str]


@dataclass
class FakeScryfall:
    """A local stand-in for api.scryfall.com and data.scryfall.io that serves only the recorded responses.

    The API (`url`) answers `/bulk-data` with a listing whose `default_cards` entry points at the
    data host (`data_url`), a second server, so a script must follow the listed URI; and it answers
    `cards/named` from the recordings, as S1's script asked. The data host serves the Default Cards
    file built from `bulk` (every recorded card and printing, unless a test narrows it).

    `refuse = True` makes both hosts answer like a proxy that blocks them: 403 and an HTML body.
    `limit = True` makes both answer as Scryfall does past its rate limit: 429 and an error object.
    `cards_refused = True` makes every `/cards/…` request a 500: a lookup must not need one.
    `cut_off = True` makes the data host send half the file under the whole file's length and hang up.
    An unrecorded request gets a 500, which a correct script reports as unreachable (exit 3),
    so a test that trips one fails loudly rather than seeing a made-up answer.
    """

    url: str = ""
    data_url: str = ""
    requests: list[Request] = field(default_factory=list)
    data_requests: list[Request] = field(default_factory=list)
    refuse: bool = False
    limit: bool = False
    cards_refused: bool = False
    cut_off: bool = False
    bulk: list[dict] = field(default_factory=bulk_cards)
    unrecorded: list[str] = field(default_factory=list)

    @property
    def card_requests(self) -> list[Request]:
        return [r for r in self.requests if r.path.startswith("/cards")]

    @property
    def downloads(self) -> list[Request]:
        return [r for r in self.data_requests if r.path == BULK_PATH]

    def listing(self) -> dict:
        def entry(kind: str, name: str, path: str) -> dict:
            return {
                "object": "bulk_data",
                "type": kind,
                "name": name,
                "updated_at": "2026-11-08T10:07:57.464+00:00",
                "jsonl_download_uri": self.data_url + path,
                "content_type": "application/gzip",
            }

        return {
            "object": "list",
            "has_more": False,
            "data": [
                entry("oracle_cards", "Oracle Cards", DECOY_PATH),
                entry("default_cards", "Default Cards", BULK_PATH),
                entry("all_cards", "All Cards", "/all-cards/all-cards-20261108102418.jsonl.gz"),
            ],
        }


def _serve(fake: FakeScryfall, recorded):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            parts = urlsplit(self.path)
            query = parse_qs(parts.query)
            fake.requests.append(
                Request(time.monotonic(), parts.path, query, {k.lower(): v for k, v in self.headers.items()})
            )
            if fake.refuse:
                return self._send(403, b"<html><body>Blocked by proxy</body></html>", "text/html")
            if fake.limit:
                body = b'{"object":"error","status":429,"details":"Too many requests"}'
                return self._send(429, body, "application/json")
            if parts.path == "/bulk-data":
                return self._send(200, json.dumps(fake.listing()).encode(), "application/json")
            if fake.cards_refused and parts.path.startswith("/cards"):
                return self._send(500, b'{"object":"error","status":500}', "application/json")
            mode = "exact" if "exact" in query else "fuzzy" if "fuzzy" in query else None
            if parts.path != "/cards/named" or mode is None:
                fake.unrecorded.append(self.path)
                return self._send(500, b'{"object":"error","status":500}', "application/json")
            key = (mode, query[mode][0].casefold())
            if key not in recorded:
                fake.unrecorded.append(self.path)
                return self._send(500, b'{"object":"error","status":500}', "application/json")
            status, body = recorded[key]
            if status == 200:
                body = with_prices(body)
            self._send(status, json.dumps(body).encode(), "application/json")

        def _send(self, status, payload, ctype):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    return Handler


def _serve_data(fake: FakeScryfall):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            parts = urlsplit(self.path)
            fake.data_requests.append(
                Request(time.monotonic(), parts.path, {}, {k.lower(): v for k, v in self.headers.items()})
            )
            if fake.refuse:
                return self._send(403, b"<html><body>Blocked by proxy</body></html>", "text/html")
            if fake.limit:
                return self._send(429, b'{"object":"error","status":429}', "application/json")
            if parts.path != BULK_PATH:
                fake.unrecorded.append(self.path)
                return self._send(500, b"", "text/plain")
            payload = jsonl_gz(fake.bulk)
            if not fake.cut_off:
                return self._send(200, payload, "application/gzip")
            self.send_response(200)
            self.send_header("Content-Type", "application/gzip")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload[: len(payload) // 2])
            self.wfile.flush()
            self.close_connection = True

        def _send(self, status, payload, ctype):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    return Handler


@pytest.fixture
def scryfall():
    fake = FakeScryfall()
    servers = [
        ThreadingHTTPServer(("127.0.0.1", 0), _serve(fake, load_recorded())),
        ThreadingHTTPServer(("127.0.0.1", 0), _serve_data(fake)),
    ]
    fake.url, fake.data_url = (f"http://127.0.0.1:{server.server_address[1]}" for server in servers)
    for server in servers:
        threading.Thread(target=server.serve_forever, daemon=True).start()
    yield fake
    for server in servers:
        server.shutdown()
        server.server_close()


@pytest.fixture
def unreachable_url() -> str:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return f"http://127.0.0.1:{port}"


# Commands that act on one deck file, and so take `--deck PATH` after the command.
DECK_COMMANDS = {"add", "remove", "target", "bracket", "tally", "page", "read", "judge", "theme", "plan", "available"}


class Deckwright:
    """Runs deck.py as the skill does, in one working folder, against one Scryfall URL.

    `deck_path`, when set, is given as `--deck` to every command that acts on a deck, so a test can
    drive a named deck in `decks/` with the same calls as S1's `./deck.json`.

    A call given another Scryfall URL than this runner's own (`api=`) runs with an empty cache
    folder of its own, unless the test names one. That is the world the S1 tests mean by "Scryfall
    is out of reach": nothing has ever been fetched. At S1 a card those tests add offline had never
    been looked up; at head the bulk file is cached by the first lookup, and would otherwise answer
    for Scryfall. A test that wants Scryfall out of reach with the cache as it is uses `offline()`.
    """

    def __init__(self, cwd: Path, api: str, script: Path = SCRIPT, deck_path: str | None = None):
        self.cwd = cwd
        self.api = api
        self.script = script
        self.deck_path = deck_path

    def env(self, api: str | None = None, extra: dict | None = None) -> dict:
        env = {
            k: v
            for k, v in os.environ.items()
            if not k.lower().endswith("_proxy") and not k.startswith("DECKWRIGHT_")
        }
        env["NO_PROXY"] = env["no_proxy"] = "127.0.0.1,localhost"
        env["DECKWRIGHT_SCRYFALL_API"] = api or self.api
        if api and api != self.api and "DECKWRIGHT_CACHE" not in (extra or {}):
            port = urlsplit(api).port
            env["DECKWRIGHT_CACHE"] = str(self.cwd.parent / f"never-reached-cache-{port}")
        env.update(extra or {})
        return env

    def offline(self, api: str) -> Deckwright:
        """The same working folder, deck and cache, with Scryfall at `api` (out of reach)."""
        return Deckwright(self.cwd, api, self.script, self.deck_path)

    def using(self, deck_path: str | None) -> Deckwright:
        """The same working folder and Scryfall, acting on another deck file."""
        return Deckwright(self.cwd, self.api, self.script, deck_path)

    def run(self, *args: str, api: str | None = None, env: dict | None = None, expect: int | None = 0):
        assert self.script.exists(), f"the script is not built yet: {self.script}"
        if self.deck_path and args and args[0] in DECK_COMMANDS and "--deck" not in args:
            args = (args[0], "--deck", self.deck_path, *args[1:])
        proc = subprocess.run(
            [sys.executable, str(self.script), *args],
            cwd=self.cwd,
            env=self.env(api, env),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
        )
        if expect is not None:
            assert proc.returncode == expect, (
                f"deck.py {' '.join(args)} exited {proc.returncode}, expected {expect}\n"
                f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
            )
        return proc

    def json(self, *args: str, **kw):
        return json.loads(self.run(*args, **kw).stdout)

    def new(self, commander: str = COMMANDER, template: str = "commander", name: str | None = None, **kw):
        args = ["new", "--template", template, "--commander", commander]
        if name is not None:
            args += ["--name", name]
        return self.run(*args, **kw)

    def named(self, name: str, commander: str = COMMANDER, **kw) -> Deckwright:
        """Starts a named deck, and returns a runner bound to its file, `decks/<file name>.json`."""
        self.new(commander, name=name, **kw)
        bound = self.using(f"decks/{file_key(name)}.json")
        assert bound.deck_file.is_file(), f"new --name {name!r} should write {bound.deck_path}"
        return bound

    def collection(self, path: str | Path, **kw) -> dict:
        return self.json("collection", str(path), **kw)

    def available(self, *flags: str, **kw) -> dict:
        return self.json("available", *flags, **kw)

    def read(self, **kw) -> dict:
        return self.json("read", **kw)

    def judge(self, judgements: list[dict], **kw):
        return self.run("judge", json.dumps(judgements, ensure_ascii=False), **kw)

    def add(self, name: str, *categories: str, count: int | None = None, **kw):
        args = ["add", name]
        if count is not None:
            args += ["--count", str(count)]
        if categories:
            args += ["--category", *categories]
        return self.run(*args, **kw)

    def tally(self, **kw) -> dict:
        return self.json("tally", **kw)

    def page(self, out: str = "deck.html", **kw) -> str:
        self.run("page", "--out", out, **kw)
        return (self.cwd / out).read_text(encoding="utf-8")

    @property
    def deck_file(self) -> Path:
        return self.cwd / (self.deck_path or "deck.json")

    @property
    def cache(self) -> Path:
        return self.cwd / "deckwright-cache"


@pytest.fixture
def deck(tmp_path, scryfall) -> Deckwright:
    work = tmp_path / "work"
    work.mkdir()
    return Deckwright(work, scryfall.url)


def write_file(folder: Path, name: str, content: str | bytes) -> Path:
    """A file the player hands over, written outside the working folder's own files."""
    path = folder / name
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_bytes(content.encode("utf-8"))
    return path


MANABOX = FIXTURES / "collection" / "manabox.csv"
MANABOX_HEADER = MANABOX.read_bytes().split(b"\r\n", 1)[0].decode("utf-8")


def manabox_row(card: dict, quantity: int | str, binder: str = "Binder", binder_type: str = "binder") -> str:
    """One ManaBox export row for a printing, in the export's column order, its price blank."""
    values = {
        "Binder Name": binder,
        "Binder Type": binder_type,
        "Name": card["name"],
        "Set code": card["set"].upper(),
        "Set name": card.get("set_name", ""),
        "Collector number": card["collector_number"],
        "Foil": "normal",
        "Rarity": card.get("rarity", ""),
        "Quantity": str(quantity),
        "ManaBox ID": "",
        "Scryfall ID": card["id"],
        "Purchase price": "",
        "Misprint": "false",
        "Altered": "false",
        "Condition": "near_mint",
        "Language": "en",
        "Purchase price currency": "SEK",
        "Added": "",
    }
    cells = []
    for column in MANABOX_HEADER.split(","):
        value = values[column]
        cells.append(f'"{value}"' if "," in value or '"' in value else value)
    return ",".join(cells)


def manabox_csv(*rows: str, header: str = MANABOX_HEADER) -> bytes:
    return ("\r\n".join([header, *rows]) + "\r\n").encode("utf-8")


def copy_tree_files(root: Path) -> dict[Path, bytes]:
    """Every file under a folder, with its bytes."""
    return {p: p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def category(tally: dict, name: str) -> dict:
    matches = [c for c in tally["categories"] if c["name"] == name]
    assert len(matches) == 1, f"tally has no single category {name!r}: {tally['categories']}"
    return matches[0]


# The page ------------------------------------------------------------------------------

_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


class _PageReader(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, str | None]] = []
        self.texts: dict[str, list[str]] = {}
        self.open: list[list[str]] = []
        self.scripts: list[dict] = []
        self.buttons = 0
        self.decklist_raw_children = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "script":
            self.scripts.append(attrs)
        if tag == "button":
            self.buttons += 1
        if any(key == "section:decklist" for key, _ in self.stack):
            self.decklist_raw_children += 1
        if tag in _VOID:
            return
        key = None
        if attrs.get("data-section"):
            key = "section:" + attrs["data-section"]
        elif attrs.get("data-category"):
            key = "category:" + attrs["data-category"]
        if key:
            buf: list[str] = []
            self.texts.setdefault(key, []).append(buf)  # type: ignore[arg-type]
            self.open.append(buf)
        self.stack.append((key or "", tag))

    def handle_endtag(self, tag):
        if tag in _VOID:
            return
        while self.stack:
            key, open_tag = self.stack.pop()
            if key:
                self.open.pop()
            if open_tag == tag:
                break

    def handle_data(self, data):
        for buf in self.open:
            buf.append(data)


@dataclass
class Page:
    raw: str
    texts: dict[str, list[str]]
    scripts: list[dict]
    buttons: int
    decklist_children: int

    def one(self, key: str) -> str:
        found = self.texts.get(key, [])
        assert len(found) == 1, f"the page should have exactly one element marked {key!r}, found {len(found)}"
        return found[0]

    def section(self, name: str) -> str:
        return self.one("section:" + name)

    def category(self, name: str) -> str:
        return self.one("category:" + name)


def read_page(raw: str) -> Page:
    reader = _PageReader()
    reader.feed(raw)
    reader.close()
    texts = {k: ["".join(buf) for buf in bufs] for k, bufs in reader.texts.items()}
    return Page(raw, texts, reader.scripts, reader.buttons, reader.decklist_raw_children)


def count_of(text: str, count: int, target: int) -> bool:
    """Whether the text shows `count / target`, as the page and the tally's prose render it."""
    return re.search(rf"(?<!\d){count}\s*/\s*{target}(?!\d)", text) is not None


def escaped(text: str) -> str:
    return html.escape(text, quote=False)
