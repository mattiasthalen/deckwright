---
# E1: nothing is recorded for the misspelling until it has been looked up, and the card recorded is the real one by its real name.
type: regex
target: trace
match: not_contains
pattern: '^(?:(?!"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:[^"\\]|\\.)*?\blookup\b(?:[^"\\]|\\.)*?Vampiric Tutr)[\s\S])*?"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:[^"\\]|\\.)*?\badd\b(?:[^"\\]|\\.)*?Vampiric Tut'
---
