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

describe('spectrum domain boundary', () => {
  it('keeps production video sources off the legacy preview spectrum adapter import path', () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url))
    const videoRoot = path.resolve(currentDir, '..', '..')

    const offenders = collectSourceFiles(videoRoot)
      .filter((filePath) => path.relative(videoRoot, filePath).replace(/\\/g, '/') !== 'preview/spectrumAdapter.ts')
      .filter((filePath) =>
        readFileSync(filePath, 'utf8').includes("from '@/features/video/preview/spectrumAdapter'"),
      )
      .map((filePath) => path.relative(videoRoot, filePath).replace(/\\/g, '/'))

    expect(offenders).toEqual([])
  })

  it('keeps the spectrum workspace editor off settings-owned spectrum helpers', () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url))
    const workspaceRoot = path.resolve(currentDir, '..', '..', 'workspace')
    const useSpectrumEditorPath = path.join(workspaceRoot, 'useSpectrumEditor.ts')
    const spectrumInspectorPath = path.join(workspaceRoot, 'SpectrumInspector.tsx')

    const editorSource = readFileSync(useSpectrumEditorPath, 'utf8')
    const inspectorSource = readFileSync(spectrumInspectorPath, 'utf8')

    expect(editorSource).not.toContain("@/features/settings/settingsTemplateDraft")
    expect(editorSource).not.toContain("@/features/settings/pythonVideoSettings")
    expect(inspectorSource).not.toMatch(
      /SPECTRUM_PRESET_OPTIONS[\s\S]*@\/features\/settings\/pythonVideoSettings/,
    )
  })
})
