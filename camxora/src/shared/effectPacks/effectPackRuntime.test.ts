import {
  buildEffectPackCatalogOptions,
  buildTemplateEffectPackApplyPatch,
  buildTemplateEffectPackReferencePatch,
  parseEffectPackCatalogValue,
  readTemplateEffectPackMap,
  resolveEffectPackSelectionStatus,
} from './effectPackRuntime'
import type { EffectPackCatalogItem } from './effectPackContracts'

function buildCatalogItem(overrides?: Partial<EffectPackCatalogItem>): EffectPackCatalogItem {
  return {
    packId: 'pack.spectrum.alpha',
    version: '1.0.0',
    domain: 'spectrum',
    name: 'Spectrum Alpha',
    vendor: 'CAMXORA',
    description: '',
    tags: [],
    appVersionRange: '^0.1.0',
    domainContractVersion: 1,
    manifestVersion: 1,
    enabled: true,
    active: true,
    status: 'ready',
    installedAt: '2026-07-04T00:00:00.000Z',
    sourceType: 'file',
    sourceValue: 'D:/packs/spectrum-alpha.zip',
    directoryPath: 'D:/packs/spectrum-alpha',
    preview: null,
    templatePatch: {
      style: 'flying-glow',
      audioSettings: {
        inputGain: 3.2,
      },
    },
    issues: [],
    ...overrides,
  }
}

describe('effectPackRuntime', () => {
  it('reads persisted pack references from template state', () => {
    expect(
      readTemplateEffectPackMap({
        effectPacks: {
          spectrum: {
            packId: 'pack.spectrum.alpha',
            version: '1.0.0',
          },
          logo: {
            packId: 'pack.logo.beta',
            version: '2.1.0',
          },
        },
      }),
    ).toEqual({
      spectrum: {
        packId: 'pack.spectrum.alpha',
        version: '1.0.0',
      },
      logo: {
        packId: 'pack.logo.beta',
        version: '2.1.0',
      },
    })
  })

  it('builds a merged template patch containing both the reference and domain payload', () => {
    expect(
      buildTemplateEffectPackApplyPatch('spectrum', buildCatalogItem()),
    ).toEqual({
      effectPacks: {
        spectrum: {
          packId: 'pack.spectrum.alpha',
          version: '1.0.0',
        },
      },
      style: 'flying-glow',
      audioSettings: {
        inputGain: 3.2,
      },
    })
  })

  it('resolves selection status for ready, disabled, and missing packs', () => {
    const readyItem = buildCatalogItem()
    const disabledItem = buildCatalogItem({
      enabled: false,
      status: 'disabled',
      issues: ['Pack is disabled.'],
    })

    expect(
      resolveEffectPackSelectionStatus(
        'spectrum',
        { packId: readyItem.packId, version: readyItem.version },
        [readyItem],
      ),
    ).toMatchObject({
      status: 'ready',
      item: readyItem,
    })

    expect(
      resolveEffectPackSelectionStatus(
        'spectrum',
        { packId: disabledItem.packId, version: disabledItem.version },
        [disabledItem],
      ),
    ).toMatchObject({
      status: 'disabled',
      message: 'Pack is disabled.',
    })

    expect(
      resolveEffectPackSelectionStatus(
        'spectrum',
        { packId: 'missing.pack', version: '9.9.9' },
        [readyItem],
      ),
    ).toMatchObject({
      status: 'missing',
    })
  })

  it('filters selectable catalog options to ready or available items only', () => {
    const items: EffectPackCatalogItem[] = [
      buildCatalogItem(),
      buildCatalogItem({
        packId: 'pack.spectrum.beta',
        version: '1.1.0',
        status: 'available',
        active: false,
      }),
      buildCatalogItem({
        packId: 'pack.spectrum.disabled',
        version: '1.2.0',
        status: 'disabled',
        enabled: false,
      }),
    ]

    expect(buildEffectPackCatalogOptions('spectrum', items)).toEqual([
      { value: 'pack.spectrum.alpha::1.0.0', label: 'Spectrum Alpha (1.0.0)' },
      { value: 'pack.spectrum.beta::1.1.0', label: 'Spectrum Alpha (1.1.0)' },
    ])
    expect(parseEffectPackCatalogValue('pack.spectrum.alpha::1.0.0')).toEqual({
      packId: 'pack.spectrum.alpha',
      version: '1.0.0',
    })
    expect(buildTemplateEffectPackReferencePatch('background', null)).toEqual({
      effectPacks: {
        background: null,
      },
    })
  })
})
