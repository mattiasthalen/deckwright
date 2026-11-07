---
# AC20: a tally runs after the lands are recorded and before Sol Ring is.
type: regex
target: trace
pattern: '"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:[^"\\]|\\.)*?\badd\b(?:[^"\\]|\\.)*?(?:Swamp|Forest|Command Tower)(?:(?!"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:[^"\\]|\\.)*?\badd\b(?:[^"\\]|\\.)*?Sol Ring)[\s\S])*?"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:[^"\\]|\\.)*?\btally\b'
---
