import './globals.css';
import type { Metadata } from 'next';
import { Inter, Outfit } from 'next/font/google';

import { PlayerProvider } from '@/components/player-provider';
import { AuthProvider } from '@/components/auth-provider';
import { LikesProvider } from '@/components/likes-provider';
import ShellSwitcher from '@/components/shell-switcher';

const fontSans = Inter({
  variable: '--font-sans',
  subsets: ['latin'],
  weight: ['400', '500', '600'],
  display: 'swap',
});

const fontDisplay = Outfit({
  variable: '--font-display',
  subsets: ['latin'],
  weight: ['500', '600', '700'],
  display: 'swap',
});

export const metadata: Metadata = {
  title: {
    default: 'Camxora Music',
    template: '%s | Camxora Music',
  },
  description: 'Create and stream AI-generated music with Camxora.',
  icons: {
    icon: [{ url: '/camxora-logo.svg', type: 'image/svg+xml' }],
    shortcut: ['/camxora-logo.svg'],
    apple: ['/camxora-logo.svg'],
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${fontSans.variable} ${fontDisplay.variable}`}>
      <body>
        <AuthProvider>
          <PlayerProvider>
            <LikesProvider>
              <ShellSwitcher>{children}</ShellSwitcher>
            </LikesProvider>
          </PlayerProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
