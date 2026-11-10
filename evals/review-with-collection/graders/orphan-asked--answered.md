---
# AC33: the player keeps it with the new pairing: after that swap, Sheoldred is taken off the maybeboard and put back on it, paired anew (a remove, then an add).
type: regex
target: trace
flags: i
pattern: '"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:''|\\\")?\s+swap(?:\b|(?<=\\n))(?:\s+--deck\s+\S+)?\s+''Grisly Salvage''[\s\S]*?"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:''|\\\")?\s+maybeboard(?:\s+--deck\s+\S+)?\s+remove(?:\b|(?<=\\n))(?:[^"\\]|\\.)*?Sheoldred[\s\S]*?"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:''|\\\")?\s+maybeboard(?:\s+--deck\s+\S+)?\s+add(?:\b|(?<=\\n))(?:[^"\\]|\\.)*?Sheoldred'
---
