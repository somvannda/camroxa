import type { MetadataRoute } from "next";

/**
 * Public pages (home, docs, legal) must stay crawlable — Google's OAuth brand
 * verification fetches them directly. Only authenticated app surfaces are
 * excluded so they never show up in search results.
 */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      disallow: ["/dashboard/", "/admin/", "/backend/"],
    },
    sitemap: "https://musicapi.camxora.com/sitemap.xml",
    host: "https://musicapi.camxora.com",
  };
}
