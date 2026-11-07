---
description: "A commander that cannot be one, a misspelt card, a card outside the commander's colours, a card named twice, and a Game Changer in a bracket 2 deck: each said, flagged and left to the player."
tags: [traps, network]
plugins: ["../../plugins/deckwright"]
max_turns: 120
timeout_seconds: 1800
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit]
---
help me build a commander deck

(Everything below is my side of the conversation, written in advance because I can't reply while you work. Play the conversation through to its end: wherever you would stop and wait for me, take my answer from this script and carry on. Write only your own side; don't write my lines out. I say yes to no card I don't name here.)

1. When you ask for my commander: "Llanowar Elves."
2. If you tell me it can't be a commander and ask whether to keep it or choose another: "Oh. Then Meren of Clan Nel Toth."
3. When you start on lands: "Skip lands for now. Let's do ramp."
4. In ramp, one at a time:
   - "Add Sol Ring."
   - "Add Vampiric Tutr." If you say you couldn't find that and ask whether I meant another card: "Yes, that one."
   - If you tell me a card would push the deck past its bracket: "Keep it anyway."
   - "Add Lightning Bolt." If you tell me it's outside my commander's colours: "Keep it anyway."
   - If you tell me a card isn't ramp: "Put it wherever it counts."
   - "Add Sol Ring."
5. If you tell me Sol Ring is already in: "Right, never mind then."
6. Then: "Stop here and show me the deck page."
7. To any other question: "Nothing more from me on that. Carry on."
