import type { Metadata } from "next";
import "./globals.css";

import { AuthProvider } from "@/components/AuthProvider";

export const metadata: Metadata = {
  metadataBase: new URL("https://camxora.com"),
  applicationName: "Camxora",
  title: {
    default: "Camxora — Home",
    template: "%s — Camxora",
  },
  description:
    "Listen to what creators are making, or make the next track everyone plays.",
  icons: {
    icon: "/camxora-logo.svg",
  },
  openGraph: {
    type: "website",
    siteName: "Camxora",
    title: "Camxora — Create. Discover. Enjoy AI Music.",
    description:
      "Listen to what creators are making, or make the next track everyone plays.",
    images: [{ url: "/hero.png", width: 1200, height: 630, alt: "Camxora" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Camxora — Create. Discover. Enjoy AI Music.",
    description:
      "Listen to what creators are making, or make the next track everyone plays.",
    images: ["/hero.png"],
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap"
          rel="stylesheet"
        />
        <link rel="stylesheet" href="/fontawesome/css/all.min.css" />
      </head>
      <body data-auth="out">
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
