---
# AC28: the planted card outside the colour identity. After Lightning Bolt is looked up, an assistant message names it and says it is outside Meren's colours: colour identity, off-colour, outside or not in the colours, or red against black or green.
type: regex
target: trace
flags: i
pattern: '"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:''|\\\")?\s+lookup(?:\b|(?<=\\n))(?:[^"\\]|\\.)*?Lightning Bolt(?:(?<![^\n])(?![^\n]*"(?:name":"Bash"|role":"assistant"))(?=(?<L1>[^\n]*\n))\k<L1>|(?!(?<![^\n])(?![^\n]*"(?:name":"Bash"|role":"assistant")))[\s\S])*?"role":"assistant"[^\n]*"type":"text","text":"(?=(?:[^"\\]|\\.)*?Lightning Bolt)(?=(?:[^"\\]|\\.)*?(?:colou?r identity|off[- ]colou?r|outside(?:[^"\\.!?]|\\[^n]){0,60}?colou?rs?|not in(?:[^"\\.!?]|\\[^n]){0,40}?colou?rs?|\bred\b(?:[^"\\]|\\.){0,300}?(?:black|green|Golgari)))'
---
