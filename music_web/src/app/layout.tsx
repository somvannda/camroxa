import './globals.css';
import type { Metadata, Viewport } from 'next';

// Self-hosted fonts (no external dependency)
import '@fontsource/inter/400.css';
import '@fontsource/inter/500.css';
import '@fontsource/inter/600.css';
import '@fontsource/outfit/500.css';
import '@fontsource/outfit/600.css';
import '@fontsource/outfit/700.css';

import { PlayerProvider } from '@/components/player-provider';
import { AuthProvider } from '@/components/auth-provider';
import { LikesProvider } from '@/components/likes-provider';
import ShellSwitcher from '@/components/shell-switcher';

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  viewportFit: 'cover',
  interactiveWidget: 'resizes-content',
};

export const metadata: Metadata = {
  title: {
    default: 'Camxora Music',
    template: '%s | Camxora Music',
  },
  description: 'Create and stream AI-generated music with Camxora.',
  icons: {
    icon: [
      { url: '/camxora-now-playing.png', sizes: '512x512', type: 'image/png' },
      { url: '/camxora-logo.svg', type: 'image/svg+xml' },
    ],
    shortcut: ['/camxora-now-playing.png'],
    apple: [{ url: '/apple-touch-icon.png', sizes: '180x180' }],
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
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
