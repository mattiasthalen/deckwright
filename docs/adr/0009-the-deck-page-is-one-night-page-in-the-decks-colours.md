# ADR-0009 — The deck page is one night page in the deck's colours

**Status:** Accepted (2026-11-11)

## Context

The milestone 1 design agreed that the deck page looks like the page "Vren's Rat
Pack", with scenes in the style of the page "Bloomburrow Commanders". That
agreement was recorded only in a design document outside the repository. The
template that shipped had a system font, tabs and one flat accent, and nothing in
the repository could show it had drifted. Vren's page is night-coloured with a
gold accent, made for one blue-black deck; the template serves every deck.

## Decision

The page is one page read top to bottom, in this order: a hero with the hero
card's artwork, the deck name, a pitch, the criteria and headline numbers counted
by the page; the scenes; the cards by category, each opening a dialog with the
card, its cost as symbols, its rules text and its why; the mana curve split into
creatures and other spells; the handbook with a chapter list that stays in view;
the ledger; the Arena list. Headings use a display serif and body text a humanist
sans. The background is night for every deck. The accent comes from the colours
of the deck's cards: one colour gives that colour, several give a blend, none
gives gold. The curve keeps two fixed colours, so its two parts stay apart in any
deck.

The template is the statement of this look. A browser test opens it with a test
deck and fails when a part above is missing.

Rejected:

- Night and gold for every deck: the player chose the deck's own colours from a
  mockup of both.
- Tabs: the agreed page is read top to bottom, and tabs hid the handbook and the
  curve.
- A light version: the model has none.
- Describing the look in the skill text: ADR-0002 keeps agreed design out of it.

## Consequences

A deck's page tells its colours at a glance. The accent is computed, so a colour
combination nobody has looked at can read badly; the curve already needed fixed
colours for that reason. The fonts come from Google Fonts, with system fonts
named as fallbacks. A change to the look is a change to the template and to the
browser test together.
