---
# AC26: before the first swap or maybeboard add, an assistant message asks whether to suggest from the player's cards, cards they don't own, or both (your cards or collection, don't own, both …?).
type: regex
target: trace
flags: i
pattern: '^(?:(?<![^\n])(?![^\n]*"(?:name":"Bash"|role":"assistant"))(?=(?<L1>[^\n]*\n))\k<L1>|(?!(?<![^\n])(?![^\n]*"(?:name":"Bash"|role":"assistant")))(?!"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:''|\\\")?\s+(?:swap|maybeboard)(?:\b|(?<=\\n)))[\s\S])*?"role":"assistant"[^\n]*"type":"text","text":"(?=(?:[^"\\]|\\.)*?(?:your (?:own )?cards|your collection|cards you own|what you own))(?=(?:[^"\\]|\\.)*?(?:don''t|don’t|do not|not) own)(?=(?:[^"\\]|\\.)*?(?:\b|(?<=\\n))both(?:\b|(?<=\\n))(?:[^"\\?]|\\[^n]){0,60}?\?)'
---
