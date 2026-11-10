# Assumptions

| Id | Assumption | Area | Stops holding when |
|---|---|---|---|
| A1 | Where code execution is on, the skill's script runs with uv in every Claude interface, mobile chat included; where uv is missing, `python3` 3.11 or later runs it the same way (the script has no dependencies). | platform | a run where neither `uv run` nor `python3` 3.11+ is there |
| A2 | On an individual plan, scripts in claude.ai chat reach api.scryfall.com and data.scryfall.io without the player changing settings. On Team and Enterprise plans code execution's egress is limited by default and only an owner can allow a domain (Anthropic help, "Create and edit files with Claude", read 2026-11-07). | lookup | a download of the bulk file from `deck.py` itself fails in chat on an individual plan |
| A3 | An eval case can drive a whole interview from one scripted prompt holding the player's answers, with an `append_system_prompt` saying the player's side is already given. | testing | eval runs end before the script's last line more than rarely (measured 1 in 32 with the prompt, 6 in 24 without) |
| A4 | ManaBox imports the decklist as the page writes it: `// COMMANDER`, `1 Name`, a blank line, `// MAINBOARD`, then `N Name` rows with no set codes, a double-faced card under its full `A // B` name. From the project's rules; imported by hand into ManaBox by Mattias, 2026-11-08: it works. `// SIDEBOARD` and `// MAYBEBOARD` are also valid sections (Mattias, 2026-11-08). A decklist ending with a `// MAYBEBOARD` of names has not been imported by hand; it rests on Mattias's word (2026-11-09). | page | an import of a rendered decklist drops or rejects a card, or counts a maybeboard card into the deck |
| A5 | In the Claude app, a plugin added from this repository's marketplace (Customize → Plugins → Add → Add marketplace) gives its skill to chat on every surface signed in to the account, mobile included. Anthropic help, "Use plugins in Claude" (read 2026-11-07), says skills from plugins work in web chat, desktop chat, Cowork and Claude Code, and that plugins are saved to the account; it does not mention the mobile apps. | install | the skill is missing from mobile chat after the plugin is added on the web |
| A6 | Claude Code's working folder and a project's shared folder outlive the conversation, so the bulk file, the collection and the decks kept there are found again by the next conversation. In plain claude.ai chat nothing outlives the conversation: each one starts with the player's export and one download of the bulk file. Not yet observed: from what the folders are for, not from a run. | storage | a later conversation in the same project cannot find a deck or the collection kept by an earlier one |
| A7 | The chat sandbox can download Default Cards (81 MB gzipped) and read it line by line within one command's time limit. Oracle Cards (25 MB) streamed there on 2026-11-08; Default Cards has not been tried there. On a host the first read took about 5.5 s and 133 to 217 MB of memory, and each later command about 0.3 s (2026-11-08). | lookup | the download or the read of Default Cards times out or runs out of memory in chat |
| A8 | Reading every available card in the commander's colours fits one conversation with room for the interview: about 7k tokens (one colour) to 32k (five) on the owner's collection of 661 distinct cards. | interview | a collection's in-colour read crowds out the interview, or the conversation runs out of room before the deck is done |
| A9 | A full build, its review and its improvements fit one conversation: the room A8 leaves after the read holds the rest of the interview, the review and a run of swaps, through to the deck page. Every swap and maybeboard card is recorded the moment the player says yes, so running out of room loses no decision. Not yet observed. | interview | an eval or a real build runs out of room before the deck page |

## Measured

- The Command Zone #658 (2025-02-18) template: lands 38, card advantage 12, ramp 10,
  targeted disruption 12, mass disruption 6, plan 30. Source: episode notes at
  alanwsmith.com/en/38/z9/2w/vi/, read 2026-11-07. A second-hand summary that gives
  plan 22 is wrong.
- The owner's mobile claude.ai chat has code execution and file creation on
  (Mattias, 2026-11-07). Other interfaces and other players are unconfirmed.
- In that chat, Python 3.13 runs in a cloud sandbox, pip installs work, and scripts
  calling other websites are generally blocked (claude.ai chat's own account of its
  sandbox, relayed by Mattias, 2026-11-07). uv 0.11.32 is installed there, and a
  shell request to api.scryfall.com/cards/named returned HTTP 200.
- In the same chat, data.scryfall.io answered HTTP 200 and today's Oracle Cards file
  streamed and decompressed to real card records (relayed by Mattias, 2026-11-08).
- Scryfall's `/bulk-data` entries carry `jsonl_download_uri`, a gzipped JSONL file with
  one card per line, and no `download_uri`. Sizes on 2026-11-08: Oracle Cards 25.4 MB,
  Default Cards 81.0 MB, All Cards 403.8 MB, Oracle Tags 6.1 MB, all gzipped. Scryfall
  asks clients to cache for at least 24 hours, says gameplay data needs fetching at most
  weekly, and points large lookups at bulk data (scryfall.com/docs/api/rate-limits,
  read 2026-11-08). Files on `*.scryfall.io` have no rate limit.
- Scryfall's `cards/named`, `cards/search`, `cards/random` and `cards/collection` are
  each limited to 2 requests a second (500 ms); a 429 locks the client out for 30
  seconds (scryfall.com/docs/api/rate-limits, read 2026-11-08). `cards/collection`
  takes at most 75 identifiers per request.
- Scryfall treats case and punctuation as optional in `cards/named` names, for exact and
  fuzzy alike: `smugglers copter` and a curly apostrophe both answer Smuggler's Copter
  (documented; probed 2026-11-07).
- The owner's collection (deck-composer-v3's card facts, 2026-11-08): 661 distinct cards,
  1,438 copies, 631 nonland. Eight token lots share a card's name (Starscape Cleric: six
  copies of the card, two of a token); token lots sit in sets ManaBox names
  "… Tokens". A ManaBox CSV export carries `Binder Name`, `Binder Type` (`binder` or
  `deck`), `Scryfall ID` (the printing's) and `Quantity`, among 18 columns.
- A Claude app skill's description is at most 200 characters (Anthropic help, "How to
  create custom skills", read 2026-11-07).
- `claude plugin eval` on this kind of host: the run's own sandbox settings deny writes to
  `//tmp`, so `TMPDIR` must be outside `/tmp`; a shell command reaches only the domains
  granted with `WebFetch(domain:…)`; an `llm` grader on the trace sees only its first and
  last 12 lines, mostly streaming deltas (measured 2026-11-07; see evals/README.md).
- An `llm` grader can instead judge a file the run leaves, with `focus: { source: file,
  path }`; the runner takes three judge votes per grader, and two passes is a pass
  (probed 2026-11-09; see evals/README.md).
