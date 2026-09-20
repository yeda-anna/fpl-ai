/* FPL Copilot (local) — frontend */
const S = { meta:null, teamId:localStorage.getItem('fpl_team_id')||'', horizon:5,
            entry:null, players:null, loaded:{} };

const $  = s => document.querySelector(s);
const el = id => document.getElementById(id);
const POS = {1:'GKP',2:'DEF',3:'MID',4:'FWD'};
const TITLES = {
  dashboard:['Dashboard','Your squad, projected forward.'],
  xpts:['Expected Points','Every player, every fixture. The data behind everything else.'],
  solver:['Solver','A mixed-integer program that plans your transfers several gameweeks at once.'],
  chips:['Chip Strategy','Every valid Wildcard, Free Hit, Bench Boost and Triple Captain week, ranked.'],
  rate:['Rate My Team','A graded breakdown of your squad and what to fix first.'],
  compare:['Compare Players','Two players, side by side, on the numbers that matter.'],
  league:['Mini-Leagues','Rival squads, effective ownership and win probability.'],
  model:['How It Works','The rules, data and maths behind every number on this site.']
};

async function api(path, opts){
  const r = await fetch(path, opts);
  if(!r.ok){ let m; try{ m=(await r.json()).detail }catch(e){ m=r.statusText } throw new Error(m||'Request failed'); }
  return r.json();
}
const num = (v,d=2)=> (v==null||isNaN(v)) ? '–' : Number(v).toFixed(d);
const loading = t => `<div class="loading">${t||'Working'}</div>`;
const errBox  = e => `<div class="err"><b>Something went wrong.</b><br>${e.message||e}</div>`;
const pos = p => `<span class="pill pos${p}">${POS[p]}</span>`;
const fdr = f => `<span class="fdr fdr${f}">${f}</span>`;
const flag = p => p.status && p.status!=='a'
  ? `<span class="flag" title="${(p.news||'').replace(/"/g,'')}">●</span>` : '';

function needTeam(){
  if(!S.teamId) return `<div class="card"><h3>Team ID required</h3>
    <p class="sub" style="font-size:13.5px">Enter your FPL Team ID at the top and press Load.
    You'll find it in the URL when you view your own points page on the FPL site:
    <code>fantasy.premierleague.com/entry/<b>1234567</b>/event/1</code>.</p></div>`;
  return null;
}

/* ---------- navigation ---------- */
let current = 'dashboard';
el('nav').addEventListener('click', e => {
  const b = e.target.closest('button[data-view]'); if(!b) return;
  document.querySelectorAll('#nav button').forEach(x=>x.classList.toggle('on', x===b));
  current = b.dataset.view;
  document.querySelectorAll('.view').forEach(v=>v.classList.toggle('on', v.id==='view-'+current));
  el('view-title').textContent = TITLES[current][0];
  el('view-sub').textContent   = TITLES[current][1];
  render(current);
});

el('load').addEventListener('click', ()=>{
  S.teamId = el('teamId').value.trim();
  S.horizon = +el('horizon').value;
  localStorage.setItem('fpl_team_id', S.teamId);
  S.loaded = {}; S.entry = null; S.players = null;
  render(current);
});
el('horizon').addEventListener('change', ()=>{
  S.horizon = +el('horizon').value; S.loaded = {}; S.players = null; render(current);
});

/* ---------- views ---------- */
function render(view){
  const target = el('view-'+view);
  if(S.loaded[view+S.horizon+S.teamId]) return;
  S.loaded[view+S.horizon+S.teamId] = true;
  ({dashboard:renderDashboard, xpts:renderXpts, solver:renderSolver, chips:renderChips,
    rate:renderRate, compare:renderCompare, league:renderLeague, model:renderModel})[view](target);
}

/* Dashboard */
async function renderDashboard(t){
  t.innerHTML = loading('Loading projections');
  try{
    const picks = await api(`/api/picks?horizon=${S.horizon}`);
    let head = '';
    if(S.teamId){
      const e = await api(`/api/entry/${S.teamId}?horizon=${S.horizon}`);
      S.entry = e;
      head = `
      <div class="grid g4" style="margin-bottom:14px">
        ${card('Overall rank', e.entry.overall_rank ? e.entry.overall_rank.toLocaleString() : '–', e.entry.name||'')}
        ${card('Total points', e.entry.overall_points ?? '–', `GW${e.gw}: ${e.entry.gw_points ?? '–'} pts`)}
        ${card('Squad value', `£${num(e.entry.value,1)}m`, `£${num(e.bank,1)}m in the bank`)}
        ${card('Free transfers', e.free_transfers, e.chips_used.length? 'Chips used: '+e.chips_used.join(', ') : 'No chips used yet')}
      </div>
      <div class="grid g2" style="margin-bottom:14px">
        <div class="card">
          <h3>Projected XI — GW${e.next_gw} · ${e.formation}</h3>
          ${pitch(e.starting_xi, e.bench, e.captain)}
          <div class="legend">Starting XI projects <b class="accent">${num(e.xi_xpts)}</b> xPts,
            bench <b>${num(e.bench_xpts)}</b>. Captain doubles ${e.captain?e.captain.web_name:'–'}
            for another <b class="accent">${e.captain?num(e.captain.xpts):'0'}</b>.</div>
        </div>
        <div class="card">
          <h3>Your squad over ${S.horizon} gameweeks</h3>
          <div class="scroll"><table><thead><tr>
            <th>Player</th><th></th><th class="num">£</th><th class="num">GW${e.next_gw}</th><th class="num">${S.horizon} GW</th><th>Trend</th>
          </tr></thead><tbody>
          ${e.squad.sort((a,b)=>b.xpts_total-a.xpts_total).map(p=>`<tr>
            <td>${p.web_name} ${flag(p)}<div class="sub">${p.team_short}</div></td>
            <td>${pos(p.position)}</td>
            <td class="num">${num(p.price,1)}</td>
            <td class="num accent">${num(p.xpts)}</td>
            <td class="num">${num(p.xpts_total)}</td>
            <td>${spark(p.per_gw.map(g=>g.xpts))}</td>
          </tr>`).join('')}
          </tbody></table></div>
        </div>
      </div>`;
    } else {
      head = `<div class="card" style="margin-bottom:14px"><h3>Get started</h3>
        <p class="sub" style="font-size:13.5px">Enter your FPL Team ID above to load your squad,
        run the solver and rate your team. Everything below works without one.</p></div>`;
    }

    t.innerHTML = head + `
      <div class="grid g3">
        <div class="card"><h3>Captain picks — GW${picks.gw}</h3>
          <table><tbody>${picks.captains.slice(0,7).map((p,i)=>`<tr>
            <td style="width:22px;color:var(--ink-3)">${i+1}</td>
            <td>${p.web_name}<div class="sub">${p.team_short} · ${num(p.price,1)}m</div></td>
            <td>${pos(p.position)}</td>
            <td class="num accent">${num(p.xpts)}</td></tr>`).join('')}</tbody></table>
          <div class="legend">Expected points for the single gameweek, doubled if captained.</div>
        </div>
        <div class="card"><h3>Differentials under 15% owned</h3>
          <table><tbody>${picks.differentials.slice(0,8).map(p=>`<tr>
            <td>${p.web_name}<div class="sub">${p.team_short}</div></td>
            <td>${pos(p.position)}</td>
            <td class="num">${num(p.selected_by_percent,1)}%</td>
            <td class="num accent">${num(p.xpts_total)}</td></tr>`).join('')}</tbody></table>
          <div class="legend">Right column is projected points over ${S.horizon} gameweeks.</div>
        </div>
        <div class="card"><h3>Best value per £m</h3>
          <table><tbody>${picks.best_value.slice(0,8).map(p=>`<tr>
            <td>${p.web_name}<div class="sub">${p.team_short}</div></td>
            <td>${pos(p.position)}</td>
            <td class="num">${num(p.price,1)}</td>
            <td class="num accent">${num(p.xpts_total)}</td></tr>`).join('')}</tbody></table>
        </div>
      </div>
      <div class="card" style="margin-top:14px">
        <h3>Dream team — GW${picks.gw} · ${picks.dream_team.formation} · £${num(picks.dream_team.cost,1)}m</h3>
        ${pitch(picks.dream_team.xi, [], picks.dream_team.captain)}
      </div>`;
  }catch(e){ t.innerHTML = errBox(e); }
}

function card(label, value, sub){
  return `<div class="card tight"><h3>${label}</h3><div class="stat sm">${value}</div><div class="sub">${sub||''}</div></div>`;
}
function spark(vals){
  const mx = Math.max(...vals, 0.1);
  return `<div class="spark">${vals.map(v=>`<i style="height:${Math.max(6,v/mx*100)}%" title="${num(v)}"></i>`).join('')}</div>`;
}
function pitch(xi, bench, captain){
  const rows = {1:[],2:[],3:[],4:[]};
  xi.forEach(p => rows[p.position].push(p));
  const chip = p => `<div class="chip-p ${captain&&p.id===captain.id?'cap':''}">
      <div class="nm">${p.web_name}</div><div class="mt">${p.team_short}${captain&&p.id===captain.id?' (C)':''}</div>
      <div class="xp">${num(p.xpts)}</div></div>`;
  return `<div class="pitch">
    ${[1,2,3,4].map(q=>`<div class="row">${rows[q].map(chip).join('')}</div>`).join('')}
    ${bench.length?`<div class="row benchrow">${bench.map(chip).join('')}</div>`:''}
  </div>`;
}

/* Expected points table */
async function renderXpts(t){
  t.innerHTML = `
    <div class="card" style="margin-bottom:14px">
      <div class="controls">
        <label class="fld">Position<select id="fPos"><option value="">All</option>
          <option value="1">GKP</option><option value="2">DEF</option>
          <option value="3">MID</option><option value="4">FWD</option></select></label>
        <label class="fld">Max price<input id="fPrice" type="number" step="0.5" placeholder="any" style="width:84px"></label>
        <label class="fld">Search<input id="fSearch" placeholder="name" style="width:130px"></label>
        <label class="fld">Sort<select id="fSort">
          <option value="xpts_total">xPts (horizon)</option>
          <option value="xpts_next">xPts (next GW)</option>
          <option value="value">Points per £m</option>
          <option value="ownership">Ownership</option></select></label>
        <label class="fld">Rows<select id="fLimit"><option>40</option><option selected>80</option><option>150</option></select></label>
        <label class="fld">&nbsp;<span><input type="checkbox" id="fAvail" checked> <span style="text-transform:none;font-size:12px;letter-spacing:0">Available only</span></span></label>
      </div>
    </div>
    <div id="xptsTable">${loading('Projecting every player')}</div>`;
  const run = async ()=>{
    const q = new URLSearchParams({horizon:S.horizon, sort:el('fSort').value, limit:el('fLimit').value});
    if(el('fPos').value) q.set('position', el('fPos').value);
    if(el('fPrice').value) q.set('max_price', el('fPrice').value);
    if(el('fSearch').value) q.set('search', el('fSearch').value);
    if(el('fAvail').checked) q.set('available_only','true');
    el('xptsTable').innerHTML = loading('Projecting');
    try{
      const d = await api('/api/players?'+q);
      const gws = d.players.length? d.players[0].per_gw.map(g=>g.gw) : [];
      el('xptsTable').innerHTML = `<div class="card"><h3>${d.count} players · GW${gws[0]}–${gws[gws.length-1]}</h3>
        <div class="scroll"><table><thead><tr>
          <th>Player</th><th></th><th class="num">£</th><th class="num">Own</th><th class="num">Form</th>
          ${gws.map(g=>`<th class="num">${g}</th>`).join('')}
          <th class="num">Total</th></tr></thead><tbody>
        ${d.players.map(p=>`<tr>
          <td><a href="#" onclick="showPlayer(${p.id});return false">${p.web_name}</a> ${flag(p)}
              <div class="sub">${p.team_short}</div></td>
          <td>${pos(p.position)}</td>
          <td class="num">${num(p.price,1)}</td>
          <td class="num">${num(p.selected_by_percent,1)}</td>
          <td class="num">${num(p.form,1)}</td>
          ${p.per_gw.map(g=>`<td class="num" title="${g.fixtures.map(f=>f.opponent_short+(f.home?' (H)':' (A)')).join(', ')||'Blank'}">
              ${g.blank?'<span style="color:var(--ink-3)">–</span>':num(g.xpts)}
              ${g.fixtures.length?' '+fdr(Math.min(...g.fixtures.map(f=>f.fdr))):''}</td>`).join('')}
          <td class="num accent"><b>${num(p.xpts_total)}</b></td></tr>`).join('')}
        </tbody></table></div>
        <div class="legend">Hover a gameweek cell for the fixture. The small square is the FPL difficulty rating.
        Click a name for the full points breakdown.</div></div>`;
    }catch(e){ el('xptsTable').innerHTML = errBox(e); }
  };
  ['fPos','fPrice','fSearch','fSort','fLimit','fAvail'].forEach(id=>{
    el(id).addEventListener('change', run);
    if(id==='fSearch') el(id).addEventListener('keyup', ev=>{ if(ev.key==='Enter') run(); });
  });
  run();
}

window.showPlayer = async function(id){
  const box = el('xptsTable');
  const keep = box.innerHTML;
  box.innerHTML = loading('Loading player');
  try{
    const p = await api(`/api/player/${id}?horizon=${S.horizon}`);
    const b = {};
    p.per_gw.forEach(g=>g.fixtures.forEach(f=>{
      for(const k in f.breakdown) b[k]=(b[k]||0)+f.breakdown[k];
    }));
    box.innerHTML = `<div class="card"><h3>${p.web_name} · ${p.team_short} · ${POS[p.position]} · £${num(p.price,1)}m</h3>
      <div class="grid g3">
        <div><h3>Fixtures</h3><table><tbody>${p.per_gw.map(g=>`<tr>
          <td>GW${g.gw}</td>
          <td>${g.fixtures.map(f=>`${f.opponent_short} (${f.home?'H':'A'}) ${fdr(f.fdr)}`).join(' + ')||'<span class="sub">Blank</span>'}</td>
          <td class="num accent">${num(g.xpts)}</td></tr>`).join('')}
          <tr><td colspan="2"><b>Total</b></td><td class="num accent"><b>${num(p.xpts_total)}</b></td></tr></tbody></table></div>
        <div><h3>Where the points come from</h3>
          ${Object.entries(b).sort((x,y)=>Math.abs(y[1])-Math.abs(x[1])).map(([k,v])=>
            `<div class="kv"><span>${k.replace(/_/g,' ')}</span><span class="${v<0?'bad':''}">${num(v)}</span></div>`).join('')}
        </div>
        <div><h3>Underlying rates</h3>
          <div class="kv"><span>Expected minutes</span><span>${num(p.minutes_model.xmins,0)}</span></div>
          <div class="kv"><span>Start probability</span><span>${num(p.minutes_model.p_start*100,0)}%</span></div>
          <div class="kv"><span>xG per 90</span><span>${num(p.rates.xg90,3)}</span></div>
          <div class="kv"><span>xA per 90</span><span>${num(p.rates.xa90,3)}</span></div>
          <div class="kv"><span>Def. contribution / 90</span><span>${num(p.rates.dc90,1)}</span></div>
          <div class="kv"><span>BPS per 90</span><span>${num(p.rates.bps90,1)}</span></div>
          <div class="kv"><span>Season points</span><span>${p.total_points}</span></div>
          <div class="kv"><span>Minutes played</span><span>${p.minutes}</span></div>
          <div class="kv"><span>FPL's own ep_next</span><span>${num(p.fpl_ep_next)}</span></div>
          ${p.news?`<div class="note" style="margin-top:10px">${p.news}</div>`:''}
        </div>
      </div>
      <button class="btn" style="margin-top:12px" id="backBtn">← Back to table</button></div>`;
    el('backBtn').onclick = ()=>{ box.innerHTML = keep; };
  }catch(e){ box.innerHTML = errBox(e); }
};

/* Solver */
async function renderSolver(t){
  const n = needTeam(); if(n){ t.innerHTML = n; return; }
  t.innerHTML = `
    <div class="card" style="margin-bottom:14px">
      <div class="controls">
        <label class="fld">Max hits<select id="sHits"><option>0</option><option selected>1</option><option>2</option><option>3</option></select></label>
        <label class="fld">Wildcard in GW<select id="sWC"><option value="">none</option></select></label>
        <label class="fld">Free Hit in GW<select id="sFH"><option value="">none</option></select></label>
        <label class="fld">Free transfers<input id="sFT" type="number" min="1" max="5" placeholder="auto" style="width:76px"></label>
        <button class="btn primary" id="runSolve">Run solver</button>
      </div>
      <div class="legend">The solver maximises expected points across all ${S.horizon} gameweeks at once,
      with a ${'−'}4 charge per extra transfer and a decay so near gameweeks count more.</div>
    </div>
    <div id="solveOut">${loading('Solving')}</div>`;

  const e = S.entry || await api(`/api/entry/${S.teamId}?horizon=${S.horizon}`);
  S.entry = e;
  for(let i=0;i<S.horizon;i++){
    const g = e.next_gw+i;
    el('sWC').insertAdjacentHTML('beforeend', `<option value="${g}">GW${g}</option>`);
    el('sFH').insertAdjacentHTML('beforeend', `<option value="${g}">GW${g}</option>`);
  }
  const run = async ()=>{
    el('solveOut').innerHTML = loading('Optimising — this runs a real MIP, give it a few seconds');
    try{
      const body = { team_id:+S.teamId, horizon:S.horizon, max_hits:+el('sHits').value };
      if(el('sWC').value) body.wildcard_gw = +el('sWC').value;
      if(el('sFH').value) body.free_hit_gw = +el('sFH').value;
      if(el('sFT').value) body.free_transfers = +el('sFT').value;
      const r = await api('/api/solve', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
      el('solveOut').innerHTML = `
        <div class="grid g4" style="margin-bottom:14px">
          ${card('Plan total', num(r.total_xpts)+' xPts', `${r.horizon} gameweeks, net of hits`)}
          ${card('Hits taken', r.total_hits, r.total_hits? `${r.total_hits*4} points paid` : 'No hits needed')}
          ${card('Doing nothing', num(r.no_transfer_baseline)+' xPts', 'Your current XI in GW'+r.gameweeks[0].gw)}
          ${card('Solver status', r.status, `${r.pool_size} players considered`)}
        </div>
        ${r.gameweeks.map(g=>`<div class="plan">
          <div class="hd">
            <div class="gw">GW${g.gw} ${g.chip?`<span class="pill pos3">${g.chip}</span>`:''}</div>
            <div class="sub">FT ${g.free_transfers} · bank £${num(g.bank,1)}m ·
              <b class="accent">${num(g.xpts)} xPts</b>${g.hits?` <span class="bad">(−${g.hit_cost} hit)</span>`:''}</div>
          </div>
          ${g.transfers_in.length? g.transfers_in.map((p,i)=>`<div class="mv">
              <span class="out">− ${g.transfers_out[i]?g.transfers_out[i].web_name:'–'}</span>
              <span class="sub">${g.transfers_out[i]?'£'+num(g.transfers_out[i].price,1)+'m · '+num(g.transfers_out[i].xpts)+' xPts':''}</span>
              <span style="color:var(--ink-3)">→</span>
              <span class="in">+ ${p.web_name}</span>
              <span class="sub">£${num(p.price,1)}m · ${num(p.xpts)} xPts</span>
            </div>`).join('') : '<div class="sub">No transfer — roll it.</div>'}
          <div class="mt sub" style="margin-top:8px">Captain: <b>${g.captain?g.captain.web_name:'–'}</b> ·
            XI: ${g.starting_xi.map(p=>p.web_name).join(', ')}</div>
          <div class="sub" style="margin-top:4px;color:var(--ink-3)">Bench: ${g.bench.map(p=>p.web_name).join(', ')}</div>
        </div>`).join('')}`;
    }catch(err){ el('solveOut').innerHTML = errBox(err); }
  };
  el('runSolve').onclick = run;
  run();
}

/* Chips */
async function renderChips(t){
  const n = needTeam(); if(n){ t.innerHTML = n; return; }
  t.innerHTML = loading('Simulating every chip in every gameweek — this takes a little while');
  try{
    const r = await api('/api/chips', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({team_id:+S.teamId, horizon:S.horizon})});
    const names = {WC:'Wildcard', FH:'Free Hit', BB:'Bench Boost', TC:'Triple Captain'};
    t.innerHTML = `
      <div class="card" style="margin-bottom:14px">
        <h3>Best chip plans over the next ${S.horizon} gameweeks</h3>
        ${r.best_plans.slice(0,5).map((p,i)=>`<div class="plan">
          <div class="hd"><div class="gw">#${i+1}</div>
            <div class="sub">Worth <b class="accent">+${num(p.total_gain)} xPts</b> over playing no chips</div></div>
          ${p.picks.map(c=>`<div class="mv"><span class="pill pos3">${names[c.chip]}</span>
            <b>GW${c.gw}</b><span class="accent">+${num(c.gain)}</span>
            <span class="sub">${c.detail}</span></div>`).join('')}
        </div>`).join('') || '<div class="sub">All chips already used.</div>'}
        ${r.chips_used.length?`<div class="legend">Already played: ${r.chips_used.join(', ')}</div>`:''}
      </div>
      <div class="grid g2">
        ${Object.entries(r.options).filter(([k,v])=>v.length).map(([k,v])=>`
        <div class="card"><h3>${names[k]} — gameweek by gameweek</h3>
          <table><thead><tr><th>GW</th><th class="num">Gain</th><th>Why</th></tr></thead><tbody>
          ${v.map(o=>`<tr><td>GW${o.gw}</td>
            <td class="num ${o.gain>0?'accent':'bad'}">${o.gain>0?'+':''}${num(o.gain)}</td>
            <td class="sub">${o.detail}</td></tr>`).join('')}
          </tbody></table></div>`).join('')}
      </div>
      <div class="card" style="margin-top:14px"><h3>Your baseline (no chips)</h3>
        <table><thead><tr><th>GW</th><th class="num">XI</th><th class="num">Captain</th><th class="num">Bench</th><th class="num">Total</th></tr></thead><tbody>
        ${r.baseline.map(b=>`<tr><td>GW${b.gw}</td><td class="num">${num(b.xi_xpts)}</td>
          <td class="num">${b.captain||'–'} (${num(b.captain_xpts)})</td>
          <td class="num">${num(b.bench_xpts)}</td><td class="num accent">${num(b.total)}</td></tr>`).join('')}
        </tbody></table></div>`;
  }catch(e){ t.innerHTML = errBox(e); }
}

/* Rate my team */
async function renderRate(t){
  const n = needTeam(); if(n){ t.innerHTML = n; return; }
  t.innerHTML = loading('Grading your squad');
  try{
    const r = await api(`/api/rate/${S.teamId}?horizon=${S.horizon}`);
    const bars = Object.entries(r.scores).map(([k,v])=>`
      <div style="margin-bottom:11px"><div class="kv" style="border:0;padding:0">
        <span>${k}</span><span>${num(v,0)}</span></div>
        <div class="bar"><i style="width:${Math.max(2,Math.min(100,v))}%"></i></div></div>`).join('');
    t.innerHTML = `
      <div class="grid g3" style="margin-bottom:14px">
        <div class="card" style="text-align:center">
          <h3>${r.entry.name||'Your team'}</h3>
          <div class="grade">${r.grade}</div>
          <div class="sub">${num(r.overall,0)} / 100 · rank ${r.entry.overall_rank?r.entry.overall_rank.toLocaleString():'–'}</div>
        </div>
        <div class="card"><h3>Score breakdown</h3>${bars}</div>
        <div class="card"><h3>Key numbers</h3>
          <div class="kv"><span>Squad xPts (${S.horizon} GW)</span><span>${num(r.squad_xpts)}</span></div>
          <div class="kv"><span>Strong-squad benchmark</span><span>${num(r.benchmark_xpts)}</span></div>
          <div class="kv"><span>Efficiency</span><span>${num(r.efficiency,0)}%</span></div>
          <div class="kv"><span>Best formation</span><span>${r.formation}</span></div>
          <div class="kv"><span>XI / bench next GW</span><span>${num(r.xi_xpts)} / ${num(r.bench_xpts)}</span></div>
          <div class="kv"><span>Value + bank</span><span>£${num(r.squad_value,1)}m</span></div>
        </div>
      </div>
      <div class="grid g2">
        <div class="card"><h3>What to fix</h3>${r.notes.map(t=>`<div class="note">${t}</div>`).join('')}</div>
        <div class="card"><h3>Highest-value single transfers</h3>
          <table><thead><tr><th>Out</th><th>In</th><th class="num">Gain</th></tr></thead><tbody>
          ${r.top_upgrades.map(u=>`<tr>
            <td class="out">${u.out.web_name}<div class="sub">${u.out.team_short} · £${num(u.out.price,1)}m · ${num(u.out.xpts_total)}</div></td>
            <td class="in">${u.in.web_name}<div class="sub">${u.in.team_short} · £${num(u.in.price,1)}m · ${num(u.in.xpts_total)}</div></td>
            <td class="num accent">+${num(u.gain)}</td></tr>`).join('') || '<tr><td colspan="3" class="sub">No clear upgrade within budget.</td></tr>'}
          </tbody></table>
          <div class="legend">Gain is extra xPts over ${S.horizon} gameweeks, affordable with your current bank.</div>
        </div>
      </div>`;
  }catch(e){ t.innerHTML = errBox(e); }
}

/* Compare */
async function renderCompare(t){
  t.innerHTML = `<div class="card" style="margin-bottom:14px"><div class="controls">
      <label class="fld">Player A<select id="cA"></select></label>
      <label class="fld">Player B<select id="cB"></select></label>
      <button class="btn primary" id="cGo">Compare</button></div></div>
    <div id="cOut"></div>`;
  const d = await api(`/api/players?horizon=${S.horizon}&limit=400&min_minutes=90`);
  const opts = d.players.slice().sort((a,b)=>a.web_name.localeCompare(b.web_name))
    .map(p=>`<option value="${p.id}">${p.web_name} (${p.team_short}, ${POS[p.position]} £${num(p.price,1)}m)</option>`).join('');
  el('cA').innerHTML = opts; el('cB').innerHTML = opts;
  el('cA').value = d.players[0].id; el('cB').value = d.players[1].id;
  const go = async ()=>{
    el('cOut').innerHTML = loading('Comparing');
    try{
      const r = await api(`/api/compare?a=${el('cA').value}&b=${el('cB').value}&horizon=${S.horizon}`);
      const rowfn = (k,label,fmt=(v)=>num(v)) => {
        const a=r.a[k], b=r.b[k];
        const aw = a>b ? 'accent' : '', bw = b>a ? 'accent' : '';
        return `<tr><td class="num ${aw}">${fmt(a)}</td><td style="text-align:center;color:var(--ink-3)">${label}</td><td class="num ${bw}">${fmt(b)}</td></tr>`;
      };
      el('cOut').innerHTML = `
        <div class="card" style="margin-bottom:14px">
          <div class="grid g3" style="align-items:center">
            <div style="text-align:right"><div class="stat sm">${r.a.web_name}</div>
              <div class="sub">${r.a.team_short} · ${r.a.pos_name} · £${num(r.a.price,1)}m</div></div>
            <div style="text-align:center"><div class="sub">verdict</div>
              <div style="font-size:14px;margin-top:4px">${r.verdict}</div></div>
            <div><div class="stat sm">${r.b.web_name}</div>
              <div class="sub">${r.b.team_short} · ${r.b.pos_name} · £${num(r.b.price,1)}m</div></div>
          </div>
          ${r.reasons.map(x=>`<div class="note" style="margin-top:10px">${x}</div>`).join('')}
        </div>
        <div class="grid g2">
          <div class="card"><h3>Head to head</h3><table><tbody>
            ${rowfn('xpts_next','xPts next GW')}
            ${rowfn('xpts_total',`xPts over ${S.horizon} GW`)}
            ${rowfn('value','xPts per £m',v=>num(v,2))}
            ${rowfn('xg90','xG / 90',v=>num(v,3))}
            ${rowfn('xa90','xA / 90',v=>num(v,3))}
            ${rowfn('dc90','Def. contributions / 90',v=>num(v,1))}
            ${rowfn('bps90','BPS / 90',v=>num(v,1))}
            ${rowfn('xmins','Expected minutes',v=>num(v,0))}
            ${rowfn('total_points','Season points',v=>v)}
            ${rowfn('form','Form',v=>num(v,1))}
            <tr><td class="num">${num(r.a.selected_by_percent,1)}%</td><td style="text-align:center;color:var(--ink-3)">Ownership</td><td class="num">${num(r.b.selected_by_percent,1)}%</td></tr>
          </tbody></table></div>
          <div class="card"><h3>Fixture by fixture</h3><table><thead><tr>
            <th class="num">${r.a.web_name}</th><th style="text-align:center">GW</th><th class="num">${r.b.web_name}</th></tr></thead><tbody>
            ${r.a.per_gw.map((g,i)=>`<tr>
              <td class="num">${num(g.xpts)} <span class="sub">${g.opp}</span></td>
              <td style="text-align:center">${g.gw}</td>
              <td class="num">${num(r.b.per_gw[i].xpts)} <span class="sub">${r.b.per_gw[i].opp}</span></td></tr>`).join('')}
          </tbody></table></div>
        </div>`;
    }catch(e){ el('cOut').innerHTML = errBox(e); }
  };
  el('cGo').onclick = go;
}

/* Mini-leagues */
async function renderLeague(t){
  t.innerHTML = `<div class="card" style="margin-bottom:14px"><div class="controls">
      <label class="fld">League ID<input id="lgId" type="number" placeholder="e.g. 314" style="width:130px" value="${localStorage.getItem('fpl_league')||''}"></label>
      <label class="fld">Rivals<select id="lgN"><option>6</option><option selected>12</option><option>20</option></select></label>
      <button class="btn primary" id="lgGo">Analyse</button></div>
      <div class="legend">Find the ID in the URL of your league page:
      <code>fantasy.premierleague.com/leagues/<b>123456</b>/standings/c</code>. 314 is the global league.</div></div>
    <div id="lgOut"></div>`;
  el('lgGo').onclick = async ()=>{
    const id = el('lgId').value.trim(); if(!id) return;
    localStorage.setItem('fpl_league', id);
    el('lgOut').innerHTML = loading('Pulling rival squads and running simulations');
    try{
      const r = await api(`/api/league/${id}?horizon=${S.horizon}&rivals=${el('lgN').value}`);
      el('lgOut').innerHTML = `
        <div class="card" style="margin-bottom:14px"><h3>${r.league.name||'League'} — ${r.rivals_analysed} squads · ${r.sims.toLocaleString()} simulations</h3>
          <table><thead><tr><th>#</th><th>Manager</th><th class="num">Points</th>
            <th class="num">xPts (${S.horizon} GW)</th><th class="num">Win %</th><th class="num">Top 3 %</th><th>Captain</th></tr></thead><tbody>
          ${r.managers.map(m=>`<tr>
            <td class="sub">${m.rank}</td>
            <td><b>${m.name}</b><div class="sub">${m.player_name}</div></td>
            <td class="num">${m.total}</td>
            <td class="num">${num(m.horizon_xpts,1)}</td>
            <td class="num accent"><b>${num(m.win_probability,1)}%</b></td>
            <td class="num">${num(m.top3_probability,1)}%</td>
            <td class="sub">${(r.ownership.find(o=>o.player.id===m.captain_id)||{player:{web_name:'–'}}).player.web_name}</td>
          </tr>`).join('')}</tbody></table></div>
        <div class="grid g3">
          <div class="card"><h3>Most owned in this league</h3><table><tbody>
            ${r.ownership.slice(0,12).map(o=>`<tr><td>${o.player.web_name}<div class="sub">${o.player.team_short}</div></td>
              <td class="num">${o.pct}%</td><td class="num accent">${num(o.player.xpts_total)}</td></tr>`).join('')}
          </tbody></table></div>
          <div class="card"><h3>Effective ownership</h3><table><tbody>
            ${r.effective_ownership.map(o=>`<tr><td>${o.player.web_name}<div class="sub">${o.player.team_short}</div></td>
              <td class="num">${o.effective_ownership}%</td></tr>`).join('')}
          </tbody></table>
          <div class="legend">Counts captaincy twice — this is what actually moves you up or down the table.</div></div>
          <div class="card"><h3>Differentials your rivals don't own</h3><table><tbody>
            ${r.differentials.map(o=>`<tr><td>${o.player.web_name}<div class="sub">${o.player.team_short} · £${num(o.player.price,1)}m</div></td>
              <td class="num">${o.league_pct}%</td><td class="num accent">${num(o.player.xpts_total)}</td></tr>`).join('')}
          </tbody></table></div>
        </div>`;
    }catch(e){ el('lgOut').innerHTML = errBox(e); }
  };
}

/* How it works */
async function renderModel(t){
  try{
    const m = await api('/api/meta');
    const teams = Object.entries(m.team_ratings)
      .map(([id,r])=>({name:(m.teams.find(x=>x.id==id)||{}).short_name, ...r}))
      .sort((a,b)=>b.attack-a.attack);
    t.innerHTML = `
      <div class="grid g2" style="margin-bottom:14px">
        <div class="card"><h3>The expected-points model</h3>
          <p style="font-size:13.6px;color:var(--ink-2)">Every projection starts with two Poisson means for a fixture:
          how many goals each side is expected to score. Those come from each team's xG and xG conceded so far this season,
          shrunk toward the league average of 1.45 goals a game because only ${teams[0]?teams[0].games:0} matches have been played,
          then adjusted for home advantage.</p>
          <p style="font-size:13.6px;color:var(--ink-2)">A player's own rates — xG, xA and defensive contributions per 90 —
          are shrunk toward a prior fitted from his price, which is the market's estimate of his talent. His slice of the team's
          attack is then scaled onto the fixture and multiplied by expected minutes.</p>
          <p style="font-size:13.6px;color:var(--ink-2)">The rest is FPL's own scoring table: 6/6/5/4 points a goal by position,
          3 an assist, a Poisson clean-sheet probability, −1 per two goals conceded, a save every three, 2 points for hitting
          the defensive-contribution threshold (10 for defenders, 12 for everyone else), bonus estimated from BPS per 90,
          and appearance points weighted by the chance of playing 60 minutes.</p>
        </div>
        <div class="card"><h3>The solver</h3>
          <p style="font-size:13.6px;color:var(--ink-2)">The transfer planner is a mixed-integer program solved with CBC.
          It chooses your squad, your eleven, your captain and every transfer across all gameweeks in the horizon
          simultaneously, subject to the real rules: 15 players, 2/5/5/3 by position, at most 3 from a club,
          a legal formation, your actual bank and selling prices, free transfers that bank up to 5,
          and −4 for every transfer beyond them.</p>
          <p style="font-size:13.6px;color:var(--ink-2)">Bench points are worth 12% of face value, and each gameweek further
          out is discounted by 13%, so it prefers points it can be more confident about.</p>
          <h3 style="margin-top:14px">Data</h3>
          <div class="kv"><span>Source</span><span>fantasy.premierleague.com/api</span></div>
          <div class="kv"><span>Players</span><span>${m.total_players ? '' : ''}${Object.keys(m.team_ratings).length} teams</span></div>
          <div class="kv"><span>Current gameweek</span><span>GW${m.current_gw}</span></div>
          <div class="kv"><span>Next deadline</span><span>GW${m.next_gw}</span></div>
        </div>
      </div>
      <div class="card"><h3>Team ratings the model derived</h3>
        <div class="scroll"><table><thead><tr><th>Team</th><th class="num">Attack</th><th class="num">Defence</th>
          <th class="num">xG / game</th><th class="num">xGC / game</th><th class="num">Played</th></tr></thead><tbody>
        ${teams.map(t=>`<tr><td>${t.name}</td>
          <td class="num accent">${num(t.attack)}</td>
          <td class="num ${t.defence>1?'bad':'accent'}">${num(t.defence)}</td>
          <td class="num">${num(t.xg_per_game)}</td>
          <td class="num">${num(t.xgc_per_game)}</td>
          <td class="num">${t.games}</td></tr>`).join('')}
        </tbody></table></div>
        <div class="legend">1.00 is league average. Attack above 1 means a team scores more than average;
        defence above 1 means it concedes more than average.</div>
      </div>`;
  }catch(e){ t.innerHTML = errBox(e); }
}

/* boot */
(async function(){
  if(S.teamId) el('teamId').value = S.teamId;
  S.horizon = +el('horizon').value;
  try{
    S.meta = await api('/api/meta');
    el('meta-foot').innerHTML = `GW${S.meta.current_gw} played · GW${S.meta.next_gw} next`;
  }catch(e){}
  render('dashboard');
})();
