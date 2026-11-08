"""AC11, C35: no price in any command's output, the deck file, the page or the decklist, a
collection given or not; no price in the fixtures.

The stand-in Scryfall adds prices, purchase links and image links to every card it serves, in the
bulk file as on `cards/named`, as the real one does; and the collection handed over here carries a
purchase price on every row, as the owner's export does. So these prove the script drops them
rather than never seeing them. The CSV is built here, never kept as a fixture.
"""

from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path

from conftest import MANABOX, MANABOX_HEADER, PRICE_KEYS, ROOT, manabox_csv, write_file

PRICE_WORDS = re.compile(r"price|purchase", re.I)
FIXTURE_KEYS = re.compile(r"price|purchase|image|tcgplayer|cardmarket", re.I)
PRICE_VALUES = [v for group in PRICE_KEYS.values() for v in group.values()]


def keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from keys(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from keys(v)


def assert_priceless(text: str, where: str):
    assert not PRICE_WORDS.search(text), f"{where} mentions a price or purchase"
    for value in PRICE_VALUES:
        assert value not in text, f"{where} carries {value!r} from Scryfall's price or link fields"
    assert not re.search(r"[$€£]\s?\d", text), f"{where} shows an amount of money"


def test_no_prices(deck, unreachable_url):
    names = ["Sol Ring", "Vampiric Tutor", "Bloodline Keeper", "Meren of Clan Nel Toth"]
    out = deck.run("lookup", *names).stdout
    assert_priceless(out, "lookup output")
    for k in keys(json.loads(out)):
        assert not FIXTURE_KEYS.search(k), f"lookup output has key {k!r}"

    deck.new()
    deck.add("Sol Ring", "Ramp")
    deck.add("Vampiric Tutor", "Plan")
    deck.add("Bloodline Keeper", "Plan")
    deck.add("Swamp", count=20)
    deck.run("add", "Homebrew Owl", "--from-player", "Flying.", "--category", "Plan", api=unreachable_url)

    deck_text = deck.deck_file.read_text(encoding="utf-8")
    assert_priceless(deck_text, "deck.json")
    for k in keys(json.loads(deck_text)):
        assert not FIXTURE_KEYS.search(k), f"deck.json has key {k!r}"

    assert_priceless(deck.run("tally").stdout, "tally output")
    assert_priceless(deck.page(), "the page")

    for cached in sorted((deck.cwd / "deckwright-cache").glob("*.json")):
        assert_priceless(cached.read_text(encoding="utf-8"), f"cache file {cached.name}")


# The price on each row of the collection below, and its currency.
ROW_PRICE = "543.21"


def priced_collection() -> bytes:
    """manabox.csv with a purchase price on every row."""
    rows = list(csv.DictReader(io.StringIO(MANABOX.read_text(encoding="utf-8"), newline="")))
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=MANABOX_HEADER.split(","), lineterminator="\r\n")
    for row in rows:
        writer.writerow({**row, "Purchase price": ROW_PRICE})
    return manabox_csv(*out.getvalue().split("\r\n")[:-1])


def test_no_prices_collection(deck, tmp_path):
    player = tmp_path / "player"
    player.mkdir()
    outputs = {"collection": deck.run("collection", str(write_file(player, "export.csv", priced_collection()))).stdout}
    built = deck.named("Bat Drain")
    outputs["available"] = built.run("available").stdout
    outputs["read"] = built.run("read").stdout
    outputs["judge"] = built.judge([{"name": "Starscape Cleric", "categories": ["Plan"], "serves_theme": True}]).stdout
    outputs["theme"] = built.run("theme", "Bats").stdout
    outputs["plan"] = built.run("plan", "Drain with bats.").stdout
    outputs["add"] = built.add("Starscape Cleric", count=8).stdout
    outputs["add not owned"] = built.add("Vampiric Tutor", "Plan", count=2).stdout
    outputs["remove"] = built.run("remove", "Starscape Cleric", "--count", "1").stdout
    outputs["tally"] = built.run("tally").stdout
    outputs["decks"] = deck.run("decks").stdout
    outputs["page"] = built.page()
    outputs["deck file"] = built.deck_file.read_text(encoding="utf-8")

    for where, text in outputs.items():
        assert_priceless(text, f"{where} output")
        assert ROW_PRICE not in text, f"{where} carries the collection's purchase price"
    for where in ("collection", "available", "read", "judge", "tally", "decks", "deck file"):
        for k in keys(json.loads(outputs[where])):
            assert not FIXTURE_KEYS.search(k), f"{where} has key {k!r}"
    for path in sorted(deck.cwd.rglob("*.json")):
        text = path.read_text(encoding="utf-8")
        assert_priceless(text, str(path.relative_to(deck.cwd)))
        assert ROW_PRICE not in text


PRICE_COLUMNS = re.compile(r"price", re.I)


def assert_csv_priceless(path: Path):
    """A CSV fixture may name ManaBox's price columns in its header, but every price cell is blank
    and nothing else mentions a price."""
    rows = list(csv.reader(io.StringIO(path.read_text(encoding="utf-8"), newline="")))
    header, body = rows[0], rows[1:]
    price_columns = [i for i, column in enumerate(header) if PRICE_COLUMNS.search(column) and "currency" not in column]
    for n, row in enumerate(body, 2):
        for i in price_columns:
            assert not row[i].strip(), f"{path.relative_to(ROOT)} row {n} has a {header[i]!r}"
        others = ",".join(cell for i, cell in enumerate(row) if i not in price_columns)
        assert not PRICE_WORDS.search(others), f"{path.relative_to(ROOT)} row {n} mentions a price or purchase"
        assert not re.search(r"[$€£]\s?\d", others), f"{path.relative_to(ROOT)} row {n} shows an amount of money"


def _fixture_files():
    roots = [ROOT / "tests" / "fixtures", *sorted((ROOT / "evals").glob("*/fixture"))]
    for root in roots:
        for path in sorted(Path(root).rglob("*")):
            if path.is_file():
                yield path


def test_no_prices_in_fixtures():
    files = list(_fixture_files())
    assert any(p.suffix == ".json" for p in files), "the recorded responses are missing"
    assert any(p.suffix == ".csv" for p in files), "the collection fixtures are missing"
    for path in files:
        if path.suffix == ".csv":
            assert_csv_priceless(path)
            continue
        text = path.read_text(encoding="utf-8")
        assert not PRICE_WORDS.search(text), f"{path.relative_to(ROOT)} mentions a price or purchase"
        if path.suffix == ".json":
            for k in keys(json.loads(text)):
                assert not FIXTURE_KEYS.search(k), f"{path.relative_to(ROOT)} has key {k!r}"
