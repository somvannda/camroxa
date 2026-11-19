import { HashRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthGate } from "./features/auth/auth-gate";
import { FoundationPage } from "./features/foundation/foundation-page";
import { PlaceholderPage } from "./features/placeholders/placeholder-page";
import { Shell } from "./shell/shell";
import { UTILITY_ROUTES, WORKSPACE_ROUTES } from "./shell/routes";

const placeholders = [...WORKSPACE_ROUTES, ...UTILITY_ROUTES].filter(
  (route) => route.key !== "home",
);

export function App() {
  return (
    <HashRouter>
      <AuthGate>
        <Routes>
          <Route element={<Shell />}>
            <Route index element={<Navigate to="/home" replace />} />
            <Route path="/home" element={<FoundationPage />} />
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
