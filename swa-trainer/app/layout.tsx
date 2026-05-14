import type { Metadata, Viewport } from 'next';
import './globals.css';
import Nav from '@/components/Nav';

export const metadata: Metadata = {
  title: 'SWA Trainer — SouthWestern Advantage',
  description: 'Interactive sales training platform for SouthWestern Advantage student dealers',
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-gray-50 min-h-screen pb-20 md:pb-0">
        <Nav />
        <main className="max-w-2xl mx-auto px-4 pt-4 md:pt-6">{children}</main>
      </body>
    </html>
  );
}
