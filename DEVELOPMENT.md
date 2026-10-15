# Development notes

Setup, publishing, implementation details, and maintenance notes for [sychostar](https://lihaoze-bob.github.io/).

## Stack and setup

The default renderer uses Astro 6.4.8 and Astro Theme Pure (`astro-pure` 1.4.9), pinned in `package-lock.json`. Python 3.12 selects and converts Obsidian notes, with dependencies locked in `uv.lock`. The Jekyll renderer, Chirpy 7.6.0 templates, and Ruby dependencies remain available as a fallback.

Install Node.js 22.12+ and uv. Ruby 3.3 is only needed to build or verify the legacy theme; on macOS, install it with `brew install ruby@3.3`. Run from the project root:

```sh
uv sync --frozen --python 3.12
npm ci
cp local.example.toml local.toml
# Set vault in local.toml to the absolute path of your Obsidian vault.
.venv/bin/python scripts/site.py check
.venv/bin/python scripts/site.py preview
.venv/bin/python scripts/site.py publish
```

`local.toml` holds machine-specific settings and is ignored by Git. `publish.toml` limits exports to five configured source directories: courses, technical notes, tools, reading notes, and papers. GitHub Actions builds the exported public snapshot without access to the vault.

## Publishing from Obsidian

Use the check, preview, and publish buttons on the website publishing control page in Obsidian. The desktop Shell commands plugin runs the corresponding project scripts.

Add a boolean property to each note you want to publish:

```yaml
publish: true
```

Only boolean `publish: true` enables publication. The string `"true"` produces an error, and the old `published:` property has no effect. Edit note content in Obsidian; `docs/` is a generated public snapshot and should not be edited directly.

- `check` exports to a temporary directory, builds the site, and validates internal links and assets.
- `preview` also starts a local-only server at `http://127.0.0.1:8765/`. Running it again refreshes the content and reuses the server.
- `publish` checks the content, commits and pushes the snapshot, then waits for the matching GitHub Actions deployment. It reports success only after deployment succeeds. A lock prevents overlapping runs, and unchanged content does not create empty commits.

Publishing requires Git and GitHub CLI authenticated with the correct account. The configured target is the `main` branch of `LiHaoze-Bob/lihaoze-bob.github.io`. The publisher only commits changes under `docs/`; a different branch, a mismatched origin, or uncommitted source changes stops automatic publishing.

The current publisher derives snapshot commit messages from note changes and preserves original note titles. Single-note messages use `feat: add 「Title」`, `docs: update 「Title」`, or `docs: remove 「Title」`. Multiple changes use counts, such as `docs: add 2 notes, update 3 notes`. Changes limited to images, directories, or publication metadata use `docs: update public snapshot`.

### Titles and ordering

In Pure, a regular note's filename without `.md` is its main title. The `title` property or first level-one heading becomes a subtitle, omitted when it matches the main title. Article pages, the homepage, course indexes, tag listings, breadcrumbs, and previous/next navigation use both names; search indexes both. Directory landing pages named `index.md` retain their section titles. The Chirpy fallback keeps the original title behavior.

Use a numeric `nav_order` to order sibling notes. Directories retain their hierarchy and use natural numeric sorting. Set directory display names in the `labels` table of `publish.toml`.

### Images, links, and rich content

The exporter supports standard Markdown links, `[[Note]]`, `[[Note#Heading|Text]]`, `![[image.png]]`, and image widths. Prefer an `assets/` directory beside the notes. Images must be inside an allowed source directory. Only referenced images are copied; content hashes prevent filename collisions.

Pure centers article images and limits them to the content width and 600px, with a maximum height of 500px or 70% of the viewport. Images retain their proportions without cropping, small images are not enlarged, and explicit widths are preserved. Click a local image to zoom in.

Callouts, collapsible callouts, and math are adapted during export without changing the source notes. Callout styling follows Obsidian's Blue Topaz shade style: translucent backgrounds, darker title bars, rounded borders, and shadows, with separate light and dark palettes. Custom types, colors, and common Lucide icons from Callout Manager are carried over. Icons use local SVGs, and unknown types retain their names. Collapse arrows sit beside the title and support keyboard operation. Syntax inside code examples is left unchanged.

Links to unpublished notes become text with a notice. Missing images, ambiguous links, block references, note embeds, dynamic Dataview content, and non-image local attachments block publication.

[Tabsdown](https://github.com/grafanaKibana/obsidian-tabsdown) fences and nested tabs retain their placement, line breaks, density, appearance, colors, and alignment settings. Tabs support mouse and keyboard navigation. Without JavaScript, all panels appear in sequence. Invalid tab counts, duplicate labels, unknown options, and unclosed fences block publication.

Pure highlights code with Prism at build time. Colors and spacing follow the default Obsidian Blue Topaz code theme and support light and dark modes. The declared language, such as `python`, `json`, or `http`, is always visible at the upper left. The copy button appears at the upper right on hover or keyboard focus and stays visible on touchscreens. Incomplete teaching examples, including JSON and HTTP fragments, retain their text without syntax-error boxes. Unknown languages render as plain text. Styles live in `src/styles/code.css`; changes to Obsidian settings do not automatically update them.

### Removing or renaming notes

Set `publish` to `false` and publish again to remove a page, its unused images, and its search entry from the current site. Previously published content remains in Git history. Moving or renaming a note changes its URL.

## Site structure and presentation

Pure provides the header, reading layout, right-hand table of contents, theme switcher, and Pagefind search. The homepage takes inspiration from [Arthals' ink](https://arthals.ink/), with a centered avatar, soft gradients, columns, a personal introduction, the ten latest notes, and education cards. Narrow screens use one column. The avatar enlarges on hover; education cards include school marks and official links and rise on hover or keyboard focus. Reduced-motion preferences disable movement animations.

The header links to Course, Reading, Tech, and About. Course, Reading, and Tech landing pages show a sidebar tag cloud for their public notes, ordered by frequency. On narrow screens, a sidebar button reveals it. Empty sections show an empty state; View all opens the global tag page. That page uses a wrapping tag cloud with public-note counts, sorted by frequency, with larger text for common tags. Image zoom, code copying, MathJax, and RSS remain available. PWA offline caching is not configured.

### Files to edit

| Path | Purpose |
| --- | --- |
| `src/site.config.ts` | Pure site name, description, navigation, social links, comments, and feature settings |
| `src/layouts/`, `src/components/`, `src/styles/` | Pure layouts, note lists, and presentation |
| `astro.config.ts` | Static build and GitHub Pages base path |
| `publish.toml` | Source mappings, directory labels, and default theme (`pure` or `chirpy`) |
| `site-template/_tabs/about.md` | About content shared by both themes |
| `site-template/assets/` | Shared avatar, fonts, callout assets, Tabsdown, and MathJax |
| `_config.yml` and other `site-template/` files | Legacy Chirpy configuration and templates |

### Sections and navigation

Course uses `/courses/`. Tech uses `/knowledge/`, with `/knowledge/tech/` and `/knowledge/tools/`. Reading uses `/reading/`, with `/reading/reading/` and `/reading/paper/`.

Course preserves the source folder hierarchy. Tech landing pages list public notes with article icons beneath their top-level groups, without showing deeper folder nesting. Reading keeps the full collapsible directory tree and article icons. Note URLs and breadcrumbs retain the complete hierarchy in every section.

Breadcrumbs show the full path, such as Home › Course › FDS-ZJU › notes › Algorithm Analysis. Each parent directory links back to its index. Narrow windows keep the full path with horizontal scrolling. Directory names come from `labels`, then the public directory index title, then the folder name. Top-level sections use their sidebar names.

Course and Reading trees use native browser disclosure controls. Legacy tag, category, and pagination URLs remain available.

### Publication dates and directory indexes

The optional `date` property sets an article's date, for example `2026-09-14`. Without it, existing notes use their first public date in Git; new notes use the time of their first public export. `Posted` stays fixed. Later public content changes add an `Updated` timestamp, which does not change on repeated builds of an unchanged snapshot. Both timestamps and public content fingerprints are stored in `docs/publication.json`.

A public `index.md` takes precedence as its directory's landing page. Course directory indexes automatically list public notes in the same directory and its descendants after the body. Top-level section indexes are excluded from homepage article lists. Article headers show a description only when the note explicitly supplies `description`; they do not repeat an automatically extracted summary.

Older / Newer navigation stays within the same folder and sorts public articles naturally by original filename, placing Lecture2 before Lecture10. It ignores publication dates, display titles, and `nav_order`, and does not enter subfolders. Older points to the preceding note; Newer points to the following note. Buttons are disabled at either end.

### Homepage and quotes

The homepage uses a compact list of dates and titles. More notes opens subsequent pages, and existing pagination URLs remain valid. Later pages use detailed lists with summaries from the first four distinct headings at the outermost heading level, separated by ` · `. Headings inside code and callouts, repeated article titles, and formulas are excluded. Notes without section headings have no summary.

Detailed lists show the full public directory path, such as `Course / FDS-ZJU / notes`, using labels from `publish.toml` and allowing long paths to wrap. Edit the homepage introduction and education cards in `src/components/Home.astro`; homepage styles live in `src/styles/home.css`.

To add random homepage quotes, edit `src/data/quotes.json`:

```json
[
  "Your first quote.",
  "Your second quote. — Author"
]
```

After rebuilding and deploying, each homepage load or refresh selects a local quote beneath the education cards. No external API is used. Without JavaScript, the first quote appears. An empty array (`[]`) hides the area, and blank entries are ignored. Use double-quoted strings, separate them with commas, omit a trailing comma, and escape embedded double quotes as `\"`.

### Steam card

The About page uses `site-template/_data/steam.json` as a published snapshot of the avatar, level, online or in-game status, badges, game count, playtime over the last two weeks, and three games.

Set `endpoint` in `site-template/_data/steam-live.json` to enable live updates. The page refreshes immediately on opening, then polls status every 60 seconds while visible; profile data is cached for one hour. Status and profile data show separate collection times, and failures retain existing data. Both themes support this behavior, and background tabs pause requests. Deploy `workers/steam/worker.mjs` and configure a Steam API key in Cloudflare following the [worker deployment guide](workers/steam/README.md). Polling frequency does not guarantee the freshness of Steam's underlying data.

Without an endpoint or JavaScript, the page shows the published snapshot. GitHub Actions runs `scripts/steam.py` before each site build. Network errors or rate limits preserve the previous snapshot and its original timestamp. To refresh locally:

```sh
.venv/bin/python scripts/steam.py
.venv/bin/python scripts/site.py build
```

Snapshot refreshes do not require a Steam API key. Recent two-week playtime and each game's total playtime are displayed separately; the three games' playtime is not presented as a library-wide total.

### Comments and page views

Pure displays Giscus below previous/next navigation on each note. Homepages, directories, tag pages, and About do not show comments. Settings live in `src/site.config.ts` under `comments`; the component is `src/components/Comments.astro`.

Comments are stored in Discussions → Announcements in `LiHaoze-Bob/lihaoze-bob.github.io`. The repository must enable Discussions and authorize the [Giscus GitHub App](https://github.com/apps/giscus). Visitors sign in with GitHub to comment, reply, and react.

Giscus uses `pathname` mapping with strict matching, giving each article its own discussion. The first comment or reaction creates the discussion. Title changes preserve the association; path changes require migrating the discussion title and strict-match hash, as described in the [Giscus documentation](https://github.com/giscus/giscus/blob/main/ADVANCED-USAGE.md#data-strict).

The comment iframe loads lazily and follows the site's active light or dark theme. Comments are excluded from site search. Discussion backlinks use the production canonical URL, including in local previews. Set `comments.enable` to `false` to disable comments; existing discussions remain on GitHub.

Pure displays page views beneath About and note titles using [Busuanzi](https://busuanzi.ibruce.info/). Counts are page views, including repeat visits, rather than unique visitors. The third-party service stores counts by URL, cannot recover visits before integration, and may start a new count after domain or path changes.

`src/components/PageViews.astro` loads the counter only on the production origin configured in `astro.config.ts`. Local previews do not request the service. Loading, blocked scripts, or service failures show `— views` while leaving the article readable. The Chirpy fallback retains its existing behavior.

### Search

The header search button works on desktop and mobile. Press `⌘K` on macOS or `Ctrl+K` elsewhere to open search; pressing it again on the search page selects the current query.

Search covers titles, headings, and body text, with Course / Reading / Tech filters and space-separated keywords. Results include only public notes, excluding directory pages, tag indexes, and About.

Each result shows the full directory path, a prominent filename title, a smaller original-note subtitle, a highlighted excerpt, and matching section links. Title matches receive extra weight, and results are sorted by relevance. Ten notes load at a time, with a button to load more. Search waits for input-method composition to finish and only displays results for the latest query. Empty queries show recently published notes; failed network loads can be retried.

The URL stores the query and section in `q` and `section`, allowing sharing and restoring state after refresh or returning from an article. Use `↑` / `↓` to move between result links, `Enter` to open one, and `Esc` to clear the query. The component, behavior, and styles live in `src/components/NoteSearch.astro`, `src/scripts/search.ts`, and `src/styles/search.css`.

## Switching to Chirpy

Build the latest public snapshot with the legacy theme without changing the default or reading the vault:

```sh
# Install the legacy theme dependencies on first use.
export PATH="$(brew --prefix ruby@3.3)/bin:$PATH"
BUNDLE_PATH=.runtime/bundle bundle install
.venv/bin/python scripts/site.py build --theme chirpy
```

An existing local preview server now serves the legacy output. `build` does not read the vault or overwrite `docs/`. Use `check --theme chirpy` or `preview --theme chirpy` to check the latest public notes from Obsidian with the legacy theme. Run `build --theme pure` to restore the Pure preview.

To switch permanently, change `theme = "pure"` to `theme = "chirpy"` in `publish.toml`, check and commit the setting, then deploy. The public snapshot, publication records, and later notes are preserved. GitHub Actions installs dependencies for both themes.

The local tag `chirpy-before-astro-2026-09-29` (`9507ba0`) retains the full pre-migration source for reference. Do not reset the entire repository to that tag to change themes.

## Development checks

```sh
uv run --frozen pytest -q
ASTRO_TELEMETRY_DISABLED=1 npm run check
node --test tests/*.test.mjs
# Build only the exported public content, as GitHub Actions does.
uv run --frozen python scripts/site.py build
```

The pipeline is Obsidian source notes → `docs/` public snapshot → renderer → `site/` → GitHub Pages. Temporary data and assets live in `.runtime/`; final output lives in `site/`. Neither directory is committed.

| Script | Responsibility |
| --- | --- |
| `scripts/exporter.py` | Select public notes, convert Obsidian syntax, and copy referenced images |
| `scripts/astro.py` | Adapt the public snapshot into Pure page data |
| `scripts/jekyll.py` | Adapt the legacy theme and provide shared body conversion, directory, and date logic |
| `scripts/site.py` | Build, validate, preview, and publish |

The conversion layer preserves math, nested callouts, code, Chinese anchors, and existing URLs. Liquid expansion is disabled in article bodies, so examples containing `{{ ... }}` or `{% ... %}` stay literal. GitHub Actions does not need the Obsidian vault.

After source or theme changes, check and regenerate the public snapshot when needed:

```sh
.venv/bin/python -c 'from scripts.site import prepare; prepare(True)'
```

Review source and export changes before committing. Automatic publishing refuses uncommitted source modifications.

## Troubleshooting

- **Missing images or ambiguous links:** fix the reported reference and use an explicit relative path.
- **Uncommitted source:** review and commit the intended website source changes before publishing.
- **Network, authentication, or push failures:** check GitHub authentication and connectivity, then retry. The script never force-pushes.
- **Obsidian times out while the terminal connects:** set `proxy` in `local.toml` using `local.example.toml` as a guide. Keep the proxy application running and update the setting if its port changes.
- **New remote commits:** inspect and merge changes in the website repository, not the Obsidian vault.
- **Deployment failure or timeout:** inspect repository Actions and `.runtime/status.json`.
- **Inactive control buttons or Working directory errors:** enable Shell commands, leave its environment's Working directory empty to use the vault default, then fully restart Obsidian. The three entry scripts change to the website project directory themselves.
- **Moving the project:** update absolute paths in all three Obsidian commands and rebuild the virtual environment. Keep the plugin's Working directory empty.

## Credits and third-party notices

The site uses [Astro Theme Pure](https://github.com/cworld1/astro-theme-pure), with a retained Chirpy fallback. Homepage layout inspiration comes from [Arthals' ink](https://arthals.ink/). Callout and code styling adapts Obsidian Blue Topaz.

See [PURE-NOTICE.md](PURE-NOTICE.md) for Pure provenance and local changes, and [site-template/THIRD_PARTY.md](site-template/THIRD_PARTY.md) for bundled assets, versions, and license notices.
