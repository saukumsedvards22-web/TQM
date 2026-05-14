'use client';
import { useState } from 'react';
import { salesScripts, scriptCategories, type SalesScript } from '@/data/scripts';

export default function ScriptsPage() {
  const [activeCategory, setActiveCategory] = useState<string>('all');
  const [selected, setSelected] = useState<SalesScript | null>(null);

  const filtered =
    activeCategory === 'all'
      ? salesScripts
      : salesScripts.filter((s) => s.category === activeCategory);

  if (selected) {
    const cat = scriptCategories.find((c) => c.id === selected.category);
    return (
      <div className="space-y-4 pb-6">
        <div className="flex items-center gap-3">
          <button
            onClick={() => setSelected(null)}
            className="text-gray-400 hover:text-gray-600 font-bold text-2xl leading-none"
          >
            ‹
          </button>
          <div>
            <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${cat?.color}`}>
              {cat?.label}
            </span>
            <h1 className="text-xl font-bold text-gray-900 mt-1">{selected.title}</h1>
          </div>
        </div>

        {/* Script content */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
          <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">Script</h2>
          <pre className="text-gray-800 text-sm whitespace-pre-wrap leading-relaxed font-sans">
            {selected.content}
          </pre>
        </div>

        {/* Tips */}
        <div className="bg-amber-50 border border-amber-200 rounded-2xl p-5">
          <h2 className="text-xs font-semibold text-amber-700 uppercase tracking-wider mb-3">
            Pro Tips
          </h2>
          <ul className="space-y-2">
            {selected.tips.map((tip, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-amber-800">
                <span className="text-amber-500 mt-0.5 flex-shrink-0">✓</span>
                {tip}
              </li>
            ))}
          </ul>
        </div>

        {/* Key words */}
        {selected.keyWords && (
          <div className="bg-blue-50 border border-blue-200 rounded-2xl p-4">
            <h2 className="text-xs font-semibold text-blue-700 uppercase tracking-wider mb-2">
              Key Qualities
            </h2>
            <div className="flex flex-wrap gap-2">
              {selected.keyWords.map((kw) => (
                <span key={kw} className="bg-blue-100 text-blue-700 text-xs px-3 py-1 rounded-full font-medium">
                  {kw}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-4 pb-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Sales Scripts</h1>
        <p className="text-gray-500 text-sm mt-1">
          Every script you need — from the door to the close.
        </p>
      </div>

      {/* Category filter */}
      <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-hide">
        <button
          onClick={() => setActiveCategory('all')}
          className={`flex-shrink-0 text-xs px-3 py-1.5 rounded-full font-medium transition-colors ${
            activeCategory === 'all'
              ? 'bg-swa-blue text-white'
              : 'bg-white border border-gray-200 text-gray-600'
          }`}
        >
          All
        </button>
        {scriptCategories.map((cat) => (
          <button
            key={cat.id}
            onClick={() => setActiveCategory(cat.id)}
            className={`flex-shrink-0 text-xs px-3 py-1.5 rounded-full font-medium transition-colors ${
              activeCategory === cat.id
                ? 'bg-swa-blue text-white'
                : 'bg-white border border-gray-200 text-gray-600'
            }`}
          >
            {cat.label}
          </button>
        ))}
      </div>

      {/* Script list */}
      <div className="space-y-3">
        {filtered.map((script) => {
          const cat = scriptCategories.find((c) => c.id === script.category);
          return (
            <button
              key={script.id}
              onClick={() => setSelected(script)}
              className="w-full bg-white rounded-2xl shadow-sm border border-gray-100 p-4 text-left hover:shadow-md transition-shadow active:scale-[0.99]"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1">
                  <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${cat?.color}`}>
                    {cat?.label}
                  </span>
                  <h3 className="font-semibold text-gray-900 mt-1">{script.title}</h3>
                  <p className="text-gray-400 text-xs mt-1 line-clamp-2">
                    {script.content.slice(0, 100).replace(/"/g, '')}...
                  </p>
                </div>
                <span className="text-gray-300 text-xl flex-shrink-0 mt-1">›</span>
              </div>
              <div className="mt-2 flex items-center gap-1">
                <span className="text-xs text-gray-400">{script.tips.length} pro tips</span>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
