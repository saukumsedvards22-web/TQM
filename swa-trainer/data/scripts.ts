export interface SalesScript {
  id: string;
  title: string;
  category: 'approach' | 'presentation' | 'objection' | 'close' | 'attitude';
  content: string;
  tips: string[];
  keyWords?: string[];
}

export const salesScripts: SalesScript[] = [
  {
    id: 'door-approach',
    title: 'The Door Approach',
    category: 'approach',
    content: `"Hi! My name is [Your Name], and I'm a college student working my way through school this summer. I'm not here to sell you anything today — I'm just letting families in the area know about some educational resources that a lot of parents have found really helpful for their kids.

Do you have any children at home?"

[If yes]: "Great! How old are they? What grade are they going into?"

[If no]: "No problem at all — do you have any nieces, nephews, or grandchildren you're close to?"`,
    tips: [
      'Smile BIG before the door opens — they can hear it in your voice',
      'Stand slightly to the side, not directly in front of the peephole',
      'Be energetic but not pushy — you\'re excited to meet them',
      '"Not here to sell anything today" lowers defenses immediately',
      'Use their name as soon as you learn it',
    ],
    keyWords: ['energetic', 'friendly', 'confident', 'non-threatening'],
  },
  {
    id: 'ford-rapport',
    title: 'FORD Rapport Building',
    category: 'presentation',
    content: `FORD stands for Family, Occupation, Recreation, Dreams.

FAMILY:
"Tell me about your kids — what are their names? What are they into right now?"
"How long have you been in the neighborhood?"
"Where do they go to school?"

OCCUPATION:
"What do you do for work?"
"Do you work close by or do you commute?"

RECREATION:
"What do your kids like to do for fun in the summer?"
"Does your family do anything together on weekends?"

DREAMS:
"Where do you see [child's name] in 10 years?"
"What's important to you about their education?"
"Do they have any subjects they really love — or struggle with?"`,
    tips: [
      'Never skip rapport — it\'s the foundation of the sale',
      'Listen 80%, talk 20% during FORD',
      'Take mental notes — reference what they say later in the demo',
      'Genuine curiosity beats scripted questions every time',
      'The DREAMS questions reveal the emotional "why" that closes the sale',
    ],
    keyWords: ['listen', 'connect', 'genuine', 'curious'],
  },
  {
    id: 'five-step-presentation',
    title: 'The 5-Step Presentation',
    category: 'presentation',
    content: `STEP 1 — Introduction & Rapport (FORD)
Get invited in, build connection, learn about the family and their kids.

STEP 2 — Need Creation
"[Child's name], what subject do you find hardest at school?"
"How much time does [he/she] spend on homework each night?"
"Have you noticed that textbooks don't always explain things in a way that clicks?"

Tie their answers to the product: "That's exactly where our study system helps..."

STEP 3 — Product Demonstration
Show the books hands-on. Let them touch them.
"Open to any page — see how it breaks concepts down step by step?"
"This is the exact format that helped [child's name]'s grade level last year."

STEP 4 — Investment Conversation
"Most families in the area have invested right around $X."
Pause. Let silence work. Never fill the silence after stating the price.

STEP 5 — The Close
"Based on everything you've shared about [child's name], which set feels like the best fit for your family — the complete reference set, or the homework helper bundle?"`,
    tips: [
      'Never skip steps — each step prepares for the next',
      'Use the child\'s name throughout the entire demo',
      'Involve the child in the demonstration when possible',
      'Price comes AFTER value is established, never before',
      'The assumptive close ("which set...") is more powerful than asking yes/no',
    ],
  },
  {
    id: 'feel-felt-found',
    title: 'Feel-Felt-Found (Universal Objection Handler)',
    category: 'objection',
    content: `The Feel-Felt-Found technique works for almost any objection.

FORMAT:
"I understand how you FEEL."
"A lot of our customers have FELT the same way."
"But what they've FOUND is..."

EXAMPLE — "It's too expensive":
"I totally understand how you feel — it is a real investment. Honestly, a lot of the parents I talk to have felt the same way at first. But what they've found is that when they broke it down to less than a dollar a day over the life of their kids' education, it felt like a no-brainer compared to tutoring costs."

EXAMPLE — "I need to think about it":
"That makes complete sense — I appreciate that you take decisions like this seriously. A lot of parents have felt the same way. But what most of them found is that the kids who got started right away saw results before school started again, and that's what made the decision worth it."`,
    tips: [
      'Never argue — validate their concern first, always',
      'The bridge is "what they\'ve FOUND" — this is where you re-close',
      'Use real social proof: "families in this neighborhood," "parents I spoke with yesterday"',
      'Lower your voice slightly when you say "I understand how you feel"',
      'After Feel-Felt-Found, always move back to a close — don\'t leave it hanging',
    ],
  },
  {
    id: 'objection-not-interested',
    title: '"I\'m Not Interested" — At the Door',
    category: 'objection',
    content: `This objection comes before they even know what you\'re offering. It\'s a reflex, not a real decision.

RESPONSE:
"That's totally fair — I wouldn't expect you to be interested in something you haven't seen yet! I'm not asking you to be interested in anything, I'm just sharing some information about what a lot of families in [neighborhood] have been using. It'll literally take 90 seconds. Do you have kids at home?"

IF THEY STILL RESIST:
"Look, I completely respect that. Can I just leave you our family info card? A lot of parents actually reach back out once they see what it's about."

[Leave the card, smile, say thank you, move on — never beg]`,
    tips: [
      'Do NOT match their closed energy — stay warm and open',
      'Reframe: "I wouldn\'t expect you to be interested in something you haven\'t heard"',
      'The 90-second promise reduces perceived risk dramatically',
      'If they say no twice, respect it and leave — your time has value',
      'A graceful exit often leads to a callback or referral',
    ],
  },
  {
    id: 'objection-spouse',
    title: '"I Need to Ask My Husband/Wife"',
    category: 'objection',
    content: `This is one of the most common stalls. The goal is to get both decision-makers present, or close with one.

RESPONSE A — Get the spouse involved:
"Absolutely — that makes total sense, big decisions are better made together. Is [he/she] home right now? I'd love to meet them and show both of you — it only takes a few minutes and you can decide together."

RESPONSE B — If spouse isn't home:
"I respect that completely. Let me ask you this — setting aside [your spouse] for a second, based on what you've seen, do YOU feel like this would be valuable for [child's name]?"

[If yes]: "Great — then let's set it up so that when [spouse] gets home, you can show them what you saw. I can put together the paperwork and you can make the final call together tonight."

RESPONSE C — Assumptive:
"Of course! I'll put the order together now so everything's ready. If [spouse] isn't on board, just give me a call and we'll cancel — no hard feelings. But if [he/she] agrees with you, the books will ship Monday."`,
    tips: [
      'Never badmouth or dismiss the absent spouse',
      'Always try to get both in the room first',
      'Response B isolates their personal conviction before looping in the spouse',
      'Response C works when you have strong buying signals — use with care',
      'Always leave your contact info and follow up the next day',
    ],
  },
  {
    id: 'objection-cant-afford',
    title: '"We Can\'t Afford It"',
    category: 'objection',
    content: `Money objections are almost always about perceived value, not actual budget.

RESPONSE:
"I hear you — and I want to be respectful of that. Can I ask — is it that the timing isn't right, or is it that you're not sure it's worth the investment?"

[If timing]: "That makes sense. We do have a payment plan — most families do around $[X]/month, which works out to less than a cup of coffee a day. Would that make it more manageable?"

[If value]: "Okay, fair. What would make it feel worth it to you?"
[Listen, then reconnect to what they shared during FORD — the child's struggles, their dreams for the future]

NEVER say: "It's not that expensive" — you've never seen their bank account.`,
    tips: [
      'Separate timing from value — they\'re very different objections',
      'Break the price down to a daily cost — $X/year sounds big, $0.50/day sounds tiny',
      'Reference payment plans early if you sense budget sensitivity',
      'Connect back to the emotional WHY from the FORD conversation',
      'Never judge their financial situation — stay completely neutral and empathetic',
    ],
  },
  {
    id: 'close-assumptive',
    title: 'The Assumptive Close',
    category: 'close',
    content: `The assumptive close works by moving forward as if the sale is already made.

BASIC VERSION:
"Based on everything you shared about [child's name] and their grades in [subject], it sounds like the Complete Study System is the best fit. Let me grab your information."

ORDER OF WORDS MATTERS:
Instead of: "So... do you want to go ahead?"
Say: "Alright, let's get [child's name] set up. What's the best address for delivery?"

CHOICE CLOSE:
"Would you want the full reference set, or start with the homework helper package?"
[Either answer = a sale]

URGENCY CLOSE (use sparingly, only if true):
"I'm finishing up in this area on Friday — families who order before then get the current pricing. Want to lock that in today?"`,
    tips: [
      'Confidence in your close signals confidence in the product',
      'Move to paperwork naturally — don\'t ask permission to start writing',
      'Silence after the close is golden — let them break it',
      'If they hesitate, ask "What would make you feel good about this decision?"',
      'Never close more than 3 times on the same objection — respect the no',
    ],
  },
  {
    id: 'daily-attitude',
    title: 'Daily Attitude & Mindset Reset',
    category: 'attitude',
    content: `THE W.I.T. MINDSET — Whatever It Takes

Morning Affirmations (say these out loud):
"I am excited. I am enthusiastic. I am on fire."
"Every door is an opportunity. Every no gets me closer to yes."
"I am providing real value to real families today."
"My attitude determines my altitude."

THE NUMBERS GAME:
Every "no" has value. If you close 1 in 10 demos, and each close earns $[X], then each no is worth $[X/10]. Thank every no.

RESET BETWEEN DOORS:
Walk to the next door with your chin up, shoulders back, big smile.
Take one deep breath before you ring the bell.
The family behind that door has never met you. You get a fresh start every time.

THE LONG GAME:
"This summer is building skills I'll use my entire life."
"The reps I put in today are paying dividends for 40 years."
"Not everyone makes it through — I'm building character right now."`,
    tips: [
      'Attitude is the #1 predictor of success — protect it fiercely',
      'Never vent about a bad call to other reps before the day is done',
      'Read 10 minutes of motivational content every morning',
      'Track your numbers daily — progress is motivating',
      'Find a WHY that\'s bigger than the discomfort of rejection',
    ],
  },
];

export const scriptCategories = [
  { id: 'approach', label: 'Door Approach', color: 'bg-blue-100 text-blue-800' },
  { id: 'presentation', label: 'Presentation', color: 'bg-purple-100 text-purple-800' },
  { id: 'objection', label: 'Objection Handling', color: 'bg-red-100 text-red-800' },
  { id: 'close', label: 'Closing', color: 'bg-green-100 text-green-800' },
  { id: 'attitude', label: 'Mindset & Attitude', color: 'bg-yellow-100 text-yellow-800' },
] as const;
