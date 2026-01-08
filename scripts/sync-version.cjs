const fs = require('fs')
const path = require('path')

const rootDir = path.resolve(__dirname, '..')
const rootPackagePath = path.join(rootDir, 'package.json')
const frontPackagePath = path.join(rootDir, 'front', 'package.json')

const rootPackage = JSON.parse(fs.readFileSync(rootPackagePath, 'utf8'))
const frontPackage = JSON.parse(fs.readFileSync(frontPackagePath, 'utf8'))

if (!rootPackage.version) {
  console.error('[sync-version] Missing version in root package.json')
  process.exit(1)
}

if (frontPackage.version !== rootPackage.version) {
  frontPackage.version = rootPackage.version
  fs.writeFileSync(frontPackagePath, `${JSON.stringify(frontPackage, null, 2)}\n`, 'utf8')
  console.log(`[sync-version] Updated front/package.json to ${rootPackage.version}`)
} else {
  console.log(`[sync-version] front/package.json already at ${rootPackage.version}`)
}
