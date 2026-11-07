# Assumptions

| Id | Assumption | Area | Stops holding when |
|---|---|---|---|
| A1 | Where code execution is on, the skill's script runs with uv in every Claude interface, mobile chat included. | platform | a run where `uv run` is missing or fails |
| A2 | Scripts in claude.ai chat reach api.scryfall.com without the player changing settings. | lookup | a lookup from the script fails in chat |
| A3 | An eval case can drive a whole interview from one scripted prompt holding the player's answers. | testing | eval runs stop at the first question |

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
