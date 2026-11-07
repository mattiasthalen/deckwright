---
# AC18 for Command Tower: no assistant message speaks of it before the script has looked it up. A message that says it is looking the card up (look, check, fetch) is not a description, nor is the player's answer echoed by a run playing both sides: a mention on a quoted line (> …), inside "(Taking your answer: …)", or straight after "You said:".
type: regex
target: trace
flags: i
match: not_contains
pattern: '^(?:(?!"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:[^"\\]|\\.)*?\b(?:lookup|add)\b(?:[^"\\]|\\.)*?Command Tower)[\s\S])*?"role":"assistant"[^\n]*"type":"text","text":"(?![^\n]*?(?:\b|(?<=\\n))(?:look|check|fetch))(?:[^"\\]|\\.)*?(?<!(?:\\n|")\s*>\s(?:[^"\\]|\\")*)(?<!\((?:taking )?(?:your|my) answer:?[^)\\]*)(?<!(?:\b|(?<=\\n))(?:You said|You say|You''ve told me|You give me|You asked for)[:,]?\s*\*{0,2}(?:\\"|“)?(?:add\s+)?)Command Tower'
---
