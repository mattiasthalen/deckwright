---
# AC28: no assistant message speaks of Eternal Witness, which the player adds, before the script has looked it up (or recorded it). A message that says it is looking the card up is not a description, nor is the player's line echoed.
type: regex
target: trace
flags: i
match: not_contains
pattern: '^(?:(?<![^\n])(?![^\n]*"(?:name":"Bash"|role":"assistant"))(?=(?<L1>[^\n]*\n))\k<L1>|(?!(?<![^\n])(?![^\n]*"(?:name":"Bash"|role":"assistant")))(?!"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:''|\\\")?\s+(?:lookup|add|swap|maybeboard)(?:\b|(?<=\\n))(?:[^"\\]|\\.)*?Eternal Witness)[\s\S])*?"role":"assistant"[^\n]*"type":"text","text":"(?![^\n]*?(?:\b|(?<=\\n))(?:look|check|fetch))(?:[^"\\]|\\.)*?(?=Eternal Witness)(?<!(?:\\n|")\s*>\s(?:[^"\\]|\\")*)(?<!\((?:taking )?(?:your|my) answer:?[^)]{0,40})(?<!(?:\b|(?<=\\n))(?:You said|You say|You''ve told me|You give me|You asked for|You asked about|You proposed|You suggest(?:ed)?)[:,]?\s*\*{0,2}(?:\\\"|“)?(?:add\s+)?)Eternal Witness'
---
