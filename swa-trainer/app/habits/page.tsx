'use client';
import { useState, useEffect } from 'react';
import { habits, motivationalQuotes } from '@/data/habits';

const TIME_SECTIONS = [
  { id: 'morning', label: 'Morning', emoji: '🌅', color: 'from-orange-400 to-amber-500' },
  { id: 'selling', label: 'Selling Day', emoji: '🚪', color: 'from-blue-500 to-blue-700' },
  { id: 'evening', label: 'Evening', emoji: '🌙', color: 'from-purple-600 to-purple-800' },
] as const;

function todayKey() {
  return `swa_habits_${new Date().toISOString().slice(0, 10)}`;
}
function streakKey() {
  return 'swa_streak';
}
function lastCompletedKey() {
  return 'swa_last_completed';
}

export default function HabitsPage() {
  const [checked, setChecked] = useState<Set<string>>(new Set());
  const [streak, setStreak] = useState(0);
  const [quote] = useState(() => motivationalQuotes[Math.floor(Math.random() * motivationalQuotes.length)]);

  useEffect(() => {
    const saved = localStorage.getItem(todayKey());
    if (saved) setChecked(new Set(JSON.parse(saved) as string[]));
    const s = parseInt(localStorage.getItem(streakKey()) || '0');
    setStreak(s);
  }, []);

  function toggle(id: string) {
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      localStorage.setItem(todayKey(), JSON.stringify([...next]));

      // Update streak when all habits completed
      const total = habits.length;
      if (next.size === total) {
        const today = new Date().toISOString().slice(0, 10);
        const lastCompleted = localStorage.getItem(lastCompletedKey());
        if (lastCompleted !== today) {
          localStorage.setItem(lastCompletedKey(), today);
          const newStreak = streak + 1;
          setStreak(newStreak);
          localStorage.setItem(streakKey(), String(newStreak));
        }
      }

      return next;
    });
  }

  const completedCount = checked.size;
  const totalCount = habits.length;
  const pct = Math.round((completedCount / totalCount) * 100);

  return (
    <div className="space-y-4 pb-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Daily Habits</h1>
        <p className="text-gray-500 text-sm mt-1">Small consistent actions build championship reps.</p>
      </div>

      {/* Progress + streak */}
      <div className="bg-gradient-to-br from-swa-navy to-swa-blue rounded-2xl p-5 text-white">
        <div className="flex items-center justify-between mb-3">
          <div>
            <div className="text-3xl font-bold">{completedCount} / {totalCount}</div>
            <div className="text-blue-200 text-sm">habits completed today</div>
          </div>
          <div className="text-center">
            <div className="text-3xl">🔥</div>
            <div className="text-2xl font-bold">{streak}</div>
            <div className="text-blue-200 text-xs">day streak</div>
          </div>
        </div>
        <div className="h-2 bg-white/20 rounded-full overflow-hidden">
          <div
            className="h-full bg-swa-gold rounded-full transition-all duration-500"
            style={{ width: `${pct}%` }}
          />
        </div>
        <div className="text-right text-blue-200 text-xs mt-1">{pct}%</div>
      </div>

      {/* Quote */}
      <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
        <p className="text-amber-800 text-sm italic">&quot;{quote.quote}&quot;</p>
        <p className="text-amber-600 text-xs mt-1">— {quote.author}</p>
      </div>

      {/* Habit sections */}
      {TIME_SECTIONS.map((section) => {
        const sectionHabits = habits.filter((h) => h.time === section.id);
        const sectionDone = sectionHabits.filter((h) => checked.has(h.id)).length;
        return (
          <div key={section.id}>
            <div className={`bg-gradient-to-r ${section.color} rounded-xl px-4 py-2.5 flex items-center justify-between mb-2`}>
              <div className="flex items-center gap-2">
                <span className="text-xl">{section.emoji}</span>
                <span className="text-white font-semibold text-sm">{section.label}</span>
              </div>
              <span className="text-white/80 text-xs font-medium">
                {sectionDone}/{sectionHabits.length}
              </span>
            </div>

            <div className="space-y-2">
              {sectionHabits.map((habit) => {
                const isDone = checked.has(habit.id);
                return (
                  <button
                    key={habit.id}
                    onClick={() => toggle(habit.id)}
                    className={`w-full bg-white rounded-xl border p-4 text-left transition-all active:scale-[0.99] ${
                      isDone ? 'border-green-300 bg-green-50' : 'border-gray-100 hover:border-gray-200'
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      <div
                        className={`w-6 h-6 rounded-full border-2 flex-shrink-0 flex items-center justify-center mt-0.5 transition-all ${
                          isDone ? 'bg-green-500 border-green-500' : 'border-gray-300'
                        }`}
                      >
                        {isDone && <span className="text-white text-xs font-bold">✓</span>}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className={`font-medium text-sm ${isDone ? 'text-green-800 line-through decoration-green-400' : 'text-gray-900'}`}>
                          {habit.title}
                        </p>
                        <p className="text-gray-400 text-xs mt-0.5 leading-snug">{habit.description}</p>
                        <p className="text-blue-600 text-xs mt-1 italic">Why: {habit.why}</p>
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        );
      })}

      {completedCount === totalCount && (
        <div className="bg-green-50 border border-green-300 rounded-2xl p-5 text-center">
          <div className="text-4xl mb-2">🏆</div>
          <p className="text-green-800 font-bold text-lg">Full Day Completed!</p>
          <p className="text-green-600 text-sm mt-1">
            That&apos;s what W.I.T. looks like. See you tomorrow.
          </p>
        </div>
      )}
    </div>
  );
}
