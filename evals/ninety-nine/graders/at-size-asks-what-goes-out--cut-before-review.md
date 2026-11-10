---
# AC37: the player's answer, Grisly Salvage out, is carried out (a remove, or a swap taking it out) before measure runs. A `measure` that refused ("Nothing was measured.", a probe at 99) does not count as the review running.
type: regex
target: trace
flags: i
pattern: '^(?:(?<![^\n])(?![^\n]*"(?:name":"Bash"|role":"assistant"))(?=(?<L1>[^\n]*\n))\k<L1>|(?!(?<![^\n])(?![^\n]*"(?:name":"Bash"|role":"assistant")))(?!"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:''|\\\")?\s+measure(?:\b|(?<=\\n))(?!(?:(?!"type":"tool_result")[\s\S])*?"type":"tool_result"[^\n]*?Nothing was measured))[\s\S])*?"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:''|\\\")?\s+(?:remove(?:\b|(?<=\\n))|swap(?:\b|(?<=\\n)))(?:\s+--deck\s+\S+)?\s+''Grisly Salvage'''
---
