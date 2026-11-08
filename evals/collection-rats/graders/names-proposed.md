---
# C31: before the deck is started (new), an assistant message speaks of the deck's name and offers at least two, each a list item or a bold, quoted or italic name.
type: regex
target: trace
flags: i
pattern: '^(?:(?<![^\n])(?![^\n]*"(?:name":"Bash"|role":"assistant"))(?=(?<L1>[^\n]*\n))\k<L1>|(?!(?<![^\n])(?![^\n]*"(?:name":"Bash"|role":"assistant")))(?!"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:[^"\\]|\\.)*?(?:\b|(?<=\\n))(?:new)(?:\b|(?<=\\n)))[\s\S])*?"role":"assistant"[^\n]*"type":"text","text":"(?:[^"\\]|\\.)*?(?:\b|(?<=\\n))(?:names?|call (?:it|the deck|this deck))(?:\b|(?<=\\n))(?:[^"\\]|\\.){0,300}?(?:\\n\s*(?:[-*•]|\d+[.)])\s+(?:\*\*|__|\[)?|(?:\*\*|\\"|“|_)(?=[A-Z]))(?:[^"\\]|\\.){2,200}?(?:\\n\s*(?:[-*•]|\d+[.)])\s+(?:\*\*|__|\[)?|(?:\*\*|\\"|“|_)(?=[A-Z]))'
---
