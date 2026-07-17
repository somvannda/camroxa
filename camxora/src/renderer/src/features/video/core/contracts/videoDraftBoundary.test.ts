import { readdirSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

function collectSourceFiles(rootPath: string): string[] {
  const entries = readdirSync(rootPath, { withFileTypes: true })
  return entries.flatMap((entry) => {
    const entryPath = path.join(rootPath, entry.name)
    if (entry.isDirectory()) {
      if (entry.name === 'workspace') {
        return []
      }
      return collectSourceFiles(entryPath)
    }

    if (!/\.(ts|tsx)$/.test(entry.name) || /\.test\.(ts|tsx)$/.test(entry.name)) {
      return []
    }

    return [entryPath]
  })
}

describe('video draft boundary', () => {
  it('keeps settingsTemplateDraft imports out of non-workspace video source files', () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url))
    const videoRoot = path.resolve(currentDir, '..', '..')
    const importPattern = /from\s+['"][^'"]*settingsTemplateDraft['"]/

    const offenders = collectSourceFiles(videoRoot)
      .filter((filePath) => importPattern.test(readFileSync(filePath, 'utf8')))
      .map((filePath) => path.relative(videoRoot, filePath).replace(/\\/g, '/'))

    expect(offenders).toEqual([])
  })
})
