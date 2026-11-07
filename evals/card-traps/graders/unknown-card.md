---
# E1: after "Vampiric Tutr" is looked up and before Vampiric Tutor is recorded, an assistant message says the name was not found and, within 600 characters, names Vampiric Tutor and asks whether that is the card meant.
type: regex
target: trace
flags: i
pattern: '^(?:(?!"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:[^"\\]|\\.)*?(?:\b|(?<=\\n))add(?:\b|(?<=\\n))(?:[^"\\]|\\.)*?Vampiric Tut)[\s\S])*?"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:[^"\\]|\\.)*?(?:\b|(?<=\\n))lookup(?:\b|(?<=\\n))(?:[^"\\]|\\.)*?Vampiric Tutr(?:(?!"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:[^"\\]|\\.)*?(?:\b|(?<=\\n))add(?:\b|(?<=\\n))(?:[^"\\]|\\.)*?Vampiric Tut)[\s\S])*?"role":"assistant"[^\n]*"type":"text","text":"(?:[^"\\]|\\.)*?(?:(?:couldn''t|couldn’t|could not|can''t|cannot|didn''t|did not|wasn''t able to|unable to)\s+(?:\w+\s+){0,2}?(?:find|match|locate)|(?:\b|(?<=\\n))no (?:exact )?(?:card|match)(?:\b|(?<=\\n))|(?:\b|(?<=\\n))not found(?:\b|(?<=\\n))|(?:\b|(?<=\\n))doesn''t exist|(?:\b|(?<=\\n))does not exist|(?:\b|(?<=\\n))no card (?:by|with|named))(?=(?:[^"\\]|\\.){0,600}?(?:(?:\b|(?<=\\n))Vampiric Tutor(?:\b|(?<=\\n))))(?=(?:[^"\\]|\\.){0,600}?(?:(?:\b|(?<=\\n))(?:mean|meant|confirm|that one|Vampiric Tutor)(?:\b|(?<=\\n))(?:[^"\\.!?]|\\[^n])*\?))'
---
