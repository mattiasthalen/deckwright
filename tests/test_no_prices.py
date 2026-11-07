"""AC11: no price in a lookup's fields, the deck file, the page or the decklist; no price in the fixtures.

The stand-in Scryfall adds prices, purchase links and image links to every card it serves,
as the real one does, so this proves the script drops them rather than never seeing them.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from conftest import PRICE_KEYS, ROOT

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


def _fixture_files():
    roots = [ROOT / "tests" / "fixtures", *sorted((ROOT / "evals").glob("*/fixture"))]
    for root in roots:
        for path in sorted(Path(root).rglob("*")):
            if path.is_file():
                yield path


def test_no_prices_in_fixtures():
    files = list(_fixture_files())
    assert any(p.suffix == ".json" for p in files), "the recorded responses are missing"
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert not PRICE_WORDS.search(text), f"{path.relative_to(ROOT)} mentions a price or purchase"
        if path.suffix == ".json":
            for k in keys(json.loads(text)):
                assert not FIXTURE_KEYS.search(k), f"{path.relative_to(ROOT)} has key {k!r}"
