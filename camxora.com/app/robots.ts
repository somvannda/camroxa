import type { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        disallow: [
          "/account",
          "/library",
          "/create",
          "/checkout",
          "/notifications",
          "/invite",
          "/redeem",
          "/artist-dashboard",
        ],
      },
    ],
    sitemap: "https://camxora.com/sitemap.xml",
    host: "https://camxora.com",
  };
}
