import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { Button } from "../components/button";

export interface NavigationGuard {
  /** True when leaving the page would discard unsaved work. */
  isBlocked(): boolean;
  /** Called once the user confirms leaving. */
  discard(): void;
}

interface NavigationGuardApi {
  /** Run `action`, asking for confirmation first when a guard is dirty. */
  attempt(action: () => void): void;
  register(guard: NavigationGuard): () => void;
}

const noopApi: NavigationGuardApi = {
  attempt: (action) => action(),
  register: () => () => {},
};

const NavigationGuardContext = createContext<NavigationGuardApi>(noopApi);

export function useNavigationGuard(): NavigationGuardApi {
  return useContext(NavigationGuardContext);
}

/** Register a page-level unsaved-changes guard for the lifetime of the component. */
export function useUnsavedGuard(guard: NavigationGuard): void {
  const api = useNavigationGuard();
  const latest = useRef(guard);
  latest.current = guard;

  useEffect(
    () =>
      api.register({
        isBlocked: () => latest.current.isBlocked(),
        discard: () => latest.current.discard(),
      }),
    [api],
  );
}

export function NavigationGuardProvider({ children }: { children: ReactNode }) {
  const guardRef = useRef<NavigationGuard | null>(null);
  const [pending, setPending] = useState<(() => void) | null>(null);

  const register = useCallback((guard: NavigationGuard) => {
    guardRef.current = guard;
    return () => {
      if (guardRef.current === guard) guardRef.current = null;
    };
  }, []);

  const attempt = useCallback((action: () => void) => {
    const guard = guardRef.current;
    if (guard?.isBlocked()) {
      setPending(() => action);
      return;
    }
    action();
  }, []);

  const value = useMemo(() => ({ attempt, register }), [attempt, register]);

  function stay() {
    setPending(null);
  }

  function leave() {
    const action = pending;
    setPending(null);
    guardRef.current?.discard();
    action?.();
  }

  useEffect(() => {
    if (pending === null) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        setPending(null);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [pending]);

  return (
    <NavigationGuardContext.Provider value={value}>
      {children}
      {pending !== null ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="navigation-guard-title"
            aria-describedby="navigation-guard-description"
            className="w-full max-w-md rounded-overlay border border-border bg-surface-1 p-5 shadow-2xl"
          >
            <h2 id="navigation-guard-title" className="text-title font-semibold text-text-primary">
              Discard unsaved changes?
            </h2>
            <p id="navigation-guard-description" className="mt-1 text-body text-text-secondary">
              You have unsaved changes on this page. Leaving now discards them.
            </p>
            <div className="mt-4 flex items-center justify-end gap-2">
              <Button autoFocus variant="secondary" onClick={stay}>
                Stay
              </Button>
              <Button variant="danger" onClick={leave}>
                Discard and leave
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </NavigationGuardContext.Provider>
  );
}
