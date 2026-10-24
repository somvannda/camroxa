import type { Metadata } from "next";
import "./globals.css";

import { AuthProvider } from "@/components/AuthProvider";

export const metadata: Metadata = {
  title: {
    default: "Camxora — Home",
    template: "%s — Camxora",
  },
  description:
    "Listen to what creators are making, or make the next track everyone plays.",
  icons: {
    icon: "/camxora-logo.svg",
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
