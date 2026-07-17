import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

function collectSourceFiles(rootDir: string): string[] {
  return [
    path.join(rootDir, 'useEffectPackManager.ts'),
    path.join(rootDir, 'effectPackDraftState.ts'),
    path.join(rootDir, 'EffectPackSelectorCard.tsx'),
  ]
}

describe('effect pack workspace boundary', () => {
  it('keeps pack workspace seams off direct video domain imports', () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url))
    const offenders = collectSourceFiles(currentDir)
      .filter((filePath) => readFileSync(filePath, 'utf8').includes("/features/video/domains/"))
      .map((filePath) => path.basename(filePath))

    expect(offenders).toEqual([])
  })
})
