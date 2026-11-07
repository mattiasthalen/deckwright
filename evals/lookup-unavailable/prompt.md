---
description: "Scryfall is out of reach: deckwright says so, names the card, asks the player for its text, does not describe it from memory, and the page marks the card as the player's text."
tags: [offline]
plugins: ["../../plugins/deckwright"]
max_turns: 80
timeout_seconds: 1200
append_system_prompt: "The player in this session is scripted and cannot reply while it runs: their whole side of the conversation is already in the first user message, written in advance, and this session is a single turn. Talk to them as you would to a live player, saying and asking everything you would say and ask. Where you would then end your turn to wait for their reply, do not: take their reply from the script and carry on in the same turn. End your turn only after you have answered the last line of the script that applies. Do not write the player's lines out yourself."
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit]
---
help me build a commander deck

(Everything below is my side of the conversation, written in advance because I can't reply while you work. Play the conversation through to its end: wherever you would stop and wait for me, take my answer from this script and carry on. Write only your own side; don't write my lines out. I say yes to no card I don't name here.)

1. When you ask for my commander: "Meren of Clan Nel Toth."
2. When you start on lands: "Skip lands for now. Let's do ramp."
3. In ramp: "Add Sol Ring."
4. If you tell me you can't look a card up and ask me for its text: "It's an artifact that costs 1. Its text is: {T}: Add {C}{C}."
5. Then: "That's all for now. Show me the deck page."
6. To any other question: "Nothing more from me on that. Carry on."
