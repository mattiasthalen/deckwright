# ADR-0008 — Scenes are played from data with whole card pictures

**Status:** Accepted (2026-11-11)

## Context

The deck page is identical for every deck (ADR-0010), so anything specific to
a deck reaches the page as data. Until now a scene was an SVG string that
Deckwright wrote by hand into `deck.json`. The first real deck got line drawings
with a text label, and the player wanted the scenes to show the cards he picked.
The agreed model was the Bloomburrow Commanders page, which animates card
pictures. The card pictures are already saved in the deck folder.

On the first proof, damage and drawn cards were plain number chips, which said
what they did without showing it. From a mockup the player chose a life total
that takes the hit and card backs dealt in.

## Decision

A scene in `deck.json` is a title and a list of steps. A step is a caption and a
row of things: a card from the deck, a token, a pile shown as a card-shaped box
with its count, mana symbols, a chip with a short word or number, damage (the
opponent's life total takes the hit) or drawn cards (Magic card backs dealt in).
A thing may enter, glow, tap, leave or appear as a copy, and may carry a badge;
damage and drawn cards take none, as their −N or +N mark is their badge. The page draws every
card and token as its whole saved picture and plays the steps in a loop with no
controls. The first scene is the deck's main engine and is drawn large; the others
follow smaller.

Rejected:

- An SVG string per scene, written per deck: it shows drawings instead of the
  cards, and the page cannot improve a scene it does not draw.
- The artwork alone, cut out of the card frame: the player chose whole cards from
  a side-by-side mockup.
- A click-to-play engine as on Vren's Rat Pack: left out on purpose in the
  milestone 1 design.

## Consequences

Every deck's scenes look alike and improve when the page does. A scene can
only show what the things and their five motions can express; anything else needs
a new kind of thing in the page first. Tokens need saved pictures, and drawn
cards need the saved card back. A scene
that names a card no longer in the deck shows the name on a blank card, so a
swap that Deckwright forgets to follow degrades a scene and does not break it.
`deck.json` moves to version 2, and nothing reads the SVG scenes of version 1.
