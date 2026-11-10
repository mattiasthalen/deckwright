---
# AC28: every card that goes in by swap, or onto the maybeboard, was named in a deck.py lookup earlier in the trace: no swap's IN and no maybeboard add's card without one before it.
type: regex
target: trace
flags: i
match: not_contains
pattern: '"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:''|\\\")?\s+(?:swap(?:\b|(?<=\\n))(?:\s+--deck\s+\S+)?\s+''(?:[^'']|''\\\\'''')*''|maybeboard(?:\s+--deck\s+\S+)?\s+add(?:\b|(?<=\\n))(?:\s+--deck\s+\S+)?)\s+''(?<in>(?:[^'']|''\\\\'''')+)''(?<!"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:''|\\\")?\s+lookup(?:\b|(?<=\\n))(?:[^"\\]|\\.)*?''\k<in>''[\s\S]*)'
---
