"""Theme fit on every card: AC8, and P2 (theme fit lives in the deck's judgements).

`add … --serves-theme yes|no` records whether a card serves the deck's theme, with a collection or
without. The fit is kept where the read keeps it, the deck's `judgements` (tests/README.md), so a
deck has one place for it; `measure`'s theme density reads it.
"""

from __future__ import annotations

import json

import pytest
from conftest import (
    EXIT_USAGE,
    MANABOX,
    assert_refused,
    category,
    manabox_csv,
    manabox_row,
    scryfall_card,
    write_file,
)


def fit(deck, name: str):
    """The theme fit kept for a card, or None when none is kept."""
    return deck.stored().get("judgements", {}).get(name, {}).get("serves_theme")


# AC8 ---------------------------------------------------------------------------------


def test_add_records_theme_fit(deck):
    # Without a collection.
    deck.new()
    deck.run("theme", "Rats")
    deck.run("add", "Relentless Rats", "--count", "3", "--serves-theme", "yes")
    deck.run("add", "Sign in Blood", "--serves-theme", "no", "--category", "Card advantage")
    assert fit(deck, "Relentless Rats") is True
    assert fit(deck, "Sign in Blood") is False
    assert "Sign in Blood" in category(deck.tally(), "Card advantage")["cards"], "--category still records"
    # A fit given is not a read: a card with no fit and no category still records on a deck with no collection.
    deck.add("Sol Ring")
    assert deck.tally()["total"] == 1 + 3 + 1 + 1
    assert fit(deck, "Sol Ring") is None, "no fit given and no read: none is made up"
    # A second add with the other answer replaces the fit.
    deck.run("add", "Sign in Blood", "--count", "1", "--serves-theme", "yes")
    assert fit(deck, "Sign in Blood") is True


def test_add_records_theme_fit_with_a_collection(deck):
    deck.collection(MANABOX)
    rats = deck.named("Rat Pack")
    rats.run("theme", "Bloomburrow rats")
    rats.judge([
        {"name": "Nocturnal Hunger", "categories": ["Targeted disruption"], "serves_theme": True},
        {"name": "Feed the Cycle", "categories": ["Targeted disruption"], "serves_theme": True},
        {"name": "Starscape Cleric", "categories": ["Card advantage"], "serves_theme": False},
    ])

    # No flag: the read's judgement is the card's fit, and its categories are used.
    rats.add("Nocturnal Hunger")
    assert fit(rats, "Nocturnal Hunger") is True
    assert "Nocturnal Hunger" in category(rats.tally(), "Targeted disruption")["cards"]

    # A flag given replaces the read's judgement of the fit and keeps its categories.
    rats.run("add", "Feed the Cycle", "--serves-theme", "no")
    assert fit(rats, "Feed the Cycle") is False
    assert "Feed the Cycle" in category(rats.tally(), "Targeted disruption")["cards"]
    rats.run("add", "Starscape Cleric", "--serves-theme", "yes")
    assert fit(rats, "Starscape Cleric") is True
    entry = {e["name"]: e for e in rats.read()["cards"]}["Starscape Cleric"]
    assert (entry.get("categories"), entry.get("serves_theme")) == (["Card advantage"], True), (
        "one place for the fit: the read shows what add recorded"
    )


def test_add_records_theme_fit_judge_takes_deck_cards(deck):
    """P2: with no collection, `judge` records the fit of a card in the deck, so the review can judge it."""
    deck.new()
    deck.run("theme", "Graveyard")
    deck.add("Sign in Blood", "Card advantage")
    deck.judge([{"name": "Sign in Blood", "serves_theme": True}])
    assert fit(deck, "Sign in Blood") is True
    assert "Sign in Blood" in category(deck.tally(), "Card advantage")["cards"], "its categories are kept"

    before = deck.deck_file.read_bytes()
    proc = deck.run("judge", '[{"name": "Lightning Bolt", "serves_theme": true}]', expect=None)
    assert_refused(proc, deck, before, EXIT_USAGE)


@pytest.mark.parametrize("answer", ["maybe", "true", ""])
def test_add_records_theme_fit_only_yes_or_no(deck, answer):
    deck.new()
    before = deck.deck_file.read_bytes()
    proc = deck.run("add", "Sol Ring", "--serves-theme", answer, expect=None)
    assert_refused(proc, deck, before, EXIT_USAGE)


def test_judge_with_an_empty_narrowing(deck, tmp_path):
    """R29: with a collection kept, `unjudged` counts the narrowing only. A collection holding nothing in
    Meren's colours narrows to nothing, so nothing is unjudged, whatever the deck's own cards are."""
    player = tmp_path / "player"
    player.mkdir()
    deck.collection(write_file(player, "export.csv", manabox_csv(manabox_row(scryfall_card("Lightning Bolt"), 2))))
    deck.new()
    deck.run("theme", "Graveyard")
    deck.add("Sign in Blood", "Card advantage")
    deck.add("Sol Ring", "Ramp")
    assert deck.read()["cards"] == [], "Lightning Bolt is outside Meren's colours"

    out = json.loads(deck.judge([{"name": "Sign in Blood", "serves_theme": True}]).stdout)
    assert out["unjudged"] == 0, f"the deck's own unjudged Sol Ring is not the narrowing: {out}"
    assert fit(deck, "Sign in Blood") is True


def test_looked_up_add_moves_theme_fit(deck, unreachable_url):
    """R42: a looked-up `add` over a card recorded from the player's text, spelt as the player typed it,
    moves its theme fit to the looked-up name, and `measure` counts it as serving."""
    deck.new()
    deck.run("theme", "Artifacts")
    deck.offline(unreachable_url).run(
        "add", "sol ring", "--from-player", "{T}: Add {C}{C}.", "--type-line", "Artifact", "--serves-theme", "yes"
    )
    deck.add("Sol Ring")
    judgements = deck.stored()["judgements"]
    assert fit(deck, "Sol Ring") is True and "sol ring" not in judgements, judgements
    deck.fill()
    copies = next(e["count"] for e in deck.stored()["cards"] if e["card"]["name"] == "Sol Ring")
    assert deck.measure()["theme_density"]["serving"] == copies


def test_theme_fit_merges_with_judgement_under_looked_up_name(deck, unreachable_url, tmp_path):
    """R43: a judgement already under the looked-up name keeps its fields when the player's-text card is
    looked up, and gains the theme fit recorded under the player's spelling."""
    player = tmp_path / "player"
    player.mkdir()
    deck.collection(write_file(player, "export.csv", manabox_csv(manabox_row(scryfall_card("Grim Monolith"), 1))))
    deck.new()
    deck.run("theme", "Big mana")
    deck.judge([{"name": "Grim Monolith", "categories": ["Ramp"]}])
    deck.offline(unreachable_url).run(
        "add", "grim monolith", "--from-player", "{T}: Add {C}{C}{C}.", "--type-line", "Artifact",
        "--category", "Ramp", "--serves-theme", "yes",
    )
    deck.fill()
    measured = deck.measure()

    judgements = deck.stored()["judgements"]
    assert "grim monolith" not in judgements, judgements
    assert judgements["Grim Monolith"].get("categories") == ["Ramp"], "the judged field stands"
    assert judgements["Grim Monolith"].get("serves_theme") is True, "and the typed theme fit joins it"
    assert measured["theme_density"]["serving"] == 1
