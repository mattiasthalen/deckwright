---
description: "A finished 100-card deck built from the collection with \"not owned: no\": reviewed, then improved from both the player's cards and cards they do not own; owned cards swapped in, the rest put on the maybeboard; a swap that orphans a maybeboard entry asked about first; the review run again after the swaps, before the page."
tags: [review, collection, network]
plugins: ["../../plugins/deckwright"]
max_turns: 200
timeout_seconds: 3000
append_system_prompt: "The player in this session is scripted and cannot reply while it runs: their whole side of the conversation is already in the first user message, written in advance, and this session is a single turn. Talk to them as you would to a live player, saying and asking everything you would say and ask. Where you would then end your turn to wait for their reply, do not: take their reply from the script and carry on in the same turn. End your turn only after you have answered the last line of the script that applies. Do not write the player's lines out yourself."
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit]
---
review my commander deck. It's finished: Meren Recursion, in decks/ in this folder. My collection is collection.txt in this folder.

(Everything below is my side of the conversation, written in advance because I can't reply while you work. Play the conversation through to its end: wherever you would stop and wait for me, take my answer from this script and carry on. Write only your own side; don't write my lines out. I say yes only where this script says yes.)

1. If you ask which deck, or whether to pick one up: "Meren Recursion. It's finished."
2. When you ask whether I want you to suggest deck improvements: "Yes, please."
3. When you ask whether to suggest from my cards, cards I don't own, or both: "Both."
4. To the first swap you suggest: "No, not that one."
5. To each swap you suggest after that: "Yes." That is a yes to swapping it in now when you ask that, and a yes to the maybeboard when you ask that.
6. After the second swap you suggest: "Could Satyr Wayfinder go in for Grisly Salvage?" When you ask whether to swap it in: "Yes, swap it in."
7. If you ask what to do with a maybeboard card whose pair has gone out: "Keep it, with the new pairing you suggest."
8. Then: "Could Demonic Tutor go in for Murder? Tell me what you think first." Whatever you say about it: "No, leave it out then."
   Then: "And Lightning Bolt for Doom Blade?" Whatever you say about it: "No, leave that out too."
9. After the fifth swap you suggest: "That's all the improvements. Show me the deck page."
10. To any other question: "Nothing more from me on that. Carry on."
