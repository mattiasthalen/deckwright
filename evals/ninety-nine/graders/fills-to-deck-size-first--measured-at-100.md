---
# AC36: the review runs only once the deck holds 100: Eternal Witness, the last card, is recorded before measure first runs. A `measure` that refused ("Nothing was measured.", a probe at 99) does not count as the review running.
type: regex
target: trace
flags: i
pattern: '^(?:(?<![^\n])(?![^\n]*"(?:name":"Bash"|role":"assistant"))(?=(?<L1>[^\n]*\n))\k<L1>|(?!(?<![^\n])(?![^\n]*"(?:name":"Bash"|role":"assistant")))(?!"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:''|\\\")?\s+measure(?:\b|(?<=\\n))(?!(?:(?!"type":"tool_result")[\s\S])*?"type":"tool_result"[^\n]*?Nothing was measured))[\s\S])*?"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:''|\\\")?\s+(?:add(?:\b|(?<=\\n))|swap(?:\b|(?<=\\n)))(?:[^"\\]|\\.)*?Eternal Witness'
---
