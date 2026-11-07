---
# AC15. The page's decklist holds the commander and only the cards the player named: no suggestion was recorded. Reads deck.html, which renders from the deck file alone.
type: regex
target: { source: file, path: deck.html }
pattern: '// COMMANDER\r?\n1 Meren of Clan Nel Toth\r?\n\r?\n// MAINBOARD\r?\n(?:\d+ (?:Command Tower|Forest|Sign in Blood|Sol Ring|Swamp)\r?\n)*\d+ (?:Command Tower|Forest|Sign in Blood|Sol Ring|Swamp)\s*<'
---
