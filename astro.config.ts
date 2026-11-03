import { defineConfig } from 'astro/config'
import AstroPure from 'astro-pure'
import config from './src/site.config'
import * as pagefind from 'pagefind'
import { fileURLToPath } from 'node:url'

export default defineConfig({
  site: 'https://lihaoze-bob.github.io',
  base: '/',
  output: 'static',
  trailingSlash: 'always',
  publicDir: process.env.ASTRO_PUBLIC_DIR || './.runtime/astro-public',
  outDir: process.env.ASTRO_OUT_DIR || './site',
  integrations: [
    AstroPure({ ...config, integ: { ...config.integ, pagefind: false } }),
    {
      name: 'notes-search-index',
      hooks: {
        'astro:build:done': async ({ dir }) => {
          // UI is English; the mixed-language notes still require Chinese segmentation.
          try {
            const { index, errors } = await pagefind.createIndex({ forceLanguage: 'zh' })
            if (!index || errors.length) throw new Error(errors.join('; ') || 'Could not create search index')
            const indexed = await index.addDirectory({ path: fileURLToPath(dir) })
            if (indexed.errors.length) throw new Error(indexed.errors.join('; '))
            const written = await index.writeFiles({ outputPath: fileURLToPath(new URL('./pagefind/', dir)) })
            if (written.errors.length) throw new Error(written.errors.join('; '))
          } finally {
            await pagefind.close()
          }
        }
      }
    }
  ],
  prefetch: false
})
