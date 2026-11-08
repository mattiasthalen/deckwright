---
# C31: before the deck is started, an assistant message names the deck already in decks/, meren-graveyard (an S1 deck file, listed by its file's name).
type: regex
target: trace
flags: i
pattern: '^(?:(?<![^\n])(?![^\n]*"(?:name":"Bash"|role":"assistant"))(?=(?<L1>[^\n]*\n))\k<L1>|(?!(?<![^\n])(?![^\n]*"(?:name":"Bash"|role":"assistant")))(?!"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:[^"\\]|\\.)*?(?:\b|(?<=\\n))(?:new)(?:\b|(?<=\\n)))[\s\S])*?"role":"assistant"[^\n]*"type":"text","text":"(?:[^"\\]|\\.)*?meren[- ]graveyard'
---
