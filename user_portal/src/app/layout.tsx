import type { Metadata } from "next";
import { IBM_Plex_Sans, Sora } from "next/font/google";
import "./globals.css";
import { Toaster } from "@/components/ui/toaster";
import { getSiteMetadataBaseUrl } from "@/lib/site-urls";

const fontSans = IBM_Plex_Sans({
  variable: "--font-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  display: "swap",
});

const fontDisplay = Sora({
  variable: "--font-display",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  display: "swap",
});

export const metadata: Metadata = {
  metadataBase: new URL(getSiteMetadataBaseUrl()),
  title: {
    default: "Camxora Account",
    template: "%s | Camxora Account",
  },
  description:
    "Camxora account access for sign-in, sign-up, onboarding, billing, and faceless desktop studio activation.",
  applicationName: "Camxora Account",
  icons: {
    icon: [{ url: "/camxora-logo.svg", type: "image/svg+xml" }],
    shortcut: ["/camxora-logo.svg"],
    apple: ["/camxora-logo.svg"],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${fontSans.variable} ${fontDisplay.variable} h-full antialiased dark`}
    >
      <body className="min-h-full flex flex-col font-sans">
        {children}
        <Toaster />
      </body>
    </html>
  );
}
