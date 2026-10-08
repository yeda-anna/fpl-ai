/* Captain’s Log — the opening film. Plain JS, no build step.

   A few seconds of titles on every launch while the app loads underneath:
   letterbox bars close in, we drop out of hyperspace over a scrolling grid
   floor, the logo — a football with a planet's ring — draws itself and
   ignites, the name decodes, the captain's log types its entry, then the
   camera flies into the ball and the film irises open onto the app.

   It is a Theatre.js sequence (vendor/theatre-core.min.js, global Theatre.core):
   every moving part is a sheet object, every move a keyframe in KEYS below,
   eased with cubic Béziers. KEYS is turned into Theatre's project state at
   load, so changing the film is editing numbers here. (Theatre Studio, the
   visual editor, is a development tool and is not shipped.)

   Tap anywhere, press Esc / Enter / Space, or "Skip intro" to jump to the end.
   No film when the visitor prefers reduced motion, turned it off in the menu,
   or when the app reloads itself — index.html decides that before the first
   paint (the `no-intro` class). */
'use strict';
const Intro = (() => {
  const root = document.getElementById('intro');
  const T = window.Theatre && window.Theatre.core;
  const LEN = 4.6, OUTRO = 4.0, FPS = 24;

  /* cubic-bezier easings for the curve that leaves a keyframe */
  const EASE = {linear:[0, 0, 1, 1], in:[.55, 0, 1, .45], out:[0, .55, .45, 1], inOut:[.65, 0, .35, 1],
                expoOut:[.16, 1, .3, 1], back:[.34, 1.56, .64, 1]};
  /* object → prop → [[seconds, value, easing to the next keyframe], …] */
  const KEYS = {
    Bars:   {h:     [[0, 0, 'expoOut'], [.6, 1], [OUTRO, 1, 'inOut'], [4.45, 0]]},
    Hud:    {a:     [[.3, 0, 'out'], [.7, 1], [OUTRO, 1, 'in'], [4.3, 0]]},
    Warp:   {speed: [[0, 1], [1.05, 1, 'out'], [2.3, .05], [OUTRO, .05, 'in'], [LEN, 1]],
             a:     [[0, 0, 'out'], [.35, 1], [4.2, 1, 'in'], [LEN, .3]]},
    Floor:  {rise:  [[.85, 0, 'expoOut'], [2.2, 1]],
             a:     [[.85, 0, 'out'], [1.6, .9]]},
    Logo:   {draw:  [[.7, 0, 'inOut'], [1.95, 1]],
             scale: [[.7, .55, 'back'], [2.1, 1]],
             glow:  [[1.8, 0, 'out'], [2.15, 1]]},
    Flash:  {a:     [[1.86, 0, 'out'], [1.97, .65, 'out'], [2.45, 0]]},
    Ripple: {a:     [[1.95, 0, 'out'], [2.25, 1], [3.95, 1, 'in'], [4.4, 0]],
             scale: [[1.95, .55, 'expoOut'], [2.9, 1]]},
    Title:  {a:     [[2, 0, 'out'], [2.2, 1]],
             reveal:[[2, 0, 'linear'], [2.85, 1]],
             track: [[2, .55, 'expoOut'], [3.1, .05]]},
    Line:   {a:     [[2.8, 0, 'out'], [2.92, 1]],
             type:  [[2.95, 0, 'linear'], [3.75, 1]]},
    Camera: {zoom:  [[0, 1.25, 'out'], [2.4, 1, 'inOut'], [OUTRO, 1.06, 'in'], [LEN, 2.4]],
             y:     [[0, 5, 'out'], [2.4, 0]]},
    Iris:   {hole:  [[4.05, 0, 'in'], [LEN, 1]]}
  };

  /* KEYS → the project state Theatre expects (what Studio would export) */
  function projectState(){
    const tracksByObject = {};
    let n = 0;
    Object.keys(KEYS).forEach(obj=>{
      const trackData = {}, trackIdByPropPath = {};
      Object.keys(KEYS[obj]).forEach(prop=>{
        const id = 'tr' + (++n), kfs = KEYS[obj][prop];
        const keyframes = kfs.map((k, i)=>({id:id + 'k' + i, position:k[0], value:k[1], connectedRight:i < kfs.length - 1,
                                             handles:[.5, 1, .5, 0], type:'bezier'}));
        kfs.forEach((k, i)=>{
          if(i === kfs.length - 1) return;
          const e = EASE[k[2] || 'inOut'];
          keyframes[i].handles[2] = e[0]; keyframes[i].handles[3] = e[1];        // leaves this keyframe…
          keyframes[i + 1].handles[0] = e[2]; keyframes[i + 1].handles[1] = e[3]; // …and arrives at the next
        });
        trackData[id] = {type:'BasicKeyframedTrack', __debugName:obj + ':' + prop, keyframes};
        trackIdByPropPath[JSON.stringify([prop])] = id;
      });
      tracksByObject[obj] = {trackData, trackIdByPropPath};
    });
    return {sheetsById:{Film:{staticOverrides:{byObject:{}},
              sequence:{subUnitsPerUnit:FPS, length:LEN, type:'PositionalSequence', tracksByObject}}},
            definitionVersion:'0.4.0', revisionHistory:[]};
  }

  /* ---- state ---- */
  let runId = 0, project = null, sheet = null, live = false, built = false, stars = null, line = '', lineSrc = null, typed = -1;
  let revealDone, revealP = new Promise(r=>{ revealDone = r; });
  let finishDone, doneP = new Promise(r=>{ finishDone = r; });
  const enabled = () => !!root && !document.documentElement.classList.contains('no-intro');
  const set = (k, v) => root.style.setProperty(k, String(Math.round(v * 1000) / 1000));
  const $ = id => document.getElementById(id);

  /* the starfield: hyperspace streaks when Warp.speed is high, drifting stars when low */
  function starfield(canvas){
    const ctx = canvas.getContext && canvas.getContext('2d');
    if(!ctx) return null;
    const S = [], N = innerWidth < 640 ? 150 : 260, cols = ['#F6F4FF', '#22F0FF', '#22F0FF', '#FF3DCB', '#C8FF3D'];
    let w = 0, h = 0, dpr = 1, raf = 0, speed = 1, alpha = 0;
    const seed = (s, far)=>{ s.x = Math.random()*2 - 1; s.y = Math.random()*2 - 1; s.z = far ? 1 : Math.random()*.95 + .05; s.pz = s.z; s.c = cols[Math.floor(Math.random()*cols.length)]; };
    for(let i=0;i<N;i++){ const s = {}; seed(s); S.push(s); }
    const size = ()=>{ dpr = Math.min(2, devicePixelRatio || 1); w = canvas.clientWidth; h = canvas.clientHeight; canvas.width = w*dpr; canvas.height = h*dpr; };
    const frame = ()=>{
      raf = requestAnimationFrame(frame);
      const cx = w/2, cy = h*.44, f = Math.max(w, h)*.55;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, w, h);
      ctx.globalAlpha = alpha; ctx.lineCap = 'round';
      for(const s of S){
        s.pz = s.z; s.z -= .0025 + speed*.05;
        if(s.z <= .02){ seed(s, true); continue; }
        const x = cx + s.x/s.z*f, y = cy + s.y/s.z*f, px = cx + s.x/s.pz*f, py = cy + s.y/s.pz*f;
        if(x < -50 || x > w + 50 || y < -50 || y > h + 50){ seed(s, true); continue; }
        const d = 1 - s.z;
        ctx.strokeStyle = s.c; ctx.lineWidth = .4 + d*2.2;
        ctx.beginPath(); ctx.moveTo(px, py); ctx.lineTo(x + .01, y); ctx.stroke();
      }
    };
    return {start(){ size(); addEventListener('resize', size); if(!raf) frame(); },
            stop(){ cancelAnimationFrame(raf); raf = 0; removeEventListener('resize', size); },
            set(sp, a){ speed = sp; alpha = a; }};
  }

  function build(){
    if(built) return true;
    if(!T || !T.getProject) return false;
    try{
      project = T.getProject('Captain’s Log · opening film', {state:projectState()});
      sheet = project.sheet('Film');
      const t = T.types, num = (v, r) => t.number(v, r ? {range:r} : undefined);
      const O = {};
      Object.keys(KEYS).forEach(obj=>{
        const props = {};
        Object.keys(KEYS[obj]).forEach(p=>{ props[p] = num(KEYS[obj][p][0][1]); });
        O[obj] = sheet.object(obj, props);
      });
      const title = $('inTitle'), typeEl = $('inType'), logo = root.querySelectorAll('.in-logo path');
      stars = starfield($('inStars'));
      const warp = {speed:1, a:0};
      O.Bars.onValuesChange(v=>set('--bars', v.h));
      O.Hud.onValuesChange(v=>set('--hud-a', v.a));
      O.Warp.onValuesChange(v=>{ warp.speed = v.speed; warp.a = v.a; if(stars) stars.set(v.speed, v.a); });
      O.Floor.onValuesChange(v=>{ set('--floor', v.rise); set('--floor-a', v.a); });
      O.Logo.onValuesChange(v=>{
        logo.forEach(p=>{ p.style.strokeDashoffset = String(1 - v.draw); });
        set('--logo-s', v.scale); set('--glow', v.glow);
      });
      O.Flash.onValuesChange(v=>set('--flash', v.a));
      O.Ripple.onValuesChange(v=>{ set('--rip-a', v.a); set('--rip-s', v.scale); });
      O.Title.onValuesChange(v=>{
        set('--title-a', v.a); set('--track', v.track);
        title.setAttribute('data-scramble', typeof Magic !== 'undefined' ? Magic.scramble(title.dataset.text, v.reveal) : title.dataset.text);
        title.classList.toggle('scrambling', v.reveal < 1);
      });
      O.Line.onValuesChange(v=>{
        set('--line-a', v.a);
        if(!line && v.a > 0){        // written as late as possible, so it can name the gameweek
          try{ line = (typeof lineSrc === 'function' ? lineSrc() : lineSrc) || ''; }catch(e){ line = ''; }
          line = line || 'Stardate unknown. Plotting a course anyway.';
        }
        const k = Math.round(v.type * line.length);
        if(k !== typed){ typed = k; typeEl.textContent = line.slice(0, k); }
      });
      O.Camera.onValuesChange(v=>{ set('--zoom', v.zoom); set('--cam-y', v.y); });
      O.Iris.onValuesChange(v=>{ set('--hole', v.hole); root.classList.toggle('hole', v.hole > 0); });
      // the playhead drives the timecode and the scrubber, like a video player
      const tc = $('inTc');
      T.onChange(sheet.sequence.pointer.position, pos=>{
        const fr = Math.round(pos * FPS), s = Math.floor(fr / FPS), f = fr % FPS;
        tc.textContent = '00:' + String(s).padStart(2, '0') + ':' + String(f).padStart(2, '0');
        set('--p', pos / LEN);
        if(pos >= OUTRO - .001) revealDone();
      });
      built = true;
      return true;
    }catch(e){
      if(window.console) console.warn('Opening film unavailable:', e && e.message);
      return false;
    }
  }

  function finish(){
    if(!live) return;
    live = false;
    if(stars) stars.stop();
    if(sheet) try{ sheet.sequence.pause(); }catch(e){}
    root.hidden = true;
    document.documentElement.classList.remove('intro-on');
    removeEventListener('keydown', onKey);
    revealDone(); finishDone();
  }
  /* jump to the outro: the camera flies in and the iris opens, a little faster */
  function skip(){
    if(!live || !sheet || !project.isReady){ finish(); return; }
    const from = Math.max(sheet.sequence.position, OUTRO);
    revealDone();
    sheet.sequence.play({range:[from, LEN], rate:1.35}).then(ok=>{ if(ok) finish(); });
  }
  function onKey(e){ if(e.key === 'Escape' || e.key === 'Enter' || e.key === ' ') { e.preventDefault(); skip(); } }

  /* opts.line: the captain's log entry typed under the name ("Stardate GW8. Morale: questionable.") */
  function play(opts){
    opts = opts || {};
    if(live) return doneP;
    if(!enabled() || (!opts.replay && performance.now() > 9000) || !build()){   // no film, or the page took ages to arrive
      if(root) root.hidden = true;
      document.documentElement.classList.remove('intro-on');
      revealDone(); finishDone();
      return doneP;
    }
    const run = ++runId;
    lineSrc = opts.line; line = ''; typed = -1; live = true;
    $('inType').textContent = '';
    root.hidden = false; root.classList.remove('hole');
    document.documentElement.classList.add('intro-on');
    addEventListener('keydown', onKey);
    if(stars) stars.start();
    // Theatre plays nothing until the project has read its state, so wait for that (a tick)
    project.ready.then(()=>{
      if(!live || run !== runId) return;
      sheet.sequence.position = 0;
      sheet.sequence.play({range:[0, LEN]}).then(ok=>{ if(ok) finish(); });
    });
    setTimeout(()=>{ if(live && run === runId) finish(); }, (LEN + 4) * 1000);   // never strand anyone behind the film
    return doneP;
  }
  /* watch it again from the menu */
  function replay(lineSource){
    if(live) return doneP;
    revealP = new Promise(r=>{ revealDone = r; });
    doneP = new Promise(r=>{ finishDone = r; });
    document.documentElement.classList.remove('no-intro');
    return play({line:lineSource, replay:true});
  }

  if(root){
    root.addEventListener('click', skip);
    const sk = document.getElementById('inSkip');
    if(sk) sk.addEventListener('click', e=>{ e.stopPropagation(); skip(); });
  }
  const setEnabled = on => { try{ localStorage.setItem('fplai_intro', JSON.stringify(on ? 'on' : 'off')); }catch(e){} };
  const isOn = () => { try{ return localStorage.getItem('fplai_intro') !== '"off"'; }catch(e){ return true; } };
  return {
    play, skip, replay, setEnabled, isOn,
    get playing(){ return live; },
    get reveal(){ return revealP; },     // settles as the film starts opening onto the app
    get done(){ return doneP; }          // settles when the film has gone
  };
})();
