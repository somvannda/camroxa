import './globals.css';
import type { Metadata } from 'next';
import { Inter, Outfit } from 'next/font/google';

import PlayerBar from '@/components/player-bar';
import { PlayerProvider } from '@/components/player-provider';
import { AuthProvider } from '@/components/auth-provider';
import { LikesProvider } from '@/components/likes-provider';
import Sidebar from '@/components/sidebar';
import SiteFooter from '@/components/site-footer';
import SiteHeader from '@/components/site-header';
import { DiscoveryRail } from '@/components/catalog-cards';
import { getStreamingHome, listArtists } from '@/lib/streaming-api';

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
  description: 'Stream AI-generated music published by Camxora creators.',
  icons: {
    icon: [{ url: '/camxora-logo.svg', type: 'image/svg+xml' }],
    shortcut: ['/camxora-logo.svg'],
    apple: ['/camxora-logo.svg'],
  },
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  let railTracks: Awaited<ReturnType<typeof getStreamingHome>>['recent_tracks'] = [];
  let railAlbums: Awaited<ReturnType<typeof getStreamingHome>>['albums'] = [];
  let railArtists: Awaited<ReturnType<typeof listArtists>>['items'] = [];
  try {
    const home = await getStreamingHome();
    railTracks = home.recent_tracks;
    railAlbums = home.albums;
  } catch {
    /* empty rail */
  }
  try {
    const artists = await listArtists(8, 0);
    railArtists = artists.items;
  } catch {
    /* empty rail */
  }

  return (
    <html lang="en" className={`${fontSans.variable} ${fontDisplay.variable}`}>
      <body>
        <AuthProvider>
          <PlayerProvider>
            <LikesProvider>
            <div className="flex min-h-screen flex-col pb-32">
              <SiteHeader />
              <div className="mx-auto flex w-full max-w-[1600px] flex-1 gap-4 px-4 py-6 md:px-6">
                <Sidebar />
                <main className="min-w-0 flex-1">{children}</main>
                <DiscoveryRail tracks={railTracks} albums={railAlbums} artists={railArtists} />
              </div>
              <SiteFooter />
            </div>
            <PlayerBar />
            </LikesProvider>
          </PlayerProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
