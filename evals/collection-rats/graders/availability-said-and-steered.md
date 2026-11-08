---
# C14, said at the start: before any assistant message gives a category its target, one says how many copies it holds back from the deck binder, 6, within 200 characters of the binder's name, Vren deck.
type: regex
target: trace
flags: i
pattern: '^(?:(?<![^\n])(?![^\n]*"(?:name":"Bash"|role":"assistant"))(?=(?<L1>[^\n]*\n))\k<L1>|(?!(?<![^\n])(?![^\n]*"(?:name":"Bash"|role":"assistant")))(?!"role":"assistant"[^\n]*"type":"text","text":"(?:[^"\\]|\\.)*?(?:\b|(?<=\\n))(?:Lands|Ramp|Card advantage|Targeted disruption|Mass disruption|Plan)(?:\b|(?<=\\n))(?:[^"\\]|\\.){0,40}?(?:\b|(?<=\\n))(?:38|10|12|6|30)(?:\b|(?<=\\n)))[\s\S])*?"role":"assistant"[^\n]*"type":"text","text":"(?:[^"\\]|\\.)*?(?:Vren[^a-zA-Z0-9"]{0,6}deck(?=(?:[^"\\]|\\.){0,200}?(?:\b|(?<=\\n))(?:6|six)(?:\b|(?<=\\n)))|(?:\b|(?<=\\n))(?:6|six)(?:\b|(?<=\\n))(?=(?:[^"\\]|\\.){0,200}?Vren[^a-zA-Z0-9"]{0,6}deck))'
---
