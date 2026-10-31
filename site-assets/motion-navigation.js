/* Return a room to the viewport height of the detail frame being closed. */
(() => {
  let config = {};
  try { config = JSON.parse(document.getElementById('motion-navigation-config')?.textContent || '{}'); } catch (_) {}
  const prefix = config.base_path || '';
  const pages = config.post_pages || {};
  const pendingKey = 'roll-motion-pending-return';
  const sourceKey = path => 'roll-motion-return:' + path;
  const plainClick = event => !event.defaultPrevented && event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey;
  const relative = url => url.pathname + url.search + url.hash;
  const read = key => { try { return JSON.parse(sessionStorage.getItem(key)); } catch (_) { return null; } };
  const save = (key, value) => { try { sessionStorage.setItem(key, JSON.stringify(value)); } catch (_) {} };
  const remove = key => { try { sessionStorage.removeItem(key); } catch (_) {} };
  const hashId = hash => { try { return decodeURIComponent(hash.slice(1)); } catch (_) { return ''; } };
  function listURL(value, id) {
    if (typeof value !== 'string' || !value) return null;
    try {
      const url = new URL(value, location.origin);
      url.pathname = url.pathname.replace(/index\.html$/, '');
      const path = url.pathname.slice(prefix.length);
      if (url.origin !== location.origin || !url.pathname.startsWith(prefix + '/') ||
          !(path === '/motion/' || /^\/motion\/page\/[1-9]\d*\/$/.test(path)) ||
          (url.hash && hashId(url.hash) !== id)) return null;
      url.hash = encodeURIComponent(id);
      return url;
    } catch (_) { return null; }
  }
  function pendingReturn() {
    const record = read(pendingKey);
    return record && typeof record.id === 'string' && Number.isFinite(record.top) &&
      Math.abs(record.top) < 1000000 && Number.isFinite(record.at) &&
      Math.abs(Date.now() - record.at) < 120000 && listURL(record.url, record.id) ? record : null;
  }

  const detail = document.querySelector('.roll-motion-detail [data-motion-room]');
  if (detail) {
    const link = document.querySelector('[data-motion-return]');
    if (!link) return;
    const saved = read(sourceKey(location.pathname));
    remove(sourceKey(location.pathname));
    const target = (saved && saved.id === detail.id && listURL(saved.url, detail.id)) || listURL(link.href, detail.id);
    if (!target) return;
    link.href = relative(target);
    const remember = () => save(pendingKey, {
      url: relative(target), id: detail.id, top: detail.getBoundingClientRect().top, at: Date.now()
    });
    link.addEventListener('click', event => {
      if (!plainClick(event)) return;
      remember();
      const previous = listURL(document.referrer, detail.id);
      if (previous && previous.pathname === target.pathname && previous.search === target.search && history.length > 1) {
        event.preventDefault();
        history.back();
      }
    });
    // Native Back also leaves through pagehide, including a bfcache return.
    addEventListener('pagehide', remember);
    return;
  }
  const current = listURL(location.href, hashId(location.hash));
  if (!current) return;
  document.querySelectorAll('[data-motion-open]').forEach(link => link.addEventListener('click', event => {
    if (!plainClick(event)) return;
    const room = link.closest('[data-motion-room]');
    if (!room) return;
    try {
      const destination = new URL(link.href, location.origin);
      if (destination.origin !== location.origin || !destination.pathname.startsWith(prefix + '/motion/')) return;
      save(sourceKey(destination.pathname), { id: room.id, url: location.pathname + location.search + '#' + encodeURIComponent(room.id) });
    } catch (_) {}
  }));
  function moveToPage(id, record) {
    if (!Object.prototype.hasOwnProperty.call(pages, id)) return false;
    const destination = listURL(pages[id], id);
    if (!destination || destination.pathname === current.pathname) return false;
    destination.search = location.search;
    if (record?.id === id) save(pendingKey, { ...record, url: relative(destination) });
    location.replace(relative(destination));
    return true;
  }
  let stopAlignment = () => {};
  function alignRoom(room, saved) {
    stopAlignment();
    let active = true, queued = false, quiet, limit, fontsReady = false;
    const previousRestoration = history.scrollRestoration;
    try { history.scrollRestoration = 'manual'; } catch (_) {}
    const align = () => {
      if (!active || !room.isConnected) return;
      const top = Math.max(0, scrollY + room.getBoundingClientRect().top - saved.top);
      const scroller = document.scrollingElement || document.documentElement;
      let space = document.getElementById('roll-motion-return-space');
      const previousHeight = space ? parseFloat(space.style.height) || 0 : 0;
      const needed = Math.max(0, Math.ceil(top + innerHeight - scroller.scrollHeight + previousHeight));
      if (needed || space) {
        if (!space) {
          space = document.createElement('div');
          space.id = 'roll-motion-return-space';
          space.setAttribute('aria-hidden', 'true');
          space.style.cssText = 'height:0;pointer-events:none;overflow-anchor:none';
          document.body.append(space);
        }
        space.style.height = needed + 'px';
        const remaining = Math.ceil(top + innerHeight - scroller.scrollHeight);
        if (remaining > 0) space.style.height = needed + remaining + 'px';
      }
      if (Math.abs(scrollY - top) > .5) scrollTo({ top, behavior: 'instant' });
    };
    const schedule = () => {
      if (!active || queued) return;
      queued = true;
      clearTimeout(quiet);
      requestAnimationFrame(() => requestAnimationFrame(() => {
        queued = false;
        align();
        if (active && fontsReady) quiet = setTimeout(stop, 2000);
      }));
    };
    const observer = typeof ResizeObserver === 'function' ? new ResizeObserver(schedule) : null;
    const cancelEvents = ['wheel', 'touchstart', 'pointerdown', 'keydown'];
    const stop = () => {
      active = false;
      clearTimeout(quiet); clearTimeout(limit);
      observer?.disconnect();
      document.removeEventListener('load', schedule, true);
      removeEventListener('resize', schedule);
      cancelEvents.forEach(name => removeEventListener(name, stop, true));
      try { history.scrollRestoration = previousRestoration; } catch (_) {}
      // Keep needed tail space: removing it could clamp the user's scroll.
    };
    stopAlignment = stop;
    cancelEvents.forEach(name => addEventListener(name, stop, { capture: true, passive: true }));
    document.addEventListener('load', schedule, true);
    addEventListener('resize', schedule);
    observer?.observe(document.body); observer?.observe(room);
    schedule();
    Promise.resolve(document.fonts?.ready).then(() => { fontsReady = true; schedule(); });
    limit = setTimeout(stop, 10000);
  }
  const restoreRoom = () => {
    const saved = pendingReturn();
    const target = saved && listURL(saved.url, saved.id);
    const returningHere = target && target.pathname === current.pathname && target.search === location.search;
    const bookmark = hashId(location.hash);
    if (!returningHere && bookmark && moveToPage(bookmark, saved)) return;
    if (!returningHere) return;
    const room = document.getElementById(saved.id);
    if (!room?.matches('[data-motion-room]')) {
      if (!moveToPage(saved.id, saved)) remove(pendingKey);
      return;
    }
    remove(pendingKey);
    try { history.replaceState(history.state, '', relative(target)); } catch (_) {}
    alignRoom(room, saved);
  };
  restoreRoom();
  addEventListener('pageshow', restoreRoom);
  addEventListener('hashchange', restoreRoom);
  addEventListener('pagehide', () => stopAlignment());
})();
