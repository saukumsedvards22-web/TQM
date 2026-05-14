'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

const NAV_ITEMS = [
  { href: '/', label: 'Home', emoji: '🏠' },
  { href: '/roleplay', label: 'Roleplay', emoji: '🎭' },
  { href: '/scripts', label: 'Scripts', emoji: '📋' },
  { href: '/quiz', label: 'Quiz', emoji: '🧠' },
  { href: '/habits', label: 'Habits', emoji: '⚡' },
  { href: '/scenarios', label: 'Scenarios', emoji: '🎯' },
];

export default function Nav() {
  const pathname = usePathname();

  return (
    <>
      {/* Desktop sidebar / top bar */}
      <nav className="hidden md:flex items-center justify-between bg-swa-navy px-6 py-3 shadow-lg sticky top-0 z-50">
        <div className="flex items-center gap-2">
          <span className="text-swa-gold font-bold text-lg tracking-tight">SWA Trainer</span>
        </div>
        <div className="flex items-center gap-1">
          {NAV_ITEMS.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-swa-gold text-swa-navy'
                    : 'text-blue-200 hover:bg-white/10 hover:text-white'
                }`}
              >
                <span>{item.emoji}</span>
                <span>{item.label}</span>
              </Link>
            );
          })}
        </div>
      </nav>

      {/* Mobile bottom tab bar */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 z-50 shadow-2xl">
        <div className="grid grid-cols-6 h-16">
          {NAV_ITEMS.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex flex-col items-center justify-center gap-0.5 transition-colors ${
                  isActive ? 'text-swa-blue' : 'text-gray-400'
                }`}
              >
                <span className="text-xl leading-none">{item.emoji}</span>
                <span className={`text-[9px] font-medium leading-none ${isActive ? 'text-swa-blue' : 'text-gray-400'}`}>
                  {item.label}
                </span>
                {isActive && (
                  <span className="absolute bottom-0 w-8 h-0.5 bg-swa-blue rounded-full" />
                )}
              </Link>
            );
          })}
        </div>
      </nav>
    </>
  );
}
