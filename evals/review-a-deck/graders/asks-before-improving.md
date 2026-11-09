---
# AC25: after the review is recorded, an assistant message asks whether the player wants improvements suggested (want, like, shall or should … improve …?), and before it no card is looked up and nothing is swapped or put on the maybeboard: nothing is suggested before the answer.
type: regex
target: trace
flags: i
pattern: '"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:''|\\\")?\s+review(?:\b|(?<=\\n))(?:(?<![^\n])(?![^\n]*"(?:name":"Bash"|role":"assistant"))(?=(?<L1>[^\n]*\n))\k<L1>|(?!(?<![^\n])(?![^\n]*"(?:name":"Bash"|role":"assistant")))(?!"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:''|\\\")?\s+(?:lookup(?:\b|(?<=\\n))|(?:swap|maybeboard)(?:\b|(?<=\\n))))[\s\S])*?"role":"assistant"[^\n]*"type":"text","text":"(?:[^"\\]|\\.)*?(?:\b|(?<=\\n))(?:want|like|shall|should)(?:\b|(?<=\\n))(?:[^"\\?]|\\[^n]){0,80}?(?:\b|(?<=\\n))improv\w*(?:[^"\\?]|\\[^n]){0,80}?\?'
---
