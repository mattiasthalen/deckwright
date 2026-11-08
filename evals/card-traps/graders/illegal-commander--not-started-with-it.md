---
# E7: no deck is started with Llanowar Elves as its commander.
type: regex
target: trace
match: not_contains
pattern: '"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:[^"\\]|\\.)*?(?:\b|(?<=\\n))new(?:\b|(?<=\\n))(?:[^"\\]|\\.)*?Llanowar Elves'
---
