---
description: "A no to cards not owned: only collection cards offered after it, nothing unowned recorded, and the interview carries on."
tags: [collection, network]
plugins: ["../../plugins/deckwright"]
max_turns: 120
timeout_seconds: 1800
append_system_prompt: "The player in this session is scripted and cannot reply while it runs: their whole side of the conversation is already in the first user message, written in advance, and this session is a single turn. Talk to them as you would to a live player, saying and asking everything you would say and ask. Where you would then end your turn to wait for their reply, do not: take their reply from the script and carry on in the same turn. End your turn only after you have answered the last line of the script that applies. Do not write the player's lines out yourself."
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit]
---
help me build a commander deck from my collection. My ManaBox export is ManaBox_Collection.csv in this folder.

(Everything below is my side of the conversation, written in advance because I can't reply while you work. Play the conversation through to its end: wherever you would stop and wait for me, take my answer from this script and carry on. Write only your own side; don't write my lines out. I say yes to no card I don't name here.)

1. When you ask for my commander: "Vren, the Relentless."
2. When you ask what to call the deck: "Drowned Rats."
3. When you ask for a theme: "Bloomburrow rats."
4. For lands: "Skip lands for now."
5. For ramp, once you've offered suggestions: "Add the first card on your list of ones missing from my collection."
6. If you ask whether to use cards I don't own: "No. Only cards I own, please."
7. Then: "Add Blitzball."
8. Then: "Add Thought Shucker."
9. Then: "Let's stop there for today."
10. To any other question: "Nothing more from me on that. Carry on."
