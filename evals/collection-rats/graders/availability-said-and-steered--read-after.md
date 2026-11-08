---
# C14, steered: the read runs after the Vren deck binder is made available, so it reads that binder's cards too.
type: regex
target: trace
pattern: '"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:[^"\\]|\\.)*?(?:\b|(?<=\\n))(?:available)(?:\b|(?<=\\n))(?:[^"\\]|\\.)*?--include(?:[^"\\]|\\.)*?Vren deck[\s\S]*"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:[^"\\]|\\.)*?(?:\b|(?<=\\n))(?:read)(?:\b|(?<=\\n))'
---
