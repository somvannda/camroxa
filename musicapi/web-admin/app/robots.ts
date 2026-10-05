import type { MetadataRoute } from "next";

/**
 * The admin console is operator-only. Keep crawlers out entirely — this
 * complements the `robots: { index: false }` metadata in the root layout.
 */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: [{ userAgent: "*", disallow: "/" }],
  };
}
