import { effectPackManifestSchema } from './effectPackContracts'

describe('effectPackContracts', () => {
  it('parses manifests for every supported domain payload', () => {
    expect(
      effectPackManifestSchema.parse({
        manifestVersion: 1,
        packId: 'pack.spectrum.alpha',
        name: 'Spectrum Alpha',
        vendor: 'CAMXORA',
        version: '1.0.0',
        domain: 'spectrum',
        appVersionRange: '^0.1.0',
        domainContractVersion: 1,
        payload: {
          templatePatch: {
            style: 'flying-glow',
            layers: [],
          },
        },
      }),
    ).toMatchObject({ domain: 'spectrum' })

    expect(
      effectPackManifestSchema.parse({
        manifestVersion: 1,
        packId: 'pack.background.alpha',
        name: 'Background Alpha',
        vendor: 'CAMXORA',
        version: '1.0.0',
        domain: 'background',
        appVersionRange: '^0.1.0',
        domainContractVersion: 1,
        payload: {
          templatePatch: {
            backgroundSettings: {
              fitMode: 'cover',
            },
          },
        },
      }),
    ).toMatchObject({ domain: 'background' })

    expect(
      effectPackManifestSchema.parse({
        manifestVersion: 1,
        packId: 'pack.logo.alpha',
        name: 'Logo Alpha',
        vendor: 'CAMXORA',
        version: '1.0.0',
        domain: 'logo',
        appVersionRange: '^0.1.0',
        domainContractVersion: 1,
        payload: {
          templatePatch: {
            logoSettings: {
              enabled: true,
            },
          },
        },
      }),
    ).toMatchObject({ domain: 'logo' })

    expect(
      effectPackManifestSchema.parse({
        manifestVersion: 1,
        packId: 'pack.particles.alpha',
        name: 'Particles Alpha',
        vendor: 'CAMXORA',
        version: '1.0.0',
        domain: 'particles',
        appVersionRange: '^0.1.0',
        domainContractVersion: 1,
        payload: {
          templatePatch: {
            particlesSettings: {
              enabled: true,
            },
          },
        },
      }),
    ).toMatchObject({ domain: 'particles' })
  })

  it('rejects unknown payload keys inside strict domain payload contracts', () => {
    expect(() =>
      effectPackManifestSchema.parse({
        manifestVersion: 1,
        packId: 'pack.logo.alpha',
        name: 'Logo Alpha',
        vendor: 'CAMXORA',
        version: '1.0.0',
        domain: 'logo',
        appVersionRange: '^0.1.0',
        domainContractVersion: 1,
        payload: {
          templatePatch: {
            logoSettings: {
              enabled: true,
            },
            invalid: true,
          },
        },
      }),
    ).toThrow()
  })
})
