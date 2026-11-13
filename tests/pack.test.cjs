// The packed file pack.py makes from a deck folder, opened from disk.
//
// Run: node --test tests/*.test.cjs

const test = require('node:test');
const { before, after } = test;
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { execFileSync } = require('node:child_process');
const { REPO, PACK, FONT_HOSTS, answerFontHost, chromium, RICH_LEDGER, deckFolders, testPictures, writeSavedFiles, untilDrawn } = require('./page-harness.cjs');

let browser, root, saved;
before(async () => {
  browser = await chromium.launch();
  root = fs.mkdtempSync(path.join(os.tmpdir(), 'deck-pack-'));
  saved = await testPictures(browser);
});
after(async () => { await browser?.close(); if (root) fs.rmSync(root, { recursive: true, force: true }); });

// Saves a harness deck folder under root, packs it with pack.py, and opens the
// packed file from its file:// URL in a fresh context that answers the font hosts
// with nothing and refuses every other request off the disk. Records every
// request, every console message and every error.
async function openPacked(folderName, folder) {
  const dir = path.join(root, folderName);
  writeSavedFiles(dir, folder, saved);
  const printed = execFileSync('python3', [PACK, dir], { cwd: root, encoding: 'utf8' }).trim();
  const packed = path.join(root, `${folderName}.html`);
  const context = await browser.newContext();
  const requested = [], messages = [], errors = [];
  await context.route('**/*', route => {
    const url = new URL(route.request().url());
    if (FONT_HOSTS.includes(url.hostname)) return answerFontHost(route);
    return url.protocol === 'file:' ? route.continue() : route.abort();
  });
  const page = await context.newPage();
  page.setDefaultTimeout(4000);
  page.on('request', r => requested.push(r.url()));
  page.on('console', m => { messages.push(m.text()); if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', e => errors.push(String(e)));
  await page.goto(pathToFileURL(packed).href, { waitUntil: 'load' });
  await untilDrawn(page);
  return { page, context, dir, packed, printed, requested, messages, errors };
}

// Loads every picture in the page now, and returns once each has loaded or failed.
const settlePictures = page => page.evaluate(async () => {
  const imgs = [...document.querySelectorAll('img')];
  imgs.forEach(i => { i.loading = 'eager'; });
  await Promise.all(imgs.map(i => i.complete ? null : new Promise(r => { i.addEventListener('load', r, { once: true }); i.addEventListener('error', r, { once: true }); })));
});

// The paths of the deck folder the page asked for: its pictures and its art.
const ofTheFolder = requested => requested.filter(u => u.startsWith('file:') && /\/(cards|art)\//.test(new URL(u).pathname));

test('P9: The packed file opened from file:// draws the cards, their pictures, the hero art and the ledger, and asks for no file of the deck folder', async () => {
  assert.ok(fs.existsSync(PACK), `there is no pack.py beside the page at ${path.relative(REPO, PACK)}`);
  // The rich deck has a maybeboard card and tokens, so every kind of picture the page asks for is packed.
  const folder = deckFolders().rich;
  assert.ok(folder.deck.maybeboard.length && folder.deck.tokens.length, 'the packed deck has no maybeboard card or no token, so this test proves less than it says');
  const { page, context, packed, printed, requested, messages, errors } = await openPacked('brawl-gutter-swarm', folder);
  try {
    assert.equal(path.resolve(root, printed), packed, 'pack.py does not print the packed file\'s path');

    assert.equal((await page.locator('#top h1').innerText()).replace(/\s+/g, ' ').trim(), folder.deck.name, 'the packed deck is not drawn');
    const shown = await page.evaluate(async () => {
      const imgs = [...document.querySelectorAll('#cards img, #engine img')];
      imgs.forEach(i => { i.loading = 'eager'; });
      await Promise.all(imgs.map(i => i.complete ? null : new Promise(r => { i.addEventListener('load', r, { once: true }); i.addEventListener('error', r, { once: true }); })));
      return imgs.map(i => ({ packed: i.src.startsWith('data:image/jpeg;base64,'), loaded: i.complete && i.naturalWidth > 0 }));
    });
    assert.ok(shown.length >= folder.deck.cards.length, `the packed page draws ${shown.length} pictures in the cards and the scenes`);
    assert.deepEqual(shown.filter(p => !p.packed || !p.loaded), [], 'a picture is not drawn from the packed file');
    let timer;
    const art = await Promise.race([
      page.locator('#top').evaluate(h => new Promise(found => {
        const look = () => [h, ...h.querySelectorAll('*')].map(e => getComputedStyle(e).backgroundImage).find(b => b.includes('data:image/jpeg'));
        if (look()) return found(true);
        new MutationObserver((_, o) => { if (look()) { o.disconnect(); found(true); } }).observe(h, { attributes: true, subtree: true });
      })),
      new Promise(none => { timer = setTimeout(() => none(false), 4000); }),
    ]);
    clearTimeout(timer);
    assert.ok(art, 'the hero does not show the packed art');
    assert.ok((await page.locator('#ledger').innerText()).includes(RICH_LEDGER.at(-1)[3]), 'the packed ledger is not drawn');

    // A refused fetch from file:// makes no request event, so deck.json and LEDGER.md are shown to come from the packed file this way.
    assert.deepEqual(await page.evaluate(() => ['deck.json', 'LEDGER.md'].map(f => f in window.DECK_FILES)), [true, true], 'deck.json or LEDGER.md is not in window.DECK_FILES');
    assert.deepEqual(messages.filter(m => /Fetch API cannot load/.test(m)), [], 'the packed page fetched a file of the deck folder');
    assert.deepEqual(ofTheFolder(requested), [], 'the packed page asked for a file of the deck folder');
    assert.deepEqual(errors, [], 'the packed page logged an error');
  } finally {
    await context.close();
  }
});

test('R1: A packed page asks for nothing outside itself, also when a picture deck.json names was never saved: such a card is its name on a blank card and the hero has no art', async () => {
  // The deck with a round on offer, whose last offered card's picture was never saved; nor are one deck card's picture and the hero's art.
  const base = deckFolders().offered;
  const lostOffered = base.deck.offer.groups.flatMap(g => g.cards).find(c => !base.pictures.has(c.scryfall_id));
  const lostInDeck = base.deck.cards.find(c => c.name === 'Gutter Scout');
  assert.ok(lostOffered && lostInDeck && base.deck.hero, 'the deck has no offered card without a picture, no Gutter Scout or no hero, so this test proves less than it says');
  const folder = { ...base, art: [], pictures: new Set([...base.pictures].filter(id => id !== lostInDeck.scryfall_id)) };
  const { page, context, requested, errors } = await openPacked('brawl-lost-pictures', folder);
  try {
    await settlePictures(page);
    assert.deepEqual(ofTheFolder(requested), [], 'the packed page asked for a picture or art of the deck folder that it does not hold');
    assert.deepEqual(errors, [], 'the packed page logged an error');
    const blankIn = (id, name) => page.locator(`#${id}`).evaluate((root, name) => [...root.querySelectorAll('*')].some(e => e.tagName !== 'IMG' && !e.querySelector('img')
      && e.textContent.trim() === name && e.checkVisibility() && e.offsetWidth > 0 && e.offsetHeight / e.offsetWidth > 1.3 && e.offsetHeight / e.offsetWidth < 1.5), name);
    assert.ok(await blankIn('offer', lostOffered.name), `${lostOffered.name}, on offer with no picture saved, is not its name on a blank card`);
    assert.ok(await blankIn('cards', lostInDeck.name), `${lostInDeck.name}, in the deck with no picture saved, is not its name on a blank card`);
    const art = await page.locator('#top').evaluate(h => [h, ...h.querySelectorAll('*')].map(e => getComputedStyle(e).backgroundImage).filter(b => b.includes('url(')));
    assert.deepEqual(art, [], 'the hero shows art that was never saved');
  } finally {
    await context.close();
  }
});

test('R5: The packed page, once it has run, is titled as pack.py titled it, for a deck whose format is " brawl"', async () => {
  // The page reads the format as written, lower-cased and not trimmed, so " brawl" is Standard to it.
  const base = deckFolders()['nameless-with-theme'];
  const { page, context, dir } = await openPacked('brawl-padded-format', { ...base, deck: { ...base.deck, format: ' brawl' } });
  try {
    const written = await page.evaluate(html => new DOMParser().parseFromString(html, 'text/html').title, fs.readFileSync(path.join(dir, 'index.html'), 'utf8'));
    assert.equal(await page.title(), written, `pack.py titles the page "${written}", the page titles itself "${await page.title()}"`);
  } finally {
    await context.close();
  }
});
