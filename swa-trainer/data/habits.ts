export interface Habit {
  id: string;
  time: 'morning' | 'selling' | 'evening';
  title: string;
  description: string;
  why: string;
}

export const habits: Habit[] = [
  // Morning habits
  {
    id: 'h1',
    time: 'morning',
    title: 'Wake up by 6:30 AM',
    description: 'Start the day before the chaos starts.',
    why: 'Top earners are up before the competition. Morning silence is your prep time.',
  },
  {
    id: 'h2',
    time: 'morning',
    title: 'Read 10 min of motivational content',
    description: 'Book, podcast, or affirmation — fill the tank before you leave the house.',
    why: 'You can\'t pour from an empty cup. Attitude is the #1 performance variable.',
  },
  {
    id: 'h3',
    time: 'morning',
    title: 'Set 3 clear daily goals',
    description: 'Write down: # of doors, # of demos, and 1 skill to focus on today.',
    why: 'What gets measured gets done. Vague intentions produce vague results.',
  },
  {
    id: 'h4',
    time: 'morning',
    title: 'Say your affirmations out loud',
    description: '"I am excited. I am enthusiastic. I am on fire."',
    why: 'Verbal affirmations activate the brain differently than silent ones. Say it like you mean it.',
  },
  {
    id: 'h5',
    time: 'morning',
    title: 'Attend morning team meeting',
    description: 'Be on time, engaged, and contribute something positive.',
    why: 'Team energy is contagious. What you put into the meeting, the team puts back into you.',
  },
  {
    id: 'h6',
    time: 'morning',
    title: 'Role-play one objection script',
    description: 'Practice one objection handle with a teammate or in the mirror.',
    why: 'Reps who practice daily outperform reps who wing it. Your scripts should be muscle memory.',
  },

  // Selling habits
  {
    id: 'h7',
    time: 'selling',
    title: 'Reset attitude at every door',
    description: 'Chin up, shoulders back, genuine smile — fresh start every time.',
    why: 'Each homeowner gets the real you, not the tired version left over from the last call.',
  },
  {
    id: 'h8',
    time: 'selling',
    title: 'Use the customer\'s name 3x in every demo',
    description: 'Learn their name within 30 seconds. Use it often.',
    why: 'People light up when they hear their own name. It signals presence and respect.',
  },
  {
    id: 'h9',
    time: 'selling',
    title: 'Ask for referrals after every closed sale',
    description: '"Do you have any neighbors or friends who might love this for their kids?"',
    why: 'Warm referrals close at 3-5x the rate of cold doors. Every sale is also a referral opportunity.',
  },
  {
    id: 'h10',
    time: 'selling',
    title: 'Track every interaction',
    description: 'Note doors knocked, demos run, and outcomes in your tracker.',
    why: 'Your numbers tell you where your gaps are. Tracking removes guesswork from improvement.',
  },
  {
    id: 'h11',
    time: 'selling',
    title: 'Get inside the house for every demo',
    description: 'Door demos close at a fraction of in-home demos. Always ask to come in.',
    why: 'Once you\'re in their space, engagement and close rate both skyrocket.',
  },
  {
    id: 'h12',
    time: 'selling',
    title: 'Never skip lunch',
    description: 'Eat a real meal, even on a hot streak.',
    why: 'Low blood sugar kills rapport and decision-making. Your body is your tool — maintain it.',
  },

  // Evening habits
  {
    id: 'h13',
    time: 'evening',
    title: 'Attend evening debrief meeting',
    description: 'Share one win and one thing you\'re working on.',
    why: 'Accountability + shared learning accelerates your growth faster than solo reflection.',
  },
  {
    id: 'h14',
    time: 'evening',
    title: 'Review your numbers for the day',
    description: 'Doors, demos, closes, income. Compare to your goal.',
    why: 'Review creates awareness. Awareness creates intention. Intention creates results.',
  },
  {
    id: 'h15',
    time: 'evening',
    title: 'Write down 3 things that went well',
    description: 'Find the wins even in a bad day.',
    why: 'Your brain remembers what you rehearse. Rehearsing wins trains you to replicate them.',
  },
  {
    id: 'h16',
    time: 'evening',
    title: 'Identify one thing to improve tomorrow',
    description: 'One specific skill, not a vague "do better."',
    why: 'Small, targeted improvements compound. 1% better every day is 37x better over a year.',
  },
  {
    id: 'h17',
    time: 'evening',
    title: 'Get 7-8 hours of sleep',
    description: 'Protect your sleep like a professional athlete protects their body.',
    why: 'Sleep deprivation tanks emotional regulation — which tanks your ability to connect at the door.',
  },
];

export const motivationalQuotes = [
  {
    quote: 'The harder I work, the luckier I get.',
    author: 'Samuel Goldwyn',
  },
  {
    quote: 'Don\'t wish it were easier. Wish you were better.',
    author: 'Jim Rohn',
  },
  {
    quote: 'Success is the sum of small efforts, repeated day in and day out.',
    author: 'Robert Collier',
  },
  {
    quote: 'Every no gets me one step closer to yes.',
    author: 'SWA Field Wisdom',
  },
  {
    quote: 'Do it scared. Do it tired. Do it anyway.',
    author: 'Field Proverb',
  },
  {
    quote: 'Your attitude determines your altitude.',
    author: 'Zig Ziglar',
  },
  {
    quote: 'The sale is made or lost at the door — before you ever open your mouth.',
    author: 'SWA Field Wisdom',
  },
  {
    quote: 'You miss 100% of the shots you don\'t take.',
    author: 'Wayne Gretzky',
  },
];
