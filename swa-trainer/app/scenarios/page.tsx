'use client';
import { useState, useEffect } from 'react';
import { scenarios, type Scenario } from '@/data/scenarios';

type OutcomeColors = {
  best: string;
  okay: string;
  bad: string;
};

const OUTCOME_STYLES: OutcomeColors = {
  best: 'border-green-400 bg-green-50',
  okay: 'border-amber-400 bg-amber-50',
  bad: 'border-red-400 bg-red-50',
};

const OUTCOME_LABELS: Record<string, string> = {
  best: '✅ Best Response',
  okay: '⚠️ Acceptable',
  bad: '❌ Avoid This',
};

export default function ScenariosPage() {
  const [selected, setSelected] = useState<Scenario | null>(null);
  const [chosenIdx, setChosenIdx] = useState<number | null>(null);
  const [completedIds, setCompletedIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    const saved = localStorage.getItem('swa_scenario_ids');
    if (saved) setCompletedIds(new Set(JSON.parse(saved) as string[]));
  }, []);

  function openScenario(s: Scenario) {
    setSelected(s);
    setChosenIdx(null);
  }

  function choose(idx: number) {
    if (chosenIdx !== null) return;
    setChosenIdx(idx);
    if (selected) {
      const next = new Set(completedIds);
      next.add(selected.id);
      setCompletedIds(next);
      localStorage.setItem('swa_scenario_ids', JSON.stringify([...next]));
      localStorage.setItem('swa_scenarios', String(next.size));
    }
  }

  if (selected) {
    return (
      <div className="space-y-4 pb-6">
        <div className="flex items-start gap-3">
          <button
            onClick={() => setSelected(null)}
            className="text-gray-400 hover:text-gray-600 font-bold text-2xl leading-none mt-1"
          >
            ‹
          </button>
          <div>
            <h1 className="text-xl font-bold text-gray-900">{selected.title}</h1>
          </div>
        </div>

        {/* Setup */}
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 text-sm text-blue-800">
          <span className="font-semibold">Setup: </span>{selected.setup}
        </div>

        {/* Situation */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
          <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
            The Situation
          </div>
          <p className="text-gray-800 text-sm leading-relaxed">{selected.situation}</p>
        </div>

        {/* Options */}
        <div>
          <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
            {chosenIdx === null ? 'What do you do?' : 'Results'}
          </div>
          <div className="space-y-3">
            {selected.options.map((opt, i) => {
              const isChosen = chosenIdx === i;
              const revealed = chosenIdx !== null;
              let cls =
                'w-full rounded-xl border-2 p-4 text-left text-sm transition-all ';
              if (!revealed) {
                cls += 'bg-white border-gray-200 hover:border-blue-400 hover:bg-blue-50 cursor-pointer active:scale-[0.99]';
              } else {
                cls += OUTCOME_STYLES[opt.outcome];
                if (!isChosen) cls += ' opacity-60';
              }
              return (
                <button
                  key={i}
                  onClick={() => choose(i)}
                  className={cls}
                  disabled={chosenIdx !== null}
                >
                  <p className={`font-medium ${revealed ? 'text-gray-800' : 'text-gray-800'} leading-snug`}>
                    {opt.label}
                  </p>
                  {revealed && (
                    <div className="mt-2 pt-2 border-t border-current/10">
                      <span className="text-xs font-bold block mb-1">
                        {OUTCOME_LABELS[opt.outcome]}
                      </span>
                      <p className="text-xs opacity-80 leading-relaxed">{opt.explanation}</p>
                    </div>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {/* Key lesson */}
        {chosenIdx !== null && (
          <div className="bg-swa-navy rounded-2xl p-5 text-white">
            <div className="text-xs font-semibold text-blue-300 uppercase tracking-wider mb-2">
              Key Lesson
            </div>
            <p className="text-sm leading-relaxed">{selected.keyLesson}</p>
          </div>
        )}

        {chosenIdx !== null && (
          <button
            onClick={() => setSelected(null)}
            className="w-full bg-swa-blue text-white py-3.5 rounded-xl font-semibold text-sm"
          >
            Next Scenario →
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-4 pb-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">What-If Scenarios</h1>
        <p className="text-gray-500 text-sm mt-1">
          Real door situations. Choose your response — find out why it works or doesn&apos;t.
        </p>
      </div>

      <div className="bg-blue-50 border border-blue-200 rounded-xl p-3 flex items-center gap-3">
        <span className="text-2xl">🎯</span>
        <p className="text-blue-800 text-sm">
          {completedIds.size} of {scenarios.length} scenarios completed
        </p>
      </div>

      <div className="space-y-3">
        {scenarios.map((s) => {
          const isDone = completedIds.has(s.id);
          return (
            <button
              key={s.id}
              onClick={() => openScenario(s)}
              className="w-full bg-white rounded-2xl shadow-sm border border-gray-100 p-4 text-left hover:shadow-md transition-shadow active:scale-[0.99]"
            >
              <div className="flex items-start gap-3">
                <div className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 ${isDone ? 'bg-green-100' : 'bg-gray-100'}`}>
                  <span className="text-xl">{isDone ? '✅' : '🎯'}</span>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <h3 className="font-semibold text-gray-900 text-sm">{s.title}</h3>
                    {isDone && (
                      <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full">Done</span>
                    )}
                  </div>
                  <p className="text-gray-500 text-xs mt-0.5 leading-snug">{s.setup}</p>
                </div>
                <span className="text-gray-300 text-xl flex-shrink-0">›</span>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
