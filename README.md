# sychostar

浙江大学 CS 本科生的课程笔记、知识积累与阅读记录。

[网站](https://lihaoze-bob.github.io/) · [部署记录](https://github.com/LiHaoze-Bob/lihaoze-bob.github.io/actions)

## 日常发布

在 Obsidian 的「网站发布」控制页点击「检查内容」「预览网站」「发布网站」。三个入口由桌面版 Shell commands 插件调用项目脚本。

为要公开的笔记添加布尔属性：

```yaml
publish: true
```

只有 `publish: true` 生效，字符串 `"true"` 会报错，旧的 `published:` 属性不参与发布。正文在 Obsidian 中维护，`docs/` 是自动生成的副本，不要直接编辑。

`publish.toml` 限定课程、技术积累、Tools、Reading 和 Paper 五个源目录。`local.toml` 保存本机 Vault 路径并被 Git 忽略。GitHub Actions 只构建已导出的公开内容。

Pure 网站的普通笔记使用文件名（不含 `.md`）作为主标题，属性 `title` 或正文第一个一级标题作为副标题；两者相同时省略副标题。文章页、首页、课程目录、标签文章列表、路径导航和上一篇／下一篇统一使用这两层名称，搜索也包含两者。`index.md` 目录首页保留原有栏目标题。Chirpy 回退主题继续使用原标题。`nav_order` 用数字控制同层笔记顺序。目录保留原层级、按数字自然排序；目录名称可在 `publish.toml` 的 `labels` 中设置。

## 图片、链接与撤下页面

支持标准 Markdown 链接、`[[笔记]]`、`[[笔记#标题|文字]]`、`![[图片.png]]` 和图片宽度。建议使用笔记旁的 `assets/` 目录；图片必须位于配置允许的源目录内。程序只复制引用的图片，并通过内容哈希避免同名覆盖。

Pure 正文图片默认居中，宽度不超过正文和 600px，高度不超过 500px 或视口高度的 70%，保持比例且不裁剪；较小图片不会被放大，笔记中指定的图片宽度仍保留。点击本地图片可放大查看细节。

提示块、折叠提示块和数学公式在导出时适配网站，原文不变；Callout Manager 中定义的自定义类型、颜色和常用图标会一并带到网站，未知类型也保留原名称。代码中的示例语法不会转换。未公开笔记的链接转为文字并提示。缺图、歧义链接、块引用、笔记嵌入、动态 Dataview 和非图片本地附件会阻止发布。

支持 [Tabsdown](https://github.com/grafanaKibana/obsidian-tabsdown) 围栏及嵌套标签页。导出后保留位置、换行、密度、外观、配色和对齐配置，并支持鼠标与键盘切换；浏览器禁用 JavaScript 时改为依次显示所有面板，不会隐藏正文。无效的标签数量、重复标签、未知配置或未闭合围栏会阻止发布。

将 `publish` 改成 `false` 后再次发布，对应页面和不再使用的图片会从当前网站及搜索索引移除。已经公开的 Git 历史仍保留旧内容。笔记移动或重命名会改变网址。

## 环境与命令

默认使用 **Astro 6.4.8 + Astro Theme Pure（astro-pure 1.4.9）**，依赖由 `package-lock.json` 固定。Python 3.12 负责筛选并转换 Obsidian 笔记，依赖由 `uv.lock` 固定。原来的 Jekyll + Chirpy 7.6.0 渲染器、模板和 Ruby 依赖仍然保留，支持回退。

新机器安装 Node.js 22.12+；需要验证或使用旧主题时再安装 Ruby 3.3（macOS 可用 `brew install ruby@3.3`）。在项目根目录执行：

```sh
uv sync --frozen --python 3.12
npm ci
cp local.example.toml local.toml
# 编辑 local.toml，填写本机 Vault 的绝对路径
.venv/bin/python scripts/site.py check
.venv/bin/python scripts/site.py preview
.venv/bin/python scripts/site.py publish
```

发布需要 Git、已登录正确账号的 GitHub CLI。目标固定为 `LiHaoze-Bob/lihaoze-bob.github.io` 的 `main` 分支；只自动提交 `docs/` 中的公开快照。其他分支、其他 origin、未提交的源码修改会阻止自动发布。

`check` 在临时目录导出、构建并校验内部链接与资源。`preview` 同时启动仅绑定本机的预览服务：`http://127.0.0.1:8765/`；再次点击会更新内容并复用服务。

`publish` 完成检查后提交、推送并等待该提交的 GitHub Actions 部署结果，只有成功才提示「已上线」。重复点击受互斥锁保护，内容没变化不会生成空提交。

提交信息按本次公开笔记变化自动生成，标题保留原文：单篇新增用 `feat: add 「标题」`，更新用 `docs: update 「标题」`，撤下用 `docs: remove 「标题」`；多篇变化用数量汇总，例如 `docs: add 2 notes, update 3 notes`。只改图片、目录或发布元数据时使用 `docs: update public snapshot`。

## 排错

- **缺失图片或歧义链接**：按报错修正引用，使用明确的相对路径。
- **源码未提交**：在网站项目中检查并提交认可的代码修改，再发布。
- **网络、认证或推送失败**：检查 GitHub 登录与连接后重试；脚本不会强制推送。
- **终端可连接、Obsidian 连接超时**：在 `local.toml` 设置 `proxy`，参考示例文件。本机已设置代理，发布时需保持代理应用运行；代理端口变更后同步更新此项。
- **远端有新提交**：在网站项目中检查差异并合并，不要对 Obsidian Vault 执行这些操作。
- **部署失败或超时**：查看仓库 Actions；本地状态保存在 `.runtime/status.json`。
- **控制页无反应或 Working directory 报错**：确认 Shell commands 插件已启用，将 Environments 中的 Working directory 留空（默认使用 Vault 目录），再正常重启 Obsidian。三个入口脚本会自行切换到网站项目目录。
- **移动项目目录**：更新三个命令中的绝对路径，并重建虚拟环境；插件 Working directory 保持留空。

## 网站与主题

使用 [Astro Theme Pure](https://github.com/cworld1/astro-theme-pure) 的原生组件、顶部导航、阅读布局、右侧目录、明暗切换和 Pagefind 全文搜索。首页参考 [Arthals' ink](https://arthals.ink/) 的居中头像、淡色渐变与分栏布局，展示个人介绍、最新 10 篇笔记和教育经历卡片；窄屏改为单栏。头像支持悬浮放大，教育卡片带学校标志和官网链接，悬浮或键盘聚焦时浮起；减少动态效果的系统偏好会关闭位移动画。顶部依次为 **Course / Reading / Tech / About**。Course、Reading、Tech 栏目首页右侧显示本栏目公开笔记的 Tags 标签云，按使用次数排序，点击可进入标签文章页；窄屏通过侧栏按钮展开。没有标签时显示空状态，View all 可进入全站标签汇总。Tags 汇总页使用横向自动换行的标签云，每个标签带公开笔记数量，按数量降序排列，常用标签字号更大。图片放大、代码复制、MathJax 公式和 RSS 保留。

- `src/site.config.ts`：Pure 的站名、简介、导航、社交链接和功能设置。
- `src/layouts/`、`src/components/`、`src/styles/`：Pure 页面、首页列表和笔记样式。
- `astro.config.ts`：静态构建及 GitHub Pages 根路径。
- `publish.toml` 的 `site.theme`：默认主题，`pure` 或 `chirpy`。
- `site-template/_tabs/about.md`：两种主题共用的 About 正文。
- `site-template/assets/`：共用的头像、字体、Callout、Tabsdown 和 MathJax 资源。
- `_config.yml` 和其余 `site-template/` 文件：保留的 Chirpy 设置及模板。

About 的 Steam 卡片使用 `site-template/_data/steam.json` 保存发布快照，展示头像、等级、在线或游戏状态、徽章、游戏数量、近两周时长和三款游戏。配置 `site-template/_data/steam-live.json` 的 `endpoint` 后，打开页面立即更新，可见时每 60 秒查询状态，资料缓存一小时；状态和资料分别标注采集时间，失败时保留旧数据。两种主题均支持，后台标签页暂停请求。需要部署 `workers/steam/worker.mjs` 并在 Cloudflare 配置 Steam Key，见 [部署步骤](workers/steam/README.md)。查询间隔不保证 Steam 数据的实际延迟。

接口未配置或 JavaScript 不可用时显示发布快照。GitHub Actions 每次发布前运行 `scripts/steam.py`；网络错误或限流时保留旧快照及其原始更新时间。本地刷新快照可运行 `.venv/bin/python scripts/steam.py`，随后运行 `.venv/bin/python scripts/site.py build`；此快照流程无需 Steam API 密钥。近两周时长与每款游戏的累计时长各自展示，不将三款游戏时长当作全库总时长。

课程使用 `/courses/`；Tech 使用 `/knowledge/`，子目录为 `/knowledge/tech/` 和 `/knowledge/tools/`；Reading 使用 `/reading/`，子目录为 `/reading/reading/` 和 `/reading/paper/`。Course 按原目录层级显示文件夹和笔记；Tech 的栏目首页不展示深层文件夹，而是在一级分组下直接列出带文章图标的公开笔记；Reading 则保留完整的可折叠目录树和文章图标。笔记的 URL 和顶部路径导航仍保留完整目录层级。

可选属性 `date` 设置文章日期（如 `2026-09-14`）。没有该属性时，已有笔记使用 Git 中首次公开的日期；新笔记使用首次导出到公开快照的时间。`Posted` 会保持不变；公开内容后续发生变化时，文章页会同时显示 `Updated`，更新时间不会因公开快照未变的重复构建而刷新。这两类时间和公开内容指纹均保存在 `docs/publication.json`。公开的目录 `index.md` 优先作为该目录首页；课程目录首页会在正文后自动列出同目录及子目录中已公开的笔记，顶层栏目索引不重复加入首页文章列表。文章页标题下不自动重复正文摘要；只有笔记显式填写 `description` 时才显示简介。

文章底部的 Older / Newer 只在同一文件夹的公开文章之间跳转，按原文件名自然排序（例如 Lecture2 在 Lecture10 前），不受文章日期、显示标题或 `nav_order` 影响，也不会进入子文件夹。Older 指向前一篇，Newer 指向后一篇；到达首尾时对应按钮禁用。

首页以日期和标题组成紧凑文章列表，点击 More notes 进入后续分页；原分页网址保持可用。后续分页保留详细列表，自动提取正文最外层级的前 4 个不同章节标题，以「 · 」分隔；忽略代码和提示块内的标题、重复的文章标题及公式，没有章节标题时省略摘要。详细列表底部显示完整公开目录（如 `Course / FDS-ZJU / notes`），目录名称沿用 `publish.toml` 的 `labels`，长路径允许换行。首页介绍与教育经历在 `src/components/Home.astro` 维护，首页专用样式位于 `src/styles/home.css`。

### 添加首页随机名言

编辑 `src/data/quotes.json`，在数组里填入句子，每句使用英文双引号，句子之间用逗号隔开。例如（下面是填写格式，不会自动展示到网站）：

```json
[
  "你的第一句话。",
  "你的第二句话。——作者"
]
```

保存并重新构建、提交发布后，每次打开或刷新首页会从列表中随机显示一句，位置在教育经历下方。使用本地句子，不依赖第三方接口；关闭 JavaScript 时显示第一句。空数组 `[]` 会完全隐藏名言区域，空白句子会被忽略。最后一句后面不要加逗号；句子里的英文双引号需写为 `\"`。

顶部路径导航按笔记所在目录显示完整层级，例如 Home › Course › FDS-ZJU › notes › 算法分析基础，每个上级目录均可点击返回；窄窗口中保留该路径并支持横向滚动，不再显示笼统的 Post。目录名称优先使用 `labels`，其次使用公开目录首页的标题，最后使用文件夹名；顶层栏目使用侧栏名称。

Course 和 Reading 的目录使用浏览器原生折叠控件。旧标签、分类和分页网址继续可用。静态资源版本及许可证见 `site-template/THIRD_PARTY.md`，Pure 的来源及改动见 `PURE-NOTICE.md`。当前未配置 PWA 离线缓存。

### 文章评论（Giscus）

Pure 的每篇笔记在上一篇／下一篇导航下显示 Giscus 评论区；首页、目录、标签和 About 不显示。配置位于 `src/site.config.ts` 的 `comments`，组件位于 `src/components/Comments.astro`。评论保存在 `LiHaoze-Bob/lihaoze-bob.github.io` 的 Discussions → Announcements，仓库必须开启 Discussions，并通过 [Giscus GitHub App](https://github.com/apps/giscus) 授权访问该仓库。访客登录 GitHub 后可评论、回复和添加表情。

使用 `pathname` 映射和严格匹配，每篇文章有独立讨论；第一次评论或回应时自动创建讨论。修改标题不会影响关联，修改文章路径则需要迁移对应讨论标题及严格匹配哈希（见 [Giscus 文档](https://github.com/giscus/giscus/blob/main/ADVANCED-USAGE.md#data-strict)）。评论 iframe 懒加载，主题跟随网站实际深浅色状态；评论区域不进入站内搜索索引。正式站点 canonical URL 用作讨论回链，本地预览也不会生成 localhost 回链。关闭评论可设置 `comments.enable: false`，已有讨论仍保留在 GitHub。

Pure 的 About 和笔记标题下显示 `views`，使用[不蒜子](https://busuanzi.ibruce.info/)记录当前页面的累计访问次数（PV，重复访问会累加，不代表独立访客数）。计数由第三方服务按页面网址保存，不能补回接入前的历史访问；更换域名或路径可能重新计数。`src/components/PageViews.astro` 仅在 `astro.config.ts` 配置的正式站点域名加载计数脚本，本地预览不请求统计服务。加载中、脚本被拦截或服务不可用时显示 `— views`，正文正常显示；Chirpy 回退主题保持原状。

### 搜索笔记

顶部搜索按钮在桌面和手机上均可直接使用，也可按 `⌘K`（macOS）或 `Ctrl+K` 打开搜索；搜索页中再次按下会选中当前关键词。支持标题、章节和正文的全文搜索，可用 Course / Reading / Tech 限定栏目，多个关键词用空格分隔。只展示公开笔记，目录页、标签汇总和 About 不混入结果。

每条结果显示完整目录、突出的文件名主标题、较小的原笔记副标题、命中高亮摘要及相关章节链接。标题匹配提高权重，结果按相关性排列；每次加载 10 篇，可点击「显示更多结果」。中文输入法组词期间不会提交搜索，快速改词时只展示最后一次查询。空输入显示最近发布的笔记，网络加载失败可重试。

搜索词和栏目保存在网址的 `q`、`section` 参数中，可复制分享、刷新或从文章返回恢复。使用 `↑` / `↓` 在结果链接之间切换，`Enter` 打开，`Esc` 清空。搜索组件、交互和样式分别位于 `src/components/NoteSearch.astro`、`src/scripts/search.ts` 和 `src/styles/search.css`。

## 回到 Chirpy

先用**最新公开快照**预览旧主题，不改默认设置或笔记：

```sh
# 第一次使用旧主题时安装它的依赖
export PATH="$(brew --prefix ruby@3.3)/bin:$PATH"
BUNDLE_PATH=.runtime/bundle bundle install
.venv/bin/python scripts/site.py build --theme chirpy
# 此时本机预览服务显示旧主题；build 不读取 Vault 或覆盖 docs/
```

也可以运行 `check --theme chirpy` 或 `preview --theme chirpy`，临时用旧主题检查最新的 Obsidian 公开笔记。恢复 Pure 预览运行 `build --theme pure`。

永久切回时，仅将 `publish.toml` 中的 `theme = "pure"` 改为 `theme = "chirpy"`，检查并提交该设置后再部署。`docs/`、发布时间记录和后续新增笔记都保留；GitHub Actions 已同时安装两种主题所需依赖。旧版本另有本地标签 `chirpy-before-astro-2026-09-29`（`9507ba0`），用于查看完整的迁移前源码，**不要为了换外观将整个仓库重置到该标签**。

## 开发

```sh
uv run --frozen pytest -q
ASTRO_TELEMETRY_DISABLED=1 npm run check
# 仅用已导出的公开内容构建，与 GitHub Actions 相同，不读取 Vault
uv run --frozen python scripts/site.py build
```

`scripts/exporter.py` 负责筛选公开内容、转换 Obsidian 语法和复制引用图片；`scripts/astro.py` 将公开快照适配为 Pure 页面数据；`scripts/jekyll.py` 保留原主题适配器，也提供两种主题共用的正文转换、目录和日期逻辑；`scripts/site.py` 负责构建、检查、预览和发布。临时数据及资源位于 `.runtime/`，最终输出位于 `site/`，均不提交。

转换层保留数学公式、嵌套提示块、代码、中文锚点与既有网址。正文禁用 Liquid 展开，因此笔记里的 `{{ ... }}` 或 `{% ... %}` 示例仍作为原文展示。GitHub Actions 无需访问 Obsidian Vault。

修改源码或主题设置后，可检查并重新生成公开快照：

```sh
.venv/bin/python -c 'from scripts.site import prepare; prepare(True)'
```

审阅源码与导出变更后再提交。自动发布入口会拒绝尚未提交的源码修改。
