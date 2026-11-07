---
description: "The player skips Lands, changes the Ramp target and jumps to Mass disruption; deckwright follows, says what changed, and later tallies and the page use the new target."
tags: [bend, network]
plugins: ["../../plugins/deckwright"]
max_turns: 120
timeout_seconds: 1800
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit]
---
help me build a commander deck

(Everything below is my side of the conversation, written in advance because I can't reply while you work. Play the conversation through to its end: wherever you would stop and wait for me, take my answer from this script and carry on. Write only your own side; don't write my lines out. I say yes to no card I don't name here.)

1. When you ask for my commander: "Meren of Clan Nel Toth."
2. When you start on lands: "Skip lands, I'll sort those out myself."
3. When you start on ramp: "This deck wants less ramp. Make the ramp target 8." Then: "Add Sol Ring."
4. When ramp is done: "Let's jump straight to mass disruption." Then: "Add Pernicious Deed."
5. Then: "That's it for today. Show me the deck page."
6. To any other question: "Nothing more from me on that. Carry on."
