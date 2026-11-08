---
# C26: the question comes before the 20 Island are recorded.
type: regex
target: trace
flags: i
pattern: '^(?:(?<![^\n])(?![^\n]*"(?:name":"Bash"|role":"assistant"))(?=(?<L1>[^\n]*\n))\k<L1>|(?!(?<![^\n])(?![^\n]*"(?:name":"Bash"|role":"assistant")))(?!"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:[^"\\]|\\.)*?(?:\b|(?<=\\n))(?:add)(?:\b|(?<=\\n))(?:[^"\\]|\\.)*?Island)[\s\S])*?"role":"assistant"[^\n]*"type":"text","text":"(?:[^"\\]|\\.)*?(?:(?:don\x27t|don’t|do not) own|not in your collection|aren\x27t in your collection|aren’t in your collection|not[- ]owned|unowned|cards? (?:you\x27re|you’re|you are) missing)(?:[^"\\.!?]|\\[^n]){0,80}\?'
---
