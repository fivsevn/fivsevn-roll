/* Exercise the shipped script with history, bfcache, and changing frame geometry. */
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';

const source = await readFile(new URL('../site-assets/motion-navigation.js', import.meta.url), 'utf8');
const pendingKey = 'roll-motion-pending-return';
const sourceKey = path => 'roll-motion-return:' + path;
const origin = 'https://roll.test';
const eventBus = () => {
  const handlers = new Map();
  return {
    add(name, callback) { if (!handlers.has(name)) handlers.set(name, new Set()); handlers.get(name).add(callback); },
    remove(name, callback) { handlers.get(name)?.delete(callback); },
    emit(name, event = {}) { [...(handlers.get(name) || [])].forEach(callback => callback(event)); }
  };
};
const click = (extra = {}) => ({ button: 0, defaultPrevented: false, preventDefault() { this.defaultPrevented = true; }, ...extra });
const record = (url, top = 205, extra = {}) => JSON.stringify({ id: 'sample', url, top, at: Date.now(), ...extra });
const stored = (storage, key) => JSON.parse(storage.get(key));

async function page({ detail = false, storage = new Map(), base = '', path, fallback, referrer = '',
  historyLength = 1, height = 3000, ready = true, roomPresent = true, pages, blocked = false } = {}) {
  const windowEvents = eventBus(), documentEvents = eventBus(), returnEvents = eventBus(), openEvents = eventBus();
  const state = { docY: 1216, fixedTop: 205, scrolls: [], nodes: new Map(), raf: [], timers: new Map(), observers: [],
    height, redirects: [], backCalls: 0, historyURLs: [], nextTimer: 0 };
  let fontReady;
  const fontPromise = new Promise(resolve => { fontReady = resolve; });
  if (ready) fontReady();
  const context = { URL, Date, Promise, Number, JSON, Object, Math, parseFloat };
  const room = { id: 'sample', isConnected: true, matches: selector => selector === '[data-motion-room]',
    getBoundingClientRect: () => ({ top: detail ? state.fixedTop : state.docY - context.scrollY }) };
  const back = { href: fallback || base + '/motion/page/2/#sample', addEventListener: returnEvents.add };
  const open = { href: origin + base + '/motion/sample/', closest: () => room, addEventListener: openEvents.add };
  const root = {};
  Object.defineProperty(root, 'scrollHeight', { get: () => state.height + [...state.nodes.values()]
    .reduce((sum, node) => sum + (parseFloat(node.style.height) || 0), 0) });
  const location = new URL(origin + (path || (detail ? base + '/motion/sample/' : base + '/motion/page/2/')));
  location.replace = url => state.redirects.push(url);
  context.location = location;
  context.sessionStorage = {
    getItem(key) { if (blocked) throw new Error('Storage blocked'); return storage.get(key) ?? null; },
    setItem(key, value) { if (blocked) throw new Error('Storage blocked'); storage.set(key, value); },
    removeItem(key) { if (blocked) throw new Error('Storage blocked'); storage.delete(key); }
  };
  context.history = { length: historyLength, state: { existing: true }, scrollRestoration: 'auto',
    back() { state.backCalls++; },
    replaceState(value, unused, url) { state.historyURLs.push(url); this.state = value; location.href = new URL(url, location).href; }
  };
  context.document = {
    referrer, documentElement: root, scrollingElement: root, body: { append: node => state.nodes.set(node.id, node) },
    fonts: { ready: fontPromise },
    querySelector: selector => selector === '.roll-motion-detail [data-motion-room]' ? (detail ? room : null)
      : selector === '[data-motion-return]' && detail ? back : null,
    querySelectorAll: selector => selector === '[data-motion-open]' && !detail ? [open] : [],
    getElementById: id => id === 'motion-navigation-config' ? { textContent: JSON.stringify({ base_path: base,
      post_pages: pages || { sample: base + '/motion/page/2/' } }) } : id === 'sample' && roomPresent ? room : state.nodes.get(id),
    createElement: () => ({ style: {}, setAttribute() {} }),
    addEventListener: documentEvents.add, removeEventListener: documentEvents.remove
  };
  context.addEventListener = windowEvents.add;
  context.removeEventListener = windowEvents.remove;
  context.requestAnimationFrame = callback => state.raf.push(callback);
  context.setTimeout = (callback, delay) => { const id = ++state.nextTimer; state.timers.set(id, { callback, delay }); return id; };
  context.clearTimeout = id => state.timers.delete(id);
  context.ResizeObserver = class {
    constructor(callback) { this.callback = callback; this.active = true; state.observers.push(this); }
    observe() {}
    disconnect() { this.active = false; }
  };
  context.scrollY = 1000; context.innerHeight = 900;
  context.scrollTo = options => { state.scrolls.push(options); context.scrollY = Math.min(options.top, Math.max(0, root.scrollHeight - context.innerHeight)); };
  vm.runInNewContext(source, context);
  const flush = async () => { await Promise.resolve(); while (state.raf.length) state.raf.splice(0).forEach(callback => callback()); };
  await flush();
  return { state, context, storage, room, back, open, windowEvents, documentEvents, returnEvents, openEvents, fontReady, flush,
    stop: () => windowEvents.emit('wheel'),
    resize: async () => { state.observers.filter(observer => observer.active).forEach(observer => observer.callback()); await flush(); },
    expire: async delay => { [...state.timers.values()].filter(timer => timer.delay === delay).forEach(timer => timer.callback()); await flush(); }
  };
}

const results = [];
async function scenario(name, test) { await test(); results.push(name); }

await scenario('direct details use their generated page and current detail-frame height', async () => {
  const storage = new Map([['roll-motion-return', JSON.stringify({ id: 'other', url: '/motion/page/9/#other' })]]);
  const detail = await page({ detail: true, storage });
  detail.state.fixedTop = 67;
  detail.returnEvents.emit('click', click());
  assert.equal(detail.back.href, '/motion/page/2/#sample');
  assert.equal(stored(storage, pendingKey).top, 67);
  assert.equal(detail.state.backCalls, 0);
});
await scenario('a page-2 open returns with native history and consumes only its own source', async () => {
  const storage = new Map();
  const list = await page({ storage, path: '/motion/page/2/?view=all' });
  list.openEvents.emit('click', click());
  assert.deepEqual(stored(storage, sourceKey('/motion/sample/')), { id: 'sample', url: '/motion/page/2/?view=all#sample' });
  const detail = await page({ detail: true, storage, referrer: origin + '/motion/page/2/?view=all', historyLength: 2,
    fallback: '/motion/#sample' });
  detail.state.fixedTop = -14;
  const event = click(); detail.returnEvents.emit('click', event);
  assert.equal(event.defaultPrevented, true);
  assert.equal(detail.state.backCalls, 1);
  assert.equal(stored(storage, pendingKey).top, -14);
  assert.equal(detail.back.href, '/motion/page/2/?view=all#sample');
  assert.equal(storage.has(sourceKey('/motion/sample/')), false);
  const fresh = await page({ detail: true, storage, fallback: '/motion/#sample' });
  assert.equal(fresh.back.href, '/motion/#sample');
});
await scenario('alignment preserves frame Y across lazy players, fonts, and resizing, then yields to the user', async () => {
  const storage = new Map([[pendingKey, record('/motion/page/2/#sample')]]);
  const list = await page({ storage, ready: false });
  assert.equal(list.room.getBoundingClientRect().top, 205);
  assert.equal(list.state.scrolls[0].top, 1011);
  assert.equal(list.state.scrolls[0].behavior, 'instant');
  assert.equal(list.context.history.scrollRestoration, 'manual');
  assert.equal(list.context.location.hash, '#sample');
  assert.equal(storage.has(pendingKey), false);
  list.state.docY += 120; list.documentEvents.emit('load', { target: { tagName: 'IFRAME' } }); await list.flush();
  assert.equal(list.room.getBoundingClientRect().top, 205);
  list.state.docY += 30; list.fontReady(); await list.flush();
  assert.equal(list.room.getBoundingClientRect().top, 205);
  list.state.docY += 25; await list.resize();
  assert.equal(list.room.getBoundingClientRect().top, 205);
  list.stop(); list.state.docY += 80; list.documentEvents.emit('load'); await list.flush();
  assert.equal(list.room.getBoundingClientRect().top, 285);
  assert.equal(list.context.history.scrollRestoration, 'auto');
});
await scenario('native Back and bfcache pageshow capture the latest detail frame, including project paths', async () => {
  const storage = new Map();
  const list = await page({ storage, base: '/project' });
  const detail = await page({ detail: true, storage, base: '/project' });
  detail.state.fixedTop = 31; detail.windowEvents.emit('pagehide');
  list.windowEvents.emit('pageshow', { persisted: true }); await list.flush();
  assert.equal(list.room.getBoundingClientRect().top, 31);
  list.windowEvents.emit('pagehide');
  detail.state.fixedTop = 44; detail.windowEvents.emit('pagehide');
  list.windowEvents.emit('pageshow', { persisted: true }); await list.flush();
  assert.equal(list.room.getBoundingClientRect().top, 44); list.stop();
});
await scenario('short final pages gain only the tail space needed and shrink it after layout grows', async () => {
  const list = await page({ height: 1100, storage: new Map([[pendingKey, record('/motion/page/2/#sample')]]) });
  assert.equal(list.room.getBoundingClientRect().top, 205);
  const space = list.state.nodes.get('roll-motion-return-space');
  assert.equal(space.style.height, '811px');
  list.state.height += 100; await list.resize();
  assert.equal(space.style.height, '711px');
  assert.equal(list.room.getBoundingClientRect().top, 205);
  list.stop(); assert.equal(space.style.height, '711px');
});
await scenario('a moved post carries its pending frame height to its new pagination page', async () => {
  const storage = new Map([[pendingKey, record('/motion/page/2/?view=all#sample', 72)]]);
  const old = await page({ storage, path: '/motion/page/2/?view=all', roomPresent: false, pages: { sample: '/motion/page/3/' } });
  assert.deepEqual(old.state.redirects, ['/motion/page/3/?view=all#sample']);
  assert.equal(stored(storage, pendingKey).top, 72);
  assert.equal(stored(storage, pendingKey).url, '/motion/page/3/?view=all#sample');
  const current = await page({ storage, path: old.state.redirects[0], pages: { sample: '/motion/page/3/' } });
  assert.equal(current.room.getBoundingClientRect().top, 72);
  assert.deepEqual(current.state.redirects, []); current.stop();
});
await scenario('old bookmarks and hash changes relocate to the current page without inventing a post', async () => {
  const list = await page({ path: '/motion/page/2/?view=all#sample', pages: { sample: '/motion/page/3/' } });
  assert.deepEqual(list.state.redirects, ['/motion/page/3/?view=all#sample']);
  const unknown = await page({ path: '/motion/#unknown', pages: { sample: '/motion/page/3/' } });
  assert.deepEqual(unknown.state.redirects, []);
  unknown.context.location.hash = '#sample'; unknown.windowEvents.emit('hashchange');
  assert.deepEqual(unknown.state.redirects, ['/motion/page/3/#sample']);
});
await scenario('modified and already-handled clicks keep ordinary browser behavior', async () => {
  const list = await page();
  const detail = await page({ detail: true, referrer: origin + '/motion/page/2/', historyLength: 2 });
  for (const extra of [{ metaKey: true }, { ctrlKey: true }, { shiftKey: true }, { altKey: true }, { button: 1 }, { defaultPrevented: true }]) {
    list.openEvents.emit('click', click(extra)); detail.returnEvents.emit('click', click(extra));
  }
  assert.equal(list.storage.size, 0); assert.equal(detail.storage.size, 0);
  assert.equal(detail.state.backCalls, 0);
});
await scenario('foreign, mismatched, and short histories never invoke native Back', async () => {
  for (const options of [{ referrer: 'https://other.test/motion/page/2/', historyLength: 2 },
    { referrer: origin + '/motion/page/3/', historyLength: 2 },
    { referrer: origin + '/motion/page/2/', historyLength: 1 }]) {
    const detail = await page({ detail: true, ...options }); const event = click();
    detail.returnEvents.emit('click', event);
    assert.equal(event.defaultPrevented, false); assert.equal(detail.state.backCalls, 0);
  }
});
await scenario('blocked storage preserves generated anchors and allows clicks', async () => {
  const list = await page({ blocked: true }); list.openEvents.emit('click', click());
  const detail = await page({ detail: true, blocked: true }); const event = click(); detail.returnEvents.emit('click', event);
  assert.equal(detail.back.href, '/motion/page/2/#sample'); assert.equal(event.defaultPrevented, false);
  assert.equal(detail.storage.size, 0);
});
await scenario('invalid, expired, foreign, and unrelated saved returns do not scroll or redirect', async () => {
  for (const value of ['{', record('https://other.test/motion/page/2/#sample'), record('/motion/page/3/#sample'),
    record('/motion/page/2/#other'), record('/motion/page/2/#sample', 205, { at: Date.now() - 180000 }),
    record('/motion/page/2/#sample', null), record('/motion/page/2/#sample', 2000000)]) {
    const list = await page({ storage: new Map([[pendingKey, value]]) });
    assert.equal(list.state.scrolls.length, 0); assert.equal(list.state.redirects.length, 0);
  }
  const unsafe = await page({ path: '/motion/#sample', pages: { sample: 'https://other.test/motion/' } });
  assert.equal(unsafe.state.redirects.length, 0);
});
await scenario('correction stops after settling and remains bounded when fonts never finish', async () => {
  for (const ready of [true, false]) {
    const list = await page({ ready, storage: new Map([[pendingKey, record('/motion/page/2/#sample')]]) });
    await list.expire(ready ? 2000 : 10000);
    list.state.docY += 100; list.documentEvents.emit('load'); await list.resize();
    assert.equal(list.room.getBoundingClientRect().top, 305);
    assert.equal(list.context.history.scrollRestoration, 'auto');
  }
});
console.log(`Passed ${results.length} Motion navigation scenarios.`);
results.forEach(result => console.log(`  ✓ ${result}`));
