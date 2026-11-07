---
# AC16: before Sol Ring is recorded, or after it and before the next Bash call, an assistant message speaks of Sol Ring outside a suggestion list and, before the next list item or Sign in Blood, says what it does (two colourless mana) and that it counts in Ramp.
type: regex
target: trace
flags: i
pattern: '^(?:(?!"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:[^"\\]|\\.)*?(?:\b|(?<=\\n))add(?:\b|(?<=\\n))(?:[^"\\]|\\.)*?Sol Ring)[\s\S])*?(?:"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:[^"\\]|\\.)*?(?:\b|(?<=\\n))add(?:\b|(?<=\\n))(?:[^"\\]|\\.)*?Sol Ring(?:(?!"name":"Bash")[\s\S])*?)?"role":"assistant"[^\n]*"type":"text","text":"(?:[^"\\]|\\.)*?(?<!(?:\\n|")\s*(?:[-*•]|\d+[.)])\s+(?:\*\*)?)Sol Ring(?=(?:(?!Sign in Blood|\\n\s*(?:[-*•]|\d+[.)])\s)(?:[^"\\]|\\.)){0,600}?(?:\{C\}\s?\{C\}|(?:\b|(?<=\\n))(?:two|2) (?:colou?rless|mana)(?:\b|(?<=\\n))|colou?rless mana))(?=(?:(?!Sign in Blood|\\n\s*(?:[-*•]|\d+[.)])\s)(?:[^"\\]|\\.)){0,600}?(?:(?:\b|(?<=\\n))ramp(?:\b|(?<=\\n))))'
---
