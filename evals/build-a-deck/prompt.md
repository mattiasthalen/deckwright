---
description: "Commander first, then Lands and Ramp in template order, with suggestions, critique, a declined suggestion, a card filed under the wrong category and a collection mention, then an early stop and the page."
tags: [build, network]
plugins: ["../../plugins/deckwright"]
max_turns: 120
timeout_seconds: 1800
append_system_prompt: "The player in this session is scripted and cannot reply while it runs: their whole side of the conversation is already in the first user message, written in advance, and this session is a single turn. Talk to them as you would to a live player, saying and asking everything you would say and ask. Where you would then end your turn to wait for their reply, do not: take their reply from the script and carry on in the same turn. End your turn only after you have answered the last line of the script that applies. Do not write the player's lines out yourself."
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit]
---
help me build a commander deck

(Everything below is my side of the conversation, written in advance because I can't reply while you work. Play the conversation through to its end: wherever you would stop and wait for me, take my answer from this script and carry on. Write only your own side; don't write my lines out. I say yes to no card I don't name here.)

1. When you ask for my commander: "Meren of Clan Nel Toth."
2. For lands: "Command Tower, 18 Swamp and 17 Forest. That's all the lands for now."
3. For ramp, once you've offered suggestions: "No thanks to the first one you suggested." Then: "Add Sol Ring." Then: "Add Sign in Blood as ramp."
4. If you tell me Sign in Blood isn't ramp: "Fair enough, put it under card advantage then."
5. When ramp is done: "By the way, I've got a big collection. Can you build from the cards I own?"
   Whenever you ask me for my collection: "No collection."
6. Then: "Let's stop there for today. Show me the deck page."
7. To any other question: "Nothing more from me on that. Carry on."
