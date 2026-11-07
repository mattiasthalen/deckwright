---
# AC17, where it counts: before Sign in Blood is recorded, an assistant message names Card advantage, in the same window as wrong-category-called-out.
type: regex
target: trace
flags: i
pattern: '^(?:(?!"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:[^"\\]|\\.)*?(?:\b|(?<=\\n))add(?:\b|(?<=\\n))(?:[^"\\]|\\.)*?Sign in Blood)[\s\S])*?"role":"assistant"[^\n]*"type":"text","text":"(?:[^"\\]|\\.)*?(?:Sign in Blood(?=(?:(?!Sol Ring|\?)(?:[^"\\]|\\.)){0,600}?(?:(?:\b|(?<=\\n))card advantage(?:\b|(?<=\\n))))|(?:(?:\b|(?<=\\n))card advantage(?:\b|(?<=\\n)))(?=(?:(?!Sol Ring|\?)(?:[^"\\]|\\.)){0,300}?(?:Sign in Blood)))'
---
