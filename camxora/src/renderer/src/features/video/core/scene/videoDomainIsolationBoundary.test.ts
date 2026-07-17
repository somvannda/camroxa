import { readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

function collectSourceFiles(rootPath: string): string[] {
  const entries = readdirSync(rootPath, { withFileTypes: true })
  return entries.flatMap((entry) => {
    const entryPath = path.join(rootPath, entry.name)
    if (entry.isDirectory()) {
      return collectSourceFiles(entryPath)
    }

    if (!/\.(ts|tsx)$/.test(entry.name) || /\.test\.(ts|tsx)$/.test(entry.name)) {
      return []
    }

    return [entryPath]
  })
}

describe('video domain isolation boundary', () => {
  it('keeps production video sources off legacy composition and particle adapter paths', () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url))
    const videoRoot = path.resolve(currentDir, '..', '..')
    const allowedCompatFiles = new Set([
      'core/scene/sceneGraphComposer.ts',
      'preview/particleAdapter.ts',
      'preview/spectrumAdapter.ts',
    ])

    const offenders = collectSourceFiles(videoRoot)
      .filter((filePath) => !allowedCompatFiles.has(path.relative(videoRoot, filePath).replace(/\\/g, '/')))
      .filter((filePath) => {
        const source = readFileSync(filePath, 'utf8')
        return (
          source.includes("from '@/features/video/core/scene/sceneGraphComposer'") ||
          source.includes("from '@/features/video/preview/particleAdapter'") ||
          source.includes("from '@/features/video/preview/spectrumAdapter'")
        )
      })
      .map((filePath) => path.relative(videoRoot, filePath).replace(/\\/g, '/'))

    expect(offenders).toEqual([])
  })

  it('keeps background, logo, and particle editors off settings-owned helpers', () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url))
    const workspaceRoot = path.resolve(currentDir, '..', '..', 'workspace')
    const files = [
      'useBackgroundEditor.ts',
      'useLogoEditor.ts',
      'useParticlesEditor.ts',
      'BackgroundInspector.tsx',
      'LogoInspector.tsx',
      'ParticlesInspector.tsx',
    ]

    const offenders = files
      .filter((relativePath) => {
        const source = readFileSync(path.join(workspaceRoot, relativePath), 'utf8')
        return (
          source.includes("@/features/settings/settingsTemplateDraft") ||
          source.includes("@/features/settings/pythonVideoSettings")
        )
      })
      .map((relativePath) => `workspace/${relativePath}`)

    expect(offenders).toEqual([])
  })
})
