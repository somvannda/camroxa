import type { Metadata } from "next";
import { Inter, Outfit } from "next/font/google";
import "./globals.css";
import { Toaster } from "@/components/ui/toaster";
import { getWebsiteBaseUrl } from "@/lib/site-urls";

const fontSans = Inter({
  variable: "--font-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  display: "swap",
});

const fontDisplay = Outfit({
  variable: "--font-display",
  subsets: ["latin"],
  weight: ["500", "600", "700"],
  display: "swap",
});

export const metadata: Metadata = {
  metadataBase: new URL(getWebsiteBaseUrl()),
  title: {
    default: "Camxora",
    template: "%s | Camxora",
  },
  description:
    "Camxora is the faceless desktop studio for music channel production — lyrics, music, images, video, and export in one Windows app.",
  applicationName: "Camxora",
  icons: {
    icon: [
      { url: "/camxora-logo.svg", type: "image/svg+xml" },
      { url: "/favicon.svg", type: "image/svg+xml" },
    ],
    shortcut: ["/camxora-logo.svg"],
    apple: ["/camxora-logo.svg"],
  },
  alternates: {
    canonical: "/",
  },
  openGraph: {
    type: "website",
    url: getWebsiteBaseUrl(),
    siteName: "Camxora",
    title: "Camxora",
    description:
      "Faceless desktop studio for music channels — lyrics to YouTube-ready video.",
  },
  twitter: {
    card: "summary_large_image",
    title: "Camxora",
    description:
      "Faceless desktop studio for music channels — lyrics to YouTube-ready video.",
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
