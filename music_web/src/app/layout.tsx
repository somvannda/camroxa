import './globals.css';
import type { Metadata } from 'next';
import PlayerBar from '@/components/player-bar';
import { PlayerProvider } from '@/components/player-provider';
import Sidebar from '@/components/sidebar';

export const metadata: Metadata = {
  title: 'Camxora Music',
  description: 'Stream AI-generated music from Camxora creators.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <PlayerProvider>
          <div className="flex min-h-screen pb-24">
            <Sidebar />
            <div className="flex-1 px-6 py-8">{children}</div>
          </div>
          <PlayerBar />
        </PlayerProvider>
      </body>
    </html>
  );
}
