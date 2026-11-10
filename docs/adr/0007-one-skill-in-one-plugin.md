# ADR-0007 — One skill in one plugin

**Status:** Accepted (2026-11-10)

## Context

Deckwright ships through a plugin marketplace and runs in project threads in
milestone 1. A few rules apply at every step of a build.

## Decision

The deckwright repository is a marketplace with one plugin holding one skill: a
short main file with the rules that always apply, the page template, and further
files only where the bare runs fail. The briefs and checks live in the repository,
outside the plugin.

Rejected for now: several skills behind an entry skill, because the always-on
rules would have to be repeated in each, and one copy drifting lets a step run
without them.

## Consequences

The main file is read on every build, so it must stay short. A split is taken only
when the runs show a step's file is not being read; that split supersedes this
record.
