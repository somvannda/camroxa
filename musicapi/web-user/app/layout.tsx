import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import ClientProviders from "@/components/client-providers";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Camxora Music API — AI Music Generation REST API",
  description:
    "Camxora Music API is a developer platform for generating watermark-free AI music — vocals, instrumentals, extensions and covers — through a documented REST API.",
  applicationName: "Camxora Music API",
  alternates: { canonical: "https://musicapi.camxora.com" },
  openGraph: {
    type: "website",
    siteName: "Camxora Music API",
    url: "https://musicapi.camxora.com",
    title: "Camxora Music API — AI Music Generation REST API",
    description:
      "Generate watermark-free AI music — vocals, instrumentals, extensions and covers — through a documented REST API.",
  },
  // Optional Google Search Console ownership token (baked in at build time from
  // GOOGLE_SITE_VERIFICATION) so the OAuth app's domain can be verified without
  // editing code. Required for Google OAuth brand verification.
  ...(process.env.GOOGLE_SITE_VERIFICATION
    ? { verification: { google: process.env.GOOGLE_SITE_VERIFICATION } }
    : {}),
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col">
        <ClientProviders>{children}</ClientProviders>
      </body>
    </html>
  );
}
