'use client';
import { useState, useEffect } from 'react';
import { quizQuestions, quizCategories } from '@/data/quizzes';

type QuizState = 'select' | 'playing' | 'results';

export default function QuizPage() {
  const [state, setState] = useState<QuizState>('select');
  const [category, setCategory] = useState<string>('All');
  const [questions, setQuestions] = useState(quizQuestions);
  const [currentIdx, setCurrentIdx] = useState(0);
  const [selected, setSelected] = useState<number | null>(null);
  const [answers, setAnswers] = useState<(number | null)[]>([]);
  const [bestScore, setBestScore] = useState(0);

  useEffect(() => {
    const saved = parseInt(localStorage.getItem('swa_best_quiz') || '0');
    setBestScore(saved);
  }, []);

  function startQuiz(cat: string) {
    const filtered =
      cat === 'All' ? quizQuestions : quizQuestions.filter((q) => q.category === cat);
    const shuffled = [...filtered].sort(() => Math.random() - 0.5).slice(0, 10);
    setQuestions(shuffled);
    setCategory(cat);
    setCurrentIdx(0);
    setSelected(null);
    setAnswers([]);
    setState('playing');
  }

  function handleSelect(idx: number) {
    if (selected !== null) return;
    setSelected(idx);
  }

  function handleNext() {
    const newAnswers = [...answers, selected];
    if (currentIdx + 1 >= questions.length) {
      setAnswers(newAnswers);
      const correct = newAnswers.filter((a, i) => a === questions[i].correctIndex).length;
      const pct = Math.round((correct / questions.length) * 100);
      if (pct > bestScore) {
        setBestScore(pct);
        localStorage.setItem('swa_best_quiz', String(pct));
      }
      setState('results');
    } else {
      setAnswers(newAnswers);
      setCurrentIdx((i) => i + 1);
      setSelected(null);
    }
  }

  if (state === 'select') {
    return (
      <div className="space-y-4 pb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Quizzes & Tests</h1>
          <p className="text-gray-500 text-sm mt-1">Test your knowledge. Learn from the explanations.</p>
        </div>

        {bestScore > 0 && (
          <div className="bg-green-50 border border-green-200 rounded-xl p-4 flex items-center gap-3">
            <span className="text-3xl">🏆</span>
            <div>
              <p className="text-green-800 font-semibold">Best Score: {bestScore}%</p>
              <p className="text-green-600 text-xs">Keep practicing to improve!</p>
            </div>
          </div>
        )}

        <div>
          <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">Choose a Category</h2>
          <div className="space-y-3">
            {['All', ...quizCategories].map((cat) => {
              const count =
                cat === 'All'
                  ? quizQuestions.length
                  : quizQuestions.filter((q) => q.category === cat).length;
              return (
                <button
                  key={cat}
                  onClick={() => startQuiz(cat)}
                  className="w-full bg-white rounded-2xl shadow-sm border border-gray-100 p-4 text-left hover:shadow-md transition-shadow active:scale-[0.99] flex items-center justify-between"
                >
                  <div>
                    <div className="font-semibold text-gray-900">{cat}</div>
                    <div className="text-gray-400 text-sm">{count} questions</div>
                  </div>
                  <span className="text-gray-300 text-xl">›</span>
                </button>
              );
            })}
          </div>
        </div>
      </div>
    );
  }

  if (state === 'results') {
    const correct = answers.filter((a, i) => a === questions[i].correctIndex).length;
    const pct = Math.round((correct / questions.length) * 100);
    const emoji = pct >= 90 ? '🏆' : pct >= 70 ? '💪' : pct >= 50 ? '📚' : '🔄';
    const label = pct >= 90 ? 'Excellent!' : pct >= 70 ? 'Solid work!' : pct >= 50 ? 'Keep studying!' : 'Time to drill!';

    return (
      <div className="space-y-4 pb-6">
        <div className="bg-gradient-to-br from-swa-navy to-swa-blue rounded-2xl p-6 text-center text-white">
          <div className="text-5xl mb-2">{emoji}</div>
          <div className="text-3xl font-bold">{pct}%</div>
          <div className="text-blue-200 font-medium">{label}</div>
          <div className="text-blue-300 text-sm mt-1">
            {correct} of {questions.length} correct
          </div>
        </div>

        {/* Review answers */}
        <div className="space-y-3">
          <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Review</h2>
          {questions.map((q, i) => {
            const userAnswer = answers[i];
            const isCorrect = userAnswer === q.correctIndex;
            return (
              <div
                key={q.id}
                className={`bg-white rounded-2xl shadow-sm border p-4 ${
                  isCorrect ? 'border-green-200' : 'border-red-200'
                }`}
              >
                <div className="flex items-start gap-2 mb-2">
                  <span className="text-lg flex-shrink-0">{isCorrect ? '✅' : '❌'}</span>
                  <p className="font-medium text-gray-900 text-sm">{q.question}</p>
                </div>
                {!isCorrect && userAnswer !== null && (
                  <p className="text-red-600 text-xs mb-1 ml-7">
                    Your answer: {q.options[userAnswer]}
                  </p>
                )}
                <p className="text-green-700 text-xs mb-2 ml-7">
                  Correct: {q.options[q.correctIndex]}
                </p>
                <p className="text-gray-500 text-xs ml-7 italic">{q.explanation}</p>
              </div>
            );
          })}
        </div>

        <div className="flex gap-3">
          <button
            onClick={() => setState('select')}
            className="flex-1 bg-gray-100 text-gray-700 py-3 rounded-xl font-semibold text-sm"
          >
            Choose Category
          </button>
          <button
            onClick={() => startQuiz(category)}
            className="flex-1 bg-swa-blue text-white py-3 rounded-xl font-semibold text-sm"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  // Playing state
  const q = questions[currentIdx];
  const progress = ((currentIdx) / questions.length) * 100;

  return (
    <div className="space-y-4 pb-6">
      {/* Progress */}
      <div className="flex items-center gap-3">
        <button onClick={() => setState('select')} className="text-gray-400 font-bold text-xl">‹</button>
        <div className="flex-1">
          <div className="flex justify-between text-xs text-gray-400 mb-1">
            <span>{category}</span>
            <span>{currentIdx + 1} / {questions.length}</span>
          </div>
          <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
            <div
              className="h-full bg-swa-blue rounded-full transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      </div>

      {/* Question */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
        <div className="text-xs font-medium text-gray-400 mb-2">{q.category}</div>
        <p className="text-gray-900 font-semibold text-base leading-snug">{q.question}</p>
      </div>

      {/* Options */}
      <div className="space-y-2">
        {q.options.map((opt, i) => {
          let cls =
            'w-full bg-white rounded-xl border p-4 text-left text-sm font-medium transition-all ';
          if (selected === null) {
            cls += 'border-gray-200 hover:border-blue-400 hover:bg-blue-50 text-gray-800 cursor-pointer';
          } else if (i === q.correctIndex) {
            cls += 'border-green-400 bg-green-50 text-green-800';
          } else if (i === selected) {
            cls += 'border-red-400 bg-red-50 text-red-800';
          } else {
            cls += 'border-gray-100 text-gray-400';
          }
          return (
            <button key={i} onClick={() => handleSelect(i)} className={cls} disabled={selected !== null}>
              <span className="mr-2 font-bold text-gray-400">{String.fromCharCode(65 + i)}.</span>
              {opt}
            </button>
          );
        })}
      </div>

      {/* Explanation */}
      {selected !== null && (
        <div
          className={`rounded-2xl p-4 border text-sm ${
            selected === q.correctIndex
              ? 'bg-green-50 border-green-200 text-green-800'
              : 'bg-red-50 border-red-200 text-red-800'
          }`}
        >
          <p className="font-semibold mb-1">
            {selected === q.correctIndex ? '✅ Correct!' : '❌ Not quite.'}
          </p>
          <p className="text-sm opacity-90">{q.explanation}</p>
        </div>
      )}

      {selected !== null && (
        <button
          onClick={handleNext}
          className="w-full bg-swa-blue text-white py-3.5 rounded-xl font-semibold text-sm"
        >
          {currentIdx + 1 >= questions.length ? 'See Results' : 'Next Question'} →
        </button>
      )}
    </div>
  );
}
