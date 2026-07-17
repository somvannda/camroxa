import { readdirSync, readFileSync } from 'node:fs'
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

describe('preview runtime boundary', () => {
  it('keeps deleted GPU compatibility adapters out of preview source imports', () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url))
    const previewRoot = currentDir

    const offenders = collectSourceFiles(previewRoot)
      .filter((filePath) => path.basename(filePath) !== 'previewRuntimeBoundary.test.ts')
      .filter((filePath) => readFileSync(filePath, 'utf8').includes('previewGpuFrameRenderer'))
      .map((filePath) => path.relative(previewRoot, filePath).replace(/\\/g, '/'))

    expect(offenders).toEqual([])
  })
})
