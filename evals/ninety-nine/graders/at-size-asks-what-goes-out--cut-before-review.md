---
# AC37: the player's answer, Grisly Salvage out, is carried out (a remove, or a swap taking it out) before measure runs.
type: regex
target: trace
flags: i
pattern: '^(?:(?<![^\n])(?![^\n]*"(?:name":"Bash"|role":"assistant"))(?=(?<L1>[^\n]*\n))\k<L1>|(?!(?<![^\n])(?![^\n]*"(?:name":"Bash"|role":"assistant")))(?!"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:''|\\\")?\s+measure(?:\b|(?<=\\n)))[\s\S])*?"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:''|\\\")?\s+(?:remove(?:\b|(?<=\\n))|swap(?:\b|(?<=\\n)))(?:\s+--deck\s+\S+)?\s+''Grisly Salvage'''
---
