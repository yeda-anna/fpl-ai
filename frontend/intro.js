/* Papa Ranjeet — the opening film. Plain JS, no build step.

   A few seconds of titles on every launch while the app loads underneath:
   letterbox bars close in over a grid floor where a couple of thousand drones
   wait in rows. They lift off in a wave, swoop up and fly into place, light up
   in the colours of the logo portrait (traced from its own lights by
   scripts/digitize.py into portrait.js) and dissolve into the picture itself
   (portrait.webp). The name decodes, the tagline — a villain's one-liner —
   types itself, then the camera pushes in and the film irises open onto the
   app. Six seconds in all.

   It is a Theatre.js sequence (vendor/theatre-core.min.js, global Theatre.core):
   every moving part is a sheet object, every move a keyframe in KEYS below,
   eased with cubic Béziers. KEYS is turned into Theatre's project state at
   load, so changing the film is editing numbers here. (Theatre Studio, the
   visual editor, is a development tool and is not shipped.) The drones are
   drawn on a canvas from Swarm.gather / ignite / glow / hover / photo.

   Tap anywhere, press Esc / Enter / Space, or "Skip intro" to jump to the end.
   No film when the visitor prefers reduced motion, turned it off in the menu,
   or when the app reloads itself — index.html decides that before the first
   paint (the `no-intro` class). */
'use strict';
const Intro = (() => {
  const root = document.getElementById('intro');
  const T = window.Theatre && window.Theatre.core;
  const LEN = 6, OUTRO = 5.4, FPS = 24;

  /* cubic-bezier easings for the curve that leaves a keyframe */
  const EASE = {linear:[0, 0, 1, 1], in:[.55, 0, 1, .45], out:[0, .55, .45, 1], inOut:[.65, 0, .35, 1],
                expoOut:[.16, 1, .3, 1], back:[.34, 1.56, .64, 1]};
  /* object → prop → [[seconds, value, easing to the next keyframe], …] */
  const KEYS = {
    Bars:   {h:     [[0, 0, 'expoOut'], [.6, 1], [OUTRO, 1, 'inOut'], [5.85, 0]]},
    Hud:    {a:     [[.2, 0, 'out'], [.6, 1], [OUTRO, 1, 'in'], [5.7, 0]]},
    Floor:  {rise:  [[0, .55, 'expoOut'], [.9, 1]],
             a:     [[0, 0, 'out'], [.5, .9], [3.2, .9, 'inOut'], [4.2, .35]]},
    Swarm:  {gather:[[.4, 0, 'linear'], [3.0, 1]],           // 0 all on the pad … 1 all in place (each drone eases its own flight)
             ignite:[[2.65, 0, 'out'], [3.05, 1]],          // flight white → their own colours
             glow:  [[2.9, 0, 'out'], [3.06, 1, 'out'], [3.9, .5]],
             hover: [[2.9, 0, 'out'], [3.5, 1]],
             photo: [[2.95, 0, 'inOut'], [3.65, 1]]},             // the drones hand over to the picture itself
    Flash:  {a:     [[2.92, 0, 'out'], [3.02, .45, 'out'], [3.45, 0]]},
    Title:  {a:     [[3.1, 0, 'out'], [3.3, 1]],
             reveal:[[3.1, 0, 'linear'], [3.8, 1]],
             track: [[3.1, .55, 'expoOut'], [4.0, .12]]},
    Line:   {a:     [[3.75, 0, 'out'], [3.85, 1]],            // the tagline: a villain's one-liner
             type:  [[3.9, 0, 'linear'], [4.85, 1]]},
    Camera: {zoom:  [[0, 1.12, 'out'], [3.0, 1, 'inOut'], [OUTRO, 1.05, 'in'], [LEN, 2.6]],
             y:     [[0, 3, 'out'], [3.0, 0]]},
    Iris:   {hole:  [[5.45, 0, 'in'], [LEN, 1]]}
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
  let runId = 0, project = null, sheet = null, live = false, built = false, drones = null, line = '', lineSrc = null, typed = -1;
  let revealDone, revealP = new Promise(r=>{ revealDone = r; });
  let finishDone, doneP = new Promise(r=>{ finishDone = r; });
  const enabled = () => !!root && !document.documentElement.classList.contains('no-intro');
  const set = (k, v) => root.style.setProperty(k, String(Math.round(v * 1000) / 1000));
  const $ = id => document.getElementById(id);

  /* the swarm: every drone in PORTRAIT (portrait.js) as a light on a canvas. They wait in
     rows on the launch pad, lift off back row last, swoop up and fly to their place in the
     portrait, then take their colours from it. The camera (the same zoom as the stage)
     applies to where they're going, so they fly into the push-in at the end. */
  const FLIGHT = '#CFF9FF';
  function swarm(canvas, mark){
    const ctx = canvas && canvas.getContext && canvas.getContext('2d'), P = typeof PORTRAIT !== 'undefined' ? PORTRAIT : null;   // portrait.js (a top-level const, not on window)
    if(!ctx || !P || !mark) return null;
    const n = P.d.length / 4, D = [];
    let seed = 11; const rnd = ()=>((seed = (seed * 16807) % 2147483647) / 2147483647);   // the same film every time
    const cols = Math.ceil(Math.sqrt(n * 2.4)), rows = Math.ceil(n / cols);
    const slot = Array.from({length:n}, (_, i)=>i);
    for(let i=n-1;i>0;i--){ const k = Math.floor(rnd() * (i + 1)); const t = slot[i]; slot[i] = slot[k]; slot[k] = t; }
    for(let i=0;i<n;i++){
      const r = Math.floor(slot[i] / cols), c = slot[i] % cols, pz = (r + .5) / rows, b = P.d[i*4+3] / 9;
      D.push({tx:P.d[i*4] / P.w, ty:P.d[i*4+1] / P.h, w:b, c:P.d[i*4+2], size:.62 + b * .5,
              px:(c + .5) / cols - .5, pz, delay:.04 + pz * .26 + rnd() * .1, swing:(rnd() - .5) * .5, ph:rnd() * 6.283});
    }
    const sprites = {};
    let w = 0, h = 0, dpr = 1, raf = 0, box = null;
    const V = {gather:0, ignite:0, glow:0, hover:0, zoom:1, camY:0, a:1};
    function sprite(col){
      const c = document.createElement('canvas'), s = 64; c.width = c.height = s;
      const g = c.getContext('2d'), gr = g.createRadialGradient(s/2, s/2, 0, s/2, s/2, s/2);
      gr.addColorStop(0, '#FFFFFF'); gr.addColorStop(.14, col); gr.addColorStop(.32, col + '88'); gr.addColorStop(1, col + '00');
      g.fillStyle = gr; g.fillRect(0, 0, s, s);
      return c;
    }
    P.pal.forEach((col, i)=>{ sprites[i] = sprite(col); }); sprites.flight = sprite(FLIGHT);
    function size(){
      dpr = Math.min(2, devicePixelRatio || 1); w = canvas.clientWidth; h = canvas.clientHeight;
      canvas.width = w * dpr; canvas.height = h * dpr;
      // where the portrait goes, in the stage's own (untransformed) layout
      let x = 0, y = 0, el = mark;
      while(el && el !== root){ x += el.offsetLeft; y += el.offsetTop; el = el.offsetParent; }
      box = {x, y, w:mark.offsetWidth, h:mark.offsetHeight};
    }
    const ease = t => t < .5 ? 4*t*t*t : 1 - Math.pow(-2*t + 2, 3) / 2;
    function frame(now){
      raf = requestAnimationFrame(frame);
      if(!box || !box.w) return;
      const t = now / 1000, ox = w / 2, oy = h * .44, z = V.zoom, cy = V.camY * h / 100;
      const unit = box.w / P.w * 3.1, horizon = h * .62, near = h * 1.02;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, w, h);
      ctx.globalCompositeOperation = 'lighter';
      for(const d of D){
        // on the pad
        const k = 1 / (1 + d.pz * 2.6), sx = ox + d.px * w * 1.5 * k, sy = horizon + (near - horizon) * k;
        // in the portrait, through the camera
        let tx = box.x + d.tx * box.w, ty = box.y + d.ty * box.h;
        tx = ox + (tx - ox) * z; ty = oy + (ty - oy) * z + cy;
        const f = ease(Math.min(1, Math.max(0, (V.gather - d.delay) / .6)));
        const bob = V.hover * Math.sin(t * 2.1 + d.ph) * .9 * z;
        // a swoop: up off the pad first, then across
        const mx = sx + (tx - sx) * .35 + d.swing * w * .25, my = Math.min(sy, ty) - h * (.18 + .12 * (1 - d.pz));
        const u = 1 - f, x = u*u*sx + 2*u*f*mx + f*f*tx, y = u*u*sy + 2*u*f*my + f*f*ty + bob * f;
        const base = (f > 0 ? unit * d.size * (1 + V.glow * .45) : unit * .55 * k) * (f > 0 ? (.75 + .25 * f) * Math.sqrt(z) : 1);
        const r = base * 2.6, lit = f >= 1 ? V.ignite : Math.max(0, V.ignite - (1 - f) * 4);
        const alpha = V.a * (f > 0 ? .55 + .45 * Math.min(1, f * 3) : .5) * (.55 + .45 * d.w);
        if(lit < 1){ ctx.globalAlpha = alpha * (1 - lit); ctx.drawImage(sprites.flight, x - r, y - r, r * 2, r * 2); }
        if(lit > 0){ ctx.globalAlpha = alpha * lit; ctx.drawImage(sprites[d.c], x - r, y - r, r * 2, r * 2); }
      }
      ctx.globalAlpha = 1; ctx.globalCompositeOperation = 'source-over';
    }
    return {count:n, V,
            start(){ size(); addEventListener('resize', size); if(!raf) raf = requestAnimationFrame(frame); },
            stop(){ cancelAnimationFrame(raf); raf = 0; removeEventListener('resize', size); }};
  }

  function build(){
    if(built) return true;
    if(!T || !T.getProject) return false;
    try{
      project = T.getProject('Papa Ranjeet · opening film', {state:projectState()});
      sheet = project.sheet('Film');
      const t = T.types, num = (v, r) => t.number(v, r ? {range:r} : undefined);
      const O = {};
      Object.keys(KEYS).forEach(obj=>{
        const props = {};
        Object.keys(KEYS[obj]).forEach(p=>{ props[p] = num(KEYS[obj][p][0][1]); });
        O[obj] = sheet.object(obj, props);
      });
      const title = $('inTitle'), typeEl = $('inType');
      drones = swarm($('inDrones'), $('inMark'));
      if(drones && $('inCount')) $('inCount').textContent = drones.count + ' drones';
      const V = drones ? drones.V : {};
      O.Bars.onValuesChange(v=>set('--bars', v.h));
      O.Hud.onValuesChange(v=>set('--hud-a', v.a));
      O.Floor.onValuesChange(v=>{ set('--floor', v.rise); set('--floor-a', v.a); });
      O.Swarm.onValuesChange(v=>{
        V.gather = v.gather; V.ignite = v.ignite; V.glow = v.glow; V.hover = v.hover;
        V.a = 1 - .72 * v.photo; set('--photo', v.photo);           // the drones dim as the picture comes up beneath them
      });
      O.Flash.onValuesChange(v=>set('--flash', v.a));
      O.Title.onValuesChange(v=>{
        set('--title-a', v.a); set('--track', v.track);
        title.setAttribute('data-scramble', typeof Magic !== 'undefined' ? Magic.scramble(title.dataset.text, v.reveal) : title.dataset.text);
        title.classList.toggle('scrambling', v.reveal < 1);
      });
      O.Line.onValuesChange(v=>{
        set('--line-a', v.a);
        if(!line && v.a > 0){        // written as late as possible, so it can name the gameweek
          try{ line = (typeof lineSrc === 'function' ? lineSrc() : lineSrc) || ''; }catch(e){ line = ''; }
          line = line || '“Free transfer? Yahan kuch bhi free nahi milta.”';
        }
        const k = Math.round(v.type * line.length);
        if(k !== typed){ typed = k; typeEl.textContent = line.slice(0, k); }
      });
      O.Camera.onValuesChange(v=>{ set('--zoom', v.zoom); set('--cam-y', v.y); V.zoom = v.zoom; V.camY = v.y; });
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
    if(drones) drones.stop();
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

  /* opts.line: the tagline typed under the name, a villain's one-liner (QUIPS.intro in app.js) */
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
    if(drones) drones.start();
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
