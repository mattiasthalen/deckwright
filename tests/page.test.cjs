// The deck page, opened in a browser with test decks.
//
// Run: node --test tests/*.test.cjs
//
// Hooks the page must keep (everything else is read the way a reader sees it):
//   #top       the hero
//   #hero-line the hero's line of format, card count and progress
//   #offer     the cards on offer section
//   #engine    the scenes section
//   #cards     the cards section
//   #curve     the mana curve section
//   #handbook  the handbook section, also the hero's handbook link target
//   #ledger    the ledger section
//   #import    the Arena list section
//   #arena-list the Arena list itself
//   .scene     one scene's box
//   .thing     one thing in a scene step
//   .mana      a run of mana symbols, one child element per symbol
//   --accent   the accent colour, a custom property on the root element

const test = require('node:test');
const { describe, before, after } = test;
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const {
  REPO, EXAMPLE, FONT_HOSTS, UUID, chromium, scryfallId, RICH_LEDGER, MISSING_OFFERED_PICTURE, offeredCards, TRIBES, TRIBES_WITHOUT_S, LINE_THE_PAGE_CANNOT_SPLIT, LINE_THE_PAGE_CANNOT_SPLIT_WITH_ID,
  LONG_WORD, startDeckServer, withDeck, untilDrawn,
} = require('./page-harness.cjs');

let browser, server;
before(async () => { browser = await chromium.launch(); server = await startDeckServer(browser); });
after(async () => { server?.close(); await browser?.close(); });

const open = (name, options, use) => withDeck(browser, server, name, options, use);
const deckOf = name => server.folders[name].deck;
const picturePath = (deckName, id) => `/${deckName}/cards/${id}.jpg`;
const byName = (deck, name) => deck.cards.find(c => c.name === name);
const count = c => c.count ?? 1;
const frontType = c => (c.copy?.type_line || '').split(' // ')[0];
const isLand = c => /\bLand\b/.test(frontType(c));
const isCreature = c => /\bCreature\b/.test(frontType(c));
// Scryfall's cmc when the copy has it; otherwise each symbol: a number its value,
// X nothing, a hybrid with a number ({2/W}) that number, any other symbol one.
const symbolValue = s => { const n = s.slice(1, -1).split('/').find(p => /^\d+$/.test(p)); return n !== undefined ? +n : /X/.test(s) ? 0 : 1; };
const manaValue = c => c.copy?.mana_value ?? ((c.copy?.mana_cost || '').match(/\{[^}]+\}/g) || []).reduce((n, s) => n + symbolValue(s), 0);
const NUMBER_WORDS = ['one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight'];

const arenaList = deck => {
  const live = deck.cards.filter(c => (c.count ?? 1) > 0);
  const line = c => `${c.count ?? 1} ${c.name}`;
  const commander = live.filter(c => c.category === 'Commander'), rest = live.filter(c => c.category !== 'Commander');
  return (commander.length ? `Commander\n${commander.map(line).join('\n')}\n\n` : '') + `Deck\n${rest.map(line).join('\n')}`;
};

function rgb(css) {
  const m = String(css).match(/rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)/);
  if (!m) throw new Error(`not an rgb colour: ${css}`);
  return m.slice(1, 4).map(Number);
}

function hsl([r, g, b]) {
  r /= 255; g /= 255; b /= 255;
  const max = Math.max(r, g, b), min = Math.min(r, g, b), l = (max + min) / 2, d = max - min;
  if (d === 0) return { h: 0, s: 0, l };
  const s = d / (1 - Math.abs(2 * l - 1));
  const h = max === r ? 60 * (((g - b) / d) % 6) : max === g ? 60 * ((b - r) / d + 2) : 60 * ((r - g) / d + 4);
  return { h: (h + 360) % 360, s, l };
}

// Resolves any CSS colour expression (a custom property included) to rgb() in the page.
const resolveColour = (page, expression) => page.evaluate(expr => {
  const probe = document.createElement('div');
  probe.style.color = expr;
  document.body.append(probe);
  const out = getComputedStyle(probe).color;
  probe.remove();
  return out;
}, expression);

// Scrolls an element into view and waits for every picture inside it to finish loading.
async function settlePictures(locator) {
  await locator.scrollIntoViewIfNeeded();
  await locator.evaluate(async root => {
    const imgs = [...root.querySelectorAll('img')];
    imgs.forEach(i => { i.loading = 'eager'; });
    await Promise.all(imgs.map(i => i.complete ? null : new Promise(r => { i.addEventListener('load', r, { once: true }); i.addEventListener('error', r, { once: true }); setTimeout(r, 3000); })));
  });
}

const pictures = locator => locator.evaluate(root => [...root.querySelectorAll('img')].map(i => ({
  src: new URL(i.currentSrc || i.src, location.href).pathname, loaded: i.complete && i.naturalWidth > 0, broken: i.complete && i.naturalWidth === 0,
  width: i.getBoundingClientRect().width, top: i.getBoundingClientRect().top, bottom: i.getBoundingClientRect().bottom,
})));

const until = async (check, ms = 4000, every = 50) => {
  const end = Date.now() + ms;
  let last;
  while (Date.now() < end) { last = await check(); if (last) return last; await new Promise(r => setTimeout(r, every)); }
  return check();
};

async function visible(locator) {
  return (await locator.count()) > 0 && locator.first().isVisible();
}

async function sectionText(page, id) {
  const section = page.locator(`#${id}`);
  assert.ok(await visible(section), `the #${id} section is not on the page`);
  return section.innerText();
}

// The headline numbers read from the hero, label -> number, for labels drawn as
// a number on one line (or the same line) with its label.
async function headline(page, labels) {
  const text = await sectionText(page, 'top');
  const found = {};
  for (const [key, label] of Object.entries(labels)) {
    const m = text.match(new RegExp(`^\\s*(\\d+(?:\\.\\d+)?)\\s*(?:\\n\\s*)?(?:${label})\\s*$`, 'im'));
    if (m) found[key] = Number(m[1]);
  }
  return { text, found };
}

const deckStats = deck => {
  const live = deck.cards.filter(c => count(c) > 0);
  const total = list => list.reduce((n, c) => n + count(c), 0);
  const spells = live.filter(c => !isLand(c));
  return {
    cards: total(live),
    creatures: total(live.filter(isCreature)),
    lands: total(live.filter(isLand)),
    average: spells.reduce((s, c) => s + manaValue(c) * count(c), 0) / total(spells),
    rares: total(live.filter(c => ['rare', 'mythic'].includes(c.copy?.rarity))),
  };
};

async function copiedBy(page, button) {
  await page.evaluate(() => navigator.clipboard.writeText(''));
  await button.click();
  return until(async () => (await page.evaluate(() => navigator.clipboard.readText())) || null);
}

const dialog = page => page.locator('dialog[open], [role="dialog"]').filter({ visible: true });

// The card's tile in the grid: the nearest element around its picture (or its
// blank stand-in) that also shows its name.
async function tile(page, deckName, cardName) {
  const deck = deckOf(deckName);
  const c = byName(deck, cardName) || deck.maybeboard.find(m => m.name === cardName);
  const handle = await page.evaluateHandle(({ src, name }) => {
    const cards = document.getElementById('cards');
    if (!cards) return null;
    const pic = [...cards.querySelectorAll('img')].find(i => new URL(i.src, location.href).pathname === src);
    let el = pic || [...cards.querySelectorAll('*')].find(e => e.children.length === 0 && e.textContent.trim() === name);
    while (el && el !== cards && !(el.innerText || '').includes(name)) el = el.parentElement;
    return el && el !== cards ? el : null;
  }, { src: picturePath(deckName, c.scryfall_id), name: cardName });
  const element = handle.asElement();
  assert.ok(element, `no tile for ${cardName} in the cards section`);
  return element;
}

async function openCard(page, deckName, cardName) {
  const t = await tile(page, deckName, cardName);
  await t.click();
  const d = dialog(page);
  assert.ok(await until(() => d.count()), `opening ${cardName} from the grid shows no dialog`);
  return d.first();
}

const closeDialog = page => page.keyboard.press('Escape');

// A name drawn on its own, not as a control: the blank card standing in for a picture.
const blankCardNamed = (scope, name) => scope.evaluate((root, name) => [...root.querySelectorAll('*')]
  .some(e => e.children.length === 0 && e.textContent.trim() === name && e.checkVisibility() && !e.closest('button, a, [role="button"]')), name);
const controlsNamed = (scope, name) => scope.locator('button, a, [role="button"], [role="link"]').filter({ hasText: new RegExp(`^\\s*${name}\\s*$`) }).count();
const heroArt = hero => hero.evaluate(h => [h, ...h.querySelectorAll('*')].map(e => getComputedStyle(e).backgroundImage).find(b => b.includes('/art/') || b.includes('data:image')) || null);

// Scrolls a scene into view and returns once an IntersectionObserver has seen it
// there. The page's own observer of the scene was made earlier, so it has been
// told first, and the scene moves when the clock runs.
async function onScreen(locator) {
  await locator.scrollIntoViewIfNeeded();
  await locator.evaluate(root => new Promise(seen => {
    const box = root.closest('.scene') || root.querySelector('.scene') || root;
    new IntersectionObserver((entries, observer) => {
      if (entries.at(-1).isIntersecting) { observer.disconnect(); seen(); }
    }).observe(box);
  }));
}

// Advances the paused clock in small steps until the caption leaves the scope.
async function nextStep(page, scope, caption, limit = 4000) {
  await onScreen(scope);
  for (let spent = 0; spent <= limit; spent += 200) {
    if (!(await scope.innerText()).includes(caption)) return spent;
    await page.clock.runFor(200);
  }
  assert.fail(`"${caption}" was still shown after ${limit} ms on screen`);
}

// What a reader sees in the thing at an index of the step a scene shows, once its
// pictures have loaded or failed: the text of each element shown at more than
// half opacity, its pictures, and its blank cards (card-shaped boxes holding no
// picture and no smaller card shape). At 'start' every motion in the thing is
// rewound to its beginning first; at 'end' every motion is finished. The caption
// and the thing are read in one call; null when the scene shows another step.
const readThing = (scene, caption, index, at) => scene.evaluate(async (s, { caption, index, at }) => {
  const t = s.innerText.includes(caption) && s.querySelectorAll('.thing')[index];
  if (!t) return null;
  await Promise.all([...t.querySelectorAll('img')].map(i => i.complete ? null : new Promise(settled => {
    i.addEventListener('load', settled, { once: true });
    i.addEventListener('error', settled, { once: true });
    setTimeout(settled, 3000);
  })));
  if (!t.isConnected) return null;
  const motions = t.getAnimations({ subtree: true });
  const running = motions.filter(a => a.playState === 'running').length;
  if (at === 'start') motions.forEach(a => { a.currentTime = 0; });
  if (at === 'end') motions.forEach(a => { try { a.finish(); } catch {} });
  const opacity = e => { let o = 1; for (; e && e !== t.parentElement; e = e.parentElement) o *= +getComputedStyle(e).opacity; return o; };
  const shown = e => e.checkVisibility({ visibilityProperty: true }) && opacity(e) > 0.5;
  const all = [...t.querySelectorAll('*')].filter(shown);
  const ownText = e => [...e.childNodes].filter(n => n.nodeType === Node.TEXT_NODE).map(n => n.textContent).join('').trim();
  const cardShaped = e => e.offsetWidth > 0 && e.offsetHeight / e.offsetWidth > 1.3 && e.offsetHeight / e.offsetWidth < 1.5;
  return {
    texts: all.map(ownText).filter(Boolean),
    pictures: all.filter(e => e.tagName === 'IMG').map(i => ({ src: new URL(i.currentSrc || i.src, location.href).pathname, loaded: i.complete && i.naturalWidth > 0, broken: i.complete && i.naturalWidth === 0 })),
    blanks: all.filter(e => e.tagName !== 'IMG' && cardShaped(e) && !e.querySelector('img') && ![...e.querySelectorAll('*')].some(cardShaped)).length,
    running,
  };
}, { caption, index, at });
const numbersIn = seen => seen.texts.filter(s => /^\d+$/.test(s)).map(Number);
const minusMarkIn = (seen, n) => seen.texts.some(s => new RegExp(`^[−–-]\\s?${n}$`).test(s));
const plusMarkIn = (seen, n) => seen.texts.some(s => new RegExp(`^\\+\\s?${n}$`).test(s));

// The thing in a scene's step at an index, read at every 100 ms of the fake clock
// while the step is shown; the last reading is the thing at the end of its step.
async function atEndOfStep(page, scene, caption, index, limit = 4000) {
  for (let spent = 0, last = null; ; spent += 100) {
    const seen = await readThing(scene, caption, index, 'end');
    if (!seen) {
      assert.ok(last, `"${caption}" was no longer shown when its thing ${index} was read`);
      return last;
    }
    assert.ok(spent <= limit, `"${caption}" was still shown after ${limit} ms on screen`);
    last = seen;
    await page.clock.runFor(100);
  }
}

// Runs the fake clock until read, which reads the step with the caption, reads something.
async function whenShown(page, caption, read, limit = 6000) {
  for (let spent = 0; ; spent += 100) {
    const seen = await read();
    if (seen) return seen;
    assert.ok(spent <= limit, `"${caption}" was not shown within ${limit} ms`);
    await page.clock.runFor(100);
  }
}

// The motions on the parts of a damage or draw thing in the step a scene shows:
// on its body (the elements from the lowered life total's number, or from each
// card back's picture, up to the thing) and on its "−N" or "+N" mark; and how
// faded or grey each part of the body ends once every motion is finished. Null
// when the scene shows another step.
const partsOfThing = (scene, caption, index) => scene.evaluate((s, { caption, index }) => {
  const t = s.innerText.includes(caption) && s.querySelectorAll('.thing')[index];
  if (!t) return null;
  const upToThing = e => { const chain = []; for (; e && e !== t; e = e.parentElement) chain.push(e); return chain; };
  const motionNames = elements => [...new Set(elements.flatMap(e => e.getAnimations().map(a => a.animationName)))].sort();
  const ends = [...t.querySelectorAll('*')].filter(e => !e.children.length);
  const mark = ends.find(e => /^[−+]/.test(e.textContent.trim()));
  const anchors = [...t.querySelectorAll('img'), ...ends.filter(e => /^\d+$/.test(e.textContent.trim())).slice(-1)];
  const seen = { anchors: anchors.length, body: motionNames(anchors.flatMap(upToThing)), mark: mark ? motionNames(upToThing(mark)) : null };
  t.getAnimations({ subtree: true }).forEach(a => { try { a.finish(); } catch {} });
  seen.ended = anchors.map(a => {
    const chain = upToThing(a);
    return { opacity: chain.reduce((o, e) => o * +getComputedStyle(e).opacity, 1), grey: chain.some(e => /grayscale\((1|0\.[5-9])/.test(getComputedStyle(e).filter)) };
  });
  return seen;
}, { caption, index });

// Brings a scene of the drawn decks to its last step, the one with damage and a draw.
async function toLastStep(page, deckName, sceneIndex) {
  const scene = page.locator('#engine .scene').nth(sceneIndex);
  assert.ok(await visible(scene), `scene ${sceneIndex} of ${deckName} is not drawn`);
  await onScreen(scene);
  const [first, last] = deckOf(deckName).scenes[sceneIndex].steps;
  for (let spent = 0; !(await scene.innerText()).includes(first.caption); spent += 100) {
    assert.ok(spent <= 6000, `"${first.caption}" was not shown within ${spent} ms`);
    await page.clock.runFor(100);
  }
  await nextStep(page, scene, first.caption);
  assert.ok((await scene.innerText()).includes(last.caption), `the scene did not move to "${last.caption}"`);
  return { scene, step: last };
}

const STARTING_LIFE = { brawl: 25, standard: 20 };

// What the mana curve draws: the two legend colours and, per column from left to
// right, the height of the creature part and the other-spells part.
const readCurve = page => page.evaluate(() => {
  const section = document.getElementById('curve');
  if (!section) return null;
  const transparent = c => c === 'rgba(0, 0, 0, 0)' || c === 'transparent';
  const swatchOf = name => {
    const item = [...section.querySelectorAll('*')].find(e => (e.innerText || '').trim().toLowerCase() === name && e.children.length <= 2);
    if (!item) return null;
    const near = [item, ...item.querySelectorAll('*'), item.previousElementSibling].filter(Boolean);
    const swatch = near.find(e => !transparent(getComputedStyle(e).backgroundColor));
    return swatch ? { element: swatch, colour: getComputedStyle(swatch).backgroundColor } : null;
  };
  const creature = swatchOf('creatures'), other = swatchOf('other spells');
  if (!creature || !other) return { legend: false };
  const parts = colour => [...section.querySelectorAll('*')]
    .filter(e => e !== creature.element && e !== other.element && getComputedStyle(e).backgroundColor === colour)
    .map(e => { const r = e.getBoundingClientRect(); return { x: r.left + r.width / 2, height: r.height, top: r.top }; });
  const all = [...parts(creature.colour).map(p => ({ ...p, kind: 'creature' })), ...parts(other.colour).map(p => ({ ...p, kind: 'other' }))].sort((a, b) => a.x - b.x);
  const columns = [];
  for (const p of all) {
    let col = columns.find(c => Math.abs(c.x - p.x) < 8);
    if (!col) columns.push(col = { x: p.x, creature: 0, other: 0, tops: [] });
    col[p.kind] += p.height;
    if (p.height > 0) col.tops.push(p.top);
  }
  return { legend: true, creature: creature.colour, other: other.colour, columns: columns.sort((a, b) => a.x - b.x) };
});

// The curve once every motion in it has finished.
async function finishedCurve(page) {
  await page.evaluate(() => document.getElementById('curve')?.getAnimations({ subtree: true }).forEach(a => { try { a.finish(); } catch {} }));
  return readCurve(page);
}

const curveBuckets = deck => {
  const buckets = Array.from({ length: 8 }, () => ({ creature: 0, other: 0 }));
  deck.cards.filter(c => !isLand(c)).forEach(c => { buckets[Math.min(manaValue(c), 7)][isCreature(c) ? 'creature' : 'other'] += count(c); });
  return buckets;
};

const ledgerSubject = subject => subject.replace(/\s*\([0-9a-f-]{36}\)/, '');
const KIND_WORDS = { in: 'In', out: 'Out', criteria: 'Criteria', category: 'Category', finding: 'Finding' };

// The page around a section it could not draw: that section is left out with its
// error on the console, and every other section, the ledger, the Arena list and
// the card dialog are drawn.
async function drawnWithout(page, errors, deckName, leftOut) {
  const deck = deckOf(deckName);
  for (const id of ['top', 'cards', 'curve', 'handbook', 'ledger', 'import'].filter(id => id !== leftOut)) {
    assert.ok(await visible(page.locator(`#${id}`)), `the #${id} section is not drawn; errors: ${errors.join(' | ')}`);
  }
  const pre = page.locator('pre').filter({ visible: true });
  assert.equal(await pre.count(), 1, 'the Arena list is not drawn');
  assert.equal(await page.locator('#arena-list').textContent(), arenaList(deck));
  assert.ok(await until(async () => (await page.locator('#ledger').innerText()).includes('the commander')), 'the ledger entry is not drawn');
  const d = await openCard(page, deckName, 'Quick Shock');
  assert.ok((await d.innerText()).includes('Quick Shock'), 'the card dialog does not open');
  await closeDialog(page);
  assert.ok(!(await visible(page.locator(`#${leftOut}`))), `the #${leftOut} section it could not draw is shown`);
  assert.ok(errors.some(e => e.includes(`#${leftOut}`)), `the console does not say the #${leftOut} section could not be drawn: ${errors.join(' | ')}`);
}

// ======================================================================
describe('The look', () => {
  test('AC1 (ADR-0013): The page has no tab control, and its sections appear in this order: hero, cards on offer, scenes, cards, curve, handbook, ledger, Arena list', () =>
    open('offered', async ({ page, deck }) => {
      const tabs = await page.locator('[role="tab"], [role="tablist"], [aria-selected]').count();
      assert.equal(tabs, 0, 'the page has a tab control');
      const markers = {
        hero: deck.name,
        'cards on offer': deck.offer.groups[0].cards[0].reason,
        scenes: deck.scenes[0].title,
        cards: 'Commander',
        curve: 'Other spells',
        handbook: deck.handbook[0].title,
        ledger: RICH_LEDGER.at(-1)[3],
        'Arena list': arenaList(deck).split('\n')[1],
      };
      const order = await page.evaluate(markers => {
        const all = [...document.body.querySelectorAll('*')];
        const at = text => all.findIndex(e => e.checkVisibility() && (e.innerText || '').includes(text) && ![...e.children].some(k => (k.innerText || '').includes(text)));
        return Object.fromEntries(Object.entries(markers).map(([k, v]) => [k, at(v)]));
      }, markers);
      for (const [part, at] of Object.entries(order)) assert.ok(at >= 0, `the ${part} is not visible on the page`);
      const drawn = Object.entries(order).sort((a, b) => a[1] - b[1]).map(([part]) => part);
      assert.deepEqual(drawn, Object.keys(markers));
    }));

  test('AC2: Headings use the display serif family and body text the humanist sans family', () =>
    open('rich', async ({ page }) => {
      const families = await page.evaluate(() => ({
        headings: [...document.querySelectorAll('h1, h2, h3')].filter(h => h.checkVisibility()).map(h => getComputedStyle(h).fontFamily),
        body: getComputedStyle(document.body).fontFamily,
        paragraphs: [...document.querySelectorAll('p')].filter(p => p.checkVisibility()).map(p => getComputedStyle(p).fontFamily),
      }));
      assert.ok(families.headings.length > 3, 'too few headings to judge');
      const first = list => list.split(',')[0].trim().replace(/["']/g, '');
      const generic = list => list.split(',').map(f => f.trim());
      for (const h of families.headings) {
        assert.match(first(h), /IM Fell/, `a heading is set in ${h}`);
        assert.ok(generic(h).includes('serif'), `a heading has no serif fallback: ${h}`);
      }
      for (const b of [families.body, ...families.paragraphs]) {
        assert.match(first(b), /Alegreya Sans/, `body text is set in ${b}`);
        assert.ok(generic(b).includes('sans-serif'), `body text has no sans-serif fallback: ${b}`);
      }
    }));

  test('AC3: Each section below the hero has a label, a heading and, where the spec gives one, a lede', () =>
    open('rich', async ({ page, deck }) => {
      for (const id of ['engine', 'cards', 'curve', 'handbook', 'ledger', 'import']) {
        const parts = await page.evaluate(id => {
          const s = document.getElementById(id);
          if (!s || !s.checkVisibility()) return null;
          const heading = [...s.querySelectorAll('h2')].find(h => h.checkVisibility());
          if (!heading) return { heading: null };
          const label = [...s.querySelectorAll('*')].find(e => e.checkVisibility() && e.children.length === 0 && e.textContent.trim()
            && (e.compareDocumentPosition(heading) & Node.DOCUMENT_POSITION_FOLLOWING));
          return { heading: heading.innerText.trim(), label: label?.innerText.trim() };
        }, id);
        assert.ok(parts, `the #${id} section is not on the page`);
        assert.ok(parts.heading, `the #${id} section has no heading`);
        assert.ok(parts.label, `the #${id} section has no label above its heading`);
      }
      assert.ok((await sectionText(page, 'engine')).includes(deck.scenes[0].lede), 'the main scene\'s lede is not shown');
    }));

  test('AC4: The hero shows the art file as its background, the deck name, the pitch, the criteria, and buttons to the handbook and the Arena copy', async () => {
    for (const name of ['rich', 'mono']) {
      await open(name, async ({ page, deck }) => {
        const hero = page.locator('#top');
        assert.ok(await visible(hero), 'the hero is not on the page');
        const art = await until(() => hero.evaluate(h => [h, ...h.querySelectorAll('*')].map(e => getComputedStyle(e).backgroundImage).find(b => b.includes('/art/')) || null));
        assert.ok(art, `${name}: no element in the hero has the art file as its background`);
        assert.ok(art.includes(`/${name}/art/${deck.hero}.jpg`), `${name}: the hero background is ${art}`);
        assert.equal((await hero.locator('h1').innerText()).replace(/\s+/g, ' ').trim(), deck.name);
        const text = await hero.innerText();
        assert.ok(text.includes(deck.pitch), `${name}: the pitch is not in the hero`);
        for (const c of deck.criteria) assert.ok(text.includes(c.text), `${name}: the criterion "${c.text}" is not in the hero`);
        const copy = hero.getByRole('button', { name: /copy/i });
        assert.ok(await visible(copy), `${name}: the hero has no copy button`);
        assert.equal(await copiedBy(page, copy.first()), arenaList(deck));
        if ((deck.handbook || []).length) {
          const toHandbook = hero.getByRole('link', { name: /handbook/i }).or(hero.getByRole('button', { name: /handbook/i }));
          assert.ok(await visible(toHandbook), `${name}: the hero has no handbook button`);
          await toHandbook.first().click();
          const reached = await until(() => page.evaluate(() => { const t = document.getElementById('handbook').getBoundingClientRect().top; return t > -20 && t < 300; }));
          assert.ok(reached, `${name}: the handbook button does not bring the handbook into view`);
        }
      });
    }
  });

  test('AC5: The headline numbers equal the counts of the test deck: cards, the shared creature type or creatures, lands, average mana value, rares and mythics', async () => {
    const labels = { cards: 'cards', rats: 'Rats?', creatures: 'creatures', lands: 'lands', average: 'average mana value', rares: 'rares and mythics' };
    await open('rich', async ({ page, deck }) => {
      const want = deckStats(deck);
      const { found } = await headline(page, labels);
      assert.equal(found.cards, want.cards, 'cards');
      assert.equal(found.rats, 5, 'five creatures are Rats, more than a third of the creatures');
      assert.equal(found.creatures, undefined, 'the shared creature type replaces the creature count');
      assert.equal(found.lands, want.lands, 'lands');
      assert.ok(Math.abs(found.average - want.average) < 0.051, `average mana value ${found.average}, want ${want.average.toFixed(2)}`);
      assert.equal(found.rares, want.rares, 'rares and mythics');
    });
    await open('mono', async ({ page, deck }) => {
      const want = deckStats(deck);
      const { text, found } = await headline(page, labels);
      assert.equal(found.cards, want.cards, 'cards');
      assert.equal(found.creatures, want.creatures, 'no type is shared by more than three creatures, so creatures are counted');
      assert.equal(found.lands, want.lands, 'lands');
      assert.ok(Math.abs(found.average - want.average) < 0.051, `average mana value ${found.average}, want ${want.average.toFixed(2)}`);
      assert.doesNotMatch(text, /rares and mythics/i, 'a deck with no rare or mythic shows no rares and mythics');
    });
  });

  test('AC6: A deck of one colour gets that colour\'s accent; a deck of several gets a blend; a deck with no coloured symbol gets gold', async () => {
    const accentHue = async page => hsl(rgb(await resolveColour(page, 'var(--accent)')));
    await open('mono', async ({ page }) => {
      const { h, s } = await accentHue(page);
      assert.ok(h >= 90 && h <= 160 && s > 0.2, `a green deck's accent has hue ${h.toFixed(0)}`);
    });
    await open('several', async ({ page, deck }) => {
      const { h, s } = await accentHue(page);
      assert.ok((h <= 25 || h >= 335) && s > 0.2, `a black-red deck's accent, its first colour that is not black, has hue ${h.toFixed(0)}`);
      const lastWord = deck.name.split(' ').at(-1);
      const blend = await page.evaluate(word => {
        const h1 = document.querySelector('h1');
        const el = [h1, ...h1.querySelectorAll('*')].find(e => e.textContent.trim() === word && /gradient/.test(getComputedStyle(e).backgroundImage));
        return el ? getComputedStyle(el).backgroundImage : null;
      }, lastWord);
      assert.ok(blend, `the last word of the deck name, "${lastWord}", carries no blend`);
      const colours = new Set(blend.match(/rgba?\([^)]+\)/g));
      assert.ok(colours.size >= 2, `the blend has ${colours.size} colour(s): ${blend}`);
    });
    await open('colourless', async ({ page }) => {
      const { h, s } = await accentHue(page);
      assert.ok(h >= 30 && h <= 55 && s > 0.4, `a deck with no coloured symbol has accent hue ${h.toFixed(0)}, not gold`);
    });
  });

  test('AC7: At phone width nothing scrolls sideways', () =>
    open('rich', { viewport: { width: 375, height: 740 } }, async ({ page }) => {
      for (const id of ['top', 'engine', 'cards', 'curve', 'handbook', 'ledger', 'import']) {
        assert.ok(await visible(page.locator(`#${id}`)), `the #${id} section is not drawn, so the width check would prove nothing`);
      }
      await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
      const widths = await page.evaluate(() => ({ page: document.documentElement.scrollWidth, body: document.body.scrollWidth, view: document.documentElement.clientWidth }));
      assert.ok(widths.page <= widths.view && widths.body <= widths.view, `the page is ${widths.page} px wide in a ${widths.view} px window`);
    }));

  test('A card name or handbook word longer than the window wraps: at phone width nothing scrolls sideways, in the page or the card dialog', () =>
    open('long-names', { viewport: { width: 375, height: 740 } }, async ({ page }) => {
      for (const id of ['top', 'cards', 'curve', 'handbook', 'ledger', 'import']) {
        assert.ok(await visible(page.locator(`#${id}`)), `the #${id} section is not drawn, so the width check would prove nothing`);
      }
      const width = () => page.evaluate(() => ({ page: document.documentElement.scrollWidth, body: document.body.scrollWidth, view: document.documentElement.clientWidth }));
      let w = await width();
      assert.ok(w.page <= w.view && w.body <= w.view, `the page is ${w.page} px wide in a ${w.view} px window`);
      const d = await openCard(page, 'long-names', LONG_WORD);
      const box = await d.evaluate(e => { const r = e.getBoundingClientRect(); return { left: r.left, right: r.right, inner: e.scrollWidth - e.clientWidth }; });
      w = await width();
      assert.ok(box.left >= 0 && box.right <= w.view && box.inner <= 0, `the dialog spans ${box.left.toFixed(0)} to ${box.right.toFixed(0)} px (${box.inner} px hidden) in a ${w.view} px window`);
    }));

  test('A deck name with spaces before, after or doubled inside it is drawn word by word, and its last word carries the blend', () =>
    open('spaced-name', async ({ page }) => {
      assert.equal((await page.locator('#top h1').innerText()).replace(/\s+/g, ' ').trim(), 'Ash and Shadow Pack');
      const blended = await page.evaluate(() => {
        const h1 = document.querySelector('h1');
        return [h1, ...h1.querySelectorAll('*')].filter(e => /gradient/.test(getComputedStyle(e).backgroundImage)).map(e => e.textContent);
      });
      assert.deepEqual(blended, ['Pack'], `the blend is on ${JSON.stringify(blended)}`);
    }));

  test('AC8: A deck with no hero field still shows its name and numbers', () =>
    open('several', async ({ page, deck, outside }) => {
      assert.ok(await visible(page.locator('#top')), 'the hero is not on the page');
      assert.equal((await page.locator('#top h1').innerText()).replace(/\s+/g, ' ').trim(), deck.name);
      const want = deckStats(deck);
      const { found } = await headline(page, { cards: 'cards', lands: 'lands' });
      assert.equal(found.cards, want.cards, 'cards');
      assert.equal(found.lands, want.lands, 'lands');
      assert.deepEqual(outside, []);
    }));

  test('The headline counts copies: a rare at two copies counts twice, and the shared creature type is reached through copies', () =>
    open('rich', async ({ page, deck }) => {
      const rats = deck.cards.filter(c => isCreature(c) && /\bRat\b/.test(frontType(c)));
      assert.ok(rats.length <= 3, 'more than three distinct Rat cards: the deck reaches the shared type without counting copies');
      assert.ok(deck.cards.some(c => count(c) > 1 && ['rare', 'mythic'].includes(c.copy?.rarity)), 'no rare in the test deck has more than one copy');
      const { found } = await headline(page, { rats: 'Rats', rares: 'rares and mythics' });
      assert.equal(found.rats, rats.reduce((n, c) => n + count(c), 0), 'the Rats are not counted by copies');
      assert.equal(found.rares, deckStats(deck).rares, 'rares and mythics are not counted by copies');
    }));

  test('The shared creature type is named in the plural Arena uses: Merfolk, Kithkin and Kor take no s', async () => {
    for (const [type, plural] of Object.entries(TRIBES)) {
      await open(`tribe-${type.toLowerCase()}`, async ({ page }) => {
        const { text, found } = await headline(page, { shared: plural });
        assert.equal(found.shared, 4, `four ${type} creatures are not headlined as 4 ${plural}: ${text.replace(/\s+/g, ' ')}`);
      });
    }
  });

  test('The shared creature type is named in the plural Arena uses: Eldrazi, Myr, Vedalken, Aetherborn and Deer take no s', async () => {
    for (const type of TRIBES_WITHOUT_S) {
      await open(`tribe-${type.toLowerCase()}`, async ({ page }) => {
        const { text, found } = await headline(page, { shared: type });
        assert.equal(found.shared, 4, `four ${type} creatures are not headlined as 4 ${type}: ${text.replace(/\s+/g, ' ')}`);
      });
    }
  });

  test('The hero art file is missing: the hero shows no art and announces none', () =>
    open('lost-files', async ({ page, deck }) => {
      const hero = page.locator('#top');
      assert.equal((await hero.locator('h1').innerText()).replace(/\s+/g, ' ').trim(), deck.name);
      const settled = await until(async () => (await heroArt(hero)) === null && (await hero.getByRole('img').count()) === 0);
      assert.ok(settled, `the hero keeps art it cannot show (${await heroArt(hero)}) or announces it (${await hero.getByRole('img').count()} images)`);
    }));
});

// ======================================================================
describe('Scenes', () => {
  test('AC9: Every card and token thing in a scene is an image of that card\'s saved picture; the page draws no scene from an SVG string in deck.json', async () => {
    await open('rich', { clock: true }, async ({ page, deck }) => {
      const engine = page.locator('#engine');
      assert.ok(await visible(engine), 'the scenes section is not on the page');
      const idOf = t => t.card ? byName(deck, t.card).scryfall_id : deck.tokens.find(k => k.name === t.token).scryfall_id;
      const expected = steps => steps.flatMap(s => s.things.filter(t => t.card || t.token).map(t => picturePath('rich', idOf(t)))).sort();
      const check = async steps => {
        await settlePictures(engine);
        const shown = await pictures(engine);
        assert.deepEqual(shown.map(p => p.src).sort(), expected(steps));
        for (const p of shown) assert.ok(p.loaded, `${p.src} did not load`);
      };
      await check(deck.scenes.map(s => s.steps[0]));
      await nextStep(page, engine, deck.scenes[0].steps[0].caption);
      const shown = await engine.innerText();
      assert.ok(shown.includes(deck.scenes[0].steps[1].caption), 'the main scene did not move to its second step');
      await check([deck.scenes[0].steps[1], ...deck.scenes.slice(1).map(s => s.steps[0])]);
    });
    await open('version-one', async ({ page }) => {
      const drawn = await page.evaluate(() => ({ svg: !!document.querySelector('svg[data-v1-scene]'), text: document.body.innerText.includes('Old drawing') }));
      assert.deepEqual(drawn, { svg: false, text: false }, 'a scene was drawn from an SVG string');
    });
  });

  test('AC10: The first scene is drawn large under its own title as a heading; the others are drawn smaller below it', () =>
    open('rich', { clock: true }, async ({ page, deck }) => {
      const engine = page.locator('#engine');
      assert.ok(await visible(engine), 'the scenes section is not on the page');
      const headings = await engine.evaluate(e => [...e.querySelectorAll('h1, h2, h3, h4, h5, h6')].map(h => ({ text: h.innerText.trim(), size: parseFloat(getComputedStyle(h).fontSize) })));
      const main = headings.find(h => h.text === deck.scenes[0].title);
      assert.ok(main, 'the first scene\'s title is not a heading');
      for (const s of deck.scenes.slice(1)) {
        const other = headings.find(h => h.text === s.title);
        assert.ok(other, `the scene "${s.title}" has no heading`);
        assert.ok(other.size < main.size, `"${s.title}" is titled as large as the first scene`);
      }
      await settlePictures(engine);
      const shown = await pictures(engine);
      const first = shown.find(p => p.src === picturePath('rich', scryfallId(1)));
      const second = shown.find(p => p.src === picturePath('rich', scryfallId(11)));
      assert.ok(first && second, 'the first two scenes\' cards are not both drawn');
      assert.ok(first.width > second.width, `the first scene's card is ${first.width} px wide, the second's ${second.width} px`);
      assert.ok(second.top > first.bottom, 'the other scenes are not below the first');
    }));

  test('AC11: A scene on screen moves to its next step by itself and returns to the first after the last; the scenes section has no button', () =>
    open('rich', { clock: true }, async ({ page, deck }) => {
      const engine = page.locator('#engine');
      assert.ok(await visible(engine), 'the scenes section is not on the page');
      assert.equal(await engine.locator('button, [role="button"], a[href], input').count(), 0, 'the scenes section has a control');
      await onScreen(engine);
      const steps = deck.scenes[0].steps;
      for (const step of steps) {
        assert.ok((await engine.innerText()).includes(step.caption), `the step "${step.caption}" is not shown`);
        await nextStep(page, engine, step.caption);
      }
      assert.ok((await engine.innerText()).includes(steps[0].caption), 'after the last step the scene did not return to the first');
    }));

  test('AC12: A pile shows its count, mana shows its symbols, a chip shows its text, and a badge shows on its thing', () =>
    open('rich', { clock: true }, async ({ page }) => {
      const scene = page.locator('.scene').filter({ hasText: 'Counters, a graveyard, a cost and damage.' });
      assert.ok(await visible(scene), 'the scene with a pile, mana and a chip is not drawn');
      await settlePictures(scene);
      const thing = text => scene.locator('.thing').filter({ hasText: text }).first();
      assert.match(await thing('Graveyard').innerText(), /(^|\s)5(\s|$)/, 'the pile does not show its count');
      const pay = thing('Pay');
      assert.equal(await pay.locator('.mana > *').count(), 3, 'the mana does not show three symbols');
      assert.doesNotMatch(await pay.innerText(), /[{}]/, 'the mana is drawn as raw braces');
      assert.match(await thing('Damage').innerText(), /(^|\s)3(\s|$)/, 'the chip does not show its text');
      const badged = await scene.locator('.thing').evaluateAll((things, src) => {
        const t = things.find(t => [...t.querySelectorAll('img')].some(i => new URL(i.src, location.href).pathname === src));
        if (!t) return null;
        const badge = [...t.querySelectorAll('*')].find(e => e.children.length === 0 && e.textContent.trim() === '2/2');
        if (!badge || !badge.checkVisibility()) return { badge: false };
        const a = badge.getBoundingClientRect(), b = t.querySelector('img').getBoundingClientRect();
        return { badge: true, on: a.right > b.left && a.left < b.right && a.bottom > b.top && a.top < b.bottom };
      }, picturePath('rich', scryfallId(3)));
      assert.ok(badged?.badge, 'the badge 2/2 is not shown on its thing');
      assert.ok(badged.on, 'the badge does not sit on its card');
    }));

  test('AC13: does sets the matching motion on the thing, one of enters, glows, taps, leaves, copies', () =>
    open('rich', { clock: true }, async ({ page }) => {
      const scene = page.locator('.scene').filter({ hasText: 'Five motions and one card standing still.' });
      assert.ok(await visible(scene), 'the scene with every motion is not drawn');
      await scene.scrollIntoViewIfNeeded();
      const ids = { enters: 3, glows: 4, taps: 5, leaves: 8, copies: 51, still: 7 };
      const motions = await scene.evaluate((s, srcs) => {
        const byThing = {};
        for (const [does, src] of Object.entries(srcs)) {
          const t = [...s.querySelectorAll('.thing')].find(t => [...t.querySelectorAll('img')].some(i => new URL(i.src, location.href).pathname === src));
          byThing[does] = t ? { thing: t, img: t.querySelector('img'), names: t.getAnimations({ subtree: true }).map(a => a.animationName || a.transitionProperty) } : null;
        }
        s.getAnimations({ subtree: true }).forEach(a => { try { a.finish(); } catch {} });
        const ends = {};
        for (const [does, found] of Object.entries(byThing)) {
          if (!found) { ends[does] = null; continue; }
          const m = new DOMMatrix(getComputedStyle(found.img).transform === 'none' ? undefined : getComputedStyle(found.img).transform);
          let opacity = 1, grey = false;
          for (let e = found.img; e && e !== found.thing.parentElement; e = e.parentElement) {
            opacity *= +getComputedStyle(e).opacity;
            grey ||= /grayscale\((1|0\.[5-9])/.test(getComputedStyle(e).filter);
          }
          ends[does] = { names: found.names, angle: Math.round(Math.atan2(m.b, m.a) * 180 / Math.PI), opacity, grey };
        }
        return ends;
      }, Object.fromEntries(Object.entries(ids).map(([k, n]) => [k, picturePath('rich', scryfallId(n))])));
      for (const [does, end] of Object.entries(motions)) assert.ok(end, `the ${does} thing is not drawn as a picture`);
      for (const does of ['enters', 'glows', 'copies']) assert.ok(motions[does].names.length, `a thing that ${does} does not move`);
      const sets = ['enters', 'glows', 'copies'].map(d => motions[d].names.slice().sort().join());
      assert.equal(new Set(sets).size, 3, `enters, glows and copies share a motion: ${sets.join(' | ')}`);
      assert.equal(Math.abs(motions.taps.angle), 90, `a thing that taps ends turned ${motions.taps.angle} degrees`);
      assert.ok(motions.leaves.names.length && (motions.leaves.opacity < 0.9 || motions.leaves.grey), 'a thing that leaves does not fade out');
      assert.deepEqual({ names: motions.still.names, angle: motions.still.angle, opacity: motions.still.opacity },
        { names: [], angle: 0, opacity: 1 }, 'a thing with no does moves');
    }));

  test('A thing that taps turns while its step is shown, from standing to turned, rather than being drawn already turned', () =>
    open('rich', { clock: true }, async ({ page }) => {
      const scene = page.locator('.scene').filter({ hasText: 'Five motions and one card standing still.' });
      assert.ok(await visible(scene), 'the scene with every motion is not drawn');
      await scene.scrollIntoViewIfNeeded();
      const turning = await scene.evaluate((s, src) => {
        const img = [...s.querySelectorAll('.thing img')].find(i => new URL(i.src, location.href).pathname === src);
        const turns = img?.getAnimations().filter(a => a.effect.getKeyframes().some(k => /rotate/.test(k.transform || '')));
        return img ? { turns: turns.length, transform: getComputedStyle(img).transform } : null;
      }, picturePath('rich', scryfallId(5)));
      assert.ok(turning, 'the thing that taps is not drawn as a picture');
      assert.ok(turning.turns > 0, `a thing that taps does not turn: it is drawn as ${turning.transform} with no animation`);
    }));

  test('A blank card standing in for a missing picture taps and leaves as a picture does', () =>
    open('lost-files', { clock: true }, async ({ page, deck }) => {
      const engine = page.locator('#engine');
      assert.ok(await visible(engine), 'the scenes section is not on the page');
      await settlePictures(engine);
      const [waits, taps, leaves] = deck.scenes[0].steps;
      const ended = () => engine.evaluate(e => {
        const blank = [...e.querySelectorAll('.thing *')].find(b => b.children.length === 0 && b.textContent.trim() === 'Faded Rat');
        if (!blank) return null;
        const moving = blank.getAnimations().length;
        blank.getAnimations().forEach(a => { try { a.finish(); } catch {} });
        const s = getComputedStyle(blank), m = new DOMMatrix(s.transform === 'none' ? undefined : s.transform);
        return { moving, angle: Math.round(Math.atan2(m.b, m.a) * 180 / Math.PI), opacity: +s.opacity, grey: /grayscale\((1|0\.[5-9])/.test(s.filter) };
      });
      await nextStep(page, engine, waits.caption);
      assert.ok((await engine.innerText()).includes(taps.caption), 'the scene did not move to the step where Faded Rat taps');
      const tapped = await ended();
      assert.ok(tapped, 'Faded Rat is not drawn on a blank card');
      assert.ok(tapped.moving > 0, 'a blank card that taps does not move');
      assert.equal(Math.abs(tapped.angle), 90, `a blank card that taps ends turned ${tapped.angle} degrees`);
      await nextStep(page, engine, taps.caption);
      assert.ok((await engine.innerText()).includes(leaves.caption), 'the scene did not move to the step where Faded Rat leaves');
      const left = await ended();
      assert.ok(left.moving > 0 && (left.opacity < 0.9 || left.grey), 'a blank card that leaves does not fade out');
    }));

  test('AC14: With reduced motion, a scene shows its last step and does not advance', () =>
    open('rich', { clock: true, reducedMotion: 'reduce' }, async ({ page, deck }) => {
      const engine = page.locator('#engine');
      assert.ok(await visible(engine), 'the scenes section is not on the page');
      await onScreen(engine);
      const shows = async () => {
        const text = await engine.innerText();
        for (const s of deck.scenes) {
          assert.ok(text.includes(s.steps.at(-1).caption), `"${s.title}" does not show its last step`);
          if (s.steps.length > 1) assert.ok(!text.includes(s.steps[0].caption), `"${s.title}" shows its first step`);
        }
      };
      await shows();
      await page.clock.runFor(10000);
      await shows();
    }));

  test('AC15: A scene that names a card not in the deck shows the name and no broken image', () =>
    open('stray', async ({ page }) => {
      const engine = page.locator('#engine');
      assert.ok(await visible(engine), 'the scenes section is not on the page');
      await settlePictures(engine);
      const text = await engine.innerText();
      for (const name of ['Not In This Deck', 'Unlisted Token', 'Lost Picture Rat']) assert.ok(text.includes(name), `"${name}" is not shown`);
      const broken = (await pictures(engine)).filter(p => p.broken).map(p => p.src);
      assert.deepEqual(broken, [], 'the scene shows a broken image');
    }));

  test('AC16: A deck with no scenes has no scenes section', async () => {
    await open('rich', async ({ page }) => assert.ok(await visible(page.locator('#engine')), 'a deck with scenes shows no scenes section'));
    await open('mono', async ({ page }) => assert.ok(!(await visible(page.locator('#engine'))), 'a deck with no scenes shows a scenes section'));
  });

  test('A picture missing from a scene is asked for once, not again at every step', () =>
    open('lost-files', { clock: true }, async ({ page, deck, missing }) => {
      const engine = page.locator('#engine');
      assert.ok(await visible(engine), 'the scenes section is not on the page');
      await settlePictures(engine);
      const src = picturePath('lost-files', byName(deck, 'Faded Rat').scryfall_id);
      const asked = () => missing.filter(p => p === src).length;
      const before = asked();
      assert.ok(before >= 1, 'the missing picture was never asked for, so this test proves nothing');
      const steps = deck.scenes[0].steps;
      for (let i = 0; i < 4; i++) await nextStep(page, engine, steps[i % steps.length].caption);
      await settlePictures(engine);
      assert.equal(asked(), before, `the missing picture was asked for ${asked() - before} more times over four steps`);
      assert.ok(await blankCardNamed(engine, 'Faded Rat'), 'the scene does not show the name on a blank card');
    }));

  test('AC40: A damage thing shows the format\'s starting life and, by the end of its step, that life less the damage with a "−N" mark; a Brawl deck starts at 25 and a Standard deck at 20', async () => {
    for (const name of ['drawn-brawl', 'drawn-standard']) {
      await open(name, { clock: true }, async ({ page, deck }) => {
        const life = STARTING_LIFE[deck.format];
        for (const sceneIndex of deck.scenes.keys()) {
          const { scene, step } = await toLastStep(page, name, sceneIndex);
          const index = step.things.findIndex(t => t.damage !== undefined);
          const { damage, label = 'Opponent' } = step.things[index];
          const start = await readThing(scene, step.caption, index, 'start');
          assert.ok(start, `${name}: "${step.caption}" was no longer shown when its damage was read`);
          assert.deepEqual(numbersIn(start), [life], `${name}: at the start of its step, ${damage} damage shows ${JSON.stringify(start.texts)}, not the starting life ${life}`);
          const end = await atEndOfStep(page, scene, step.caption, index);
          assert.deepEqual(numbersIn(end), [life - damage], `${name}: at the end of its step, ${damage} damage shows ${JSON.stringify(end.texts)}, not ${life - damage}`);
          assert.ok(minusMarkIn(end, damage), `${name}: ${damage} damage shows no "−${damage}" mark: ${JSON.stringify(end.texts)}`);
          assert.ok(end.texts.includes(label), `${name}: ${damage} damage is not labelled "${label}": ${JSON.stringify(end.texts)}`);
        }
      });
    }
  });

  test('AC41: A draw thing shows one card back per card drawn, at most five, each an image of cards/back.jpg, with a "+N" mark and a label; a missing cards/back.jpg shows blank cards and no broken image', async () => {
    const drawIn = step => { const index = step.things.findIndex(t => t.draw !== undefined); return { index, ...step.things[index] }; };
    await open('drawn-brawl', { clock: true }, async ({ page, deck, missing }) => {
      for (const sceneIndex of deck.scenes.keys()) {
        const { scene, step } = await toLastStep(page, 'drawn-brawl', sceneIndex);
        const { index, draw, label = `You draw ${draw}` } = drawIn(step);
        await settlePictures(scene);
        const end = await atEndOfStep(page, scene, step.caption, index);
        const backs = end.pictures.filter(p => p.src === '/drawn-brawl/cards/back.jpg');
        assert.equal(backs.length, Math.min(draw, 5), `a draw of ${draw} shows ${backs.length} card backs; it shows the pictures ${JSON.stringify(end.pictures)} and ${end.blanks} blank cards, and the server did not find ${JSON.stringify(missing)}`);
        assert.equal(end.pictures.length, backs.length, `a draw of ${draw} shows a picture that is not the card back: ${JSON.stringify(end.pictures)}`);
        for (const b of backs) assert.ok(b.loaded, `a card back in a draw of ${draw} did not load`);
        assert.ok(plusMarkIn(end, draw), `a draw of ${draw} shows no "+${draw}" mark: ${JSON.stringify(end.texts)}`);
        assert.ok(end.texts.includes(label), `a draw of ${draw} is not labelled "${label}": ${JSON.stringify(end.texts)}`);
      }
    });
    await open('drawn-no-back', { clock: true }, async ({ page, deck, missing }) => {
      for (const sceneIndex of deck.scenes.keys()) {
        const { scene, step } = await toLastStep(page, 'drawn-no-back', sceneIndex);
        const { index, draw, label = `You draw ${draw}` } = drawIn(step);
        await settlePictures(scene);
        const end = await atEndOfStep(page, scene, step.caption, index);
        assert.equal(end.blanks, Math.min(draw, 5), `with no cards/back.jpg, a draw of ${draw} shows ${end.blanks} blank cards`);
        assert.deepEqual((await pictures(scene)).filter(p => p.broken).map(p => p.src), [], 'the scene shows a broken image');
        assert.ok(plusMarkIn(end, draw), `with no cards/back.jpg, a draw of ${draw} shows no "+${draw}" mark: ${JSON.stringify(end.texts)}`);
        assert.ok(end.texts.includes(label), `with no cards/back.jpg, a draw of ${draw} is not labelled "${label}": ${JSON.stringify(end.texts)}`);
      }
      assert.ok(missing.includes('/drawn-no-back/cards/back.jpg'), 'the page never asked for cards/back.jpg, so this test proves nothing');
    });
  });

  test('AC42: With reduced motion a damage thing shows the lowered life total and a draw thing shows its whole fan, neither moving', () =>
    open('drawn-brawl', { clock: true, reducedMotion: 'reduce' }, async ({ page, deck }) => {
      const life = STARTING_LIFE[deck.format];
      // Where every element of a thing is drawn, relative to the thing, and how.
      const layout = thing => thing.evaluate(t => {
        const at = t.getBoundingClientRect();
        return [t, ...t.querySelectorAll('*')].map(e => {
          const r = e.getBoundingClientRect(), s = getComputedStyle(e);
          return [e.tagName, Math.round(r.left - at.left), Math.round(r.top - at.top), Math.round(r.width), Math.round(r.height), s.opacity, s.transform, s.filter, e.textContent.trim()].join(' ');
        });
      });
      for (const [sceneIndex, s] of deck.scenes.entries()) {
        const scene = page.locator('#engine .scene').nth(sceneIndex);
        assert.ok(await visible(scene), `the scene "${s.title}" is not drawn`);
        await settlePictures(scene);
        const step = s.steps.at(-1);
        const di = step.things.findIndex(t => t.damage !== undefined), wi = step.things.findIndex(t => t.draw !== undefined);
        const { damage } = step.things[di], { draw } = step.things[wi];
        const hitThing = scene.locator('.thing').nth(di), fanThing = scene.locator('.thing').nth(wi);
        const hit = await readThing(scene, step.caption, di, 'now'), fan = await readThing(scene, step.caption, wi, 'now');
        assert.deepEqual(numbersIn(hit), [life - damage], `with reduced motion, ${damage} damage shows ${JSON.stringify(hit.texts)}, not the lowered life ${life - damage}`);
        assert.ok(minusMarkIn(hit, damage), `with reduced motion, ${damage} damage shows no "−${damage}" mark: ${JSON.stringify(hit.texts)}`);
        const backs = fan.pictures.filter(p => p.src === '/drawn-brawl/cards/back.jpg' && p.loaded);
        assert.equal(backs.length, Math.min(draw, 5), `with reduced motion, a draw of ${draw} shows ${backs.length} card backs`);
        assert.equal(hit.running + fan.running, 0, `with reduced motion, ${hit.running} motions run in the damage and ${fan.running} in the draw`);
        const still = [await layout(hitThing), await layout(fanThing)];
        await page.evaluate(() => document.getAnimations().forEach(a => { try { a.finish(); } catch {} }));
        await page.clock.runFor(10000);
        assert.deepEqual([await layout(hitThing), await layout(fanThing)], still, 'with reduced motion, the damage or the draw moves');
      }
    }));

  test('does on a damage or draw thing moves its life total or its fan, and its mark moves as on a thing with no does', () =>
    open('drawn-oddly', { clock: true }, async ({ page, deck }) => {
      const scene = page.locator('#main-scene');
      assert.ok(await visible(scene), 'the scene with damage and drawn cards that move is not drawn');
      await settlePictures(scene);
      await onScreen(scene);
      const [still, leaves, glows] = deck.scenes[0].steps;
      const read = {};
      for (const step of [still, leaves, glows]) {
        read[step.caption] = await whenShown(page, step.caption, async () => {
          const parts = await Promise.all([0, 1].map(i => partsOfThing(scene, step.caption, i)));
          return parts.every(Boolean) ? parts : null;
        });
      }
      for (const [i, kind] of ['damage', 'draw'].entries()) {
        const [s, l, g] = [still, leaves, glows].map(step => read[step.caption][i]);
        assert.ok(s.anchors && l.anchors && g.anchors, `the ${kind} thing shows no life total or card back: ${JSON.stringify([s, l, g])}`);
        assert.ok(l.ended.every(e => e.opacity < 0.9 || e.grey), `a ${kind} thing that leaves ends with its ${kind === 'damage' ? 'life total' : 'fan'} not faded: ${JSON.stringify(l)}`);
        assert.ok(!s.ended.some(e => e.opacity < 0.9 || e.grey), `a ${kind} thing with no does ends faded: ${JSON.stringify(s)}`);
        assert.ok(g.body.some(name => !s.body.includes(name)), `a ${kind} thing that glows moves its ${kind === 'damage' ? 'life total' : 'fan'} as with no does: ${JSON.stringify(g.body)} against ${JSON.stringify(s.body)}`);
        for (const [does, seen] of [['leaves', l], ['glows', g]]) {
          assert.deepEqual(seen.mark, s.mark, `the mark of a ${kind} thing that ${does} moves otherwise than with no does`);
        }
      }
    }));

  test('At the end of its step the "−N" mark sits on the life total\'s circle and the "+N" mark on a card back, in the main scene and a smaller one, at desktop and phone width', async () => {
    // Where the thing's "−N" or "+N" mark is drawn, and whether it touches what it
    // marks: the life total's circle itself, not the square box around it, or a
    // card back as drawn, turned with the fan, not the larger box around the turn.
    const marked = (scene, caption, index) => scene.evaluate((s, { caption, index }) => {
      const t = s.innerText.includes(caption) && s.querySelectorAll('.thing')[index];
      if (!t) return null;
      t.getAnimations({ subtree: true }).forEach(a => { try { a.finish(); } catch {} });
      const ends = [...t.querySelectorAll('*')].filter(e => !e.children.length);
      const mark = ends.find(e => /^[−+]/.test(e.textContent.trim()));
      if (!mark) return { mark: null };
      const m = mark.getBoundingClientRect(), at = { left: Math.round(m.left), top: Math.round(m.top), right: Math.round(m.right), bottom: Math.round(m.bottom) };
      let circle = ends.filter(e => /^\d+$/.test(e.textContent.trim())).at(-1);
      while (circle && circle !== t && getComputedStyle(circle).borderTopLeftRadius !== '50%') circle = circle.parentElement;
      if (circle && circle !== t) {
        const c = circle.getBoundingClientRect(), x = c.left + c.width / 2, y = c.top + c.height / 2;
        const dx = Math.max(m.left - x, 0, x - m.right), dy = Math.max(m.top - y, 0, y - m.bottom);
        return { mark: at, circle: { left: Math.round(c.left), top: Math.round(c.top), width: Math.round(c.width) }, touches: Math.hypot(dx, dy) < c.width / 2 };
      }
      const backs = [...t.querySelectorAll('img')];
      let touches = false;
      for (let px = m.left + 1; px < m.right && !touches; px += 2)
        for (let py = m.top + 1; py < m.bottom && !touches; py += 2)
          touches = document.elementsFromPoint(px, py).some(e => backs.includes(e));
      return { mark: at, backs: backs.length, touches };
    }, { caption, index });
    for (const [width, viewport] of [['desktop', { width: 1280, height: 800 }], ['phone', { width: 375, height: 740 }]]) {
      await open('drawn-brawl', { clock: true, viewport }, async ({ page, deck }) => {
        for (const sceneIndex of deck.scenes.keys()) {
          const { scene, step } = await toLastStep(page, 'drawn-brawl', sceneIndex);
          await settlePictures(scene);
          const where = `at ${width} width, in the ${sceneIndex === 0 ? 'main' : 'smaller'} scene "${step.caption}"`;
          for (const kind of ['damage', 'draw']) {
            const index = step.things.findIndex(t => t[kind] !== undefined);
            const seen = await whenShown(page, step.caption, () => marked(scene, step.caption, index));
            assert.ok(seen.mark && (seen.circle || seen.backs), `${where}, the ${kind} thing shows no mark, or nothing for it to sit on: ${JSON.stringify(seen)}`);
            assert.ok(seen.touches, `${where}, the ${kind === 'damage' ? '"−N" mark is off the life total\'s circle' : '"+N" mark is off every card back'}: ${JSON.stringify(seen)}`);
          }
        }
      });
    }
  });

  test('A badge given on a damage or draw thing is not drawn: its "−N" or "+N" mark is its badge', () =>
    open('drawn-oddly', { reducedMotion: 'reduce' }, async ({ page, deck }) => {
      const scene = page.locator('#engine .scene').nth(1);
      assert.ok(await visible(scene), 'the scene with badges given is not drawn');
      await settlePictures(scene);
      const step = deck.scenes[1].steps[0];
      for (const [i, t] of step.things.entries()) {
        const seen = await readThing(scene, step.caption, i, 'now');
        const kind = t.damage !== undefined ? 'damage' : 'draw';
        assert.ok(!seen.texts.includes(t.badge), `a ${kind} thing given the badge "${t.badge}" draws it: ${JSON.stringify(seen.texts)}`);
        const marks = seen.texts.filter(s => /^[−+]/.test(s));
        assert.deepEqual(marks, [kind === 'damage' ? `−${t.damage}` : `+${t.draw}`], `a ${kind} thing given a badge shows the marks ${JSON.stringify(marks)}`);
      }
    }));

  test('X damage shows "−X" on the starting life, which stays; X cards drawn deals one card back marked "+X" and labelled "You draw X"', () =>
    open('drawn-oddly', { clock: true }, async ({ page, deck }) => {
      const scene = page.locator('#engine .scene').nth(2);
      assert.ok(await visible(scene), 'the scene with X damage and X cards is not drawn');
      await settlePictures(scene);
      const life = STARTING_LIFE[deck.format];
      const { caption } = deck.scenes[2].steps[0];
      const parts = await whenShown(page, caption, () => partsOfThing(scene, caption, 0));
      assert.deepEqual(parts.body, [], `the starting life under X damage takes a hit: ${JSON.stringify(parts.body)} move on it`);
      const start = await whenShown(page, caption, () => readThing(scene, caption, 0, 'start'));
      const hit = await whenShown(page, caption, () => readThing(scene, caption, 0, 'end'));
      assert.deepEqual([numbersIn(start), numbersIn(hit)], [[life], [life]], `X damage shows ${JSON.stringify(start.texts)} and then ${JSON.stringify(hit.texts)}, not the starting life ${life} throughout`);
      assert.ok(hit.texts.includes('−X'), `X damage shows no "−X" mark: ${JSON.stringify(hit.texts)}`);
      assert.ok(hit.texts.includes('Opponent'), `X damage is not labelled "Opponent": ${JSON.stringify(hit.texts)}`);
      const fan = await whenShown(page, caption, () => readThing(scene, caption, 1, 'end'));
      const backs = fan.pictures.filter(p => p.src === '/drawn-oddly/cards/back.jpg');
      assert.equal(backs.length, 1, `X cards drawn shows ${backs.length} card backs; it shows the pictures ${JSON.stringify(fan.pictures)} and ${fan.blanks} blank cards`);
      assert.ok(fan.texts.includes('+X'), `X cards drawn shows no "+X" mark: ${JSON.stringify(fan.texts)}`);
      assert.ok(fan.texts.includes('You draw X'), `X cards drawn is not labelled "You draw X": ${JSON.stringify(fan.texts)}`);
    }));

  test('At phone width a scene with damage and drawn cards scrolls nothing sideways', async () => {
    for (const name of ['drawn-brawl', 'drawn-oddly']) {
      await open(name, { viewport: { width: 360, height: 740 } }, async ({ page }) => {
        assert.ok(await visible(page.locator('#engine')), `${name}: the scenes section is not drawn, so the width check would prove nothing`);
        await page.locator('#engine').scrollIntoViewIfNeeded();
        const widths = await page.evaluate(() => ({ page: document.documentElement.scrollWidth, body: document.body.scrollWidth, view: document.documentElement.clientWidth }));
        assert.ok(widths.page <= widths.view && widths.body <= widths.view, `${name}: the page is ${widths.page} px wide in a ${widths.view} px window`);
      });
    }
  });
});

// ======================================================================
describe('Cards and dialog', () => {
  test('AC17: Cards are grouped by category in the deck\'s order, each group with its count and target', () =>
    open('rich', async ({ page, deck }) => {
      const text = await sectionText(page, 'cards');
      const groups = [...deck.categories.map(c => c.name), 'Maybeboard'];
      let from = 0;
      const starts = groups.map(name => { const at = text.indexOf(name, from); assert.ok(at >= 0, `the group "${name}" is missing or out of order`); from = at + name.length; return at; });
      groups.forEach((name, i) => {
        const body = text.slice(starts[i], starts[i + 1] ?? text.length);
        const meta = deck.categories.find(c => c.name === name);
        const members = name === 'Maybeboard' ? deck.maybeboard : deck.cards.filter(c => c.category === name);
        if (meta) assert.match(body, new RegExp(`\\b${members.reduce((n, c) => n + count(c), 0)} of ${meta.target}\\b`), `"${name}" does not show its count against its target`);
        if (meta?.count_reason) assert.ok(body.includes(meta.count_reason), `"${name}" does not show its count reason`);
        for (const c of members) assert.ok(body.includes(c.name), `${c.name} is not in the group "${name}"`);
      });
    }));

  test('AC18: A rare or mythic card carries its rarity mark; a common does not', () =>
    open('rich', async ({ page }) => {
      const tileText = async name => (await tile(page, 'rich', name)).innerText();
      assert.match(await tileText('Plague Herald'), /\brare\b/i, 'a rare card has no rarity mark');
      assert.match(await tileText('Doom of Ages'), /\bmythic\b/i, 'a mythic card has no rarity mark');
      assert.doesNotMatch(await tileText('Gutter Scout'), /\b(common|uncommon|rare|mythic)\b/i, 'a common card carries a rarity mark');
    }));

  test('AC19: Opening a card shows its picture, name, category, type line, rules text and why', () =>
    open('rich', async ({ page, deck }) => {
      const c = byName(deck, 'Plague Herald');
      const d = await openCard(page, 'rich', c.name);
      await settlePictures(d);
      assert.ok((await pictures(d)).some(p => p.src === picturePath('rich', c.scryfall_id) && p.loaded), 'the dialog does not show the card\'s picture');
      const text = await d.innerText();
      for (const [what, value] of [['name', c.name], ['category', c.category], ['type line', c.copy.type_line], ['rules text', c.copy.text], ['why', c.why]]) {
        assert.ok(text.toLowerCase().includes(value.toLowerCase()), `the dialog does not show the ${what}`);
      }
    }));

  test('AC20: The mana cost in the dialog is drawn as one symbol per cost symbol, coloured by colour, never as raw braces', () =>
    open('rich', async ({ page }) => {
      const d = await openCard(page, 'rich', 'Prism Totem');
      assert.doesNotMatch(await d.innerText(), /[{}]/, 'the dialog shows raw braces');
      const symbols = await d.locator('.mana').first().evaluate(m => [...m.children].map(s => getComputedStyle(s).backgroundColor));
      assert.equal(symbols.length, 6, `{2}{W}{U}{B}{R}{G} is drawn as ${symbols.length} symbols`);
      const [generic, w, u, b, r, g] = symbols.map(s => hsl(rgb(s)));
      assert.ok(generic.s < 0.25, 'the generic symbol is coloured');
      assert.ok(w.l > 0.7, 'white is not drawn light');
      assert.ok(u.h >= 190 && u.h <= 250 && u.s > 0.3, 'blue is not drawn blue');
      assert.ok(b.l < 0.45, 'black is not drawn dark');
      assert.ok((r.h <= 25 || r.h >= 335) && r.s > 0.3, 'red is not drawn red');
      assert.ok(g.h >= 90 && g.h <= 160 && g.s > 0.2, 'green is not drawn green');
    }));

  test('AC21: A card with no why shows no why line; a card that bends a criterion says so in the dialog and under its picture', () =>
    open('rich', async ({ page, deck }) => {
      const withWhy = byName(deck, 'Plague Herald');
      let d = await openCard(page, 'rich', withWhy.name);
      const whyLine = await d.evaluate((root, why) => {
        const e = [...root.querySelectorAll('*')].filter(e => e.textContent.trim() === why).at(-1);
        return e ? { id: e.id, tag: e.tagName, classes: [...e.classList] } : null;
      }, withWhy.why);
      assert.ok(whyLine, 'the why is not in the dialog');
      await closeDialog(page);
      d = await openCard(page, 'rich', 'Fire Lash');
      const stillShown = await d.evaluate((root, line) => {
        const same = line.id ? [document.getElementById(line.id)].filter(Boolean)
          : [...root.querySelectorAll(line.tag)].filter(e => line.classes.every(c => e.classList.contains(c)));
        return same.filter(e => e.checkVisibility()).map(e => e.outerHTML);
      }, whyLine);
      assert.deepEqual(stillShown, [], 'a card with no why shows a why line');
      assert.doesNotMatch(await d.innerText(), /\b(undefined|null)\b/, 'a card with no why shows a placeholder');
      await closeDialog(page);
      const bends = byName(deck, 'Cinder Pact');
      d = await openCard(page, 'rich', bends.name);
      const text = await d.innerText();
      assert.ok(text.includes(bends.bends), 'the dialog does not say what criterion the card bends');
      assert.match(text, /bends?/i);
      await closeDialog(page);
      assert.match(await (await tile(page, 'rich', bends.name)).innerText(), /bends?/i, 'the tile does not say the card bends a criterion');
    }));

  test('A maybeboard card is not a card in the deck: its name in the handbook and the ledger is plain text, and a scene or a pair shows it on a blank card', () =>
    open('second-thoughts', async ({ page, deck }) => {
      const maybe = deck.maybeboard.find(m => m.name === 'Maybe Rat');
      const inDeck = deck.cards.find(c => c.name === 'Marsh Warden');
      for (const id of ['handbook', 'ledger']) {
        const scope = page.locator(`#${id}`);
        assert.ok(await controlsNamed(scope, inDeck.name) > 0, `#${id}: a card in the deck does not open, so this test proves nothing`);
        assert.equal(await controlsNamed(scope, maybe.name), 0, `#${id}: the maybeboard name opens something`);
      }
      for (const id of ['engine', 'handbook']) {
        const scope = page.locator(`#${id}`);
        await settlePictures(scope);
        const srcs = (await pictures(scope)).map(p => p.src);
        assert.ok(srcs.includes(picturePath('second-thoughts', inDeck.scryfall_id)), `#${id}: the deck's card shows no picture`);
        assert.ok(!srcs.includes(picturePath('second-thoughts', maybe.scryfall_id)), `#${id}: the maybeboard card shows its picture as if it were in the deck`);
        assert.ok(await blankCardNamed(scope, maybe.name), `#${id}: the maybeboard card is not its name on a blank card`);
      }
    }));

  test('A maybeboard card opens from the grid, and a swap says which card it is in for, under its picture and in the dialog with its reason', () =>
    open('second-thoughts', async ({ page, deck }) => {
      const later = deck.maybeboard.find(m => m.kind === 'later'), swap = deck.maybeboard.find(m => m.kind === 'swap');
      let d = await openCard(page, 'second-thoughts', later.name);
      assert.ok((await d.innerText()).includes(later.why), 'the maybeboard card\'s dialog does not show its why');
      await closeDialog(page);
      assert.ok((await (await tile(page, 'second-thoughts', swap.name)).innerText()).includes(`In for ${swap.out}`), 'the tile does not say which card the swap is in for');
      d = await openCard(page, 'second-thoughts', swap.name);
      const lines = await d.evaluate((root, { out, why }) => {
        const shown = [...root.querySelectorAll('*')].filter(e => e.checkVisibility());
        return {
          together: shown.some(e => e.textContent.includes(`In for ${out}`) && e.textContent.includes(why) && e.textContent.length < out.length + why.length + 40),
          alone: shown.some(e => e.textContent.trim() === why),
        };
      }, swap);
      assert.ok(lines.together, 'the dialog does not give the swap\'s reason on the line that says which card it is in for');
      assert.ok(!lines.alone, 'the dialog shows the swap\'s reason as the card\'s why');
    }));

  test('A two-part cost is drawn in the dialog as two runs of symbols with // between them', () =>
    open('rich', async ({ page }) => {
      const d = await openCard(page, 'rich', 'Ember Giant');
      const cost = await d.evaluate(root => {
        const first = root.querySelector('.mana');
        if (!first) return null;
        const holder = first.parentElement;
        return { symbols: [...holder.querySelectorAll('.mana')].map(m => m.children.length), text: holder.textContent.replace(/\s+/g, ' ').trim() };
      });
      assert.deepEqual(cost?.symbols, [3, 2], `{2}{R}{R} // {2}{R} is drawn as runs of ${JSON.stringify(cost?.symbols)} symbols`);
      assert.match(cost.text, /\/\//, `the two parts are not separated by //: "${cost.text}"`);
    }));

  test('A category target is shown as written, never read as markup', () =>
    open('second-thoughts', async ({ page, deck }) => {
      const target = deck.categories.find(c => c.name === 'Removal').target;
      assert.ok((await sectionText(page, 'cards')).includes(target), `the target ${target} is not shown as written`);
    }));
});

// ======================================================================
describe('Curve', () => {
  test('AC22: Each bar holds a creature part and an other-spells part whose sizes match the test deck, and the legend names both', () =>
    open('rich', { reducedMotion: 'reduce' }, async ({ page, deck }) => {
      const curve = await finishedCurve(page);
      assert.ok(curve, 'the curve section is not on the page');
      assert.ok(curve.legend, 'the legend does not name both creatures and other spells');
      const want = curveBuckets(deck);
      assert.equal(curve.columns.length, 8, `the curve has ${curve.columns.length} bars`);
      const tallest = Math.max(...curve.columns.map(c => c.creature + c.other));
      const unit = tallest / Math.max(...want.map(b => b.creature + b.other));
      curve.columns.forEach((col, i) => {
        assert.ok(Math.abs(col.creature - want[i].creature * unit) < 2, `bar ${i}: creature part ${col.creature.toFixed(1)} px, want ${want[i].creature} cards`);
        assert.ok(Math.abs(col.other - want[i].other * unit) < 2, `bar ${i}: other-spells part ${col.other.toFixed(1)} px, want ${want[i].other} cards`);
      });
    }));

  test('AC23: The two curve colours are the same whatever the deck\'s colours', async () => {
    const seen = {};
    for (const name of ['rich', 'mono', 'colourless']) {
      await open(name, { reducedMotion: 'reduce' }, async ({ page }) => {
        const curve = await finishedCurve(page);
        assert.ok(curve?.legend, `${name}: the curve has no legend naming both parts`);
        seen[name] = { creature: curve.creature, other: curve.other };
      });
    }
    assert.deepEqual(seen.mono, seen.rich);
    assert.deepEqual(seen.colourless, seen.rich);
    const creature = hsl(rgb(seen.rich.creature)), other = hsl(rgb(seen.rich.other));
    assert.ok(creature.h >= 30 && creature.h <= 55 && creature.s > 0.4, `creatures are not gold (hue ${creature.h.toFixed(0)})`);
    assert.ok(other.h >= 170 && other.h <= 200 && other.s > 0.2, `other spells are not teal (hue ${other.h.toFixed(0)})`);
  });

  test('AC24: The curve note is shown above the bars', () =>
    open('rich', { reducedMotion: 'reduce' }, async ({ page, deck }) => {
      const curve = await finishedCurve(page);
      assert.ok(curve?.legend, 'the curve has no legend naming both parts');
      const note = await page.evaluate(text => {
        const e = [...document.querySelectorAll('#curve *')].filter(e => e.textContent.trim() === text).at(-1);
        return e && e.checkVisibility() ? e.getBoundingClientRect().bottom : null;
      }, deck.curve_note);
      assert.ok(note !== null, 'the curve note is not shown');
      const barsTop = Math.min(...curve.columns.flatMap(c => c.tops));
      assert.ok(note <= barsTop, 'the curve note is not above the bars');
    }));
});

// ======================================================================
describe('Handbook', () => {
  test('AC25: The chapter list links to every chapter and stays in view while the chapters scroll, at desktop width', () =>
    open('rich', async ({ page, deck }) => {
      const list = page.locator('#handbook nav, #handbook [role="navigation"]');
      assert.ok(await visible(list), 'the handbook has no chapter list');
      const links = await list.first().locator('a').evaluateAll(as => as.map(a => {
        const target = a.hash && document.getElementById(decodeURIComponent(a.hash.slice(1)));
        return { text: a.innerText.trim(), target: target ? target.innerText : null };
      }));
      assert.deepEqual(links.map(l => l.text), deck.handbook.map(c => c.title));
      links.forEach((l, i) => assert.ok(l.target?.includes(deck.handbook[i].title), `the link to "${l.text}" does not reach its chapter`));
      for (const title of deck.handbook.slice(1).map(c => c.title)) {
        const where = await page.evaluate(title => {
          const h = [...document.querySelectorAll('#handbook h1, #handbook h2, #handbook h3, #handbook h4')].find(h => h.innerText.includes(title));
          window.scrollTo({ top: h.getBoundingClientRect().top + scrollY - 40, behavior: 'instant' });
          return { section: document.getElementById('handbook').getBoundingClientRect().top };
        }, title);
        assert.ok(where.section < 0, 'the handbook is too short to scroll past its top');
        const box = await list.first().boundingBox();
        assert.ok(box && box.y >= 0 && box.y < 800, `while "${title}" is read, the chapter list is at ${box?.y} px`);
      }
    }));

  test('AC26: Chapters are numbered in order', () =>
    open('rich', async ({ page, deck }) => {
      const headings = await page.evaluate(() => [...document.querySelectorAll('#handbook h1, #handbook h2, #handbook h3, #handbook h4')].map(h => h.innerText.replace(/\s+/g, ' ').trim()));
      deck.handbook.forEach((chapter, i) => {
        const heading = headings.find(h => h.includes(chapter.title));
        assert.ok(heading, `the chapter "${chapter.title}" has no heading`);
        assert.match(heading, new RegExp(`\\b${NUMBER_WORDS[i]}\\b`, 'i'), `"${chapter.title}" is not numbered ${NUMBER_WORDS[i]}`);
      });
    }));

  test('AC27: Each kind of block draws: paragraphs, a bullet list, a timeline with its turn labels, a note, and pairs with both cards\' pictures', () =>
    open('rich', async ({ page, deck }) => {
      const handbook = page.locator('#handbook');
      assert.ok(await visible(handbook), 'the handbook is not on the page');
      const drawn = await handbook.evaluate(h => {
        const deepest = text => [...h.querySelectorAll('*')].filter(e => e.checkVisibility() && e.textContent.includes(text)).at(-1) || null;
        const marked = (e, stop) => { for (; e && e !== stop; e = e.parentElement) { const s = getComputedStyle(e);
          if (!['rgba(0, 0, 0, 0)', 'transparent'].includes(s.backgroundColor) || parseFloat(s.borderLeftWidth) > 0) return true; } return false; };
        const para = (text) => [...h.querySelectorAll('p')].find(p => p.textContent.includes(text));
        const p1 = para('grows the Snail while'), p2 = para('drains as the swarm grows');
        const items = [...h.querySelectorAll('li')].map(li => li.innerText.trim());
        const t1 = [...h.querySelectorAll('*')].find(e => e.children.length === 0 && e.textContent.trim() === 'T1');
        let row = t1; while (row && row !== h && !row.textContent.includes('Play a Swamp and Gutter Scout.')) row = row.parentElement;
        const note = deepest('A token that leaves the battlefield stops existing.');
        return {
          paragraphs: !!(p1 && p2 && p1 !== p2),
          list: items,
          turn: !!(t1 && t1.checkVisibility() && row && row !== h && !row.textContent.includes('Play Sewer Captain.')),
          note: !!note,
          noteMarked: note ? marked(note, h) : false,
          plainMarked: p1 ? marked(p1, h) : null,
        };
      });
      assert.ok(drawn.paragraphs, 'a text block with a blank line is not drawn as two paragraphs');
      assert.deepEqual(drawn.list.filter(i => /^(Keep Grim Bargain|Hold Cinder Pact)/.test(i)).length, 2, 'the bullet list is not drawn as list items');
      assert.ok(drawn.turn, 'the timeline does not show T1 beside its turn');
      assert.ok(drawn.note, 'the note is not drawn');
      assert.ok(drawn.noteMarked && !drawn.plainMarked, 'the note is not highlighted apart from the paragraphs');
      const pair = deck.handbook[3].blocks[0].pairs[0];
      const pairBox = handbook.locator('*').filter({ hasText: pair.text }).filter({ has: page.locator('img') }).last();
      assert.ok(await visible(pairBox), 'the pair is not drawn with pictures');
      await settlePictures(pairBox);
      const srcs = (await pictures(pairBox)).filter(p => p.loaded).map(p => p.src);
      for (const name of pair.cards) assert.ok(srcs.includes(picturePath('rich', byName(deck, name).scryfall_id)), `the pair does not show ${name}'s picture`);
    }));

  test('AC28: A full card name in handbook text opens that card\'s dialog; a name that is not a card in the deck is plain text', () =>
    open('rich', async ({ page }) => {
      const handbook = page.locator('#handbook');
      assert.ok(await visible(handbook), 'the handbook is not on the page');
      const control = name => handbook.locator('button, a, [role="button"], [role="link"]').filter({ hasText: new RegExp(`^\\s*${name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\s*$`) });
      assert.ok(await visible(control('Plague Herald')), 'the full name Plague Herald does not open its card');
      await control('Plague Herald').first().click();
      const d = dialog(page);
      assert.ok(await until(() => d.count()), 'clicking Plague Herald opens no dialog');
      assert.ok((await d.first().innerText()).includes('Plague Herald'), 'the dialog is not Plague Herald\'s');
      await closeDialog(page);
      assert.ok((await handbook.innerText()).includes('Lightning Bolt'), 'the name Lightning Bolt is not in the text');
      assert.equal(await control('Lightning Bolt').count(), 0, 'a name not in the deck opens something');
      assert.equal(await control('Vesk').count(), 0, 'a short name opens something');
    }));

  test('AC29: A deck with no handbook says the handbook is written once the deck is complete', () =>
    open('mono', async ({ page }) => {
      assert.match(await sectionText(page, 'handbook'), /written once the deck is complete/i);
      const hero = page.locator('#top');
      assert.ok(await visible(hero), 'the hero is not on the page');
      const toHandbook = hero.getByRole('link', { name: /handbook/i }).or(hero.getByRole('button', { name: /handbook/i }));
      assert.equal(await toHandbook.filter({ visible: true }).count(), 0, 'the hero has a handbook button for a deck with no handbook');
    }));

  test('A picture missing inside a handbook pair: the card\'s name on a blank card', () =>
    open('lost-files', async ({ page }) => {
      const handbook = page.locator('#handbook');
      await settlePictures(handbook);
      assert.deepEqual((await pictures(handbook)).filter(p => p.broken).map(p => p.src), [], 'the pair shows a broken image');
      assert.ok(await blankCardNamed(handbook, 'Faded Rat'), 'the pair does not show the name on a blank card');
    }));
});

// ======================================================================
describe('Ledger', () => {
  const showEarlier = page => page.locator('#ledger').locator('summary, button, a, [role="button"]').filter({ hasText: /earlier/i });

  test('AC30: The ledger shows each entry\'s kind, subject and reason, and no Scryfall id', () =>
    open('rich', async ({ page }) => {
      await sectionText(page, 'ledger');
      if (await visible(showEarlier(page))) await showEarlier(page).first().click();
      const text = await page.locator('#ledger').innerText();
      assert.doesNotMatch(text, UUID, 'the ledger shows a Scryfall id');
      for (const [, kind, subject, why] of RICH_LEDGER) {
        const row = await page.locator('#ledger').evaluate((l, { why, subject, kind, others }) => {
          let e = [...l.querySelectorAll('*')].filter(e => e.textContent.includes(why)).at(-1);
          while (e && e !== l && !(e.innerText.includes(subject) && new RegExp(`\\b${kind}\\b`, 'i').test(e.innerText))) e = e.parentElement;
          return e && e !== l && !others.some(o => e.innerText.includes(o)) ? e.innerText : null;
        }, { why, subject: ledgerSubject(subject), kind: KIND_WORDS[kind], others: RICH_LEDGER.map(e => e[3]).filter(o => o !== why) });
        assert.ok(row, `the entry "${why}" does not show its kind ${KIND_WORDS[kind]} and subject ${ledgerSubject(subject)} together`);
      }
    }));

  test('AC31: The newest entry is first; entries beyond eight sit behind one control that shows them', () =>
    open('rich', async ({ page }) => {
      const reasons = RICH_LEDGER.map(e => e[3]).reverse();
      const order = text => reasons.map(r => text.indexOf(r));
      let positions = order(await sectionText(page, 'ledger'));
      assert.ok(positions.slice(0, 8).every(p => p >= 0), 'the newest eight entries are not all shown');
      assert.ok(positions.slice(0, 8).every((p, i, a) => i === 0 || p > a[i - 1]), 'the entries are not newest first');
      assert.ok(positions.slice(8).every(p => p < 0), 'entries beyond eight are shown before asking');
      assert.equal(await showEarlier(page).filter({ visible: true }).count(), 1, 'there is not exactly one control for the earlier entries');
      assert.match(await showEarlier(page).first().innerText(), /Show the 3 earlier decisions/i);
      await showEarlier(page).first().click();
      positions = order(await page.locator('#ledger').innerText());
      assert.ok(positions.every((p, i, a) => p >= 0 && (i === 0 || p > a[i - 1])), 'after the control, not every entry is shown newest first');
    }));

  test('A ledger line the page cannot split is shown as written', () =>
    open('lost-files', async ({ page }) => {
      const text = await sectionText(page, 'ledger');
      assert.ok(text.includes(LINE_THE_PAGE_CANNOT_SPLIT), 'the line is not shown');
      assert.doesNotMatch(text, /\b(undefined|null)\b/, 'the line shows a placeholder');
    }));

  test('A ledger line the page cannot split is shown without its Scryfall id', () =>
    open('lost-files', async ({ page }) => {
      const text = await sectionText(page, 'ledger');
      assert.doesNotMatch(text, UUID, 'the ledger shows a Scryfall id');
      assert.ok(text.includes(ledgerSubject(LINE_THE_PAGE_CANNOT_SPLIT_WITH_ID)), `the line is not shown as "${ledgerSubject(LINE_THE_PAGE_CANNOT_SPLIT_WITH_ID)}"`);
    }));

  test('LEDGER.md fails to arrive: the ledger says "Nothing logged yet.", the cards still open and the Arena list is drawn', () =>
    open('rich', { refuse: ['/LEDGER.md'] }, async ({ page, deck, requested }) => {
      assert.ok(requested.some(p => p.endsWith('/LEDGER.md')), 'the page never asked for LEDGER.md, so nothing was refused');
      assert.match(await until(async () => (await page.locator('#ledger').innerText()) || null) || '', /Nothing logged yet\./, 'the ledger does not say nothing is logged');
      const d = await openCard(page, 'rich', 'Plague Herald');
      assert.ok((await d.innerText()).includes('Plague Herald'));
      await closeDialog(page);
      const pre = page.locator('pre').filter({ visible: true });
      assert.equal(await pre.count(), 1, 'the Arena list is not drawn');
      assert.equal(await page.locator('#arena-list').textContent(), arenaList(deck));
    }));
});

// ======================================================================
describe('Written in the repo', () => {
  const skill = () => fs.readFileSync(path.join(REPO, 'plugins/deckwright/skills/deckwright/SKILL.md'), 'utf8');
  const example = () => JSON.parse(fs.readFileSync(EXAMPLE, 'utf8'));

  test('P13, AC33: A scene is drawn from whole card pictures: each card or token thing of a step is one image of its picture, and no scene is an SVG drawing', () =>
    open('rich', { clock: true }, async ({ page, deck }) => {
      const engine = page.locator('#engine');
      assert.ok(await visible(engine), 'the scenes section is not on the page');
      await settlePictures(engine);
      const idOf = t => t.card ? byName(deck, t.card).scryfall_id : deck.tokens.find(k => k.name === t.token).scryfall_id;
      const drawn = await engine.evaluate(e => ({
        svg: e.querySelectorAll('svg').length,
        scenes: [...e.querySelectorAll('.scene')].map(s => [...s.querySelectorAll('.thing')].map(t => [...t.querySelectorAll('img')].map(i => new URL(i.src, location.href).pathname))),
      }));
      assert.equal(drawn.svg, 0, 'a scene draws an SVG');
      const want = deck.scenes.map(s => s.steps[0].things.map(t => t.card || t.token ? [picturePath('rich', idOf(t))] : []));
      assert.deepEqual(drawn.scenes, want, 'a scene\'s first step does not draw one picture for each card or token thing and none for any other thing');
    }));

  test('AC34: deck.example.json is version 2 and the page draws it with no console error', () =>
    open('example', async ({ page, errors, deck }) => {
      assert.equal(deck.version, 2);
      assert.equal((await page.locator('h1').innerText()).replace(/\s+/g, ' ').trim(), deck.name, 'the example deck\'s name is not drawn');
      await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
      await page.waitForLoadState('networkidle');
      assert.deepEqual(errors, []);
    }));

  test('AC35: The page asks for nothing outside its own folder except the font stylesheet and its fonts', async () => {
    for (const name of ['rich', 'mono', 'several', 'colourless', 'stray', 'example']) {
      await open(name, async ({ page, outside, deck }) => {
        await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
        await page.waitForLoadState('networkidle');
        assert.deepEqual(outside, [], `${name} asked for something outside its folder`);
        assert.equal((await page.locator('h1').innerText()).replace(/\s+/g, ' ').trim(), deck.name, `${name} does not render with the fonts blocked`);
      });
    }
  });

  test('AC36: The Arena list and its copy button work as before', () =>
    open('rich', async ({ page, deck }) => {
      const list = arenaList(deck);
      const pre = page.locator('pre').filter({ hasText: 'Commander' }).filter({ visible: true });
      assert.equal(await pre.count(), 1, 'the Arena list is not shown on the page');
      assert.equal(await page.locator('#arena-list').textContent(), list);
      const section = pre.locator('xpath=ancestor::section[1]');
      const copy = section.getByRole('button', { name: /copy/i }).filter({ visible: true });
      assert.equal(await copy.count(), 1, 'the Arena list has no copy button beside it');
      assert.equal(await copiedBy(page, copy), list);
    }));

  test('deck.example.json shows every new field and every kind of thing and block', () => {
    const deck = example();
    for (const field of ['hero', 'pitch', 'curve_note', 'tokens', 'scenes', 'handbook']) assert.ok(deck[field] !== undefined, `no ${field}`);
    assert.ok(deck.cards.some(c => c.why), 'no card has a why');
    assert.ok(deck.cards.some(c => c.copy?.rarity), 'no card has a rarity in its copy');
    assert.ok(deck.cards.some(c => c.scryfall_id === deck.hero), 'the hero is not a card in the deck');
    assert.ok(deck.tokens.every(t => t.name && t.scryfall_id), 'a token lacks a name or a Scryfall id');
    assert.ok(deck.scenes.some(s => s.lede), 'no scene has a lede');
    const things = deck.scenes.flatMap(s => s.steps.flatMap(st => st.things));
    for (const kind of ['card', 'token', 'pile', 'mana', 'chip']) assert.ok(things.some(t => t[kind] !== undefined), `no thing is a ${kind}`);
    for (const extra of ['label', 'badge', 'does']) assert.ok(things.some(t => t[extra] !== undefined), `no thing carries ${extra}`);
    const names = new Set(deck.cards.map(c => c.name)), tokens = new Set(deck.tokens.map(t => t.name));
    for (const t of things) {
      if (t.card) assert.ok(names.has(t.card), `the scene names ${t.card}, not a card in the example`);
      if (t.token) assert.ok(tokens.has(t.token), `the scene names the token ${t.token}, not in tokens`);
    }
    const blocks = deck.handbook.flatMap(c => c.blocks || []);
    for (const kind of ['text', 'list', 'turns', 'note', 'pairs']) assert.ok(blocks.some(b => b[kind] !== undefined), `no block is ${kind}`);
  });

  test('evals/starts/build.py writes version 2, and the saved starts are version 2', () => {
    for (const dir of fs.readdirSync(path.join(REPO, 'evals/starts'), { withFileTypes: true }).filter(d => d.isDirectory() && d.name !== '__pycache__')) {
      const saved = JSON.parse(fs.readFileSync(path.join(REPO, 'evals/starts', dir.name, 'deck.json'), 'utf8'));
      assert.equal(saved.version, 2, `evals/starts/${dir.name} is version ${saved.version}`);
    }
    // build.py searches Scryfall; this stands a canned search in for it.
    const written = execFileSync('python3', ['-I', '-c', `
import json, pathlib, sys, tempfile, importlib.util
spec = importlib.util.spec_from_file_location("build", sys.argv[1])
sys.path.insert(0, str(pathlib.Path(sys.argv[1]).parent.parent))
build = importlib.util.module_from_spec(spec); spec.loader.exec_module(build)
card = lambda i, name, type_line: {"id": f"00000000-0000-4000-8000-{i:012d}", "name": name, "type_line": type_line,
    "mana_cost": "{1}{B}", "oracle_text": "", "rarity": "rare"}
build.search = lambda query: [card(1, "A Commander", "Legendary Creature — Rat")] + [card(i, f"Card {i}", "Creature — Rat") for i in range(2, 40)]
build.HERE = pathlib.Path(tempfile.mkdtemp())
name, deck = next(iter(build.DECKS.items()))
build.build(name, deck)
print((build.HERE / name / "deck.json").read_text())
`, path.join(REPO, 'evals/starts/build.py')], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] });
    assert.equal(JSON.parse(written).version, 2);
  });

  test('A card\'s copy gives its mana value: deck.example.json shows it, SKILL.md names it and evals/starts/build.py saves Scryfall\'s cmc as it', () => {
    assert.ok(example().cards.some(c => typeof c.copy?.mana_value === 'number'), 'no card in deck.example.json has a mana value in its copy');
    assert.match(skill(), /display copy \([^)]*mana value[^)]*\)/, 'SKILL.md does not name the mana value among the copy\'s fields');
    // build.py searches Scryfall; this stands a canned search of one adventure card in for it.
    const written = execFileSync('python3', ['-I', '-c', `
import json, pathlib, sys, tempfile, importlib.util
spec = importlib.util.spec_from_file_location("build", sys.argv[1])
sys.path.insert(0, str(pathlib.Path(sys.argv[1]).parent.parent))
build = importlib.util.module_from_spec(spec); spec.loader.exec_module(build)
card = lambda i, name, type_line: {"id": f"00000000-0000-4000-8000-{i:012d}", "name": name, "type_line": type_line,
    "mana_cost": "{2}{R} // {1}{R}", "cmc": 3.0, "oracle_text": "", "rarity": "rare"}
build.search = lambda query: [card(1, "A Commander", "Legendary Creature — Giant")] + [card(i, f"Card {i}", "Creature — Giant // Instant — Adventure") for i in range(2, 40)]
build.HERE = pathlib.Path(tempfile.mkdtemp())
name, deck = next(iter(build.DECKS.items()))
build.build(name, deck)
print((build.HERE / name / "deck.json").read_text())
`, path.join(REPO, 'evals/starts/build.py')], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] });
    for (const c of JSON.parse(written).cards) assert.equal(c.copy.mana_value, 3, `${c.name} is saved with mana value ${c.copy.mana_value}`);
  });

  test('A packed deck whose scene draws cards shows its card backs from window.DECK_FILES, without asking for cards/back.jpg', () =>
    open('packed-drawn', { reducedMotion: 'reduce' }, async ({ page, deck, requested }) => {
      const scene = page.locator('#main-scene');
      assert.ok(await visible(scene), 'the packed deck\'s scene is not drawn');
      await settlePictures(scene);
      const step = deck.scenes[0].steps.at(-1), index = step.things.findIndex(t => t.draw !== undefined);
      const backs = await scene.locator('.thing').nth(index).evaluate(t => [...t.querySelectorAll('img')].map(i => ({ packed: i.src.startsWith('data:image/'), loaded: i.complete && i.naturalWidth > 0 })));
      const blanks = (await readThing(scene, step.caption, index, 'now')).blanks;
      assert.equal(backs.filter(b => b.packed && b.loaded).length, step.things[index].draw, `a packed draw of ${step.things[index].draw} shows the card backs ${JSON.stringify(backs)} and ${blanks} blank cards`);
      await page.waitForLoadState('networkidle');
      assert.deepEqual(requested.filter(p => p.endsWith('/cards/back.jpg')), [], 'the packed page asked the server for cards/back.jpg');
    }));

  // That SKILL.md says when the card back is saved, and that ADR-0008 names both
  // kinds, is checked by reading.
  test('AC43: deck.example.json shows a damage and a draw thing, and SKILL.md names cards/back.jpg', () => {
    const things = example().scenes.flatMap(s => s.steps.flatMap(st => st.things));
    for (const kind of ['damage', 'draw']) assert.ok(things.some(t => t[kind] !== undefined), `no thing in deck.example.json is a ${kind}`);
    assert.ok(skill().includes('cards/back.jpg'), 'SKILL.md does not name cards/back.jpg');
  });

  test('A page given every file in window.DECK_FILES draws the deck without asking for deck.json, LEDGER.md or any picture', () =>
    open('packed', async ({ page, deck, requested }) => {
      assert.equal((await page.locator('h1').innerText()).replace(/\s+/g, ' ').trim(), deck.name, 'the packed deck is not drawn');
      assert.ok((await until(() => heroArt(page.locator('#top'))))?.includes('data:image'), 'the hero does not show the packed art');
      await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
      const cards = page.locator('#cards');
      await settlePictures(cards);
      const shown = await pictures(cards);
      assert.ok(shown.length && shown.every(p => p.loaded), 'a card picture in the grid did not load from the packed files');
      assert.ok((await sectionText(page, 'ledger')).includes(RICH_LEDGER.at(-1)[3]), 'the packed ledger is not drawn');
      await page.waitForLoadState('networkidle');
      assert.deepEqual(requested.filter(p => /\/(deck\.json|LEDGER\.md)$|\/(cards|art)\//.test(p)), [], 'the page asked the server for a packed file');
    }));
});

// ======================================================================
// What #offer draws for each card on offer, in the order deck.json gives them:
// the smallest box around its reason that also shows its picture, or its name
// on a blank card, and no other offered card's reason. Null for a card with no
// such box.
async function readOffer(page, deckName) {
  const offer = page.locator('#offer');
  assert.ok(await visible(offer), 'the #offer section is not drawn');
  await settlePictures(offer);
  return offer.evaluate((root, { cards, folder }) => {
    const reasons = cards.map(c => c.reason);
    const cardShaped = e => e.offsetWidth > 0 && e.offsetHeight / e.offsetWidth > 1.3 && e.offsetHeight / e.offsetWidth < 1.5;
    const all = [...root.querySelectorAll('*')];
    return cards.map(c => {
      const src = `/${folder}/cards/${c.scryfall_id}.jpg`;
      const img = el => [...el.querySelectorAll('img')].find(i => new URL(i.src, location.href).pathname === src);
      const blank = el => [...el.querySelectorAll('*')].find(b => b.tagName !== 'IMG' && cardShaped(b) && !b.querySelector('img') && b.textContent.trim() === c.name && b.checkVisibility());
      let box = all.filter(e => e.textContent.includes(c.reason)).at(-1);
      while (box && box !== root && !img(box) && !blank(box)) box = box.parentElement;
      if (!box || box === root || reasons.some(r => r !== c.reason && box.textContent.includes(r))) return null;
      const picture = img(box);
      return {
        at: all.indexOf(box),
        picture: picture ? { loaded: picture.complete && picture.naturalWidth > 0 } : null,
        blank: !!blank(box),
        leaves: [...box.querySelectorAll('*')].filter(e => e.children.length === 0 && e.checkVisibility()).map(e => e.textContent.trim()).filter(Boolean),
        text: box.textContent.replace(/\s+/g, ' '),
      };
    });
  }, { cards: offeredCards(deckOf(deckName)), folder: deckName });
}

const numberedAs = (seen, n) => seen.leaves.some(t => new RegExp(`^(No\\.?\\s*|#)?${n}(?![\\d/])`).test(t));
async function offerHeadings(page) {
  const offer = page.locator('#offer');
  assert.ok(await visible(offer), 'the #offer section is not drawn');
  return offer.evaluate(o => [...o.querySelectorAll('h1, h2, h3, h4, h5, h6')].filter(h => h.checkVisibility()).map(h => h.textContent.trim()));
}

describe('Cards on offer', () => {
  test('P1: A deck with a round on offer draws #offer between the hero and the scenes, under a heading naming the category, each card numbered across the groups with its picture and its reason', () =>
    open('offered', async ({ page, deck }) => {
      const where = await page.evaluate(() => {
        const [top, offer, engine] = ['top', 'offer', 'engine'].map(id => document.getElementById(id));
        if (!offer) return null;
        return { afterHero: !!(top.compareDocumentPosition(offer) & Node.DOCUMENT_POSITION_FOLLOWING), beforeScenes: !!(offer.compareDocumentPosition(engine) & Node.DOCUMENT_POSITION_FOLLOWING) };
      });
      assert.ok(where, 'the page has no #offer section');
      assert.deepEqual(where, { afterHero: true, beforeScenes: true }, '#offer is not between the hero and the scenes');
      const headings = await offerHeadings(page);
      assert.ok(headings.some(h => h.includes(deck.offer.category)), `no heading in #offer names the category ${deck.offer.category}: ${JSON.stringify(headings)}`);
      const cards = offeredCards(deck), seen = await readOffer(page, 'offered');
      cards.forEach((c, i) => {
        assert.ok(seen[i], `${c.name}: no box in #offer shows its reason with its picture`);
        assert.ok(numberedAs(seen[i], i + 1), `${c.name} is not numbered ${i + 1}: ${JSON.stringify(seen[i].leaves)}`);
        if (c.scryfall_id === MISSING_OFFERED_PICTURE) assert.ok(seen[i].blank && !seen[i].picture, `${c.name}, whose picture was never saved, is not its name on a blank card`);
        else assert.ok(seen[i].picture?.loaded, `${c.name}'s picture did not load`);
      });
      assert.deepEqual(seen.map(s => s.at), seen.map(s => s.at).sort((a, b) => a - b), 'the cards on offer are not drawn in the order they are numbered');
      const marked = await page.locator('#offer').evaluate(o => o.querySelectorAll('i').length === 0 && o.textContent.includes('& <i>grows</i>'));
      assert.ok(marked, 'a reason holding markup is not shown as written');
    }));

  test('P2: Each group is drawn under its heading, with "N of TOTAL shown" when it has a total; a round of one group with no heading draws no group heading', async () => {
    await open('offered', async ({ page, deck }) => {
      const [first, second] = deck.offer.groups;
      const headings = await offerHeadings(page);
      for (const g of [first, second]) assert.ok(headings.includes(g.heading), `the group "${g.heading}" has no heading: ${JSON.stringify(headings)}`);
      const text = (await page.locator('#offer').textContent()).replace(/\s+/g, ' ');
      const shown = `${first.cards.length} of ${first.total} shown`;
      assert.deepEqual(text.match(/\d+ of \d+ shown/g), [shown], `#offer does not say "${shown}" once, for the one group with a total`);
      const at = t => text.indexOf(t);
      assert.ok(at(first.heading) < at(shown) && at(shown) < at(first.cards[0].reason), `"${shown}" is not drawn between its group's heading and its first card`);
      assert.ok(at(first.cards.at(-1).reason) < at(second.heading) && at(second.heading) < at(second.cards[0].reason), 'the second group\'s heading is not drawn between the two groups\' cards');
    });
    await open('offered-unheaded', async ({ page, deck }) => {
      const headings = await offerHeadings(page);
      assert.equal(headings.length, 1, `a round of one unheaded group draws the headings ${JSON.stringify(headings)}`);
      assert.ok(headings[0].includes(deck.offer.category), `the one heading, ${JSON.stringify(headings[0])}, does not name the category`);
      assert.doesNotMatch(await page.locator('#offer').textContent(), /\bshown\b/, 'a group with no total says how many are shown');
      const seen = await readOffer(page, 'offered-unheaded');
      offeredCards(deck).forEach((c, i) => assert.ok(seen[i] && numberedAs(seen[i], i + 1), `${c.name} is not drawn numbered ${i + 1}`));
    });
  });

  test('P3: A suggested card is marked "Suggested", a crossover card "Crossover" with "Printed on Arena as" its printed name when it has one, and no card is marked otherwise', () =>
    open('offered', async ({ page, deck }) => {
      const cards = offeredCards(deck), seen = await readOffer(page, 'offered');
      cards.forEach((c, i) => {
        assert.ok(seen[i], `${c.name}: no box in #offer shows its reason with its picture`);
        assert.equal(seen[i].leaves.includes('Suggested'), c.suggested === true, `${c.name} is ${c.suggested ? 'not ' : ''}marked Suggested: ${JSON.stringify(seen[i].leaves)}`);
        assert.equal(seen[i].leaves.includes('Crossover'), c.crossover === true, `${c.name} is ${c.crossover ? 'not ' : ''}marked Crossover: ${JSON.stringify(seen[i].leaves)}`);
        const printed = c.printed_name ? `Printed on Arena as ${c.printed_name}` : 'Printed on Arena as';
        assert.equal(seen[i].text.includes(printed), !!c.printed_name, `${c.name}: ${c.printed_name ? `"${printed}" is not shown` : 'a printed name is shown for a card with none'}: ${seen[i].text}`);
      });
    }));

  test('P4: With no round on offer, or a round with no cards, #offer is hidden and holds nothing', async () => {
    for (const name of ['rich', 'offer-no-groups', 'offer-no-cards']) {
      await open(name, async ({ page }) => {
        const offer = await page.evaluate(() => {
          const o = document.getElementById('offer');
          return o && { shown: o.checkVisibility(), children: o.childElementCount, text: o.textContent.trim() };
        });
        assert.ok(offer, `${name}: the page has no #offer section`);
        assert.deepEqual(offer, { shown: false, children: 0, text: '' }, `${name}: #offer is drawn or holds something`);
      });
    }
  });

  test('P4: Cards on offer are not counted in the headline numbers, the curve or the Arena list', async () => {
    await open('offered', async ({ page, deck }) => {
      assert.ok(await visible(page.locator('#offer')), 'the #offer section is not drawn, so this test proves nothing');
      const want = deckStats(deck);
      const { found } = await headline(page, { cards: 'cards', rats: 'Rats?', lands: 'lands', average: 'average mana value', rares: 'rares and mythics' });
      assert.equal(found.cards, want.cards, 'cards');
      assert.equal(found.rats, 5, 'Rats');
      assert.equal(found.lands, want.lands, 'lands');
      assert.ok(Math.abs(found.average - want.average) < 0.051, `average mana value ${found.average}, want ${want.average.toFixed(2)}`);
      assert.equal(found.rares, want.rares, 'rares and mythics');
      assert.equal(await page.locator('#hero-line').textContent(), 'Brawl · 29 of 100 cards · In progress');
      assert.equal(await page.locator('#arena-list').textContent(), arenaList(deck));
    });
    await open('offered', { reducedMotion: 'reduce' }, async ({ page, deck }) => {
      const curve = await finishedCurve(page);
      assert.ok(curve?.legend, 'the curve is not drawn');
      const want = curveBuckets(deck);
      const unit = Math.max(...curve.columns.map(c => c.creature + c.other)) / Math.max(...want.map(b => b.creature + b.other));
      curve.columns.forEach((col, i) => assert.ok(Math.abs(col.creature - want[i].creature * unit) < 2, `bar ${i}: creature part ${col.creature.toFixed(1)} px, want ${want[i].creature} cards`));
    });
  });
});

// ======================================================================
describe('Without a name, by layout, by format', () => {
  test('P5: A deck with no name, or an empty one, is titled by its format and its first theme criterion, or by its format alone', async () => {
    for (const [name, title] of [['nameless-with-theme', 'Brawl · Rats'], ['nameless-empty-name', 'Standard · Big green creatures'], ['nameless-without-theme', 'Brawl']]) {
      await open(name, async ({ page }) => {
        assert.equal(await page.locator('#top h1').innerText(), title, `${name}: the hero's heading`);
        assert.equal(await page.title(), title, `${name}: the page's title`);
      });
    }
  });

  test('P6: The Arena list writes a modal double-faced, transform, adventure or prepare card by its front face, and a split card, a card of another layout and one with no layout by its full name', () =>
    open('layouts', async ({ page }) => {
      const want = [
        'Commander',
        '1 Moorland Watcher',
        '',
        'Deck',
        '1 Sundering Eruption',
        '1 Ember Giant',
        '1 Tidecaller Adept',
        '1 Fire // Ice',
        '1 Odd Shape // Other Shape',
        '1 Night // Day',
        '1 Quick Shock',
        '5 Mountain',
      ].join('\n');
      assert.equal(await page.locator('#arena-list').textContent(), want, 'the Arena list as drawn');
      const copy = page.locator('#import').getByRole('button', { name: /copy/i }).filter({ visible: true });
      assert.equal(await copiedBy(page, copy), want, 'the Arena list as copied');
    }));

  test('P7: The Arena import says, word for word, how to set the deck\'s format in Arena', async () => {
    const notes = {
      rich: 'In Arena, set the deck\'s format to Brawl. When you craft missing cards, Arena can show cards as not valid in Standard or Alchemy. That is normal for a Brawl deck, because Brawl allows older cards.',
      mono: 'In Arena, set the deck\'s format to Standard.',
    };
    for (const [name, note] of Object.entries(notes)) {
      await open(name, async ({ page }) => {
        const texts = await page.locator('#import').evaluate(s => [...s.querySelectorAll('*')].filter(e => e.checkVisibility()).map(e => e.innerText));
        assert.ok(texts.includes(note), `${name}: no element of the Arena import reads exactly ${JSON.stringify(note)}`);
        if (name === 'mono') assert.ok(!texts.some(t => t.includes('Brawl')), `${name}: the Arena import of a Standard deck mentions Brawl`);
      });
    }
  });
});

// ======================================================================
// Every path in a deck: each key of an object, and the first element of each list.
function* fieldPaths(value, at = []) {
  const children = Array.isArray(value) ? value.slice(0, 1).map((v, i) => [i, v]) : value && typeof value === 'object' ? Object.entries(value) : [];
  for (const [key, child] of children) {
    yield [...at, key];
    yield* fieldPaths(child, [...at, key]);
  }
}

const HOSTILE = '<img src=x onerror=window.__pwned=1>';
const wrongType = value => typeof value === 'string' ? 42 : 'wrong type';

// The text of deck.json with the field at a path changed; dropping the root leaves the file empty.
function mutated(deck, at, change) {
  if (!at.length) return change === 'dropped' ? '' : JSON.stringify(change === 'wrong type' ? 'wrong type' : change === 'null' ? null : HOSTILE);
  const copy = structuredClone(deck);
  const parent = at.slice(0, -1).reduce((v, k) => v[k], copy), key = at.at(-1);
  const old = parent[key];
  if (change === 'dropped') Array.isArray(parent) ? parent.splice(key, 1) : delete parent[key];
  else parent[key] = change === 'wrong type' ? wrongType(old) : change === 'null' ? null : HOSTILE;
  return JSON.stringify(copy, null, 2);
}

const pathName = at => at.length ? at.map(k => typeof k === 'number' ? `[${k}]` : `.${k}`).join('').slice(1) : 'the document root';

describe('Every field of the example', () => {
  test('P11: Each field of deck.example.json dropped, of the wrong type, null or a hostile string still leaves the Arena list drawn, no console error but a section left out, and no element from the string', async () => {
    const example = deckOf('example');
    const mutations = [[], ...fieldPaths(example)].flatMap(at => ['dropped', 'wrong type', 'null', 'hostile'].map(change => ({ at, change })));
    const context = await browser.newContext();
    const picture = await (await context.request.get(`${server.origin}/example/cards/${example.cards[0].scryfall_id}.jpg`)).body();
    await context.route('**/*', route => {
      const url = new URL(route.request().url());
      if (FONT_HOSTS.includes(url.hostname)) return route.fulfill({ status: 200, contentType: url.hostname === 'fonts.googleapis.com' ? 'text/css' : 'font/woff2', body: '' });
      // Every picture a changed deck names is served, so the console holds only what the page says.
      if (url.origin === server.origin && url.pathname.endsWith('.jpg')) return route.fulfill({ status: 200, contentType: 'image/jpeg', body: picture });
      return url.origin === server.origin ? route.continue() : route.abort();
    });
    const failures = [];
    const sweep = async queue => {
      const page = await context.newPage();
      let errors = [], text;
      page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
      page.on('pageerror', e => errors.push(String(e)));
      await page.route('**/example/deck.json', route => route.fulfill({ status: 200, contentType: 'application/json', body: text }));
      for (let m; (m = queue.shift());) {
        errors = [];
        text = mutated(example, m.at, m.change);
        const named = `${pathName(m.at)} ${m.change}`;
        await page.goto(`${server.origin}/example/`, { waitUntil: 'load' });
        const crashed = new Promise(settle => page.once('pageerror', settle));
        const finished = await Promise.race([untilDrawn(page, 2000).then(() => true, () => false), crashed.then(() => false)]);
        const seen = await page.evaluate(() => ({
          list: (l => l && l.checkVisibility() ? l.textContent : null)(document.getElementById('arena-list')),
          unread: /Could not read deck\.json/.test(document.getElementById('top')?.textContent || ''),
          pwned: window.__pwned !== undefined,
          injected: document.querySelectorAll('[onerror]').length,
        }));
        const problems = [];
        if (!finished) problems.push('the page did not finish drawing');
        if (m.at.length ? !seen.list : !seen.unread) problems.push(m.at.length ? 'no Arena list' : 'no "Could not read deck.json"');
        const stray = errors.filter(e => !/^The #[\w-]+ section could not be drawn/.test(e));
        if (stray.length) problems.push(`console: ${stray.join(' | ')}`);
        if (seen.pwned || seen.injected) problems.push('the hostile string ran or made an element');
        if (problems.length) failures.push(`${named}: ${problems.join('; ')}`);
      }
      await page.close();
    };
    try {
      const queue = [...mutations];
      await Promise.all(Array.from({ length: 4 }, () => sweep(queue)));
    } finally {
      await context.close();
    }
    assert.ok(mutations.length > 4 * 40, `only ${mutations.length} changes were made to the example, so the sweep proves little`);
    assert.ok(!failures.length, `${failures.length} of ${mutations.length} changes to deck.example.json break the page:\n${failures.join('\n')}`);
  });
});

// ======================================================================
describe('Edge cases', () => {
  test('The format is read whatever its case, and a format the page does not know is drawn as Standard', async () => {
    for (const [name, format, size, life] of [['drawn-capital-brawl', 'Brawl', 100, 25], ['drawn-no-format', 'Standard', 60, 20]]) {
      await open(name, { reducedMotion: 'reduce' }, async ({ page, deck }) => {
        assert.equal(await page.locator('#hero-line').textContent(), `${format} · 10 of ${size} cards · In progress`, `format "${deck.format}": the hero line`);
        const scene = page.locator('#main-scene');
        await settlePictures(scene);
        const step = deck.scenes[0].steps.at(-1), index = step.things.findIndex(t => t.damage !== undefined);
        const hit = await readThing(scene, step.caption, index, 'now');
        assert.deepEqual(numbersIn(hit), [life - step.things[index].damage], `format "${deck.format}": ${step.things[index].damage} damage shows ${JSON.stringify(hit.texts)}, not from a starting life of ${life}`);
        const commanderFirst = (await sectionText(page, 'import')).includes('The Commander section comes first');
        assert.equal(commanderFirst, format === 'Brawl', `format "${deck.format}": the Arena import ${commanderFirst ? 'says' : 'does not say'} the Commander section comes first`);
      });
    }
  });

  test('P13: The hero line shows the format, the card count against the format\'s size, and Approved or In progress, exactly as drawn', async () => {
    for (const [name, line] of [['rich', 'Brawl · 29 of 100 cards · In progress'], ['mono', 'Standard · 36 of 60 cards · Approved']]) {
      await open(name, async ({ page }) => {
        assert.equal(await page.locator('#hero-line').textContent(), line, `${name}: the hero line`);
      });
    }
  });

  test('deck.json cannot be read: the hero says so and nothing else is drawn', () =>
    open('unreadable', async ({ page }) => {
      assert.match(await sectionText(page, 'top'), /deck\.json/, 'the hero does not say deck.json could not be read');
      const rest = await page.evaluate(() => {
        const hero = document.getElementById('top');
        return [...document.body.children].filter(e => e !== hero && !e.contains(hero) && e.checkVisibility()).map(e => e.innerText.trim()).join('');
      });
      assert.equal(rest, '', 'something besides the hero is drawn');
    }));

  test('A card picture is missing: the card\'s name on a blank card, in the grid and the dialog', () =>
    open('stray', async ({ page }) => {
      const cards = page.locator('#cards');
      await settlePictures(cards);
      assert.deepEqual((await pictures(cards)).filter(p => p.broken).map(p => p.src), [], 'the grid shows a broken image');
      assert.ok((await (await tile(page, 'stray', 'Lost Picture Rat')).innerText()).includes('Lost Picture Rat'));
      const d = await openCard(page, 'stray', 'Lost Picture Rat');
      await settlePictures(d);
      assert.deepEqual((await pictures(d)).filter(p => p.broken).map(p => p.src), [], 'the dialog shows a broken image');
      assert.ok((await d.innerText()).includes('Lost Picture Rat'));
    }));

  test('An empty category says "Nothing picked yet." under its heading', () =>
    open('rich', async ({ page }) => {
      const text = await sectionText(page, 'cards');
      const body = text.slice(text.indexOf('Protection'), text.indexOf('Lands', text.indexOf('Protection')));
      assert.match(body, /Nothing picked yet\./);
    }));

  test('No ledger file: the ledger says "Nothing logged yet."', () =>
    open('mono', async ({ page }) => assert.match(await sectionText(page, 'ledger'), /Nothing logged yet\./)));

  test('deck.json holds no deck (null, a number, a list): the hero says it could not be read and nothing else is drawn', async () => {
    for (const name of ['deck-null', 'deck-number', 'deck-array']) {
      await open(name, async ({ page }) => {
        assert.match(await sectionText(page, 'top'), /Could not read deck\.json/, `${name}: the hero does not say deck.json could not be read`);
        const rest = await page.evaluate(() => {
          const hero = document.getElementById('top');
          return [...document.body.children].filter(e => e !== hero && !e.contains(hero) && e.checkVisibility()).map(e => e.innerText.trim()).join('');
        });
        assert.equal(rest, '', `${name}: something besides the hero is drawn`);
      });
    }
  });

  test('The clipboard is refused: the page says to copy the list by hand and brings the Arena list into view', () =>
    open('rich', { clipboard: false }, async ({ page, deck }) => {
      await page.locator('#top').getByRole('button', { name: /copy/i }).first().click();
      const said = await until(async () => (await page.getByRole('status').innerText()).trim() || null);
      assert.match(said || '', /select the list/i, `the page says "${said}"`);
      const pre = page.locator('pre').filter({ visible: true });
      const inView = await until(() => pre.evaluate(e => { const r = e.getBoundingClientRect(); return r.top < innerHeight && r.bottom > 0; }));
      assert.ok(inView, 'the Arena list is not brought into view');
      assert.equal(await page.locator('#arena-list').textContent(), arenaList(deck));
    }));

  test('The clipboard refused a second time still brings the Arena list into view', () =>
    open('rich', { clipboard: false }, async ({ page }) => {
      const copy = page.locator('#top').getByRole('button', { name: /copy/i }).first();
      const pre = page.locator('pre').filter({ visible: true });
      const inView = () => until(() => pre.evaluate(e => { const r = e.getBoundingClientRect(); return r.top < innerHeight && r.bottom > 0; }));
      await copy.click();
      assert.ok(await inView(), 'the first refusal does not bring the Arena list into view');
      await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }));
      assert.ok(!(await pre.evaluate(e => e.getBoundingClientRect().top < innerHeight)), 'the Arena list is still in view at the top of the page, so this test proves nothing');
      await copy.click();
      assert.ok(await inView(), 'the second refusal does not bring the Arena list into view');
    }));

  test('A scene step whose things are not a list leaves the scenes out, and the rest of the page is drawn', () =>
    open('misdrawn-scene', ({ page, errors }) => drawnWithout(page, errors, 'misdrawn-scene', 'engine')));

  test('A handbook block whose list is not a list leaves the handbook out, with no link to it, and the rest of the page is drawn', () =>
    open('misdrawn-block', async ({ page, errors }) => {
      await drawnWithout(page, errors, 'misdrawn-block', 'handbook');
      const toHandbook = page.locator('#top').getByRole('link', { name: /handbook/i });
      assert.equal(await toHandbook.filter({ visible: true }).count(), 0, 'the hero links to a handbook that is left out');
    }));

  test('A mana value with a fraction is drawn in the curve column of its whole number, and the rest of the page is drawn', () =>
    open('half-mana-value', { reducedMotion: 'reduce' }, async ({ page, errors }) => {
      const pre = page.locator('pre').filter({ visible: true });
      assert.equal(await pre.count(), 1, `the Arena list is not drawn; errors: ${errors.join(' | ')}`);
      assert.equal(await page.locator('#arena-list').textContent(), arenaList(deckOf('half-mana-value')));
      const curve = await finishedCurve(page);
      assert.ok(curve?.legend, 'the curve is not drawn');
      const parts = curve.columns.map(c => c.other > 0 ? 'other' : c.creature > 0 ? 'creature' : '');
      assert.deepEqual(parts.slice(0, 3), ['other', 'other', 'creature'], 'Half Spark (0.5) is not in column 0 beside the two one-mana spells in column 1 and the commander in column 2');
      assert.deepEqual(errors, []);
    }));

  test('No pitch, curve note, why or rarity: that line or mark is absent', () =>
    open('several', async ({ page }) => {
      const body = await page.locator('body').innerText();
      assert.doesNotMatch(body, /\b(undefined|null|NaN)\b/, 'a missing field shows a placeholder');
      assert.ok(await visible(page.locator('#cards')), 'the cards section is not on the page');
      const d = await openCard(page, 'several', 'Quick Shock');
      assert.doesNotMatch(await d.innerText(), /\b(undefined|null|NaN|common|rare|mythic)\b/i, 'the dialog shows a missing field');
    }));
});
