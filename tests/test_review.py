"""The reviewed state: AC9, AC10, E14 (P3).

A deck is reviewed when `measure` has stored its measures and `review` its written review, both on
the deck as it is. The tests see it two ways: the deck file's `review` record (P3: `review.measures`,
`review.text`), and the page, which carries the unfinished mark until the deck is reviewed.
"""

from __future__ import annotations

import pytest
from conftest import EXIT_USAGE, Deckwright, assert_refused, read_page, unfinished_mark

REVIEW = "The deck wins late, through Meren's recursion.\n\nRamp is short; the lands carry it."


def full_deck(deck: Deckwright) -> None:
    deck.new()
    deck.add("Sol Ring", "Ramp")
    deck.add("Sign in Blood", "Card advantage")
    deck.add("Ravenous Chupacabra", "Targeted disruption", "Plan")
    deck.add("Pernicious Deed", "Mass disruption")
    deck.add("Command Tower")
    deck.add("Evolving Wilds")
    deck.fill()


def mark(deck: Deckwright) -> str | None:
    """The page's unfinished mark, or None when the page has none."""
    texts = read_page(deck.page()).texts.get("section:unfinished", [])
    assert len(texts) <= 1, texts
    return texts[0] if texts else None


def reviewed(deck: Deckwright) -> bool:
    record = deck.stored().get("review") or {}
    return "measures" in record and "text" in record


def review_it(deck: Deckwright) -> None:
    deck.measure()
    deck.review(REVIEW)
    assert reviewed(deck) and mark(deck) is None


# AC9 ---------------------------------------------------------------------------------


def test_reviewed_after_measure_and_review(deck):
    full_deck(deck)
    assert not reviewed(deck)
    assert unfinished_mark(100).search(mark(deck) or ""), mark(deck)

    # The written review before the measures: refused, nothing stored.
    before = deck.deck_file.read_bytes()
    assert_refused(deck.run("review", REVIEW, expect=None), deck, before, EXIT_USAGE)

    deck.measure()
    assert "measures" in deck.stored()["review"], "measure stores what it prints"
    assert not reviewed(deck)
    assert unfinished_mark(100).search(mark(deck) or ""), "measured but not yet written: still not reviewed"

    deck.review(REVIEW)
    assert deck.stored()["review"]["text"] == REVIEW, "the written review is kept as given"
    assert reviewed(deck)
    assert mark(deck) is None, "a deck at its size and reviewed is finished: no unfinished mark"


def test_reviewed_after_measure_and_review_measure_again(deck):
    """P3: `measure` again drops the written review: the review has to be written on the new measures."""
    full_deck(deck)
    review_it(deck)
    deck.measure()
    assert "text" not in deck.stored()["review"]
    assert not reviewed(deck)
    assert unfinished_mark(100).search(mark(deck) or "")


def test_reviewed_after_measure_and_review_on_the_deck_as_it_is(deck):
    """P3: `review` refuses until `measure` has run on the deck as it is: a change in between drops the measures."""
    full_deck(deck)
    deck.measure()
    deck.run("target", "Ramp", "8")
    before = deck.deck_file.read_bytes()
    assert_refused(deck.run("review", REVIEW, expect=None), deck, before, EXIT_USAGE)


# AC10, E14 ---------------------------------------------------------------------------

# Each step runs on a reviewed deck; `setup` runs before the review. Spelled as the commands are run.
CLEARS = {
    "add": ([], ["add", "Vampiric Tutor", "--category", "Plan"], 101),
    "remove": ([], ["remove", "Sign in Blood"], 99),
    "swap": ([], ["swap", "Sign in Blood", "Feed the Cycle", "--why", "Removal over draw", "--category", "Plan"], 100),
    "target": ([], ["target", "Ramp", "8"], 100),  # E14
    "bracket": ([], ["bracket", "3"], 100),
    "theme": ([], ["theme", "Rats"], 100),
    "plan": ([], ["plan", "Bring back the dead."], 100),
}
KEEPS = {
    "maybeboard add": ([], ["maybeboard", "add", "Demonic Tutor", "--replaces", "Sign in Blood", "--why", "Better"]),
    "maybeboard remove": (
        [["maybeboard", "add", "Demonic Tutor", "--replaces", "Sign in Blood", "--why", "Better"]],
        ["maybeboard", "remove", "Demonic Tutor"],
    ),
    # P3: neither is in R1's list of changes.
    "judge": ([], ["judge", '[{"name": "Sign in Blood", "serves_theme": true}]']),
    "not-owned": ([], ["not-owned", "yes"]),
}


@pytest.mark.parametrize("step", list(CLEARS))
def test_what_clears_reviewed(deck, step):
    setup, command, total = CLEARS[step]
    full_deck(deck)
    for s in setup:
        deck.run(*s)
    review_it(deck)

    deck.run(*command)
    assert "review" not in deck.stored(), f"{step} drops the review record whole (P3)"
    assert not reviewed(deck)
    assert unfinished_mark(total).search(mark(deck) or ""), f"after {step}: {mark(deck)!r}"


@pytest.mark.parametrize("step", list(KEEPS))
def test_what_clears_reviewed_not_the_maybeboard(deck, step):
    setup, command = KEEPS[step]
    full_deck(deck)
    for s in setup:
        deck.run(*s)
    review_it(deck)
    kept = deck.stored()["review"]

    deck.run(*command)
    assert deck.stored().get("review") == kept, f"{step} leaves the review as it was"
    assert mark(deck) is None, f"after {step} the deck is still finished"


@pytest.mark.parametrize("text", ["", "  \n\t "])
def test_review_refuses_blank_text(deck, text):
    """R23: a written review has words: a blank one records nothing, and the deck is still not reviewed."""
    full_deck(deck)
    deck.measure()
    before = deck.deck_file.read_bytes()
    assert_refused(deck.run("review", text, expect=None), deck, before)
    assert not reviewed(deck)
    assert mark(deck) is not None
