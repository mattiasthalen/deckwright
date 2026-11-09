---
# AC33: after the swap that takes Grisly Salvage out, and before any maybeboard command, an assistant message names Sheoldred, Whispering One and asks whether to drop it or keep it with a new pairing (drop, remove or take off; keep or pair; a question mark).
type: regex
target: trace
flags: i
pattern: '"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:''|\\\")?\s+swap(?:\b|(?<=\\n))(?:\s+--deck\s+\S+)?\s+''Grisly Salvage''(?:(?<![^\n])(?![^\n]*"(?:name":"Bash"|role":"assistant"))(?=(?<L1>[^\n]*\n))\k<L1>|(?!(?<![^\n])(?![^\n]*"(?:name":"Bash"|role":"assistant")))(?!"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:''|\\\")?\s+maybeboard(?:\b|(?<=\\n)))[\s\S])*?"role":"assistant"[^\n]*"type":"text","text":"(?=(?:[^"\\]|\\.)*?Sheoldred)(?=(?:[^"\\]|\\.)*?(?:\b|(?<=\\n))(?:drop|remov\w*|take (?:it )?off))(?=(?:[^"\\]|\\.)*?(?:\b|(?<=\\n))(?:keep|re-?pair\w*|pair\w*))(?=(?:[^"\\]|\\.)*?\?)'
---
