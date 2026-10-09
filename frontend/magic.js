/* Footy — Magic UI, without React.

   Magic UI (https://magicui.design, MIT — vendor/magicui-LICENSE.md) is a React +
   Tailwind collection, so the effects we use are re-built here in plain JS, with
   their CSS in the "Magic UI" block of styles.css. Each function follows the
   original component and is named after it:

     hyperText     HyperText          a heading scrambles, then resolves left to right
     typing        TypingAnimation    text types itself in, one character at a time
     meteors       Meteors            streaks of light across a container
     ripple        Ripple             rings that breathe out from a centre
     orbit         OrbitingCircles    small bodies circling a centre
     borderBeam    BorderBeam         a beam of light running round an element's edge
     shimmer       ShimmerButton      a spark racing round a button's edge
     beamArrow     AnimatedBeam       a beam of light flowing from one thing to another
     retroGrid     RetroGrid          a perspective grid floor, scrolling towards you
     (CSS only)    AnimatedShinyText, ScrollProgress (.mg-shiny, .mg-progress)

   Number Ticker, Blur Fade and Animated List need springs and in-view triggers,
   so they live in motion.js on top of Motion. Everything here leaves the final
   state in place when the visitor prefers reduced motion. */
'use strict';
const Magic = (() => {
  const reduced = !!(window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches);
  const CHARS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789#%&*+<>/\\';
  const rnd = n => Math.floor(Math.random()*n);

  /* HyperText: one frame of the scramble. Letters up to `progress` are real, the rest random. */
  function scramble(text, progress){
    const upto = progress * text.length;
    let out = '';
    for(let i=0;i<text.length;i++){
      const ch = text[i];
      out += (ch === ' ' || i < upto) ? ch : CHARS[rnd(CHARS.length)];
    }
    return out;
  }
  /* The real text stays in the element the whole time (screen readers and textContent
     see it); the scramble is painted over it by .mg-hyper.scrambling::after. */
  const running = new WeakMap();
  function hyperText(el, opts){
    if(!el) return;
    opts = opts || {};
    const text = el.textContent, duration = opts.duration || 800;
    cancelAnimationFrame(running.get(el) || 0);
    if(reduced || !text.trim()){ el.classList.remove('scrambling'); return; }
    const t0 = performance.now();
    el.classList.add('mg-hyper', 'scrambling');
    const step = now => {
      const p = Math.min(1, (now - t0) / duration);
      el.setAttribute('data-scramble', scramble(text, p));
      if(p < 1) running.set(el, requestAnimationFrame(step));
      else { el.classList.remove('scrambling'); el.removeAttribute('data-scramble'); running.delete(el); }
    };
    running.set(el, requestAnimationFrame(step));
  }

  /* TypingAnimation: types `text` into `el`; resolves when done. */
  function typing(el, text, opts){
    opts = opts || {};
    const speed = opts.speed || 26, delay = opts.delay || 0;
    return new Promise(done=>{
      if(!el) return done();
      if(reduced){ el.textContent = text; return done(); }
      el.textContent = '';
      let i = 0;
      const tick = ()=>{ i++; el.textContent = text.slice(0, i); if(i < text.length) setTimeout(tick, speed); else done(); };
      setTimeout(tick, delay);
    });
  }

  /* Meteors: `n` streaks of light, each on its own random path and pace. */
  function meteors(box, n, opts){
    if(!box || reduced) return;
    opts = opts || {};
    const angle = opts.angle == null ? 215 : opts.angle, w = box.clientWidth || innerWidth;
    box.querySelectorAll('.mg-meteor').forEach(m=>m.remove());
    for(let i=0;i<n;i++){
      const m = document.createElement('span');
      m.className = 'mg-meteor' + (i % 3 === 1 ? ' m' : i % 3 === 2 ? ' l' : '');
      m.style.setProperty('--angle', -((2*angle) % 360) + 'deg');   // Magic UI turns the head twice (rotate + transform); this is the net heading
      m.style.left = Math.floor(Math.random() * w * 1.2) + 'px';
      m.style.animationDelay = (Math.random()*4 + .2).toFixed(2) + 's';
      m.style.animationDuration = Math.floor(Math.random()*6 + 4) + 's';
      box.appendChild(m);
    }
  }

  /* Ripple: `n` concentric rings breathing out from the middle of `box`. */
  function ripple(box, n, opts){
    if(!box) return;
    opts = opts || {};
    const base = opts.size || 70, step = opts.step || 34;
    box.innerHTML = Array.from({length:n}, (_, i)=>
      `<i style="--i:${i};width:${base + i*step}px;height:${base + i*step}px;opacity:${Math.max(.08, .5 - i*.09).toFixed(2)}"></i>`).join('');
  }

  /* OrbitingCircles: little satellites on a circular path round the middle of `box`. */
  function orbit(box, bodies, opts){
    if(!box) return;
    opts = opts || {};
    const radius = opts.radius || 50, duration = opts.duration || 12;
    box.innerHTML = `<svg class="mg-orbit-path" aria-hidden="true"><circle cx="50%" cy="50%" r="${radius}"/></svg>` +
      bodies.map((b, i)=>`<span class="mg-orbit ${b.cls || ''}${opts.reverse ? ' rev' : ''}" style="--angle:${Math.round(360/bodies.length*i)};--radius:${radius};--dur:${duration};--s:${b.size || 8}px">${b.html || ''}</span>`).join('');
  }

  /* BorderBeam: a beam of light that runs round the edge of `el` (CSS offset-path). */
  function borderBeam(el, opts){
    if(!el || el.querySelector(':scope > .mg-beam')) return;
    opts = opts || {};
    const b = document.createElement('span');
    b.className = 'mg-beam'; b.setAttribute('aria-hidden', 'true');
    if(opts.size) b.style.setProperty('--size', opts.size + 'px');
    if(opts.duration) b.style.setProperty('--dur', opts.duration + 's');
    if(opts.delay) b.style.setProperty('--delay', opts.delay + 's');
    if(opts.from) b.style.setProperty('--from', opts.from);
    if(opts.to) b.style.setProperty('--to', opts.to);
    el.appendChild(b);
    return b;
  }

  /* ShimmerButton: the spark that races round the edge. The markup is in place
     already when a button is written with it; this adds it to one that isn't. */
  function shimmer(btn){
    if(!btn || btn.querySelector('.mg-spark')) return;
    btn.classList.add('mg-shimmer');
    btn.insertAdjacentHTML('afterbegin', '<span class="mg-spark" aria-hidden="true"><span></span></span>');
  }

  /* AnimatedBeam, inline: a curved beam of light from "out" to "in". */
  const beamArrow = () => `<svg class="mg-beam-arr" viewBox="0 0 46 12" aria-hidden="true">
    <path class="trk" d="M2 8Q23 1 40 8"/><path class="flow" d="M2 8Q23 1 40 8"/><path class="tip" d="M38.6 4.6 44 8.4l-6.2 1.3z"/></svg>`;

  /* RetroGrid: markup for a perspective grid floor (the CSS does the rest). */
  const retroGrid = () => '<div class="retro"><div class="retro-plane"><div class="retro-grid"></div></div></div>';

  return {reduced, scramble, hyperText, typing, meteors, ripple, orbit, borderBeam, shimmer, beamArrow, retroGrid};
})();
