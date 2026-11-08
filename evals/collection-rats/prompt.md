---
description: "A collection export with a deck binder: availability said and steered, the read before any suggestion, theme first, a category the collection cannot fill, one question about cards not owned, names proposed beside the decks there are, and a theme that fits its commander."
tags: [collection, theme, network]
plugins: ["../../plugins/deckwright"]
max_turns: 120
timeout_seconds: 1800
append_system_prompt: "The player in this session is scripted and cannot reply while it runs: their whole side of the conversation is already in the first user message, written in advance, and this session is a single turn. Talk to them as you would to a live player, saying and asking everything you would say and ask. Where you would then end your turn to wait for their reply, do not: take their reply from the script and carry on in the same turn. End your turn only after you have answered the last line of the script that applies. Do not write the player's lines out yourself."
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit]
---
help me build a commander deck from my collection. My ManaBox export is ManaBox_Collection.csv in this folder.

(Everything below is my side of the conversation, written in advance because I can't reply while you work. Play the conversation through to its end: wherever you would stop and wait for me, take my answer from this script and carry on. Write only your own side; don't write my lines out. I say yes to no card I don't name here.)

1. When you ask for my commander: "Vren, the Relentless."
2. When you ask what to call the deck: "Rat Pack."
3. When you ask for a theme: "Bloomburrow rats."
4. When you tell me what is held back in my deck binders: "Use the cards in my Vren deck too."
5. For lands: "Add 20 Island, 14 Swamp and Mudflat Village. That's all the lands for now."
6. If you ask whether to use cards I don't own: "Yes, that's fine."
7. For ramp, once you've offered suggestions: "Add Blitzball. And add Talisman of Dominance."
8. When ramp is done: "Add Thought Shucker."
9. Then: "Let's stop there for today. Show me the deck page."
10. To any other question: "Nothing more from me on that. Carry on."
