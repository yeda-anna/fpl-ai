// End-to-end checks for Papa Ranjeet on a phone (390x844, touch) and a desktop
// (1440x900) viewport. Start the app first, then:  npm --prefix tests test
//   BASE_URL=http://127.0.0.1:9000/ npm --prefix tests test   (another server)
//   TEAM_ID=1234567 npm --prefix tests test                    (a real team on live)
// Screenshots are written to tests/screenshots/ (git-ignored).
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');
const OUT = process.argv[2] || path.join(__dirname, 'screenshots');
const BASE = (process.env.BASE_URL || 'http://127.0.0.1:8787/').replace(/\/?$/, '/');
const TEAM = process.env.TEAM_ID || '1';
fs.mkdirSync(OUT, { recursive: true });
const results = [];
const ok = (name, cond, extra='') => { results.push(`${cond ? 'PASS' : 'FAIL'}  ${name}${extra ? '  — ' + extra : ''}`); return cond; };

// Strict check: the layout viewport must stay at the device width, and nothing in the
// visible view may poke past it unless it lives inside an intentional scroller.
let lastOverflow = [];
async function noOverflow(page, vw = 390){
  lastOverflow = await page.evaluate((vw) => {
    const out = [];
    if (window.innerWidth > vw + 1) out.push('layout viewport widened to ' + window.innerWidth);
    const scroller = el => { for (let a = el.parentElement; a && a !== document.body; a = a.parentElement){
      if (/(auto|scroll|hidden)/.test(getComputedStyle(a).overflowX)) return true; } return false; };
    const roots = [document.querySelector('#views .view.on'), document.querySelector('.nav-bar'), document.querySelector('.page-head'), document.getElementById('dock'), document.getElementById('segs')];
    for (const root of roots) { if (!root) continue;
      for (const e of root.querySelectorAll('*')) { const r = e.getBoundingClientRect();
        if (r.width && r.right > vw + 1 && !scroller(e)) { out.push((e.className && typeof e.className === 'string' ? '.' + e.className.split(' ')[0] : e.tagName) + ' right=' + Math.round(r.right)); if (out.length > 3) return out; } } }
    return out;
  }, vw);
  return lastOverflow.length === 0;
}
const errIn = (page, sel) => page.$$eval(`${sel} .err`, els => els.map(e => e.textContent.trim()).slice(0, 2));
// wait until a view has drawn something real (no loader, some text)
const settled = (page, sel, timeout) => page.waitForFunction(s => { const v = document.querySelector(s);
  return v && !v.querySelector('.loading') && !v.querySelector('.skel') && v.innerText.trim().length > 40; }, sel, { timeout }).then(() => true, () => false);

async function phone(browser){
  const ctx = await browser.newContext({ viewport:{width:390,height:844}, deviceScaleFactor:2, isMobile:true, hasTouch:true,
    userAgent:'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1' });
  const page = await ctx.newPage();
  const consoleErrors = [];
  page.on('console', m => { if (m.type() === 'error') consoleErrors.push(m.text()); });
  page.on('pageerror', e => consoleErrors.push('pageerror: ' + e.message));
  const badResponses = [];
  page.on('response', r => { if (r.status() >= 400 && !r.url().includes('/api/entry/999999999')) badResponses.push(r.status() + ' ' + r.url()); });
  const entryReads = [];
  page.on('request', r => { if (r.url().includes(`/api/entry/${TEAM}?`)) entryReads.push(r.url()); });

  // ---- the opening film plays on launch (Theatre.js), and Skip ends it ----
  await page.goto(BASE, { waitUntil: 'networkidle' });
  ok('phone: the page is named Papa Ranjeet', /^Papa Ranjeet\b/.test(await page.title()), await page.title());
  ok('phone: animation libraries load from /static/vendor (GSAP, anime.js, Motion, Theatre.js, AutoAnimate)', await page.evaluate(() =>
    !!(window.gsap && window.DrawSVGPlugin && window.MotionPathPlugin && window.anime && window.Motion && window.Motion.animate && window.Motion.inView
       && window.Theatre && window.Theatre.core && typeof window.autoAnimate === 'function'
       && typeof FX !== 'undefined' && typeof Magic !== 'undefined' && typeof Intro !== 'undefined')));
  {
    const tc0 = await page.textContent('#inTc'); await page.waitForTimeout(450); const tc1 = await page.textContent('#inTc');
    ok('phone: the opening film plays on launch, its timecode running', await page.isVisible('#intro') && tc0 !== tc1, `${tc0} → ${tc1}`);
    ok('phone: the film flies the drones traced from the logo portrait, and the logo is that portrait', await page.evaluate(() =>
      typeof PORTRAIT !== 'undefined' && PORTRAIT.d.length / 4 > 300 && /^\d+ drones$/i.test(document.getElementById('inCount').textContent.trim())
      && /logo\.webp$/.test(document.querySelector('#logo image').getAttribute('href'))
      && document.querySelector('#inMark .in-photo').complete), await page.textContent('#inCount'));
    await page.waitForTimeout(1800);
    await page.screenshot({ path: `${OUT}/m-00-film.png` });
    await page.click('#inSkip');
    ok('phone: Skip ends the opening film', await page.waitForSelector('#intro', { state: 'hidden', timeout: 3000 }).then(() => true, () => false));
  }
  // ---- first visit: the landing screen asks for the Team ID ----
  ok('phone: first visit opens the landing screen', await page.isVisible('#landing'));
  ok('phone: landing carries a line of house humour', (await page.textContent('#landQuip')).trim().length > 20);
  ok('phone: landing has the neon pitch scene', (await page.$$('#scene .ln')).length >= 5 && !!(await page.$('#sceneBall')));
  ok('phone: five tabs in the dock, no "More"', (await page.$$('#dock button[data-tab]')).length === 5 && !(await page.$('[data-more]')));
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${OUT}/m-01-landing.png` });
  await page.click('#landGo');
  ok('phone: an empty ID explains what to do', /team id/i.test(await page.textContent('#landErr')));
  await page.fill('#landId', '999999999'); await page.click('#landGo');
  await page.waitForFunction(() => /couldn’t find/i.test(document.querySelector('#landErr').textContent), null, { timeout: 15000 }).catch(() => {});
  ok('phone: an unknown team shows a clear error', /couldn’t find team 999999999/i.test(await page.textContent('#landErr')), await page.textContent('#landErr'));
  await page.fill('#landId', TEAM); await page.click('#landGo');
  await page.waitForSelector('#landing', { state: 'hidden', timeout: 30000 });
  await page.waitForSelector('#v-home-squad .pitch-card', { timeout: 30000 });
  ok('phone: the team loads straight into Home → My squad', (await page.evaluate(() => location.hash)) === '#home/squad');
  ok('phone: the Team ID is saved in the browser', await page.evaluate(t => JSON.parse(localStorage.getItem('fplai_team')) === t, TEAM));
  ok('phone: the team pill shows the team name', !/add team/i.test(await page.textContent('#teamLabel')), await page.textContent('#teamLabel'));
  ok('phone: the first read of the team asks FPL afresh (fresh=1)', entryReads.length >= 1 && /[?&]fresh=1/.test(entryReads[0]), entryReads[0] || 'none');
  await page.waitForTimeout(1300);
  {
    const want = await page.evaluate(t => fetch(`/api/entry/${t}?horizon=5`).then(r => r.json()).then(j => j.entry.overall_rank ? j.entry.overall_rank.toLocaleString() : '–'), TEAM);
    const got = (await page.textContent('#v-home-squad .tile .val')).trim();
    ok('phone: counters count up to the true value', got === want, `${got} vs ${want}`);
  }
  {
    // Home wears the team's name, and My squad opens with a roast of the last gameweek's score
    const ent = await page.evaluate(t => fetch(`/api/entry/${t}?horizon=5`).then(r => r.json()), TEAM);
    const pts = ent.history.length ? String(ent.history[ent.history.length - 1].points) : '';
    ok('phone: the Home title is the team name from FPL', (await page.textContent('#view-title')).trim() === ent.entry.name, await page.textContent('#view-title'));
    const sub = (await page.textContent('#view-sub')).trim();
    ok('phone: My squad opens with a roast of the week’s score', await page.$eval('#view-sub', e => e.classList.contains('verdict')) && sub.length > 25
       && !/projected forward/i.test(sub) && (!pts || sub.includes(pts) || /average|shocker/i.test(sub)), sub);
    await page.click('#segs button[data-seg="picks"]'); await page.waitForTimeout(200);
    ok('phone: other Home pages keep the team name and their own line', (await page.textContent('#view-title')).trim() === ent.entry.name
       && !(await page.$eval('#view-sub', e => e.classList.contains('verdict'))));
    await page.click('#segs button[data-seg="squad"]'); await page.waitForTimeout(200);
    ok('phone: the verdict is the same line on the way back', (await page.textContent('#view-sub')).trim() === sub);
  }
  ok('phone: home fits width', await noOverflow(page), lastOverflow.join(', '));
  ok('phone: a meteor shower crosses the sky behind every page', (await page.$$('#skyMeteors .mg-meteor')).length >= 12);
  await page.screenshot({ path: `${OUT}/m-02-home.png` });
  {
    // a transfer made in the FPL app (private until the deadline) can be entered by hand and counts everywhere
    const outId = await page.$eval('#madeOut option[value]:not([value=""])', o => o.value);
    await page.selectOption('#madeOut', outId);
    await page.waitForSelector('#madeIn:not([disabled])', { timeout: 8000 });
    const inId = await page.$eval('#madeIn option[value]:not([value=""])', o => o.value);
    await page.selectOption('#madeIn', inId); await page.click('#madeAdd');
    await page.waitForSelector('#v-home-squad .made-list [data-unmade]', { timeout: 15000 });
    const saved = await page.evaluate(t => JSON.parse(localStorage.getItem('fplai_made'))[t], TEAM);
    const squadIds = await page.evaluate(t => fetch(`/api/entry/${t}?horizon=5&made=${JSON.parse(localStorage.getItem('fplai_made'))[t].map(p => p.join('-')).join(',')}`)
      .then(r => r.json()).then(j => j.squad.map(p => p.id)), TEAM);
    ok('phone: a transfer made in the FPL app can be added by hand', JSON.stringify(saved) === JSON.stringify([[+outId, +inId]])
       && squadIds.includes(+inId) && !squadIds.includes(+outId), JSON.stringify(saved));
    ok('phone: the made-transfers card fits width', await noOverflow(page), lastOverflow.join(', '));
    await page.screenshot({ path: `${OUT}/m-02b-made.png`, fullPage: false });
    await page.click('#v-home-squad .made-list [data-unmade]');
    await page.waitForFunction(() => !document.querySelector('#v-home-squad .made-list [data-unmade]') && document.querySelector('#madeOut'), null, { timeout: 15000 });
    ok('phone: a hand-entered transfer can be removed', await page.evaluate(t => !(JSON.parse(localStorage.getItem('fplai_made') || '{}')[t]), TEAM));
  }

  // ---- every tab and every sub-page renders, with no error and nothing wider than the phone ----
  const tabs = await page.$$eval('#dock button[data-tab]', bs => bs.map(b => b.dataset.tab));
  for (const t of tabs) {
    await page.click(`#dock button[data-tab="${t}"]`); await page.waitForTimeout(250);
    ok(`phone: ${t} tab is highlighted`, await page.$eval(`#dock button[data-tab="${t}"]`, b => b.classList.contains('on')));
    if (t === 'plan') ok('phone: other tabs keep their own title', (await page.textContent('#view-title')).trim() === 'Plan', await page.textContent('#view-title'));
    const segs = await page.$$eval('#segs:not([hidden]) button[data-seg]', bs => bs.map(b => b.dataset.seg));
    for (const s of (segs.length ? segs : [null])) {
      if (s) await page.click(`#segs button[data-seg="${s}"]`);
      const seg = s || (await page.evaluate(() => location.hash.split('/')[1]));
      const sel = `#v-${t}-${seg}`;
      if (t === 'plan' && seg === 'transfers') await page.waitForSelector('#svLeft .path', { timeout: 90000 }).catch(() => {});
      const done = (t === 'leagues' || t === 'ask') ? true : await settled(page, sel, 120000);
      const errs = await errIn(page, sel);
      ok(`phone: ${t}/${seg} renders without an error`, done && errs.length === 0, errs.join(' | ') || (done ? '' : 'timed out'));
      ok(`phone: ${t}/${seg} fits width`, await noOverflow(page), lastOverflow.join(', '));
      ok(`phone: address is #${t}/${seg}`, (await page.evaluate(() => location.hash)) === `#${t}/${seg}`);
      await page.screenshot({ path: `${OUT}/m-03-${t}-${seg}.png` });
    }
  }

  // ---- the tools still do their jobs ----
  await page.click('#dock button[data-tab="players"]'); await page.click('#segs button[data-seg="projections"]');
  await page.waitForSelector('#xpBody tr', { timeout: 30000 });
  {
    // re-sorting keeps the table and moves the rows (keyed rows + AutoAnimate) instead of redrawing it
    const first = await page.$eval('#xpBody tr', tr => tr.dataset.pid);
    await page.$eval('#xpTable .card.xp', c => { c.dataset.mark = 'kept'; });
    await page.selectOption('#fSort', 'ownership');
    const moved = await page.waitForFunction(f => { const tr = [...document.querySelectorAll('#xpBody > tr')].find(x => !('__aa_del' in x)); const c = document.querySelector('#xpTable .card.xp');
      return c && !c.classList.contains('busy') && tr && tr.dataset.pid !== f; }, first, { timeout: 20000 }).then(() => true, () => false);
    ok('phone: re-sorting moves the rows in place (AutoAnimate)', moved && await page.$eval('#xpTable .card.xp', c => c.dataset.mark === 'kept')
       && await page.$eval('#xpBody', b => !!b._aa));
    await page.selectOption('#fSort', 'xpts_total');
    await page.waitForFunction(f => { const tr = [...document.querySelectorAll('#xpBody > tr')].find(x => !('__aa_del' in x)); const c = document.querySelector('#xpTable .card.xp');
      return c && !c.classList.contains('busy') && tr && tr.dataset.pid === f; }, first, { timeout: 20000 }).catch(() => {});
  }
  const pid = await page.$$eval('#xpBody > tr', trs => trs.find(x => !('__aa_del' in x)).dataset.pid);
  const who = (await page.textContent(`#xpBody tr[data-pid="${pid}"] td:first-child a`)).trim();
  const before = await page.textContent(`#xpBody tr[data-pid="${pid}"] td:last-child`);
  await page.click(`#xpBody tr[data-pid="${pid}"] .mins`); await page.fill(`#xpBody tr[data-pid="${pid}"] .mins input`, '45'); await page.keyboard.press('Enter');
  await page.waitForSelector('#resetMins', { timeout: 20000 });
  await page.fill('#fSearch', who); await page.press('#fSearch', 'Enter');
  await page.waitForSelector(`#xpBody tr[data-pid="${pid}"] .mins.set`, { timeout: 20000 });
  const after = await page.textContent(`#xpBody tr[data-pid="${pid}"] td:last-child`);
  ok('phone: a minutes edit applies', parseFloat(after) < parseFloat(before), `${who}: ${before.trim()} → ${after.trim()} xPts at 45′`);
  await page.click('#resetMins'); await page.waitForSelector('#xpBody tr', { timeout: 20000 });
  ok('phone: a minutes edit resets', !(await page.$('#resetMins')));

  await page.click('#dock button[data-tab="plan"]'); await page.click('#segs button[data-seg="transfers"]');
  await page.waitForSelector('#svLeft .path', { timeout: 90000 });
  ok('phone: the solver returns plans', (await page.$$('#svLeft .path')).length >= 1);
  await page.click('#gwNext'); await page.waitForTimeout(250);
  ok('phone: the pitch steps to the next gameweek', /GW\d+/.test(await page.textContent('.gw-nav span')));

  await page.click('#dock button[data-tab="ask"]');
  await page.click('#v-ask-copilot .chipset button');
  await page.waitForSelector('#ans .bubble', { timeout: 60000 });
  ok('phone: the Copilot answers', (await page.textContent('#ans .bubble')).length > 20);
  await page.click('#v-ask-copilot .chipset button:nth-child(2)');
  await page.waitForFunction(() => document.querySelectorAll('#ans .qa .bubble').length >= 2, null, { timeout: 60000 }).catch(() => {});
  ok('phone: the Copilot keeps a log, newest entry first', await page.evaluate(() => {
    const qa = [...document.querySelectorAll('#ans > .qa')].filter(x => !('__aa_del' in x));
    return qa.length === 2 && /Log 002/.test(qa[0].textContent) && qa[1].classList.contains('old'); }));

  await page.click('#dock button[data-tab="leagues"]');
  await page.fill('#lgId', '314'); await page.selectOption('#lgN', '6'); await page.click('#lgGo');
  ok('phone: a mini-league is analysed', await page.waitForSelector('#lgOut table', { timeout: 60000 }).then(() => true, () => false), (await errIn(page, '#v-leagues-league')).join(' | '));
  ok('phone: leagues fit width', await noOverflow(page), lastOverflow.join(', '));

  await page.click('#dock button[data-tab="home"]'); await page.click('#segs button[data-seg="squad"]');
  await page.waitForSelector('#v-home-squad .pl-tok', { timeout: 20000 });
  await page.click('#v-home-squad .pl-tok');
  ok('phone: the player sheet opens', await page.waitForSelector('.sheet .tile', { timeout: 20000 }).then(() => true, () => false));
  await page.keyboard.press('Escape'); await page.waitForTimeout(200);

  // ---- menu: how it works, refresh, forget ----
  await page.click('#menuBtn');
  ok('phone: the menu opens with How it works', await page.waitForSelector('.sheet #menuModel table', { timeout: 20000 }).then(() => true, () => false));
  ok('phone: the menu fits width', await noOverflow(page), lastOverflow.join(', '));
  await page.screenshot({ path: `${OUT}/m-04-menu.png` });
  await Promise.all([page.waitForNavigation({ waitUntil: 'networkidle' }), page.click('#mRefresh')]);
  ok('phone: Refresh app reloads, and the saved team skips the landing screen', !(await page.isVisible('#landing')) && !/add team/i.test(await page.textContent('#teamLabel')));
  ok('phone: the opening film plays again on a fresh launch, then gets out of the way by itself', await page.isVisible('#intro')
     && await page.waitForSelector('#intro', { state: 'hidden', timeout: 17000 }).then(() => true, () => false));
  ok('phone: old addresses still work (#solver → #plan/transfers)', await page.goto(BASE + '#solver', { waitUntil: 'networkidle' }).then(() => page.evaluate(() => location.hash)) === '#plan/transfers');
  await page.click('#inSkip').catch(() => {}); await page.waitForSelector('#intro', { state: 'hidden', timeout: 3000 }).catch(() => {});
  await page.click('#menuBtn'); await page.waitForSelector('#mForget');
  await page.click('#mForget'); await page.waitForTimeout(600);
  ok('phone: Forget team clears the device and asks again', await page.isVisible('#landing') && await page.evaluate(() => localStorage.getItem('fplai_team') === null));
  await page.click('#landSkip'); await page.waitForTimeout(600);
  ok('phone: Just browsing lands on Picks', (await page.evaluate(() => location.hash)) === '#home/picks');
  await page.click('#segs button[data-seg="grade"]');
  ok('phone: a team-only page offers to add a team', await page.waitForSelector('#v-home-grade .need-team', { timeout: 10000 }).then(() => true, () => false));

  const realErrors = consoleErrors.filter(m => !/Failed to load resource/.test(m));
  // the menu can turn the film off for this device
  await page.click('#menuBtn'); await page.waitForSelector('#mFilm');
  await page.click('#mFilm');
  ok('phone: the menu turns the opening film off', await page.evaluate(() => localStorage.getItem('fplai_intro') === '"off"'));
  await page.keyboard.press('Escape');
  await page.reload({ waitUntil: 'networkidle' });
  ok('phone: with the film off, the app opens straight away', !(await page.isVisible('#intro')));
  ok('phone: no console errors', realErrors.length === 0, realErrors.slice(0, 4).join(' || '));
  ok('phone: no failed requests (besides the deliberate unknown team)', badResponses.length === 0, badResponses.slice(0, 4).join(' || '));
  await ctx.close();
}

async function desktop(browser){
  const ctx = await browser.newContext({ viewport:{width:1440,height:900}, deviceScaleFactor:1 });
  const page = await ctx.newPage();
  const consoleErrors = [];
  page.on('console', m => { if (m.type() === 'error') consoleErrors.push(m.text()); });
  page.on('pageerror', e => consoleErrors.push('pageerror: ' + e.message));
  await page.goto(BASE, { waitUntil: 'networkidle' });
  await page.waitForTimeout(1900);
  await page.screenshot({ path: `${OUT}/d-00-film.png` });
  ok('desktop: the opening film runs to its end and opens onto the app', await page.waitForSelector('#intro', { state: 'hidden', timeout: 17000 }).then(() => true, () => false));
  ok('desktop: first visit opens the landing screen', await page.isVisible('#landing'));
  await page.waitForTimeout(1800);
  await page.screenshot({ path: `${OUT}/d-01-landing.png` });
  await page.fill('#landId', TEAM); await page.click('#landGo');
  await page.waitForSelector('#v-home-squad .pitch-card', { timeout: 30000 });
  ok('desktop: tab links visible, dock hidden', await page.isVisible('#nav') && !(await page.isVisible('#dock')));
  {
    const build = await page.$eval('meta[name="app-build"]', m => m.content).catch(() => '');
    const live = await page.evaluate(() => fetch('/version', { cache: 'no-store' }).then(r => r.json()).then(j => j.build).catch(() => ''));
    ok('desktop: page carries a build id matching /version', !!build && build === live, `${build} vs ${live}`);
    const refs = await page.$$eval('link[rel=stylesheet][href^="/static/"], script[src^="/static/"]', els => els.map(e => e.getAttribute('href') || e.getAttribute('src')));
    ok('desktop: CSS and JS, vendor libraries included, are content-fingerprinted', refs.length >= 7 && refs.every(u => /\?v=[0-9a-f]{12}$/.test(u)), refs.join(', '));
    const head = await page.evaluate(() => fetch('/', { cache: 'no-store' }).then(r => r.headers.get('cache-control')));
    ok('desktop: page is never stored by the browser (no-store)', /no-store/.test(head || ''), head);
    const apiHead = await page.evaluate(() => fetch('/api/meta').then(r => r.headers.get('cache-control')));
    ok('desktop: API answers are never stored by the browser (no-store)', /no-store/.test(apiHead || ''), apiHead);
    const enc = await page.evaluate(u => fetch(u).then(r => r.headers.get('content-encoding')), refs.find(u => /motion\.min\.js/.test(u)));
    ok('desktop: scripts are served compressed (gzip)', enc === 'gzip', enc);
  }
  await page.waitForTimeout(1200);
  await page.screenshot({ path: `${OUT}/d-02-home.png` });
  for (const t of ['plan', 'players', 'leagues', 'ask', 'home']) {
    await page.click(`#nav button[data-tab="${t}"]`);
    const sel = await page.evaluate(() => '#v-' + location.hash.slice(1).replace('/', '-'));
    if (t === 'plan') await page.waitForSelector('#svLeft .path', { timeout: 90000 }).catch(() => {});
    const done = (t === 'leagues' || t === 'ask') ? true : await settled(page, sel, 120000);
    ok(`desktop: ${t} renders without an error`, done && (await errIn(page, sel)).length === 0, (await errIn(page, sel)).join(' | '));
    await page.screenshot({ path: `${OUT}/d-03-${t}.png` });
  }
  await page.reload({ waitUntil: 'networkidle' });
  ok('desktop: a returning visitor goes straight to their team', !(await page.isVisible('#landing')));
  ok('desktop: no console errors', consoleErrors.length === 0, consoleErrors.slice(0, 4).join(' || '));
  await ctx.close();
}

async function reducedMotion(browser){
  const ctx = await browser.newContext({ viewport:{width:390,height:844}, reducedMotion:'reduce' });
  const page = await ctx.newPage();
  await page.goto(BASE, { waitUntil: 'networkidle' });
  ok('reduced motion: no opening film', !(await page.isVisible('#intro')));
  ok('reduced motion: no meteor shower', (await page.$$('.mg-meteor')).length === 0);
  await page.fill('#landId', TEAM); await page.click('#landGo');
  await page.waitForSelector('#v-home-squad .tile', { timeout: 30000 });
  const st = await page.evaluate(() => ({ minOpacity: Math.min(...[...document.querySelectorAll('#v-home-squad .tile, #v-home-squad .card')].map(e => +getComputedStyle(e).opacity)),
    rank: document.querySelector('#v-home-squad .tile .val').textContent.trim() }));
  ok('reduced motion: everything is visible at once, nothing counts up', st.minOpacity === 1 && !/^0$/.test(st.rank), JSON.stringify(st));
  await ctx.close();
}

// For visitors who don't play FPL: the landing offers a made-up demo team, roasted, with a tour.
async function demoTeam(browser){
  const ctx = await browser.newContext({ viewport:{width:390,height:844}, isMobile:true, hasTouch:true, reducedMotion:'reduce' });
  const page = await ctx.newPage();
  const errs = []; page.on('pageerror', e => errs.push(e.message)); page.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
  await page.goto(BASE, { waitUntil: 'networkidle' });
  ok('demo: the landing offers a demo team to people without FPL', await page.isVisible('#landDemo'));
  await page.click('#landDemo');
  await page.waitForSelector('#v-home-squad .demo-tour', { timeout: 30000 });
  await settled(page, '#v-home-squad', 20000);
  const head = { title: (await page.textContent('#view-title')).trim(), sub: (await page.textContent('#view-sub')).trim() };
  ok('demo: Home opens on the made-up team, roasted', head.title === 'Gut Feeling FC' && head.sub.length > 25
     && await page.$eval('#view-sub', e => e.classList.contains('verdict')), JSON.stringify(head));
  ok('demo: the tour explains FPL and links every part of the app', /Fantasy Premier League/.test(await page.textContent('.demo-tour'))
     && (await page.$$('.demo-tour .tour-go')).length >= 5);
  ok('demo: no made-transfers card for a made-up team', !(await page.$('#v-home-squad .made')));
  ok('demo: nothing is saved on the device', await page.evaluate(() => localStorage.getItem('fplai_team') === null));
  ok('demo: fits the phone', await noOverflow(page), lastOverflow.join(', '));
  await page.screenshot({ path: `${OUT}/m-20-demo.png` });
  await page.click('.demo-tour .tour-go[data-go="home/grade"]');
  ok('demo: the tour opens Grade, which marks the demo squad', await settled(page, '#v-home-grade', 60000)
     && (await errIn(page, '#v-home-grade')).length === 0 && /\/\s*100/.test(await page.textContent('#v-home-grade')));
  await page.reload({ waitUntil: 'networkidle' });
  ok('demo: an app reload keeps you in the demo', await page.$eval('#landing', e => e.hidden) && /Gut Feeling/.test(await page.textContent('#teamLabel')));
  await page.click('#menuBtn'); await page.click('#mForget');
  ok('demo: leaving the demo goes back to the landing', await page.isVisible('#landing') && await page.evaluate(() => sessionStorage.getItem('fplai_demo') === null));
  ok('demo: no console errors', errs.length === 0, errs.slice(0, 3).join(' || '));
  await ctx.close();
}

(async () => {
  const browser = await chromium.launch();
  try { await phone(browser); } catch (e) { ok('phone run completed', false, e.message.split('\n')[0]); }
  try { await desktop(browser); } catch (e) { ok('desktop run completed', false, e.message.split('\n')[0]); }
  try { await reducedMotion(browser); } catch (e) { ok('reduced-motion run completed', false, e.message.split('\n')[0]); }
  try { await demoTeam(browser); } catch (e) { ok('demo run completed', false, e.message.split('\n')[0]); }
  await browser.close();
  console.log(results.join('\n'));
  const fails = results.filter(r => r.startsWith('FAIL')).length;
  console.log(`\n${results.length - fails} passed, ${fails} failed`);
  process.exit(fails ? 1 : 0);
})();
