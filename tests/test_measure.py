"""`measure`: the numbers the written review is drawn from: AC1–AC6, E1, E2, E12.

Every deck here is built from recorded cards and filled to its deck size with Swamps and Forests
(`Deckwright.fill`). What `measure` prints, and which cards it reads, is fixed in tests/README.md:
it counts every card of the deck but the commander, by copies.
"""

from __future__ import annotations

import re
import shutil

import pytest
from conftest import EXIT_USAGE, Deckwright, assert_refused, read_page, said

PLAYER_OWL = "Flying. When this creature enters, draw a card."


def curve_deck(deck: Deckwright) -> None:
    """Nonland cards whose mana values are known by hand (Scryfall's `cmc`), beside lands that hold none."""
    deck.new()
    for name in ("Sol Ring", "Llanowar Elves", "Vampiric Tutor"):  # 1
        deck.add(name)
    for name in ("Sign in Blood", "Exsanguinate"):  # 2, X counted as 0
        deck.add(name)
    # 3: Journey to Eternity is an Enchantment whose back face is a Land, Egon a Creature whose back face
    # costs {B}: each counts its front face. Relentless Rats counts every copy.
    for name in ("Cultivate", "Pernicious Deed", "Journey to Eternity", "Egon, God of Death", "Burnished Hart"):
        deck.add(name)
    deck.add("Relentless Rats", count=3)
    for name in ("Ravenous Chupacabra", "Bloodline Keeper", "Vraska, Golgari Queen"):  # 4
        deck.add(name)
    deck.add("Elbrus, the Binding Blade")  # 7: its back face, a Creature, has no cost
    deck.add("Command Tower")
    deck.add("Evolving Wilds")
    deck.fill()


# Nonland copies by mana value, the commander apart: 17 cards whose mana values sum to 50.
CURVE = {1: 3, 2: 2, 3: 8, 4: 3, 7: 1}
AVERAGE = 50 / 17


def curve_of(measured: dict) -> dict[float, int]:
    return {float(e["mana_value"]): e["count"] for e in measured["curve"] if e["count"]}


# AC1 ---------------------------------------------------------------------------------


def test_curve(deck):
    curve_deck(deck)
    measured = deck.measure()

    assert curve_of(measured) == {float(k): v for k, v in CURVE.items()}, measured["curve"]
    values = [float(e["mana_value"]) for e in measured["curve"]]
    assert values == sorted(values), "the curve runs from the lowest mana value up"
    assert abs(measured["average_mana_value"] - AVERAGE) <= 0.005, (
        f"the average of the nonland cards is 50 / 17 = {AVERAGE:.4f}: {measured['average_mana_value']}"
    )
    assert measured["average_mana_value"] == round(measured["average_mana_value"], 2), "rounded to two places"
    assert measured["not_counted"] == [], "every card was looked up, so every card is counted"


# AC2 ---------------------------------------------------------------------------------


def test_colour_balance(deck):
    deck.new()  # Meren of Clan Nel Toth: black-green
    # Pips, every face's cost, nonland only (Bloodline Keeper's back face has none): B 2+2+1+2+2 = 9,
    # G 1+1+1 = 3. Lightning Bolt's {R} is outside the identity and listed nowhere; Sol Ring's {1} is no colour.
    for name in (
        "Sign in Blood", "Ravenous Chupacabra", "Pernicious Deed", "Exsanguinate", "Bloodline Keeper",
        "Llanowar Elves", "Cultivate", "Lightning Bolt", "Sol Ring",
    ):
        deck.add(name)
    # Sources: Command Tower and Uncharted Haven list all five colours and count for B and G only;
    # Mudflat Village lists B and C, and counts for B; Ancient Tomb lists only C, Evolving Wilds nothing.
    # Llanowar Elves makes {G} but is not a land.
    for name in ("Command Tower", "Uncharted Haven", "Mudflat Village", "Ancient Tomb", "Evolving Wilds"):
        deck.add(name)
    deck.add("Swamp", count=45)
    deck.add("Forest", count=40)
    assert deck.tally()["total"] == 100

    colours = deck.measure()["colours"]
    assert [c["colour"] for c in colours] == ["B", "G"], "one entry per colour of the identity, in WUBRG order"
    by_colour = {c["colour"]: (c["pips"], c["sources"]) for c in colours}
    assert by_colour["B"] == (9, 3 + 45), colours
    assert by_colour["G"] == (3, 2 + 40), colours


# AC3 ---------------------------------------------------------------------------------


def test_lands_that_make_no_mana(deck):
    deck.new()
    for name in ("Evolving Wilds", "Ancient Tomb", "Command Tower", "Journey to Eternity", "Sol Ring"):
        deck.add(name)
    deck.fill()
    # Ancient Tomb makes {C}, which is mana; Journey to Eternity's front face is not a land.
    assert deck.measure()["lands_without_mana"] == ["Evolving Wilds"]


# AC4 ---------------------------------------------------------------------------------


def test_card_types(deck):
    curve_deck(deck)
    types = deck.measure()["types"]
    assert set(types) == {"creature", "instant", "sorcery", "artifact", "enchantment", "planeswalker", "land"}
    assert types == {
        # Llanowar Elves, Ravenous Chupacabra, Bloodline Keeper, Egon (front face; its back is an Artifact),
        # 3 Relentless Rats, Burnished Hart (an Artifact Creature, so in both).
        "creature": 8,
        "instant": 1,  # Vampiric Tutor
        "sorcery": 3,  # Sign in Blood, Exsanguinate, Cultivate
        "artifact": 3,  # Sol Ring, Burnished Hart, Elbrus (front face; its back is a Creature)
        "enchantment": 2,  # Pernicious Deed, Journey to Eternity (front face; its back is a Land)
        "planeswalker": 1,  # Vraska, Golgari Queen
        "land": 82,  # Command Tower, Evolving Wilds and 80 basics: the commander is not counted
    }, types


# AC5, E12 ----------------------------------------------------------------------------


def test_theme_density(deck):
    deck.new()
    deck.run("theme", "Rats")
    deck.run("add", "Relentless Rats", "--count", "20", "--serves-theme", "yes")
    deck.run("add", "Sign in Blood", "--serves-theme", "no")
    deck.add("Sol Ring")  # no fit given, and no read: it serves nothing
    deck.fill()
    measured = deck.measure()
    assert measured["theme_density"] == {"serving": 20, "of": 99}, "copies serving, out of the deck less its commander"

    # E12: a deck with no theme has no theme density, not a zero.
    bare = deck.named("No Theme")
    bare.add("Relentless Rats", count=20)
    bare.fill()
    assert "theme_density" not in bare.measure()


# AC6 ---------------------------------------------------------------------------------


def player_text_deck(deck: Deckwright, unreachable_url: str) -> Deckwright:
    """A full deck holding two cards recorded from the player's text: Sign in Blood, which the bulk
    file knows, and Homebrew Owl, which it does not."""
    deck.new()
    deck.add("Sol Ring")
    offline = deck.offline(unreachable_url)
    offline.run("add", "Sign in Blood", "--from-player", "Target player draws two cards and loses 2 life.",
                "--type-line", "Sorcery")
    offline.run("add", "Homebrew Owl", "--from-player", PLAYER_OWL, "--type-line", "Creature — Bird")
    deck.fill()
    return offline


def test_player_text_cards_looked_up_again(deck, unreachable_url):
    player_text_deck(deck, unreachable_url)
    measured = deck.measure()

    assert measured["not_counted"] == ["Homebrew Owl"], "only the card the bulk file does not know is left out"
    # Sign in Blood is counted now, at its looked-up mana value: Sol Ring at 1, Sign in Blood at 2.
    assert curve_of(measured) == {1.0: 1, 2.0: 1}, measured["curve"]
    # And it is the looked-up card from now on: the page marks only Homebrew Owl as the player's text.
    marked = read_page(deck.page()).section("player-text")
    assert "Homebrew Owl" in marked and "Sign in Blood" not in marked, marked


def test_player_text_cards_looked_up_again_unreachable(deck, unreachable_url):
    """P5: with no bulk file and Scryfall out of reach, the cards stay as they are, are listed as not
    counted, and `measure` does not fail for it."""
    offline = player_text_deck(deck, unreachable_url)
    shutil.rmtree(deck.cache)
    measured = offline.measure()
    assert measured["not_counted"] == ["Homebrew Owl", "Sign in Blood"]
    assert curve_of(measured) == {1.0: 1}, measured["curve"]
    assert "Sign in Blood" in read_page(offline.page()).section("player-text"), "still the player's text"


# E1, E2 ------------------------------------------------------------------------------


def test_refuses_short_deck(deck):
    deck.new()
    deck.add("Sol Ring")
    deck.add("Swamp", count=32)  # 34 of 100
    before = deck.deck_file.read_bytes()
    proc = deck.run("measure", expect=None)
    assert_refused(proc, deck, before, EXIT_USAGE)
    text = said(proc)
    assert re.search(r"(?<!\d)66(?!\d)", text), f"the message says 66 cards are missing: {text!r}"
    assert re.search(r"missing|short|more", text, re.I), text


def test_refuses_over_deck(deck):
    deck.new()
    deck.add("Sol Ring")
    deck.fill()
    deck.add("Forest", count=3)  # 103 of 100
    before = deck.deck_file.read_bytes()
    proc = deck.run("measure", expect=None)
    assert_refused(proc, deck, before, EXIT_USAGE)
    text = said(proc)
    assert re.search(r"(?<!\d)3(?!\d)", text) and re.search(r"\bover\b|too many", text, re.I), (
        f"the message says the deck is 3 over: {text!r}"
    )


@pytest.mark.parametrize("total", [99, 101])
def test_refuses_short_deck_and_over_by_one(deck, total):
    """E1, E2 at the edge: one card short or one over is refused too."""
    deck.new()
    deck.fill(total)
    before = deck.deck_file.read_bytes()
    assert_refused(deck.run("measure", expect=None), deck, before, EXIT_USAGE)


def test_player_text_card_keeps_its_theme_fit(deck, unreachable_url):
    """R20: a card recorded from the player's text, spelt as the player typed it, keeps its theme fit when
    `measure` finds it: the judgement moves to the looked-up name and the card counts as serving."""
    deck.new()
    deck.run("theme", "Big mana")
    deck.offline(unreachable_url).run(
        "add", "grim monolith", "--from-player", "{T}: Add {C}{C}{C}.", "--type-line", "Artifact",
        "--serves-theme", "yes",
    )
    deck.fill()
    measured = deck.measure()

    assert measured["not_counted"] == [], "the bulk file knows Grim Monolith under its own spelling"
    assert measured["theme_density"] == {"serving": 1, "of": 99}, measured.get("theme_density")
    judgements = deck.stored()["judgements"]
    assert judgements.get("Grim Monolith", {}).get("serves_theme") is True, judgements
    assert "grim monolith" not in judgements, "the player's spelling gives way to the card's"


def test_split_card(deck):
    """R31: a split card is cast as either half, so the pips of both halves count, and its mana value is
    Scryfall's, the halves added up: Destined // Lead is {1}{B} // {3}{G}, mana value 6."""
    deck.new()
    deck.add("Destined // Lead")
    deck.fill()
    measured = deck.measure()
    assert {c["colour"]: c["pips"] for c in measured["colours"]} == {"B": 1, "G": 1}, measured["colours"]
    assert curve_of(measured) == {6.0: 1}, measured["curve"]


def test_modal_double_faced_card(deck):
    """R37: a modal double-faced card is cast as either face, so both faces' pips count, as a split card's
    halves do: Egon, God of Death // Throne of Death is {2}{B} // {B}, two B. Its mana value stays its front
    face's, 3."""
    deck.new()
    deck.add("Egon, God of Death")
    deck.fill()
    measured = deck.measure()
    assert {c["colour"]: c["pips"] for c in measured["colours"]} == {"B": 2, "G": 0}, measured["colours"]
    assert curve_of(measured) == {3.0: 1}, measured["curve"]


# Bloodline Keeper recorded from the player's text, under its front face's name only (R46–R48).
KEEPER_TYPED = ("Bloodline Keeper", "--from-player", "Flying.", "--type-line", "Legendary Creature — Vampire")


def test_two_spellings_of_one_card_merge(deck, unreachable_url):
    """R48: two player's-text entries that are one card's two faces, once `measure` finds them, are one
    entry under the card's name, their copies added and their categories merged, so the copies check
    sees two copies."""
    deck.new()
    offline = deck.offline(unreachable_url)
    offline.run("add", *KEEPER_TYPED, "--category", "Plan")
    offline.run("add", "Lord of Lineage", "--from-player", "Other Vampire creatures you control get +2/+2.",
                "--type-line", "Legendary Creature — Vampire", "--category", "Card advantage")
    deck.fill()
    deck.measure()

    entries = [e for e in deck.stored()["cards"] if "Lineage" in e["card"]["name"] or "Keeper" in e["card"]["name"]]
    assert [(e["card"]["name"], e["count"]) for e in entries] == [("Bloodline Keeper // Lord of Lineage", 2)], entries
    assert sorted(entries[0]["categories"]) == ["Card advantage", "Plan"], entries[0]["categories"]
    assert "Bloodline Keeper // Lord of Lineage" in deck.tally()["checks"]["singleton"]
