// The number check (AC22): every number in a written review is one `measure` printed, or the tally.
//
//   node evals/tools/review-numbers.mjs <deck file> <tally file>
//
// Run over each kept run's workspace after an eval with --keep-temp: the deck file is the run's
// decks/<file name>.json, and the tally file that run's `deck.py tally --deck …` stdout, saved.
//
// It reads the written review (`review.text`), strips the name of every card the deck file names
// (the commander, the cards and their faces, the swaps, the maybeboard), drops turn spans ("turns
// 4–6", "turns 7-9", "turns 7+", "turns 7 and on"), and reads what numbers are left. A number is
// carried when it equals a number anywhere in the stored measures (`review.measures`) or the tally,
// at any depth. A single "turn 8" is not a span, so its 8 must be carried like any other number.
//
// Exit 0 when every number is carried; 1 when one is not, printing each such number on a line of
// its own; 2 when the deck file has no written review, or the files cannot be read.
import fs from 'fs';

const [deckPath, tallyPath] = process.argv.slice(2);
if (!deckPath || !tallyPath) {
  console.error('usage: node review-numbers.mjs <deck file> <tally file>');
  process.exit(2);
}

let deck;
let tally;
try {
  deck = JSON.parse(fs.readFileSync(deckPath, 'utf8'));
  tally = JSON.parse(fs.readFileSync(tallyPath, 'utf8'));
} catch (error) {
  console.error(`review-numbers: cannot read the files: ${error.message}`);
  process.exit(2);
}
const text = deck?.review?.text;
if (typeof text !== 'string') {
  console.error(`review-numbers: ${deckPath} has no written review (review.text)`);
  process.exit(2);
}

const carried = new Set();
(function collect(value) {
  if (typeof value === 'number') carried.add(value);
  else if (Array.isArray(value)) value.forEach(collect);
  else if (value && typeof value === 'object') Object.values(value).forEach(collect);
})([deck.review.measures, tally]);

const names = new Set();
const addName = (name) => {
  if (typeof name !== 'string' || !name) return;
  names.add(name);
  for (const face of name.split(' // ')) names.add(face);
};
addName(deck.commander?.name);
for (const entry of deck.cards || []) addName(entry?.card?.name);
for (const swap of deck.swaps || []) { addName(swap?.out); addName(swap?.in); }
for (const entry of deck.maybeboard || []) { addName(entry?.name); addName(entry?.replaces); }

const escape = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
let rest = text;
for (const name of [...names].sort((a, b) => b.length - a.length)) {
  rest = rest.replace(new RegExp(escape(name), 'gi'), ' ');
}
rest = rest
  .replace(/\bturns?\s+\d+\s*(?:[–—-]|to|through|until)\s*\d+/gi, ' ')
  .replace(/\bturns?\s+\d+\s*(?:\+|and\s+(?:on(?:wards?)?|later|beyond|after)\b|onwards?\b)/gi, ' ');

const strays = [];
for (const match of rest.matchAll(/(?<![\d.])\d+(?:\.\d+)?/g)) {
  if (!carried.has(Number(match[0])) && !strays.includes(match[0])) strays.push(match[0]);
}
for (const stray of strays) console.log(stray);
process.exit(strays.length ? 1 : 0);
