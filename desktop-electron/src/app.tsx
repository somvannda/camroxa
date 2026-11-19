import { lazy, Suspense } from "react";
import { HashRouter, Navigate, Route, Routes } from "react-router-dom";
import { PageLoading } from "./components/page-loading";
import { AuthGate } from "./features/auth/auth-gate";
import { PlaceholderPage } from "./features/placeholders/placeholder-page";
import { UpdateGate } from "./features/updates/update-gate";
import { Shell } from "./shell/shell";
import { UTILITY_ROUTES, WORKSPACE_ROUTES } from "./shell/routes";

const DashboardPage = lazy(() =>
  import("./features/dashboard/dashboard-page").then((module) => ({
    default: module.DashboardPage,
  })),
);
const ProfilePage = lazy(() =>
  import("./features/profile/profile-page").then((module) => ({ default: module.ProfilePage })),
);
const ProgressPage = lazy(() =>
  import("./features/progress/views/progress-page").then((module) => ({
    default: module.ProgressPage,
  })),
);
const MusicPage = lazy(() =>
  import("./features/music/views/music-page").then((module) => ({ default: module.MusicPage })),
);
const ImagePage = lazy(() =>
  import("./features/image/views/image-page").then((module) => ({ default: module.ImagePage })),
);
const MarketplacePage = lazy(() =>
  import("./features/marketplace/views/marketplace-page").then((module) => ({
    default: module.MarketplacePage,
  })),
);
const SettingsPage = lazy(() =>
  import("./features/settings/views/settings-page").then((module) => ({
    default: module.SettingsPage,
  })),
);
const VizzyPage = lazy(() =>
  import("./features/vizzy/vizzy-page").then((module) => ({ default: module.VizzyPage })),
);

const IMPLEMENTED_ROUTES = new Set([
  "home",
  "profile",
  "progress",
  "music",
  "image",
  "vizzy",
  "marketplace",
  "settings",
]);

const placeholders = [...WORKSPACE_ROUTES, ...UTILITY_ROUTES].filter(
  (route) => !IMPLEMENTED_ROUTES.has(route.key),
);

export function App() {
  return (
    <HashRouter>
      <UpdateGate>
        <AuthGate>
          <Suspense fallback={<PageLoading />}>
            <Routes>
              <Route element={<Shell />}>
                <Route index element={<Navigate to="/home" replace />} />
                <Route path="/home" element={<DashboardPage />} />
                <Route path="/profile" element={<ProfilePage />} />
                <Route path="/progress" element={<ProgressPage />} />
                <Route path="/music" element={<MusicPage />} />
                <Route path="/image" element={<ImagePage />} />
                <Route path="/vizzy" element={<VizzyPage />} />
                <Route path="/marketplace" element={<MarketplacePage />} />
                <Route path="/settings" element={<SettingsPage />} />
                {placeholders.map((route) => (
                  <Route
                    key={route.key}
                    path={route.path}
                    element={<PlaceholderPage route={route} />}
                  />
                ))}
                <Route path="*" element={<Navigate to="/home" replace />} />
              </Route>
            </Routes>
          </Suspense>
        </AuthGate>
      </UpdateGate>
    </HashRouter>
  );
}
