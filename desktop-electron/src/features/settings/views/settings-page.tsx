import { useEffect, useRef, type KeyboardEvent as ReactKeyboardEvent } from "react";
import { PageHeader } from "../../../components/page-header";
import { Button } from "../../../components/button";
import { classNames } from "../../../lib/format";
import { useUnsavedGuard } from "../../../shell/navigation-guard";
import { SETTINGS_TABS, dirtyTabLabel, type SettingsTab } from "../settings-types";
import { ConfirmDialog } from "../settings-fields";
import { ProfilesTab } from "../profiles-tab";
import { PublicationTab } from "../publication-tab";
import { PreferencesTab } from "../preferences-tab";
import { useSettingsWorkspace } from "../use-settings-workspace";

function tabLabel(tab: SettingsTab): string {
  return SETTINGS_TABS.find((item) => item.id === tab)?.label ?? tab;
}

export function SettingsPage() {
  const ws = useSettingsWorkspace();
  useUnsavedGuard({
    isBlocked: () => ws.dirtyCount > 0,
    discard: () => {
      ws.discardProfiles();
      ws.discardPublication();
      ws.discardPreferences();
    },
  });
  const saveAllRef = useRef(ws.saveAll);
  const dirtyRef = useRef(ws.dirtyCount);
  saveAllRef.current = ws.saveAll;
  dirtyRef.current = ws.dirtyCount;

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
        event.preventDefault();
        saveAllRef.current();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  useEffect(() => {
    function onBeforeUnload(event: BeforeUnloadEvent) {
      if (dirtyRef.current === 0) return;
      event.preventDefault();
      event.returnValue = "";
    }
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, []);

  const dirtyPerTab: Record<SettingsTab, boolean> = {
    profiles: ws.dirtyTabs.includes("profiles"),
    publication: ws.dirtyTabs.includes("publication"),
    preferences: ws.dirtyTabs.includes("preferences"),
  };

  function onTabListKeyDown(event: ReactKeyboardEvent<HTMLElement>) {
    const keys = ["ArrowDown", "ArrowUp", "ArrowRight", "ArrowLeft", "Home", "End"];
    if (!keys.includes(event.key)) return;
    event.preventDefault();
    const index = SETTINGS_TABS.findIndex((tab) => tab.id === ws.activeTab);
    let nextIndex = index;
    if (event.key === "ArrowDown" || event.key === "ArrowRight") nextIndex = (index + 1) % SETTINGS_TABS.length;
    if (event.key === "ArrowUp" || event.key === "ArrowLeft") {
      nextIndex = (index - 1 + SETTINGS_TABS.length) % SETTINGS_TABS.length;
    }
    if (event.key === "Home") nextIndex = 0;
    if (event.key === "End") nextIndex = SETTINGS_TABS.length - 1;
    const next = SETTINGS_TABS[nextIndex].id;
    ws.setActiveTab(next);
    const target = event.currentTarget.querySelector<HTMLButtonElement>(`[data-settings-tab="${next}"]`);
    target?.focus();
  }

  const pending = ws.pendingConfirm;
  let confirmTitle = "";
  let confirmBody = "";
  let confirmLabel = "Continue";
  let confirmTone: "primary" | "danger" = "primary";
  if (pending?.kind === "switch-profile") {
    confirmTitle = "Discard unsaved profile changes?";
    confirmBody = `Switching to ${pending.profile.name} reloads the editor. Unsaved changes to the current profile are lost.`;
    confirmLabel = "Discard and switch";
    confirmTone = "danger";
  } else if (pending?.kind === "new-profile") {
    confirmTitle = "Discard this profile draft?";
    confirmBody = "Creating a new profile clears the unsaved changes in the current editor.";
    confirmLabel = "Discard and create";
    confirmTone = "danger";
  } else if (pending?.kind === "switch-publication") {
    confirmTitle = "Discard unsaved publication changes?";
    confirmBody = "Loading another profile reloads its publication defaults. Unsaved changes are lost.";
    confirmLabel = "Discard and switch";
    confirmTone = "danger";
  } else if (pending?.kind === "discard-all") {
    confirmTitle = "Discard all changes?";
    confirmBody = `${dirtyTabLabel(ws.dirtyTabs)} Every draft reverts to the last saved values.`;
    confirmLabel = "Discard changes";
    confirmTone = "danger";
  } else if (pending?.kind === "delete-profile") {
    confirmTitle = `Delete ${pending.profile.name}?`;
    confirmBody =
      "This removes the channel profile. Generated files on disk are not deleted, and runs that already started keep the configuration they captured.";
    confirmLabel = "Delete profile";
    confirmTone = "danger";
  } else if (pending?.kind === "disconnect-youtube") {
    confirmTitle = "Disconnect YouTube?";
    confirmBody = `The channel is removed from ${pending.profile.name}. Publication defaults stay on the profile and uploads stop until a channel is connected again.`;
    confirmLabel = "Disconnect";
    confirmTone = "danger";
  }

  const savingLabel = ws.saving?.current ? `Saving ${tabLabel(ws.saving.current).toLowerCase()}…` : null;
  const footerStatus = savingLabel
    ? savingLabel
    : ws.dirtyCount > 0
      ? dirtyTabLabel(ws.dirtyTabs)
      : ws.lastSavedAt
        ? `All changes saved at ${new Date(ws.lastSavedAt).toLocaleTimeString()}.`
        : "No unsaved changes.";

  return (
    <div className="flex min-h-full flex-col">
      <PageHeader
        eyebrow="Workspace"
        title="Settings"
        description="Channel profiles, YouTube publication defaults, and local preferences."
      />

      <div className="flex flex-1 items-start gap-6 p-6">
        <nav
          aria-label="Settings sections"
          role="tablist"
          aria-orientation="vertical"
          className="sticky top-6 w-[200px] shrink-0"
          onKeyDown={onTabListKeyDown}
        >
          <div className="space-y-0.5">
            {SETTINGS_TABS.map((tab) => {
              const active = ws.activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  type="button"
                  role="tab"
                  id={`settings-tab-${tab.id}`}
                  aria-selected={active}
                  aria-controls="settings-tabpanel"
                  tabIndex={active ? 0 : -1}
                  data-settings-tab={tab.id}
                  className={classNames(
                    "relative flex h-8 w-full items-center gap-2 rounded-[6px] px-2.5 text-left text-body transition-colors",
                    active
                      ? "bg-surface-active text-text-primary"
                      : "text-text-secondary hover:bg-surface-hover hover:text-text-primary",
                  )}
                  onClick={() => ws.setActiveTab(tab.id)}
                >
                  {active ? (
                    <span className="absolute left-0 top-1.5 h-5 w-0.5 rounded-full bg-accent" />
                  ) : null}
                  <span className="flex-1 truncate">{tab.label}</span>
                  {dirtyPerTab[tab.id] ? (
                    <>
                      <span className="h-1.5 w-1.5 rounded-full bg-warning" aria-hidden="true" />
                      <span className="sr-only">Unsaved changes</span>
                    </>
                  ) : null}
                </button>
              );
            })}
          </div>
          <p className="mt-6 px-2.5 text-caption leading-5 text-text-muted">
            Descriptions, Structures, Moods, Pools and Suno arrive in P8. They are not tabs in this
            build yet.
          </p>
        </nav>

        <div
          className="min-w-0 flex-1"
          id="settings-tabpanel"
          role="tabpanel"
          aria-labelledby={`settings-tab-${ws.activeTab}`}
        >
          {ws.activeTab === "profiles" ? <ProfilesTab workspace={ws} /> : null}
          {ws.activeTab === "publication" ? <PublicationTab workspace={ws} /> : null}
          {ws.activeTab === "preferences" ? <PreferencesTab workspace={ws} /> : null}
        </div>
      </div>

      <footer className="sticky bottom-0 z-10 flex flex-wrap items-center justify-between gap-3 border-t border-border bg-surface-1 px-6 py-3">
        <p
          aria-live="polite"
          className={classNames(
            "text-body",
            ws.saving ? "text-text-secondary" : ws.dirtyCount > 0 ? "text-warning" : "text-text-secondary",
          )}
          data-testid="settings-footer-status"
        >
          {footerStatus}
        </p>
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            disabled={ws.dirtyCount === 0 || Boolean(ws.saving)}
            onClick={ws.requestDiscardAll}
          >
            Discard
          </Button>
          <Button
            variant="primary"
            loading={Boolean(ws.saving)}
            disabled={ws.dirtyCount === 0 || Boolean(ws.saving)}
            onClick={ws.saveAll}
            data-testid="settings-save-all"
          >
            Save all changes
          </Button>
        </div>
      </footer>

      <ConfirmDialog
        open={Boolean(pending)}
        title={confirmTitle}
        description={confirmBody}
        confirmLabel={confirmLabel}
        tone={confirmTone}
        busy={ws.confirmBusy}
        onConfirm={ws.resolveConfirm}
        onCancel={ws.cancelConfirm}
      />
    </div>
  );
}
