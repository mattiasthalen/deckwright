---
# AC18 for Sign in Blood: no assistant message speaks of it before the script has looked it up. A message that says it is looking the card up (look, check, fetch) is not a description.
type: regex
target: trace
flags: i
match: not_contains
pattern: '^(?:(?!"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:[^"\\]|\\.)*?\b(?:lookup|add)\b(?:[^"\\]|\\.)*?Sign in Blood)[\s\S])*?"role":"assistant"[^\n]*"type":"text","text":"(?![^\n]*?\b(?:look|check|fetch))(?:[^"\\]|\\.)*?Sign in Blood'
---
