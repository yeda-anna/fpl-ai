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

All use goes through `frontend/motion.js`, which degrades to "no animation"
if any of these fail to load.
