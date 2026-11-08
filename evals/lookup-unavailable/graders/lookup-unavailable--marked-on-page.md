---
# E2: the page marks it as the player's text.
type: regex
target: { source: file, path: decks/meren-of-clan-nel-toth.html }
pattern: 'data-section="player-text"[^>]*>(?:(?!data-section=)[\s\S])*?Sol Ring'
---
