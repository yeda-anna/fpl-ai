/* Papa Ranjeet — motion (the FX layer). Plain JS, no build step.

   Five libraries, each doing what it's best at (all vendored in /static/vendor):
   - GSAP (+ DrawSVGPlugin, MotionPathPlugin): the landing timeline, drawing the
     neon strokes, the ball's flight into the goal and the sliding indicators in
     the dock and the section switcher.
   - anime.js: drawing a tab icon when it lights up, and the landing logo powering on.
   - Motion (motion.dev): physics and the viewport — cards blur-fade in as they
     scroll into view, figures tick up on springs, buttons spring back when
     pressed, lists drop in one by one and the scroll-progress line.
   - AutoAnimate: lists that change (the projections table re-sorting, the
     Copilot log) move their rows into place instead of jumping.
   - Theatre.js drives the opening film; that lives in intro.js.
   Magic UI's components are rebuilt in magic.js; the ones that need springs or
   in-view triggers (Blur Fade, Number Ticker, Animated List) are here.

   Every function is safe to call when a library failed to load or the visitor
   prefers reduced motion: it then leaves things in their finished state.
   The global is FX — `Motion` is the motion.dev library. */
'use strict';
const FX = (() => {
  const G = window.gsap, A = window.anime, M = window.Motion, AA = window.autoAnimate;
  const reduced = !!(window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches);
  if(G && window.DrawSVGPlugin && window.MotionPathPlugin) G.registerPlugin(DrawSVGPlugin, MotionPathPlugin);
  const canG = !reduced && !!G, canA = !reduced && !!A, canM = !reduced && !!(M && M.animate && M.inView);
  const canDraw = canG && !!window.DrawSVGPlugin, canPath = canG && !!window.MotionPathPlugin;
  const EXPO = [.16, 1, .3, 1];
  const wait = ms => new Promise(r=>setTimeout(r, ms));
  const clearInline = n => { n.style.opacity = ''; n.style.transform = ''; n.style.filter = ''; };

  /* ---- landing: draw the pitch, the logo flickers on, the boot lines type
         themselves (Magic UI TypingAnimation), the title decodes (HyperText),
         then the ball goes in ---- */
  let landTls = [], bootRun = 0;
  async function bootType(root){
    const run = ++bootRun, lines = Array.prototype.slice.call(root.querySelectorAll('.boot div'));
    lines.forEach(l=>{ if(!l.dataset.html) l.dataset.html = l.innerHTML; });
    if(reduced || typeof Magic === 'undefined'){ lines.forEach(l=>{ l.innerHTML = l.dataset.html; l.style.visibility = ''; }); return; }
    lines.forEach(l=>{ l.innerHTML = ''; l.style.visibility = 'hidden'; });     // keep each line's height
    await wait(260);
    for(const l of lines){
      if(run !== bootRun) return;
      const prefix = l.dataset.type || '', rest = l.dataset.html.slice(prefix.length);
      l.style.visibility = ''; l.innerHTML = '<span></span>';
      await Magic.typing(l.firstChild, prefix, {speed:13});
      if(run !== bootRun) return;
      l.insertAdjacentHTML('beforeend', rest);
      await wait(70);
    }
  }
  function landingIn(root){
    landTls.forEach(t=>t.kill()); landTls = [];
    if(typeof Magic !== 'undefined') Magic.hyperText(root.querySelector('.land-title'), {duration:1000});
    bootType(root);
    if(!canG) return;
    const q = s => root.querySelectorAll(s), card = root.querySelector('.land-card');
    const intro = G.timeline({defaults:{ease:'power2.out'}});
    intro.fromTo(card, {y:44, opacity:0}, {y:0, opacity:1, duration:.8, ease:'expo.out', clearProps:'transform,opacity'}, 0);
    if(canDraw){
      intro.fromTo(q('.scene .ln'), {drawSVG:'0%'}, {drawSVG:'100%', duration:1.1, stagger:.12}, .05)
           .fromTo(q('.scene .goal, .scene .net'), {drawSVG:'0%'}, {drawSVG:'100%', duration:.6, stagger:.08}, .55);
    }
    intro.fromTo(q('.scene .spot'), {scale:0, transformOrigin:'50% 50%'}, {scale:1, duration:.4, ease:'back.out(3)'}, .9);
    // the drone portrait powers up (anime.js)
    if(canA) A.animate(root.querySelector('.land-logo .neon-logo'), {opacity:[0, 1], scale:[.85, 1], duration:700, ease:'outBack', delay:300});
    landTls.push(intro);

    if(!canPath) return;
    const arc = root.querySelector('#shotPath'), ball = root.querySelector('#sceneBall'),
          word = root.querySelector('#goalWord'), net = root.querySelector('#goalNet');
    const shot = G.timeline({repeat:-1, repeatDelay:2.6, delay:1.4});
    shot.set(word, {opacity:0, scale:.5, transformOrigin:'50% 50%'})
        .fromTo(arc, {opacity:0}, {opacity:.9, duration:.3})
        .to(ball, {duration:1.15, ease:'power1.in', rotation:540, transformOrigin:'50% 50%',
                   motionPath:{path:arc, align:arc, alignOrigin:[.5, .5]}}, '<')
        .to(net, {scaleY:1.3, transformOrigin:'50% 0%', duration:.1, yoyo:true, repeat:3, ease:'sine.inOut'})
        .to(word, {opacity:1, scale:1, duration:.4, ease:'back.out(3)'}, '<')
        .to(word, {opacity:0, scale:1.2, duration:.5, delay:.9})
        .to(arc, {opacity:0, duration:.3}, '<');
    landTls.push(shot);
  }
  function landingOut(root, done){
    const finish = ()=>{
      landTls.forEach(t=>t.kill()); landTls = []; bootRun++;
      done();
    };
    if(!canG){ finish(); return; }
    const card = root.querySelector('.land-card');
    G.to(card, {y:30, opacity:0, duration:.32, ease:'power2.in'});
    G.to(root, {opacity:0, duration:.42, delay:.08, ease:'power1.in', onComplete:()=>{
      G.set([root, card], {clearProps:'opacity,transform'});
      finish();
    }});
  }

  /* ---- navigation: indicators slide, the icon draws itself, the season bar runs in ---- */
  function slide(ind, btn, box){
    if(!ind || !btn || !box) return;
    box.classList.add('has-ind');
    const x = btn.offsetLeft, w = btn.offsetWidth;
    if(G){
      if(canG && ind.dataset.placed) G.to(ind, {x, width:w, duration:.6, ease:'elastic.out(1,.78)'});
      else G.set(ind, {x, width:w});
    } else { ind.style.transform = 'translateX(' + x + 'px)'; ind.style.width = w + 'px'; }
    ind.dataset.placed = '1';
  }
  function drawIcon(svg){
    if(!svg || !canA || !A.svg) return;
    const paths = svg.querySelectorAll('path');
    if(!paths.length) return;
    A.animate(A.svg.createDrawable(paths), {draw:['0 0', '0 1'], duration:650, ease:'inOutQuad'});
  }
  function drawTitle(){
    const segs = document.querySelectorAll('#raceBar span');
    if(!segs.length || !canG) return;
    G.fromTo(segs, {scaleY:0}, {scaleY:1, duration:.4, ease:'back.out(2)', stagger:.012, clearProps:'transform'});
  }
  function viewIn(view){
    if(!view || !canM || gate) return;
    M.animate(view, {opacity:[0, 1], y:[14, 0]}, {duration:.45, ease:EXPO}).then(()=>clearInline(view));
  }
  function navigated(o){
    const dock = o.dock, segs = o.segs;
    slide(dock && dock.querySelector('.ind'), dock && dock.querySelector('button.on'), dock);
    if(segs && !segs.hidden){
      const sb = segs.querySelector('button.on');
      slide(segs.querySelector('.seg-ind'), sb, segs);
      if(sb && segs.scrollWidth > segs.clientWidth) segs.scrollTo({left:Math.max(0, sb.offsetLeft - 24), behavior:canG ? 'smooth' : 'auto'});
    }
    if(o.tabChanged){
      drawIcon(dock && dock.querySelector('button.on svg'));
      drawIcon(o.nav && o.nav.querySelector('button.on svg'));
      drawTitle();
    }
    viewIn(o.view);
  }
  function relayout(){
    const dock = document.getElementById('dock'), segs = document.getElementById('segs');
    [[dock, '.ind'], [segs, '.seg-ind']].forEach(([box, sel])=>{
      if(!box) return; const ind = box.querySelector(sel), b = box.querySelector('button.on');
      if(ind && b){ ind.dataset.placed = ''; slide(ind, b, box); }
    });
  }

  /* ---- content (Motion): new cards blur-fade in (Magic UI Blur Fade) — the ones on
         screen one after another, the ones further down as you scroll to them —
         and figures tick up on a spring (Magic UI Number Ticker). While the opening
         film runs, all of it waits and then plays as the film opens onto the app. ---- */
  const IN_SEL = '.tile, .card, .path, .plan, .gw-c, .stats-row > div, .need-team';   // the Copilot log is AutoAnimate's
  const CU_SEL = '.tile .val, .stat-v, .path .pv, .gw-score, .gw-c .v, .cu';
  const seen = new WeakSet();
  let batch = [], queued = false, gate = null, waiting = [];
  const onScreen = n => { const r = n.getBoundingClientRect(); return r.bottom > 0 && r.top < innerHeight && r.width > 0; };
  function blurFade(nodes){
    if(!nodes.length) return;
    M.animate(nodes, {opacity:[0, 1], y:[16, 0], filter:['blur(6px)', 'blur(0px)']},
              {duration:.55, ease:EXPO, delay:M.stagger(.05)}).then(()=>nodes.forEach(clearInline), ()=>nodes.forEach(clearInline));
  }
  function flush(){
    queued = false;
    if(gate) return;
    let nodes = batch.filter(n=>n.isConnected); batch = [];
    nodes = nodes.filter(n=>!nodes.some(o=>o !== n && o.contains(n)));          // a card inside a card moves with its parent
    if(!nodes.length || !canM) return;
    const now = nodes.filter(onScreen), later = nodes.filter(n=>!onScreen(n));
    try{
      blurFade(now.slice(0, 18));
      if(later.length){
        later.forEach(n=>{ n.style.opacity = '0'; });
        M.inView(later, n=>{ blurFade([n]); }, {margin:'0px 0px -6% 0px'});
      }
    }catch(e){ nodes.forEach(clearInline); }                                  // never leave a card hidden
  }
  function countUp(node){
    if(!canM || node.dataset.cu) return;
    const tn = Array.prototype.find.call(node.childNodes, n=>n.nodeType === 3 && /\d/.test(n.nodeValue));
    if(!tn || !/^\D{0,2}-?[\d,]*\.?\d+\D{0,3}$/.test(tn.nodeValue.trim())) return;    // a plain figure, not a name with a digit in it
    const m = tn.nodeValue.match(/^(\D*?)(-?[\d,]*\.?\d+)([\s\S]*)$/); if(!m) return;
    const target = parseFloat(m[2].replace(/,/g, '')); if(!isFinite(target)) return;
    const dec = (m[2].split('.')[1] || '').length, comma = m[2].indexOf(',') >= 0, final = tn.nodeValue;
    const fmt = v => { let t = v.toFixed(dec); if(comma){ const [a, b] = t.split('.'); t = a.replace(/\B(?=(\d{3})+(?!\d))/g, ',') + (b ? '.' + b : ''); } return m[1] + t + m[3]; };
    node.dataset.cu = '1';
    const run = ()=>{
      // rest when within a hair of the figure, so the last digits never crawl (then the exact text is put back)
      const big = Math.abs(target);
      tn.nodeValue = fmt(0);
      try{
        M.animate(0, target, {type:'spring', visualDuration:.8, bounce:0,
          restDelta:Math.max(big * 4e-4, .5 * Math.pow(10, -dec)), restSpeed:Math.max(big * 2e-3, 1),
          onUpdate:v=>{ tn.nodeValue = fmt(v); }, onComplete:()=>{ tn.nodeValue = final; }});
      }catch(e){ tn.nodeValue = final; }
    };
    // the figure only drops to 0 once its tick is certain to start, so it can never be stranded at 0
    const tick = ()=>M.inView(node, run, {amount:.3});
    if(gate) waiting.push(tick);
    else { if(onScreen(node)) tn.nodeValue = fmt(0); tick(); }
  }
  function scan(root){
    const hit = sel => (root.matches && root.matches(sel) ? [root] : []).concat(Array.prototype.slice.call(root.querySelectorAll(sel)));
    hit(IN_SEL).forEach(n=>{ if(!seen.has(n)){ seen.add(n); if(batch.length < 40) batch.push(n); } });
    hit(CU_SEL).forEach(countUp);
    if(!queued){ queued = true; requestAnimationFrame(flush); }
  }
  function observe(root){
    if(!root || !window.MutationObserver) return;
    new MutationObserver(muts=>muts.forEach(m=>m.addedNodes.forEach(n=>{ if(n.nodeType === 1) scan(n); })))
      .observe(root, {childList:true, subtree:true});
  }
  /* hold every entrance until `promise` settles (the opening film opening onto the app) */
  function hold(promise){
    if(!promise || !canM) return;
    gate = promise;
    const go = ()=>{ if(gate !== promise) return; gate = null; flush(); waiting.splice(0).forEach(f=>f()); };
    promise.then(go, go);
    setTimeout(go, 9000);                     // whatever happens to the film, the app makes its entrance
  }

  /* ---- Magic UI Animated List: items drop in one after another, on springs ---- */
  function listIn(items){
    items = Array.prototype.slice.call(items || []);
    if(!items.length || !canM) return;
    try{
      items.forEach(n=>{ n.style.opacity = '0'; });
      M.animate(items, {opacity:[0, 1], scale:[.85, 1], y:[-8, 0]},
                {type:'spring', stiffness:350, damping:30, delay:M.stagger(.11, {startDelay:.05})})
        .then(()=>items.forEach(clearInline), ()=>items.forEach(clearInline));
    }catch(e){ items.forEach(clearInline); }
  }

  /* ---- AutoAnimate: a list that moves its children into place when they change ---- */
  function auto(el, opts){
    if(!el || !AA || reduced) return null;
    if(!el._aa) el._aa = AA(el, Object.assign({duration:280, easing:'cubic-bezier(.16,1,.3,1)'}, opts || {}));
    return el._aa;
  }

  /* ---- touch: buttons spring back when pressed (Motion) ---- */
  function presses(){
    if(!canM) return;
    const SEL = '.dock button, .links button, .segs button, .btn, .cta, .chipset button, .team-pill, .icon-btn, .path, .gw-c';
    document.addEventListener('pointerdown', e=>{
      const b = e.target.closest && e.target.closest(SEL); if(!b || b.disabled) return;
      M.animate(b, {scale:.94}, {duration:.1, ease:'easeOut'});
      const up = ()=>{
        M.animate(b, {scale:1}, {type:'spring', stiffness:520, damping:14}).then(()=>{ b.style.transform = ''; }, ()=>{ b.style.transform = ''; });
        window.removeEventListener('pointerup', up); window.removeEventListener('pointercancel', up);
      };
      window.addEventListener('pointerup', up); window.addEventListener('pointercancel', up);
    }, {passive:true});
  }

  /* ---- Magic UI Scroll Progress: a neon line under the top bar fills as you scroll (Motion scroll) ---- */
  function scrollProgress(){
    const bar = document.getElementById('scrollProg');
    if(!bar || !M || !M.scroll) return;
    M.scroll(p=>{ bar.style.transform = 'scaleX(' + (typeof p === 'number' ? p : 0).toFixed(4) + ')'; });
  }

  /* ---- pointer: hover the name in the top bar and it decodes itself again (Magic UI HyperText's animateOnHover) ---- */
  function pointerGlow(){
    if(!window.matchMedia || !matchMedia('(hover:hover)').matches) return;
    const name = document.getElementById('brandName');
    if(name && typeof Magic !== 'undefined') name.parentNode.addEventListener('mouseenter', ()=>Magic.hyperText(name, {duration:650}));
  }

  /* ---- a wrong Team ID gets a little head-shake ---- */
  function shake(node){
    if(!node || !canG) return;
    G.fromTo(node, {x:-10}, {x:0, duration:.6, ease:'elastic.out(1,.3)', clearProps:'transform'});
  }

  /* ---- confetti: one canvas, the app's colours, a single burst ---- */
  const canvas = document.getElementById('fx'), ctx = canvas && canvas.getContext ? canvas.getContext('2d') : null;
  let bits = [], raf = 0, dpr = 1;
  function burst(x, y, n){
    if(reduced || !ctx) return;
    dpr = Math.min(2, window.devicePixelRatio || 1);
    canvas.width = innerWidth * dpr; canvas.height = innerHeight * dpr;
    const cols = ['#d2ff2e', '#2ee88f', '#8b7bff', '#efffc4', '#f2f6f5'];
    for(let i=0;i<n;i++){
      const a = Math.random()*Math.PI*2, v = 5 + Math.random()*9;
      bits.push({x, y, vx:Math.cos(a)*v, vy:Math.sin(a)*v - 6, g:.28 + Math.random()*.12, w:5 + Math.random()*6, h:3 + Math.random()*5,
        r:Math.random()*6.28, vr:(Math.random()-.5)*.4, c:cols[i % cols.length], life:1});
    }
    if(!raf) raf = requestAnimationFrame(step);
  }
  function step(){
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    bits = bits.filter(b=>b.life > 0 && b.y < innerHeight + 40);
    for(const b of bits){
      b.vx *= .99; b.vy += b.g; b.x += b.vx; b.y += b.vy; b.r += b.vr; b.life -= .012;
      ctx.save(); ctx.globalAlpha = Math.max(0, Math.min(1, b.life*1.6)); ctx.shadowColor = b.c; ctx.shadowBlur = 8*dpr;
      ctx.translate(b.x*dpr, b.y*dpr); ctx.rotate(b.r); ctx.fillStyle = b.c;
      ctx.fillRect(-b.w/2*dpr, -b.h/2*dpr, b.w*dpr, b.h*dpr); ctx.restore();
    }
    if(bits.length) raf = requestAnimationFrame(step);
    else { raf = 0; ctx.clearRect(0, 0, canvas.width, canvas.height); }
  }

  function start(){ presses(); pointerGlow(); scrollProgress(); window.addEventListener('resize', relayout); }
  return {reduced, start, landingIn, landingOut, navigated, relayout, observe, hold, listIn, auto, shake, burst};
})();
