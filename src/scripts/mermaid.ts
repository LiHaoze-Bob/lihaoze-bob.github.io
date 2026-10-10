export async function renderMermaid() {
  const diagrams = Array.from(document.querySelectorAll<HTMLElement>('.note-code[data-language="mermaid"]'))
    .flatMap(block => {
      const code = block.querySelector('code')
      const pre = block.querySelector('pre')
      return code && pre ? [{ block, pre, source: code.textContent || '' }] : []
    })
  if (!diagrams.length) return

  try {
    const { default: mermaid } = await import('mermaid')
    await document.fonts.ready
    let lastTheme = ''
    let sequence = 0
    let pending = Promise.resolve()

    async function render() {
      const theme = document.documentElement.classList.contains('dark') ? 'dark' : 'default'
      if (theme === lastTheme) return
      lastTheme = theme
      mermaid.initialize({ startOnLoad: false, securityLevel: 'strict', theme, suppressErrorRendering: true })
      for (const { block, pre, source } of diagrams) {
        try {
          const { svg } = await mermaid.render(`notes-mermaid-${sequence++}`, source)
          let output = block.querySelector<HTMLElement>('.mermaid')
          if (!output) {
            output = document.createElement('div')
            output.className = 'mermaid'
            pre.before(output)
          }
          output.innerHTML = svg
          const graph = output.querySelector('svg')
          if (graph) output.style.setProperty('--mermaid-width', `${graph.viewBox.baseVal.width}px`)
          pre.hidden = true
          block.dataset.mermaidTheme = theme
        } catch (error) {
          block.querySelector('.mermaid')?.remove()
          pre.hidden = false
          delete block.dataset.mermaidTheme
          console.warn('Mermaid 图表渲染失败，保留源码。', error)
        }
      }
    }

    const scheduleRender = () => { pending = pending.then(render) }
    new MutationObserver(scheduleRender).observe(document.documentElement, { attributes: true, attributeFilter: ['class'] })
    scheduleRender()
    await pending
  } catch (error) {
    console.warn('Mermaid 加载失败，保留源码。', error)
  }
}
