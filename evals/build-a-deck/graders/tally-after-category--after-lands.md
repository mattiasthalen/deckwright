---
# AC20: a tally runs after the lands are recorded and before Sol Ring is, in a Bash call of its own after the one that recorded them.
type: regex
target: trace
pattern: '"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:[^"\\]|\\.)*?(?:\b|(?<=\\n))add(?:\b|(?<=\\n))(?:[^"\\]|\\.)*?(?:Swamp|Forest|Command Tower)(?:(?!"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:[^"\\]|\\.)*?(?:\b|(?<=\\n))add(?:\b|(?<=\\n))(?:[^"\\]|\\.)*?Sol Ring)[\s\S])*?(?!"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:[^"\\]|\\.)*?(?:\b|(?<=\\n))add(?:\b|(?<=\\n))(?:[^"\\]|\\.)*?Sol Ring)"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:[^"\\]|\\.)*?(?:\b|(?<=\\n))tally(?:\b|(?<=\\n))'
---
