# shotgate · website (`web` branch)

This orphan branch holds the **shotgate** website, served by GitHub Pages at
<https://shotgate.coldqubit.org>. It shares no history with `main`: the product
lives on `main`, the site lives here.

## Structure

```text
index.html                  the landing page
404.html                    branded not-found page
docs/
  index.html                the docs reader shell
  docs.css                  reader surface styles (from the design-system docs kit)
  docs.js                   fetches docs/*.md from main (raw.githubusercontent),
                            renders with marked + DOMPurify, mermaid on demand
styles/
  styles.css                design-system entry point (fonts + tokens + components)
  fonts.css                 brand faces (IBM Plex Mono + Sans, Google Fonts)
  colors_and_type.css       token layer (color, type, spacing, radii, motion)
  components.css            canonical component classes
  site.css                  page-level styles for the landing surface only
js/site.js                  navbar name reveal + terminal demo + repo-synced badges
assets/                     logomark SVG + PNG favicons
.github/workflows/pages.yml deploy workflow (Pages in GitHub Actions mode)
```

The landing badges and the docs content sync themselves from the repository at
view time (GitHub API + raw.githubusercontent, cached 10 minutes, static
fallbacks baked into the HTML). Deploying the site is never needed just
because the docs changed: the reader always renders `main`.

`styles/{styles,fonts,colors_and_type,components}.css` are vendored verbatim
from the coldqubit design system. Do not edit them here; change the design
system and re-copy. Surface-specific rules belong in `styles/site.css`.

## Deploying

Push to `web`. The `deploy-pages` workflow uploads the branch root as the
Pages artifact and deploys it. No build step, no dependencies.

## Domain

`shotgate.coldqubit.org`, a CNAME to `coldqubit.github.io`, configured in the
repository's Pages settings. The coldqubit project home is at
<https://coldqubit.org>.
