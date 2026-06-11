# shotgate · website (`web` branch)

This orphan branch holds the **shotgate** website, served by GitHub Pages at
<https://shotgate.coldqubit.org>. It shares no history with `main`: the product
lives on `main`, the site lives here.

## Structure

```
index.html                  the landing page (single surface)
404.html                    branded not-found page
styles/
  styles.css                design-system entry point (fonts + tokens + components)
  fonts.css                 brand faces (IBM Plex Mono + Sans, Google Fonts)
  colors_and_type.css       token layer (color, type, spacing, radii, motion)
  components.css            canonical component classes
  site.css                  page-level styles for this surface only
js/site.js                  scroll-reveal navbar name + hero terminal demo
assets/                     logomark SVG + PNG favicons
.github/workflows/pages.yml deploy workflow (Pages in GitHub Actions mode)
```

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
