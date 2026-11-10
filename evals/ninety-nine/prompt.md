---
description: "A deck at 99 cards with every category done: the last card asked for, then a second card past the deck size, which card goes out asked before the review; the review only once the deck holds 100."
tags: [review, network]
plugins: ["../../plugins/deckwright"]
max_turns: 150
timeout_seconds: 2400
append_system_prompt: "The player in this session is scripted and cannot reply while it runs: their whole side of the conversation is already in the first user message, written in advance, and this session is a single turn. Talk to them as you would to a live player, saying and asking everything you would say and ask. Where you would then end your turn to wait for their reply, do not: take their reply from the script and carry on in the same turn. End your turn only after you have answered the last line of the script that applies. Do not write the player's lines out yourself."
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit]
---
let's finish my commander deck: Meren Recursion, in decks/ in this folder.

(Everything below is my side of the conversation, written in advance because I can't reply while you work. Play the conversation through to its end: wherever you would stop and wait for me, take my answer from this script and carry on. Write only your own side; don't write my lines out. I say yes only where this script says yes.)

1. If you ask which deck, or whether to pick one up: "Meren Recursion. Let's finish it."
2. When you ask me for the last card, or for more cards: "Add Eternal Witness. And add Ravenous Chupacabra."
3. If you ask which card goes out, or which cards to cut: "Take out Grisly Salvage."
4. When you ask whether I want you to suggest deck improvements: "No improvements this time. But would Demonic Tutor or Lightning Bolt be worth a place? Tell me what you think." Whatever you say about them: "Then leave them out. Show me the deck page."
5. To any other question: "Nothing more from me on that. Carry on."
