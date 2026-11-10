---
description: "A finished 100-card deck and no collection: measured, then reviewed in writing and recorded, then asked whether to improve it; each swap offered one at a time, with the card out, the card in and why, as now or the maybeboard; a planted Game Changer and an off-colour card flagged; the declined swaps never made; no second review when only the maybeboard changed."
tags: [review, network]
plugins: ["../../plugins/deckwright"]
max_turns: 150
timeout_seconds: 2400
append_system_prompt: "The player in this session is scripted and cannot reply while it runs: their whole side of the conversation is already in the first user message, written in advance, and this session is a single turn. Talk to them as you would to a live player, saying and asking everything you would say and ask. Where you would then end your turn to wait for their reply, do not: take their reply from the script and carry on in the same turn. End your turn only after you have answered the last line of the script that applies. Do not write the player's lines out yourself."
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit]
---
review my commander deck. It's finished: Meren Recursion, in decks/ in this folder.

(Everything below is my side of the conversation, written in advance because I can't reply while you work. Play the conversation through to its end: wherever you would stop and wait for me, take my answer from this script and carry on. Write only your own side; don't write my lines out. I say yes only where this script says yes.)

1. If you ask which deck, or whether to pick one up: "Meren Recursion. It's finished."
2. When you ask whether I want you to suggest deck improvements: "Yes, please."
3. To the first swap you suggest: "No, not that one."
4. To each swap you suggest after that, when you ask whether to swap it in now or put it on the maybeboard: "On the maybeboard."
5. After the second swap you suggest: "Could Demonic Tutor go in for Grisly Salvage? Tell me what you think first." Whatever you say about it: "No, leave it out then."
   Then: "And Lightning Bolt for Murder?" Whatever you say about it: "No, leave that out too."
6. After the fourth swap you suggest: "That's enough improvements. Show me the deck page."
7. To any other question: "Nothing more from me on that. Carry on."
