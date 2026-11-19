import { useMemo, useState } from "react";
import { Button } from "../../components/button";
import { Badge } from "../../components/status";
import { classNames } from "../../lib/format";
import {
  filterPromptOptions,
  paginatePromptOptions,
  promptEntriesToOptions,
  promptKindInfo,
  promptOptionLabel,
  type PromptKind,
  type PromptOption,
} from "./settings-types";
import {
  EmptyState,
  ErrorBanner,
  KeyValueRow,
  Note,
  Section,
  SelectInput,
  Skeleton,
  TextAreaInput,
  TextInput,
} from "./settings-fields";
import type { SettingsWorkspace } from "./use-settings-workspace";

function formatUpdated(value: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : date.toLocaleDateString();
}

function defaultOptions(options: PromptOption[], current: string) {
  const list = options.map((option) => ({ value: option.id, label: promptOptionLabel(option) }));
  if (current && !list.some((option) => option.value === current)) {
    list.unshift({ value: current, label: "Saved selection (not in the catalog anymore)" });
  }
  return list;
}

/**
 * One catalog tab: Descriptions, Structures and Moods differ only by `kind`.
 * The workspace default is account settings (Save all applies it); the editor
 * writes a user-owned prompt immediately.
 */
export function PromptCatalogTab({ workspace, kind }: { workspace: SettingsWorkspace; kind: PromptKind }) {
  const ws = workspace;
  const info = promptKindInfo(kind);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);

  const options = ws.promptWorkspace[kind];
  const entries = ws.userPrompts[kind];
  const loading = ws.promptWorkspaceLoading[kind] || ws.userPromptsLoading[kind];
  const catalogError = ws.promptWorkspaceError[kind];
  const libraryError = ws.userPromptsError[kind];
  const defaultField =
    kind === "descriptions" ? "descriptionId" : kind === "structures" ? "structureId" : "moodId";
  const selectedId = ws.promptDefaults[defaultField];
  const selected = options.find((option) => option.id === selectedId) ?? null;
  const structureSelected =
    kind === "descriptions"
      ? ws.promptWorkspace.structures.find((option) => option.id === ws.promptDefaults.structureId) ?? null
      : null;
  const selectedAdmin = options.filter((option) => !option.owned);

  const filteredEntries = useMemo(
    () =>
      filterPromptOptions(promptEntriesToOptions(entries), search).map(
        (option) => entries.find((entry) => entry.id === option.id) ?? null,
      ),
    [entries, search],
  );
  const visibleEntries = filteredEntries.filter((entry): entry is NonNullable<typeof entry> =>
    Boolean(entry),
  );
  const paged = paginatePromptOptions(
    promptEntriesToOptions(visibleEntries),
    page,
  );
  const pageEntries = paged.items
    .map((option) => visibleEntries.find((entry) => entry.id === option.id) ?? null)
    .filter((entry): entry is NonNullable<typeof entry> => Boolean(entry));

  const draft = ws.promptDrafts[kind];
  const errors = ws.promptFieldErrors[kind];
  const editorDirty = ws.promptEditorDirty[kind];
  const busy = Boolean(ws.saving) || ws.promptBusy === kind;
  const selectedEntry = draft.id ? entries.find((entry) => entry.id === draft.id) ?? null : null;
  const defaultTabDirty =
    kind === "descriptions"
      ? ws.promptDefaultsDirty.descriptions || ws.promptDefaultsDirty.structures
      : ws.promptDefaultsDirty[kind];

  function applyDefault(id: string) {
    ws.updatePromptDefault(defaultField, id);
  }

  if (loading) {
    return (
      <div className="space-y-4" data-testid={`settings-${kind}-tab`}>
        <div data-testid={`settings-${kind}-loading`}>
          <Section title={`${info.label} defaults`} description="Workspace selection and your own catalog.">
            <Skeleton rows={4} />
          </Section>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4" data-testid={`settings-${kind}-tab`}>
      {ws.tabErrors[kind] ? (
        <ErrorBanner
          message={ws.tabErrors[kind] as string}
          onRetry={() => ws.clearTabError(kind)}
          retryLabel="Dismiss"
        />
      ) : null}
      {catalogError ? (
        <ErrorBanner
          message={`Unable to load the ${info.singular} catalog. ${catalogError}`}
          onRetry={() => ws.retryPromptWorkspace(kind)}
        />
      ) : null}
      {libraryError ? (
        <ErrorBanner
          message={`Unable to load your ${info.singular} library. ${libraryError}`}
          onRetry={() => ws.retryUserPrompts(kind)}
        />
      ) : null}

      <Section
        title="Workspace default"
        description={`Loads on the Music page after Save all changes.`}
        action={
          <Badge tone={defaultTabDirty ? "warning" : "neutral"}>
            {defaultTabDirty ? "Unsaved" : "Saved"}
          </Badge>
        }
        data-testid={`settings-${kind}-default`}
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <SelectInput
            id={`settings-${kind}-default-select`}
            label={`Default ${info.singular}`}
            placeholder={`No default ${info.singular}`}
            value={selectedId}
            options={defaultOptions(options, selectedId)}
            disabled={busy}
            onChange={(event) => applyDefault(event.target.value)}
          />
          {kind === "descriptions" ? (
            <div>
              <SelectInput
                id="settings-descriptions-default-structure"
                label="Default structure"
                placeholder="No default structure"
                value={ws.promptDefaults.structureId}
                options={defaultOptions(ws.promptWorkspace.structures, ws.promptDefaults.structureId)}
                disabled={busy}
                onChange={(event) => ws.updatePromptDefault("structureId", event.target.value)}
              />
              {ws.promptDefaultsDirty.structures ? (
                <p className="mt-1 text-caption text-warning">
                  The paired structure is unsaved. Save all changes applies it from the Structures default.
                </p>
              ) : null}
            </div>
          ) : null}
        </div>

        <div className="rounded-control border border-border bg-surface-1">
          <KeyValueRow label="Selected name" value={selected?.name ?? "None"} />
          {kind === "descriptions" ? (
            <KeyValueRow label="Paired structure" value={structureSelected?.name ?? "None"} />
          ) : null}
          <KeyValueRow
            label="Source"
            value={
              selected ? (
                <Badge tone={selected.owned ? "accent" : "neutral"}>
                  {selected.owned ? "Your prompt" : "Camxora · read-only"}
                </Badge>
              ) : (
                "—"
              )
            }
          />
        </div>

        <Note>
          {kind === "descriptions"
            ? "The paired structure is shared with the Structures tab. Save all changes applies the pair on the Music page."
            : "The selected default only takes effect after Save all changes in the footer."}
        </Note>
      </Section>

      <Section
        title="Camxora catalog"
        description="Shared entries from the Admin Portal. They are read-only here."
        data-testid={`settings-${kind}-catalog`}
      >
        {selectedAdmin.length === 0 ? (
          <p className="text-body text-text-secondary">No Camxora {info.label.toLowerCase()} are available.</p>
        ) : (
          <ul className="divide-y divide-border">
            {selectedAdmin.map((option) => (
              <li key={option.id} className="flex items-center justify-between gap-3 py-2">
                <span className="min-w-0 truncate text-body text-text-primary">{option.name}</span>
                <div className="flex shrink-0 items-center gap-2">
                  <Badge tone="neutral">Read-only</Badge>
                  <Button
                    variant="ghost"
                    className="h-7 px-2"
                    disabled={busy || selectedId === option.id}
                    onClick={() => applyDefault(option.id)}
                  >
                    {selectedId === option.id ? "Selected" : "Use as default"}
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section
        title="Your catalog"
        description={`Your own ${info.label.toLowerCase()}. Searching filters this list only.`}
        action={
          <Button
            variant="secondary"
            className="h-8"
            disabled={busy}
            onClick={() => ws.requestNewPrompt(kind)}
            data-testid={`settings-${kind}-new`}
          >
            New {info.singular}
          </Button>
        }
        data-testid={`settings-${kind}-library`}
      >
        <TextInput
          id={`settings-${kind}-search`}
          label="Search your catalog"
          placeholder="Search by name"
          value={search}
          disabled={entries.length === 0}
          onChange={(event) => {
            setSearch(event.target.value);
            setPage(0);
          }}
        />

        {entries.length === 0 ? (
          <EmptyState
            message={`No user ${info.label.toLowerCase()} yet.`}
            action={
              <Button variant="secondary" onClick={() => ws.requestNewPrompt(kind)}>
                Create {info.singular}
              </Button>
            }
          />
        ) : visibleEntries.length === 0 ? (
          <EmptyState message="No prompt matches this search." />
        ) : (
          <>
            <ul className="divide-y divide-border" data-testid={`settings-${kind}-list`}>
              {pageEntries.map((entry) => {
                const active = draft.id === entry.id;
                return (
                  <li key={entry.id}>
                    <button
                      type="button"
                      className={classNames(
                        "flex w-full items-center justify-between gap-3 rounded-control px-2 py-2 text-left transition-colors",
                        active ? "bg-surface-active" : "hover:bg-surface-hover",
                      )}
                      onClick={() => ws.requestSelectPrompt(kind, entry)}
                    >
                      <span className="min-w-0">
                        <span className="block truncate text-body text-text-primary">{entry.name}</span>
                        <span className="block text-caption text-text-muted">
                          {formatUpdated(entry.updatedAt) || "No update date"}
                        </span>
                      </span>
                      {ws.promptDefaults[defaultField] === entry.id ? (
                        <Badge tone="accent">Music default</Badge>
                      ) : null}
                    </button>
                  </li>
                );
              })}
            </ul>
            <div className="flex items-center justify-between gap-3">
              <span className="text-caption text-text-muted" data-testid={`settings-${kind}-page-label`}>
                Page {paged.page + 1} of {paged.pageCount} · {visibleEntries.length}{" "}
                {visibleEntries.length === 1 ? "entry" : "entries"}
              </span>
              <div className="flex gap-2">
                <Button
                  variant="secondary"
                  className="h-7 px-2.5"
                  disabled={busy || paged.page === 0}
                  onClick={() => setPage((value) => Math.max(0, value - 1))}
                >
                  Previous
                </Button>
                <Button
                  variant="secondary"
                  className="h-7 px-2.5"
                  disabled={busy || paged.page >= paged.pageCount - 1}
                  onClick={() => setPage((value) => Math.min(paged.pageCount - 1, value + 1))}
                >
                  Next
                </Button>
              </div>
            </div>
          </>
        )}
      </Section>

      <Section
        title="Prompt editor"
        description={
          draft.id
            ? "Editing a prompt in your catalog. Saving writes it immediately."
            : "Create a prompt in your catalog. Saving writes it immediately."
        }
        action={
          <Badge tone={editorDirty ? "warning" : "neutral"}>{editorDirty ? "Unsaved" : "Saved"}</Badge>
        }
        data-testid={`settings-${kind}-editor`}
      >
        <TextInput
          id={`settings-${kind}-name`}
          label="Name"
          value={draft.name}
          maxLength={100}
          error={errors.name}
          disabled={busy}
          placeholder={`${info.label} name`}
          onChange={(event) => ws.updatePromptDraft(kind, { name: event.target.value })}
        />
        <div>
          <TextAreaInput
            id={`settings-${kind}-content`}
            label={info.contentLabel}
            rows={8}
            value={draft.content}
            maxLength={5000}
            error={errors.content}
            disabled={busy}
            placeholder={info.placeholder}
            onChange={(event) => ws.updatePromptDraft(kind, { content: event.target.value })}
          />
          <p
            className={classNames(
              "mt-1 text-right text-caption",
              draft.content.length > 5000 ? "text-danger" : "text-text-muted",
            )}
            data-testid={`settings-${kind}-count`}
          >
            {draft.content.length} / 5000
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="primary"
            loading={ws.promptBusy === kind}
            disabled={busy || !editorDirty}
            onClick={() => void ws.savePromptEditor(kind)}
            data-testid={`settings-${kind}-save`}
          >
            Save prompt
          </Button>
          <Button
            variant="secondary"
            disabled={busy || !editorDirty}
            onClick={() => ws.resetPromptEditor(kind)}
          >
            Revert
          </Button>
          <Button
            variant="ghost"
            disabled={busy || !selectedEntry}
            onClick={() => selectedEntry && applyDefault(selectedEntry.id)}
          >
            Use as default
          </Button>
          <Button
            variant="ghost"
            className="text-danger"
            disabled={busy || !draft.id}
            onClick={() => selectedEntry && ws.requestDeletePrompt(kind, selectedEntry)}
            data-testid={`settings-${kind}-delete`}
          >
            Delete
          </Button>
        </div>
        {!draft.id ? (
          <p className="text-caption text-text-muted">
            Save this prompt before it can be deleted. The delete action asks for confirmation.
          </p>
        ) : null}
        <Note>
          {kind === "descriptions"
            ? "Camxora descriptions and your own descriptions both appear in the Music selector. Only your own entries can be edited here."
            : "Camxora entries are read-only here; your own entries can be edited and deleted."}
        </Note>
      </Section>
    </div>
  );
}
