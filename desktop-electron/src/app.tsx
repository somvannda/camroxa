import { HashRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthGate } from "./features/auth/auth-gate";
import { DashboardPage } from "./features/dashboard/dashboard-page";
import { PlaceholderPage } from "./features/placeholders/placeholder-page";
import { ProfilePage } from "./features/profile/profile-page";
import { Shell } from "./shell/shell";
import { UTILITY_ROUTES, WORKSPACE_ROUTES } from "./shell/routes";

const IMPLEMENTED_ROUTES = new Set(["home", "profile"]);

const placeholders = [...WORKSPACE_ROUTES, ...UTILITY_ROUTES].filter(
  (route) => !IMPLEMENTED_ROUTES.has(route.key),
);

export function App() {
  return (
    <HashRouter>
      <AuthGate>
        <Routes>
          <Route element={<Shell />}>
            <Route index element={<Navigate to="/home" replace />} />
            <Route path="/home" element={<DashboardPage />} />
            <Route path="/profile" element={<ProfilePage />} />
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
      </AuthGate>
    </HashRouter>
  );
}
