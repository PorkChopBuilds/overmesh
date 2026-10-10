// EST-83 Q4: exercise the REAL openWaypointModal() template with stubs and check
// the network-aware tab + the "Also add to Log" checkbox, instead of only
// grepping app.js for strings.
const fs = require('fs');
const path = require('path');
const REPO = path.join(__dirname, '..');
const src = fs.readFileSync(path.join(REPO, 'static/js/app.js'), 'utf8');

function assert(cond, msg) {
  if (!cond) { console.error('FAIL: ' + msg); process.exit(1); }
}

const m = src.match(/async function openWaypointModal\(lat, lon\) \{[\s\S]*?\n  \}/);
assert(m, 'openWaypointModal() must be found');

const escHtml = s => String(s == null ? '' : s);
const jsSafe = s => String(s == null ? '' : s);

function render(mapShowMt, mapShowMc, mcLastStatus, mcHide) {
  let modalHtml = '';
  const openModal = (title, html) => { modalHtml = html; };
  const localStorage = {
    _v: { mcHide: mcHide },
    getItem(k) { return this._v[k] === undefined ? null : this._v[k]; },
    setItem(k, v) { this._v[k] = String(v); },
  };
  const document = { getElementById: () => ({ focus() {} }) };
  const setTimeout = fn => { try { fn(); } catch (_) {} return 0; };
  const clearTimeout = () => {};
  const AbortController = class { constructor() { this.signal = {}; } abort() {} };
  const fetch = () => Promise.reject(new Error('no radio in test'));
  const fn = new Function(
    'escHtml', 'jsSafe', 'WP_EMOJIS', 'openModal', 'BASE_PATH', 'activeRadioId',
    'fetch', 'AbortController', 'clearTimeout', 'setTimeout', 'document',
    'mapShowMt', 'mapShowMc', 'mcLastStatus', 'localStorage',
    'return ' + m[0],
  );
  // `_wpLat`, `_wpLon`, `_editWpId`, `_wpDestNode`, `_wpMarkerEmoji` are assigned
  // (sloppy-mode globals) by the function; WP_EMOJIS/openModal etc. are injected.
  const openWaypointModal = fn(
    escHtml, jsSafe, [['📍', '📝']], openModal, '', null,
    fetch, AbortController, clearTimeout, setTimeout, document,
    mapShowMt, mapShowMc, mcLastStatus, localStorage,
  );
  return openWaypointModal(46.04321, 14.51234).then(() => modalHtml);
}

(async () => {
  // MT visible (both networks) -> both tabs, Mark labelled as the MT waypoint tab.
  let html = await render(true, true, { r1: { status: 'connected' } }, null);
  assert(html.includes('📡 Mark (MT waypoint)'),
         'MT map must show the "📡 Mark (MT waypoint)" tab');
  assert(html.includes('Sent as a Meshtastic waypoint. MeshCore has no waypoint message.'),
         'the Mark tab must explain it is MT-only');
  assert(html.includes('Also add to Log'), 'the Self Note tab must offer "Also add to Log"');
  assert(html.includes('id="note-also-log"'), 'the checkbox must have id note-also-log');

  // MC-only -> no Mark tab; Self Note is the one that is visible.
  html = await render(false, true, { r1: { status: 'connected' } }, null);
  assert(!html.includes('📡 Mark (MT waypoint)'),
         'an MC-only map must NOT offer the MT waypoint tab');
  assert(html.includes('Also add to Log'), 'MC-only still saves a Self Note (with the Log checkbox)');
  assert(/id="wptab-note-content"(?! style="display:none")/.test(html),
         'on an MC-only map the Self Note tab must be the visible one');

  // MC hidden -> treated as MT-visible (both tabs).
  html = await render(false, true, { r1: { status: 'connected' } }, '1');
  assert(html.includes('📡 Mark (MT waypoint)'),
         'a force-hidden MC map must fall back to the MT waypoint tab');

  console.log('ok: waypoint dialog is network-aware and carries the Log checkbox');
})().catch(e => { console.error('FAIL: ' + (e && e.message || e)); process.exit(1); });

// ── EST-85 sweep: drive the REAL saveMapNote() so "checkbox off = no Log call"
// is exercised, not just grepped. It needs a DOM + fetch stub, like the modal
// template test above.
const saveSrc = src.match(/async function saveMapNote\(\) \{[\s\S]*?\n  \}/);
assert(saveSrc, 'saveMapNote() must be found');

function runSaveNote(alsoLog) {
  const els = {
    'note-name-input': { value: 'Parking spot' },
    'note-desc-input': { value: 'by the trailhead' },
    'note-save-status': { style: {}, textContent: '' },
    'note-also-log': { checked: alsoLog },
  };
  const document = { getElementById: id => (id in els ? els[id] : null) };
  const calls = [];
  const fetch = async (url, opts) => {
    calls.push({ url, body: opts && opts.body });
    if (url.indexOf('/api/notes') !== -1) return { ok: true, json: async () => ({ ok: true }) };
    if (url.indexOf('/api/toc') !== -1) return { ok: true, json: async () => ({ ok: true, id: 1 }) };
    return { ok: false, json: async () => ({}) };
  };
  const _tocStructuredMarkdown = obj => Object.entries(obj).map(([k, v]) => `**${k}:** ${v}`).join('\n');
  const closeModal = () => {};
  const setTimeout = () => 0;
  const fn = new Function(
    'document', 'fetch', 'BASE_PATH', '_wpLat', '_wpLon', '_wpMarkerEmoji',
    '_tocStructuredMarkdown', 'closeModal', 'setTimeout',
    'return ' + saveSrc[0],
  );
  return fn(document, fetch, '', 46.04321, 14.51234, '📍', _tocStructuredMarkdown, closeModal, setTimeout)()
    .then(() => calls);
}

(async () => {
  const off = await runSaveNote(false);
  assert(off.length === 1 && off[0].url.indexOf('/api/notes') !== -1,
         'checkbox off must save the note and make no Log call (got ' + off.map(c => c.url).join(', ') + ')');

  const on = await runSaveNote(true);
  assert(on.length === 2, 'checkbox on must save the note and POST the Log entry');
  const toc = on.find(c => c.url.indexOf('/api/toc') !== -1);
  assert(toc, 'checkbox on must POST to /api/toc');
  const payload = JSON.parse(toc.body);
  assert(payload.category === 'NOTE', 'the Log entry must use category NOTE like tocSubmit');
  assert(payload.body.indexOf('**Name:** Parking spot') !== -1, 'the Log entry must carry the note name');
  assert(payload.body.indexOf('**Coordinates:** 46.04321, 14.51234') !== -1,
         'the Log entry must carry the coordinates');
  console.log('ok: marker dialog Log checkbox gates the /api/toc call');
})().catch(e => { console.error('FAIL: ' + (e && e.message || e)); process.exit(1); });
