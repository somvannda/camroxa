import type { MetadataRoute } from "next";

const BASE = "https://musicapi.camxora.com";

/** Public, login-free pages (the pages Google's OAuth brand review checks). */
export default function sitemap(): MetadataRoute.Sitemap {
  return [
    { url: `${BASE}/`, changeFrequency: "weekly", priority: 1 },
    { url: `${BASE}/docs`, changeFrequency: "weekly", priority: 0.8 },
    { url: `${BASE}/privacy`, changeFrequency: "yearly", priority: 0.5 },
    { url: `${BASE}/terms`, changeFrequency: "yearly", priority: 0.5 },
    { url: `${BASE}/data-deletion`, changeFrequency: "yearly", priority: 0.5 },
  ];
}
