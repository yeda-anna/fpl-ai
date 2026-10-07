/* Mug’s Game FC — the roast room. Plain JS, no build step.

   House style: deadpan roast comedy. Short setup, flat delivery, a punchline that
   lands on the manager's own decisions. Chess blunders, cricket, engineering-
   college and Indian-household references are fair game. Every line is original.

   The rules (see CLAUDE.md):
   - Aim at the manager's own luck, rank and choices. Never at a religion, caste,
     region, community, body, family tragedy or any real person.
   - A roast is a separate aside under a suggestion. It never replaces, rewords
     or sits inside the advice, the numbers or an error.
   - Lines name players with {c1}, {out} … slots; app.js escapes them on output.
   Keep each line under ~120 characters so it reads on a phone. */
const ROAST = {
  loading: [
    'Sharma ji’s son finished this ages ago. Beta, take your time.',
    'Hope is a free transfer. You’ll roll it over and never use it.',
    'Optimising your squad. Papa gave up optimising you years ago.',
    'Loading like a Bengaluru commute: moving, but not going anywhere.',
    'Log kya kahenge? Your overall rank already did.',
    'Chai is brewing. Your rank is not.',
    'Unlike your relatives, the maths will not ask when you’re settling down.',
    'Jugaad is not a transfer strategy. We checked.',
    'Every captain pick is an act of faith. We’re here for the postmortem.',
    'Still faster than reading the 47 ‘Good Morning’ forwards in the family group.',
    'Like a Mumbai local at peak hour: crowded, late, and somehow you’re still in it.',
    '“Tumse na ho payega,” said everyone. We’re running the numbers anyway.',
    'Somewhere a chess engine is crying. It has seen your team.',
    'Thinking harder than you did before captaining a defender.',
    'Hold on. The server needs a moment to process the audacity.',
    'Running the numbers. Unlike your gut, they showed up to work.',
    'Use this time to reflect on that Bench Boost.'
  ],
  welcome: [
    'Your captain will blank. Your relatives will still ask what happened.',
    'Rank in the millions? Don’t worry, beta. It’s a stable, pensionable position.',
    'Everyone says “tumse na ho payega”. The model says: let’s see the expected points.',
    'Be like Sharma ji’s son: roll the transfer, ignore the group chat.',
    'Fantasy football: an EMI of hope, repaid in heartbreak, with interest.',
    'Your parents wanted a doctor or an engineer. Instead you’re agonising over a £5.5m defender.',
    'Welcome back. The model missed you. Your rank didn’t.',
    'Another week, another chance to hang a queen for a pawn.',
    'This app does the maths. You supply the confidence. We both know which one is short.'
  ],
  mood: {
    great: [
      'Well above average. Enjoy it. The “it was skill” phase lasts exactly one gameweek.',
      'Beat the average by a mile. Screenshot it now. Evidence disappears.',
      'For one week, Sharma ji’s son is taking notes from you. The captain blanks next week.',
      'Beating the average by that much? Relatives will call it luck. They’re right. Don’t tell them.'
    ],
    above: [
      'Above average. In an Indian household that means: “Good. But why not more?”',
      'Above average: enough to feel clever, not enough to stop checking the app at 2 AM.',
      'A little above average. The mini-league still won’t clap.',
      'Above average. Don’t get excited, the average is not a high bar. Look at who’s in it.'
    ],
    below: [
      'Below average. Beta, this is why we said engineering.',
      'Slightly below average. Think of it as character building, like every relative calls your last job.',
      'Below average. You had a plan, a captain and a dream. One of them did its job.',
      'Under the average. The average is made of people who forgot to set a team. Sit with that.'
    ],
    awful: [
      'That score deserves a moment of silence, then a Wildcard, then another moment of silence.',
      'Well below average. Even your bench looked embarrassed on your behalf.',
      'That wasn’t a gameweek, it was a blunder with a scoreboard.',
      'Far below average. At this point the free transfer is just a polite gesture.'
    ],
    none: [
      'No average yet. Enjoy the last few minutes of self-esteem.',
      'The average isn’t out. Neither is the verdict. Your hopes are, unfortunately, on show.'
    ]
  },
  captain: [
    '{c1} on top. Obvious, like opening 1.e4 and calling it a personality.',
    'Everyone will captain {c1}. If it goes wrong, at least you’ll fail in good company.',
    '{c1} first, {c2} second. The tragedy is you’ll pick the third one anyway.',
    '{c1} is the safe pick. Safe is how most rank-3-million stories begin.'
  ],
  differentials: [
    'Under 15% owned. Either genius or a very expensive way to be wrong alone.',
    'Differentials: for when you want to lose rank on your own terms.',
    'Pick one. Two, if you hate your mini-league more than you love your sleep.'
  ],
  value: [
    'The best value in the game. The only thing in your life offering returns.',
    'Cheap, cheerful and better than your last three transfers combined.'
  ],
  dream: [
    'The dream team. Unlike your real one, it has never met you.',
    'A perfect-hindsight XI. You’ll never own it, but it’s nice to look at, like a flat in Mumbai.'
  ],
  plan: {
    nothing: [
      'The plan is to do nothing. A bold strategy for someone who got here by doing things.',
      'Roll the transfer. The only move that has never lost you points on its own.'
    ],
    hits: [
      'This plan takes a hit. You’d pay anything not to sit with your own decisions.',
      'A hit: paying points for the feeling of control. Cheaper than a coach, less effective.'
    ],
    chip: [
      'A chip in the plan. Panic, but with a spreadsheet. The dignified kind.',
      'There’s a chip in this plan. Use it properly, unlike last time.'
    ],
    many: [
      'That’s not a plan, that’s a hostile takeover of your own squad.',
      'So many moves. Your squad isn’t being managed, it’s being renovated.'
    ],
    sensible: [
      'A sensible plan. You’ll abandon it by Friday for a hunch and a thumbnail.',
      'Sensible, boring, correct. Which is why you’ll ignore it.',
      'Calm, measured, mathematical. Three words nobody has ever used about your transfers.'
    ]
  },
  grade: {
    top: [
      'Top marks. Your parents will still ask about the ones you lost.',
      'A+ squad. Don’t let it go to your head. The head already plays too many mind games.'
    ],
    good: [
      'Respectable. “Fine” in the language of every relative you have.',
      'Good, not great. The cricket equivalent of getting out on 47.'
    ],
    mid: [
      'An average squad. Like average cricket: mostly rain delays and false hope.',
      'Mid. The squad version of “we’ll see”.'
    ],
    low: [
      'A D. Even the autocorrect on your transfers is embarrassed.',
      'This squad has the energy of a group project the night before submission.'
    ]
  },
  note: {
    flagged: 'Injured players in your XI. You’re not managing a team, you’re running a clinic.',
    dead: 'These players are on a paid holiday. You’re the sponsor.',
    gap: 'The gap between you and the best squad is basically your whole personality.',
    bench: 'A bench that thin isn’t a bench, it’s a bus stop.',
    premium: 'No premium players. Travelling economy and expecting business-class returns.',
    diffs: 'Everything you own, everyone owns. Originality isn’t dead, you just never met it.',
    templates: 'A very template squad. You’re not a manager, you’re a group-chat forward.',
    bank: 'Cash in the bank. Hoarding it like a fixed deposit while the squad goes hungry.',
    clean: 'No problems found. Suspicious. Go and look for the blunder you’ve hidden from yourself.'
  },
  upgrades: [
    'Selling {out} for {in}. {out} will be fine. You’ll be fine too, eventually.',
    '{out} to {in}: the transfer you already knew about and avoided, like a dentist.'
  ],
  chip: {
    wildcard: 'Wildcard: every manager’s way of saying “I have no idea what I’m doing, but with more players.”',
    freehit: 'Free Hit: a one-week fling. All the fun, none of the commitment.',
    bboost: 'Bench Boost: suddenly you care about the players you’ve ignored all season.',
    '3xc': 'Triple Captain: all hopes on one man, like every family and the cousin who “settled abroad”.',
    none: 'Every chip played. You’ve run out of things to blame.'
  },
  copilot: {
    captain: [
      'Captain advice from a model. Your gut will overrule it anyway, as it did last week.',
      'Captaincy: the one decision where you can be wrong in two directions.'
    ],
    hit: ['A hit is four points for a feeling. Make sure the feeling comes with a receipt.'],
    transfer: ['Every transfer is a confession that the last one didn’t work.'],
    rate: ['You asked for a rating. Brave. Most people ask for a miracle.'],
    chip: ['Chip timing. Because “whenever I panic” is not a strategy.'],
    differential: ['Punts: the football version of a life-changing business idea at 2 AM.'],
    bench: ['Your bench: the people you pay to watch.'],
    price: ['Prices rise when you’re not looking and fall when you are.'],
    overview: ['Ask better questions. Or at least more confident ones.']
  },
  compare: [
    '{w} wins. {l} will be told it was close.',
    'Choosing between {a} and {b} is the easy part. The rest of your season is the hard part.'
  ],
  scout: {
    prices: 'Prices change in the dead of night. So does your resolve.',
    setpieces: 'Set-piece takers: the only people in football who get a second chance, and still miss.',
    defcon: 'Defensive contribution: finally, a reward for doing a lot and being ignored. Relatable.',
    lineups: 'Predicted line-ups: guesses with a statistics degree. Their manager will do something else.'
  },
  league: [
    '{name} is the favourite. The rest of you are here for the group chat.',
    'Everyone owns {mo}. Imagine the chaos if he blanks. Please do.'
  ],
  xpts: [
    'Every player, projected. Your gut isn’t in here, and that’s the best news you’ll get today.',
    'Minutes are the whole game. Edit them yourself, then watch reality ignore you.'
  ],
  toggle: {
    on: ['Roast mode on. Brave.', 'Roast mode on. Your squad is now fair game.'],
    off: ['Roast mode off. Coward.', 'Roast mode off. The maths stays, the dignity is optional.']
  },
  tap: [
    'You tapped the logo. Productive use of a deadline day.',
    'Touch grass. Then touch your transfers.',
    'Mug’s Game FC: where hope goes to get a rank.',
    'Nothing here. Like your bench points.',
    'The logo does not have your Wildcard. Check the Chips tab.'
  ]
};
