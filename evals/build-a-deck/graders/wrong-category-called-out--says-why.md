---
# AC17, the why: before Sign in Blood is recorded, an assistant message says it makes no mana or puts no lands into play, in the same window as wrong-category-called-out.
type: regex
target: trace
flags: i
pattern: '^(?:(?<![^\n])(?![^\n]*"(?:name":"Bash"|role":"assistant"))(?=(?<L1>[^\n]*\n))\k<L1>|(?!(?<![^\n])(?![^\n]*"(?:name":"Bash"|role":"assistant")))(?!"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:[^"\\]|\\.)*?(?:\b|(?<=\\n))add(?:\b|(?<=\\n))(?:[^"\\]|\\.)*?Sign in Blood)[\s\S])*?"role":"assistant"[^\n]*"type":"text","text":"(?:[^"\\]|\\.)*?(?:Sign in Blood(?=(?:(?!Sol Ring|\?)(?:[^"\\]|\\.)){0,600}?(?:(?:\b|(?<=\\n))(?:makes|adds|produces|gives|generates|puts)\s+no\s+(?:\w+\s+)?(?:mana|lands?)(?:\b|(?<=\\n))|(?:\b|(?<=\\n))no\s+(?:extra\s+)?mana(?:\b|(?<=\\n))|(?:\b|(?<=\\n))not\s+mana(?:\b|(?<=\\n))|(?:doesn''t|doesn’t|does not|won''t|can''t|never)\s+(?:\w+\s+){0,3}?(?:mana|lands?)(?:\b|(?<=\\n))))|(?:(?:\b|(?<=\\n))(?:makes|adds|produces|gives|generates|puts)\s+no\s+(?:\w+\s+)?(?:mana|lands?)(?:\b|(?<=\\n))|(?:\b|(?<=\\n))no\s+(?:extra\s+)?mana(?:\b|(?<=\\n))|(?:\b|(?<=\\n))not\s+mana(?:\b|(?<=\\n))|(?:doesn''t|doesn’t|does not|won''t|can''t|never)\s+(?:\w+\s+){0,3}?(?:mana|lands?)(?:\b|(?<=\\n)))(?=(?:(?!Sol Ring|\?)(?:[^"\\]|\\.)){0,300}?(?:Sign in Blood)))'
---
