import type { MetadataRoute } from "next";
import { allArtistSlugs } from "@/lib/artist-data";
import { allPlaylistSlugs } from "@/lib/playlist-data";

const BASE_URL = "https://camxora.com";

export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date();
  const staticRoutes = [
    "",
    "/discover",
    "/charts",
    "/community",
    "/studio",
    "/developers",
    "/pricing",
    "/about",
    "/blog",
    "/changelog",
    "/contact",
    "/support",
    "/legal",
    "/features",
    "/services",
    "/download",
    "/artist-program",
    "/publish",
    "/search",
    "/google-api",
    "/privacy",
    "/terms",
    "/cookies",
    "/copyright",
    "/acceptable-use",
    "/data-deletion",
  ];
  const playlists = allPlaylistSlugs().map((slug) => `/playlists/${slug}`);
  const artists = allArtistSlugs().map((id) => `/artist/${id}`);

  return [...staticRoutes, ...playlists, ...artists].map((route) => ({
    url: `${BASE_URL}${route || "/"}`,
    lastModified: now,
    changeFrequency: route === "" ? "daily" : "weekly",
    priority: route === "" ? 1 : route.startsWith("/pricing") ? 0.9 : 0.7,
  }));
}
