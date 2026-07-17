// @vitest-environment node

import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

import {
  installEffectPackFromFile,
  listEffectPackCatalog,
  removeEffectPack,
} from './effectPackRegistry'
import {
  effectPackManifestSchema,
  type EffectPackManifest,
} from '../shared/effectPacks/effectPackContracts'

function buildManifest(overrides?: Record<string, unknown>): EffectPackManifest {
  return effectPackManifestSchema.parse({
    manifestVersion: 1,
    packId: 'pack.spectrum.alpha',
    name: 'Spectrum Alpha',
    vendor: 'CAMXORA',
    version: '1.0.0',
    domain: 'spectrum',
    description: 'Pack for tests',
    tags: ['test'],
    appVersionRange: '^0.1.0',
    domainContractVersion: 1,
    preview: {
      title: 'Spectrum Alpha',
      summary: 'Test pack',
      accentColor: '#ff00ff',
    },
    payload: {
      templatePatch: {
        style: 'flying-glow',
        audioSettings: {
          inputGain: 2.5,
        },
      },
    },
    ...overrides,
  })
}

function buildExpandZip(
  manifest: EffectPackManifest,
  files: Record<string, string> = { 'marker.txt': 'marker' },
) {
  return async (_zipPath: string, destinationDir: string) => {
    const packRoot = path.join(destinationDir, 'pack')
    await fs.promises.mkdir(packRoot, { recursive: true })
    await fs.promises.writeFile(path.join(packRoot, 'manifest.json'), JSON.stringify(manifest, null, 2), 'utf8')
    await Promise.all(
      Object.entries(files).map(async ([relativePath, content]) => {
        const targetPath = path.join(packRoot, relativePath)
        await fs.promises.mkdir(path.dirname(targetPath), { recursive: true })
        await fs.promises.writeFile(targetPath, content, 'utf8')
      }),
    )
  }
}

describe('effectPackRegistry', () => {
  it('installs, lists, and removes a valid effect pack', async () => {
    const registryRoot = await fs.promises.mkdtemp(path.join(os.tmpdir(), 'camxora-effect-pack-registry-'))
    const zipPath = path.join(registryRoot, 'pack.zip')
    await fs.promises.writeFile(zipPath, 'zip', 'utf8')

    try {
      const installResult = await installEffectPackFromFile({
        registryRoot,
        appVersion: '0.1.0',
        zipPath,
        expandZip: buildExpandZip(buildManifest()),
      })

      expect(installResult.ok).toBe(true)
      expect(installResult.item).toMatchObject({
        packId: 'pack.spectrum.alpha',
        version: '1.0.0',
        status: 'ready',
      })

      const catalog = await listEffectPackCatalog({
        registryRoot,
        appVersion: '0.1.0',
      })
      expect(catalog.items).toHaveLength(1)
      expect(catalog.items[0]).toMatchObject({
        packId: 'pack.spectrum.alpha',
        status: 'ready',
      })

      const removeResult = await removeEffectPack({
        registryRoot,
        appVersion: '0.1.0',
        packId: 'pack.spectrum.alpha',
        version: '1.0.0',
      })
      expect(removeResult).toEqual({ ok: true, removed: true })

      const nextCatalog = await listEffectPackCatalog({
        registryRoot,
        appVersion: '0.1.0',
      })
      expect(nextCatalog.items).toEqual([])
    } finally {
      await fs.promises.rm(registryRoot, { recursive: true, force: true })
    }
  })

  it('rejects packs with unsupported domain contract versions', async () => {
    const registryRoot = await fs.promises.mkdtemp(path.join(os.tmpdir(), 'camxora-effect-pack-registry-'))
    const zipPath = path.join(registryRoot, 'pack.zip')
    await fs.promises.writeFile(zipPath, 'zip', 'utf8')

    try {
      const installResult = await installEffectPackFromFile({
        registryRoot,
        appVersion: '0.1.0',
        zipPath,
        expandZip: buildExpandZip(
          buildManifest({
            domainContractVersion: 2,
          }),
        ),
      })

      expect(installResult.ok).toBe(false)
      expect(installResult.error).toContain('is not supported')
    } finally {
      await fs.promises.rm(registryRoot, { recursive: true, force: true })
    }
  })

  it('reports missing local files as broken catalog items', async () => {
    const registryRoot = await fs.promises.mkdtemp(path.join(os.tmpdir(), 'camxora-effect-pack-registry-'))
    const zipPath = path.join(registryRoot, 'pack.zip')
    await fs.promises.writeFile(zipPath, 'zip', 'utf8')

    try {
      const installResult = await installEffectPackFromFile({
        registryRoot,
        appVersion: '0.1.0',
        zipPath,
        expandZip: buildExpandZip(buildManifest()),
      })
      expect(installResult.ok).toBe(true)

      await fs.promises.rm(installResult.item?.directoryPath ?? '', { recursive: true, force: true })

      const catalog = await listEffectPackCatalog({
        registryRoot,
        appVersion: '0.1.0',
      })
      expect(catalog.items[0]).toMatchObject({
        status: 'broken',
      })
      expect(catalog.items[0]?.issues[0]).toContain('missing')
    } finally {
      await fs.promises.rm(registryRoot, { recursive: true, force: true })
    }
  })

  it('rolls back the previous installed version contents when registry activation fails', async () => {
    const registryRoot = await fs.promises.mkdtemp(path.join(os.tmpdir(), 'camxora-effect-pack-registry-'))
    const zipPath = path.join(registryRoot, 'pack.zip')
    await fs.promises.writeFile(zipPath, 'zip', 'utf8')

    try {
      const initialInstall = await installEffectPackFromFile({
        registryRoot,
        appVersion: '0.1.0',
        zipPath,
        expandZip: buildExpandZip(buildManifest(), { 'marker.txt': 'old' }),
      })
      expect(initialInstall.ok).toBe(true)

      const originalWriteFile = fs.promises.writeFile.bind(fs.promises)
      const writeFileSpy = vi.spyOn(fs.promises, 'writeFile').mockImplementation(async (targetPath, data, options) => {
        if (String(targetPath).endsWith(`${path.sep}registry.json.tmp`)) {
          throw new Error('simulated registry write failure')
        }
        return originalWriteFile(targetPath, data, options as never)
      })

      const failedInstall = await installEffectPackFromFile({
        registryRoot,
        appVersion: '0.1.0',
        zipPath,
        expandZip: buildExpandZip(buildManifest(), { 'marker.txt': 'new' }),
      })

      writeFileSpy.mockRestore()

      expect(failedInstall.ok).toBe(false)
      expect(failedInstall.error).toContain('simulated registry write failure')

      const markerPath = path.join(
        registryRoot,
        'packs',
        'pack.spectrum.alpha',
        '1.0.0',
        'marker.txt',
      )
      expect(await fs.promises.readFile(markerPath, 'utf8')).toBe('old')
    } finally {
      await fs.promises.rm(registryRoot, { recursive: true, force: true })
    }
  })
})
