/* FPL AI — frontend. Plain JS, no build step. */
'use strict';

const store = {
  get(k, d){ try{ const v = localStorage.getItem(k); return v==null ? d : JSON.parse(v); }catch(e){ return d; } },
  set(k, v){ try{ localStorage.setItem(k, JSON.stringify(v)); }catch(e){} }
};

const S = {
  teamId: store.get('fplai_team', ''),
  horizon: 5,
  overrides: store.get('fplai_minutes', {}),   // {playerId: minutes} - your own numbers
  entry: null, meta: null, loaded: {}
};

const el  = id => document.getElementById(id);
const POS = {1:'GKP',2:'DEF',3:'MID',4:'FWD'};
const esc = s => String(s==null?'':s).replace(/[&<>"]/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const num = (v,d=2) => (v==null||isNaN(v)) ? '–' : Number(v).toFixed(d);
const sign = (v,d=2) => (v>0?'+':'') + num(v,d);

const TITLES = {
  dashboard:['Dashboard','Your squad, projected forward, and this week’s standout picks.'],
  xpts:['Expected Points','Every player across the coming gameweeks. Click any minutes figure to set your own — every tool then uses it.'],
  solver:['Solver','Plans transfers, captaincy and line-ups across the whole horizon at once, and shows you the next-best routes too.'],
  chips:['Chip Strategy','Each chip scored in every gameweek, then combined into the best overall plan.'],
  copilot:['Copilot','Ask a question in plain English. Every answer is read straight off the model, so you can check the numbers behind it.'],
  rate:['Rate My Team','Your squad scored out of 100, with the fixes that move the score most.'],
  compare:['Compare Players','Two players side by side on projections, underlying numbers and fixtures.'],
  league:['Mini-Leagues','What your rivals own, who they captain, and how likely each of you is to win.'],
  scout:['Scout','Price moves, set-piece duties, defensive-contribution leaders and predicted line-ups.'],
  model:['How It Works','The data, the rules and the maths behind every number here.']
};

async function api(path, opts){
  const r = await fetch(path, opts);
  if(!r.ok){
    let m; try{ m = (await r.json()).detail; }catch(e){ m = r.statusText; }
    throw new Error(m || ('Request failed ('+r.status+')'));
  }
  return r.json();
}
const post = (path, body) => api(path, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
const ovParam = () => Object.entries(S.overrides).map(([k,v])=>k+':'+v).join(',');
const ovQuery = () => { const o = ovParam(); return o ? '&overrides='+encodeURIComponent(o) : ''; };

const loading = t => `<div class="card"><div class="loading">${esc(t||'Working')}</div></div>`;
const errBox  = e => `<div class="err"><b>That didn’t work.</b> ${esc(e.message||e)}</div>`;
const pos  = p => `<span class="pill pos${p}">${POS[p]}</span>`;
const fdr  = f => `<span class="fdr fdr${f}">${f}</span>`;
const flag = p => p.status && p.status!=='a' ? `<span class="dot" title="${esc(p.news||'Flagged')}"></span>` : '';
const tile = (lbl, val, sub, cls='') => `<div class="tile"><div class="lbl">${lbl}</div><div class="val ${cls}">${val}</div><div class="sub">${sub||''}</div></div>`;

function needTeam(){
  if(S.teamId) return null;
  return `<div class="card" style="max-width:640px">
    <h3>Team ID needed</h3>
    <p style="margin:0 0 10px;color:var(--ink-2)">Enter your FPL Team ID at the top and press <b>Load team</b>.</p>
    <div class="note">Find it on the FPL site under <b>Points</b> — it’s the number in the address bar:
      <code>fantasy.premierleague.com/entry/<b>1234567</b>/event/5</code></div></div>`;
}

/* ---------------- navigation ---------------- */
let current = 'dashboard';
function go(view){
  current = view;
  document.querySelectorAll('#nav button').forEach(b=>b.classList.toggle('on', b.dataset.view===view));
  document.querySelectorAll('.view').forEach(v=>v.classList.toggle('on', v.id==='view-'+view));
  el('view-title').textContent = TITLES[view][0];
  el('view-sub').textContent   = TITLES[view][1];
  render(view);
  window.scrollTo({top:0, behavior:'smooth'});
}
el('nav').addEventListener('click', e=>{
  const b = e.target.closest('button[data-view]'); if(b) go(b.dataset.view);
});
function invalidate(){ S.loaded = {}; S.entry = null; }
el('load').addEventListener('click', ()=>{
  S.teamId = el('teamId').value.trim(); store.set('fplai_team', S.teamId);
  invalidate(); render(current);
});
el('teamId').addEventListener('keydown', e=>{ if(e.key==='Enter') el('load').click(); });
el('horizon').addEventListener('change', ()=>{ S.horizon = +el('horizon').value; invalidate(); render(current); });

function render(view){
  const key = [view, S.horizon, S.teamId, ovParam()].join('|');
  if(S.loaded[view] === key) return;
  S.loaded[view] = key;
  VIEWS[view](el('view-'+view));
}

/* ---------------- shared drawing ---------------- */
function spark(vals){
  const mx = Math.max(...vals, 0.1);
  return `<div class="spark">${vals.map(v=>`<i style="height:${Math.max(8, v/mx*100)}%" title="${num(v)}"></i>`).join('')}</div>`;
}

/* ---------------- Shirts & pitch ---------------- */
/* Plain shirt shapes tinted in each club's colours — no crests, sponsors or kit designs. */
const KIT = {ARS:['#DB1F2B','#FFFFFF'], AVL:['#76203F','#9CC3E8'], BHA:['#1A5FBF','#FFFFFF'], BOU:['#C9252C','#1B1B1B'],
  BRE:['#DA2128','#FFFFFF'], CHE:['#1149A3','#FFFFFF'], COV:['#73B7E3','#FFFFFF'], CRY:['#1E4A92','#C42234'],
  EVE:['#1D42A0','#FFFFFF'], FUL:['#F3F5F8','#1B1B1B'], HUL:['#F0A23A','#1B1B1B'], IPS:['#2F5DA9','#FFFFFF'],
  LEE:['#F3F5F8','#1F4590'], LIV:['#C41230','#E9E2CF'], MCI:['#80BBE6','#FFFFFF'], MUN:['#CF2A21','#FFFFFF'],
  NEW:['#1D1D1D','#F3F5F8'], NFO:['#C9232B','#FFFFFF'], SUN:['#D9252F','#FFFFFF'], TOT:['#F3F5F8','#17275E']};
const GK_KIT = ['#E7C83C','#2C3E57'];
function shirt(team, isGk){
  const [body, trim] = isGk ? GK_KIT : (KIT[team] || ['#3A86FF','#FFFFFF']);
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
  const tok = p => `<div class="pl-tok" onclick="openPlayer(${p.id})" title="${esc(p.web_name)} · £${num(p.price,1)}m">
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

/* ---------------- Dashboard ---------------- */
async function viewDashboard(t){
  t.innerHTML = loading('Projecting the gameweek');
  try{
    const [picks, meta] = await Promise.all([api(`/api/picks?horizon=${S.horizon}`), S.meta ? S.meta : api('/api/meta')]);
    S.meta = meta;
    const lastGw = meta.events.find(e=>e.id===meta.current_gw) || {};
    let head = '';
    if(S.teamId){
      const e = await api(`/api/entry/${S.teamId}?horizon=${S.horizon}${ovQuery()}`);
      S.entry = e;
      const last = e.history.length ? e.history[e.history.length-1] : null;
      const vsAvg = last && lastGw.average!=null ? last.points - lastGw.average : null;
      head = `
      <div class="grid g4 mb">
        ${tile('Overall rank', e.entry.overall_rank ? e.entry.overall_rank.toLocaleString() : '–', esc(e.entry.name||''))}
        ${tile('GW'+e.gw+' score', last ? last.points : '–',
               vsAvg==null ? 'Average not out yet' : `<span class="${vsAvg>=0?'up':'down'}">${sign(vsAvg,0)}</span> vs the ${lastGw.average}-point average`)}
        ${tile('Squad value', '£'+num(e.entry.value,1)+'m', '£'+num(e.bank,1)+'m in the bank')}
        ${tile('Free transfers', e.free_transfers, (()=>{ const av=(e.chips_available||{})[e.next_gw]||[]; const N={wildcard:'WC',freehit:'FH',bboost:'BB','3xc':'TC'}; return av.length ? 'Chips now: '+av.map(c=>N[c]).join(' · ') : 'No chips until GW20'; })())}
      </div>
      <div class="grid g23 mb">
        <div class="card">
          <h3>Best XI for GW${e.next_gw} <span class="r">${e.formation} · ${num(e.xi_xpts)} xPts</span></h3>
          ${pitch(e.starting_xi, e.bench, e.captain, e.starting_xi.filter(p=>!e.captain||p.id!==e.captain.id).sort((a,b)=>b.xpts-a.xpts)[0])}
          <div class="legend">Captain <b>${e.captain?esc(e.captain.web_name):'–'}</b> adds another ${e.captain?num(e.captain.xpts):'0'}.
            Bench projects ${num(e.bench_xpts)}; G is the reserve keeper, 1–3 the order outfielders come on.</div>
        </div>
        <div class="card">
          <h3>Your fifteen over ${S.horizon} gameweeks</h3>
          <div class="well"><table><thead><tr>
            <th>Player</th><th></th><th class="num">£</th><th class="num">GW${e.next_gw}</th><th class="num">${S.horizon}GW</th><th>Trend</th>
          </tr></thead><tbody>
          ${e.squad.slice().sort((a,b)=>b.xpts_total-a.xpts_total).map(p=>`<tr onclick="openPlayer(${p.id})" style="cursor:pointer">
            <td><span class="nm">${esc(p.web_name)}</span>${flag(p)}<div class="u2">${esc(p.team_short)}</div></td>
            <td>${pos(p.position)}</td><td class="num">${num(p.price,1)}</td>
            <td class="num accent"><b>${num(p.xpts)}</b></td><td class="num">${num(p.xpts_total,1)}</td>
            <td style="width:76px">${spark(p.per_gw.map(g=>g.xpts))}</td></tr>`).join('')}
          </tbody></table></div>
        </div>
      </div>`;
    } else {
      head = `<div class="card mb"><h3>Start here</h3>
        <p style="margin:0;color:var(--ink-2)">Add your Team ID at the top to load your squad, run the solver and grade your team.
        Everything else on this page works without one.</p></div>`;
    }

    const pulse = `<div class="grid g4 mb">
      ${tile('GW'+meta.current_gw+' average', lastGw.average ?? '–', 'Highest score: '+(lastGw.highest ?? '–'))}
      ${tile('Most captained', esc(lastGw.most_captained||'–'), 'Most owned: '+esc(lastGw.most_selected||'–'))}
      ${tile('Player of the week', esc(lastGw.top_player||'–'), lastGw.top_player_points!=null ? lastGw.top_player_points+' points' : '')}
      ${tile('Most bought', esc(lastGw.most_transferred_in||'–'), lastGw.transfers_made ? (lastGw.transfers_made/1e6).toFixed(1)+'m transfers made' : '')}
    </div>`;

    const list = (rows, right, sub) => `<div class="well"><table><tbody>${rows.map((p,i)=>`
      <tr onclick="openPlayer(${p.id})" style="cursor:pointer">
        <td style="width:20px" class="dim">${i+1}</td>
        <td><span class="nm">${esc(p.web_name)}</span>${flag(p)}<div class="u2">${esc(p.team_short)} · £${num(p.price,1)}m</div></td>
        <td>${pos(p.position)}</td>${right(p)}</tr>`).join('')}</tbody></table></div>${sub?`<div class="legend">${sub}</div>`:''}`;

    t.innerHTML = head + pulse + `
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
const XP = { limit: 40, offset: 0 };
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
          <option value="value">xPts per £m</option><option value="ownership">Ownership</option></select></label>
        <label class="fld">Show<select id="fFdr"><option value="xp">xPts</option><option value="fdr">Fixtures</option></select></label>
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

  if(el('resetMins')) el('resetMins').onclick = ()=>{ S.overrides = {}; store.set('fplai_minutes', {}); invalidate(); render('xpts'); };
  XP.offset = 0; XP.limit = 40;
  const run = async (append)=>{
    const q = new URLSearchParams({horizon:S.horizon, sort:el('fSort').value, limit:XP.limit, offset:XP.offset});
    ['fPos:position','fTeam:team','fPrice:max_price','fSearch:search'].forEach(pair=>{
      const [id,key] = pair.split(':'); if(el(id).value) q.set(key, el(id).value);
    });
    const ov = ovParam(); if(ov) q.set('overrides', ov);
    if(!append) el('xpTable').innerHTML = loading('Projecting');
    try{
      const d = await api('/api/players?'+q);
      const gws = d.players.length ? d.players[0].per_gw.map(g=>g.gw) : [];
      const showFdr = el('fFdr').value === 'fdr';
      const rowHtml = p => {
        const firstMins = (p.per_gw[0] && p.per_gw[0].fixtures[0]) ? p.per_gw[0].fixtures[0].xmins : 0;
        const edited = S.overrides[p.id] != null;
        return `<tr>
          <td><a href="#" onclick="openPlayer(${p.id});return false" class="nm" style="color:var(--ink)">${esc(p.web_name)}</a>${flag(p)}
              <div class="u2">${esc(p.team_short)} · ${POS[p.position]} · £${num(p.price,1)}m · ${num(p.selected_by_percent,1)}%</div></td>
          ${p.per_gw.map(g=>{
            if(g.blank) return `<td class="num dim">—</td>`;
            if(showFdr) return `<td class="num">${g.fixtures.map(f=>`${fdr(f.fdr)} <span class="u2" style="display:inline">${esc(f.opponent_short)}${f.home?'':'·a'}</span>`).join('<br>')}</td>`;
            const v = g.xpts, hot = v >= 6 ? 'font-weight:800;color:var(--accent-deep)' : v >= 4.5 ? 'font-weight:700' : '';
            return `<td class="num" title="${esc(g.fixtures.map(f=>f.opponent_short+(f.home?' (H)':' (A)')).join(', '))}" style="${hot}">${num(v,1)}${g.double?'<sup class="accent">2</sup>':''}</td>`;
          }).join('')}
          <td class="num"><span class="mins ${edited?'set':''}" data-pid="${p.id}" title="${edited?'Your number — click to change':'Click to set your own minutes'}">${num(edited?S.overrides[p.id]:firstMins,0)}′ ✎</span></td>
          <td class="num accent"><b>${num(p.xpts_total,1)}</b></td></tr>`;
      };
      const body = d.players.map(rowHtml).join('');
      if(append && el('xpBody')){
        el('xpBody').insertAdjacentHTML('beforeend', body);
      } else {
        const ago = d.updated ? Math.max(0, Math.round((Date.now()/1000 - d.updated)/60)) : null;
        el('xpTable').innerHTML = `<div class="card pad-0">
          <h3>${d.count} players <span class="r">${ago!=null?'Model rebuilt '+(ago<1?'just now':ago+' min ago'):''}</span></h3>
          <div class="well flush" style="max-height:none"><table><thead><tr>
            <th>Player</th>${gws.map(g=>`<th class="num">GW${g}</th>`).join('')}<th class="num">Mins</th><th class="num">Total</th>
          </tr></thead><tbody id="xpBody">${body}</tbody></table></div>
          <div style="padding:12px 20px;display:flex;gap:9px;align-items:center;flex-wrap:wrap" id="xpMore"></div></div>`;
      }
      const shown = XP.offset + d.players.length;
      el('xpMore').innerHTML = shown < d.count
        ? `<button class="btn sm" id="moreBtn">Show 40 more</button><button class="btn sm" id="allBtn">Show all ${d.count}</button><span class="sub">${shown} of ${d.count}</span>`
        : `<span class="sub">All ${d.count} shown.</span>`;
      if(el('moreBtn')) el('moreBtn').onclick = ()=>{ XP.offset = shown; XP.limit = 40; run(true); };
      if(el('allBtn'))  el('allBtn').onclick  = ()=>{ XP.offset = shown; XP.limit = d.count; run(true); };
    }catch(e){ el('xpTable').innerHTML = errBox(e); }
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
      store.set('fplai_minutes', S.overrides); invalidate(); render('xpts');
    };
    inp.addEventListener('keydown', k=>{ if(k.key==='Enter') commit(); if(k.key==='Escape') render('xpts'); });
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
      ${p.news?`<div class="note">${esc(p.news)}</div>`:''}
      <div class="grid g4 mb">
        ${tile('Next GW', num(p.xpts_next), 'FPL’s own estimate: '+num(p.fpl_ep_next))}
        ${tile(S.horizon+' gameweeks', num(p.xpts_total,1), num(p.xpts_total/S.horizon)+' a week')}
        ${tile('Expected minutes', num(mm.xmins,0)+'′', 'Start chance '+num(mm.p_start*100,0)+'%')}
        ${tile('Minutes when starting', num(mm.starter_minutes,0)+'′', mm.recent_trend==null?'':'Recent vs season: '+sign(mm.recent_trend,0)+'′')}
      </div>
      <div class="grid g3">
        <div class="card"><h3>Fixtures</h3><div class="well"><table><tbody>
          ${p.per_gw.map(g=>`<tr><td class="dim">GW${g.gw}</td>
            <td>${g.fixtures.map(f=>`${fdr(f.fdr)} ${esc(f.opponent_short)} <span class="u2" style="display:inline">${f.home?'home':'away'} · ${num(f.xmins,0)}′</span>`).join('<br>')||'<span class="dim">No fixture</span>'}</td>
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
  }catch(e){ root.querySelector('.sheet').innerHTML = errBox(e); }
};

/* ---------------- Solver workspace ---------------- */
const SV = { key:null, r:null, path:0, gw:0 };
async function viewSolver(t){
  const n = needTeam(); if(n){ t.innerHTML = n; return; }
  const hOpts = [1,3,5,6,8,10].map(h=>`<option value="${h}" ${h===S.horizon?'selected':''}>${h} GW</option>`).join('');
  t.innerHTML = `<div class="ws">
    <div class="ws-left" id="svLeft"><div class="skel" style="height:86px;margin-bottom:16px"></div><div class="skel" style="height:640px;border-radius:24px"></div></div>
    <div class="ws-right">
      <div class="ws-controls">
        <select id="sPaths" title="How many alternative plans"><option value="1">1 Path</option><option value="2">2 Paths</option><option value="3" selected>3 Paths</option></select>
        <select id="sH" title="Planning horizon">${hOpts}</select>
        <select id="sHits" title="Hits allowed"><option value="0">No hits</option><option value="1" selected>≤ 1 hit</option><option value="2">≤ 2 hits</option><option value="3">≤ 3 hits</option></select>
        <details class="adv" id="adv"><summary>Advanced settings</summary><div class="adv-body">
          <label class="fld">Wildcard in<select id="sWC"><option value="">Not this window</option></select></label>
          <label class="fld">Free Hit in<select id="sFH"><option value="">Not this window</option></select></label>
          <label class="fld">Free transfers<input id="sFT" type="number" min="1" max="5" placeholder="Auto from your history"></label>
          <div class="sub">${Object.keys(S.overrides).length ? 'Using your '+Object.keys(S.overrides).length+' minute edit(s) from Expected Points.' : 'Edit any player’s minutes in Expected Points and the solver will use them.'}</div>
        </div></details>
      </div>
      <button class="cta" id="runSolve"><svg viewBox="0 0 24 24" fill="#fff"><path d="M7 4.5v15l12.5-7.5z"/></svg>Suggest transfers</button>
      <div id="svRight"><div class="skel" style="height:70px;margin:22px 0 18px"></div><div class="skel" style="height:96px;margin-bottom:12px"></div><div class="skel" style="height:300px"></div></div>
    </div></div>`;

  let e;
  try{
    e = S.entry || await api(`/api/entry/${S.teamId}?horizon=${S.horizon}${ovQuery()}`); S.entry = e;
    for(let i=0;i<S.horizon;i++){
      const g = e.next_gw+i, o = `<option value="${g}">GW${g}</option>`, av = (e.chips_available||{})[g] || [];
      if(av.includes('wildcard')) el('sWC').insertAdjacentHTML('beforeend', o);
      if(av.includes('freehit'))  el('sFH').insertAdjacentHTML('beforeend', o);
    }
  }catch(err){ el('svRight').innerHTML = errBox(err); el('svLeft').innerHTML=''; return; }

  const markAdv = ()=> el('adv').dataset.active = (el('sWC').value||el('sFH').value||el('sFT').value) ? '1' : '0';
  ['sWC','sFH','sFT'].forEach(id=>el(id).addEventListener('change', markAdv));
  el('sH').addEventListener('change', ()=>{ S.horizon = +el('sH').value; el('horizon').value = S.horizon; invalidate(); render('solver'); });

  const run = async ()=>{
    const body = {team_id:+S.teamId, horizon:S.horizon, max_hits:+el('sHits').value, paths:+el('sPaths').value};
    if(el('sWC').value) body.wildcard_gw = +el('sWC').value;
    if(el('sFH').value) body.free_hit_gw = +el('sFH').value;
    if(el('sFT').value) body.free_transfers = +el('sFT').value;
    const ov = ovParam(); if(ov) body.overrides = ov;
    const key = JSON.stringify(body);
    el('adv').open = false;
    if(SV.key === key && SV.r){ draw(); return; }
    el('runSolve').disabled = true;
    el('runSolve').innerHTML = 'Optimising '+S.horizon+' gameweeks…';
    el('svLeft').innerHTML = `<div class="skel" style="height:86px;margin-bottom:16px"></div><div class="skel" style="height:640px;border-radius:24px"></div>`;
    el('svRight').innerHTML = `<div class="skel" style="height:70px;margin:22px 0 18px"></div><div class="skel" style="height:96px;margin-bottom:12px"></div><div class="skel" style="height:300px"></div>`;
    try{
      SV.r = await post('/api/solve', body); SV.key = key; SV.path = 0; SV.gw = 0;
      draw();
    }catch(err){ el('svRight').innerHTML = errBox(err); el('svLeft').innerHTML = ''; }
    el('runSolve').disabled = false;
    el('runSolve').innerHTML = '<svg viewBox="0 0 24 24" fill="#fff"><path d="M7 4.5v15l12.5-7.5z"/></svg>Suggest transfers';
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
        ${r.paths.map((x,i)=>`<button class="path ${i===SV.path?'on':''}" data-k="${i}">
          <div class="pl">${x.label}</div><div class="pv">${num(x.total_xpts,1)}</div>
          <div class="ps">${i===0?'best found':(Math.abs(x.total_xpts-best)<0.05?'level':sign(x.total_xpts-best,1))} · ${x.total_hits?'−'+(x.total_hits*4):'no hits'}</div></button>`).join('')}
      </div>
      ${pitch(g.starting_xi, g.bench, g.captain, g.vice_captain, {header, ins: g.transfers_in.map(x=>x.id)})}`;
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
              return `<div class="tl-move"><span class="o">${po?esc(po.web_name):'–'}</span><span class="arr">→</span><span class="i">${esc(pin.web_name)}</span></div>`; }).join('')
            : '<div class="tl-roll">Roll</div>'}</div></div>`).join('')}
      </div></div>
      <div class="legend">Captain ${esc(p.gameweeks[SV.gw].captain?p.gameweeks[SV.gw].captain.web_name:'–')}, vice ${esc(p.gameweeks[SV.gw].vice_captain?p.gameweeks[SV.gw].vice_captain.web_name:'–')} in GW${p.gameweeks[SV.gw].gw}.
        Template rating compares your planned XI’s ownership with the eleven most-owned players: 100 is pure template, low is differential.
        Plans are within 0.5% of the best possible; ${r.pool_size} players searched.</div>`;
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
  t.innerHTML = loading('Scoring every chip in every gameweek — the Wildcard re-solves take around half a minute');
  try{
    const body = {team_id:+S.teamId, horizon:S.horizon}; const ov = ovParam(); if(ov) body.overrides = ov;
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
        ${S.teamId?'Answering for team <b>'+esc(S.teamId)+'</b>.':'Add a Team ID for answers about your own squad.'}</div>
    </div>
    <div id="ans"></div>`;
  const ask = async q=>{
    if(!q) return; el('q').value = q;
    el('ans').innerHTML = loading('Working it out');
    try{
      const body = {question:q, horizon:S.horizon}; if(S.teamId) body.team_id = +S.teamId;
      const ov = ovParam(); if(ov) body.overrides = ov;
      const r = await post('/api/copilot', body);
      const needsTeam = !r.has_team && ['hit','transfer','rate','chip','bench'].includes(r.intent);
      el('ans').innerHTML = `<div class="grid g23">
        <div><div class="bubble">${esc(r.answer)}</div>
          ${r.points.length?`<div class="card" style="margin-top:14px"><h3>Why</h3>${r.points.map(p=>`<div class="note">${esc(p)}</div>`).join('')}</div>`:''}
          ${needsTeam?'<div class="note" style="margin-top:12px">Load your Team ID to get this answer for your own squad.</div>':''}</div>
        <div>${r.table?`<div class="card"><h3>${esc(r.table.title)}</h3><div class="well"><table>
            <thead><tr>${r.table.columns.map((c,i)=>`<th class="${i>1?'num':''}">${esc(c)}</th>`).join('')}</tr></thead>
            <tbody>${r.table.rows.map(row=>`<tr>${row.map((c,i)=>`<td class="${i>1?'num':''}">${esc(c)}</td>`).join('')}</tr>`).join('')}</tbody></table></div></div>`:''}
          <div class="legend">Read as a question about: <span class="tag">${esc(r.intent)}</span></div></div></div>`;
    }catch(e){ el('ans').innerHTML = errBox(e); }
  };
  el('askBtn').onclick = ()=>ask(el('q').value.trim());
  el('q').addEventListener('keydown', e=>{ if(e.key==='Enter') ask(el('q').value.trim()); });
  t.querySelector('.chipset').addEventListener('click', e=>{ const b = e.target.closest('button'); if(b) ask(b.dataset.q); });
}

/* ---------------- Rate my team ---------------- */
async function viewRate(t){
  const n = needTeam(); if(n){ t.innerHTML = n; return; }
  t.innerHTML = loading('Grading your squad');
  try{
    const r = await api(`/api/rate/${S.teamId}?horizon=${S.horizon}${ovQuery()}`);
    const LBL = {projection:'Projected points',structure:'Line-up strength',bench:'Bench cover',fitness:'Fitness',value:'Value for money'};
    t.innerHTML = `
      <div class="grid g3 mb">
        <div class="card" style="text-align:center;padding:26px 20px">
          <h3 style="justify-content:center">${esc(r.entry.name||'Your team')}</h3>
          <div class="grade">${esc(r.grade)}</div>
          <div style="font-size:30px;font-weight:700;letter-spacing:-.03em;margin-top:8px">${num(r.overall,0)}<span class="dim" style="font-size:16px"> / 100</span></div>
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
        <div class="card"><h3>Fix these first</h3>${r.notes.map(x=>`<div class="note">${esc(x)}</div>`).join('')}</div>
        <div class="card"><h3>Moves that raise the score</h3>
          <div class="well"><table><thead><tr><th>Out</th><th>In</th><th class="num">Gain</th></tr></thead><tbody>
          ${r.top_upgrades.map(u=>`<tr>
            <td><span class="down nm">${esc(u.out.web_name)}</span><div class="u2">${esc(u.out.team_short)} · £${num(u.out.price,1)}m · ${num(u.out.xpts_total,1)}</div></td>
            <td><span class="up nm">${esc(u.in.web_name)}</span><div class="u2">${esc(u.in.team_short)} · £${num(u.in.price,1)}m · ${num(u.in.xpts_total,1)}</div></td>
            <td class="num up"><b>${sign(u.gain,1)}</b></td></tr>`).join('') || '<tr><td colspan="3" class="sub">No clear upgrade within budget.</td></tr>'}
          </tbody></table></div>
          <div class="legend">Extra xPts over ${S.horizon} gameweeks, affordable with your current bank.</div></div>
      </div>`;
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
async function viewLeague(t){
  t.innerHTML = `<div class="card mb"><div class="controls">
      <label class="fld">League ID<input id="lgId" type="number" placeholder="e.g. 314" style="width:136px" value="${esc(store.get('fplai_league',''))}"></label>
      <label class="fld">Rivals<select id="lgN"><option>6</option><option selected>12</option><option>20</option></select></label>
      <button class="btn primary" id="lgGo">Analyse</button></div>
      <div class="legend">The league ID is in the address bar on your league page:
        <code>fantasy.premierleague.com/leagues/<b>123456</b>/standings/c</code>. Try 314 for the overall league.</div></div>
    <div id="lgOut"></div>`;
  const go = async ()=>{
    const id = el('lgId').value.trim(); if(!id) return;
    store.set('fplai_league', id);
    el('lgOut').innerHTML = loading('Fetching rival squads and simulating 4,000 finishes');
    try{
      const r = await api(`/api/league/${id}?horizon=${S.horizon}&rivals=${el('lgN').value}`);
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
            <td><span class="nm">${esc(m.name)}</span><div class="u2">${esc(m.player_name)}</div></td>
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
  if(el('lgId').value) go();
}

/* ---------------- Scout ---------------- */
let scoutTab = 'prices';
async function viewScout(t){
  t.innerHTML = `<div class="rowtabs" id="scTabs">
      ${[['prices','Price changes'],['setpieces','Set pieces'],['defcon','Defensive contribution'],['lineups','Predicted line-ups']]
        .map(([k,l])=>`<button data-k="${k}" class="${k===scoutTab?'on':''}">${l}</button>`).join('')}
    </div><div id="scOut">${loading('Scouting')}</div>`;
  let data = null, lineups = null;
  const draw = async ()=>{
    const o = el('scOut');
    try{
      if(scoutTab === 'lineups'){
        if(!lineups){ o.innerHTML = loading('Predicting every line-up'); lineups = await api('/api/lineups?horizon=1'); }
        o.innerHTML = `<div class="grid g3">${lineups.teams.map(tm=>`
          <div class="card lift"><h3>${esc(tm.name)} <span class="r">${esc(tm.team)}</span></h3>
            ${tm.xi.map(x=>`<div class="kv"><span>${pos(x.player.position)} <span style="color:var(--ink)">${esc(x.player.web_name)}</span>${x.doubt?' <span class="tag y" style="font-size:10px;padding:1px 6px">doubt</span>':''}</span>
              <span class="${x.p_start>=80?'up':x.p_start>=55?'':'warn'}">${x.p_start}%</span></div>`).join('')}
            ${tm.rotation_risks.length?`<div class="legend"><b>Rotation risk:</b> ${tm.rotation_risks.map(r=>esc(r.player.web_name)+' '+r.p_start+'%').join(', ')}</div>`:''}
            ${tm.doubts.length?`<div class="legend"><b>Flagged:</b> ${tm.doubts.map(d=>esc(d.player.web_name)).join(', ')}</div>`:''}
          </div>`).join('')}</div>`;
        return;
      }
      if(!data){ o.innerHTML = loading('Scouting'); data = await api(`/api/scout?horizon=${S.horizon}`); }
      if(scoutTab === 'prices'){
        const P = data.prices, R = (S.meta&&S.meta.rules)||{};
        const next = (R.price_change_deadlines||[])[0];
        const tbl = (list, dir) => `<div class="well"><table><thead><tr><th>Player</th><th style="width:34%">Progress</th><th>Odds tonight</th><th class="num">Net transfers</th></tr></thead><tbody>
          ${list.map(x=>`<tr><td><span class="nm">${esc(x.player.web_name)}</span><div class="u2">${esc(x.player.team_short)} · £${num(x.player.price,1)}m</div></td>
            <td><div style="display:flex;align-items:center;gap:8px"><div class="meter" style="flex:1;margin:0"><i style="width:${Math.min(100,Math.abs(x.projected))}%;${dir<0?'background:linear-gradient(90deg,#C33E51,#E58A97)':''}"></i></div>
              <span style="font-family:var(--mono);font-size:12px;min-width:46px;text-align:right">${num(x.projected,0)}%</span></div></td>
            <td><span class="tag ${dir>0?'g':'r'}">${esc(x.likelihood_label)}</span></td>
            <td class="num ${x.net_transfers>=0?'up':'down'}">${x.net_transfers>=0?'+':''}${x.net_transfers.toLocaleString()}</td></tr>`).join('')
            || '<tr><td colspan="4" class="sub">Nobody close to a change tonight.</td></tr>'}</tbody></table></div>`;
        o.innerHTML = `
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
      } else if(scoutTab === 'setpieces'){
        const who = l => l.length ? l.map((x,i)=>`<span class="${i===0?'nm':'dim'}">${i+1}. ${esc(x.web_name)}</span>`).join('<br>') : '<span class="dim">—</span>';
        o.innerHTML = `<div class="card"><div class="well" style="max-height:none"><table><thead><tr><th>Club</th><th>Penalties</th><th>Direct free kicks</th><th>Corners &amp; indirect</th></tr></thead><tbody>
          ${data.set_pieces.teams.map(tm=>`<tr><td><b>${esc(tm.team)}</b><div class="u2">${esc(tm.name)}</div></td>
            <td>${who(tm.penalties)}</td><td>${who(tm.freekicks)}</td><td>${who(tm.corners)}</td></tr>`).join('')}</tbody></table></div>
          <div class="legend">Order of preference as listed by FPL. The first name takes it when he’s on the pitch.</div></div>`;
      } else {
        o.innerHTML = `<div class="card"><h3>Most likely to earn defensive-contribution points <span class="r">next gameweek</span></h3>
          <div class="well" style="max-height:none"><table><thead><tr><th>Player</th><th></th><th class="num">Per 90</th><th class="num">Needs</th><th style="width:26%">Chance to hit</th><th class="num">xPts</th><th class="num">Season total</th></tr></thead><tbody>
          ${data.defcon.players.map(x=>`<tr><td><span class="nm">${esc(x.player.web_name)}</span><div class="u2">${esc(x.player.team_short)} · £${num(x.player.price,1)}m</div></td>
            <td>${pos(x.player.position)}</td><td class="num">${num(x.dc_per_90,1)}</td><td class="num dim">${x.threshold}</td>
            <td><div style="display:flex;align-items:center;gap:8px"><div class="meter" style="flex:1;margin:0"><i style="width:${x.hit_probability}%"></i></div>
              <b style="font-family:var(--mono);font-size:12px;min-width:44px;text-align:right">${num(x.hit_probability,0)}%</b></div></td>
            <td class="num accent">${num(x.xpts_from_dc)}</td><td class="num">${x.dc_total}</td></tr>`).join('')}</tbody></table></div>
          <div class="legend">Defenders score 2 for 10 clearances, blocks, interceptions and tackles in a match; midfielders and forwards need 12, with recoveries also counting.</div></div>`;
      }
    }catch(e){ o.innerHTML = errBox(e); }
  };
  el('scTabs').addEventListener('click', e=>{
    const b = e.target.closest('button'); if(!b) return;
    scoutTab = b.dataset.k;
    document.querySelectorAll('#scTabs button').forEach(x=>x.classList.toggle('on', x===b));
    draw();
  });
  draw();
}

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
          This season's xG and xG conceded then pull each club away from that starting point, more with every game played. How many goals an Elo point is worth is fitted from this season's own numbers.`)}
        ${P('2 · Who plays, and for how long?', `Minutes come from FPL's week-by-week data (<code>/event/{gw}/live/</code>), with each week further back weighted 28% less. The model learns each player's <b>minutes when he starts</b>, eases injury returners back in (about 60′, then 75′), lets doubtful players' odds recover week by week, and drifts longer-range weeks back toward a player's usual role.
          Loanees barred from facing their parent club get zero for that week. You can overwrite anyone's minutes in the Expected Points table.`)}
        ${P('3 · What is each fixture worth?', `Goals for each side follow a <b>Poisson model</b> with home advantage. A player gets his share of his club's attack from his xG and xA per 90, shrunk toward a price-based estimate when his sample is thin.
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

/* ---------------- boot ---------------- */
const VIEWS = {dashboard:viewDashboard, xpts:viewXpts, solver:viewSolver, chips:viewChips, copilot:viewCopilot,
               rate:viewRate, compare:viewCompare, league:viewLeague, scout:viewScout, model:viewModel};
function setTheme(th){
  document.documentElement.dataset.theme = th; store.set('fplai_theme', th);
}
el('themeBtn').addEventListener('click', ()=>{
  setTheme(document.documentElement.dataset.theme === 'light' ? 'dark' : 'light');
});
document.querySelector('.brand').addEventListener('click', ()=>go('dashboard'));
document.body.insertAdjacentHTML('afterbegin', `<svg width="0" height="0" style="position:absolute" aria-hidden="true"><defs>
  <linearGradient id="shirtShade" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#fff" stop-opacity=".22"/><stop offset=".55" stop-color="#fff" stop-opacity="0"/>
    <stop offset="1" stop-color="#000" stop-opacity=".22"/></linearGradient></defs></svg>`);
(async function boot(){
  el('teamId').value = S.teamId || '';
  S.horizon = +el('horizon').value;
  try{
    S.meta = await api('/api/meta');
    const ev = S.meta.events.find(e=>e.id===S.meta.next_gw);
    const dl = ev ? new Date(ev.deadline) : null;
    el('rail-foot').textContent = `GW${S.meta.next_gw} deadline · ${dl?dl.toLocaleString([], {weekday:'short', day:'numeric', month:'short', hour:'2-digit', minute:'2-digit'}):'—'}`;
  }catch(e){ el('rail-foot').textContent = 'Model offline'; }
  const h = location.hash.replace('#','');
  go(VIEWS[h] ? h : 'dashboard');
})();
window.addEventListener('hashchange', ()=>{ const h = location.hash.replace('#',''); if(VIEWS[h] && h!==current) go(h); });
