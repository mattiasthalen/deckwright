---
# AC28: no assistant message speaks of Lightning Bolt, which the scripted player proposes, before the script has looked it up. A mention is not a description when a word for looking it up (look, check, fetch) sits within 60 characters of the name, in the same sentence; nor is the player's line echoed (a quoted line, a line opening on a quotation mark, "(Your answer: …)", "You said:", "You asked about", "You also asked about") or the player's ask restated ("Next, Lightning Bolt for Murder:").
type: regex
target: trace
flags: i
match: not_contains
pattern: '^(?:(?<![^\n])(?![^\n]*"(?:name":"Bash"|role":"assistant"))(?=(?<L1>[^\n]*\n))\k<L1>|(?!(?<![^\n])(?![^\n]*"(?:name":"Bash"|role":"assistant")))(?!"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:''|\\\")?\s+(?:lookup|add|swap|maybeboard)(?:\b|(?<=\\n))(?:[^"\\]|\\.)*?Lightning Bolt)[\s\S])*?"role":"assistant"[^\n]*"type":"text","text":"(?:[^"\\]|\\.)*?(?=Lightning Bolt)(?<!(?:\\n|")\s*>\s(?:[^"\\]|\\")*)(?<!(?:\\n|")\s*\*{0,2}(?:\\"|“)(?:[^"\\”]|\\[^"n])*)(?<!\((?:taking )?(?:your|my) answer:?[^)]{0,40})(?<!(?:\b|(?<=\\n))(?:You said|You say|You''ve told me|You give me|You(?: also)? asked for|You(?: also)? asked about|You proposed|You suggest(?:ed)?)[:,]?\s*\*{0,2}(?:\\\"|“)?(?:add\s+)?)(?<!(?:\b|(?<=\\n))(?:look|check|fetch)(?:[^"\\.!?]|\\[^n]){0,60})(?:(?<!(?:\b|(?<=\\n))(?:Next|Now|Then|And)[:,]?\s*\*{0,2})Lightning Bolt|Lightning Bolt(?!\*{0,2}\s+for\s+(?:[^"\\.:?]|\\[^n]){1,40}?\*{0,2}[:?]))(?!(?:[^"\\.!?]|\\[^n]){0,60}?(?:\b|(?<=\\n))(?:look|check|fetch))'
---
