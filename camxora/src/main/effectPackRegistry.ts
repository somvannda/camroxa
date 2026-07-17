import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

import {
  EFFECT_PACK_DOMAIN_CONTRACT_VERSIONS,
  effectPackManifestSchema,
  type EffectPackCatalogItem,
  type EffectPackCatalogResponse,
  type EffectPackInstallResult,
  type EffectPackActivateResult,
  type EffectPackRemoveResult,
  type EffectPackToggleResult,
  type EffectPackManifest,
} from '../shared/effectPacks/effectPackContracts'
import { matchesAppVersionRange } from '../shared/effectPacks/effectPackVersioning'

type EffectPackSourceType = 'url' | 'file'

type EffectPackRegistryVersionRecord = {
  version: string
  relativeDir: string
  installedAt: string
  sourceType: EffectPackSourceType
  sourceValue: string
  manifest: EffectPackManifest
}

type EffectPackRegistryRecord = {
  packId: string
  enabled: boolean
  activeVersion: string
  previousVersion: string | null
  versions: Record<string, EffectPackRegistryVersionRecord>
}

type EffectPackRegistryData = {
  packs: Record<string, EffectPackRegistryRecord>
}

type InstallEffectPackOptions = {
  registryRoot: string
  appVersion: string
  zipPath?: string
  url?: string
  sourceType: EffectPackSourceType
  sourceValue: string
  downloadToFile?: (targetUrl: string, targetPath: string) => Promise<void>
  expandZip: (zipPath: string, destinationDir: string) => Promise<void>
}

type EffectPackRegistryOptions = {
  registryRoot: string
  appVersion: string
}

function createEmptyRegistry(): EffectPackRegistryData {
  return { packs: {} }
}

function getRegistryFilePath(registryRoot: string): string {
  return path.join(registryRoot, 'registry.json')
}

function getPacksRoot(registryRoot: string): string {
  return path.join(registryRoot, 'packs')
}

async function ensureRegistryLayout(registryRoot: string): Promise<void> {
  await fs.promises.mkdir(getPacksRoot(registryRoot), { recursive: true })
}

async function readRegistry(registryRoot: string): Promise<EffectPackRegistryData> {
  await ensureRegistryLayout(registryRoot)
  const registryPath = getRegistryFilePath(registryRoot)
  try {
    const raw = await fs.promises.readFile(registryPath, 'utf8')
    const parsed = JSON.parse(raw) as EffectPackRegistryData
    if (!parsed || typeof parsed !== 'object' || typeof parsed.packs !== 'object') {
      return createEmptyRegistry()
    }
    return parsed
  } catch {
    return createEmptyRegistry()
  }
}

async function writeRegistry(registryRoot: string, registry: EffectPackRegistryData): Promise<void> {
  await ensureRegistryLayout(registryRoot)
  const registryPath = getRegistryFilePath(registryRoot)
  const tempPath = `${registryPath}.tmp`
  await fs.promises.writeFile(tempPath, JSON.stringify(registry, null, 2), 'utf8')
  await fs.promises.rename(tempPath, registryPath)
}

async function listFilesRecursive(baseDir: string): Promise<string[]> {
  const results: string[] = []
  const stack = [baseDir]
  while (stack.length) {
    const current = stack.pop()
    if (!current) {
      continue
    }
    const entries = await fs.promises.readdir(current, { withFileTypes: true })
    for (const entry of entries) {
      const nextPath = path.join(current, entry.name)
      if (entry.isDirectory()) {
        stack.push(nextPath)
        continue
      }
      if (entry.isFile()) {
        results.push(nextPath)
      }
    }
  }
  return results
}

async function findManifestPath(extractDir: string): Promise<string> {
  const files = await listFilesRecursive(extractDir)
  const manifests = files.filter((filePath) => path.basename(filePath).toLowerCase() === 'manifest.json')
  if (manifests.length !== 1) {
    throw new Error('Effect pack zip must contain exactly one manifest.json file.')
  }
  return manifests[0]
}

async function readManifestFromPath(manifestPath: string): Promise<EffectPackManifest> {
  const raw = await fs.promises.readFile(manifestPath, 'utf8')
  return effectPackManifestSchema.parse(JSON.parse(raw))
}

function validateManifestCompatibility(manifest: EffectPackManifest): string | null {
  const supportedDomainVersion = EFFECT_PACK_DOMAIN_CONTRACT_VERSIONS[manifest.domain]
  if (manifest.domainContractVersion !== supportedDomainVersion) {
    return `${manifest.domain} pack contract ${manifest.domainContractVersion} is not supported; expected ${supportedDomainVersion}.`
  }
  return null
}

function buildCatalogItem(
  record: EffectPackRegistryRecord,
  versionRecord: EffectPackRegistryVersionRecord,
  options: { appVersion: string; registryRoot: string; issues?: string[] },
): EffectPackCatalogItem {
  const issues = [...(options.issues ?? [])]
  const compatible = matchesAppVersionRange(options.appVersion, versionRecord.manifest.appVersionRange)
  const targetDir = path.resolve(getPacksRoot(options.registryRoot), versionRecord.relativeDir)

  let status: EffectPackCatalogItem['status'] = 'available'
  if (issues.length) {
    status = 'broken'
  } else if (!record.enabled) {
    status = 'disabled'
    issues.push('Pack is disabled.')
  } else if (!compatible) {
    status = 'incompatible'
    issues.push(
      `Pack requires app version ${versionRecord.manifest.appVersionRange}, current app is ${options.appVersion}.`,
    )
  } else if (record.activeVersion === versionRecord.version) {
    status = 'ready'
  }

  return {
    packId: record.packId,
    version: versionRecord.version,
    domain: versionRecord.manifest.domain,
    name: versionRecord.manifest.name,
    vendor: versionRecord.manifest.vendor,
    description: versionRecord.manifest.description ?? '',
    tags: versionRecord.manifest.tags ?? [],
    appVersionRange: versionRecord.manifest.appVersionRange,
    domainContractVersion: versionRecord.manifest.domainContractVersion,
    manifestVersion: versionRecord.manifest.manifestVersion,
    enabled: record.enabled,
    active: record.activeVersion === versionRecord.version,
    status,
    installedAt: versionRecord.installedAt,
    sourceType: versionRecord.sourceType,
    sourceValue: versionRecord.sourceValue,
    directoryPath: targetDir,
    preview: versionRecord.manifest.preview
      ? {
          title: versionRecord.manifest.preview.title ?? versionRecord.manifest.name,
          summary: versionRecord.manifest.preview.summary ?? versionRecord.manifest.description ?? '',
          accentColor: versionRecord.manifest.preview.accentColor ?? '',
        }
      : null,
    templatePatch: versionRecord.manifest.payload.templatePatch as Record<string, unknown>,
    issues,
  }
}

async function buildCatalog(options: EffectPackRegistryOptions): Promise<EffectPackCatalogResponse> {
  const registry = await readRegistry(options.registryRoot)
  const items: EffectPackCatalogItem[] = []
  for (const record of Object.values(registry.packs)) {
    for (const versionRecord of Object.values(record.versions)) {
      const relativeDir = versionRecord.relativeDir
      const targetDir = path.resolve(getPacksRoot(options.registryRoot), relativeDir)
      const issues: string[] = []
      try {
        const stat = await fs.promises.stat(targetDir)
        if (!stat.isDirectory()) {
          issues.push('Pack files are missing from local storage.')
        }
      } catch {
        issues.push('Pack files are missing from local storage.')
      }
      const compatibilityError = validateManifestCompatibility(versionRecord.manifest)
      if (compatibilityError) {
        issues.push(compatibilityError)
      }
      items.push(buildCatalogItem(record, versionRecord, { ...options, issues }))
    }
  }
  items.sort((left, right) =>
    `${left.domain}:${left.name}:${left.version}`.localeCompare(`${right.domain}:${right.name}:${right.version}`),
  )
  return { items }
}

export async function listEffectPackCatalog(options: EffectPackRegistryOptions): Promise<EffectPackCatalogResponse> {
  return buildCatalog(options)
}

function resolveSourceZipPath(options: InstallEffectPackOptions, stagingDir: string): string {
  if (options.zipPath) {
    return path.resolve(options.zipPath)
  }
  return path.join(stagingDir, 'download.zip')
}

async function moveDirectoryIfPresent(sourceDir: string, targetDir: string): Promise<boolean> {
  try {
    const stat = await fs.promises.stat(sourceDir)
    if (!stat.isDirectory()) {
      return false
    }
  } catch {
    return false
  }
  await fs.promises.mkdir(path.dirname(targetDir), { recursive: true })
  await fs.promises.rm(targetDir, { recursive: true, force: true })
  await fs.promises.rename(sourceDir, targetDir)
  return true
}

async function installPack(options: InstallEffectPackOptions): Promise<EffectPackInstallResult> {
  await ensureRegistryLayout(options.registryRoot)
  const stagingDir = await fs.promises.mkdtemp(path.join(os.tmpdir(), 'camxora-effect-pack-'))
  const extractDir = path.join(stagingDir, 'extract')
  const targetZipPath = resolveSourceZipPath(options, stagingDir)

  try {
    if (options.url) {
      if (!options.downloadToFile) {
        throw new Error('Download helper is unavailable.')
      }
      await options.downloadToFile(options.url, targetZipPath)
    } else {
      const zipStat = await fs.promises.stat(targetZipPath)
      if (!zipStat.isFile()) {
        throw new Error('Selected effect pack file is not valid.')
      }
    }

    await fs.promises.mkdir(extractDir, { recursive: true })
    await options.expandZip(targetZipPath, extractDir)
    const manifestPath = await findManifestPath(extractDir)
    const manifest = await readManifestFromPath(manifestPath)
    const manifestCompatibilityError = validateManifestCompatibility(manifest)
    if (manifestCompatibilityError) {
      return {
        ok: false,
        item: null,
        replacedVersion: null,
        error: manifestCompatibilityError,
      }
    }

    if (!matchesAppVersionRange(options.appVersion, manifest.appVersionRange)) {
      return {
        ok: false,
        item: null,
        replacedVersion: null,
        error: `Pack requires app version ${manifest.appVersionRange}, current app is ${options.appVersion}.`,
      }
    }

    const contentRoot = path.dirname(manifestPath)
    const versionDir = path.join(manifest.packId, manifest.version)
    const targetDir = path.resolve(getPacksRoot(options.registryRoot), versionDir)
    const backupDir = path.join(stagingDir, 'backup')
    const hadExistingTarget = await moveDirectoryIfPresent(targetDir, backupDir)
    let replacedVersion: string | null = null
    await fs.promises.mkdir(path.dirname(targetDir), { recursive: true })
    await fs.promises.cp(contentRoot, targetDir, { recursive: true, force: true })

    try {
      const registry = await readRegistry(options.registryRoot)
      const existing = registry.packs[manifest.packId]
      replacedVersion =
        existing && existing.activeVersion && existing.activeVersion !== manifest.version ? existing.activeVersion : null
      const nextRecord: EffectPackRegistryRecord = existing
        ? {
            ...existing,
            enabled: true,
            activeVersion: manifest.version,
            previousVersion: replacedVersion ?? existing.previousVersion,
            versions: {
              ...existing.versions,
              [manifest.version]: {
                version: manifest.version,
                relativeDir: versionDir,
                installedAt: new Date().toISOString(),
                sourceType: options.sourceType,
                sourceValue: options.sourceValue,
                manifest,
              },
            },
          }
        : {
            packId: manifest.packId,
            enabled: true,
            activeVersion: manifest.version,
            previousVersion: null,
            versions: {
              [manifest.version]: {
                version: manifest.version,
                relativeDir: versionDir,
                installedAt: new Date().toISOString(),
                sourceType: options.sourceType,
                sourceValue: options.sourceValue,
                manifest,
              },
            },
          }
      registry.packs[manifest.packId] = nextRecord
      await writeRegistry(options.registryRoot, registry)
    } catch (error) {
      await fs.promises.rm(targetDir, { recursive: true, force: true })
      if (hadExistingTarget) {
        await moveDirectoryIfPresent(backupDir, targetDir)
      }
      throw error
    }

    if (hadExistingTarget) {
      await fs.promises.rm(backupDir, { recursive: true, force: true })
    }
    const catalog = await buildCatalog(options)
    const item =
      catalog.items.find((entry) => entry.packId === manifest.packId && entry.version === manifest.version) ?? null

    return {
      ok: true,
      item,
      replacedVersion,
    }
  } catch (error) {
    return {
      ok: false,
      item: null,
      replacedVersion: null,
      error: error instanceof Error ? error.message : 'Unable to install effect pack.',
    }
  } finally {
    try {
      await fs.promises.rm(stagingDir, { recursive: true, force: true })
    } catch {
      // ignore cleanup failures
    }
  }
}

export async function installEffectPackFromFile(
  options: Omit<InstallEffectPackOptions, 'sourceType' | 'sourceValue'> & { zipPath: string },
): Promise<EffectPackInstallResult> {
  return installPack({
    ...options,
    sourceType: 'file',
    sourceValue: path.resolve(options.zipPath),
  })
}

export async function installEffectPackFromUrl(
  options: Omit<InstallEffectPackOptions, 'sourceType' | 'sourceValue'> & { url: string },
): Promise<EffectPackInstallResult> {
  return installPack({
    ...options,
    sourceType: 'url',
    sourceValue: options.url,
  })
}

export async function setEffectPackEnabled(
  options: EffectPackRegistryOptions & { packId: string; enabled: boolean },
): Promise<EffectPackToggleResult> {
  const registry = await readRegistry(options.registryRoot)
  const record = registry.packs[options.packId]
  if (!record) {
    return { ok: false, item: null, error: 'Effect pack is not installed.' }
  }
  record.enabled = options.enabled
  registry.packs[options.packId] = record
  await writeRegistry(options.registryRoot, registry)
  const catalog = await buildCatalog(options)
  const item = catalog.items.find((entry) => entry.packId === options.packId && entry.active) ?? null
  return { ok: true, item }
}

export async function activateEffectPackVersion(
  options: EffectPackRegistryOptions & { packId: string; version: string },
): Promise<EffectPackActivateResult> {
  const registry = await readRegistry(options.registryRoot)
  const record = registry.packs[options.packId]
  if (!record) {
    return { ok: false, item: null, error: 'Effect pack is not installed.' }
  }
  if (!record.versions[options.version]) {
    return { ok: false, item: null, error: 'Requested effect pack version is not installed.' }
  }
  const versionRecord = record.versions[options.version]
  if (!matchesAppVersionRange(options.appVersion, versionRecord.manifest.appVersionRange)) {
    return { ok: false, item: null, error: 'Requested effect pack version is not compatible with this app.' }
  }
  record.previousVersion = record.activeVersion === options.version ? record.previousVersion : record.activeVersion
  record.activeVersion = options.version
  record.enabled = true
  registry.packs[options.packId] = record
  await writeRegistry(options.registryRoot, registry)
  const catalog = await buildCatalog(options)
  const item =
    catalog.items.find((entry) => entry.packId === options.packId && entry.version === options.version) ?? null
  return { ok: true, item }
}

export async function removeEffectPack(
  options: EffectPackRegistryOptions & { packId: string; version: string },
): Promise<EffectPackRemoveResult> {
  const registry = await readRegistry(options.registryRoot)
  const record = registry.packs[options.packId]
  if (!record || !record.versions[options.version]) {
    return { ok: false, removed: false, error: 'Effect pack version is not installed.' }
  }

  const versionRecord = record.versions[options.version]
  const targetDir = path.resolve(getPacksRoot(options.registryRoot), versionRecord.relativeDir)
  await fs.promises.rm(targetDir, { recursive: true, force: true })
  delete record.versions[options.version]

  const remainingVersions = Object.keys(record.versions)
  if (!remainingVersions.length) {
    delete registry.packs[options.packId]
  } else {
    if (record.activeVersion === options.version) {
      record.activeVersion =
        (record.previousVersion && record.versions[record.previousVersion] && record.previousVersion) ||
        remainingVersions.sort().at(-1) ||
        remainingVersions[0]
      record.previousVersion = null
    } else if (record.previousVersion === options.version) {
      record.previousVersion = null
    }
    registry.packs[options.packId] = record
  }

  await writeRegistry(options.registryRoot, registry)
  return { ok: true, removed: true }
}
