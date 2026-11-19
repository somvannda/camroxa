import fs from "node:fs";
import path from "node:path";
import { app } from "electron";

export interface AppPaths {
  userData: string;
  downloads: string;
  renders: string;
  images: string;
  templates: string;
  projects: string;
  cache: string;
  logs: string;
}

export function getAppPaths(): AppPaths {
  const userData = app.getPath("userData");
  return {
    userData,
    downloads: path.join(userData, "downloads"),
    renders: path.join(userData, "renders"),
    images: path.join(userData, "images"),
    templates: path.join(userData, "templates"),
    projects: path.join(userData, "projects"),
    cache: path.join(userData, "cache"),
    logs: path.join(userData, "logs"),
  };
}

export function ensureAppDirs(): AppPaths {
  const paths = getAppPaths();
  for (const directory of Object.values(paths)) {
    fs.mkdirSync(directory, { recursive: true });
  }
  return paths;
}
