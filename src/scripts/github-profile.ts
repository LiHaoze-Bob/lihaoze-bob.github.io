import { parseGitHubActivity, formatActivityUpdatedAt } from '../lib/github-profile.mjs'

export async function setupGitHubProfile(root: HTMLElement) {
  root.querySelectorAll<HTMLElement>('[data-profile-image]').forEach(container => {
    const img = container.querySelector<HTMLImageElement>('img')!
    const fallback = container.querySelector<HTMLElement>('.image-fallback')!
    let imageTimeout: ReturnType<typeof setTimeout> | undefined
    const unavailable = () => { clearTimeout(imageTimeout); img.hidden = true; fallback.hidden = false }
    const available = () => { clearTimeout(imageTimeout); img.hidden = false; fallback.hidden = true }
    img.addEventListener('error', unavailable, { once: true })
    img.addEventListener('load', available, { once: true })
    if (img.complete) {
      if (!img.naturalWidth) unavailable()
    } else {
      imageTimeout = setTimeout(unavailable, 8000)
    }
  })
  const status = root.querySelector<HTMLElement>('[data-github-refresh]')!
  status.textContent = 'Checking GitHub for updates…'
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 8000)
  try {
    const response = await fetch('https://raw.githubusercontent.com/LiHaoze-Bob/LiHaoze-Bob/main/README.md', {
      signal: controller.signal, credentials: 'omit', cache: 'no-store'
    })
    if (!response.ok) throw new Error('Profile is unavailable')
    const report = parseGitHubActivity(await response.text())
    root.querySelector<HTMLElement>('[data-github-obsidian]')!.textContent = report.obsidian.replace(/^Time @Obsidian · /, '')
    root.querySelector<HTMLElement>('[data-github-weekly]')!.textContent = report.weekly
    root.querySelector<HTMLElement>('[data-github-updated]')!.textContent = report.sourceUpdatedAt
      ? formatActivityUpdatedAt(report.sourceUpdatedAt)
      : `Reporting period ${report.periodStart} – ${report.periodEnd} (Asia/Shanghai); update time unavailable`
    root.querySelector<HTMLElement>('[data-github-snapshot]')!.hidden = true
    status.textContent = ''
  } catch {
    status.textContent = 'GitHub update unavailable; showing the saved snapshot.'
  } finally {
    clearTimeout(timeout)
  }
}
