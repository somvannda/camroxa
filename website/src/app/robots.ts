import type { MetadataRoute } from "next";
import { getWebsiteBaseUrl } from "@/lib/site-urls";

export default function robots(): MetadataRoute.Robots {
  const baseUrl = getWebsiteBaseUrl();
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
      },
    ],
    sitemap: `${baseUrl}/sitemap.xml`,
  };
}

