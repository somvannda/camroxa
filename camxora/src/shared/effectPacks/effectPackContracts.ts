import { z } from 'zod'

export const EFFECT_PACK_DOMAINS = ['spectrum', 'background', 'logo', 'particles'] as const

export type EffectPackDomain = (typeof EFFECT_PACK_DOMAINS)[number]

export const EFFECT_PACK_DOMAIN_CONTRACT_VERSIONS: Record<EffectPackDomain, number> = {
  spectrum: 1,
  background: 1,
  logo: 1,
  particles: 1,
}

export const effectPackDomainSchema = z.enum(EFFECT_PACK_DOMAINS)

const versionStringSchema = z.string().trim().min(1).max(64)

const effectPackPreviewSchema = z
  .object({
    title: z.string().trim().min(1).max(120).optional(),
    summary: z.string().trim().max(240).optional(),
    accentColor: z.string().trim().max(32).optional(),
  })
  .partial()
  .optional()

const spectrumTemplatePatchSchema = z
  .object({
    style: z.string().trim().min(1).optional(),
    spectrumEnabled: z.boolean().optional(),
    audioSettings: z.record(z.unknown()).optional(),
    position: z.record(z.unknown()).optional(),
    previewBindings: z.record(z.unknown()).optional(),
    layers: z.array(z.record(z.unknown())).optional(),
  })
  .strict()

const backgroundTemplatePatchSchema = z
  .object({
    backgroundSettings: z.record(z.unknown()).optional(),
    effects: z
      .object({
        vignette: z.record(z.unknown()).optional(),
        smoke: z.record(z.unknown()).optional(),
      })
      .partial()
      .optional(),
  })
  .strict()

const logoTemplatePatchSchema = z
  .object({
    logoPath: z.string().optional(),
    previewLogo: z.string().optional(),
    logoSettings: z.record(z.unknown()).optional(),
  })
  .strict()

const particlesTemplatePatchSchema = z
  .object({
    particlesSettings: z.record(z.unknown()).optional(),
  })
  .strict()

const sharedManifestShape = {
  manifestVersion: z.literal(1),
  packId: z
    .string()
    .trim()
    .min(3)
    .max(120)
    .regex(/^[a-z0-9]+(?:[._-][a-z0-9]+)*$/i),
  name: z.string().trim().min(1).max(120),
  vendor: z.string().trim().min(1).max(120),
  version: versionStringSchema,
  domain: effectPackDomainSchema,
  description: z.string().trim().max(500).optional(),
  tags: z.array(z.string().trim().min(1).max(32)).max(12).optional(),
  appVersionRange: z.string().trim().min(1).max(64).default('*'),
  domainContractVersion: z.number().int().min(1).max(100).default(1),
  preview: effectPackPreviewSchema,
}

export const effectPackManifestSchema = z.discriminatedUnion('domain', [
  z.object({
    ...sharedManifestShape,
    domain: z.literal('spectrum'),
    payload: z.object({
      templatePatch: spectrumTemplatePatchSchema,
    }),
  }),
  z.object({
    ...sharedManifestShape,
    domain: z.literal('background'),
    payload: z.object({
      templatePatch: backgroundTemplatePatchSchema,
    }),
  }),
  z.object({
    ...sharedManifestShape,
    domain: z.literal('logo'),
    payload: z.object({
      templatePatch: logoTemplatePatchSchema,
    }),
  }),
  z.object({
    ...sharedManifestShape,
    domain: z.literal('particles'),
    payload: z.object({
      templatePatch: particlesTemplatePatchSchema,
    }),
  }),
])

export type EffectPackManifest = z.infer<typeof effectPackManifestSchema>

export type EffectPackTemplateReference = {
  packId: string
  version: string
}

export type TemplateEffectPackMap = Partial<Record<EffectPackDomain, EffectPackTemplateReference | null>>

export type EffectPackCatalogStatus =
  | 'ready'
  | 'disabled'
  | 'incompatible'
  | 'broken'
  | 'missing'
  | 'available'

export type EffectPackCatalogItem = {
  packId: string
  version: string
  domain: EffectPackDomain
  name: string
  vendor: string
  description: string
  tags: string[]
  appVersionRange: string
  domainContractVersion: number
  manifestVersion: number
  enabled: boolean
  active: boolean
  status: EffectPackCatalogStatus
  installedAt: string
  sourceType: 'url' | 'file'
  sourceValue: string
  directoryPath: string
  preview: {
    title: string
    summary: string
    accentColor: string
  } | null
  templatePatch: Record<string, unknown>
  issues: string[]
}

export type EffectPackCatalogResponse = {
  items: EffectPackCatalogItem[]
}

export type EffectPackInstallResult = {
  ok: boolean
  item: EffectPackCatalogItem | null
  replacedVersion: string | null
  error?: string
}

export type EffectPackToggleResult = {
  ok: boolean
  item: EffectPackCatalogItem | null
  error?: string
}

export type EffectPackRemoveResult = {
  ok: boolean
  removed: boolean
  error?: string
}

export type EffectPackActivateResult = {
  ok: boolean
  item: EffectPackCatalogItem | null
  error?: string
}

export type EffectPackSelectionStatus = {
  domain: EffectPackDomain
  selection: EffectPackTemplateReference | null
  item: EffectPackCatalogItem | null
  status: EffectPackCatalogStatus
  message: string
}
