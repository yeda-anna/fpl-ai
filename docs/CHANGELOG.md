# Changelog

## 2026-10-17 — Your season, as a rank chart

- **Home → My squad** ends with **Your season**: your overall rank after every
  gameweek, one green line, best at the top. Rank runs on a log scale, so climbing
  from 2M to 1M looks as big as 200K to 100K. The current rank sits at the end of the
  line, your best week is ringed, and a line above says where you are, how far you
  moved last week and your best rank so far.
- Hover or tap the chart (or focus it and use ← → Home End) for a week's rank, its
  climb or drop, points and any hit. **Week by week** opens the same numbers as a table.
- `GET /api/entry/{id}` now carries `season`: each ranked week with its `climb`
  (positive = up the table), plus `best`, `worst` and `latest`. `history` is unchanged.
- Drawn by hand as SVG at the card's own width (redrawn on resize), in the race-day
  tokens; no new library. Works for the demo team too.

## 2026-10-17 — Behind the scenes: every change is built and checked before it ships

- Nothing changes in the app itself. Every pull request is now **built the same
  way Railway builds the live site, started up and smoke-tested** before it can
  be merged, so a broken build or a change that won't start never reaches you.
- The unit tests also run on every pull request, on both the Python the live
  site uses and the older one the app promises to support, along with a syntax
  check of the app's scripts and the colour-contrast check.
- `scripts/smoke.sh` checks any running copy (local, preview or live) in one go.

## 2026-10-17 — Logs you can search

- The server now writes **one JSON line per event** to stdout, which Railway's log
  explorer reads as structured logs: filter by `@event:fpl.fetch_failed`,
  `@status:>=500` or `@route:/api/solve` and so on (`docs/DEPLOYMENT.md` → Logs).
- Every request gets a line with its method, **route template**, status and time
  taken. Team and league IDs are never logged: routes are logged as templates
  (`/api/entry/{team_id}`) and FPL calls by kind (`entry`).
- Problems that used to vanish now show up: an FPL outage (and whether a stale
  copy was served instead), a failed start-up warm-up, a missing Elo prior or
  recent-minutes feed, and any plan the solver couldn't make feasible. Engine
  rebuilds and every solve log how long they took.
- uvicorn's own lines go through the same JSON format on stdout (they used to go
  to stderr, which Railway shows as errors); its plain access log is replaced by
  the request line. `LOG_LEVEL` (default `INFO`) sets how much is written.

## 2026-10-16 — All your mini-leagues, from a Team ID

- **Leagues → Mini-league** now opens with **every league a manager is in**: type any
  FPL Team ID (yours is filled in) and it reads their public profile. For each
  private league: their place and how far they moved since last week, their points
  and this week's score against the league's average, the leader, the gap to the
  leader and to the managers either side. FPL's own leagues (Overall, country,
  club …) and head-to-head leagues are listed with place and percentile, and four
  tiles summarise it (leagues, leading, moving, best place).
- **Analyse** on a league opens the existing rival analysis (what they own, effective
  ownership, who's likeliest to win) for it, and the manager is **always in the
  table**, tagged "you", even when they sit outside the top 12.
- New `GET /api/entry/{id}/leagues`; `GET /api/league/{id}` takes `entry=`. Up to
  15 private leagues are read in full, four at a time; the demo team is in none.

## 2026-10-13 — The planner's new rules: form, chance to score, fitness, opponents

- **Recent form counts.** A player's scoring rate now blends his season xG/xA
  with his last six gameweeks (up to 35%) and, a little, the goals and assists he
  actually got (up to 25%). Minutes already came from recent gameweeks.
- **Chance to score** for every fixture (`1 − e^(−xG)`): on the player sheet, and
  in Players → Projections as "Show: Chance to score" and a sort.
- **Fitness rule:** Plan → Transfers won't buy, captain or vice-captain anyone
  under 75% to play in the coming gameweek (Advanced settings: 100 / 75 / 50 /
  anyone), and says who it left out.
- **Opponents in poor form:** each club's last six games lean its attack and
  defence (by at most 20–25%), so a side that has stopped scoring or started
  leaking is treated that way. The player sheet flags "opponent leaky lately".

## 2026-10-13 — Race day: a new look

- The whole app is redesigned after a racing-game leaderboard the owner supplied:
  a dark teal night, flat teal surfaces, italic **Chakra Petch** type (vendored,
  OFL), and every button, tab and chip slanted like a speed stripe. Lime is the
  main action and the open tab, green is progress, purple is the selected
  sub-page and the projection bars.
- Under every title, the **season as a race**: a segment a gameweek, lime to green
  up to now, the next one outlined, and how many gameweeks are left.
- Tables are rows on the surface with hairlines between; tiles carry big italic
  numbers; bars are slanted purple segments; the pitch has lime markings and a
  touchline glow; phone sheets are trays with a grabber.
- Gone: the meteor shower and its ground impacts, the neon sky wires, the
  sci-fi corner brackets, scanlines, scan beam and monospace readouts, and the
  glows. The background is still.
- Kept: the drone intro film (its title, tagline, progress line and floor now in
  the new colours), the landing pitch scene, the demo team and every feature.

## 2026-10-11 — A demo team for people who don't play FPL

- The first screen now offers **See a demo team — no account needed**. It opens
  *Gut Feeling FC*, a made-up side picked on vibes: the priciest names the
  budget allows, whoever is left, an injured star kept "for the badge", a
  Wildcard burnt in GW2, a hit every third week and a shocker last week. The
  squad is legal under this season's rules and uses real players, prices and
  fixtures, so Grade, Transfers, Chips, Players and Ask all work on it.
- Home → My squad roasts it from its own list and opens with a short tour:
  FPL in one sentence, then a button for each part of the app and what it does.
- Nothing is saved: the demo lives in this tab only, a team you've saved stays
  saved, and "Leave the demo" (on the tour or in the menu) goes back.
- Links to the app now unfurl properly on LinkedIn, WhatsApp and Slack: Open
  Graph title, description and image, made absolute for whichever address the
  app is served from.

## 2026-10-09 — Tell the app about a transfer FPL hasn't published yet

- The previous fix didn't help: FPL keeps a transfer for the coming gameweek
  **private** — only the manager, logged in, can see it — until the deadline
  passes, so neither the picks nor the public transfers list carry it.
- Home → My squad now has a **Transfers made for GW…** card: pick the player
  sold and the player bought (same position) and every team view — squad, best
  XI, bank, free transfers, the solver, chips, Grade and Ask — plans from the
  updated squad. The transfers are kept on the device per team
  (`fplai_made`), sent as `made=out-in,…`, can be removed, and drop out on their
  own once the deadline passes and FPL's picks carry them.

## 2026-10-09 — Transfers show up the moment you make them

- A transfer made on the FPL site or app for the coming gameweek now shows in
  your squad on the next refresh. FPL only moves it into your "picks" when the
  deadline passes, so the app now also reads your transfers list and applies the
  ones made since the last deadline: the player swaps in, the bank moves by the
  sale and purchase prices, and the free transfers go down (not under a Wildcard
  or Free Hit). Home → My squad names them under Free transfers
  ("Made for GW9: Out → In"), and the solver plans from the updated squad.

## 2026-10-09 — The tagline holds, and the meteors land

- In the opening film the tagline now **stays on screen for six seconds** after
  it has typed, over the hovering drone portrait, before the camera pushes in
  (about 11½ seconds in all; still skippable at any moment).
- **Meteors strike the ground.** Every meteor in the shower now falls all the
  way to the grid floor and hits it: a white-hot flash, two shockwaves rolling
  out flat across the floor, sparks thrown up and a glowing crater that cools
  over a couple of seconds, while the floor flares where it's struck. Each
  meteor pauses between falls, so the sky stays busy without turning to noise.

## 2026-10-09 — A six-second film with a villain's tagline

- The opening film now runs **six seconds**: the drones take longer over their
  flight, and the name and tagline have time to land before the camera pushes in.
- **The tagline is a one-liner in the manner of a 70s Hindi-film villain**, a
  different one each launch — “Free transfer? Yahan kuch bhi free nahi
  milta.”, “Hit lega? Le le. Points main le jaaunga.”, “Wildcard khel le. Ab
  tujhe koi nahi bacha sakta.” They're written for the app (`QUIPS.intro`),
  not quotes from any actor or film.

## 2026-10-09 — Papa Ranjeet, and a meteor shower

- The app is now called **Papa Ranjeet**: the page title, home-screen name,
  top bar, landing screen, menu and the opening film's title. Saved teams and
  settings carry over.
- **A meteor shower** (Magic UI Meteors) now falls across the night sky behind
  every page — 18 streaks on a phone, up to 36 on a wide screen — in cyan,
  magenta and lime, and the landing sky has twice as many. Reduced motion turns
  it off.
- e2e: 107 checks.

## 2026-10-09 — Papa Ranjeet

- The app is now called **Papa Ranjeet**: the page title, home-screen name,
  top bar, landing screen, menu and the opening film's title. Nothing else
  changes — saved teams and settings carry over.

## 2026-10-09 — Footy, and a logo made of drones

- **A new name: Footy.** New tagline: “Football’s a funny old game. Might as
  well do the maths.” The page title, home-screen name and icons follow it, and
  the readout above each title is `SYS//…` again. Saved teams and settings
  carry over.
- **The logo is the drone portrait** supplied by the owner, used as it is: a
  face made of points of light, cropped round the face for the app and the
  home-screen icons.
- **The opening film is a drone show:** about 2,600 drones, traced from the
  portrait's own lights, wait in rows on a neon grid floor, lift off in a wave,
  swarm and lock into place, light up in its colours and dissolve into the
  picture itself. The name decodes, the log types “Matchday GW8.”
  and a line of dark humour, and the camera pushes in as the film opens onto
  the app. Still Theatre.js, still under five seconds, still skippable.
- e2e: 105 checks.

## 2026-10-08 — Captain’s Log: a new name, an opening film, and four more ways to move

- **A new name and logo.** Mug’s Game FC is now **Captain’s Log** — your FPL
  captain, and a ship’s log for the sci-fi look. The logo is a football with a
  planet’s ring round it, in the same neon (magenta ball, cyan ring, lime star).
  New tagline: “Your rank is lost in space. Might as well do the maths.” The
  page title, home-screen name and icons (SVG plus PNGs for iOS and Android)
  follow it; the readout above each title is now `LOG//PLAN/TRANSFERS · GW8`.
  Your saved team and settings carry over.
- **An opening film on every launch**, about four and a half seconds and
  skippable at any moment: letterbox bars, a jump out of hyperspace over a
  scrolling grid floor, the logo drawing itself and igniting, the name decoding,
  the captain’s log typing “Stardate GW8. Morale: questionable.”, then the
  camera flies into the ball and the film irises open onto the app — which has
  been loading underneath the whole time. Built with
  [Theatre.js](https://www.theatrejs.com/docs/latest). Turn it off (or watch it
  again) from the menu; it never plays with reduced motion, nor when the app
  reloads itself.
- **[Magic UI](https://magicui.design) effects**, rebuilt without React: titles
  decode themselves (HyperText), the landing’s boot lines type out, meteors
  cross the landing sky, rings and satellites circle the logo, a beam of light
  runs round loading cards and the chosen plan (Border Beam), a spark races round
  “Let’s go” and “Suggest transfers” (Shimmer Button), light flows from the
  player out to the player in (Animated Beam), the night sky has a moving grid
  floor (Retro Grid), the readout glints, and a neon line under the top bar
  fills as you scroll.
- **[Motion](https://motion.dev):** cards blur-fade in as you scroll to them,
  figures tick up on springs, buttons spring back when pressed, and the
  Copilot’s and Grade’s reasons drop in one by one.
- **[AutoAnimate](https://auto-animate.formkit.com):** sorting or filtering the
  projections now glides the rows into their new order instead of redrawing the
  table, and the Copilot keeps a log of your questions — newest on top, older
  answers folded underneath (tap to open).
- Pages, scripts and data are now sent gzipped. The three new libraries add
  about 86 KB to the first load and nothing after (they’re cached for good).
- e2e: 104 checks.

## 2026-10-08 — The HUD: a sci-fi layer over the neon

Same tabs, same pages, same flow — dressed as a ship's console.

- **Target-lock corners** on every card, tile and plan: cyan brackets that turn
  lime on hover.
- **Readouts in monospace:** labels, card titles, tabs, the section switcher,
  table heads and buttons are uppercase mono. Above every page title an
  "eyebrow" shows where you are — `SYS//PLAN/TRANSFERS · GW8` — with a blinking
  status light, and the title glitches in on change.
- **Screen texture:** faint CRT scanlines, a dot grid and a slow scan beam
  across the sky. The pitch is a hologram: scanlines over the turf and a light
  sweep running down it.
- **Landing boot sequence:** "LINK FPL MAINFRAME … OK", "xPTS ENGINE … ONLINE",
  "SOLVER CORE … ARMED", then a blinking cursor waits for your Team ID. The
  logo sits inside a spinning radar ring.
- Primary buttons get a hazard-stripe sheen; secondary buttons are cyan
  outlines; corners are tighter throughout.
- Reduced motion turns off the beam, the sweep, the glitch and the spin.

## 2026-10-07 — Your name up in lights, and a verdict on your week

- Home is now titled with your team's name, read from FPL with your Team ID,
  instead of "Home".
- My squad opens with a dark football roast of your last gameweek instead of a
  description — "62 points, 10 above average. A mid-table side that thinks it's
  in a title race in October." It's picked by your score against the average,
  stays the same until a new gameweek is scored, and lives only in the page
  head; the numbers below stay plain.
- e2e: 93 checks.

## 2026-10-07 — Neon, five tabs, and your Team ID remembered

- **One neon look.** Near-black violet, dark glass, and three neons: lime for
  "do this", cyan for lines and information, magenta for the ball and
  celebration. The theme picker and the five other themes are gone. The pitch is
  dark turf with cyan neon markings. Every text colour passes AA.
- **Motion by GSAP and anime.js**, vendored in `frontend/vendor/` (no CDN) and
  wrapped by `frontend/motion.js`. On the landing screen the pitch and goal draw
  themselves, the neon mug flickers on, and the ball flies along a dotted path
  into the net. Neon wires cross the sky with pulses of light running along
  them. Tab icons draw themselves, the dock capsule and section pill slide,
  the title line redraws, cards rise in, figures count up, and buttons spring.
  Reduced motion turns all of it off.
- **Five tabs instead of ten views.** Home (My squad · Grade · Picks), Plan
  (Transfers · Chips), Players (Projections · Compare · Prices · Line-ups · Set
  pieces · DEFCON), Leagues, Ask. No "More" sheet. Every sub-page has an address
  and the old ones still work. How it works, Refresh app and Forget team live in
  the ⓘ menu.
- **The Team ID is asked once per device.** The landing screen asks on the first
  visit and saves it in the browser; after that you go straight to your team.
- **Roast mode is gone**: no roasts under suggestions, no verdict banner, no
  switch. The light British and Indian dark humour stays on the landing screen
  and under the loader.
- The server now fingerprints assets in sub-folders, so the vendor libraries
  are content-hashed and cached as immutable like the rest.
- Tests: the e2e suite is rewritten for the new app — 88 checks on phone,
  desktop and reduced motion.

## 2026-10-07 — Stage lights, roasts and two new palettes

- **A stage, not a spreadsheet.** Two stage-light beams sweep the backdrop;
  cards and tiles catch a glow that follows your pointer; the primary button,
  the selected plan and the logo breathe; cards, tiles and plans rise in one
  after another; numbers count up to their value; the players walk onto the
  pitch row by row; bars and sparklines grow; the page title catches a glint on
  every navigation; the phone dock's capsule slides (with a little overshoot) to
  the tab you tap; theme changes cross-fade. Everything stops under
  `prefers-reduced-motion`.
- **Two new themes.** **Open Mic** (ink-violet, lilac glass, lime and hot pink)
  is the new default for first visits; **Dark Roast** (espresso, cream glass,
  saffron and ember). Forest, Midnight, Graphite and Chalk stay, and a saved
  choice is respected. All six pass WCAG AA — `scripts/check_contrast.py` checks
  them and exits non-zero on a miss.
- **Roast mode.** A deadpan roast under every suggestion — the captain picks,
  differentials and value picks, each solver plan, chip timing, your Rate My Team
  grade and every fix, each Copilot answer, comparisons, league favourites and
  every Scout tab — in Indian-household and chess-blunder roast-comedy register.
  Roasts are separate labelled asides, never inside the advice, a number or an
  error. The dashboard opens with **This week's verdict**, a banner with a
  rotating lit border that reacts to your score against the average; **Roast me
  again** re-rolls it. One switch (More → Theme) turns every roast off.
- **Confetti** for a big week, an A grade, a solver plan that gains and, if you
  tap the logo five times, no reason at all.
- **Rate My Team** draws its grade inside a ring that fills to your score.
- Lines now live in `frontend/roast.js`; the engine and effects are in `app.js`.
- Tests: 108 e2e checks (was 88), including counters, the verdict banner, a
  roast on every view, the roast switch and the six themes.

## 2026-10-07 — Clean loads, right free transfers, darker humour

- **Free transfers were one too many after a chip.** A Wildcard or Free Hit week
  uses up that week's own free transfer and keeps what was banked, so the next
  week you hold the same number you had going in. The replay (and the solver)
  added one on top. A manager on 1 free transfer who had wildcarded saw 2; one
  on 2 saw 3. Fixed in `rules.roll_free_transfers`, used by both. The solver
  plan now shows the free-transfer count FPL would give for each later week.
  A history that is newer than the cached calendar no longer counts a gameweek
  the squad on screen hasn't reached.
- **Mobile always loads clean.** The page and every API answer are `no-store`
  (the browser keeps no copy and back/forward can't resurrect a stale page);
  scripts and styles stay content-hashed and immutable, so reloads are still
  quick. The first read of your team after each page load re-reads it from FPL
  (`fresh=1`), the app re-reads it after ten minutes away, a page restored from
  the back/forward cache reloads, and **More → Refresh app** gives home-screen
  apps the reload button they lack.
- **Indian dark humour**, alongside the British kind: a line on the welcome
  screen, under every loading spinner, and a mood line on the dashboard that
  reacts to your gameweek score against the average. Never in errors, numbers or
  advice.
- Tests: 88 e2e checks, plus `tests/test_free_transfers.py`.

## 2026-10-06 — Crisp glass and themes

- **Crisp frosted glass.** Panels are evenly lit with a fine light rim along
  the top edge and a two-layer soft shadow; the coloured glow in the corner of
  stat tiles is gone; backdrop orbs are quieter.
- **Theme picker** (palette button, or More → Theme): Forest, Midnight,
  Graphite, Chalk and Match system. Each follows 60:30:10 with the same lime and
  sky highlights, and every text colour passes WCAG AA in every theme. Old
  light/dark settings carry over.
- Keyboard focus ring in the highlight colour.
- e2e: 81 checks (theme picker, every theme, persistence, legacy settings).

## 2026-10-06 — Always fresh

- Returning visitors no longer see an old stylesheet. `index.html` is served
  `no-cache` with an ETag; CSS/JS links are rewritten to content hashes and
  cached as immutable; `/version` lets an open or home-screen app notice a new
  deploy and reload itself when brought back to the foreground.
- The manual `?v=N` cache-buster is gone.
- e2e: three new checks (build id, fingerprinted assets, revalidation) — 67.

## 2026-10-06 — Forest & lime

- **New palette, 60:30:10.** Forest `#1B4332` background (60%), mint `#96E6A1`
  and sea green `#84FAB0` content (30%), lime `#D4FC79` and sky `#8FD3F4`
  highlights (10%). Text on highlights is forest. Light theme follows the same
  split on a pale lime base. AA contrast re-checked.
- Logo, app icon, manifest and `theme-color` recoloured to match.
- **Repository guidance:** `CLAUDE.md`, `AGENTS.md`, `.claude/settings.json`,
  six specialist agents (model analyst, solver engineer, UI designer, QA tester,
  FPL data scout, release manager) and six skills (run locally, e2e test,
  calibrate xPts, deploy to Railway, brand and design, add a feature).
- `docs/`: architecture, model, solver, API, design, data sources, testing,
  deployment and this changelog.
- `tests/`: the Playwright suite is now in the repo (`npm --prefix tests test`,
  `BASE_URL` for live runs, non-zero exit on failure).
- `scripts/calibrate.py`: level and correlation vs FPL's `ep_next`, per-player
  spot checks, MAE against a reference CSV.

## 2026-10-05 — Mug's Game FC (`f42b18b`)

- Rebranded from Lucky Socks to **Mug's Game FC**, with light British humour in
  taglines, empty states and loading lines.
- Animated mug-and-football logo: steam, bob, hover clink and hop, a welcome
  dunk. Respects reduced motion.

## 2026-10-05 — Lucky Socks: glass and the app shell (`e7916fb`)

- Quirky interim name **Lucky Socks** and a logo that doesn't look like "AI".
- Glassmorphism design with blur kept to floating chrome.
- Phone app shell below 1024px: top bar, floating tab dock, More sheet,
  bottom-sheet details; installable as a home-screen app.
- The Team ID is asked on every launch, remembered, and skippable.
- Fixed phone overflow (fluid pitch, `minmax(0,1fr)` grids) and a stale-result
  race in Expected Points search.

## 2026-10-03 — Railway (`e70777d`)

- Railway deployment via `railway.json` (Railpack, explicit start command
  `uvicorn main:app --app-dir backend …`, `/healthz`), `.python-version` 3.12.

## 2026-10-03 — FPL AI: redesign and model upgrades (`2f27324`)

- Redesigned UI (solver page with plan list, pitch and gameweek stepper).
- Rules read from `bootstrap-static` (2026/27 10-point goalkeeper goal, chip
  windows, banked transfers, sell-on fee).
- Elo prior from FPL-Core-Insights; recent per-gameweek minutes from
  `event/{gw}/live`; injury-return ramp; doubtful-flag recovery; regression to
  usual role; loan blocks from `scout_risks`.
- Solver alternatives via no-good cuts; 0.5% optimality gap.
- Fixed: from-scratch solves spending free transfers, a free-transfer replay
  off-by-one, inflated Rate My Team grades.

## 2026-09-20 — First version (`c55ac5c`)

- Local FPL planner: FastAPI backend over the FPL API with disk cache and
  offline mode.
- xPts engine, multi-gameweek MIP solver, chip strategies, Rate My Team,
  Compare, Minileagues, Scout, rules-based Copilot.
- Vanilla-JS single-page app.
