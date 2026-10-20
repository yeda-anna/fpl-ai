/* Papa Ranjeet — frontend. Plain JS, no build step. Animation lives in motion.js (FX),
   and the Magic UI effects in magic.js (Magic). */
'use strict';

const store = {
  get(k, d){ try{ const v = localStorage.getItem(k); return v==null ? d : JSON.parse(v); }catch(e){ return d; } },
  set(k, v){ try{ localStorage.setItem(k, JSON.stringify(v)); }catch(e){} },
  del(k){ try{ localStorage.removeItem(k); }catch(e){} }
};

const S = {
  teamId: '', teamName: '',
  horizon: 5,
  overrides: store.get('fplai_minutes', {}),   // {playerId: minutes} - your own numbers
  made: store.get('fplai_made', {}),           // {teamId: [[outId, inId], ...]} - transfers made in the FPL app, not public yet
  entry: null, meta: null, loaded: {},
  fresh: true,         // the next read of your team bypasses the server's cache (every page load starts true)
  ready: null,         // the first, fresh read of a saved team; team views wait for it
  lastSeg: {}          // the sub-page you last used in each tab
};

const el  = id => document.getElementById(id);
const POS = {1:'GKP',2:'DEF',3:'MID',4:'FWD'};
const esc = s => String(s==null?'':s).replace(/[&<>"]/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const num = (v,d=2) => (v==null||isNaN(v)) ? '–' : Number(v).toFixed(d);
const sign = (v,d=2) => (v>0?'+':'') + num(v,d);

async function api(path, opts){
  const r = await fetch(path, Object.assign({cache:'no-store'}, opts));   // never a browser-held copy
  if(!r.ok){
    let m; try{ m = (await r.json()).detail; }catch(e){ m = r.statusText; }
    throw new Error(m || ('Request failed ('+r.status+')'));
  }
  return r.json();
}
const post = (path, body) => api(path, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
const ovParam = () => Object.entries(S.overrides).map(([k,v])=>k+':'+v).join(',');
const entryUrl = id => `/api/entry/${id}?horizon=${S.horizon}${ovQuery()}${S.fresh ? '&fresh=1' : ''}`;
/* The demo team, for visitors who don't play FPL: team 0 never exists on FPL, so the
   server answers for a made-up side instead (backend/demo.py). Kept for this tab only. */
const DEMO = '0';
const isDemo = () => S.teamId === DEMO;
const demoFlag = on => { try{ on ? sessionStorage.setItem('fplai_demo', '1') : sessionStorage.removeItem('fplai_demo'); }catch(e){} };
const madeParam = () => (S.made[S.teamId] || []).map(([o,i])=>o+'-'+i).join(',');
const ovQuery = () => { const o = ovParam(), m = madeParam(); return (o ? '&overrides='+encodeURIComponent(o) : '') + (m ? '&made='+m : ''); };
/* Your minute edits and the transfers you've told us about, on a request body. */
const withEdits = b => { const o = ovParam(), m = madeParam(); if(o) b.overrides = o; if(m) b.made = m; return b; };

/* ---------------- house humour ----------------
   British dry wit and Indian dark humour in the waiting and on the landing screen.
   Aimed at the manager's own luck, never at anyone else, and never in errors,
   numbers or anything a manager acts on. */
const QUIPS = {
  loading: [
    'Sharma ji’s son finished this ages ago. Beta, take your time.',
    'Hope is a free transfer. You’ll roll it over and never use it.',
    'Loading like a Bengaluru commute: moving, but not going anywhere.',
    'Chai is brewing. Your rank is not.',
    'Unlike your relatives, the maths will not ask when you’re settling down.',
    'Jugaad is not a transfer strategy. We checked.',
    'Still faster than reading the 47 ‘Good Morning’ forwards in the family group.',
    'Putting the kettle on. The numbers take a minute.',
    'Somewhere a chess engine is warming up. So is this.'
  ],
  welcome: [
    'Your captain will blank. Your relatives will still ask what happened.',
    'Everyone says “tumse na ho payega”. The model says: let’s see the expected points.',
    'Fantasy football: an EMI of hope, repaid in heartbreak, with interest.',
    'This app does the maths. You bring the confidence.',
    'Rank in the millions? Don’t worry, beta. It’s a stable position.'
  ]
};
const lastQuip = {};
function quip(kind){
  const list = QUIPS[kind] || [];
  if(!list.length) return '';
  let i = Math.floor(Math.random()*list.length);
  if(list.length > 1 && i === lastQuip[kind]) i = (i+1) % list.length;   // never the same line twice running
  lastQuip[kind] = i;
  return list[i];
}

/* ---------------- the week's verdict ----------------
   Home → My squad opens with a dark football roast of your last gameweek, chosen
   by how your score compares with the average. It lives in the page head, apart
   from the numbers, and never gives advice. The pick is seeded by team and
   gameweek, so it stays put on a re-render and changes when a new week is scored. */
const SCORE_ROASTS = {
  great: [
    '{pts} points, {diff} above the average. Enjoy it — the board’s full backing usually arrives the week before the sack.',
    '{pts} points. Frame it. By next week this squad goes back to being a loan nobody wants.',
    '{diff} clear of the average. Your mini-league has asked for a doping test.',
    '{pts} points. A proper statement win. Regression to the mean is already on the team bus.',
    '{pts} points. Even a stopped clock does the double once a season.'
  ],
  above: [
    '{pts} points, {diff} above average. A mid-table side that thinks it’s in a title race in October.',
    'Beat the average by {diff}. Not a statement win — a scrappy 1–0 against ten men.',
    '{pts} points. Respectable. The kind of week a pundit forgets before the ad break.',
    '{pts} points. The fans aren’t singing your name, but they’ve stopped singing about you.',
    'Just above average. Somewhere a director of football is calling it “a platform to build on”.'
  ],
  level: [
    'Exactly average: {pts} points of pure, uncut mid-table.',
    'Bang on the average. Nobody will remember this gameweek, least of all you.'
  ],
  below: [
    '{pts} points, {diff} under the average. The vote of confidence has been drafted.',
    '{diff} below average. Somewhere a director of football is quietly googling your replacement.',
    '{pts} points. Not a disaster — just the slow misery of a relegation six-pointer you drew 0–0.',
    '{diff} short of the average. Your captain played like he’s already agreed a free in the summer.',
    '{pts} points. The away end has gone very quiet.'
  ],
  awful: [
    '{pts} points. That’s not a gameweek, it’s an own goal with replays from three angles.',
    '{diff} below the average. The fans started leaving in the 60th minute of your season.',
    '{pts} points. Even your bench has asked to go out on loan.',
    'A shocker. The sack-race bookies have stopped taking bets on you.',
    '{pts} points. Park the bus. Then sell the bus. Then play your Wildcard.'
  ],
  none: [
    'No average yet. Enjoy the last few minutes before the post-match interview.',
    'The average isn’t out. The dressing room has gone very quiet anyway.'
  ],
  fresh: [
    'No games played yet. Unbeaten, undefeated and completely unproven.'
  ],
  demo: [     // the made-up demo team only - a below-average week, every week
    'Gut Feeling FC: {pts} points, {diff} under the average. Picked on vibes, captained on vibes, relegated on vibes.',
    '{pts} points. This squad was built like flat-pack furniture: total confidence, no instructions.',
    '{diff} below the average. Kept the injured star “for the badge”. The badge has a hamstring.',
    '{pts} points. Took a hit, lost the hit, then took another hit to fix the hit.',
    '{diff} under the average. The transfer strategy is a coin toss, and the coin is on loan.'
  ]
};
function scoreRoast(teamId, last, vsAvg){
  const d = vsAvg == null ? null : Math.round(vsAvg);
  const kind = !last ? 'fresh' : d == null ? 'none' : d >= 15 ? 'great' : d > 0 ? 'above' : d === 0 ? 'level' : d > -15 ? 'below' : 'awful';
  const list = isDemo() && (kind === 'below' || kind === 'awful') ? SCORE_ROASTS.demo : SCORE_ROASTS[kind], seed = teamId + '|' + (last ? last.gw + ':' + last.points : '-');
  let h = 0; for(let i=0;i<seed.length;i++) h = (h*31 + seed.charCodeAt(i)) | 0;
  const slots = {pts: last ? last.points : '–', diff: d == null ? '' : Math.abs(d)};
  return list[Math.abs(h) % list.length].replace(/\{(\w+)\}/g, (m,k)=> slots[k] != null ? slots[k] : m);
}

/* A neon ball looping along a path while the numbers come in (pure CSS animation). */
const LOADER = `<svg class="loader" viewBox="0 0 120 40" aria-hidden="true">
  <path class="trk" d="M10 30 C 30 2, 50 2, 60 20 S 90 38, 110 10"/>
  <path class="run" d="M10 30 C 30 2, 50 2, 60 20 S 90 38, 110 10"/>
  <path class="run run2" d="M10 30 C 30 2, 50 2, 60 20 S 90 38, 110 10"/></svg>`;
const BEAM = '<span class="mg-beam" aria-hidden="true"></span>';      // Magic UI Border Beam (CSS)
const loading = t => { const q = quip('loading');
  return `<div class="card">${BEAM}<div class="loading">${LOADER}<span>${esc(t||'Working')}</span></div>${q?`<div class="quip">${esc(q)}</div>`:''}</div>`; };
const errBox  = e => `<div class="err"><b>That didn’t work.</b> ${esc(e.message||e)}</div>`;
const pos  = p => `<span class="pill pos${p}">${POS[p]}</span>`;
const fdr  = f => `<span class="fdr fdr${f}">${f}</span>`;
const flag = p => p.status && p.status!=='a' ? `<span class="dot" title="${esc(p.news||'Flagged')}"></span>` : '';
const tile = (lbl, val, sub, cls='') => `<div class="tile"><div class="lbl">${lbl}</div><div class="val ${cls}">${val}</div><div class="sub">${sub||''}</div></div>`;

function needTeam(){
  if(S.teamId) return null;
  return `<div class="card need-team">
    <div class="mark"><svg aria-hidden="true" viewBox="0 0 32 32"><use href="#logo"/></svg></div>
    <div style="flex:1;min-width:200px"><h3 style="margin-bottom:6px">This one needs your team</h3>
      <p class="sub" style="margin:0">We can read xG, not minds. Add your FPL Team ID and we’ll remember it on this device — projections, players and leagues work without it.</p></div>
    <button class="btn primary" onclick="openLanding()">Add my team</button></div>`;
}
const teamReady = () => S.ready || Promise.resolve(null);

/* ---------------- shared drawing ---------------- */
function spark(vals){
  const mx = Math.max(...vals, 0.1);
  return `<div class="spark">${vals.map(v=>`<i style="height:${Math.max(8, v/mx*100)}%" title="${num(v)}"></i>`).join('')}</div>`;
}

/* ---------------- Season rank chart (Home → My squad) ---------------- */
/* Overall rank by gameweek, drawn by hand as SVG (no chart library). Rank runs on a
   log scale, best at the top: a climb from 2M to 1M is as big a move as 200K to 100K.
   One series, so no legend; the end of the line carries the current rank and the best
   week is marked. Hover, tap or arrow keys show a week; the table below has every value. */
const ordinal = n => { const s = ['th','st','nd','rd'], v = n % 100; return n.toLocaleString() + (s[(v-20)%10] || s[v] || s[0]); };
const compactRank = n => n >= 1e6 ? +(n/1e6).toFixed(n >= 1e7 ? 0 : 2) + 'M'
                       : n >= 1e3 ? +(n/1e3).toFixed(n >= 1e5 ? 0 : 1) + 'K' : String(n);

function rankTicks(lo, hi){
  // Round values inside the range: the finest set of mantissas (× a power of ten) that gives
  // two to five ticks. A range too narrow for any is nearly linear, so use an even round step.
  const within = ms => { const out = [];
    for(let p = Math.floor(Math.log10(lo)); p <= Math.ceil(Math.log10(hi)); p++)
      for(const m of ms){ const v = m * 10 ** p; if(v >= lo && v <= hi) out.push(v); }
    return out; };
  for(const ms of [[1, 1.5, 2, 2.5, 3, 4, 5, 6, 8], [1, 2, 3, 5], [1, 2, 5], [1, 3], [1]]){
    const t = within(ms); if(t.length >= 2 && t.length <= 5) return t;
  }
  const t = within([1]); if(t.length > 5) return t.filter((_, i) => i % 2 === 0);
  const raw = (hi - lo) / 3, mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map(m => m * mag).find(s => s >= raw) || 10 * mag;
  const out = []; for(let v = Math.ceil(lo / step) * step; v <= hi; v += step) out.push(v);
  return out;
}

function seasonCard(season){
  const w = (season && season.weeks) || [];
  if(!w.length) return '';
  const last = season.latest, best = season.best;
  const move = last.climb == null ? '' : last.climb > 0 ? `, up ${last.climb.toLocaleString()} places in GW${last.gw}`
             : last.climb < 0 ? `, down ${(-last.climb).toLocaleString()} places in GW${last.gw}` : `, unchanged in GW${last.gw}`;
  const bestTxt = best.gw === last.gw ? 'Your best rank of the season.' : `Best: ${ordinal(best.rank)} in GW${best.gw}.`;
  return `<div class="card mb season-card">
    <h3>Your season <span class="r">Overall rank, GW${w[0].gw}–${last.gw}</span></h3>
    <p class="season-lead">Now <b>${ordinal(last.rank)}</b>${move}. ${bestTxt}</p>
    ${w.length < 2 ? '<p class="legend">The line starts once a second gameweek has been ranked.</p>' : ''}
    <div class="season-plot" id="seasonPlot" tabindex="0" role="img"
         aria-label="Overall rank by gameweek: ${esc(w.map(x => 'GW' + x.gw + ' ' + x.rank.toLocaleString()).join(', '))}"></div>
    <details class="adv season-table"><summary>Week by week</summary>
      <div class="well"><table><thead><tr><th>GW</th><th class="num">Points</th><th class="num">Overall rank</th><th class="num">Move</th><th class="num">Hits</th></tr></thead><tbody>
      ${w.slice().reverse().map(x => `<tr><td>GW${x.gw}</td><td class="num">${x.points}</td><td class="num">${x.rank.toLocaleString()}</td>
        <td class="num">${x.climb == null ? '–' : x.climb > 0 ? `<span class="up">▲ ${x.climb.toLocaleString()}</span>`
          : x.climb < 0 ? `<span class="down">▼ ${(-x.climb).toLocaleString()}</span>` : '0'}</td>
        <td class="num">${x.hits ? '−' + x.hits : '–'}</td></tr>`).join('')}
      </tbody></table></div></details>
  </div>`;
}

function drawSeason(season){
  const host = el('seasonPlot'); if(!host || !season || !season.weeks.length) return;
  const w = season.weeks, n = w.length, SVG = 'http://www.w3.org/2000/svg';
  const render = () => {
    if(!host.isConnected) return;
    const W = Math.max(260, Math.floor(host.clientWidth)), narrow = W < 460;
    const H = narrow ? 200 : 250, L = narrow ? 44 : 52, R = narrow ? 50 : 76, T = 16, B = 28;
    const ranks = w.map(x => x.rank);
    let lo = Math.min(...ranks) / 1.18, hi = Math.max(...ranks) * 1.18;
    lo = Math.max(1, lo);
    const ly = v => T + (Math.log10(v) - Math.log10(lo)) / (Math.log10(hi) - Math.log10(lo)) * (H - T - B);
    const lx = i => n === 1 ? (L + W - R) / 2 : L + i * (W - L - R) / (n - 1);
    const ticks = rankTicks(lo, hi);
    const every = Math.max(1, Math.ceil(n / (narrow ? 6 : 12)));
    const pts = w.map((x, i) => [lx(i), ly(x.rank)]);
    const bi = w.findIndex(x => x.gw === season.best.gw), li = n - 1;
    const endLbl = narrow ? compactRank(w[li].rank) : w[li].rank.toLocaleString();
    host.innerHTML = `<svg class="season-svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" aria-hidden="true">
      ${ticks.map(v => `<line class="grid" x1="${L}" x2="${W - R}" y1="${ly(v).toFixed(1)}" y2="${ly(v).toFixed(1)}"/>
        <text class="ax" x="${L - 8}" y="${(ly(v) + 4).toFixed(1)}" text-anchor="end">${compactRank(v)}</text>`).join('')}
      ${w.map((x, i) => (i % every === 0 || i === li) && !(i !== li && li - i < every / 2)
        ? `<text class="ax" x="${lx(i).toFixed(1)}" y="${H - 8}" text-anchor="middle">${x.gw}</text>` : '').join('')}
      ${n > 1 ? `<polyline class="season-line" points="${pts.map(p => p[0].toFixed(1) + ',' + p[1].toFixed(1)).join(' ')}"/>` : ''}
      ${bi !== li ? `<circle class="season-best" cx="${pts[bi][0].toFixed(1)}" cy="${pts[bi][1].toFixed(1)}" r="4.5"/>
        <text class="ax lbl" x="${(pts[bi][0] + (bi < n / 2 ? 9 : -9)).toFixed(1)}" y="${(pts[bi][1] + (pts[bi][1] < T + 16 ? 16 : -9)).toFixed(1)}"
              text-anchor="${bi < n / 2 ? 'start' : 'end'}">Best</text>` : ''}
      <circle class="season-dot" cx="${pts[li][0].toFixed(1)}" cy="${pts[li][1].toFixed(1)}" r="4.5"/>
      <text class="end" x="${(pts[li][0] + 10).toFixed(1)}" y="${(pts[li][1] + 4).toFixed(1)}">${endLbl}</text>
      <line class="season-cross" x1="0" x2="0" y1="${T}" y2="${H - B}" style="display:none"/>
      <circle class="season-hover" r="5" style="display:none"/>
      <rect class="season-hit" x="${L - 12}" y="0" width="${W - L - R + 24}" height="${H}"/>
    </svg><div class="season-tip" role="status" aria-live="polite" hidden></div>`;
    const svg = host.firstElementChild, tip = host.querySelector('.season-tip');
    const cross = svg.querySelector('.season-cross'), dot = svg.querySelector('.season-hover');
    const show = i => {
      const x = w[i], [px, py] = pts[i];
      cross.setAttribute('x1', px); cross.setAttribute('x2', px); cross.style.display = '';
      dot.setAttribute('cx', px); dot.setAttribute('cy', py); dot.style.display = '';
      tip.replaceChildren();
      const line = (txt, cls) => { const d = document.createElement('div'); if(cls) d.className = cls; d.textContent = txt; tip.appendChild(d); };
      line('GW' + x.gw, 'tip-gw');
      line(ordinal(x.rank), 'tip-val');
      if(x.climb != null) line(x.climb > 0 ? '▲ up ' + x.climb.toLocaleString() : x.climb < 0 ? '▼ down ' + (-x.climb).toLocaleString() : 'No change',
                               x.climb > 0 ? 'up' : x.climb < 0 ? 'down' : '');
      line(x.points + ' pts' + (x.hits ? ' (−' + x.hits + ' hit)' : ''));
      tip.hidden = false;
      const tw = tip.offsetWidth, left = Math.min(W - tw - 4, Math.max(4, px - tw / 2));
      tip.style.left = left + 'px';
      tip.style.top = Math.max(0, py - tip.offsetHeight - 14) + 'px';
      host.dataset.at = i;
    };
    const hide = () => { cross.style.display = 'none'; dot.style.display = 'none'; tip.hidden = true; delete host.dataset.at; };
    const nearest = ev => { const r = svg.getBoundingClientRect(), x = ev.clientX - r.left;
      let k = 0; pts.forEach((p, i) => { if(Math.abs(p[0] - x) < Math.abs(pts[k][0] - x)) k = i; }); return k; };
    const hit = svg.querySelector('.season-hit');
    hit.addEventListener('pointermove', ev => show(nearest(ev)));
    hit.addEventListener('pointerdown', ev => show(nearest(ev)));
    hit.addEventListener('pointerleave', ev => { if(ev.pointerType === 'mouse') hide(); });
    host.onkeydown = ev => {
      const at = host.dataset.at == null ? li : +host.dataset.at;
      if(ev.key === 'ArrowLeft'){ show(Math.max(0, at - 1)); ev.preventDefault(); }
      else if(ev.key === 'ArrowRight'){ show(Math.min(li, at + 1)); ev.preventDefault(); }
      else if(ev.key === 'Home'){ show(0); ev.preventDefault(); }
      else if(ev.key === 'End'){ show(li); ev.preventDefault(); }
      else if(ev.key === 'Escape') hide();
    };
    host.onfocus = () => { if(host.dataset.at == null) show(li); };
    host.onblur = hide;
  };
  render();
  if(window.ResizeObserver){
    let last = host.clientWidth, t = 0;
    const ro = new ResizeObserver(() => {
      if(!host.isConnected){ ro.disconnect(); return; }
      if(Math.abs(host.clientWidth - last) < 2) return;
      last = host.clientWidth; clearTimeout(t); t = setTimeout(render, 80);
    });
    ro.observe(host);
  }
}

/* ---------------- Shirts & pitch ---------------- */
/* Plain shirt shapes tinted in each club's colours — no crests, sponsors or kit designs. */
const KIT = {ARS:['#DB1F2B','#FFFFFF'], AVL:['#76203F','#9CC3E8'], BHA:['#1A5FBF','#FFFFFF'], BOU:['#C9252C','#1B1B1B'],
  BRE:['#DA2128','#FFFFFF'], CHE:['#1149A3','#FFFFFF'], COV:['#73B7E3','#FFFFFF'], CRY:['#1E4A92','#C42234'],
  EVE:['#1D42A0','#FFFFFF'], FUL:['#F3F5F8','#1B1B1B'], HUL:['#F0A23A','#1B1B1B'], IPS:['#2F5DA9','#FFFFFF'],
  LEE:['#F3F5F8','#1F4590'], LIV:['#C41230','#E9E2CF'], MCI:['#80BBE6','#FFFFFF'], MUN:['#CF2A21','#FFFFFF'],
  NEW:['#1D1D1D','#F3F5F8'], NFO:['#C9232B','#FFFFFF'], SUN:['#D9252F','#FFFFFF'], TOT:['#F3F5F8','#17275E']};
const GK_KIT = ['#E7C83C','#1B4332'];
function shirt(team, isGk){
  const [body, trim] = isGk ? GK_KIT : (KIT[team] || ['#84FAB0','#1B4332']);
  return `<svg class="shirt" viewBox="0 0 64 60" aria-hidden="true">
    <path d="M22 4L11 8.5 1.5 20.5l8.5 8 6-4.2V55.5Q32 59 48 55.5V24.3l6 4.2 8.5-8L53 8.5 42 4Q32 11.5 22 4z" fill="${body}" stroke="rgba(0,0,0,.22)" stroke-width="1"/>
    <path d="M11 8.5L1.5 20.5l8.5 8 6-4.2V14z" fill="${trim}"/><path d="M53 8.5l9.5 12-8.5 8-6-4.2V14z" fill="${trim}"/>
    <path d="M22 4Q32 11.5 42 4l-3-1.2Q32 8 25 2.8z" fill="${trim}"/>
    <path d="M22 4L11 8.5 1.5 20.5l8.5 8 6-4.2V55.5Q32 59 48 55.5V24.3l6 4.2 8.5-8L53 8.5 42 4Q32 11.5 22 4z" fill="url(#shirtShade)"/>
  </svg>`;
}
function pitch(xi, bench, captain, vice, opts){
  opts = opts || {};
  const ins = new Set(opts.ins || []);
  const rows = {1:[],2:[],3:[],4:[]};
  xi.forEach(p => rows[p.position] && rows[p.position].push(p));
  const isC = p => captain && p.id === captain.id, isV = p => vice && p.id === vice.id;
  const open = opts.swap ? 'tapPlayer' : 'openPlayer';      // your own squad: a tap shows who to swap him for
  const tok = p => `<div class="pl-tok" onclick="${open}(${p.id})" title="${esc(p.web_name)} · £${num(p.price,1)}m${opts.swap && owns(p.id) ? ' — tap for transfer ideas' : ''}">
      ${isC(p) ? '<span class="badge c">C</span>' : isV(p) ? '<span class="badge v">V</span>' : ''}
      ${ins.has(p.id) ? '<span class="badge in">IN</span>' : ''}
      ${shirt(p.team_short, p.position === 1)}
      <div class="pl-card"><div class="n">${esc(p.web_name)}</div><div class="o">${esc(p.opp || p.team_short)}</div>
        <div class="x">${num(p.xpts,1)}<small>xPts</small></div></div></div>`;
  const gk = bench.filter(p => p.position === 1), out = bench.filter(p => p.position !== 1);
  const benchHtml = bench.length ? `<div class="bench">
      ${gk.map(p => `<div><div class="slot-lbl">GKP</div>${tok(p)}</div>`).join('')}
      ${out.map((p,i) => `<div><div class="slot-lbl">${i+1}.${POS[p.position]}</div>${tok(p)}</div>`).join('')}</div>` : '';
  return `<div class="pitch-card">${opts.header || ''}
    <div class="turf"><div class="turf-lines"></div><div class="turf-half"></div>
      <div class="turf-plane">${[1,2,3,4].map(q => `<div class="line-row">${rows[q].map(tok).join('')}</div>`).join('')}</div></div>
    ${benchHtml}</div>`;
}

/* ---------------- Home: your squad ---------------- */
async function viewSquad(t){
  const n = needTeam(); if(n){ t.innerHTML = n; return; }
  t.innerHTML = loading('Projecting your gameweek');
  try{
    await teamReady();
    const [e, meta] = await Promise.all([S.entry ? S.entry : api(entryUrl(S.teamId)), S.meta ? S.meta : api('/api/meta')]);
    S.entry = e; S.meta = meta; S.fresh = false;
    const lastGw = meta.events.find(x=>x.id===meta.current_gw) || {};
    const last = e.history.length ? e.history[e.history.length-1] : null;
    const vsAvg = last && lastGw.average!=null ? last.points - lastGw.average : null;
    S.squadSub = scoreRoast(S.teamId, last, vsAvg);
    if(cur.tab === 'home' && cur.seg === 'squad') syncHead(true);
    const av = (e.chips_available||{})[e.next_gw] || [], CH = {wildcard:'WC',freehit:'FH',bboost:'BB','3xc':'TC'};
    t.innerHTML = `${isDemo() ? demoTour(e) : ''}
      <div class="grid g4 mb">
        ${tile('Overall rank', e.entry.overall_rank ? e.entry.overall_rank.toLocaleString() : '–', esc(e.entry.name||''))}
        ${tile('GW'+e.gw+' score', last ? last.points : '–',
               vsAvg==null ? 'Average not out yet' : `<span class="${vsAvg>=0?'up':'down'}">${sign(vsAvg,0)}</span> vs the ${lastGw.average}-point average`)}
        ${tile('Squad value', '£'+num(e.entry.value,1)+'m', '£'+num(e.bank,1)+'m in the bank')}
        ${tile('Free transfers', e.free_transfers, (e.pending_transfers||[]).length
          ? 'Made for GW'+e.next_gw+': '+e.pending_transfers.map(t=>esc((t.out||'?')+' → '+(t.in||'?'))).join(', ')
          : av.length ? 'Chips now: '+av.map(c=>CH[c]).join(' · ') : 'No chips this week')}
      </div>
      ${isDemo() ? '' : madeCard(e)}
      <div class="grid g23 mb">
        <div class="card">
          <h3>Best XI for GW${e.next_gw} <span class="r">${e.formation} · ${num(e.xi_xpts)} xPts</span></h3>
          ${pitch(e.starting_xi, e.bench, e.captain, e.starting_xi.filter(p=>!e.captain||p.id!==e.captain.id).sort((a,b)=>b.xpts-a.xpts)[0], {swap:true})}
          <div class="legend">Captain <b>${e.captain?esc(e.captain.web_name):'–'}</b> adds another ${e.captain?num(e.captain.xpts):'0'}.
            Bench projects ${num(e.bench_xpts)}; G is the reserve keeper, 1–3 the order outfielders come on.
            <b>Tap a player</b> to see who you could swap him for.</div>
          <div class="controls" style="margin-top:14px">
            <button class="btn primary" onclick="go('plan','transfers')">Plan my transfers</button>
            <button class="btn" onclick="go('home','grade')">Grade my squad</button></div>
        </div>
        <div class="card">
          <h3>Your fifteen over ${S.horizon} gameweeks</h3>
          <div class="well"><table><thead><tr>
            <th>Player</th><th></th><th class="num">£</th><th class="num">GW${e.next_gw}</th><th class="num">${S.horizon}GW</th><th>Trend</th>
          </tr></thead><tbody>
          ${e.squad.slice().sort((a,b)=>b.xpts_total-a.xpts_total).map(p=>`<tr onclick="tapPlayer(${p.id})" style="cursor:pointer" title="Tap for transfer ideas">
            <td><span class="nm">${esc(p.web_name)}</span>${flag(p)}<div class="u2">${esc(p.team_short)}</div></td>
            <td>${pos(p.position)}</td><td class="num">${num(p.price,1)}</td>
            <td class="num accent"><b>${num(p.xpts)}</b></td><td class="num">${num(p.xpts_total,1)}</td>
            <td style="width:76px">${spark(p.per_gw.map(g=>g.xpts))}</td></tr>`).join('')}
          </tbody></table></div>
        </div>
      </div>
      ${seasonCard(e.season)}`;
    drawSeason(e.season);
    if(isDemo()){ if(el('demoExit')) el('demoExit').onclick = exitDemo; }
    else wireMade(e);
    if(vsAvg != null && vsAvg >= 15 && !S.celebrated){ S.celebrated = true; FX.burst(innerWidth/2, 180, 120); }
  }catch(err){
    t.innerHTML = errBox(err);
    if(cur.tab === 'home' && cur.seg === 'squad') el('view-sub').textContent = 'Couldn’t read the scoreline right now.';
  }
}

/* The demo's guided tour: what FPL is in one breath, and where each part of the app lives. */
function demoTour(e){
  const stop = (to, label, what) => `<li><button class="tour-go" data-go="${to}">${label}</button><span>${what}</span></li>`;
  return `<div class="card mb demo-tour">
    <h3>Demo team <span class="r">no FPL account needed</span></h3>
    <p class="demo-lead"><b>Fantasy Premier League</b> in one breath: you get £${+e.entry.value}m to pick ${e.squad.length} real footballers, and they score you points every week they play well in real matches. Millions play. Most of them think they’re good at it.</p>
    <p class="demo-lead">This is <b>${esc(e.entry.name)}</b>, a made-up team picked on vibes: the biggest names the money allowed, whoever was left, and an injured star kept “for the badge”. The scores are invented; the players, prices and fixtures are real. Here’s what the app makes of it:</p>
    <ol class="tour">
      ${stop('home/grade', 'Grade', 'marks the squad out of 100 against the best one the same money could buy.')}
      ${stop('plan/transfers', 'Transfers', 'plans the next few weeks at once: who to sell, who to buy, who to captain.')}
      ${stop('plan/chips', 'Chips', 'finds the best week to play each one-off power-up.')}
      ${stop('players/projections', 'Players', 'projects points for every player in the league, fixture by fixture.')}
      ${stop('ask/copilot', 'Ask', 'answers plain questions, like “who should I captain?”')}
    </ol>
    <div class="controls" style="margin-top:14px">
      <button class="btn primary" onclick="openLanding()">Try it with my own team</button>
      <button class="btn" id="demoExit">Leave the demo</button></div></div>`;
}
document.addEventListener('click', ev=>{
  const b = ev.target.closest('.tour-go'); if(!b) return;
  const [tab, seg] = b.dataset.go.split('/'); go(tab, seg);
});

/* Transfers made in the FPL app. FPL keeps a transfer for the coming gameweek private
   until that deadline passes, so the public data we read can't see it: the manager
   tells us here, it's kept on this device, and every team view counts it. */
function madeCard(e){
  const made = S.made[S.teamId] || [], pend = e.pending_transfers || [];
  const row = t => `<li><span class="nm">${esc(t.out||'?')}</span> ${Magic.beamArrow()} <span class="nm">${esc(t.in||'?')}</span>
    ${t.manual ? `<button class="btn sm" data-unmade="${t.out_id}-${t.in_id}" aria-label="Remove ${esc((t.out||'')+' to '+(t.in||''))}">Remove</button>` : '<span class="dim">from FPL</span>'}</li>`;
  const stale = made.filter(([o,i])=>!pend.some(t=>t.manual && t.out_id===o && t.in_id===i)).length;
  return `<div class="card mb made">
    <h3>Transfers made for GW${e.next_gw} <span class="r">${pend.length ? pend.length+' counted' : 'none yet'}</span></h3>
    <div class="legend" style="margin-top:0">Made a transfer in the FPL app? FPL keeps it private until the deadline, so add it here and every view will count it. It’s kept on this device and drops out once the deadline passes.</div>
    ${pend.length ? `<ul class="made-list">${pend.map(row).join('')}</ul>` : ''}
    ${stale ? `<div class="legend">${stale} saved transfer${stale>1?'s':''} no longer fit${stale>1?'':'s'} your squad and ${stale>1?'were':'was'} skipped. <button class="btn sm" id="madeClear">Clear saved</button></div>` : ''}
    <div class="controls made-add">
      <label class="fld">Out<select id="madeOut"><option value="">Player sold…</option>
        ${e.squad.slice().sort((a,b)=>a.position-b.position||a.web_name.localeCompare(b.web_name)).map(p=>`<option value="${p.id}" data-pos="${p.position}">${esc(p.web_name)} · ${POS[p.position]}</option>`).join('')}</select></label>
      <label class="fld">In<select id="madeIn" disabled><option value="">Player bought…</option></select></label>
      <button class="btn primary" id="madeAdd" disabled>Add transfer</button>
    </div></div>`;
}
function wireMade(e){
  const save = list => { if(list.length) S.made[S.teamId] = list; else delete S.made[S.teamId];
    store.set('fplai_made', S.made); invalidate(); rerender(); };
  const mine = () => (S.made[S.teamId] || []).slice();
  document.querySelectorAll('[data-unmade]').forEach(b=>b.onclick = ()=>{
    const [o,i] = b.dataset.unmade.split('-').map(Number);
    save(mine().filter(([a,c])=>!(a===o && c===i)));
  });
  if(el('madeClear')) el('madeClear').onclick = ()=>save([]);
  const out = el('madeOut'), inn = el('madeIn'), add = el('madeAdd');
  if(!out) return;
  const owned = new Set(e.squad.map(p=>p.id));
  out.onchange = async ()=>{
    const opt = out.selectedOptions[0]; add.disabled = true;
    if(!out.value){ inn.disabled = true; inn.innerHTML = '<option value="">Player bought…</option>'; return; }
    inn.disabled = true; inn.innerHTML = '<option value="">Loading…</option>';
    try{
      const d = await api(`/api/players?horizon=${S.horizon}&position=${opt.dataset.pos}&sort=ownership&limit=800`);
      const list = d.players.filter(p=>!owned.has(p.id)).sort((a,b)=>a.web_name.localeCompare(b.web_name));
      inn.innerHTML = '<option value="">Player bought…</option>' + list.map(p=>`<option value="${p.id}">${esc(p.web_name)} · ${esc(p.team_short)} · £${num(p.price,1)}m</option>`).join('');
      inn.disabled = false;
    }catch(err){ inn.innerHTML = '<option value="">Couldn’t load players</option>'; }
  };
  inn.onchange = ()=>{ add.disabled = !(out.value && inn.value); };
  add.onclick = ()=>{ if(out.value && inn.value) save(mine().concat([[+out.value, +inn.value]])); };
}

/* The opponent's recent run, where it matters to this player: attackers care whether the
   other side has been leaking chances lately, defenders and keepers whether it's been blunt. */
function oppForm(f, position){
  const att = position >= 3, d = f.opp_form_defence || 1, a = f.opp_form_attack || 1;
  if(att && d >= 1.08) return ' · <span class="up">opponent leaky lately</span>';
  if(att && d <= 0.92) return ' · <span class="warn">opponent tight lately</span>';
  if(!att && a <= 0.92) return ' · <span class="up">opponent blunt lately</span>';
  if(!att && a >= 1.08) return ' · <span class="warn">opponent firing lately</span>';
  return '';
}

/* ---------------- Home: this week's picks (no team needed) ---------------- */
async function viewPicks(t){
  t.innerHTML = loading('Picking this week’s standouts');
  try{
    const [picks, meta] = await Promise.all([api(`/api/picks?horizon=${S.horizon}`), S.meta ? S.meta : api('/api/meta')]);
    S.meta = meta;
    const lastGw = meta.events.find(x=>x.id===meta.current_gw) || {};
    const list = (rows, right, sub) => `<div class="well"><table><tbody>${rows.map((p,i)=>`
      <tr onclick="openPlayer(${p.id})" style="cursor:pointer">
        <td style="width:20px" class="dim">${i+1}</td>
        <td><span class="nm">${esc(p.web_name)}</span>${flag(p)}<div class="u2">${esc(p.team_short)} · £${num(p.price,1)}m</div></td>
        <td>${pos(p.position)}</td>${right(p)}</tr>`).join('')}</tbody></table></div>${sub?`<div class="legend">${sub}</div>`:''}`;
    t.innerHTML = `
      <div class="grid g4 mb">
        ${tile('GW'+meta.current_gw+' average', lastGw.average ?? '–', 'Highest score: '+(lastGw.highest ?? '–'))}
        ${tile('Most captained', esc(lastGw.most_captained||'–'), 'Most owned: '+esc(lastGw.most_selected||'–'))}
        ${tile('Player of the week', esc(lastGw.top_player||'–'), lastGw.top_player_points!=null ? lastGw.top_player_points+' points' : '')}
        ${tile('Most bought', esc(lastGw.most_transferred_in||'–'), lastGw.transfers_made ? (lastGw.transfers_made/1e6).toFixed(1)+'m transfers made' : '')}
      </div>
      <div class="grid g3 mb">
        <div class="card lift"><h3>Captain picks <span class="r">GW${picks.gw}</span></h3>
          ${list(picks.captains.slice(0,7), p=>`<td class="num accent"><b>${num(p.xpts)}</b></td>`, 'Single-gameweek projection. Doubled if captained.')}</div>
        <div class="card lift"><h3>Differentials <span class="r">under 15% owned</span></h3>
          ${list(picks.differentials.slice(0,7), p=>`<td class="num dim">${num(p.selected_by_percent,1)}%</td><td class="num accent"><b>${num(p.xpts_total,1)}</b></td>`, `Right column: projected points over ${S.horizon} gameweeks.`)}</div>
        <div class="card lift"><h3>Best value <span class="r">points per £m</span></h3>
          ${list(picks.best_value.slice(0,7), p=>`<td class="num accent"><b>${num(p.xpts_total,1)}</b></td>`)}</div>
      </div>
      <div class="card">
        <h3>Dream team for GW${picks.gw} <span class="r">${picks.dream_team.formation} · £${num(picks.dream_team.cost,1)}m · ${num(picks.dream_team.total)} xPts</span></h3>
        ${pitch(picks.dream_team.xi, [], picks.dream_team.captain, null)}
      </div>`;
  }catch(e){ t.innerHTML = errBox(e); }
}

/* ---------------- Expected Points ---------------- */
/* Keyed rows: each player keeps his <tr>, which is updated and moved rather than
   rebuilt, so AutoAnimate can glide the table into a new order when you sort or
   filter. Rows AutoAnimate is still fading out are marked __aa_del; leave them be.
   Past 120 rows ("Show all") the animation steps aside. */
function syncRows(body, list, cells, append){
  const live = Array.prototype.filter.call(body.children, tr=>!('__aa_del' in tr));
  const ctl = FX.auto(body);
  if(ctl){ if((append ? live.length : 0) + list.length > 120) ctl.disable(); else ctl.enable(); }
  if(append){ body.insertAdjacentHTML('beforeend', list.map(p=>`<tr data-pid="${p.id}">${cells(p)}</tr>`).join('')); return; }
  const old = new Map(live.map(tr=>[tr.dataset.pid, tr]));
  const keep = new Set(list.map(p=>String(p.id)));
  live.forEach(tr=>{ if(!keep.has(tr.dataset.pid)) tr.remove(); });
  let prev = null;
  list.forEach(p=>{
    const id = String(p.id), html = cells(p);
    let tr = old.get(id);
    if(!tr){ tr = document.createElement('tr'); tr.dataset.pid = id; }
    if(tr._html !== html){ tr.innerHTML = html; tr._html = html; }
    const at = prev ? prev.nextSibling : body.firstChild;
    if(at !== tr) body.insertBefore(tr, at);
    prev = tr;
  });
}
const XP = { limit: 40, offset: 0, seq: 0 };
async function viewXpts(t){
  const nEdits = Object.keys(S.overrides).length;
  t.innerHTML = `
    <div class="card mb"><div class="controls" style="justify-content:space-between;width:100%">
      <div class="controls">
        <label class="fld">Position<select id="fPos"><option value="">All</option>
          <option value="1">GKP</option><option value="2">DEF</option><option value="3">MID</option><option value="4">FWD</option></select></label>
        <label class="fld">Team<select id="fTeam"><option value="">All</option></select></label>
        <label class="fld">Max £<input id="fPrice" type="number" step="0.5" placeholder="any" style="width:80px"></label>
        <label class="fld">Search<input id="fSearch" placeholder="Player name" style="width:150px"></label>
        <label class="fld">Sort<select id="fSort">
          <option value="xpts_total">xPts, horizon</option><option value="xpts_next">xPts, next GW</option>
          <option value="value">xPts per £m</option><option value="ownership">Ownership</option><option value="p_goal">Chance to score, next GW</option></select></label>
        <label class="fld">Show<select id="fFdr"><option value="xp">xPts</option><option value="goal">Chance to score</option><option value="fdr">Fixtures</option></select></label>
      </div>
      <div class="controls">
        ${nEdits?`<button class="btn sm" id="resetMins">Reset ${nEdits} minute edit${nEdits>1?'s':''}</button>`:''}
      </div>
    </div></div>
    <div id="xpTable">${loading('Projecting every player')}</div>`;

  try{
    S.meta = S.meta || await api('/api/meta');
    S.meta.teams.slice().sort((a,b)=>a.short_name.localeCompare(b.short_name))
      .forEach(tm=>el('fTeam').insertAdjacentHTML('beforeend', `<option value="${tm.id}">${esc(tm.short_name)}</option>`));
  }catch(e){}

  if(el('resetMins')) el('resetMins').onclick = ()=>{ S.overrides = {}; store.set('fplai_minutes', {}); invalidate(); rerender(); };
  XP.offset = 0; XP.limit = 40;
  const run = async (append)=>{
    const q = new URLSearchParams({horizon:S.horizon, sort:el('fSort').value, limit:XP.limit, offset:XP.offset});
    ['fPos:position','fTeam:team','fPrice:max_price','fSearch:search'].forEach(pair=>{
      const [id,key] = pair.split(':'); if(el(id).value) q.set(key, el(id).value);
    });
    const ov = ovParam(); if(ov) q.set('overrides', ov);
    const card = el('xpTable').querySelector('.card.xp');
    if(!append){ if(card) card.classList.add('busy'); else el('xpTable').innerHTML = loading('Projecting'); }   // a table already up stays, dimmed
    const mine = ++XP.seq;              // only the newest request may paint the table
    try{
      const d = await api('/api/players?'+q);
      if(mine !== XP.seq || !el('xpTable')) return;
      const gws = d.players.length ? d.players[0].per_gw.map(g=>g.gw) : [];
      const showFdr = el('fFdr').value === 'fdr', showGoal = el('fFdr').value === 'goal';
      const cells = p => {
        const firstMins = (p.per_gw[0] && p.per_gw[0].fixtures[0]) ? p.per_gw[0].fixtures[0].xmins : 0;
        const edited = S.overrides[p.id] != null;
        return `<td><a href="#" onclick="openPlayer(${p.id});return false" class="nm" style="color:var(--ink)">${esc(p.web_name)}</a>${flag(p)}
              <div class="u2">${esc(p.team_short)} · ${POS[p.position]} · £${num(p.price,1)}m · ${num(p.selected_by_percent,1)}%</div></td>
          ${p.per_gw.map(g=>{
            if(g.blank) return `<td class="num dim">—</td>`;
            if(showFdr) return `<td class="num">${g.fixtures.map(f=>`${fdr(f.fdr)} <span class="u2" style="display:inline">${esc(f.opponent_short)}${f.home?'':'·a'}</span>`).join('<br>')}</td>`;
            if(showGoal){ const pg = g.p_goal || 0;
              return `<td class="num" style="${pg >= .4 ? 'color:var(--accent-deep)' : pg < .1 ? 'color:var(--ink-3);font-weight:600' : ''}">${num(pg*100,0)}%${g.double?'<sup class="accent">2</sup>':''}</td>`; }
            const v = g.xpts, hot = v >= 6 ? 'font-weight:800;color:var(--accent-deep)' : v >= 4.5 ? 'font-weight:700' : '';
            return `<td class="num" title="${esc(g.fixtures.map(f=>f.opponent_short+(f.home?' (H)':' (A)')).join(', '))}" style="${hot}">${num(v,1)}${g.double?'<sup class="accent">2</sup>':''}</td>`;
          }).join('')}
          <td class="num"><span class="mins ${edited?'set':''}" data-pid="${p.id}" title="${edited?'Your number — click to change':'Click to set your own minutes'}">${num(edited?S.overrides[p.id]:firstMins,0)}′ ✎</span></td>
          <td class="num accent"><b>${num(p.xpts_total,1)}</b></td>`;
      };
      const cols = gws.join(',');
      if(!el('xpBody') || el('xpBody').dataset.cols !== cols){        // first draw, or the gameweek columns changed
        el('xpTable').innerHTML = `<div class="card pad-0 xp">
          <h3><span id="xpCount"></span> <span class="r" id="xpAgo"></span></h3>
          <div class="well flush" style="max-height:none"><table><thead><tr>
            <th>Player</th>${gws.map(g=>`<th class="num">GW${g}</th>`).join('')}<th class="num">Mins</th><th class="num">Total</th>
          </tr></thead><tbody id="xpBody" data-cols="${cols}"></tbody></table></div>
          <div style="padding:12px 20px;display:flex;gap:9px;align-items:center;flex-wrap:wrap" id="xpMore"></div></div>`;
      }
      const ago = d.updated ? Math.max(0, Math.round((Date.now()/1000 - d.updated)/60)) : null;
      el('xpCount').textContent = d.count + ' players';
      el('xpAgo').textContent = ago != null ? 'Model rebuilt ' + (ago < 1 ? 'just now' : ago + ' min ago') : '';
      syncRows(el('xpBody'), d.players, cells, append);
      el('xpTable').querySelector('.card.xp').classList.remove('busy');
      const shown = XP.offset + d.players.length;
      el('xpMore').innerHTML = shown < d.count
        ? `<button class="btn sm" id="moreBtn">Show 40 more</button><button class="btn sm" id="allBtn">Show all ${d.count}</button><span class="sub">${shown} of ${d.count}</span>`
        : `<span class="sub">All ${d.count} shown.</span>`;
      if(el('moreBtn')) el('moreBtn').onclick = ()=>{ XP.offset = shown; XP.limit = 40; run(true); };
      if(el('allBtn'))  el('allBtn').onclick  = ()=>{ XP.offset = shown; XP.limit = d.count; run(true); };
    }catch(e){ if(mine === XP.seq && el('xpTable')) el('xpTable').innerHTML = errBox(e); }
  };

  // click a minutes figure to type your own
  el('xpTable').addEventListener('click', ev=>{
    const m = ev.target.closest('.mins'); if(!m || m.querySelector('input')) return;
    const pid = m.dataset.pid, curr = parseInt(m.textContent,10)||0;
    m.innerHTML = `<input type="number" min="0" max="90" value="${curr}">`;
    const inp = m.querySelector('input'); inp.focus(); inp.select();
    const commit = ()=>{
      const v = inp.value.trim();
      if(v === '') delete S.overrides[pid]; else S.overrides[pid] = Math.max(0, Math.min(90, +v));
      store.set('fplai_minutes', S.overrides); invalidate(); rerender();
    };
    inp.addEventListener('keydown', k=>{ if(k.key==='Enter') commit(); if(k.key==='Escape'){ delete S.loaded[cur.tab+'/'+cur.seg]; rerender(); } });
    inp.addEventListener('blur', commit);
  });

  ['fPos','fTeam','fPrice','fSort','fFdr'].forEach(id=>el(id).addEventListener('change', ()=>{ XP.offset=0; XP.limit=40; run(false); }));
  el('fSearch').addEventListener('keyup', ev=>{ if(ev.key==='Enter'){ XP.offset=0; run(false); } });
  run(false);
}

/* ---------------- Player sheet (floats above the page) ---------------- */
window.openPlayer = async function(id){
  const root = el('sheet-root');
  root.innerHTML = `<div class="scrim" id="scrim"><div class="sheet"><div class="loading">Loading player</div></div></div>`;
  const close = ()=>{ root.innerHTML = ''; document.removeEventListener('keydown', esc_); };
  const esc_ = e=>{ if(e.key==='Escape') close(); };
  document.addEventListener('keydown', esc_);
  el('scrim').addEventListener('click', e=>{ if(e.target.id==='scrim') close(); });
  try{
    const ov = S.overrides[id];
    const p = await api(`/api/player/${id}?horizon=${S.horizon}${ov!=null?'&minutes='+ov:''}`);
    const b = {};
    p.per_gw.forEach(g=>g.fixtures.forEach(f=>{ for(const k in f.breakdown) b[k]=(b[k]||0)+f.breakdown[k]; }));
    const mm = p.minutes_model;
    root.querySelector('.sheet').innerHTML = `
      <button class="btn sm x" id="closeSheet">Close ✕</button>
      <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px">
        ${pos(p.position)}<h2 style="font-size:24px">${esc(p.web_name)}</h2>
        <span class="sub">${esc(p.team_short)} · £${num(p.price,1)}m · ${num(p.selected_by_percent,1)}% owned</span>
        ${mm.returning?'<span class="tag y">Returning from injury</span>':''}
        ${ov!=null?`<span class="tag">Your minutes: ${ov}′</span>`:''}
      </div>
      ${owns(p.id) ? `<div class="controls" style="margin:-4px 0 16px"><button class="btn primary" id="playerSwap">Who could replace ${esc(p.web_name)}?</button></div>` : ''}
      ${p.news?`<div class="note">${esc(p.news)}</div>`:''}
      <div class="grid g4 mb">
        ${tile('Next GW', num(p.xpts_next), 'FPL’s own estimate: '+num(p.fpl_ep_next))}
        ${tile(S.horizon+' gameweeks', num(p.xpts_total,1), num(p.xpts_total/S.horizon)+' a week')}
        ${tile('Expected minutes', num(mm.xmins,0)+'′', 'Start chance '+num(mm.p_start*100,0)+'% · '+(p.chance_next!=null?p.chance_next:100)+'% fit to play')}
        ${tile('Minutes when starting', num(mm.starter_minutes,0)+'′', mm.recent_trend==null?'':'Recent vs season: '+sign(mm.recent_trend,0)+'′')}
      </div>
      <div class="grid g3">
        <div class="card"><h3>Fixtures</h3><div class="well"><table><tbody>
          ${p.per_gw.map(g=>`<tr><td class="dim">GW${g.gw}</td>
            <td>${g.fixtures.map(f=>`${fdr(f.fdr)} ${esc(f.opponent_short)} <span class="u2" style="display:inline">${f.home?'home':'away'} · ${num(f.xmins,0)}′ · ${num(f.p_goal*100,0)}% to score${oppForm(f, p.position)}</span>`).join('<br>')||'<span class="dim">No fixture</span>'}</td>
            <td class="num accent"><b>${num(g.xpts)}</b></td></tr>`).join('')}
        </tbody></table></div></div>
        <div class="card"><h3>Where the points come from</h3>
          ${Object.entries(b).sort((x,y)=>Math.abs(y[1])-Math.abs(x[1])).map(([k,v])=>`
            <div class="kv"><span>${k.replace(/_/g,' ')}</span><span class="${v<0?'down':''}">${num(v)}</span></div>`).join('')}
        </div>
        <div class="card"><h3>Underlying rates <span class="r">per 90</span></h3>
          <div class="kv"><span>xG</span><span>${num(p.rates.xg90,3)}</span></div>
          <div class="kv"><span>xA</span><span>${num(p.rates.xa90,3)}</span></div>
          <div class="kv"><span>Defensive actions</span><span>${num(p.rates.dc90,1)}</span></div>
          <div class="kv"><span>Bonus points system</span><span>${num(p.rates.bps90,1)}</span></div>
          <div class="kv"><span>Season points</span><span>${p.total_points}</span></div>
          <div class="kv"><span>Minutes played</span><span>${p.minutes}</span></div>
          <div class="kv"><span>Goals · assists</span><span>${p.season.goals} · ${p.season.assists}</span></div>
          <div class="kv"><span>ICT index</span><span>${esc(p.season.ict_index)}</span></div>
        </div>
      </div>`;
    el('closeSheet').onclick = close;
    if(el('playerSwap')) el('playerSwap').onclick = ()=>{ close(); openSwap(p.id); };
  }catch(e){ root.querySelector('.sheet').innerHTML = errBox(e); }
};

/* ---------------- Swap sheet: who to bring in for one of your players ---------------- */
/* a player in the loaded team's current squad: tapping him anywhere offers transfer ideas */
const owns = id => S.teamId != null && !!(S.entry && S.entry.squad && S.entry.squad.some(p=>p.id===id));
window.tapPlayer = id => owns(id) ? openSwap(id) : openPlayer(id);
const SW = { seq:0 };
window.openSwap = async function(id){
  const root = el('sheet-root'), mine = ++SW.seq;
  root.innerHTML = `<div class="scrim" id="scrim"><div class="sheet"><div class="loading">Looking for a better option</div></div></div>`;
  const close = ()=>{ root.innerHTML = ''; document.removeEventListener('keydown', esc_); };
  const esc_ = e=>{ if(e.key==='Escape') close(); };
  document.addEventListener('keydown', esc_);
  el('scrim').addEventListener('click', e=>{ if(e.target.id==='scrim') close(); });
  try{
    const d = await api(`/api/entry/${S.teamId}/swaps/${id}?horizon=${S.horizon}${ovQuery()}`);
    if(mine !== SW.seq) return;                                   // a later click took over the sheet
    const me = d.player, best = d.options[0], H = d.horizon;
    const verdict = d.keep
      ? `<div class="note swap-verdict"><b>Keep ${esc(me.web_name)}.</b> ${d.options.length
          ? `The best swap you can afford, ${esc(best.web_name)}, adds only ${sign(best.gain_total,1)} over ${H} gameweeks${d.hit ? ' and costs a 4-point hit' : ''}.`
          : 'Nobody you can afford at his position beats him.'}</div>`
      : `<div class="note swap-verdict"><b>Best swap: ${esc(me.web_name)} → ${esc(best.web_name)}.</b>
          ${sign(best.gain_total,1)} xPts over ${H} gameweek${H>1?'s':''}${d.hit ? `, ${sign(best.net_total,1)} after a ${num(d.hit,0)}-point hit (no free transfer left)` : ', and it uses a free transfer'}.</div>`;
    const row = (o, i) => `<tr onclick="openPlayer(${o.id})" style="cursor:pointer">
        <td><span class="rk">${i+1}</span><span class="nm">${esc(o.web_name)}</span>${flag(o)}<div class="u2">${esc(o.team_short)} · ${esc(o.opp)}${o.chance_next<100 ? ' · '+o.chance_next+'% fit' : ''}</div></td>
        <td class="num">${num(o.price,1)}<div class="u2">£${num(o.bank_after,1)}m left</div></td>
        <td class="num ${o.gain_next>=0?'up':'down'}">${sign(o.gain_next,1)}</td>
        <td class="num ${o.gain_total>=0?'up':'down'}"><b>${sign(o.gain_total,1)}</b></td>
        <td class="num accent"><b>${num(o.xpts,1)}</b></td></tr>`;
    root.querySelector('.sheet').innerHTML = `
      <button class="btn sm x" id="closeSheet">Close ✕</button>
      <div style="display:flex;align-items:center;gap:12px;margin-bottom:6px;flex-wrap:wrap">
        ${pos(me.position)}<h2 style="font-size:24px">Swap ${esc(me.web_name)}</h2>
        <span class="sub">${esc(me.team_short)} · sells for £${num(me.sells_for,1)}m</span>
      </div>
      <p class="menu-sub">Your top ${d.options.length>1 ? d.options.length+' ' : ''}${POS[me.position]} swap${d.options.length>1?'s':''} with £${num(d.budget,1)}m to spend, ranked by extra points over the next ${H} gameweek${H>1?'s':''}.</p>
      ${verdict}
      ${d.options.length ? `<div class="card mb"><div class="well"><table><thead><tr>
          <th>Bring in</th><th class="num">£</th><th class="num">GW${d.next_gw}</th><th class="num">${H}GW</th><th class="num">xPts</th>
        </tr></thead><tbody>${d.options.map(row).join('')}</tbody></table></div></div>` : ''}
      <div class="legend">Columns GW${d.next_gw} and ${H}GW are the extra points over ${esc(me.web_name)} (${num(me.xpts,1)} next gameweek, ${num(me.xpts_total,1)} over ${H}).
        Only players who fit your budget and the three-a-club limit, and are likely to play${d.passed_over ? ` (${d.passed_over} doubtful ${d.passed_over>1?'players are':'player is'} left out)` : ''}.
        ${d.free_transfers ? `You have ${d.free_transfers} free transfer${d.free_transfers>1?'s':''}.` : 'You have no free transfer, so a swap costs 4 points.'}</div>
      <div class="controls" style="margin-top:14px">
        <button class="btn primary" id="swapPlan">Plan my transfers</button>
        <button class="btn" id="swapMe">About ${esc(me.web_name)}</button></div>`;
    el('closeSheet').onclick = close;
    el('swapPlan').onclick = ()=>{ close(); go('plan','transfers'); };
    el('swapMe').onclick = ()=>{ close(); openPlayer(me.id); };
  }catch(e){ if(mine === SW.seq) root.querySelector('.sheet').innerHTML = `<button class="btn sm x" id="closeSheet">Close ✕</button>${errBox(e)}`; if(el('closeSheet')) el('closeSheet').onclick = close; }
};

/* ---------------- Solver workspace ---------------- */
const SV = { key:null, r:null, path:0, gw:0 };
async function viewSolver(t){
  const n = needTeam(); if(n){ t.innerHTML = n; return; }
  await teamReady();
  const hOpts = [1,3,5,6,8,10].map(h=>`<option value="${h}" ${h===S.horizon?'selected':''}>${h} GW</option>`).join('');
  t.innerHTML = `<div class="ws">
    <div class="ws-cmd">
      <div class="ws-controls">
        <select id="sPaths" title="How many alternative plans"><option value="1">1 Path</option><option value="2">2 Paths</option><option value="3" selected>3 Paths</option></select>
        <select id="sH" title="Planning horizon">${hOpts}</select>
        <select id="sHits" title="Hits allowed"><option value="0">No hits</option><option value="1" selected>≤ 1 hit</option><option value="2">≤ 2 hits</option><option value="3">≤ 3 hits</option></select>
        <details class="adv" id="adv"><summary>Advanced settings</summary><div class="adv-body">
          <label class="fld">Wildcard in<select id="sWC"><option value="">Not this window</option></select></label>
          <label class="fld">Free Hit in<select id="sFH"><option value="">Not this window</option></select></label>
          <label class="fld">Free transfers<input id="sFT" type="number" min="1" max="5" placeholder="Auto from your history"></label>
          <label class="fld">Buy or captain only if<select id="sChance">
            <option value="100">Fully fit (100%)</option><option value="75" selected>75%+ likely to play</option>
            <option value="50">50%+ likely to play</option><option value="0">Anyone, flags or not</option></select></label>
          <div class="sub">${Object.keys(S.overrides).length ? 'Using your '+Object.keys(S.overrides).length+' minute edit(s) from Expected Points.' : 'Edit any player’s minutes in Expected Points and the solver will use them.'}</div>
        </div></details>
      </div>
      <button class="cta mg-shimmer" id="runSolve"><span class="mg-spark" aria-hidden="true"><span></span></span><svg viewBox="0 0 24 24" fill="currentColor"><path d="M7 4.5v15l12.5-7.5z"/></svg><span class="lbl">Suggest transfers</span></button>
    </div>
    <div class="ws-left" id="svLeft"><div class="skel" style="height:86px;margin-bottom:16px"></div><div class="skel" style="height:640px;border-radius:24px"></div></div>
    <div class="ws-res" id="svRight"><div class="skel" style="height:70px;margin:22px 0 18px"></div><div class="skel" style="height:96px;margin-bottom:12px"></div><div class="skel" style="height:300px"></div></div>
  </div>`;

  let e;
  try{
    e = S.entry || await api(entryUrl(S.teamId)); S.entry = e; S.fresh = false;
    for(let i=0;i<S.horizon;i++){
      const g = e.next_gw+i, o = `<option value="${g}">GW${g}</option>`, av = (e.chips_available||{})[g] || [];
      if(av.includes('wildcard')) el('sWC').insertAdjacentHTML('beforeend', o);
      if(av.includes('freehit'))  el('sFH').insertAdjacentHTML('beforeend', o);
    }
  }catch(err){ el('svRight').innerHTML = errBox(err); el('svLeft').innerHTML=''; return; }

  const markAdv = ()=> el('adv').dataset.active = (el('sWC').value||el('sFH').value||el('sFT').value||el('sChance').value !== '75') ? '1' : '0';
  ['sWC','sFH','sFT','sChance'].forEach(id=>el(id).addEventListener('change', markAdv));
  el('sH').addEventListener('change', ()=>{ S.horizon = +el('sH').value; el('horizon').value = S.horizon; invalidate(); rerender(); });

  const run = async ()=>{
    const body = {team_id:+S.teamId, horizon:S.horizon, max_hits:+el('sHits').value, paths:+el('sPaths').value};
    if(el('sWC').value) body.wildcard_gw = +el('sWC').value;
    if(el('sFH').value) body.free_hit_gw = +el('sFH').value;
    if(el('sFT').value) body.free_transfers = +el('sFT').value;
    body.min_chance = +el('sChance').value;
    withEdits(body);
    const key = JSON.stringify(body);
    el('adv').open = false;
    if(SV.key === key && SV.r){ draw(); return; }
    const btn = el('runSolve');
    btn.disabled = true; btn.classList.add('busy');        // the shimmer races while the solver works
    btn.querySelector('.lbl').textContent = (Math.random() < .5 ? 'Putting the kettle on' : 'Chai on the stove')+' — optimising '+S.horizon+' gameweeks…';
    el('svLeft').innerHTML = `<div class="skel" style="height:86px;margin-bottom:16px"></div><div class="skel" style="height:640px;border-radius:24px"></div>`;
    el('svRight').innerHTML = `<div class="skel" style="height:70px;margin:22px 0 18px"></div><div class="skel" style="height:96px;margin-bottom:12px"></div><div class="skel" style="height:300px"></div>`;
    try{
      SV.r = await post('/api/solve', body); SV.key = key; SV.path = 0; SV.gw = 0;
      draw();
      const best = SV.r.paths[0];
      if(best && best.gain_vs_nothing > 0.5){ const b = el('runSolve').getBoundingClientRect(); FX.burst(b.left + b.width/2, b.top - 6, 55); }   // burst from the button's top edge, clear of its label
    }catch(err){ el('svRight').innerHTML = errBox(err); el('svLeft').innerHTML = ''; }
    btn.disabled = false; btn.classList.remove('busy');
    btn.querySelector('.lbl').textContent = 'Suggest transfers';
  };

  const CHIPS = {Wildcard:'WC', 'Free Hit':'FH'};

  const drawLeft = ()=>{
    const r = SV.r, p = r.paths[SV.path], g = p.gameweeks[SV.gw], best = r.paths[0].total_xpts;
    const header = `<div class="pitch-top">
        <div class="gw-nav"><button id="gwPrev" ${SV.gw===0?'disabled':''} aria-label="Previous gameweek">‹</button>
          <span>GW${g.gw}</span><button id="gwNext" ${SV.gw===p.gameweeks.length-1?'disabled':''} aria-label="Next gameweek">›</button></div>
        <div class="gw-score">${num(g.xpts,1)}</div>
        <div class="gw-meta"><span>£${num(g.bank,1)}m</span><span class="ft">${g.free_transfers} FT</span>
          ${g.hits?`<span class="hit">−${g.hit_cost}</span>`:''}${g.chip?`<span class="chip">${CHIPS[g.chip]||g.chip}</span>`:''}</div></div>`;
    el('svLeft').innerHTML = `
      <div class="paths"><div class="lbl">Plans</div>
        ${r.paths.map((x,i)=>`<button class="path ${i===SV.path?'on':''}" data-k="${i}">${i===SV.path?'<span class="mg-beam" aria-hidden="true" style="--from:var(--on-accent);--to:var(--purple);--dur:5s"></span>':''}
          <div class="pl">${x.label}</div><div class="pv">${num(x.total_xpts,1)}</div>
          <div class="ps">${i===0?'best found':(Math.abs(x.total_xpts-best)<0.05?'level':sign(x.total_xpts-best,1))} · ${x.total_hits?'−'+(x.total_hits*4):'no hits'}</div></button>`).join('')}
      </div>
      ${pitch(g.starting_xi, g.bench, g.captain, g.vice_captain, {header, ins: g.transfers_in.map(x=>x.id), swap:true})}`;
    el('gwPrev').onclick = ()=>{ SV.gw = Math.max(0, SV.gw-1); draw(); };
    el('gwNext').onclick = ()=>{ SV.gw = Math.min(p.gameweeks.length-1, SV.gw+1); draw(); };
    el('svLeft').querySelector('.paths').addEventListener('click', ev=>{
      const b = ev.target.closest('.path'); if(!b) return; SV.path = +b.dataset.k; SV.gw = Math.min(SV.gw, r.paths[SV.path].gameweeks.length-1); draw();
    });
  };
  const drawRight = ()=>{
    const r = SV.r, p = r.paths[SV.path];
    el('svRight').innerHTML = `
      <div class="stats-row">
        <div><div class="stat-k">Plan xPts</div><div class="stat-v">${num(p.total_xpts,1)}${p.total_hits?`<small class="down">Hits −${p.total_hits*4}</small>`:'<small>No hits</small>'}</div></div>
        <div><div class="stat-k">vs no transfers</div><div class="stat-v">${sign(p.gain_vs_nothing,1)}</div></div>
        <div><div class="stat-k">Template rating</div><div class="stat-v">${p.template_rating}<small>/100</small></div></div>
      </div>
      <div class="gw-strip">${p.gameweeks.map((g,i)=>`<button class="gw-c ${i===SV.gw?'on':''}" data-i="${i}">
        <div class="g">GW${g.gw}</div><div class="v">${num(g.xpts,1)}</div>
        <div class="h ${g.chip?'chip':''}">${g.chip?(CHIPS[g.chip]||g.chip):g.hits?'−'+g.hit_cost:''}</div></button>`).join('')}</div>
      <div class="card" style="padding:8px 12px"><div class="timeline">
        ${p.gameweeks.map((g,i)=>`<div class="tl-row ${i===SV.gw?'on':''}" data-i="${i}">
          <div class="tl-gw">GW${g.gw}${g.hits?`<div><span class="tag r">−${g.hit_cost} hit</span></div>`:''}${g.chip?`<div><span class="tag">${g.chip}</span></div>`:''}</div>
          <div class="tl-moves">${g.transfers_in.length ? g.transfers_in.map((pin,k)=>{ const po = g.transfers_out[k];
              return `<div class="tl-move"><span class="o">${po?esc(po.web_name):'–'}</span>${Magic.beamArrow()}<span class="i">${esc(pin.web_name)}</span></div>`; }).join('')
            : '<div class="tl-roll">Roll</div>'}</div></div>`).join('')}
      </div></div>
      <div class="legend">Captain ${esc(p.gameweeks[SV.gw].captain?p.gameweeks[SV.gw].captain.web_name:'–')}, vice ${esc(p.gameweeks[SV.gw].vice_captain?p.gameweeks[SV.gw].vice_captain.web_name:'–')} in GW${p.gameweeks[SV.gw].gw}.
        Template rating compares your planned XI’s ownership with the eleven most-owned players: 100 is pure template, low is differential.
        Plans are within 0.5% of the best possible; ${r.pool_size} players searched.
        ${r.min_chance ? `Nobody under ${r.min_chance}% to play is bought or captained in GW${p.gameweeks[0].gw}${(r.passed_over||[]).length ? ' — left out: '+r.passed_over.map(x=>esc(x.web_name)+' ('+x.chance_next+'%)').join(', ') : ''}.` : 'Flagged players can be bought and captained.'}</div>`;
    const pick = ev=>{ const x = ev.target.closest('[data-i]'); if(!x) return; SV.gw = +x.dataset.i; draw(); };
    el('svRight').querySelector('.gw-strip').addEventListener('click', pick);
    el('svRight').querySelector('.timeline').addEventListener('click', pick);
  };
  const draw = ()=>{ drawLeft(); drawRight(); };

  el('runSolve').onclick = ()=>{ SV.key = null; run(); };
  run();
}

/* ---------------- Chips ---------------- */
const CHIP = {WC:'Wildcard', FH:'Free Hit', BB:'Bench Boost', TC:'Triple Captain'};
async function viewChips(t){
  const n = needTeam(); if(n){ t.innerHTML = n; return; }
  await teamReady();
  t.innerHTML = loading('Scoring every chip in every gameweek — about half a minute, so long enough to brew');
  try{
    const body = withEdits({team_id:+S.teamId, horizon:S.horizon});
    const r = await post('/api/chips', body);
    const top = r.best_plans[0];
    t.innerHTML = `
      ${top?`<div class="grid g4 mb">${top.picks.map(c=>tile(CHIP[c.chip], 'GW'+c.gw, `<span class="up">${sign(c.gain,1)} xPts</span>`)).join('')}</div>`:''}
      <div class="card mb"><h3>Best chip plans <span class="r">next ${S.horizon} gameweeks</span></h3>
        ${r.best_plans.slice(0,5).map((p,i)=>`<div class="plan">
          <div class="hd"><div class="gw">Plan ${i+1}</div><div class="sub"><b class="up">${sign(p.total_gain,1)} xPts</b> over playing nothing</div></div>
          ${p.picks.map(c=>`<div class="mv"><span class="tag">${CHIP[c.chip]}</span><b>GW${c.gw}</b>
            <span class="up">${sign(c.gain,1)}</span><span class="sub">${esc(c.detail)}</span></div>`).join('')}
        </div>`).join('') || '<div class="sub">Every chip has been played.</div>'}
        ${r.chips_used.length?`<div class="legend">Already played: ${r.chips_used.map(esc).join(', ')}.</div>`:''}
      </div>
      <div class="grid g2">
        ${Object.entries(r.options).filter(([k,v])=>v.length).map(([k,v])=>{ const mx = Math.max(...v.map(x=>x.gain), 0.1); return `
          <div class="card lift"><h3>${CHIP[k]} <span class="r">by gameweek</span></h3>
            <div class="well"><table><tbody>${v.slice().sort((a,b)=>a.gw-b.gw).map(o=>`<tr>
              <td style="width:52px"><b>GW${o.gw}</b></td>
              <td style="width:120px"><div class="meter"><i style="width:${Math.max(3, Math.min(100, o.gain/mx*100))}%"></i></div></td>
              <td class="num ${o.gain>0?'up':'down'}"><b>${sign(o.gain,1)}</b></td>
              <td class="sub">${esc(o.detail)}</td></tr>`).join('')}</tbody></table></div></div>`; }).join('')}
      </div>`;
  }catch(e){ t.innerHTML = errBox(e); }
}

/* ---------------- Copilot ---------------- */
const ASK = ['Who should I captain this week?','Is a hit worth it?','What transfer should I make?',
             'When should I play my chips?','Who are the best differentials?','What should my starting XI be?',
             'Who is rising in price tonight?','Is my team any good?'];
async function viewCopilot(t){
  t.innerHTML = `
    <div class="card mb">
      <div class="ask"><input id="q" placeholder="Ask anything — captaincy, hits, transfers, chips, line-ups, prices…" autocomplete="off">
        <button class="btn primary" id="askBtn">Ask</button></div>
      <div class="chipset">${ASK.map(a=>`<button data-q="${esc(a)}">${esc(a)}</button>`).join('')}</div>
      <div class="legend">Answers are read straight off the projection model and the solver, so every claim has a number behind it.
        ${S.teamId?'Answering for '+(isDemo()?'the demo team, ':'team ')+'<b>'+esc(S.teamName||S.teamId)+'</b>.':'Add a Team ID for answers about your own squad.'}</div>
    </div>
    <div id="ans" class="qa-log" aria-live="polite"></div>`;
  /* The log: every answer is an entry, newest on top. AutoAnimate slides
     the older ones down; they fold to the question and the answer (tap to unfold).
     The reasons under a new answer drop in one by one (Magic UI Animated List). */
  const log = el('ans'), entries = () => Array.prototype.filter.call(log.children, x=>!('__aa_del' in x));
  FX.auto(log);
  const ask = async q=>{
    if(!q) return; el('q').value = q;
    entries().forEach(x=>x.classList.add('old'));
    const n = ++CP.n, when = new Date().toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'});
    const entry = document.createElement('article');
    entry.className = 'qa';
    entry.innerHTML = `<div class="qa-h"><span class="qa-n">Log ${String(n).padStart(3, '0')}</span><span class="qa-q">${esc(q)}</span><span>${esc(when)}</span></div>
      <div class="qa-body"><div class="loading">${LOADER}<span>Working it out</span></div></div>`;
    log.insertBefore(entry, log.firstChild);
    entries().slice(5).forEach(x=>x.remove());          // keep the last five
    const body = entry.querySelector('.qa-body');
    try{
      const b = {question:q, horizon:S.horizon}; if(S.teamId) b.team_id = +S.teamId;
      withEdits(b);
      const r = await post('/api/copilot', b);
      const needsTeam = !r.has_team && ['hit','transfer','rate','chip','bench'].includes(r.intent);
      body.innerHTML = `<div class="grid g23">
        <div><div class="bubble">${esc(r.answer)}</div>
          <div class="qa-extra">
          ${r.points.length?`<div class="card qa-why" style="margin-top:14px"><h3>Why</h3>${r.points.map(p=>`<div class="note">${esc(p)}</div>`).join('')}</div>`:''}
          ${needsTeam?'<div class="note" style="margin-top:12px">Load your Team ID to get this answer for your own squad.</div>':''}</div></div>
        <div class="qa-extra">${r.table?`<div class="card"><h3>${esc(r.table.title)}</h3><div class="well"><table>
            <thead><tr>${r.table.columns.map((c,i)=>`<th class="${i>1?'num':''}">${esc(c)}</th>`).join('')}</tr></thead>
            <tbody>${r.table.rows.map(row=>`<tr>${row.map((c,i)=>`<td class="${i>1?'num':''}">${esc(c)}</td>`).join('')}</tr>`).join('')}</tbody></table></div></div>`:''}
          <div class="legend">Read as a question about: <span class="tag">${esc(r.intent)}</span></div></div></div>`;
      FX.listIn(body.querySelectorAll('.qa-why .note'));
    }catch(e){ body.innerHTML = errBox(e); }
  };
  el('askBtn').onclick = ()=>ask(el('q').value.trim());
  el('q').addEventListener('keydown', e=>{ if(e.key==='Enter') ask(el('q').value.trim()); });
  t.querySelector('.chipset').addEventListener('click', e=>{ const b = e.target.closest('button'); if(b) ask(b.dataset.q); });
  log.addEventListener('click', e=>{ const x = e.target.closest('.qa.old'); if(x) x.classList.remove('old'); });
}
const CP = { n: 0 };

/* ---------------- Rate my team ---------------- */
async function viewRate(t){
  const n = needTeam(); if(n){ t.innerHTML = n; return; }
  await teamReady();
  t.innerHTML = loading('Grading your squad');
  try{
    const r = await api(`/api/rate/${S.teamId}?horizon=${S.horizon}${ovQuery()}`);
    const LBL = {projection:'Projected points',structure:'Line-up strength',bench:'Bench cover',fitness:'Fitness',value:'Value for money'};
    t.innerHTML = `
      <div class="grid g3 mb">
        <div class="card" style="text-align:center;padding:26px 20px">
          <h3 style="justify-content:center">${esc(r.entry.name||'Your team')}</h3>
          <div class="grade-ring"><svg viewBox="0 0 120 120" aria-hidden="true"><defs><linearGradient id="ringGrad" x1="0" y1="0" x2="1" y2="1"><stop offset="0" style="stop-color:var(--ring-a)"/><stop offset="1" style="stop-color:var(--ring-b)"/></linearGradient></defs>
            <circle class="trk" cx="60" cy="60" r="52"/><circle class="arc" cx="60" cy="60" r="52" pathLength="100" style="--p:${Math.max(2,Math.min(100,r.overall))}"/></svg>
            <div class="grade">${esc(r.grade)}</div></div>
          <div class="cu" style="font-size:30px;font-weight:700;letter-spacing:-.03em;margin-top:8px">${num(r.overall,0)}<span class="dim" style="font-size:16px"> / 100</span></div>
          <div class="sub">Rank ${r.entry.overall_rank?r.entry.overall_rank.toLocaleString():'–'}</div>
        </div>
        <div class="card"><h3>How the score is built</h3>
          ${Object.entries(r.scores).map(([k,v])=>`<div style="margin-bottom:12px">
            <div class="kv" style="border:0;padding:0"><span>${LBL[k]||k}</span><span>${num(v,0)}</span></div>
            <div class="meter"><i style="width:${Math.max(2,Math.min(100,v))}%"></i></div></div>`).join('')}
        </div>
        <div class="card"><h3>Key numbers</h3>
          <div class="kv"><span>Squad xPts (${S.horizon} GW)</span><span>${num(r.squad_xpts,1)}</span></div>
          <div class="kv"><span>Strong-squad benchmark</span><span>${num(r.benchmark_xpts,1)}</span></div>
          <div class="kv"><span>Efficiency</span><span>${num(r.efficiency,0)}%</span></div>
          <div class="kv"><span>Best formation</span><span>${esc(r.formation)}</span></div>
          <div class="kv"><span>XI / bench, next GW</span><span>${num(r.xi_xpts,1)} / ${num(r.bench_xpts,1)}</span></div>
          <div class="kv"><span>Value incl. bank</span><span>£${num(r.squad_value,1)}m</span></div>
        </div>
      </div>
      <div class="grid g2">
        <div class="card"><h3>Fix these first</h3><div id="rateNotes">${r.notes.map(x=>`<div class="note">${esc(x)}</div>`).join('')}</div></div>
        <div class="card"><h3>Moves that raise the score</h3>
          <div class="well"><table><thead><tr><th>Out</th><th></th><th>In</th><th class="num">Gain</th></tr></thead><tbody>
          ${r.top_upgrades.map(u=>`<tr>
            <td><span class="down nm">${esc(u.out.web_name)}</span><div class="u2">${esc(u.out.team_short)} · £${num(u.out.price,1)}m · ${num(u.out.xpts_total,1)}</div></td>
            <td style="width:52px;padding-left:0;padding-right:0">${Magic.beamArrow()}</td>
            <td><span class="up nm">${esc(u.in.web_name)}</span><div class="u2">${esc(u.in.team_short)} · £${num(u.in.price,1)}m · ${num(u.in.xpts_total,1)}</div></td>
            <td class="num up"><b>${sign(u.gain,1)}</b></td></tr>`).join('') || '<tr><td colspan="4" class="sub">No clear upgrade within budget.</td></tr>'}
          </tbody></table></div>
          <div class="legend">Extra xPts over ${S.horizon} gameweeks, affordable with your current bank.</div></div>
      </div>`;
    FX.listIn(el('rateNotes').children);
    if(/^A/.test(r.grade)){ const c = t.querySelector('.grade-ring'); if(c){ const b = c.getBoundingClientRect(); FX.burst(b.left + b.width/2, b.top + b.height/2, 110); } }
  }catch(e){ t.innerHTML = errBox(e); }
}
/* ---------------- Compare ---------------- */
async function viewCompare(t){
  t.innerHTML = `<div class="card mb"><div class="controls">
      <label class="fld">Player A<select id="cA" style="min-width:230px"></select></label>
      <label class="fld">Player B<select id="cB" style="min-width:230px"></select></label>
      <button class="btn primary" id="cGo">Compare</button></div></div><div id="cOut"></div>`;
  try{
    const d = await api(`/api/players?horizon=${S.horizon}&limit=450&min_minutes=90${ovQuery()}`);
    const opts = d.players.slice().sort((a,b)=>a.web_name.localeCompare(b.web_name))
      .map(p=>`<option value="${p.id}">${esc(p.web_name)} — ${esc(p.team_short)} ${POS[p.position]} £${num(p.price,1)}m</option>`).join('');
    el('cA').innerHTML = opts; el('cB').innerHTML = opts;
    el('cA').value = d.players[0].id; el('cB').value = d.players[1].id;
  }catch(e){ el('cOut').innerHTML = errBox(e); return; }
  const go = async ()=>{
    el('cOut').innerHTML = loading('Comparing');
    try{
      const r = await api(`/api/compare?a=${el('cA').value}&b=${el('cB').value}&horizon=${S.horizon}`);
      const row = (k,label,f=v=>num(v)) => { const a=r.a[k], b=r.b[k];
        return `<tr><td class="num ${a>b?'accent':''}" style="${a>b?'font-weight:800':''}">${f(a)}</td>
          <td style="text-align:center" class="sub">${label}</td>
          <td class="num ${b>a?'accent':''}" style="${b>a?'font-weight:800':''}">${f(b)}</td></tr>`; };
      el('cOut').innerHTML = `
        <div class="card mb"><div class="grid g3" style="align-items:center">
          <div style="text-align:right"><div style="font-size:22px;font-weight:700">${esc(r.a.web_name)}</div><div class="sub">${esc(r.a.team_short)} · ${r.a.pos_name} · £${num(r.a.price,1)}m</div></div>
          <div class="bubble" style="text-align:center;font-size:14px">${esc(r.verdict)}</div>
          <div><div style="font-size:22px;font-weight:700">${esc(r.b.web_name)}</div><div class="sub">${esc(r.b.team_short)} · ${r.b.pos_name} · £${num(r.b.price,1)}m</div></div>
        </div>${r.reasons.map(x=>`<div class="note" style="margin-top:12px">${esc(x)}</div>`).join('')}</div>
        <div class="grid g2">
          <div class="card"><h3>Head to head</h3><div class="well"><table><tbody>
            ${row('xpts_next','xPts, next GW')}${row('xpts_total','xPts, '+S.horizon+' GW',v=>num(v,1))}
            ${row('value','xPts per £m')}${row('xg90','xG / 90',v=>num(v,3))}${row('xa90','xA / 90',v=>num(v,3))}
            ${row('dc90','Defensive actions / 90',v=>num(v,1))}${row('bps90','BPS / 90',v=>num(v,1))}
            ${row('xmins','Expected minutes',v=>num(v,0))}${row('total_points','Season points',v=>v)}${row('form','Form',v=>num(v,1))}
            <tr><td class="num">${num(r.a.selected_by_percent,1)}%</td><td style="text-align:center" class="sub">Ownership</td><td class="num">${num(r.b.selected_by_percent,1)}%</td></tr>
          </tbody></table></div></div>
          <div class="card"><h3>Week by week</h3><div class="well"><table><thead><tr>
            <th class="num">${esc(r.a.web_name)}</th><th style="text-align:center">GW</th><th class="num">${esc(r.b.web_name)}</th></tr></thead><tbody>
            ${r.a.per_gw.map((g,i)=>{ const h=r.b.per_gw[i]; return `<tr>
              <td class="num"><span class="u2" style="display:inline">${esc(g.opp)}</span> <b class="${g.xpts>h.xpts?'accent':''}">${num(g.xpts)}</b></td>
              <td style="text-align:center"><b>${g.gw}</b></td>
              <td class="num"><b class="${h.xpts>g.xpts?'accent':''}">${num(h.xpts)}</b> <span class="u2" style="display:inline">${esc(h.opp)}</span></td></tr>`; }).join('')}
          </tbody></table></div></div>
        </div>`;
    }catch(e){ el('cOut').innerHTML = errBox(e); }
  };
  el('cGo').onclick = go; go();
}

/* ---------------- Mini-leagues ---------------- */
/* ---------------- Matches: who is likeliest to win, and by how many goals ---------------- */
const MT = {gw:null, seq:0};
const pct = v => Math.round(v * 100) + '%';
async function viewMatches(t){
  const mine = ++MT.seq;
  t.innerHTML = loading('Simulating every match');
  try{
    const r = await api('/api/matches' + (MT.gw ? '?gw='+MT.gw : ''));
    if(mine !== MT.seq) return;
    MT.gw = r.gw;
    const s = r.summary || {}, fav = s.biggest_favourite, dr = s.likeliest_draw;
    const day = m => m.kickoff ? new Date(m.kickoff).toLocaleDateString([], {weekday:'long', day:'numeric', month:'short'}) : 'Date to be confirmed';
    const clock = m => m.kickoff ? new Date(m.kickoff).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'}) : '';
    const card = m => {
      const played = !!m.actual, win = m.pick === 'home' ? m.home.name+' to win' : m.pick === 'away' ? m.away.name+' to win' : 'Draw';
      const shown = played ? m.actual : m.score;
      return `<article class="card mt ${played ? 'played' : ''}">
        <div class="mt-top"><span>${clock(m)}</span>${played ? `<span class="tag ${m.finished ? 'g' : 'y'}">${m.finished ? 'Full time' : 'Live'}</span>` : `<span class="dim">${esc(win)}</span>`}</div>
        <div class="mt-row">
          <div class="mt-team ${!played && m.pick === 'home' ? 'fav' : ''}"><b>${esc(m.home.short)}</b><span class="u2">${esc(m.home.name)}</span></div>
          <div class="mt-score" aria-label="${played ? 'Result' : 'Predicted score'} ${shown[0]} to ${shown[1]}"><b>${shown[0]}</b><i>–</i><b>${shown[1]}</b>
            <small>${played ? 'model: '+m.score[0]+'–'+m.score[1] : 'xG '+num(m.xg_home,1)+' – '+num(m.xg_away,1)}</small></div>
          <div class="mt-team away ${!played && m.pick === 'away' ? 'fav' : ''}"><b>${esc(m.away.short)}</b><span class="u2">${esc(m.away.name)}</span></div>
        </div>
        <div class="mt-bar" role="img" aria-label="${esc(m.home.name)} ${pct(m.p_home)}, draw ${pct(m.p_draw)}, ${esc(m.away.name)} ${pct(m.p_away)}">
          <i class="${m.pick === 'home' ? 'pick' : ''}" style="flex:${m.p_home}"></i><i class="d ${m.pick === 'draw' ? 'pick' : ''}" style="flex:${m.p_draw}"></i><i class="${m.pick === 'away' ? 'pick' : ''}" style="flex:${m.p_away}"></i></div>
        <div class="mt-odds"><span>${esc(m.home.short)} ${pct(m.p_home)}</span><span>Draw ${pct(m.p_draw)}</span><span>${esc(m.away.short)} ${pct(m.p_away)}</span></div>
        <div class="mt-facts">Clean sheet: ${esc(m.home.short)} ${pct(m.p_cs_home)} · ${esc(m.away.short)} ${pct(m.p_cs_away)}<br>Both score ${pct(m.p_btts)} · 3+ goals ${pct(m.p_over25)}</div>
        <details class="mt-more"><summary>Scoreline odds</summary><div class="mt-chips">${m.top_scores.map(x=>`<span class="tag ${x.home === m.score[0] && x.away === m.score[1] ? '' : 'g'}">${x.home}–${x.away} <b>${pct(x.p)}</b></span>`).join('')}</div></details>
      </article>`;
    };
    const days = [];
    r.matches.forEach(m=>{ const d = day(m), last = days[days.length-1]; if(last && last.d === d) last.ms.push(m); else days.push({d, ms:[m]}); });
    t.innerHTML = `
      <div class="card mb"><div class="controls mt-nav">
        <div class="gw-nav"><button id="mtPrev" aria-label="Previous gameweek" ${r.gw <= r.first ? 'disabled' : ''}>‹</button><span>GW${r.gw}</span><button id="mtNext" aria-label="Next gameweek" ${r.gw >= r.last ? 'disabled' : ''}>›</button></div>
        <button class="btn sm" id="mtNow" ${r.gw === r.next_gw ? 'hidden' : ''}>Back to GW${r.next_gw}</button>
        <span class="dim mt-when">${r.finished ? 'Played' : r.gw === r.next_gw ? 'Next up' : r.gw < r.next_gw ? 'Played' : 'Coming up'}</span></div></div>
      ${r.matches.length ? `<div class="grid g4 mb">
        ${tile('Matches', s.matches, s.home_wins+' home · '+s.draws+' draw'+(s.draws === 1 ? '' : 's')+' · '+s.away_wins+' away')}
        ${tile('Goals a match', num(s.goals_per_match,1), 'expected, on average')}
        ${tile('Biggest favourite', esc(fav.short), pct(fav.p)+' to beat '+esc(fav.against)+(fav.home ? ' at home' : ' away'))}
        ${tile('Likeliest draw', esc(dr.home)+' v '+esc(dr.away), pct(dr.p))}
      </div>` : `<div class="note">No matches are scheduled in GW${r.gw}.</div>`}
      ${days.map(d=>`<h2 class="mt-day">${esc(d.d)}</h2><div class="mt-list">${d.ms.map(card).join('')}</div>`).join('')}
      <div class="legend">Predictions come from each club’s Elo rating, this season’s chances created and conceded, its last six games and home advantage — the same goal model as the player projections. The headline score is the likeliest scoreline <i>once the likeliest result is chosen</i>. Football is noisy: a 60% favourite still fails to win four times in ten. For planning and fun, not a betting tip.</div>`;
    const to = g => { MT.gw = g; viewMatches(t); };
    el('mtPrev').onclick = ()=>to(Math.max(r.first, r.gw - 1));
    el('mtNext').onclick = ()=>to(Math.min(r.last, r.gw + 1));
    el('mtNow').onclick = ()=>to(r.next_gw);
  }catch(e){ if(mine === MT.seq) t.innerHTML = errBox(e); }
}

/* Every league a manager is in (any Team ID), with their place, the leader and the gap. */
const LG = {team:''};         // the manager whose leagues are listed (their row is always in the analysis)
const ord = n => n == null ? '–' : n.toLocaleString();
function leaguesHtml(r){
  const by = k => r.leagues.filter(l=>l.kind === k), priv = by('private'), s = r.summary || {};
  if(!r.leagues.length) return r.demo
    ? `<div class="note">The demo team is in no mini-leagues. Enter a real Team ID above, or try a league ID below (314 is the Overall league).</div>`
    : `<div class="note">${esc(r.team || 'This team')} isn’t in any leagues yet. FPL lists them on the manager’s profile.</div>`;
  const move = l => l.movement > 0 ? ` <span class="up">▲${ord(l.movement)}</span>` : l.movement < 0 ? ` <span class="down">▼${ord(-l.movement)}</span>` : '';
  const rowOf = l => {
    const place = l.my_rank ? '#'+ord(l.my_rank)+move(l) : '–';
    const gap = l.unavailable ? '<span class="dim">unavailable</span>'
      : l.i_lead ? `<span class="tag">Leading</span>${l.ahead_of_next != null ? `<div class="u2">+${l.ahead_of_next} clear</div>` : ''}`
      : l.gap_to_leader != null ? `−${l.gap_to_leader}<div class="u2">${esc(l.leader.entry_name||'')}</div>` : '–';
    const pts = l.my_total != null ? `${l.my_total}<div class="u2">GW ${l.my_gw}${l.gw_avg != null ? ' · avg '+num(l.gw_avg,0) : ''}</div>` : '–';
    return `<tr><td><span class="nm">${esc(l.name)}</span><div class="u2">${l.size ? ord(l.size)+' managers' : ''}${l.closed ? ' · closed' : ''}</div>
        <button class="btn sm lg-go" data-lg="${l.id}">Analyse</button></td>
      <td class="num">${place}</td><td class="num">${pts}</td><td class="num">${gap}</td></tr>`;
  };
  const other = by('h2h').concat(by('system'));
  return `
    <div class="grid g4 mb">
      ${tile('Mini-leagues', s.private, s.unread ? s.unread+' not read in full' : 'private leagues')}
      ${tile('Leading', s.leading, s.top3 ? s.top3+' in the top three' : 'none in the top three')}
      ${tile('Moving', '<span class="up">▲'+(s.climbing||0)+'</span> <span class="down">▼'+(s.falling||0)+'</span>', 'places since last week')}
      ${tile('Best place', s.best ? '#'+ord(s.best.rank) : '–', s.best ? esc(s.best.name)+(s.best.size ? ' of '+ord(s.best.size) : '') : '')}
    </div>
    ${priv.length ? `<div class="well mb"><table><thead><tr><th>League</th><th class="num">Place</th><th class="num">Points</th><th class="num">Behind leader</th></tr></thead>
      <tbody>${priv.map(rowOf).join('')}</tbody></table></div>` : ''}
    ${other.length ? `<div class="well"><table><thead><tr><th>FPL’s own &amp; head-to-head</th><th class="num">Place</th><th class="num">Top</th></tr></thead><tbody>
      ${other.map(l=>`<tr><td><span class="nm">${esc(l.name)}</span><div class="u2">${l.kind === 'h2h' ? 'head-to-head' : 'FPL league'}${l.size ? ' · '+ord(l.size)+' managers' : ''}</div></td>
        <td class="num">${l.my_rank ? '#'+ord(l.my_rank)+move(l) : '–'}</td>
        <td class="num">${l.percentile != null ? 'top '+l.percentile+'%' : '–'}</td></tr>`).join('')}</tbody></table></div>` : ''}`;
}
async function viewLeague(t){
  const mine = S.teamId && !isDemo() ? S.teamId : '';
  t.innerHTML = `<div class="card mb"><h3>Your mini-leagues <span class="r" id="lgWho"></span></h3>
      <div class="controls">
        <label class="fld">FPL Team ID<input id="lgTeam" type="number" placeholder="e.g. 1421260" style="width:150px" value="${esc(LG.team || mine)}"></label>
        <button class="btn primary" id="lgFind">Find leagues</button></div>
      <div class="legend">Any manager’s ID works. Every league they’re in, with their place, the leader and the gap; Analyse opens the rivals’ squads and win chances below.</div>
      <div id="lgList" style="margin-top:14px"></div></div>
    <div class="card mb"><div class="controls">
      <label class="fld">League ID<input id="lgId" type="number" placeholder="e.g. 314" style="width:136px" value="${esc(store.get('fplai_league',''))}"></label>
      <label class="fld">Rivals<select id="lgN"><option>6</option><option selected>12</option><option>20</option></select></label>
      <button class="btn primary" id="lgGo">Analyse</button></div>
      <div class="legend">The league ID is in the address bar on your league page:
        <code>fantasy.premierleague.com/leagues/<b>123456</b>/standings/c</code>. Try 314 for the overall league.</div></div>
    <div id="lgOut"></div>`;
  const find = async ()=>{
    const id = el('lgTeam').value.replace(/\D/g, '');
    if(!id){ el('lgList').innerHTML = ''; el('lgWho').textContent = ''; return; }
    LG.team = id;
    el('lgList').innerHTML = loading('Reading every league');
    try{
      const r = await api(`/api/entry/${id}/leagues`);
      el('lgWho').textContent = [r.team, r.manager].filter(Boolean).join(' · ');
      el('lgList').innerHTML = leaguesHtml(r);
      el('lgList').querySelectorAll('[data-lg]').forEach(b=>b.onclick = ()=>{
        el('lgId').value = b.dataset.lg; go();
        el('lgOut').scrollIntoView({behavior: FX.reduced ? 'auto' : 'smooth', block:'start'});
      });
    }catch(e){ el('lgList').innerHTML = errBox(e); }
  };
  const go = async ()=>{
    const id = el('lgId').value.trim(); if(!id) return;
    store.set('fplai_league', id);
    el('lgOut').innerHTML = loading('Fetching rival squads and simulating 4,000 finishes');
    try{
      const r = await api(`/api/league/${id}?horizon=${S.horizon}&rivals=${el('lgN').value}${LG.team ? '&entry='+LG.team : ''}`);
      const top = r.managers[0], o0 = r.ownership[0], e0 = r.effective_ownership[0];
      el('lgOut').innerHTML = `
        <div class="grid g4 mb">
          ${tile('League', esc(r.league.name||'—'), r.rivals_analysed+' squads analysed')}
          ${tile('Favourite', esc(top?top.name:'—'), top?num(top.win_probability,1)+'% to win':'')}
          ${tile('Most owned', esc(o0?o0.player.web_name:'—'), o0?o0.pct+'% of rivals':'')}
          ${tile('Top effective ownership', esc(e0?e0.player.web_name:'—'), e0?e0.effective_ownership+'% incl. captaincy':'')}
        </div>
        <div class="card mb"><h3>Chance to win <span class="r">${r.sims.toLocaleString()} simulations over ${S.horizon} GW</span></h3>
          <div class="well"><table><thead><tr><th>#</th><th>Manager</th><th class="num">Points</th><th class="num">Projected</th><th style="width:30%">Win</th><th class="num">Top 3</th></tr></thead><tbody>
          ${r.managers.map(m=>`<tr><td class="dim">${m.rank}</td>
            <td><span class="nm">${esc(m.name)}</span>${String(m.entry) === String(LG.team) ? ' <span class="tag">you</span>' : ''}<div class="u2">${esc(m.player_name)}</div></td>
            <td class="num">${m.total}</td><td class="num">${num(m.horizon_xpts,1)}</td>
            <td><div style="display:flex;align-items:center;gap:9px"><div class="meter" style="flex:1;margin:0"><i style="width:${Math.max(1,m.win_probability)}%"></i></div>
              <b class="accent" style="font-family:var(--mono);font-size:12.5px;min-width:44px;text-align:right">${num(m.win_probability,1)}%</b></div></td>
            <td class="num">${num(m.top3_probability,1)}%</td></tr>`).join('')}</tbody></table></div></div>
        <div class="grid g3">
          <div class="card lift"><h3>Most owned here</h3><div class="well"><table><tbody>
            ${r.ownership.slice(0,10).map(o=>`<tr><td><span class="nm">${esc(o.player.web_name)}</span><div class="u2">${esc(o.player.team_short)}</div></td>
              <td class="num">${o.pct}%</td><td class="num accent">${num(o.player.xpts_total,1)}</td></tr>`).join('')}</tbody></table></div></div>
          <div class="card lift"><h3>Effective ownership</h3><div class="well"><table><tbody>
            ${r.effective_ownership.slice(0,10).map(o=>`<tr><td><span class="nm">${esc(o.player.web_name)}</span><div class="u2">${esc(o.player.team_short)}</div></td>
              <td class="num"><b>${o.effective_ownership}%</b></td></tr>`).join('')}</tbody></table></div>
            <div class="legend">Captaincy counts twice. Above 100% means rivals gain on you if he scores and you don’t own him.</div></div>
          <div class="card lift"><h3>Nobody here owns</h3><div class="well"><table><tbody>
            ${r.differentials.slice(0,10).map(o=>`<tr><td><span class="nm">${esc(o.player.web_name)}</span><div class="u2">${esc(o.player.team_short)} · £${num(o.player.price,1)}m</div></td>
              <td class="num">${o.league_pct}%</td><td class="num accent">${num(o.player.xpts_total,1)}</td></tr>`).join('')}</tbody></table></div></div>
        </div>`;
    }catch(e){ el('lgOut').innerHTML = errBox(e); }
  };
  el('lgGo').onclick = go;
  el('lgFind').onclick = find;
  el('lgTeam').addEventListener('keydown', ev=>{ if(ev.key === 'Enter') find(); });
  if(el('lgTeam').value) find();
  else if(isDemo()) el('lgList').innerHTML = leaguesHtml({leagues:[], demo:true});
  if(el('lgId').value) go();
}

/* ---------------- Players: prices, line-ups, set pieces, DEFCON ----------------
   One request feeds three of these pages, so it's shared and keyed by horizon. */
const SC = { key:null, data:null, lineups:null };
async function scoutData(){
  if(SC.key !== S.horizon || !SC.data){ SC.data = await api(`/api/scout?horizon=${S.horizon}`); SC.key = S.horizon; }
  return SC.data;
}
const scoutView = kind => async function(t){
  t.innerHTML = loading(kind === 'lineups' ? 'Predicting every line-up' : 'Scouting');
  try{
    if(kind === 'lineups'){
      const lineups = SC.lineups = SC.lineups || await api('/api/lineups?horizon=1');
      t.innerHTML = `<div class="grid g3">${lineups.teams.map(tm=>`
        <div class="card lift"><h3>${esc(tm.name)} <span class="r">${esc(tm.team)}</span></h3>
          ${tm.xi.map(x=>`<div class="kv"><span>${pos(x.player.position)} <span style="color:var(--ink)">${esc(x.player.web_name)}</span>${x.doubt?' <span class="tag y" style="font-size:10px;padding:1px 6px">doubt</span>':''}</span>
            <span class="${x.p_start>=80?'up':x.p_start>=55?'':'warn'}">${x.p_start}%</span></div>`).join('')}
          ${tm.rotation_risks.length?`<div class="legend"><b>Rotation risk:</b> ${tm.rotation_risks.map(r=>esc(r.player.web_name)+' '+r.p_start+'%').join(', ')}</div>`:''}
          ${tm.doubts.length?`<div class="legend"><b>Flagged:</b> ${tm.doubts.map(d=>esc(d.player.web_name)).join(', ')}</div>`:''}
        </div>`).join('')}</div>`;
      return;
    }
    const data = await scoutData();
    if(kind === 'prices'){
      const P = data.prices, R = (S.meta&&S.meta.rules)||{};
      const next = (R.price_change_deadlines||[])[0];
      const tbl = (list, dir) => `<div class="well"><table><thead><tr><th>Player</th><th style="width:34%">Progress</th><th>Odds tonight</th><th class="num">Net transfers</th></tr></thead><tbody>
        ${list.map(x=>`<tr><td><span class="nm">${esc(x.player.web_name)}</span><div class="u2">${esc(x.player.team_short)} · £${num(x.player.price,1)}m</div></td>
          <td><div style="display:flex;align-items:center;gap:8px"><div class="meter" style="flex:1;margin:0"><i style="width:${Math.min(100,Math.abs(x.projected))}%;${dir<0?'background:linear-gradient(90deg,var(--down),var(--down-2))':''}"></i></div>
            <span style="font-family:var(--mono);font-size:12px;min-width:46px;text-align:right">${num(x.projected,0)}%</span></div></td>
          <td><span class="tag ${dir>0?'g':'r'}">${esc(x.likelihood_label)}</span></td>
          <td class="num ${x.net_transfers>=0?'up':'down'}">${x.net_transfers>=0?'+':''}${x.net_transfers.toLocaleString()}</td></tr>`).join('')
          || '<tr><td colspan="4" class="sub">Nobody close to a change tonight.</td></tr>'}</tbody></table></div>`;
      t.innerHTML = `
        ${next?`<div class="grid g4 mb">${tile('Next price update', new Date(next).toLocaleString([], {weekday:'short',hour:'2-digit',minute:'2-digit'}), 'From FPL’s published schedule')}
          ${tile('Likely risers', P.risers.length, 'at least “possible”')}${tile('Likely fallers', P.fallers.length, 'at least “possible”')}
          ${tile('Biggest mover', esc(P.most_transferred[0]?P.most_transferred[0].player.web_name:'—'), P.most_transferred[0]?(P.most_transferred[0].net>=0?'+':'')+P.most_transferred[0].net.toLocaleString()+' net':'')}</div>`:''}
        <div class="grid g2 mb">
          <div class="card"><h3>Likely to rise</h3>${tbl(P.risers.slice(0,12), 1)}</div>
          <div class="card"><h3>Likely to fall</h3>${tbl(P.fallers.slice(0,12), -1)}</div></div>
        <div class="card"><h3>Biggest movers this gameweek</h3><div class="well"><table><thead><tr><th>Player</th><th class="num">In</th><th class="num">Out</th><th class="num">Net</th></tr></thead><tbody>
          ${P.most_transferred.map(x=>`<tr><td><span class="nm">${esc(x.player.web_name)}</span><div class="u2">${esc(x.player.team_short)}</div></td>
            <td class="num">${x.in.toLocaleString()}</td><td class="num">${x.out.toLocaleString()}</td>
            <td class="num ${x.net>=0?'up':'down'}"><b>${x.net>=0?'+':''}${x.net.toLocaleString()}</b></td></tr>`).join('')}</tbody></table></div>
          <div class="legend">Progress is FPL’s own price counter: at +100% a player rises £0.1m at the next update, at −100% he falls. Odds are FPL’s projection for tonight.</div></div>`;
    } else if(kind === 'setpieces'){
      const who = l => l.length ? l.map((x,i)=>`<span class="${i===0?'nm':'dim'}">${i+1}. ${esc(x.web_name)}</span>`).join('<br>') : '<span class="dim">—</span>';
      t.innerHTML = `<div class="card"><div class="well" style="max-height:none"><table><thead><tr><th>Club</th><th>Penalties</th><th>Direct free kicks</th><th>Corners &amp; indirect</th></tr></thead><tbody>
        ${data.set_pieces.teams.map(tm=>`<tr><td><b>${esc(tm.team)}</b><div class="u2">${esc(tm.name)}</div></td>
          <td>${who(tm.penalties)}</td><td>${who(tm.freekicks)}</td><td>${who(tm.corners)}</td></tr>`).join('')}</tbody></table></div>
        <div class="legend">Order of preference as listed by FPL. The first name takes it when he’s on the pitch.</div></div>`;
    } else {
      t.innerHTML = `<div class="card"><h3>Most likely to earn defensive-contribution points <span class="r">next gameweek</span></h3>
        <div class="well" style="max-height:none"><table><thead><tr><th>Player</th><th></th><th class="num">Per 90</th><th class="num">Needs</th><th style="width:26%">Chance to hit</th><th class="num">xPts</th><th class="num">Season total</th></tr></thead><tbody>
        ${data.defcon.players.map(x=>`<tr><td><span class="nm">${esc(x.player.web_name)}</span><div class="u2">${esc(x.player.team_short)} · £${num(x.player.price,1)}m</div></td>
          <td>${pos(x.player.position)}</td><td class="num">${num(x.dc_per_90,1)}</td><td class="num dim">${x.threshold}</td>
          <td><div style="display:flex;align-items:center;gap:8px"><div class="meter" style="flex:1;margin:0"><i style="width:${x.hit_probability}%"></i></div>
            <b style="font-family:var(--mono);font-size:12px;min-width:44px;text-align:right">${num(x.hit_probability,0)}%</b></div></td>
          <td class="num accent">${num(x.xpts_from_dc)}</td><td class="num">${x.dc_total}</td></tr>`).join('')}</tbody></table></div>
        <div class="legend">Defenders score 2 for 10 clearances, blocks, interceptions and tackles in a match; midfielders and forwards need 12, with recoveries also counting.</div></div>`;
    }
  }catch(e){ t.innerHTML = errBox(e); }
};

/* ---------------- How it works ---------------- */
async function viewModel(t){
  t.innerHTML = loading('Reading the model');
  try{
    const m = S.meta = S.meta || await api('/api/meta');
    const R = m.rules || {}, sc = R.scoring || {};
    const teams = Object.entries(m.team_ratings).map(([id,r])=>({name:(m.teams.find(x=>x.id==id)||{}).short_name, ...r}))
      .sort((a,b)=>b.attack-a.attack);
    const P = (h, body) => `<div class="card lift"><h3>${h}</h3><div style="font-size:13.8px;color:var(--ink-2);line-height:1.7">${body}</div></div>`;
    const byPos = o => o ? ['GKP','DEF','MID','FWD'].map(k=>k+' '+o[k]).join(' · ') : '—';
    t.innerHTML = `
      <div class="grid g4 mb">
        ${tile('Clubs with Elo', m.model.elo_teams+' / 20', 'From FPL-Core-Insights match files')}
        ${tile('Elo → goals', (m.model.elo_k*100).toFixed(3), 'Fitted, per 100 Elo points')}
        ${tile('Form window', m.model.recent_gameweeks.length+' GWs', 'GW'+m.model.recent_gameweeks.join(', '))}
        ${tile('Loan blocks', m.model.loan_blocks, 'Weeks a loanee can’t play')}
      </div>
      <div class="grid g3 mb">
        ${P('1 · How strong is each club?', `Each club starts from its <b>Elo rating</b> (ClubElo, via the FPL-Core-Insights match files). Promoted clubs with no top-flight rating sit just below the weakest club that has one.
          This season's xG and xG conceded then pull each club away from that starting point, more with every game played. How many goals an Elo point is worth is fitted from this season's own numbers.
          Then <b>recent form</b>: each club's last six games lean its attack and defence (by at most about a fifth), so a side that has stopped creating, or started leaking, is treated that way.`)}
        ${P('2 · Who plays, and for how long?', `Minutes come from FPL's week-by-week data (<code>/event/{gw}/live/</code>), with each week further back weighted 28% less. The model learns each player's <b>minutes when he starts</b>, eases injury returners back in (about 60′, then 75′), lets doubtful players' odds recover week by week, and drifts longer-range weeks back toward a player's usual role.
          Loanees barred from facing their parent club get zero for that week. You can overwrite anyone's minutes in the Expected Points table.`)}
        ${P('3 · What is each fixture worth?', `Goals for each side follow a <b>Poisson model</b> with home advantage. A player gets his share of his club's attack from his xG and xA per 90, shrunk toward a price-based estimate when his sample is thin.
          His recent xG and xA (the last six weeks, up to 35%) and, a little, the goals and assists he actually got (up to 25%) are blended in. His <b>chance to score</b> is 1 − e<sup>−xG</sup> for the fixture.
          The points values come straight from FPL's published scoring table rather than being typed in by hand.`)}
      </div>
      <div class="grid g2 mb">
        <div class="card"><h3>Scoring, as FPL publishes it this season</h3>
          <div class="kv"><span>Goal</span><span>${byPos(sc.goal)}</span></div>
          <div class="kv"><span>Clean sheet</span><span>${byPos(sc.clean_sheet)}</span></div>
          <div class="kv"><span>Per 2 conceded</span><span>${byPos(sc.conceded_per_2)}</span></div>
          <div class="kv"><span>Defensive contribution</span><span>${byPos(sc.defensive_contribution)}</span></div>
          <div class="kv"><span>Assist · per 3 saves · yellow</span><span>${sc.assist} · ${sc.save_per_3} · ${sc.yellow}</span></div>
          <div class="kv"><span>Appearance (1–59′ / 60′+)</span><span>${sc.appearance_under_60} / ${sc.appearance_60_plus}</span></div>
          <div class="kv"><span>Squad · per club · budget</span><span>${R.squad_size} · ${R.club_limit} · £${R.budget}m</span></div>
          <div class="kv"><span>Max banked transfers · sell-on fee</span><span>${R.max_free_transfers} · ${Math.round((R.sell_on_fee||0)*100)}%</span></div>
          <div class="kv"><span>Chip windows</span><span>${[...new Set((R.chips||[]).map(c=>'GW'+c.start+'–'+c.stop))].join(', ')}</span></div>
        </div>
        ${P('The solver', `A mixed-integer program (CBC via PuLP) picks squad, starting XI, captain, vice-captain and transfers for every gameweek at once, inside the published limits above, with your real bank and selling prices.
          It won't buy or captain anyone under <b>75% to play</b> in the coming week (change it in Advanced settings), and tells you who it left out.
          After the best route it re-solves with that route ruled out, twice, so you see <b>three genuinely different plans</b>. Chips are only offered in weeks where FPL's chip windows and your history allow them.<br><br>
          <b>Data:</b> the FPL API (players, prices, fixtures, your squad, per-week minutes, price progress, set-pieces, scoring rules) and FPL-Core-Insights (club Elo). Cached locally, rebuilt every 15 minutes.`)}
      </div>
      <div class="card"><h3>Club ratings in use</h3>
        <div class="well"><table><thead><tr><th>Club</th><th class="num">Elo</th><th class="num">Attack prior</th><th class="num">Attack</th><th class="num">Defence prior</th><th class="num">Defence</th><th class="num">xG / game</th><th class="num">xGC / game</th><th class="num">Played</th></tr></thead><tbody>
        ${teams.map(x=>`<tr><td><b>${esc(x.name)}</b></td><td class="num">${x.elo?num(x.elo,0):'—'}</td>
          <td class="num dim">${num(x.attack_prior)}</td><td class="num accent"><b>${num(x.attack)}</b></td>
          <td class="num dim">${num(x.defence_prior)}</td><td class="num ${x.defence>1?'down':'up'}"><b>${num(x.defence)}</b></td>
          <td class="num">${num(x.xg_per_game)}</td><td class="num">${num(x.xgc_per_game)}</td><td class="num">${x.games}</td></tr>`).join('')}
        </tbody></table></div>
        <div class="legend">1.00 is league average. Attack above 1 scores more than average; defence above 1 concedes more.</div></div>`;
  }catch(e){ t.innerHTML = errBox(e); }
}

/* ---------------- tabs ----------------
   Six tabs, no "More". Each tab holds one or more sub-pages, picked from the
   switcher under the title. Every tab and sub-page has its own address
   (#plan/chips), and the old single-view addresses still land in the right place. */
const ICONS = {
  home:'M3.5 10.5 12 3.8l8.5 6.7V19a1.5 1.5 0 0 1-1.5 1.5h-4.2v-6h-5.6v6H5A1.5 1.5 0 0 1 3.5 19z',
  plan:'M5.5 15.8a2.2 2.2 0 1 0 0 4.4a2.2 2.2 0 1 0 0-4.4zM18.5 3.8a2.2 2.2 0 1 0 0 4.4a2.2 2.2 0 1 0 0-4.4zM7.6 17.2c5.5-1 3.2-9.6 8.8-10.4',
  players:'M8.5 4 4 6.2 2.5 10.5l3 1.2V20h13v-8.3l3-1.2L20 6.2 15.5 4a3.6 3.6 0 0 1-7 0z',
  matches:'M12 3.5a8.5 8.5 0 1 0 0 17 8.5 8.5 0 0 0 0-17zM12 8.4l3.1 2.2-1.2 3.7h-3.8l-1.2-3.7zM12 3.8v4.6M15.1 10.6l4.2-1.4M13.9 14.3l2.6 3.5M10.1 14.3l-2.6 3.5M8.9 10.6 4.7 9.2',
  leagues:'M8 4h8v5a4 4 0 0 1-8 0zM8 6H5a3 3 0 0 0 3 4M16 6h3a3 3 0 0 1-3 4M12 13v4M8.5 20h7M10 17h4',
  ask:'M20 12.2c0 4-3.6 7-8 7-1.2 0-2.3-.2-3.3-.6L4 20l1.3-3.6A6.7 6.7 0 0 1 4 12.2c0-4 3.6-7.2 8-7.2s8 3.2 8 7.2zM8.5 12h.01M12 12h.01M15.5 12h.01',
  refresh:'M20 12a8 8 0 1 1-2.6-5.9M20 4v4.6h-4.6',
  forget:'M5 7h14M10 11v6M14 11v6M6 7l1 12a2 2 0 0 0 2 1.8h6a2 2 0 0 0 2-1.8L18 7M9 7V4.5h6V7'
};
const icon = name => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${ICONS[name]}"/></svg>`;

const TABS = [
  {id:'home', label:'Home', icon:'home', title:'Home', segs:[
    {id:'squad', label:'My squad', view:viewSquad, sub:'Add your team and we’ll tell you how your week went. Gently. Ish.', waiting:'Checking the scoreline…'},
    {id:'grade', label:'Grade',    view:viewRate,  sub:'Your squad scored out of 100, with the fixes that move the score most.'},
    {id:'picks', label:'Picks',    view:viewPicks, sub:'This week’s captains, differentials, best value and the dream team.'}]},
  {id:'plan', label:'Plan', icon:'plan', title:'Plan', segs:[
    {id:'transfers', label:'Transfers', view:viewSolver, sub:'Transfers, captaincy and line-ups across the whole horizon at once — plus the next-best routes.'},
    {id:'chips',     label:'Chips',     view:viewChips,  sub:'Each chip scored in every gameweek, then combined into the best overall plan.'}]},
  {id:'players', label:'Players', icon:'players', title:'Players', segs:[
    {id:'projections', label:'Projections', view:viewXpts, sub:'Every player across the coming gameweeks. Tap a minutes figure to set your own — every tool then uses it.'},
    {id:'compare',     label:'Compare',     view:viewCompare, sub:'Two players side by side on projections, underlying numbers and fixtures.'},
    {id:'prices',      label:'Prices',      view:scoutView('prices'), sub:'Who’s about to rise or fall in price tonight, and who everyone is buying.'},
    {id:'lineups',     label:'Line-ups',    view:scoutView('lineups'), sub:'Predicted starting elevens, with rotation risks and doubts.'},
    {id:'setpieces',   label:'Set pieces',  view:scoutView('setpieces'), sub:'Who takes the penalties, free kicks and corners at every club.'},
    {id:'defcon',      label:'DEFCON',      view:scoutView('defcon'), sub:'Who is most likely to earn defensive-contribution points next gameweek.'}]},
  {id:'matches', label:'Matches', icon:'matches', title:'Matches', segs:[
    {id:'predictions', label:'Predictions', view:viewMatches, sub:'Who’s likeliest to win each match and the score to expect, from the same goal model as the projections.'}]},
  {id:'leagues', label:'Leagues', icon:'leagues', title:'Mini-leagues', segs:[
    {id:'league', label:'Mini-league', view:viewLeague, sub:'Your place in every league you’re in, the gap to the leader, and who’s likeliest to win.'}]},
  {id:'ask', label:'Ask', icon:'ask', title:'Ask', segs:[
    {id:'copilot', label:'Copilot', view:viewCopilot, sub:'Ask in plain English. Every answer is read straight off the model, so you can check the numbers behind it.'}]}
];
const LEGACY = {dashboard:'home/squad', rate:'home/grade', solver:'plan/transfers', chips:'plan/chips', xpts:'players/projections',
                compare:'players/compare', scout:'players/prices', league:'leagues/league', copilot:'ask/copilot'};
const tabOf = id => TABS.find(t=>t.id===id) || TABS[0];
let cur = {tab:'', seg:''};

function buildChrome(){
  el('nav').innerHTML = TABS.map(t=>`<button data-tab="${t.id}" title="${t.label}">${icon(t.icon)}<span>${t.label}</span></button>`).join('');
  el('dock').innerHTML = '<span class="ind" aria-hidden="true"></span>' + TABS.map(t=>`<button data-tab="${t.id}">${icon(t.icon)}${t.label}</button>`).join('');
  el('views').innerHTML = TABS.map(t=>t.segs.map(s=>`<section class="view" id="v-${t.id}-${s.id}"></section>`).join('')).join('');
}
function go(tabId, segId){
  const t = tabOf(tabId);
  const want = segId || S.lastSeg[t.id] || (t.id === 'home' && !S.teamId ? 'picks' : t.segs[0].id);
  const seg = t.segs.find(s=>s.id===want) || t.segs[0];
  const tabChanged = cur.tab !== t.id;
  if(!tabChanged && cur.seg === seg.id && S.loaded[t.id+'/'+seg.id]) return;
  if(tabChanged || cur.seg !== seg.id) countView(t.id + '/' + seg.id);
  cur = {tab:t.id, seg:seg.id}; S.lastSeg[t.id] = seg.id;

  document.querySelectorAll('#nav button, #dock button').forEach(b=>{
    const on = b.dataset.tab === t.id; b.classList.toggle('on', on);
    if(on) b.setAttribute('aria-current', 'page'); else b.removeAttribute('aria-current');
  });
  syncHead();
  const segs = el('segs');
  if(t.segs.length > 1){
    if(segs.dataset.tab !== t.id){
      segs.dataset.tab = t.id;
      segs.innerHTML = '<span class="seg-ind" aria-hidden="true"></span>' + t.segs.map(s=>`<button type="button" role="tab" data-seg="${s.id}">${s.label}</button>`).join('');
    }
    segs.querySelectorAll('button').forEach(b=>{ const on = b.dataset.seg === seg.id; b.classList.toggle('on', on); b.setAttribute('aria-selected', String(on)); });
    segs.hidden = false;
  } else { segs.hidden = true; segs.dataset.tab = ''; segs.innerHTML = ''; }
  const view = el(`v-${t.id}-${seg.id}`);
  document.querySelectorAll('#views .view').forEach(v=>v.classList.toggle('on', v === view));
  const hash = t.id + '/' + seg.id;
  if(location.hash.slice(1) !== hash){ try{ history.replaceState(null, '', '#'+hash); }catch(e){} }
  render(t.id, seg.id);
  FX.navigated({tabChanged, dock:el('dock'), nav:el('nav'), segs, view});
  if(tabChanged) window.scrollTo({top:0, behavior: FX.reduced ? 'auto' : 'smooth'});
}
function render(tab, seg){
  const key = [S.horizon, S.teamId, ovParam(), madeParam()].join('|'), id = tab+'/'+seg;
  if(S.loaded[id] === key) return;
  S.loaded[id] = key;
  const s = tabOf(tab).segs.find(x=>x.id===seg);
  s.view(el(`v-${tab}-${seg}`));
}
const rerender = () => render(cur.tab, cur.seg);
function invalidate(){ S.loaded = {}; S.entry = null; S.squadSub = ''; }
function syncHead(animate){
  if(!cur.tab) return;
  const t = tabOf(cur.tab), seg = t.segs.find(s=>s.id===cur.seg) || t.segs[0];
  const verdict = t.id === 'home' && seg.id === 'squad' && S.teamId;
  const title = el('view-title'), was = title.textContent;
  title.textContent = t.id === 'home' && S.teamId ? (S.teamName || 'Team '+S.teamId) : t.title;
  el('view-eyebrow').textContent = t.label + (t.segs.length > 1 ? ' / ' + seg.label : '') + (S.meta ? ' · GW' + S.meta.next_gw : '');
  raceBar();
  if(was !== title.textContent) Magic.hyperText(title, {duration:700});
  const sub = el('view-sub');
  sub.textContent = verdict ? (S.squadSub || seg.waiting) : seg.sub;
  sub.classList.toggle('verdict', !!(verdict && S.squadSub));
  if(animate){ sub.classList.remove('fresh'); void sub.offsetWidth; sub.classList.add('fresh'); }
}
/* The season as a race (under the page title): a segment a gameweek, lime to green up to the
   current one, the next one outlined, the rest still to run. Built once per gameweek. */
function raceBar(){
  const bar = el('raceBar'), m = S.meta;
  if(!bar || !m || !m.events || bar.dataset.gw === String(m.current_gw)) return;
  bar.dataset.gw = String(m.current_gw);
  const n = m.events.length, mix = (a, b, t) => Math.round(a + (b - a) * t);
  bar.innerHTML = m.events.map((ev, i)=>{
    const t = n > 1 ? i / (n - 1) : 0;
    if(ev.id <= m.current_gw) return `<span style="--i:${i};background:rgb(${mix(0xd2,0x2e,t)},${mix(0xff,0xe8,t)},${mix(0x2e,0x8f,t)})"></span>`;
    return `<span style="--i:${i}"${ev.id === m.next_gw ? ' class="next"' : ''}></span>`;
  }).join('');
  const left = Math.max(0, n - m.current_gw);
  el('gwLeft').innerHTML = left ? `<b>${left}</b> gameweek${left === 1 ? '' : 's'} left` : 'Season over';
}
function routeFromHash(){
  let h = location.hash.slice(1);
  if(h === 'model'){ h = ''; openMenu(); }
  if(h === 'stats'){ h = ''; openStats(); }
  h = LEGACY[h] || h;
  const [t, s] = h.split('/');
  go(TABS.some(x=>x.id===t) ? t : 'home', s);
}

el('nav').addEventListener('click', e=>{ const b = e.target.closest('button[data-tab]'); if(b) go(b.dataset.tab); });
el('dock').addEventListener('click', e=>{ const b = e.target.closest('button[data-tab]'); if(b) go(b.dataset.tab); });
el('segs').addEventListener('click', e=>{ const b = e.target.closest('button[data-seg]'); if(b) go(cur.tab, b.dataset.seg); });
el('horizon').addEventListener('change', ()=>{ S.horizon = +el('horizon').value; invalidate(); rerender(); });
window.addEventListener('hashchange', ()=>{ const h = location.hash.slice(1); if(h !== cur.tab+'/'+cur.seg) routeFromHash(); });

/* ---------------- your team: asked once, remembered on this device ---------------- */
const initials = n => (n||'').split(/\s+/).filter(Boolean).slice(0,2).map(w=>w[0].toUpperCase()).join('') || '?';
function updateTeamPill(){
  const named = S.teamId && S.teamName;
  el('teamLabel').textContent = S.teamId ? (S.teamName || 'Team '+S.teamId) : 'Add team';
  el('teamAvatar').innerHTML = named ? esc(initials(S.teamName)) : '<svg aria-hidden="true" viewBox="0 0 32 32"><use href="#logo"/></svg>';
  el('teamBtn').setAttribute('aria-label', S.teamId ? 'Change team' : 'Add your team');
  if(cur.tab === 'home') syncHead();
}
function openLanding(){
  const L = el('landing');
  el('landId').value = isDemo() ? '' : (S.teamId || '');
  el('landErr').textContent = '';
  el('landQuip').textContent = quip('welcome');
  el('landSkip').textContent = S.teamId ? 'Cancel' : 'Just browsing';
  el('landDemo').hidden = isDemo();
  el('landGo').querySelector('.lbl').textContent = S.teamId ? 'Switch team' : 'Let’s go';
  if(!L.dataset.dressed){
    L.dataset.dressed = '1';
    Magic.ripple(el('landRipple'), 4, {size:86, step:30});
    Magic.orbit(el('landOrbit'), [{cls:'sat', size:7}, {cls:'sat m', size:6}], {radius:52, duration:9});
  }
  L.hidden = false; document.body.classList.add('landing-open');
  FX.landingIn(L);
  if(window.matchMedia && matchMedia('(hover:hover)').matches) setTimeout(()=>{ try{ el('landId').focus({preventScroll:true}); }catch(e){} }, 250);
}
function closeLanding(){
  if(el('landing').hidden) return;
  FX.landingOut(el('landing'), ()=>{ el('landing').hidden = true; document.body.classList.remove('landing-open'); });
}
function forgetTeam(){
  store.del('fplai_team'); store.del('fplai_team_name'); demoFlag(false);
  S.teamId = ''; S.teamName = ''; S.ready = null; S.lastSeg = {};
  updateTeamPill(); invalidate();
}
/* The first read of a saved team after a page load: fresh from FPL. Team views wait for it. */
function loadSavedTeam(){
  const id = S.teamId;
  return api(entryUrl(id)).then(ent=>{
    S.fresh = false; S.entry = ent;
    if(ent.entry && ent.entry.name && ent.entry.name !== S.teamName){ S.teamName = ent.entry.name; if(!isDemo()) store.set('fplai_team_name', S.teamName); updateTeamPill(); }
    return ent;
  }).catch(err=>{
    if(/no fpl team|not found|404/i.test(err.message)){
      forgetTeam(); openLanding();
      el('landErr').textContent = 'We couldn’t find team '+id+' any more. Check the number and try again.';
      go('home', 'picks');
    }
    return null;
  });
}
el('landForm').addEventListener('submit', async e=>{
  e.preventDefault();
  const id = el('landId').value.replace(/\D/g, '');
  if(!id){ el('landErr').textContent = 'Enter your Team ID — or tap “Just browsing”.'; FX.shake(el('landId')); return; }
  const btn = el('landGo'), label = btn.querySelector('.lbl').textContent;
  btn.disabled = true; btn.classList.add('busy'); btn.querySelector('.lbl').textContent = 'Finding your team…';
  try{
    S.fresh = true;
    const ent = await api(entryUrl(id));
    const isNew = id !== S.teamId;
    S.teamId = id; S.teamName = (ent.entry && ent.entry.name) || ('Team '+id); S.fresh = false; S.ready = null;
    store.set('fplai_team', id); store.set('fplai_team_name', S.teamName); demoFlag(false);
    updateTeamPill(); invalidate(); S.entry = ent;
    closeLanding();
    if(isNew) S.lastSeg = {};
    cur = {tab:'', seg:''}; go('home', 'squad');
    toast('Saved on this device. Next time it’s straight to your team.');
  }catch(err){
    el('landErr').textContent = /no fpl team|not found|404/i.test(err.message)
      ? 'We couldn’t find team '+id+'. Check the number and try again.'
      : 'Couldn’t load that team right now ('+err.message+').';
    FX.shake(el('landId'));
  }finally{ btn.disabled = false; btn.classList.remove('busy'); btn.querySelector('.lbl').textContent = label; }
});
el('landId').addEventListener('input', ()=>{ el('landErr').textContent = ''; });
/* The demo: a made-up team, not saved on the device (a team you've saved stays saved). */
el('landDemo').addEventListener('click', async ()=>{
  const btn = el('landDemo'), label = btn.textContent;
  btn.disabled = true; btn.textContent = 'Picking a team on vibes…';
  try{
    const ent = await api(`/api/entry/${DEMO}?horizon=${S.horizon}`);
    S.teamId = DEMO; S.teamName = ent.entry.name; S.fresh = false; S.ready = null; S.lastSeg = {};
    demoFlag(true);
    updateTeamPill(); invalidate(); S.entry = ent;
    closeLanding();
    cur = {tab:'', seg:''}; go('home', 'squad');
    toast('A made-up team, just to look around. Nothing is saved.');
  }catch(err){ el('landErr').textContent = 'Couldn’t load the demo right now ('+err.message+').'; }
  finally{ btn.disabled = false; btn.textContent = label; }
});
function exitDemo(){
  demoFlag(false);
  const saved = String(store.get('fplai_team', '') || '');
  S.teamId = saved; S.teamName = saved ? store.get('fplai_team_name', '') : '';
  S.ready = saved ? loadSavedTeam() : null; S.lastSeg = {};
  updateTeamPill(); invalidate();
  cur = {tab:'', seg:''}; go('home', saved ? 'squad' : 'picks');
  if(!saved) openLanding();
}
el('landSkip').addEventListener('click', ()=>{ closeLanding(); if(!S.teamId && cur.tab === 'home') go('home', 'picks'); });
el('teamBtn').addEventListener('click', openLanding);

/* ---------------- the menu: team, refresh, and how it works ---------------- */
function openMenu(){
  const root = el('sheet-root');
  root.innerHTML = `<div class="scrim" id="scrim"><div class="sheet" role="dialog" aria-modal="true" aria-label="Menu">
    <button class="btn sm x" id="closeSheet">Close ✕</button>
    <h2 class="menu-h">Papa Ranjeet</h2>
    <p class="menu-sub">${isDemo() ? 'You’re looking at the demo team, <b>'+esc(S.teamName)+'</b>. Nothing is saved.' : S.teamId ? 'Team <b>'+esc(S.teamName || S.teamId)+'</b> is saved on this device.' : 'No team saved on this device.'}</p>
    <div class="menu-actions">
      <button class="btn" id="mTeam">${icon('players')}<span>${isDemo() ? 'Use my own team' : S.teamId ? 'Change team' : 'Add team'}</span></button>
      <button class="btn" id="mRefresh">${icon('refresh')}<span>Refresh app</span></button>
      <button class="btn" id="mForget" ${S.teamId ? '' : 'disabled'}>${icon('forget')}<span>${isDemo() ? 'Leave the demo' : 'Forget team'}</span></button>
    </div>
    <div id="menuModel"></div></div></div>`;
  const close = ()=>{ root.innerHTML = ''; document.removeEventListener('keydown', onKey); };
  const onKey = e=>{ if(e.key === 'Escape') close(); };
  document.addEventListener('keydown', onKey);
  el('scrim').addEventListener('click', e=>{ if(e.target.id === 'scrim') close(); });
  el('closeSheet').onclick = close;
  el('mTeam').onclick = ()=>{ close(); openLanding(); };
  el('mRefresh').onclick = ()=>location.reload();       // the page is never stored, so this is always a clean load
  el('mForget').onclick = ()=>{ close(); if(isDemo()){ exitDemo(); return; } forgetTeam(); cur = {tab:'', seg:''}; go('home', 'picks'); openLanding(); };
  viewModel(el('menuModel'));
}
el('menuBtn').addEventListener('click', openMenu);

/* ---------------- little things ---------------- */
let toastTimer = 0;
function toast(text){
  el('toastTx').textContent = text; el('toast').classList.add('show');
  clearTimeout(toastTimer); toastTimer = setTimeout(()=>el('toast').classList.remove('show'), 3000);
}
let brandTaps = [];
document.querySelector('.brand').addEventListener('click', ()=>{
  go('home');
  const now = Date.now(); brandTaps = brandTaps.filter(t=>now - t < 1500); brandTaps.push(now);
  if(brandTaps.length >= 5){ brandTaps = []; toast('Houston, we have a GOAL. (That was the logo. Your team still needs work.)'); FX.burst(innerWidth/2, 80, 140); }
});
document.addEventListener('keydown', e=>{ if(e.key === 'Escape' && !el('landing').hidden && S.teamId) closeLanding(); });

/* ---------------- anonymous usage counts (backend/usage.py) ----------------
   One visit a day per browser and the name of each page opened — nothing else. The only
   thing kept on the device is the date it first opened the app (fplai_seen) and the day
   it last said hello (fplai_day); no ID, no cookie, no third-party script. A browser that
   asks not to be tracked (Do Not Track, Global Privacy Control) or that the owner switched
   off on the stats page (fplai_nocount) sends nothing. */
const noCount = () => !!store.get('fplai_nocount', false) || navigator.doNotTrack === '1' || navigator.globalPrivacyControl === true;
function beacon(body){
  if(noCount()) return;
  try{ fetch('/api/usage', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body), keepalive:true}).catch(()=>{}); }catch(e){}
}
function countVisit(){
  const d = new Date(), today = `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
  if(store.get('fplai_day', '') === today) return;
  const seen = store.get('fplai_seen', '');
  store.set('fplai_day', today);
  if(!seen) store.set('fplai_seen', today);
  beacon({kind:'visit', returning:!!seen, mode: isDemo() ? 'demo' : S.teamId ? 'team' : 'none'});
}
const countView = page => beacon({kind:'view', page});

/* The owner's stats page: open the app at #stats. It needs the STATS_KEY set on the
   server; the key is kept on this device once it works. Not a tab, not in the menu. */
const pageName = id => { const [t, s] = id.split('/'); const tab = TABS.find(x=>x.id===t); const seg = tab && tab.segs.find(x=>x.id===s);
  return tab ? tab.label + (tab.segs.length > 1 && seg ? ' › ' + seg.label : '') : id; };
async function openStats(){
  const root = el('sheet-root');
  root.innerHTML = `<div class="scrim" id="scrim"><div class="sheet" role="dialog" aria-modal="true" aria-label="Stats"><div id="stBody"></div></div></div>`;
  const close = ()=>{ root.innerHTML = ''; document.removeEventListener('keydown', onKey); };
  const onKey = e=>{ if(e.key === 'Escape') close(); };
  document.addEventListener('keydown', onKey);
  el('scrim').addEventListener('click', e=>{ if(e.target.id === 'scrim') close(); });
  const body = el('stBody');
  const head = sub => `<button class="btn sm x" id="closeSheet">Close ✕</button><h2 class="menu-h">Who’s using the app</h2><p class="menu-sub">${sub}</p>`;
  const wire = ()=>{ el('closeSheet').onclick = close; };
  const ask = msg => {
    body.innerHTML = head('Anonymous counts for the owner. Enter the stats key set on the server (STATS_KEY).') +
      `${msg ? `<div class="err">${esc(msg)}</div>` : ''}
      <form class="controls" id="stForm" autocomplete="off"><label class="fld">Stats key<input id="stKey" type="password" autocomplete="current-password"></label>
        <button class="btn primary" type="submit">Show stats</button></form>`;
    wire();
    el('stForm').onsubmit = ev=>{ ev.preventDefault(); const k = el('stKey').value.trim(); if(k){ store.set('fplai_stats_key', k); load(); } };
    setTimeout(()=>{ try{ el('stKey').focus(); }catch(e){} }, 50);
  };
  const load = async ()=>{
    const key = store.get('fplai_stats_key', '');
    if(!key) return ask('');
    body.innerHTML = head('Counting…') + loading('Reading the counts');
    wire();
    let d;
    try{
      const r = await fetch('/api/stats?days=30', {cache:'no-store', headers:{'X-Stats-Key': key}});
      if(!r.ok){ let m = ''; try{ m = (await r.json()).detail; }catch(e){} if(r.status === 403) store.del('fplai_stats_key'); return ask(m || ('Request failed ('+r.status+')')); }
      d = await r.json();
    }catch(e){ body.innerHTML = head('') + errBox(e); wire(); return; }
    const P = d.period, W = d.week, T = d.today, pct = (a, b) => b ? Math.round(100 * a / b) + '%' : '–';
    const max = Math.max(1, ...d.days.map(x=>x.visits));
    const list = (rows, label) => rows.length ? `<div class="well"><table><tbody>${rows.map(r=>`<tr>
        <td>${esc(label(r.name))}</td><td style="width:42%"><span class="st-meter"><i style="width:${Math.max(4, 100 * r.count / rows[0].count)}%"></i></span></td>
        <td class="num"><b>${r.count.toLocaleString()}</b></td></tr>`).join('')}</tbody></table></div>` : '<p class="dim">Nothing yet.</p>';
    const off = noCount();
    body.innerHTML = head(`Anonymous counts since ${esc(d.since || '—')}: one visit a day per browser, no names, IDs or cookies.`) + `
      <div class="grid g4 mb">
        ${tile('Visitors today', T.visits, `${T.new} new · ${T.returning} returning`)}
        ${tile('Last 7 days', W.visits, `${W.new} new · ${W.returning} returning`)}
        ${tile(`Last ${d.period_days} days`, P.visits, `${pct(P.returning, P.visits)} returning`)}
        ${tile('Real team vs demo', pct(P.modes.team || 0, P.visits), `${P.modes.team || 0} real · ${P.modes.demo || 0} demo · ${P.modes.none || 0} no team yet`)}
      </div>
      <div class="card mb"><h3>Visitors a day <span class="r"><i class="st-key new"></i>new <i class="st-key ret"></i>returning</span></h3>
        <div class="st-bars" role="img" aria-label="Visitors a day for the last ${d.period_days} days">${d.days.map(x=>`
          <div class="st-bar" title="${x.day}: ${x.visits} visitor${x.visits===1?'':'s'} (${x.new} new)"><i class="ret" style="height:${100 * (x.visits - x.new) / max}%"></i><i class="new" style="height:${100 * x.new / max}%"></i></div>`).join('')}
        </div>
        <div class="st-axis"><span>${esc(d.days[0].day)}</span><span>today</span></div></div>
      <div class="grid g2 mb">
        <div class="card"><h3>Pages opened <span class="r">${d.period_days} days</span></h3>${list(P.views, pageName)}</div>
        <div class="card"><h3>Features used <span class="r">${d.period_days} days</span></h3>${list(P.features, n => n)}</div>
      </div>
      <div class="legend">${d.persistent ? 'Counts are kept on the server’s volume and survive deploys.'
        : 'These counts start again on every deploy. To keep them, attach a Railway volume and set STATS_DIR to its path.'}
        Days are UTC. Browsers that ask not to be tracked are never counted.</div>
      <div class="controls" style="margin-top:14px">
        <button class="btn" id="stSelf" aria-pressed="${off}">${off ? 'This browser isn’t counted' : 'Don’t count this browser'}</button>
        <button class="btn" id="stForget">Forget the key</button></div>`;
    wire();
    el('stSelf').onclick = ()=>{ const now = !store.get('fplai_nocount', false); if(now) store.set('fplai_nocount', true); else store.del('fplai_nocount'); load(); };
    el('stForget').onclick = ()=>{ store.del('fplai_stats_key'); ask(''); };
  };
  load();
}

/* ---------------- boot ---------------- */
buildChrome();
FX.start();
FX.observe(el('views'));
(async function boot(){
  S.horizon = +el('horizon').value;
  const saved = String(store.get('fplai_team', '') || '');
  let demo = false; try{ demo = sessionStorage.getItem('fplai_demo') === '1'; }catch(e){}
  if(demo){                                 // still looking round the demo in this tab (e.g. after the app reloaded itself)
    S.teamId = DEMO; S.teamName = 'Demo team';
    S.ready = loadSavedTeam();
  }else if(saved){
    S.teamId = saved; S.teamName = store.get('fplai_team_name', '');
    S.ready = loadSavedTeam();              // straight to your team; no question asked
  }
  updateTeamPill();
  countVisit();
  routeFromHash();
  if(!saved && !demo) openLanding();        // first visit on this device: who are you?
  try{
    S.meta = S.meta || await api('/api/meta');
    const ev = S.meta.events.find(x=>x.id===S.meta.next_gw);
    const dl = ev ? new Date(ev.deadline) : null;
    syncHead();
    el('rail-foot').textContent = `GW${S.meta.next_gw} deadline · ${dl?dl.toLocaleString([], {weekday:'short', day:'numeric', month:'short', hour:'2-digit', minute:'2-digit'}):'—'}`;
  }catch(e){ el('rail-foot').textContent = 'Model offline'; }
})();

/* Fresh on every open. The server stamps each page with a build id; when the
   app returns to the foreground (switching tabs, reopening the home-screen app,
   restoring from the back/forward cache) we ask for the current build and
   reload if a newer one has shipped. Checks are throttled to one a minute.
   Come back after a long absence and your squad, bank and transfers are re-read
   from FPL too, so a transfer made on the FPL site is never missing. */
const STALE_AFTER = 10 * 60 * 1000;
async function softRefresh(){
  S.meta = null; S.fresh = true;
  if(S.teamId){
    try{ await api(entryUrl(S.teamId)); S.fresh = false; }catch(e){ /* offline: show what we have */ }
  }
  invalidate(); rerender();
}
(function freshness(){
  const meta = document.querySelector('meta[name="app-build"]');
  const mine = meta && meta.content;
  let last = 0, reloading = false, hiddenAt = 0;
  async function check(){
    if(!mine || reloading || Date.now() - last < 60000) return;
    last = Date.now();
    try{
      const r = await fetch('/version', {cache:'no-store'});
      if(!r.ok) return;
      const {build} = await r.json();
      if(build && build !== mine){ reloading = true; location.reload(); }
    }catch(e){ /* offline: keep what we have */ }
  }
  function back(){
    check();
    if(hiddenAt && Date.now() - hiddenAt > STALE_AFTER && !reloading){ hiddenAt = 0; softRefresh(); }
  }
  document.addEventListener('visibilitychange', ()=>{
    if(document.visibilityState === 'hidden'){ hiddenAt = Date.now(); }
    else back();
  });
  window.addEventListener('pageshow', e=>{
    if(e.persisted){ last = 0; location.reload(); }         // restored from the back/forward cache: start clean
  });
  window.addEventListener('focus', check);
})();
