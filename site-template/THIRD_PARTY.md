# Theme assets

Chirpy layouts, styles and JavaScript are provided by the MIT-licensed `jekyll-theme-chirpy` 7.6.0 gem.

`assets/lib/` contains unmodified libraries and fonts from [chirpy-static-assets](https://github.com/cotes2020/chirpy-static-assets), commit `5cde3f0076b62e45fc68291893cf7d93e122adb7`. The bundled font licenses and repository license are retained. MathJax 3.2.2 remains self-hosted in `assets/vendor/mathjax/` with its license.

`_data/locales/en.yml` and `_data/origin/basic.yml` are from Chirpy 7.6.0; changes add the custom tab names and point MathJax to the existing local bundle.

`_includes/post-nav.html` adapts Chirpy 7.6.0's navigation component to link public notes in the same folder by filename instead of site-wide publication date.

`_layouts/home.html` adapts Chirpy 7.6.0's home cards to show section headings and complete public directory paths.

`_includes/topbar.html` adapts Chirpy 7.6.0's top bar to show the exported folder hierarchy in note and directory breadcrumbs, retaining the theme's navigation for other pages.

`assets/css/breadcrumbs.css` keeps that hierarchy visible in Chirpy's compact top bar.

## Callout icons

`assets/lib/lucide/` contains the Lucide SVG shapes used by the locally installed
Obsidian app for built-in callouts and the configured Callout Manager types.
They are rendered as CSS masks to retain the callout color. Lucide's ISC and
Feather's MIT notices are retained in that directory's `LICENSE` file; see the
[Lucide project](https://github.com/lucide-icons/lucide).

## Education images

School marks are used only to identify the author's education; they are not covered by the theme's software license. The original image files are retained without modification; the homepage crops and fades them with CSS.

- `assets/images/education/hanggao.jpg`: [Hangzhou High School official website](http://www.hanggao.net/), [original image](http://www.hanggao.net/admin/uploadotherall/site/gyhanggao/xiaoyoulogo.jpg).
- `assets/images/education/zju.png`: Zhejiang University mark, via [Wikipedia's file page](https://zh.wikipedia.org/wiki/File:Zhejiang_University_Logo.svg), [PNG image](https://thumb.wikimedia.org/wikipedia/zh/thumb/1/16/Zhejiang_University_Logo.svg/250px-Zhejiang_University_Logo.svg.png). See also the university's [official description of its mark](https://www.zju.edu.cn/xb/listm.htm).
