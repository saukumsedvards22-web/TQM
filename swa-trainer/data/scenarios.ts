export interface Scenario {
  id: string;
  title: string;
  setup: string;
  situation: string;
  options: {
    label: string;
    outcome: 'best' | 'okay' | 'bad';
    explanation: string;
  }[];
  keyLesson: string;
}

export const scenarios: Scenario[] = [
  {
    id: 's1',
    title: 'The Angry Door Slam',
    setup: 'You\'ve knocked on 20 doors with no demos. It\'s 4pm and hot outside.',
    situation:
      'You ring the bell. A man opens the door, sighs loudly, and says "Look, I\'ve had three of you guys come to my door this week. I\'m not interested and I never will be. Please stop sending people here." He starts to close the door.',
    options: [
      {
        label:
          'Apologize sincerely: "I\'m so sorry for that — I completely understand. I won\'t take more of your time. Thank you." Then leave with a smile.',
        outcome: 'best',
        explanation:
          'This is the right call. When someone has been over-canvassed and is genuinely frustrated, a graceful, respectful exit preserves your dignity, the company\'s reputation, and sometimes even earns a second look. Pushing back would only confirm his frustration.',
      },
      {
        label:
          '"I get it — but I\'m different from those other reps. Just give me 2 minutes and I promise it\'ll be worth it."',
        outcome: 'bad',
        explanation:
          '"I\'m different" is exactly what every pushy rep says. This dismisses his feelings and escalates his frustration. You\'re now an obstacle to his peace, not a helpful visitor.',
      },
      {
        label: 'Ask him if you can come back another day when he\'s in a better mood.',
        outcome: 'bad',
        explanation:
          'Suggesting his mood is the problem is condescending and will likely make things worse. He\'s not in a bad mood — he\'s been over-solicited and has a legitimate reason to be firm.',
      },
      {
        label: 'Give him a flyer for his neighbors and ask if any of them have kids.',
        outcome: 'okay',
        explanation:
          'Creative, but probably not the right moment. When someone is closing the door on you, trying to extract value from the interaction can feel disrespectful. Exit first, then maybe leave a card.',
      },
    ],
    keyLesson:
      'A graceful exit is not a defeat — it\'s professional. Some doors are not your customers. Respect the no, protect your energy, and move to the next door.',
  },
  {
    id: 's2',
    title: 'The Genuinely Interested Parent',
    setup: 'You\'re mid-demo with a mom who loves what she sees.',
    situation:
      'Sarah has been engaged the whole demo — asking questions, nodding, calling her daughter over. She says: "I really like this. I just want to check the price online to make sure it\'s fair before I commit. Can you write down the product name and price for me?"',
    options: [
      {
        label:
          '"Absolutely, Sarah — I want you to feel great about this. Let me write that down. And just so you know, the pricing I\'m offering is our direct-to-family price which isn\'t always available online."',
        outcome: 'best',
        explanation:
          'You\'re not blocking her research — you\'re validating her instinct while gently planting a relevant truth. Giving her the info builds trust. Adding context about pricing keeps you relevant.',
      },
      {
        label: '"I\'d prefer you didn\'t look it up — the online prices can be confusing."',
        outcome: 'bad',
        explanation:
          'This immediately kills trust. You\'re now hiding something, and she knows it. Even if it\'s not true, it sounds like you\'re afraid of transparency.',
      },
      {
        label:
          '"Of course! And while you\'re looking, would you mind if I showed Emma one more section? I think she\'ll love it."',
        outcome: 'best',
        explanation:
          'Smart move — you\'re keeping the daughter engaged (which keeps the emotional connection alive) while showing you\'re completely comfortable with the research. Confidence signals honesty.',
      },
      {
        label: 'Tell her the sale is today only and the price goes up tomorrow.',
        outcome: 'bad',
        explanation:
          'If this isn\'t true, it\'s a lie — and she may find out. False urgency destroys trust and can cost you referrals and future business. Only use urgency that is 100% real.',
      },
    ],
    keyLesson:
      'Transparency builds trust. A customer who feels respected and not pressured is far more likely to buy — and to refer their neighbors. Confidence in your product means you\'re not afraid of comparison.',
  },
  {
    id: 's3',
    title: 'The "We Already Have Encyclopedias"',
    setup: 'You\'re at the door with a retired couple.',
    situation:
      'A grandfather answers the door and listens politely. When you mention educational books, he says: "We already have two sets of encyclopedias from the 80s. The grandkids can use those when they visit."',
    options: [
      {
        label:
          '"Oh, encyclopedias are great for general knowledge! Our materials work differently though — they\'re designed specifically around today\'s school curriculum, the way teachers are actually testing kids right now. Can I show you the difference?"',
        outcome: 'best',
        explanation:
          'You validated what he has (don\'t make him feel foolish) and pivoted to a clear differentiation: curriculum alignment. Old encyclopedias can\'t cover Common Core, modern science standards, or the specific format of today\'s tests.',
      },
      {
        label: '"Encyclopedias are pretty outdated — the internet has replaced them, honestly."',
        outcome: 'bad',
        explanation:
          'You just insulted something he owns and values. Even if it\'s true, this puts him on the defensive. Dismissing his existing resources makes you an adversary, not an advisor.',
      },
      {
        label:
          '"Do your grandkids come over often? How old are they, and what grades are they in?"',
        outcome: 'okay',
        explanation:
          'Pivoting to FORD is a reasonable move — gather more info before countering. But without addressing the encyclopedias objection, he may feel you dodged his point. Better to acknowledge it first.',
      },
      {
        label: 'Thank him for his time and move on — this isn\'t a good prospect.',
        outcome: 'bad',
        explanation:
          'This is giving up too early. Many grandparents are the decision-makers for grandchildren\'s educational gifts and are often willing to invest. The encyclopedias objection is very handleable.',
      },
    ],
    keyLesson:
      'Never dismiss what the customer already has — validate it, then differentiate. The goal is to be additive, not replacement-focused.',
  },
  {
    id: 's4',
    title: 'The "Let Me Think About It" Stall',
    setup: 'You\'ve done a full 30-minute demo. The mom is interested but not committing.',
    situation:
      'Maria has been engaged the whole time. She picks up the book again, flips through it one more time, and says: "I really do like it. I just want to think about it. Can you come back next week?"',
    options: [
      {
        label:
          '"Of course — I appreciate that. Can I ask, what specifically would you want to think about? Is it the investment, the timing, or something else? I want to make sure I answer any questions before I go."',
        outcome: 'best',
        explanation:
          '"Think about it" is almost never about thinking — it\'s usually a specific concern she hasn\'t voiced yet. Asking what specifically she needs to think about surfaces the real objection and gives you a chance to handle it now.',
      },
      {
        label: '"Sure! I\'ll be back Tuesday." [Leave]',
        outcome: 'bad',
        explanation:
          'Statistically, "let me think about it" almost never converts to a sale a week later. Leaving without uncovering the real objection means that concern sits and grows. Come Tuesday, she\'ll have talked herself out of it.',
      },
      {
        label:
          '"I totally understand. You know what — let me set up the order now and if you decide it\'s not right in the next 24 hours, just call me and I\'ll cancel it. That way if you decide yes, the books ship Monday."',
        outcome: 'okay',
        explanation:
          'The "tentative order" technique works with strong buying signals, but use it carefully. It only works if she truly seems interested and not just being polite. If used on someone who was going to say no anyway, it comes off as pushy.',
      },
      {
        label:
          '"I understand — the reason most people want to think about it is the investment. Let me break down the monthly payment one more time."',
        outcome: 'okay',
        explanation:
          'You\'re assuming the objection is money, which may not be true. It could be that she needs to talk to her spouse, or she\'s not convinced about the specific value for her child. Asking first is always better than assuming.',
      },
    ],
    keyLesson:
      'Surface the real objection behind the stall. "What specifically would you want to think about?" is one of the highest-value questions in your arsenal.',
  },
  {
    id: 's5',
    title: 'The Rainy Day Slump',
    setup: 'It\'s raining. Your team leader is out sick. You\'ve had 0 demos by 5pm.',
    situation:
      'You\'re in your car, soaked, with your books on the seat. The last 4 doors either didn\'t answer or said no immediately. You text your team leader for advice and get no response. You\'re thinking about calling it early.',
    options: [
      {
        label:
          'Call it — you\'ll make it up tomorrow when the weather is better and energy is higher.',
        outcome: 'bad',
        explanation:
          'This is the exact moment that separates top performers from average ones. Quitting in hard conditions becomes a habit. "I\'ll make it up" rarely happens — tomorrow has its own challenges. Rain is the same for everyone on the street.',
      },
      {
        label:
          'Give yourself a 10-minute reset: dry off, read your WHY statement, set a target of 3 more demos, then go back out.',
        outcome: 'best',
        explanation:
          'This is the W.I.T. response. You\'re not ignoring the difficulty — you\'re resetting intentionally. A defined small goal (3 demos) is manageable. Many of the best sales happen on hard days because fewer reps are out there.',
      },
      {
        label:
          'Knock on doors more aggressively to make up for lost time — go faster and push harder.',
        outcome: 'bad',
        explanation:
          'Desperation and rushed energy are immediately readable to homeowners. Going faster and pushing harder when you\'re already in a negative headspace usually produces worse results. Quality and presence beat speed.',
      },
      {
        label:
          'Call a teammate, get some energy back, then go back out with a renewed mindset.',
        outcome: 'okay',
        explanation:
          'Connecting with a teammate can help — but only if it genuinely resets your attitude, not if it turns into a venting session. If a 5-minute call gets you energized and back on the street, it\'s worth it.',
      },
    ],
    keyLesson:
      'Hard days are character builders. The reps who push through bad conditions are the ones who end the summer with stories worth telling — and skills worth keeping.',
  },
  {
    id: 's6',
    title: 'The Referral Opportunity',
    setup: 'You just closed a sale with a happy family.',
    situation:
      'Jennifer just bought the complete study set and is clearly excited about it. She says "My kids are going to love this!" You\'re about to pack up and leave.',
    options: [
      {
        label: 'Say thank you, give her a receipt, and head to the next house.',
        outcome: 'bad',
        explanation:
          'You just left the most valuable moment of your day on the table. A happy customer right after a purchase is the best time to ask for referrals. They\'re emotionally high and want to share the good news.',
      },
      {
        label:
          '"Jennifer, I\'m so glad! Can I ask — do you have any neighbors or friends who you think would love something like this for their kids? Anyone come to mind?"',
        outcome: 'best',
        explanation:
          'This is the referral ask in its most natural form. Warm referrals close at a dramatically higher rate than cold doors. One referral from a happy buyer can be worth 3 cold hours of door knocking.',
      },
      {
        label:
          '"Would you be willing to leave a Google review for us? It really helps."',
        outcome: 'okay',
        explanation:
          'Reviews are valuable, but a warm referral name is more immediately actionable. Lead with the referral ask, then mention reviews as a secondary if she\'s willing.',
      },
      {
        label:
          '"Jennifer, thank you so much. By the way, who are your 3 closest neighbors? I\'d love to introduce myself."',
        outcome: 'best',
        explanation:
          'Asking for specific neighbors by name or address (rather than vague "anyone you know?") produces better referrals. She\'s also more likely to give a name if she feels you\'ll represent her well, which you already have.',
      },
    ],
    keyLesson:
      'Every closed sale is also a referral opportunity. Happy customers are your best source of warm leads. Always ask — the worst they can say is they don\'t know anyone.',
  },
];
