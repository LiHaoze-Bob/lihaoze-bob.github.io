(() => {
  const card = document.querySelector('.about-steam')
  if (!card?.dataset.steamEndpoint || card.dataset.steamStarted) return
  let endpoint
  try {
    endpoint = new URL(card.dataset.steamEndpoint)
    if (endpoint.protocol !== 'https:' || endpoint.username || endpoint.password) return
  } catch { return }
  card.dataset.steamStarted = 'true'

  const english = card.dataset.uiLang === 'en'
  const ui = (en, zh) => english ? en : zh
  const labels = english ? { offline: 'Offline', online: 'Online', 'in-game': 'In game', away: 'Away',
    busy: 'Busy', snooze: 'Snooze', trade: 'Looking to trade', play: 'Looking to play', unknown: 'Status is private' } : { offline: '离线', online: '在线', 'in-game': '游戏中', away: '离开',
    busy: '忙碌', snooze: '睡眠', trade: '想要交易', play: '想要玩游戏', unknown: '状态未公开' }
  const query = selector => card.querySelector(selector)
  const message = query('.steam-refresh')
  const status = query('.steam-status')
  const formatter = new Intl.DateTimeFormat(english ? 'en-GB' : 'zh-CN', {
    timeZone: 'Asia/Shanghai', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false,
  })
  const validDate = value => typeof value === 'string' && Number.isFinite(Date.parse(value))
  const validNumber = value => value === null || (typeof value === 'number' && Number.isFinite(value) && value >= 0)
  function imageURL(value) {
    try {
      const url = new URL(value)
      return url.protocol === 'https:' && url.hostname.endsWith('.steamstatic.com') ? url.href : ''
    } catch { return '' }
  }
  function element(tag, text, className) {
    const node = document.createElement(tag)
    if (text !== undefined) node.textContent = text
    if (className) node.className = className
    return node
  }
  function setTime(selector, value) {
    const time = query(`${selector} time`)
    time.dateTime = value
    time.textContent = `${formatter.format(new Date(value))} CST`
  }
  function validStats(data) {
    return data && validDate(data.updatedAt) && ['level', 'badges', 'games', 'recentHours'].every(key => validNumber(data[key]))
      && Array.isArray(data.recentGames) && data.recentGames.length <= 3
      && data.recentGames.every(game => /^\d+$/.test(game.appid) && typeof game.name === 'string' && validNumber(game.hours))
  }
  function renderStats(data) {
    const level = query('.steam-level')
    level.textContent = data.level === null ? '' : `LV. ${data.level}`
    level.hidden = data.level === null
    const stats = query('.steam-stats')
    stats.replaceChildren()
    for (const [key, label] of [['badges', ui('Badges', '徽章')], ['games', ui('Games', '游戏')]]) {
      if (data[key] === null) continue
      const item = element('div')
      item.append(element('dt', label), element('dd', data[key]))
      stats.append(item)
    }
    const playtime = query('.steam-playtime')
    playtime.replaceChildren()
    if (data.recentHours === null) playtime.textContent = ui('Playtime is private', '游玩信息未公开')
    else playtime.append(ui('Past two weeks: ', '近两周 '), element('strong', data.recentHours), ui(' hours', ' 小时'))
    const recent = query('.steam-recent')
    recent.replaceChildren()
    recent.hidden = data.recentGames.length === 0
    recent.setAttribute('aria-label', ui('Recently played games', '近两周游玩的游戏'))
    for (const game of data.recentGames) {
      const link = element('a', undefined, 'steam-game')
      link.href = `https://store.steampowered.com/app/${game.appid}/`
      const src = imageURL(game.image)
      if (src) {
        const image = element('img')
        Object.assign(image, { src, width: 184, height: 69, alt: '', loading: 'lazy' })
        link.append(image)
      }
      link.append(element('strong', game.name))
      if (game.hours !== null) link.append(element('span', `${game.hours} h ${ui('total', '总计')}`))
      recent.append(link)
    }
    setTime('.steam-stats-updated', data.updatedAt)
  }

  let pending = false
  let controller
  let timer
  async function refresh() {
    if (pending || document.hidden) return
    pending = true
    controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), 12000)
    try {
      const response = await fetch(endpoint.href, { signal: controller.signal, credentials: 'omit', cache: 'no-store' })
      if (!response.ok) throw new Error('Unavailable')
      const data = await response.json()
      if (!data || !Object.hasOwn(labels, data.status) || !validDate(data.updatedAt)
          || typeof data.name !== 'string' || typeof data.currentGame !== 'string' || typeof data.isPublic !== 'boolean'
          || (data.stats !== null && !validStats(data.stats))) throw new Error('Invalid response')
      // Reject old/corrupt responses instead of labelling them as live.
      const age = Date.now() - Date.parse(data.updatedAt)
      if (age > 120000 || age < -60000) throw new Error('Stale response')
      query('.steam-identity strong').textContent = data.name
      const avatar = query('.steam-avatar')
      const src = imageURL(data.avatar)
      if (src && avatar) avatar.src = src
      status.dataset.status = data.status
      status.textContent = data.status === 'in-game' && data.currentGame ? `${ui('Playing ', '正在玩 ')}${data.currentGame}` : labels[data.status]
      status.title = ui('Checked every 60 seconds; Steam data and caches may be delayed', '每 60 秒查询；Steam 数据与缓存可能有延迟')
      setTime('.steam-status-updated', data.updatedAt)
      if (!data.isPublic) {
        renderStats({ level: null, badges: null, games: null, recentHours: null, recentGames: [], updatedAt: data.updatedAt })
      } else if (data.stats) renderStats(data.stats)
      message.textContent = data.isPublic && !data.stats ? ui('Status updates every 60 seconds · Profile update unavailable', '状态每 60 秒更新 · 资料更新暂不可用') : ui('Updates every 60 seconds', '每 60 秒自动更新')
    } catch {
      message.textContent = ui('Update unavailable; showing previous data', '更新暂不可用，保留上次数据')
      status.title = ui('Previously collected status; see the collection time below', '上次采集的状态；请查看下方采集时间')
    } finally {
      clearTimeout(timeout)
      pending = false
    }
  }
  function resume() {
    clearInterval(timer)
    if (document.hidden) return
    refresh()
    timer = setInterval(refresh, 60000)
  }
  document.addEventListener('visibilitychange', resume)
  window.addEventListener('pagehide', () => { clearInterval(timer); controller?.abort() })
  window.addEventListener('pageshow', event => { if (event.persisted) resume() })
  message.textContent = ui('Updating…', '正在更新…')
  resume()
})()
