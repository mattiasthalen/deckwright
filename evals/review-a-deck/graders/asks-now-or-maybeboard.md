---
# AC31: per swap: no card goes in by swap or onto the maybeboard without the question "swap it in now, or on the maybeboard?" in an assistant message after its lookup (every card offered is looked up first: incoming-looked-up-and-flagged--looked-up).
type: regex
target: trace
flags: i
match: not_contains
pattern: '"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:''|\\\")?\s+lookup(?:\b|(?<=\\n))(?:[^"\\]|\\.)*?''(?<in>(?:[^'']|''\\\\'''')+)''(?:(?<![^\n])(?![^\n]*"(?:name":"Bash"|role":"assistant"))(?=(?<L1>[^\n]*\n))\k<L1>|(?!(?<![^\n])(?![^\n]*"(?:name":"Bash"|role":"assistant")))(?!"role":"assistant"[^\n]*"type":"text","text":"(?:[^"\\]|\\.)*?(?:\b|(?<=\\n))swap(?:\b|(?<=\\n))(?:[^"\\?]|\\[^n]){0,80}?(?:\b|(?<=\\n))now(?:\b|(?<=\\n))(?:[^"\\?]|\\[^n]){0,80}?(?:\b|(?<=\\n))maybeboard(?:[^"\\?]|\\[^n]){0,40}?\?)[\s\S])*?"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:''|\\\")?\s+(?:swap(?:\b|(?<=\\n))(?:\s+--deck\s+\S+)?\s+''(?:[^'']|''\\\\'''')*''|maybeboard(?:\s+--deck\s+\S+)?\s+add(?:\b|(?<=\\n))(?:\s+--deck\s+\S+)?)\s+''\k<in>'''
---
