# Assumptions

| Id | Assumption | Area | Stops holding when |
|---|---|---|---|
| A1 | Where code execution is on, the skill's script runs with uv in every Claude interface, mobile chat included; where uv is missing, `python3` 3.11 or later runs it the same way (the script has no dependencies). | platform | a run where neither `uv run` nor `python3` 3.11+ is there |
| A2 | On an individual plan, scripts in claude.ai chat reach api.scryfall.com without the player changing settings. On Team and Enterprise plans code execution's egress is limited by default and only an owner can allow the domain (Anthropic help, "Create and edit files with Claude", read 2026-11-07). | lookup | a lookup from `deck.py` itself fails in chat on an individual plan |
| A3 | An eval case can drive a whole interview from one scripted prompt holding the player's answers, with an `append_system_prompt` saying the player's side is already given. | testing | eval runs end before the script's last line more than rarely (measured 1 in 32 with the prompt, 6 in 24 without) |
| A4 | ManaBox imports the decklist as the page writes it: `// COMMANDER`, `1 Name`, a blank line, `// MAINBOARD`, then `N Name` rows with no set codes, a double-faced card under its full `A // B` name. From the project's rules; imported by hand into ManaBox by Mattias, 2026-11-08: it works. | page | an import of a rendered decklist drops or rejects a card |
| A5 | In the Claude app, a plugin added from this repository's marketplace (Customize → Plugins → Add → Add marketplace) gives its skill to chat on every surface signed in to the account, mobile included. Anthropic help, "Use plugins in Claude" (read 2026-11-07), says skills from plugins work in web chat, desktop chat, Cowork and Claude Code, and that plugins are saved to the account; it does not mention the mobile apps. | install | the skill is missing from mobile chat after the plugin is added on the web |

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
- Scryfall's `cards/named` is limited to 2 requests a second (500 ms), stricter than the
  10 a second for other endpoints; a 429 locks the client out for 30 seconds
  (scryfall.com/docs/api/rate-limits, read 2026-11-07). The script keeps 0.5 s between requests.
- Scryfall treats case and punctuation as optional in `cards/named` names, for exact and
  fuzzy alike: `smugglers copter` and a curly apostrophe both answer Smuggler's Copter
  (documented; probed 2026-11-07).
- A Claude app skill's description is at most 200 characters (Anthropic help, "How to
  create custom skills", read 2026-11-07).
- `claude plugin eval` on this kind of host: the run's own sandbox settings deny writes to
  `//tmp`, so `TMPDIR` must be outside `/tmp`; a shell command reaches only the domains
  granted with `WebFetch(domain:…)`; an `llm` grader on the trace sees only its first and
  last 12 lines, mostly streaming deltas (measured 2026-11-07; see evals/README.md).
