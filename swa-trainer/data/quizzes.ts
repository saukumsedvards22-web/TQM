export interface QuizQuestion {
  id: string;
  category: string;
  question: string;
  options: string[];
  correctIndex: number;
  explanation: string;
}

export const quizQuestions: QuizQuestion[] = [
  // Sales Process
  {
    id: 'q1',
    category: 'Sales Process',
    question: 'What does FORD stand for in the rapport-building stage?',
    options: [
      'Family, Occupation, Recreation, Dreams',
      'Friends, Occupation, Revenue, Details',
      'Focus, Organize, Relate, Deliver',
      'Family, Office, Resources, Development',
    ],
    correctIndex: 0,
    explanation:
      'FORD is the foundation of rapport: Family (kids, home life), Occupation (their work), Recreation (hobbies), Dreams (goals for their kids). These four topics help you connect genuinely before any selling happens.',
  },
  {
    id: 'q2',
    category: 'Sales Process',
    question: 'In the 5-step presentation, when do you discuss price?',
    options: [
      'Right after the door approach, so they know upfront',
      'In Step 2, during need creation',
      'In Step 4, only after demonstrating value in Step 3',
      'Only if they ask about it first',
    ],
    correctIndex: 2,
    explanation:
      'Price always comes AFTER the product demonstration (Step 3). Price before value creates immediate resistance. Once they\'ve seen the books and connected emotionally to their child\'s future, the price is much easier to justify.',
  },
  {
    id: 'q3',
    category: 'Sales Process',
    question: 'Which close technique presents two options, both of which result in a sale?',
    options: [
      'The Assumptive Close',
      'The Choice Close',
      'The Urgency Close',
      'The Feel-Felt-Found Close',
    ],
    correctIndex: 1,
    explanation:
      'The Choice Close gives two buying options: "Would you prefer the complete reference set or the homework helper bundle?" Either answer moves the sale forward. It shifts the mental question from "Should I buy?" to "Which one should I get?"',
  },
  {
    id: 'q4',
    category: 'Sales Process',
    question: 'A homeowner says "I\'m not interested" before you explain anything. What\'s the best first response?',
    options: [
      '"Okay, sorry to bother you!" and leave immediately',
      '"That\'s totally fair — I wouldn\'t expect you to be interested in something you haven\'t heard yet!"',
      '"But this product is amazing, let me show you!"',
      '"Are you sure? This is a limited-time offer."',
    ],
    correctIndex: 1,
    explanation:
      '"Not interested" at the door is a reflex, not a real decision. Reframing with "I wouldn\'t expect you to be interested in something you haven\'t heard yet" is non-confrontational and plants curiosity without being pushy.',
  },
  {
    id: 'q5',
    category: 'Sales Process',
    question: 'After stating the price, what is the most powerful thing you can do?',
    options: [
      'Immediately offer a discount',
      'List all the features again to reinforce value',
      'Say nothing — let the silence work',
      'Ask "So what do you think?"',
    ],
    correctIndex: 2,
    explanation:
      'Silence after the price is one of the most powerful sales tools. The first person to speak after the price is stated typically loses. Give them space to process. Filling the silence signals nervousness and undermines your own close.',
  },

  // Objection Handling
  {
    id: 'q6',
    category: 'Objection Handling',
    question: 'A customer says "I need to talk to my spouse." What\'s the best immediate next step?',
    options: [
      'Say "No problem!" and leave your card',
      'Ask if the spouse is home right now so they can both decide together',
      'Tell them the price will go up if they wait',
      'Ask them to sign now and cancel if the spouse disagrees',
    ],
    correctIndex: 1,
    explanation:
      'Always try to get both decision-makers in the room first. "Is your husband/wife home? I\'d love to show both of you — big decisions are better made together." If the spouse is present, the objection disappears.',
  },
  {
    id: 'q7',
    category: 'Objection Handling',
    question: 'In the Feel-Felt-Found technique, what comes after "I understand how you feel"?',
    options: [
      '"But let me explain why you\'re wrong..."',
      '"A lot of our customers have felt the same way."',
      '"Most people don\'t realize the value until they try it."',
      '"Have you considered financing?"',
    ],
    correctIndex: 1,
    explanation:
      'Feel-Felt-Found: "I understand how you FEEL. A lot of our customers have FELT the same way. But what they\'ve FOUND is..." The middle step (Felt) uses social proof to normalize the concern before redirecting.',
  },
  {
    id: 'q8',
    category: 'Objection Handling',
    question: 'A parent says "We can\'t afford it." Before jumping to the payment plan, what should you do first?',
    options: [
      'Immediately offer a discount',
      'Ask whether it\'s a timing issue or a value issue',
      'Lower the price',
      'Tell them many families find a way to make it work',
    ],
    correctIndex: 1,
    explanation:
      '"Can\'t afford it" could mean timing (cash flow right now) or value (not convinced it\'s worth it). These need different responses. Ask: "Is it that the timing isn\'t right, or that you\'re not sure it\'s worth the investment?" Then respond to the real objection.',
  },
  {
    id: 'q9',
    category: 'Objection Handling',
    question: 'How many times should you attempt to close after the same objection comes up repeatedly?',
    options: [
      'As many times as it takes — persistence always wins',
      'Once — if they say no, respect it',
      'No more than 3 times',
      'Twice — third time, offer a big discount',
    ],
    correctIndex: 2,
    explanation:
      'Three is the rule. After three genuine closes on the same objection, continuing becomes pressure — and pressure destroys trust and referrals. A graceful, respectful exit preserves the relationship and often leads to callbacks or referrals.',
  },
  {
    id: 'q10',
    category: 'Objection Handling',
    question: '"Just leave me a brochure and I\'ll look it over." This is an example of what type of objection?',
    options: [
      'A genuine money concern',
      'A stall / delay tactic',
      'A product quality concern',
      'A spouse objection',
    ],
    correctIndex: 1,
    explanation:
      '"Leave a brochure" is almost always a polite stall. Brochures rarely close sales on their own. Respond with: "I\'d love to — and honestly, most families find they have questions once they see it. Could I walk you through the highlights right now? It\'ll take about 5 minutes."',
  },

  // Attitude & Habits
  {
    id: 'q11',
    category: 'Mindset & Attitude',
    question: 'What does W.I.T. stand for in the SWA mindset?',
    options: [
      'Work In Teams',
      'Whatever It Takes',
      'Win, Inspire, Transform',
      'Work, Improve, Thrive',
    ],
    correctIndex: 1,
    explanation:
      'W.I.T. — Whatever It Takes — is the core mindset. It means you don\'t make excuses about weather, mood, the neighborhood, or your last call. You show up fully and do what\'s required, every single day.',
  },
  {
    id: 'q12',
    category: 'Mindset & Attitude',
    question: 'If you close 1 in every 10 demos and each sale earns you $200, what is each "no" actually worth?',
    options: ['$0 — it\'s just a rejection', '$20', '$50', '$200'],
    correctIndex: 1,
    explanation:
      'Each no is worth $20. If every 10 nos leads to 1 yes worth $200, then each no is literally $200 ÷ 10 = $20 in expected value. This reframe turns rejection from discouraging into motivating — every no is a step toward the next yes.',
  },
  {
    id: 'q13',
    category: 'Mindset & Attitude',
    question: 'You had 3 terrible calls in a row. What should you do before ringing the next doorbell?',
    options: [
      'Call your manager to vent and get advice',
      'Take a long break to reset mentally',
      'Walk to the door with chin up, take a deep breath, and smile — it\'s a fresh start',
      'Review your scripts to figure out what went wrong',
    ],
    correctIndex: 2,
    explanation:
      'Each door is a clean slate. The family behind it has never met you and knows nothing about your last 3 calls. Reset physically — posture, breath, smile — before every door. Bad energy from the last call will kill the next one.',
  },
  {
    id: 'q14',
    category: 'Mindset & Attitude',
    question: 'What is the recommended first thing to do every morning as a SWA rep?',
    options: [
      'Check your phone and catch up on social media',
      'Map out the best neighborhoods for the day',
      'Read motivational content and set a clear goal for the day',
      'Call your top prospect from yesterday',
    ],
    correctIndex: 2,
    explanation:
      'Morning habits set the tone for the entire day. 10 minutes of motivational reading + clearly defined daily goals (# of demos, # of doors) creates intentionality. Reps who drift into the day perform dramatically worse than those who attack it with purpose.',
  },

  // Product Knowledge
  {
    id: 'q15',
    category: 'Product Knowledge',
    question: 'SouthWestern Advantage is primarily known for selling what type of product?',
    options: [
      'Online tutoring subscriptions',
      'Educational books and study tools for K-12 students',
      'College prep and SAT courses',
      'Teacher training materials',
    ],
    correctIndex: 1,
    explanation:
      'SWA\'s flagship products are physical educational books — reference sets, homework helpers, and study skills guides designed for K-12 students. The value proposition is that they provide clear explanations and structured support that textbooks often don\'t.',
  },
  {
    id: 'q16',
    category: 'Product Knowledge',
    question: 'When demonstrating the product, what should you do to maximize engagement?',
    options: [
      'Keep the books in your bag and describe them verbally',
      'Hand the books to the parent and child — let them touch and flip through',
      'Read from the books yourself to show the quality',
      'Show photos of the books on your phone',
    ],
    correctIndex: 1,
    explanation:
      'Physical engagement is critical. When they hold the books, flip the pages, and point to sections relevant to their child\'s struggles, ownership begins before the sale is made. "You can feel the quality" is more powerful than any description.',
  },
  {
    id: 'q17',
    category: 'Product Knowledge',
    question: 'How should you best connect the product to the customer\'s specific child?',
    options: [
      'Use generic statements about how all kids benefit',
      'Reference the specific subjects and struggles the child mentioned during FORD',
      'Show testimonials from other families',
      'Emphasize the discount they\'re getting today',
    ],
    correctIndex: 1,
    explanation:
      'Personalization is the key to closing. "You mentioned Emma struggles with fractions — look at how this breaks it down step by step, exactly the way a teacher would explain it." The more specific you are to their child, the more real the value feels.',
  },
];

export const quizCategories = [
  'Sales Process',
  'Objection Handling',
  'Mindset & Attitude',
  'Product Knowledge',
];
