import { defineConfig } from 'astro/config'
import AstroPure from 'astro-pure'
import config from './src/site.config'

export default defineConfig({
  site: 'https://lihaoze-bob.github.io',
  base: '/',
  output: 'static',
  trailingSlash: 'always',
  publicDir: process.env.ASTRO_PUBLIC_DIR || './.runtime/astro-public',
  outDir: process.env.ASTRO_OUT_DIR || './site',
  integrations: [AstroPure(config)],
  prefetch: false
})
