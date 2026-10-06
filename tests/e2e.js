// End-to-end checks for Mug's Game FC on a phone (390x844, touch) and a desktop
// (1440x900) viewport. Start the app first, then:  npm --prefix tests test
//   BASE_URL=http://127.0.0.1:9000/ npm --prefix tests test   (another server)
// Screenshots are written to tests/screenshots/ (git-ignored).
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');
const OUT = process.argv[2] || path.join(__dirname, 'screenshots');
const BASE = (process.env.BASE_URL || 'http://127.0.0.1:8787/').replace(/\/?$/, '/');
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
    const roots = [document.querySelector('.view.on'), document.querySelector('.nav-bar'), document.querySelector('.page-head'), document.getElementById('tabbar')];
    for (const root of roots) { if (!root) continue;
      for (const e of root.querySelectorAll('*')) { const r = e.getBoundingClientRect();
        if (r.width && r.right > vw + 1 && !scroller(e)) { out.push((e.className && typeof e.className === 'string' ? '.' + e.className.split(' ')[0] : e.tagName) + ' right=' + Math.round(r.right)); if (out.length > 3) return out; } } }
    return out;
  }, vw);
  return lastOverflow.length === 0;
}
async function errBoxes(page, view){
  return page.$$eval(`#view-${view} .err`, els => els.map(e => e.textContent.trim()).slice(0, 2));
}

async function phone(browser){
  const ctx = await browser.newContext({ viewport:{width:390,height:844}, deviceScaleFactor:2, isMobile:true, hasTouch:true,
    userAgent:'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1' });
  const page = await ctx.newPage();
  const consoleErrors = [];
  page.on('console', m => { if (m.type() === 'error') consoleErrors.push(m.text()); });
  page.on('pageerror', e => consoleErrors.push('pageerror: ' + e.message));
  const badResponses = [];
  page.on('response', r => { if (r.status() >= 400 && !r.url().includes('/api/entry/999999999')) badResponses.push(r.status() + ' ' + r.url()); });

  await page.goto(BASE, { waitUntil: 'networkidle' });
  ok('phone: team screen shows on launch', await page.isVisible('#onboard'));
  ok('phone: tab dock visible, desktop links hidden', await page.isVisible('#tabbar') && !(await page.isVisible('#nav')));
  await page.screenshot({ path: `${OUT}/m-01-onboard.png` });

  // a team that doesn't exist
  await page.fill('#obTeam', '999999999'); await page.click('#obGo');
  await page.waitForFunction(() => document.querySelector('#obErr').textContent.length > 0, null, { timeout: 15000 });
  ok('phone: unknown team shows a clear error', /couldn’t find team/i.test(await page.textContent('#obErr')), await page.textContent('#obErr'));

  // a real team
  await page.fill('#obTeam', '1'); await page.click('#obGo');
  await page.waitForSelector('#onboard', { state: 'hidden', timeout: 30000 });
  await page.waitForSelector('#view-dashboard .pitch-card', { timeout: 30000 });
  ok('phone: team loads, pitch renders', true);
  ok('phone: team pill shows team name', !/add team/i.test(await page.textContent('#teamLabel')), await page.textContent('#teamLabel'));
  ok('phone: dashboard fits width', await noOverflow(page), lastOverflow.join(', '));
  await page.screenshot({ path: `${OUT}/m-02-dashboard.png`, fullPage: false });
  await page.screenshot({ path: `${OUT}/m-02b-dashboard-full.png`, fullPage: true });

  // Expected Points + minutes edit
  await page.click('#tabbar button[data-view="xpts"]');
  await page.waitForSelector('#xpBody tr', { timeout: 30000 });
  ok('phone: xPts table renders', (await page.$$('#xpBody tr')).length >= 20);
  ok('phone: xPts page has no sideways page scroll', await noOverflow(page), lastOverflow.join(', '));
  const who = (await page.textContent('#xpBody tr td:first-child a')).trim();
  const before = await page.textContent('#xpBody tr td:last-child');
  await page.click('#xpBody tr .mins'); await page.fill('#xpBody tr .mins input', '45'); await page.keyboard.press('Enter');
  await page.waitForSelector('#resetMins', { timeout: 20000 });
  await page.fill('#fSearch', who); await page.press('#fSearch', 'Enter');
  await page.waitForSelector('#xpBody .mins.set', { timeout: 20000 });
  const after = await page.textContent('#xpBody tr td:last-child');
  ok('phone: minutes edit applies', parseFloat(after) < parseFloat(before), `${who}: ${before.trim()} → ${after.trim()} xPts at 45′`);
  await page.fill('#fSearch', ''); await page.press('#fSearch', 'Enter');
  await page.screenshot({ path: `${OUT}/m-03-xpts.png` });
  await page.click('#resetMins'); await page.waitForSelector('#xpBody tr', { timeout: 20000 });
  ok('phone: minutes edit resets', !(await page.$('#resetMins')));

  // Solver
  await page.click('#tabbar button[data-view="solver"]');
  await page.waitForSelector('#svLeft .path', { timeout: 90000 });
  ok('phone: solver returns plans', (await page.$$('#svLeft .path')).length >= 1, (await page.$$('#svLeft .path')).length + ' paths');
  const cmdY = await page.$eval('.ws-cmd', e => e.getBoundingClientRect().top);
  const pitchY = await page.$eval('#svLeft', e => e.getBoundingClientRect().top);
  ok('phone: solver controls sit above the pitch', cmdY < pitchY);
  ok('phone: solver fits width', await noOverflow(page), lastOverflow.join(', '));
  await page.screenshot({ path: `${OUT}/m-04-solver.png` });
  await page.$eval('#svLeft', e => e.scrollIntoView());
  await page.screenshot({ path: `${OUT}/m-04b-solver-pitch.png` });
  await page.click('#gwNext'); await page.waitForTimeout(250);
  ok('phone: pitch steps to next gameweek', /GW\d+/.test(await page.textContent('.gw-nav span')) && (await page.textContent('.gw-c.on .g')) !== null);
  if ((await page.$$('#svLeft .path')).length > 1) { await page.click('#svLeft .path[data-k="1"]'); await page.waitForTimeout(200);
    ok('phone: switching plan works', await page.$eval('#svLeft .path[data-k="1"]', e => e.classList.contains('on'))); }
  await page.$eval('#svRight', e => e.scrollIntoView());
  await page.screenshot({ path: `${OUT}/m-04c-solver-timeline.png` });

  // Copilot
  await page.click('#tabbar button[data-view="copilot"]');
  await page.click('#view-copilot .chipset button');
  await page.waitForSelector('#ans .bubble', { timeout: 60000 });
  ok('phone: copilot answers', (await page.textContent('#ans .bubble')).length > 20);
  ok('phone: copilot fits width', await noOverflow(page), lastOverflow.join(', '));
  await page.screenshot({ path: `${OUT}/m-05-copilot.png` });

  // More sheet + each tool in it
  await page.click('#tabbar button[data-more]'); await page.waitForTimeout(450);
  ok('phone: More sheet opens', await page.$eval('#more', e => e.classList.contains('open')));
  await page.screenshot({ path: `${OUT}/m-06-more.png` });
  const moreViews = [
    ['rate',    '#view-rate .grade', 60000],
    ['compare', '#cOut .bubble',      40000],
    ['scout',   '#scOut table',       40000],
    ['model',   '#view-model table',  30000],
    ['chips',   '#view-chips .plan, #view-chips .card h3', 120000],
  ];
  for (const [v, sel, to] of moreViews) {
    if (!(await page.$eval('#more', e => e.classList.contains('open')))) { await page.click('#tabbar button[data-more]'); await page.waitForTimeout(450); }
    await page.click(`#moreGrid button[data-view="${v}"]`);
    try { await page.waitForSelector(sel, { timeout: to }); ok(`phone: ${v} renders`, true); }
    catch (e) { ok(`phone: ${v} renders`, false, (await errBoxes(page, v)).join(' | ') || 'timed out'); }
    ok(`phone: ${v} has no error box`, (await errBoxes(page, v)).length === 0, (await errBoxes(page, v)).join(' | '));
    ok(`phone: ${v} fits width`, await noOverflow(page), lastOverflow.join(', '));
    ok(`phone: More tab highlighted for ${v}`, await page.$eval('#tabbar button[data-more]', e => e.classList.contains('on')));
    await page.screenshot({ path: `${OUT}/m-07-${v}.png` });
  }
  // scout sub-tabs
  for (const k of ['setpieces', 'defcon', 'lineups']) {
    await page.click('#more', { trial: true }).catch(()=>{});
    await page.click('#tabbar button[data-more]'); await page.waitForTimeout(400);
    await page.click('#moreGrid button[data-view="scout"]');
    await page.click(`#scTabs button[data-k="${k}"]`);
    await page.waitForFunction(() => !document.querySelector('#scOut .loading'), null, { timeout: 30000 });
    ok(`phone: scout ${k}`, (await errBoxes(page, 'scout')).length === 0 && (await noOverflow(page)), lastOverflow.join(', '));
  }
  // mini-league
  await page.click('#tabbar button[data-more]'); await page.waitForTimeout(400);
  await page.click('#moreGrid button[data-view="league"]');
  await page.fill('#lgId', '314'); await page.selectOption('#lgN', '6'); await page.click('#lgGo');
  try { await page.waitForSelector('#lgOut table', { timeout: 60000 }); ok('phone: minileague analysis', true); }
  catch (e) { ok('phone: minileague analysis', false, (await errBoxes(page, 'league')).join(' | ') || 'timed out'); }
  ok('phone: minileague fits width', await noOverflow(page), lastOverflow.join(', '));
  await page.screenshot({ path: `${OUT}/m-08-league.png` });

  // player sheet from the dashboard
  await page.click('#tabbar button[data-view="dashboard"]');
  await page.waitForSelector('#view-dashboard .pl-tok', { timeout: 20000 });
  await page.click('#view-dashboard .pl-tok');
  await page.waitForSelector('.sheet .tile', { timeout: 20000 });
  ok('phone: player sheet opens as bottom sheet', true);
  await page.screenshot({ path: `${OUT}/m-09-player-sheet.png` });
  await page.keyboard.press('Escape'); await page.waitForTimeout(200);

  // light theme
  await page.click('#tabbar button[data-more]'); await page.waitForTimeout(400);
  await page.click('#moreTheme'); await page.waitForTimeout(300);
  ok('phone: theme switches to light', await page.$eval('html', e => e.dataset.theme === 'light'));
  await page.click('#more .more-scrim', { position: { x: 20, y: 20 } }); await page.waitForTimeout(400);
  await page.screenshot({ path: `${OUT}/m-10-dashboard-light.png` });
  await page.click('#tabbar button[data-view="solver"]');
  await page.waitForSelector('#svLeft .path', { timeout: 90000 });
  await page.screenshot({ path: `${OUT}/m-11-solver-light.png` });

  // relaunch: asked again, remembered, skippable
  await page.reload({ waitUntil: 'networkidle' });
  ok('phone: asked again on relaunch', await page.isVisible('#onboard'));
  ok('phone: remembers the team (welcome back + prefilled)', (await page.inputValue('#obTeam')) === '1' && /welcome back/i.test(await page.textContent('#obWelcome')));
  await page.screenshot({ path: `${OUT}/m-12-onboard-return.png` });
  await page.click('#obSkip');
  await page.waitForSelector('#onboard', { state: 'hidden' });
  ok('phone: skip leaves you browsing without a team', /add team/i.test(await page.textContent('#teamLabel')));
  await page.click('#tabbar button[data-view="solver"]');
  await page.waitForSelector('#view-solver .need-team', { timeout: 10000 });
  ok('phone: team-only tool offers to add a team', true);
  await page.screenshot({ path: `${OUT}/m-13-need-team.png` });
  await page.click('#view-solver .need-team .btn');
  ok('phone: "Add my team" reopens the team screen', await page.isVisible('#onboard'));
  await page.click('#obSkip');

  const realErrors = consoleErrors.filter(m => !/Failed to load resource/.test(m));
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
  ok('desktop: team screen shows on launch', await page.isVisible('#onboard'));
  await page.screenshot({ path: `${OUT}/d-01-onboard.png` });
  await page.fill('#obTeam', '1'); await page.click('#obGo');
  await page.waitForSelector('#view-dashboard .pitch-card', { timeout: 30000 });
  ok('desktop: links visible, tab dock hidden', await page.isVisible('#nav') && !(await page.isVisible('#tabbar')));
  await page.screenshot({ path: `${OUT}/d-02-dashboard.png` });
  for (const v of ['xpts', 'solver', 'chips', 'copilot', 'rate', 'compare', 'league', 'scout', 'model']) {
    await page.click(`#nav button[data-view="${v}"]`);
    await page.waitForFunction(view => {
      const s = document.querySelector('#view-' + view);
      return s && !s.querySelector('.loading') && !s.querySelector('.skel') && s.innerText.trim().length > 40;
    }, v, { timeout: 120000 }).catch(() => {});
    ok(`desktop: ${v} renders without error`, (await errBoxes(page, v)).length === 0, (await errBoxes(page, v)).join(' | '));
    if (v === 'solver') await page.screenshot({ path: `${OUT}/d-03-solver.png` });
  }
  await page.click('#themeBtn'); await page.click('#nav button[data-view="dashboard"]'); await page.waitForTimeout(500);
  await page.screenshot({ path: `${OUT}/d-04-dashboard-light.png` });
  ok('desktop: no console errors', consoleErrors.length === 0, consoleErrors.slice(0, 4).join(' || '));
  await ctx.close();
}

(async () => {
  const browser = await chromium.launch();
  try { await phone(browser); } catch (e) { ok('phone run completed', false, e.message.split('\n')[0]); }
  try { await desktop(browser); } catch (e) { ok('desktop run completed', false, e.message.split('\n')[0]); }
  await browser.close();
  console.log(results.join('\n'));
  const fails = results.filter(r => r.startsWith('FAIL')).length;
  console.log(`\n${results.length - fails} passed, ${fails} failed`);
  process.exit(fails ? 1 : 0);
})();
