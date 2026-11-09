---
# AC37: past the deck size, the skill asks which card goes out (which or what … goes out, comes out, cut, remove, make room …?) before measure runs. A `measure` that refused ("Nothing was measured.", a probe at 99) does not count as the review running.
type: regex
target: trace
flags: i
pattern: '^(?:(?<![^\n])(?![^\n]*"(?:name":"Bash"|role":"assistant"))(?=(?<L1>[^\n]*\n))\k<L1>|(?!(?<![^\n])(?![^\n]*"(?:name":"Bash"|role":"assistant")))(?!"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:''|\\\")?\s+measure(?:\b|(?<=\\n))(?!(?:(?!"type":"tool_result")[\s\S])*?"type":"tool_result"[^\n]*?Nothing was measured))[\s\S])*?"role":"assistant"[^\n]*"type":"text","text":"(?:[^"\\]|\\.)*?(?:\b|(?<=\\n))(?:which|what)(?:\b|(?<=\\n))(?:[^"\\?]|\\[^n]){0,80}?(?:\b|(?<=\\n))(?:go(?:es)? out|come out|comes out|take out|cut|remove|make room|drop|swap out)(?:[^"\\?]|\\[^n]){0,120}?\?'
---
