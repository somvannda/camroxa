import type {
  EffectPackCatalogItem,
  EffectPackDomain,
  EffectPackSelectionStatus,
  EffectPackTemplateReference,
  TemplateEffectPackMap,
} from './effectPackContracts'

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function mergeRecords(base: Record<string, unknown>, patch: Record<string, unknown>): Record<string, unknown> {
  const next: Record<string, unknown> = { ...base }
  Object.entries(patch).forEach(([key, value]) => {
    if (isRecord(value) && isRecord(next[key])) {
      next[key] = mergeRecords(next[key] as Record<string, unknown>, value)
      return
    }
    next[key] = value
  })
  return next
}

export function readTemplateEffectPackMap(template: Record<string, unknown>): TemplateEffectPackMap {
  const effectPacks = isRecord(template.effectPacks) ? template.effectPacks : {}
  const next: TemplateEffectPackMap = {}

  ;(['spectrum', 'background', 'logo', 'particles'] as const).forEach((domain) => {
    const entry = effectPacks[domain]
    if (!isRecord(entry)) {
      return
    }
    const packId = String(entry.packId ?? '').trim()
    const version = String(entry.version ?? '').trim()
    if (!packId || !version) {
      return
    }
    next[domain] = { packId, version }
  })

  return next
}

export function buildTemplateEffectPackReferencePatch(
  domain: EffectPackDomain,
  selection: EffectPackTemplateReference | null,
): Record<string, unknown> {
  return {
    effectPacks: {
      [domain]: selection
        ? {
            packId: selection.packId,
            version: selection.version,
          }
        : null,
    },
  }
}

export function buildTemplateEffectPackApplyPatch(
  domain: EffectPackDomain,
  item: Pick<EffectPackCatalogItem, 'packId' | 'version' | 'templatePatch'>,
): Record<string, unknown> {
  return mergeRecords(buildTemplateEffectPackReferencePatch(domain, {
    packId: item.packId,
    version: item.version,
  }), item.templatePatch)
}

export function resolveEffectPackSelectionStatus(
  domain: EffectPackDomain,
  selection: EffectPackTemplateReference | null,
  catalogItems: EffectPackCatalogItem[],
): EffectPackSelectionStatus {
  if (!selection) {
    return {
      domain,
      selection: null,
      item: null,
      status: 'missing',
      message: 'No effect pack selected.',
    }
  }

  const exact = catalogItems.find(
    (item) => item.domain === domain && item.packId === selection.packId && item.version === selection.version,
  )
  if (!exact) {
    return {
      domain,
      selection,
      item: null,
      status: 'missing',
      message: `Selected ${domain} pack ${selection.packId}@${selection.version} is not installed.`,
    }
  }

  if (exact.status === 'ready' || exact.status === 'available') {
    return {
      domain,
      selection,
      item: exact,
      status: exact.status,
      message: `${exact.name} (${exact.version}) is available.`,
    }
  }

  const reason = exact.issues[0] || `${exact.name} (${exact.version}) is not available.`
  return {
    domain,
    selection,
    item: exact,
    status: exact.status,
    message: reason,
  }
}

export function buildEffectPackCatalogOptions(
  domain: EffectPackDomain,
  catalogItems: EffectPackCatalogItem[],
): Array<{ value: string; label: string }> {
  return catalogItems
    .filter((item) => item.domain === domain)
    .filter((item) => item.status === 'ready' || item.status === 'available')
    .map((item) => ({
      value: `${item.packId}::${item.version}`,
      label: `${item.name} (${item.version})`,
    }))
}

export function parseEffectPackCatalogValue(value: string): EffectPackTemplateReference | null {
  const [packId, version] = String(value || '').split('::')
  if (!packId || !version) {
    return null
  }
  return {
    packId: packId.trim(),
    version: version.trim(),
  }
}
