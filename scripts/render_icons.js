// Render frontend/icon.svg (written by scripts/digitize.py) to the PNG sizes phones use:
// 180 (iOS home screen) and 192 / 512 (the web manifest). Needs Playwright:
//   NODE_PATH=tests/node_modules node scripts/render_icons.js
// then shrink them to 256 colours: python3 -c "from PIL import Image; [Image.open(p).convert('RGB').quantize(256, dither=0).save(p, optimize=True) for p in ('frontend/icon-180.png', 'frontend/icon-192.png', 'frontend/icon-512.png')]"
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');
const FRONT = path.join(__dirname, '..', 'frontend');
(async () => {
  const svg = fs.readFileSync(path.join(FRONT, 'icon.svg'), 'utf8');
  const browser = await chromium.launch();
  for (const n of [180, 192, 512]) {
    const page = await browser.newPage({ viewport: { width: n, height: n }, deviceScaleFactor: 1 });
    await page.setContent(`<html><body style="margin:0;background:#05030F">${svg.replace('<svg ', `<svg width="${n}" height="${n}" `)}</body></html>`);
    await page.screenshot({ path: path.join(FRONT, `icon-${n}.png`) });
    await page.close();
  }
  await browser.close();
})();
