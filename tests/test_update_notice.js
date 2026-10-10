const fs = require('fs');
const path = require('path');
const REPO = path.join(__dirname, '..');

const src = fs.readFileSync(path.join(REPO, 'static/js/app.js'), 'utf8');
const appPy = fs.readFileSync(path.join(REPO, 'app.py'), 'utf8');
const indexHtml = fs.readFileSync(path.join(REPO, 'templates/index.html'), 'utf8');
const liteHtml = fs.readFileSync(path.join(REPO, 'templates/lite.html'), 'utf8');
const liteJs = fs.readFileSync(path.join(REPO, 'static/js/lite.js'), 'utf8');
const css = fs.readFileSync(path.join(REPO, 'static/css/app.css'), 'utf8');

function assert(cond, msg) {
  if (!cond) { console.error('FAIL: ' + msg); process.exit(1); }
}

// ── Server: boot + 6h check + cached endpoint, now with the version fields ─────
assert(/from routes.settings import update_check_loop/.test(appPy),
       'app.py must start the update check loop');
assert(/threading\.Thread\(target=update_check_loop, daemon=True\)\.start\(\)/.test(appPy),
       'the update check loop must run in a daemon thread');
const settingsPy = fs.readFileSync(path.join(REPO, 'routes/settings.py'), 'utf8');
assert(/def _version_at\(ref\)/.test(settingsPy), 'settings.py must read VERSION off a git ref');
assert(/info\["remote_version"\] = _version_at\(upstream\)/.test(settingsPy),
       'the check must fill remote_version from origin/main');
assert(/"remote_version": info\.get\("remote_version"\)/.test(settingsPy),
       'the SSE/state must carry remote_version');
assert(/"local_version": info\.get\("local_version"\)/.test(settingsPy),
       'the SSE/state must carry local_version');
assert(/def update_check_loop\(\)/.test(settingsPy), 'the 6h loop must still exist');

// ── Client: boot fetch + SSE flip, both pass the versions ─────────────────────
assert(/checkUpdateNotice\(\);/.test(src), 'the notice must be checked at boot');
assert(/function checkUpdateNotice\(\)/.test(src), 'checkUpdateNotice() must exist');
assert(/\/api\/settings\/update\/available/.test(src), 'the client must read the cached endpoint');
assert(/if \(data\.type === 'update_available'\)/.test(src),
       'the SSE update_available event must be handled');
assert(/showUpdateNotice\(data\.remote_commit, data\.behind, data\.remote_version, data\.local_version\)/.test(src),
       'the SSE flip must pass the versions into the banner');
assert(/showUpdateNotice\(d\.remote_commit, d\.behind, d\.remote_version, d\.local_version\)/.test(src),
       'the boot check must pass the versions into the banner');

// ── The yellow top banner (replaces the corner toast) ─────────────────────────
assert(/function showUpdateNotice\(remoteCommit, behind, remoteVersion, localVersion\)/.test(src),
       'showUpdateNotice() must take the versions');
assert(/function _updateBannerText\(/.test(src), 'the banner text must be built by _updateBannerText()');
assert(/OverMesh \$\{available\} is available \(you have \$\{youHave\}\)/.test(src),
       'the banner text must read "OverMesh <v> is available (you have <local>)"');
assert(/const useCommit = !remoteVersion \|\| !localVersion \|\| remoteVersion === localVersion;/.test(src),
       'equal/missing versions must fall back to the short commit');
assert(/document\.getElementById\('update-banner'\)/.test(src), 'the client must drive #update-banner');
assert(/document\.body\.classList\.add\('update-active'\)/.test(src),
       'showing the banner must add the body class that makes room for it');
assert(/localStorage\.setItem\('omUpdateNoticeDismissed', commit\)/.test(src) &&
       /_hideUpdateBanner\(remoteCommit\)/.test(src),
       'dismissal must be stored against the remote commit so the next release still shows');
assert(/openUpdatePanel\(\)/.test(src), 'the button must open the existing update panel');
assert(/function openUpdatePanel\(\)[\s\S]*?switchTab\('settings'\); switchSettingsTab\('app'\);/.test(src),
       'Open updates must go to Settings → App');
assert(/Open updates/.test(indexHtml), 'the banner must label its button "Open updates"');

// Markup + CSS: a top strip, not a toast.
assert(/<div id="update-banner" hidden>/.test(indexHtml), 'index.html must carry the hidden banner');
assert(/data-update-text/.test(indexHtml) && /data-update-open/.test(indexHtml) && /data-update-dismiss/.test(indexHtml),
       'the banner must have text + open + dismiss hooks');
assert(/#update-banner\s*\{/.test(css), 'app.css must style #update-banner');
assert(/background: #c9a227/.test(css), 'the banner must be yellow (Mesh-Torry #c9a227)');
assert(/body\.update-active #update-banner \{ display: flex; \}/.test(css),
       'the banner must be flex-visible only while update-active');
// EST-85 sweep: on a narrow screen the version text must shrink and ellipsize so
// the "Open updates" button and the dismiss X stay reachable.
assert(/#update-banner \[data-update-text\][^}]*text-overflow: ellipsis/.test(css),
       'app.css must ellipsize the banner text on narrow screens');
assert(/#update-banner \[data-update-text\][^}]*text-overflow: ellipsis/.test(liteHtml),
       'lite.html must ellipsize the banner text on narrow screens');
assert(/\.update-banner-btn/.test(css), 'the open button must be styled');
assert(!/\.toast\.toast-update\s*\{/.test(css), 'the old corner toast style must be gone');
assert(!/@keyframes update-glow/.test(css), 'the old toast glow must be gone');
// and showUpdateNotice no longer builds a toast
const showFn = src.match(/function showUpdateNotice\([\s\S]*?\n  \}/);
assert(showFn, 'showUpdateNotice() body must be found');
assert(!/showToast\(/.test(showFn[0]), 'the update notice must not use the corner toast any more');
// EST-85 sweep: user-visible text carries no em dashes (the banner title was the
// only one left in the client after the EST-79 pass; comments may keep theirs).
assert(!/banner\.title\s*=\s*'[^']*\u2014/.test(showFn[0]),
       'the update banner title must not show an em dash');
// EST-85 sweep: the silent strip changes the stack order, so the silent toggle
// must re-run the fit that places the update banner below it.
const silentFn = src.match(/function _updateSilentUi\([\s\S]*?\n  \}/);
assert(silentFn, '_updateSilentUi() body must be found');
assert(/_fitExposedBanner\(\)/.test(silentFn[0]),
       'toggling Silent must re-measure the banner stack');

// Drive the REAL text builder, not a copy: version line normally, commit on
// equal/missing versions.
const txtMatch = src.match(/function _updateBannerText\([\s\S]*?\n  \}/);
assert(txtMatch, '_updateBannerText() must be extractable');
const escHtml = s => String(s == null ? '' : s)
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const _updateBannerText = new Function('escHtml', 'return ' + txtMatch[0])(escHtml);
assert(_updateBannerText('abc1234', '2026.10.01.1', '2026.09.12.9') ===
       'OverMesh 2026.10.01.1 is available (you have 2026.09.12.9)',
       'different versions -> the version line (got ' + _updateBannerText('abc1234', '2026.10.01.1', '2026.09.12.9') + ')');
assert(_updateBannerText('abc1234', '2026.10.01.1', '2026.10.01.1') ===
       'OverMesh abc1234 is available (you have 2026.10.01.1)',
       'equal versions -> the short commit');
assert(_updateBannerText('abc1234', null, '2026.09.12.9') ===
       'OverMesh abc1234 is available (you have 2026.09.12.9)',
       'missing remote version -> the short commit');

// ── Settings block shows Installed / Available ────────────────────────────────
assert(/Installed: <code>\$\{escHtml\(info\.local_version/.test(src),
       'the Settings block must show "Installed: <local_version> (<commit>)"');
assert(/Available: <code>\$\{escHtml\(info\.remote_version/.test(src),
       'the Settings block must show "Available: <remote_version> (<commit>)"');

// ── OM Lite shows the same banner ─────────────────────────────────────────────
assert(/<div id="update-banner" hidden>/.test(liteHtml), 'lite.html must carry the banner too');
assert(/function checkLiteUpdateNotice\(\)/.test(liteJs), 'Lite must check the cached endpoint');
assert(/showLiteUpdateNotice\(d\.remote_commit, d\.remote_version, d\.local_version\)/.test(liteJs),
       'Lite must react to update_available over SSE');
assert(/#update-banner\s*\{/.test(liteHtml), 'Lite must style the banner');

console.log('ok: update-available banner wiring present');
