import { AppSelect } from '@/shared/ui/app-select'
import { Button } from '@/shared/ui/button'
import type { EffectPackSelectionStatus } from '@shared/effectPacks/effectPackContracts'

type EffectPackSelectorCardProps = {
  title: string
  subtitle: string
  selectedValue: string
  options: Array<{ value: string; label: string }>
  status: EffectPackSelectionStatus
  onApplySelection: (value: string) => void
  onClearSelection: () => void
  onInstallFromFile: () => void | Promise<void>
  onReloadCatalog: () => void | Promise<unknown>
  onToggleEnabled: () => void | Promise<void>
  onActivateVersion: () => void | Promise<void>
  onRemoveVersion: () => void | Promise<void>
  busy?: boolean
}

export function EffectPackSelectorCard({
  title,
  subtitle,
  selectedValue,
  options,
  status,
  onApplySelection,
  onClearSelection,
  onInstallFromFile,
  onReloadCatalog,
  onToggleEnabled,
  onActivateVersion,
  onRemoveVersion,
  busy = false,
}: EffectPackSelectorCardProps): React.JSX.Element {
  const toneClass =
    status.status === 'ready' || status.status === 'available'
      ? 'border-emerald-400/20 bg-emerald-500/10 text-emerald-100'
      : status.selection
        ? 'border-amber-400/20 bg-amber-500/10 text-amber-100'
        : 'border-white/10 bg-slate-950/50 text-slate-300'

  return (
    <div className="rounded-xl border border-white/10 bg-slate-950/55 p-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-200">{title}</p>
          <p className="mt-1 text-[10px] leading-4 text-slate-500">{subtitle}</p>
        </div>
        <span className={`rounded-lg border px-2 py-1 text-[10px] ${toneClass}`}>
          {status.selection ? status.status : 'none'}
        </span>
      </div>
      <div className="mt-3 grid gap-2">
        <AppSelect
          disabled={busy}
          options={options}
          placeholder="Select an installed pack"
          triggerClassName="h-9 bg-slate-950/70 text-xs"
          value={selectedValue}
          onChange={onApplySelection}
        />
        <p className="text-[10px] leading-4 text-slate-400">{status.message}</p>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        <Button disabled={busy} size="sm" type="button" variant="secondary" onClick={() => void onInstallFromFile()}>
          Install ZIP
        </Button>
        <Button disabled={busy} size="sm" type="button" variant="secondary" onClick={() => void onReloadCatalog()}>
          Reload
        </Button>
        <Button disabled={!status.selection || busy} size="sm" type="button" variant="secondary" onClick={onClearSelection}>
          Clear Pack
        </Button>
        {status.item ? (
          <Button disabled={busy} size="sm" type="button" variant="secondary" onClick={() => void onToggleEnabled()}>
            {status.item.enabled ? 'Disable' : 'Enable'}
          </Button>
        ) : null}
        {status.item && !status.item.active ? (
          <Button disabled={busy} size="sm" type="button" variant="secondary" onClick={() => void onActivateVersion()}>
            Activate
          </Button>
        ) : null}
        {status.item ? (
          <Button disabled={busy} size="sm" type="button" variant="secondary" onClick={() => void onRemoveVersion()}>
            Remove
          </Button>
        ) : null}
      </div>
    </div>
  )
}
