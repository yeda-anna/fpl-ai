# Vendored libraries

Served from `/static/vendor/` and content-hashed by the server like every other
asset. No CDN. To upgrade, replace the file with the build from npm and update
the version here.

| File | Library | Version | Licence |
| --- | --- | --- | --- |
| `gsap.min.js` | [GSAP](https://gsap.com/docs/v3/) core (`gsap/dist/gsap.min.js`) | 3.15.0 | GSAP Standard "no charge" licence — https://gsap.com/standard-license (header kept in the file) |
| `DrawSVGPlugin.min.js` | GSAP DrawSVGPlugin (`gsap/dist/DrawSVGPlugin.min.js`) | 3.15.0 | same |
| `MotionPathPlugin.min.js` | GSAP MotionPathPlugin (`gsap/dist/MotionPathPlugin.min.js`) | 3.15.0 | same |
| `anime.min.js` | [anime.js](https://animejs.com/documentation) UMD bundle (`animejs/dist/bundles/anime.umd.min.js`), global `anime` | 4.5.0 | MIT — `anime-LICENSE.md` |
| `motion.min.js` | [Motion](https://motion.dev) for vanilla JS, UMD bundle (`motion/dist/motion.js`, already minified), global `Motion` | 13.4.3 | MIT — `motion-LICENSE.md` |
| `fonts/chakra-petch-latin-*.woff2` | [Chakra Petch](https://fonts.google.com/specimen/Chakra+Petch) 400 · 500/600/700 upright and italic, latin subset (`@fontsource/chakra-petch/files/`), declared with `@font-face` at the top of `styles.css` | 5.3.0 | SIL OFL 1.1 — `fonts/chakra-petch-LICENSE.txt` |
| `auto-animate.min.js` | [AutoAnimate](https://auto-animate.formkit.com) (`@formkit/auto-animate/index.min.js`), global `autoAnimate` | 0.10.0 | MIT — `auto-animate-LICENSE.txt` |

[Magic UI](https://magicui.design) is a React + Tailwind component collection,
so there is nothing to vendor: the effects we use (border beam, shimmer button,
hyper text, typing animation, ripple, orbiting circles,
number ticker, blur fade, animated list, animated beam, scroll progress) are re-implemented in plain CSS and JS in
`frontend/magic.js` and the "Magic UI" block of `frontend/styles.css`, following
the originals. MIT — `magicui-LICENSE.md`.

## Upgrading

- **Motion:** copy the file named above from the npm tarball
  (`npm pack motion@<v>`).
- **AutoAnimate** ships only as an ES module, so its `index.min.js` is wrapped
  as a classic script: the trailing `export{…}` is removed and the code is put
  inside `(function(){"use strict"; … window.autoAnimate=R;})();` (`R` is the
  name the minifier gave `autoAnimate` — check the `export` line when you
  upgrade). Nothing else is changed.

All use goes through `frontend/motion.js` (`FX`), `frontend/magic.js` (`Magic`)
each of which degrades to "no animation" if a
library fails to load.
