---
# AC28: no assistant message speaks of Demonic Tutor, which the scripted player proposes, before the script has looked it up. A message that says it is looking the card up (look, check, fetch) is not a description, nor is the player's line echoed (a quoted line, "(Your answer: …)", "You said:", "You asked about").
type: regex
target: trace
flags: i
match: not_contains
pattern: '^(?:(?<![^\n])(?![^\n]*"(?:name":"Bash"|role":"assistant"))(?=(?<L1>[^\n]*\n))\k<L1>|(?!(?<![^\n])(?![^\n]*"(?:name":"Bash"|role":"assistant")))(?!"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:''|\\\")?\s+(?:lookup|add|swap|maybeboard)(?:\b|(?<=\\n))(?:[^"\\]|\\.)*?Demonic Tutor)[\s\S])*?"role":"assistant"[^\n]*"type":"text","text":"(?![^\n]*?(?:\b|(?<=\\n))(?:look|check|fetch))(?:[^"\\]|\\.)*?(?=Demonic Tutor)(?<!(?:\\n|")\s*>\s(?:[^"\\]|\\")*)(?<!\((?:taking )?(?:your|my) answer:?[^)]{0,40})(?<!(?:\b|(?<=\\n))(?:You said|You say|You''ve told me|You give me|You asked for|You asked about|You proposed|You suggest(?:ed)?)[:,]?\s*\*{0,2}(?:\\\"|“)?(?:add\s+)?)Demonic Tutor'
---
