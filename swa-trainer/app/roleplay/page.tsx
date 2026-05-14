'use client';
import { useState, useRef, useEffect } from 'react';

const SCENARIOS = [
  {
    id: 'cold_door',
    title: 'Cold Door Approach',
    emoji: '🚪',
    desc: 'A stranger answers — start from zero',
    difficulty: 'Beginner',
    diffColor: 'bg-green-100 text-green-700',
    tip: 'Focus on your door approach and FORD questions. Get them talking about their kids.',
  },
  {
    id: 'warm_prospect',
    title: 'Warm Referral',
    emoji: '🤝',
    desc: 'They were referred — already slightly open',
    difficulty: 'Intermediate',
    diffColor: 'bg-blue-100 text-blue-700',
    tip: 'They\'re open but they\'ll ask tough product questions. Know your stuff.',
  },
  {
    id: 'objection_gauntlet',
    title: 'Objection Gauntlet',
    emoji: '🔥',
    desc: '6 objections incoming — handle them all',
    difficulty: 'Advanced',
    diffColor: 'bg-red-100 text-red-700',
    tip: 'Use Feel-Felt-Found for every objection. Stay calm and empathetic.',
  },
  {
    id: 'closing_practice',
    title: 'Close the Deal',
    emoji: '🏆',
    desc: 'They liked the demo — now close',
    difficulty: 'Advanced',
    diffColor: 'bg-purple-100 text-purple-700',
    tip: 'Use the assumptive or choice close. Don\'t ask "so do you want it?"',
  },
];

type Message = { role: 'user' | 'assistant'; content: string };

export default function RoleplayPage() {
  const [selectedScenario, setSelectedScenario] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [showTip, setShowTip] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const scenario = SCENARIOS.find((s) => s.id === selectedScenario);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isStreaming]);

  async function startScenario(id: string) {
    setSelectedScenario(id);
    setMessages([]);
    setInput('');
    setShowTip(true);
    // Auto-start: send an empty first message to get the customer's opening
    const opening: Message[] = [{ role: 'user', content: '[SCENE START: The door opens. Greet me.]' }];
    setMessages([]);
    await streamResponse(opening, id);
    setTimeout(() => setShowTip(false), 6000);
  }

  async function streamResponse(msgs: Message[], scenarioId?: string) {
    const sid = scenarioId ?? selectedScenario ?? 'cold_door';
    setIsStreaming(true);
    setMessages((prev) => [...prev, { role: 'assistant', content: '' }]);

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: msgs, scenario: sid }),
      });

      if (!res.ok || !res.body) throw new Error('Stream failed');

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let text = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        text += decoder.decode(value, { stream: true });
        setMessages((prev) => {
          const updated = [...prev];
          updated[updated.length - 1] = { role: 'assistant', content: text };
          return updated;
        });
      }
    } catch {
      setMessages((prev) => {
        const updated = [...prev];
        updated[updated.length - 1] = {
          role: 'assistant',
          content: '⚠️ Connection error. Make sure ANTHROPIC_API_KEY is set in .env.local',
        };
        return updated;
      });
    } finally {
      setIsStreaming(false);
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }

  async function sendMessage() {
    const text = input.trim();
    if (!text || isStreaming) return;
    setInput('');

    // Filter out the scene-start instruction from display
    const displayMessages = messages.filter((m) => !m.content.startsWith('[SCENE START'));
    const allMessages: Message[] = [
      ...messages,
      { role: 'user', content: text },
    ];
    setMessages([...displayMessages, { role: 'user', content: text }]);
    await streamResponse(allMessages);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }

  if (!selectedScenario) {
    return (
      <div className="space-y-4 pb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">AI Roleplay</h1>
          <p className="text-gray-500 text-sm mt-1">
            Practice with a real AI customer. Pick a scenario and start talking — just like a real door.
          </p>
        </div>

        <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 text-sm text-blue-800">
          <strong>How it works:</strong> The AI plays a homeowner. You play the rep. Say what you&apos;d actually say at the door. The AI will respond like a real customer — objections included.
        </div>

        <div className="space-y-3">
          {SCENARIOS.map((s) => (
            <button
              key={s.id}
              onClick={() => startScenario(s.id)}
              className="w-full bg-white rounded-2xl shadow-sm border border-gray-100 p-4 text-left hover:shadow-md transition-shadow active:scale-[0.99]"
            >
              <div className="flex items-start gap-4">
                <div className="text-3xl">{s.emoji}</div>
                <div className="flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-semibold text-gray-900">{s.title}</span>
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${s.diffColor}`}>
                      {s.difficulty}
                    </span>
                  </div>
                  <p className="text-gray-500 text-sm mt-0.5">{s.desc}</p>
                  <p className="text-gray-400 text-xs mt-1 italic">Tip: {s.tip}</p>
                </div>
              </div>
            </button>
          ))}
        </div>
      </div>
    );
  }

  const visibleMessages = messages.filter((m) => !m.content.startsWith('[SCENE START'));

  return (
    <div className="flex flex-col h-[calc(100vh-140px)] md:h-[calc(100vh-80px)]">
      {/* Header */}
      <div className="bg-white border-b border-gray-100 rounded-t-2xl px-4 py-3 flex items-center gap-3 shadow-sm flex-shrink-0">
        <button
          onClick={() => setSelectedScenario(null)}
          className="text-gray-400 hover:text-gray-600 font-bold text-lg leading-none"
        >
          ‹
        </button>
        <div className="text-2xl">{scenario?.emoji}</div>
        <div className="flex-1 min-w-0">
          <div className="font-semibold text-gray-900 text-sm">{scenario?.title}</div>
          <div className="text-gray-400 text-xs">{scenario?.difficulty}</div>
        </div>
        <button
          onClick={() => startScenario(selectedScenario)}
          className="text-xs bg-gray-100 hover:bg-gray-200 text-gray-600 px-3 py-1.5 rounded-lg font-medium transition-colors"
        >
          Restart
        </button>
      </div>

      {/* Tip banner */}
      {showTip && (
        <div className="bg-amber-50 border-b border-amber-200 px-4 py-2 flex-shrink-0">
          <p className="text-amber-700 text-xs">
            <strong>Tip:</strong> {scenario?.tip}
          </p>
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {visibleMessages.length === 0 && (
          <div className="text-center text-gray-400 text-sm py-8">
            The door is opening...
          </div>
        )}
        {visibleMessages.map((msg, i) => (
          <div key={i} className={`message-appear flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            {msg.role === 'assistant' && (
              <div className="w-8 h-8 rounded-full bg-swa-blue flex items-center justify-center text-white text-sm flex-shrink-0 mr-2 mt-1">
                🏠
              </div>
            )}
            <div
              className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                msg.role === 'user'
                  ? 'bg-swa-blue text-white rounded-tr-sm'
                  : 'bg-white border border-gray-100 text-gray-800 shadow-sm rounded-tl-sm'
              }`}
            >
              {msg.content || (
                <span className="flex gap-1 items-center h-4">
                  <span className="typing-dot w-1.5 h-1.5 bg-gray-400 rounded-full inline-block" />
                  <span className="typing-dot w-1.5 h-1.5 bg-gray-400 rounded-full inline-block" />
                  <span className="typing-dot w-1.5 h-1.5 bg-gray-400 rounded-full inline-block" />
                </span>
              )}
            </div>
            {msg.role === 'user' && (
              <div className="w-8 h-8 rounded-full bg-swa-gold flex items-center justify-center text-white text-sm flex-shrink-0 ml-2 mt-1">
                👤
              </div>
            )}
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="bg-white border-t border-gray-100 p-3 flex-shrink-0 shadow-lg rounded-b-2xl">
        <div className="flex gap-2 items-end">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Say what you'd say at the door..."
            rows={2}
            disabled={isStreaming}
            className="flex-1 resize-none border border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 text-gray-800 placeholder-gray-400"
          />
          <button
            onClick={sendMessage}
            disabled={!input.trim() || isStreaming}
            className="bg-swa-blue text-white w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 disabled:opacity-40 hover:bg-blue-800 transition-colors"
          >
            ➤
          </button>
        </div>
        <p className="text-gray-400 text-xs mt-1.5 text-center">Enter to send · Shift+Enter for new line</p>
      </div>
    </div>
  );
}
