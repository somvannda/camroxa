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

describe('scene boundary', () => {
  it('keeps preview runtime consumers from reading scene.draft directly', () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url))
    const previewRoot = path.resolve(currentDir, '..', '..', 'preview')

    const offenders = collectSourceFiles(previewRoot)
      .filter((filePath) => path.basename(filePath) !== 'previewScene.ts')
      .filter((filePath) => readFileSync(filePath, 'utf8').includes('scene.draft'))
      .map((filePath) => path.relative(previewRoot, filePath).replace(/\\/g, '/'))

    expect(offenders).toEqual([])
  })

  it('keeps domain source files from importing sibling domain internals', () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url))
    const domainsRoot = path.resolve(currentDir, '..', '..', 'domains')
    const domainImportPattern = /from ['"]@\/features\/video\/domains\/([^/'"]+)\/([^'"]+)['"]/g

    const offenders = collectSourceFiles(domainsRoot)
      .flatMap((filePath) => {
        const domainName = path.relative(domainsRoot, filePath).split(path.sep)[0]
        const source = readFileSync(filePath, 'utf8')
        const matches = [...source.matchAll(domainImportPattern)]
        return matches
          .filter((match) => {
            const importedDomain = match[1]
            return importedDomain !== 'shared' && importedDomain !== domainName
          })
          .map((match) =>
            `${path.relative(domainsRoot, filePath).replace(/\\/g, '/')} -> ${match[1]}/${match[2]}`,
          )
      })

    expect(offenders).toEqual([])
  })
})
