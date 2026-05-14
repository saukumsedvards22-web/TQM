'use client';
import Link from 'next/link';
import { motivationalQuotes } from '@/data/habits';
import { useEffect, useState } from 'react';

const features = [
  {
    href: '/roleplay',
    emoji: '🎭',
    title: 'AI Roleplay',
    desc: 'Practice with a live AI customer — handle objections in real time',
    color: 'from-blue-600 to-blue-800',
    badge: 'Most Popular',
  },
  {
    href: '/scripts',
    emoji: '📋',
    title: 'Sales Scripts',
    desc: 'Door approach, FORD, objections, and closing techniques',
    color: 'from-purple-600 to-purple-800',
    badge: null,
  },
  {
    href: '/quiz',
    emoji: '🧠',
    title: 'Quizzes & Tests',
    desc: 'Test your knowledge of sales process, products, and mindset',
    color: 'from-green-600 to-green-800',
    badge: null,
  },
  {
    href: '/habits',
    emoji: '⚡',
    title: 'Daily Habits',
    desc: 'Morning, selling, and evening habit checklists + streak tracker',
    color: 'from-amber-500 to-amber-700',
    badge: null,
  },
  {
    href: '/scenarios',
    emoji: '🎯',
    title: 'What-If Scenarios',
    desc: 'Real door situations — choose the best response and learn why',
    color: 'from-red-600 to-red-800',
    badge: null,
  },
];

export default function HomePage() {
  const [quote, setQuote] = useState(motivationalQuotes[0]);
  const [greeting, setGreeting] = useState('Good morning');

  useEffect(() => {
    const hour = new Date().getHours();
    if (hour >= 12 && hour < 17) setGreeting('Good afternoon');
    else if (hour >= 17) setGreeting('Good evening');
    const idx = Math.floor(Math.random() * motivationalQuotes.length);
    setQuote(motivationalQuotes[idx]);
  }, []);

  return (
    <div className="space-y-5 pb-6">
      {/* Header */}
      <div className="bg-gradient-to-br from-swa-navy to-swa-blue rounded-2xl p-6 text-white shadow-lg">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-swa-gold font-bold text-sm tracking-widest uppercase">SWA Trainer</span>
        </div>
        <h1 className="text-2xl font-bold mb-1">{greeting}, Rep! 👋</h1>
        <p className="text-blue-200 text-sm">Every door is a fresh start. Let&apos;s get to work.</p>

        {/* Quote */}
        <div className="mt-4 bg-white/10 rounded-xl p-4 border border-white/20">
          <p className="text-white text-sm italic">&quot;{quote.quote}&quot;</p>
          <p className="text-blue-300 text-xs mt-1">— {quote.author}</p>
        </div>
      </div>

      {/* Quick stats bar */}
      <QuickStats />

      {/* Feature cards */}
      <div>
        <h2 className="text-gray-500 text-xs font-semibold uppercase tracking-wider mb-3">Training Modules</h2>
        <div className="space-y-3">
          {features.map((f) => (
            <Link key={f.href} href={f.href}>
              <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 flex items-center gap-4 hover:shadow-md transition-shadow active:scale-[0.99] cursor-pointer">
                <div className={`bg-gradient-to-br ${f.color} w-14 h-14 rounded-xl flex items-center justify-center text-2xl flex-shrink-0 shadow-sm`}>
                  {f.emoji}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-gray-900">{f.title}</span>
                    {f.badge && (
                      <span className="text-xs bg-swa-gold text-white px-2 py-0.5 rounded-full font-medium">
                        {f.badge}
                      </span>
                    )}
                  </div>
                  <p className="text-gray-500 text-sm mt-0.5 leading-snug">{f.desc}</p>
                </div>
                <span className="text-gray-300 text-xl flex-shrink-0">›</span>
              </div>
            </Link>
          ))}
        </div>
      </div>

      {/* Daily reminder */}
      <div className="bg-amber-50 border border-amber-200 rounded-2xl p-4 text-center">
        <p className="text-amber-800 font-semibold text-sm">Today&apos;s Focus</p>
        <p className="text-amber-700 text-sm mt-1">
          Practice one sales script before you hit the doors. Reps who rehearse daily close 40% more.
        </p>
      </div>
    </div>
  );
}

function QuickStats() {
  const [stats, setStats] = useState({ streak: 0, quizScore: 0, scenariosCompleted: 0 });

  useEffect(() => {
    const streak = parseInt(localStorage.getItem('swa_streak') || '0');
    const quizScore = parseInt(localStorage.getItem('swa_best_quiz') || '0');
    const scenariosCompleted = parseInt(localStorage.getItem('swa_scenarios') || '0');
    setStats({ streak, quizScore, scenariosCompleted });
  }, []);

  return (
    <div className="grid grid-cols-3 gap-3">
      {[
        { label: 'Day Streak', value: stats.streak, icon: '🔥', color: 'text-orange-600' },
        { label: 'Best Quiz', value: `${stats.quizScore}%`, icon: '🧠', color: 'text-green-600' },
        { label: 'Scenarios', value: stats.scenariosCompleted, icon: '🎯', color: 'text-blue-600' },
      ].map((s) => (
        <div key={s.label} className="bg-white rounded-xl shadow-sm border border-gray-100 p-3 text-center">
          <div className="text-xl">{s.icon}</div>
          <div className={`text-xl font-bold ${s.color}`}>{s.value}</div>
          <div className="text-gray-400 text-xs">{s.label}</div>
        </div>
      ))}
    </div>
  );
}
