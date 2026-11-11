# ADR-0008 — Scenes are played from data with whole card pictures

**Status:** Accepted (2026-11-11)

## Context

The page template is identical for every deck (ADR-0003), so anything specific to
a deck reaches the page as data. Until now a scene was an SVG string that
Deckwright wrote by hand into `deck.json`. The first real deck got line drawings
with a text label, and the player wanted the scenes to show the cards he picked.
The agreed model was the Bloomburrow Commanders page, which animates card
pictures. The card pictures are already saved in the deck folder.

## Decision

A scene in `deck.json` is a title and a list of steps. A step is a caption and a
row of things: a card from the deck, a token, a pile shown as a card back with a
number, mana symbols, or a chip with a short word or number. A thing may enter,
glow, tap, leave or appear as a copy, and may carry a badge. The page draws every
card and token as its whole saved picture and plays the steps in a loop with no
controls. The first scene is the deck's main engine and is drawn large; the others
follow smaller.

Rejected:

- An SVG string per scene, written per deck: it shows drawings instead of the
  cards, and the template cannot improve a scene it does not draw.
- The artwork alone, cut out of the card frame: the player chose whole cards from
  a side-by-side mockup.
- A click-to-play engine as on Vren's Rat Pack: left out on purpose in the
  milestone 1 design.

## Consequences

Every deck's scenes look alike and improve when the template does. A scene can
only show what the things and their five motions can express; anything else needs
a new kind of thing in the template first. Tokens need saved pictures. A scene
that names a card no longer in the deck shows the name on a blank card, so a
swap that Deckwright forgets to follow degrades a scene and does not break it.
`deck.json` moves to version 2, and nothing reads the SVG scenes of version 1.
