# ADR-0005 — A category is a job, and a creature type is a criterion

**Status:** Accepted (2026-11-10)

## Context

The intent offered Brawl a choice between eight categories and a fixed split of
ramp, card draw and removal plus a theme bucket. A typal deck tempts a "rats"
category beside the jobs.

## Decision

A category is a job a card does, such as ramp or removal. A creature type is a
criterion that applies to every category, never a category. Brawl starts as eight
categories of eight places: ramp, card draw, removal and personal favourites, plus
four jobs drawn from the criteria. Standard starts as nine categories of four
places, all from the criteria. A template is a starting point: a category may end
off target and a playset may be split, each recorded with its target and a
reason the player confirms.

Rejected: a second Brawl template with a fixed split, because no published Brawl
numbers exist to fix it to; the Command Zone numbers, because they are made for
four-player Commander.

## Consequences

Every card sits in exactly one category and may carry several tags. Typal fit is
judged in every category through the ladder, not in a bucket of its own.
`deck.json` records each category's target and, when it ends off target, the
reason. A category's count is worked out from its cards and never stored, so it
cannot disagree with them.
