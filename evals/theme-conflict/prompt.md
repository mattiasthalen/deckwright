---
description: "A theme that pulls against its commander, settled into the plan sentence; then a theme change that keeps the deck's cards and names the ones that no longer serve it."
tags: [collection, theme, network]
plugins: ["../../plugins/deckwright"]
max_turns: 120
timeout_seconds: 1800
append_system_prompt: "The player in this session is scripted and cannot reply while it runs: their whole side of the conversation is already in the first user message, written in advance, and this session is a single turn. Talk to them as you would to a live player, saying and asking everything you would say and ask. Where you would then end your turn to wait for their reply, do not: take their reply from the script and carry on in the same turn. End your turn only after you have answered the last line of the script that applies. Do not write the player's lines out yourself."
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit]
---
help me build a commander deck from my collection. My ManaBox export is ManaBox_Collection.csv in this folder.

(Everything below is my side of the conversation, written in advance because I can't reply while you work. Play the conversation through to its end: wherever you would stop and wait for me, take my answer from this script and carry on. Write only your own side; don't write my lines out. I say yes to no card I don't name here.)

1. When you ask for my commander: "Muerra, Trash Tactician."
2. When you ask what to call the deck: "Trash Pandas."
3. When you ask for a theme: "Squirrels."
4. If you tell me the theme pulls against my commander and ask how to settle it: "Squirrels fill the graveyard and Muerra's raccoons eat what they leave behind. Make that the plan."
5. For lands: "Add 15 Forest and 15 Mountain. That's all the lands for now."
6. Then: "Skip ahead to the plan cards."
7. For the plan, once you've offered suggestions: "Add Treetop Sentries, Thornvault Forager and Bakersbane Duo."
8. Then: "Actually, change the theme to raccoons only."
9. If you tell me which cards no longer fit: "Leave them in for now. Let's stop there for today. Show me the deck page."
10. To any other question: "Nothing more from me on that. Carry on."
