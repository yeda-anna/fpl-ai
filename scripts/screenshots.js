#!/usr/bin/env node
// Before/after screenshots of one view, at phone (390x844) and desktop (1440x900), and a
// quick check of each page while it's open: no console errors, nothing wider than the phone.
//
//   node scripts/screenshots.js --after http://127.0.0.1:8790 [--before http://127.0.0.1:8791]
//        [--view home/squad] [--from '<selector>'] [--focus '<selector>']
//        [--hover '<selector>'] [--open '<selector>'] [--team 0] [--out tests/screenshots/pr]
//
//   --before / --after  base URLs of the two servers (main and the PR branch). --before is optional.
//   --view              the page, as its address: home/squad, players/projections, plan/chips …
//   --from              crop from the top of this element to the bottom of the view; pick one
//                       that exists on both branches. Default: the top of the view.
//   --focus             the element the change is about. Shot on its own on "after"; with --hover
//                       (hover on desktop, tap on phone, 55% across it) and --open (clicked first:
//                       a <summary>, a tab) for the interaction states.
//   --team              0 = the demo team (default, needs no FPL account); any other ID is saved as
//                       the device's team, so the server must be able to load it (live FPL data).
//
// Files: before-phone.png, after-phone.png, before-desktop.png, after-desktop.png and, when
// asked, after-<phone|desktop>-hover.png / -open.png, at 2x. Exits 1 if a page logged console
// errors, overflowed the phone width or never drew the view - so it doubles as a smoke test.
// Playwright comes from tests/node_modules (npm --prefix tests install). If Playwright's own
// browser isn't installed, point PW_CHROMIUM at a Chromium binary.
const fs = require('fs');
const path = require('path');

const args = {};
for (let i = 2; i < process.argv.length; i += 2) args[process.argv[i].replace(/^--/, '')] = process.argv[i + 1];
const ROOT = path.resolve(__dirname, '..');
const view = (args.view || 'home/squad').replace(/^#/, '');
const viewSel = '#v-' + view.replace('/', '-');
const OUT = path.resolve(args.out || path.join(ROOT, 'tests', 'screenshots', 'pr'));
const TEAM = String(args.team == null ? 0 : args.team);
if (!args.after) { console.error('usage: node scripts/screenshots.js --after <url> [--before <url>] [--view tab/sub] …'); process.exit(2); }

let chromium;
try { ({ chromium } = require(path.join(ROOT, 'tests', 'node_modules', 'playwright'))); }
catch (e) { ({ chromium } = require('playwright')); }

const DEVICES = [
  ['phone', { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true }],
  ['desktop', { viewport: { width: 1440, height: 900 } }],
];

async function shoot(browser, label, base, [dev, opts], problems) {
  const ctx = await browser.newContext({ ...opts, deviceScaleFactor: 2, reducedMotion: 'reduce' });
  const page = await ctx.newPage();
  const errs = [];
  page.on('pageerror', e => errs.push(e.message));
  page.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
  await page.addInitScript(team => {
    localStorage.setItem('fplai_intro', '"off"');                         // skip the opening film
    if (team !== '0') localStorage.setItem('fplai_team', JSON.stringify(team));
  }, TEAM);
  const url = base.replace(/\/?$/, '/');
  await page.goto(url, { waitUntil: 'networkidle' });
  if (TEAM === '0') { await page.click('#landDemo'); await page.waitForSelector('#v-home-squad .card', { timeout: 30000 }); }
  await page.evaluate(v => { location.hash = v; }, view);
  const drawn = await page.waitForFunction(s => { const v = document.querySelector(s);
    return v && !v.querySelector('.loading') && v.innerText.trim().length > 40; }, viewSel, { timeout: 60000 }).then(() => true, () => false);
  if (!drawn) problems.push(`${label} ${dev}: ${viewSel} never drew`);
  await page.waitForTimeout(800);
  await page.evaluate(() => document.querySelectorAll('.toast, #toast').forEach(t => t.remove()));   // the demo's note

  const files = [];
  const from = args.from ? await page.$(args.from) : await page.$(viewSel);
  if (!from) problems.push(`${label} ${dev}: --from ${args.from} not found`);
  else {
    const top = await from.evaluate(e => e.getBoundingClientRect().top + scrollY);
    const bottom = await page.$eval(viewSel, e => e.getBoundingClientRect().bottom + scrollY);
    const width = await page.evaluate(() => document.documentElement.clientWidth);
    const y = Math.max(0, top - 12);
    const clip = { x: 0, y, width, height: Math.max(40, Math.min(bottom + 16 - y, 2600)) };
    const f = path.join(OUT, `${label}-${dev}.png`);
    await page.screenshot({ path: f, fullPage: true, clip }); files.push(f);
  }

  if (label === 'after' && args.focus) {
    const el = await page.$(args.focus);
    if (!el) problems.push(`after ${dev}: --focus ${args.focus} not found`);
    else {
      await el.scrollIntoViewIfNeeded();
      if (args.hover) {
        const h = await page.$(args.hover);
        if (!h) problems.push(`after ${dev}: --hover ${args.hover} not found`);
        else {
          const b = await h.boundingBox();
          if (opts.hasTouch) await page.touchscreen.tap(b.x + b.width * 0.55, b.y + b.height / 2);
          else await page.mouse.move(b.x + b.width * 0.55, b.y + b.height / 2);
          await page.waitForTimeout(200);
          const f = path.join(OUT, `after-${dev}-hover.png`); await el.screenshot({ path: f }); files.push(f);
        }
      }
      if (args.open) {
        const o = await page.$(args.open);
        if (!o) problems.push(`after ${dev}: --open ${args.open} not found`);
        else { await o.click(); await page.waitForTimeout(200);
               const f = path.join(OUT, `after-${dev}-open.png`); await el.screenshot({ path: f }); files.push(f); }
      }
    }
  }

  if (dev === 'phone') {
    const over = await page.evaluate(() => [...document.querySelectorAll('#views .view.on *')]
      .filter(e => { const r = e.getBoundingClientRect(); if (!r.width || r.right <= window.innerWidth + 1) return false;
        for (let a = e.parentElement; a && a !== document.body; a = a.parentElement)
          if (/(auto|scroll|hidden)/.test(getComputedStyle(a).overflowX)) return false;
        return true; })
      .slice(0, 3).map(e => e.tagName.toLowerCase() + (typeof e.className === 'string' && e.className ? '.' + e.className.split(' ')[0] : '')));
    if (over.length) problems.push(`${label} phone: wider than 390px: ${over.join(', ')}`);
  }
  if (errs.length) problems.push(`${label} ${dev}: console errors: ${errs.slice(0, 2).join(' | ')}`);
  await ctx.close();
  return files;
}

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const launch = process.env.PW_CHROMIUM ? { executablePath: process.env.PW_CHROMIUM } : {};
  const browser = await chromium.launch(launch);
  const problems = [], files = [];
  for (const [label, base] of [['before', args.before], ['after', args.after]]) {
    if (!base) continue;
    for (const d of DEVICES) files.push(...await shoot(browser, label, base, d, problems));
  }
  await browser.close();
  files.forEach(f => console.log('wrote ' + path.relative(process.cwd(), f)));
  if (problems.length) { problems.forEach(p => console.log('FAIL  ' + p)); process.exit(1); }
  console.log(`OK  ${files.length} screenshots of #${view}, no console errors, fits 390px`);
})().catch(e => { console.error(e); process.exit(1); });
