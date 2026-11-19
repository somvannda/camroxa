import { NavLink, useNavigate } from "react-router-dom";
import { Icon } from "../components/icon";
import { classNames } from "../lib/format";
import { useSessionStore } from "../store/session";
import { useNavigationGuard } from "./navigation-guard";
import { UTILITY_ROUTES, WORKSPACE_ROUTES, type ShellRoute } from "./routes";

function NavItem({ route }: { route: ShellRoute }) {
  const navigate = useNavigate();
  const guard = useNavigationGuard();

  return (
    <NavLink
      to={route.path}
      onClick={(event) => {
        event.preventDefault();
        guard.attempt(() => navigate(route.path));
      }}
      className={({ isActive }) =>
        classNames(
          "relative flex h-9 items-center gap-3 rounded-[8px] px-3 text-body-sm font-medium transition-colors",
          isActive
            ? "bg-accent-soft text-text-primary"
            : "text-text-muted hover:bg-surface-hover hover:text-text-primary",
        )
      }
    >
      {({ isActive }) => (
        <>
          {isActive ? <span className="absolute left-0 top-2 h-5 w-0.5 rounded-full bg-accent" /> : null}
          <Icon name={route.icon} size={15} className={isActive ? "text-accent" : "text-text-muted"} />
          <span className="flex-1 truncate">{route.label}</span>
        </>
      )}
    </NavLink>
  );
}

export function Sidebar() {
  const session = useSessionStore((state) => state.session);
  const clearSession = useSessionStore((state) => state.clear);
  const displayName = session?.displayName || "Guest user";
  const email = session?.email || "Not signed in";
  const initials = displayName
    .split(/\s+/)
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  async function signOut() {
    await window.camxora?.auth?.logout?.();
    clearSession();
  }

  return (
    <aside className="flex w-[256px] shrink-0 flex-col border-r border-border bg-sidebar">
      <div className="border-b border-border p-3">
        <div className="flex items-center gap-2.5 rounded-[8px] border border-border bg-surface-2 p-2">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent-soft text-meta font-semibold text-accent">
            {initials || "C"}
          </div>
          <div className="min-w-0">
            <p className="truncate text-body font-medium text-text-primary">{displayName}</p>
            <p className="truncate text-caption text-text-muted">{email}</p>
          </div>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto px-2 py-3">
        <p className="px-2 pb-2 text-caption text-text-muted">Workspace</p>
        <div className="space-y-0.5">
          {WORKSPACE_ROUTES.map((route) => (
            <NavItem key={route.key} route={route} />
          ))}
        </div>

        <p className="px-2 pb-2 pt-6 text-caption text-text-muted">System</p>
        <div className="space-y-0.5">
          {UTILITY_ROUTES.map((route) => (
            <NavItem key={route.key} route={route} />
          ))}
        </div>
      </nav>

      <div className="border-t border-border p-2">
        <button
          className="flex h-9 w-full items-center gap-3 rounded-[8px] px-3 text-body-sm text-text-secondary hover:bg-surface-hover hover:text-text-primary"
          onClick={() => void signOut()}
        >
          <Icon name="fa-arrow-right-from-bracket" size={15} className="text-text-muted" />
          Sign out
        </button>
      </div>
    </aside>
  );
}
