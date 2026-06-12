// shotgate docs reader
// Renders the repository's docs/ folder (main branch) in the design-system
// docs surface. Routing is hash-based: #/<slug> or #/<slug>/<heading-id>.
// Markdown comes from raw.githubusercontent.com, is parsed with marked,
// sanitized with DOMPurify, then post-processed (heading ids, link/image
// rewriting, code-block chrome, mermaid, TOC).
(function () {
  'use strict';

  var REPO = 'coldqubit/shotgate';
  var RAW = 'https://raw.githubusercontent.com/' + REPO + '/main/docs/';
  var BLOB = 'https://github.com/' + REPO + '/blob/main/docs/';
  var TREE = 'https://github.com/' + REPO + '/tree/main/docs/';

  // The manifest mirrors docs/README.md. Order = reading order (pager).
  var DOCS = [
    { slug: 'overview', file: 'README.md', title: 'Overview', group: 'Start here' },
    { slug: 'getting-started', file: 'getting-started.md', title: 'Getting started', group: 'Start here' },
    { slug: 'motivation', file: 'motivation.md', title: 'Motivation', group: 'Start here' },
    { slug: 'workflow-spec', file: 'workflow-spec.md', title: 'Workflow specification', group: 'Reference' },
    { slug: 'assertions', file: 'assertions.md', title: 'Assertion catalog', group: 'Reference' },
    { slug: 'architecture', file: 'architecture.md', title: 'Solution architecture', group: 'Architecture' },
    { slug: 'pipeline', file: 'pipeline.md', title: 'Pipeline schema', group: 'Architecture' },
    { slug: 'hardware-validation', file: 'hardware-validation.md', title: 'Hardware validation', group: 'Architecture' }
  ];
  var EXTERNAL = [
    { title: 'ADRs', href: TREE + 'adr' },
    { title: 'Diagrams', href: TREE + 'diagrams' },
    { title: 'Terraform module', href: 'https://github.com/' + REPO + '/blob/main/infra/terraform/README.md' },
    { title: 'KVM/QEMU runner', href: 'https://github.com/' + REPO + '/blob/main/infra/qemu/README.md' },
    { title: 'Contributing', href: 'https://github.com/' + REPO + '/blob/main/CONTRIBUTING.md' }
  ];

  var byFile = {}, bySlug = {};
  DOCS.forEach(function (d) { byFile[d.file.toLowerCase()] = d; bySlug[d.slug] = d; });

  var $article = document.getElementById('article');
  var $sidebar = document.getElementById('sidebar');
  var $toc = document.getElementById('toc');
  var tocObserver = null;
  var mermaidReady = null;

  /* ---------- helpers ---------- */

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  // GitHub-compatible heading slugs: lowercase, drop markdown emphasis marks,
  // keep word chars (underscores included, so ibm_fez stays ibm_fez), collapse
  // every other run to a single hyphen, trim. Matches the anchors GitHub mints
  // for the same docs/*.md headings, so deep links are portable both ways.
  function slugify(text) {
    return text.toLowerCase().replace(/[`*]/g, '').replace(/[^\wÀ-￿]+/g, '-').replace(/^-+|-+$/g, '');
  }

  var BAR_OFFSET = 72; // sticky docbar (60px) + a little breathing room

  // Resolve a heading by id, tolerant of legacy/variant anchors: if the exact id
  // is gone, match ignoring underscore/hyphen differences so older shared links
  // still land (e.g. an old ibmfez slug now minted as ibm_fez).
  function findAnchor(anchor) {
    var t = document.getElementById(anchor);
    if (t) return t;
    var norm = anchor.replace(/[_-]+/g, '-');
    var all = $article.querySelectorAll('[id]');
    for (var i = 0; i < all.length; i++) {
      if (all[i].id.replace(/[_-]+/g, '-') === norm) return all[i];
    }
    return null;
  }

  // Scroll a heading to just below the sticky bar. Uses an absolute window
  // offset rather than scrollIntoView(), which is unreliable under a sticky
  // header. Returns true if the target was found.
  function scrollToAnchor(anchor) {
    if (!anchor) { window.scrollTo(0, 0); return true; }
    var t = findAnchor(anchor);
    if (t) {
      var y = t.getBoundingClientRect().top + window.pageYOffset - BAR_OFFSET;
      window.scrollTo(0, Math.max(0, y));
    }
    return !!t;
  }

  // Land a deep-link anchor and keep it landed through async reflow: the brand
  // faces (IBM Plex) load after first paint and the mono is wide, so headings
  // re-wrap and the target drifts. Re-scroll on a short settle sequence and on
  // document.fonts.ready, each guarded against the user navigating away.
  function landAnchor(slug) {
    if (!pendingAnchor) { window.scrollTo(0, 0); return; }
    scrollToAnchor(pendingAnchor);
    [60, 180, 400].forEach(function (d) {
      setTimeout(function () {
        if (currentSlug === slug && pendingAnchor) scrollToAnchor(pendingAnchor);
      }, d);
    });
    if (document.fonts && document.fonts.ready) {
      document.fonts.ready.then(function () {
        if (currentSlug === slug && pendingAnchor) scrollToAnchor(pendingAnchor);
      });
    }
  }

  function fetchDoc(file) {
    var key = 'sgdocs:' + file;
    try {
      var hit = JSON.parse(sessionStorage.getItem(key));
      if (hit && Date.now() - hit.t < 10 * 60 * 1000) return Promise.resolve(hit.v);
    } catch (e) { /* network */ }
    return fetch(RAW + file).then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.text();
    }).then(function (v) {
      try { sessionStorage.setItem(key, JSON.stringify({ t: Date.now(), v: v })); } catch (e) { /* quota */ }
      return v;
    });
  }

  /* ---------- sidebar ---------- */

  function buildSidebar(activeSlug) {
    $sidebar.textContent = '';
    var groups = [];
    var seen = {};
    DOCS.forEach(function (d) {
      if (!seen[d.group]) { seen[d.group] = { name: d.group, items: [] }; groups.push(seen[d.group]); }
      seen[d.group].items.push(d);
    });
    groups.forEach(function (g) {
      var box = el('div', 'nav-group');
      box.appendChild(el('h5', null, g.name));
      g.items.forEach(function (d) {
        var a = el('a', 'nav-item' + (d.slug === activeSlug ? ' active' : ''), d.title);
        a.href = '#/' + d.slug;
        box.appendChild(a);
      });
      $sidebar.appendChild(box);
    });
    var ext = el('div', 'nav-group');
    ext.appendChild(el('h5', null, 'On GitHub'));
    EXTERNAL.forEach(function (x) {
      var a = el('a', 'nav-item ext');
      a.href = x.href; a.target = '_blank'; a.rel = 'noopener';
      a.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 3h6v6"></path><path d="M10 14 21 3"></path><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path></svg>';
      a.appendChild(document.createTextNode(x.title));
      ext.appendChild(a);
    });
    $sidebar.appendChild(ext);
  }

  /* ---------- post-processing ---------- */

  function rewriteLink(href, doc) {
    if (!href || /^(https?:|mailto:)/.test(href)) return href;
    if (href.charAt(0) === '#') return '#/' + doc.slug + '/' + href.slice(1); // in-page anchor
    var clean = href.replace(/^\.\//, '');
    var m = clean.match(/^([\w./-]+?\.md)(#.*)?$/i);
    if (m) {
      var base = m[1].split('/').pop().toLowerCase();
      var target = byFile[base];
      // only same-folder links map to local routes; subfolder/parent ones go to GitHub
      if (target && m[1].indexOf('/') === -1) {
        return '#/' + target.slug + (m[2] ? '/' + m[2].slice(1) : '');
      }
    }
    if (clean.indexOf('../') === 0) return 'https://github.com/' + REPO + '/blob/main/' + clean.replace(/^(\.\.\/)+/, '');
    return BLOB + clean; // adr/…, diagrams/…, anything else in docs/
  }

  function process(doc) {
    // heading ids + anchors
    var headings = $article.querySelectorAll('h2, h3, h4');
    var used = {};
    headings.forEach(function (h) {
      var id = slugify(h.textContent);
      while (used[id]) id += '-x';
      used[id] = true;
      h.id = id;
    });

    // links + images
    $article.querySelectorAll('a[href]').forEach(function (a) {
      var href = a.getAttribute('href');
      var out = rewriteLink(href, doc);
      a.setAttribute('href', out);
      if (/^https?:/.test(out)) { a.target = '_blank'; a.rel = 'noopener'; }
    });
    $article.querySelectorAll('img[src]').forEach(function (img) {
      var src = img.getAttribute('src');
      if (!/^(https?:|data:)/.test(src)) img.setAttribute('src', RAW + src.replace(/^\.\//, ''));
      img.loading = 'lazy';
    });

    // code blocks: chrome bar + mermaid
    var mermaidNodes = [];
    $article.querySelectorAll('pre > code').forEach(function (code) {
      var pre = code.parentNode;
      var lang = (code.className.match(/language-([\w-]+)/) || [])[1] || '';
      if (lang === 'mermaid') {
        var wrap = el('div', 'mermaid-wrap');
        var target = el('div', 'mermaid');
        target.textContent = code.textContent;
        wrap.appendChild(target);
        pre.replaceWith(wrap);
        mermaidNodes.push(target);
        return;
      }
      var box = el('div', 'code');
      var head = el('div', 'code-head');
      head.appendChild(el('span', 'dot'));
      head.appendChild(el('span', 'lang', lang || 'text'));
      pre.replaceWith(box);
      box.appendChild(head);
      box.appendChild(pre);
    });
    if (mermaidNodes.length) renderMermaid(mermaidNodes);
  }

  function renderMermaid(nodes) {
    if (!mermaidReady) {
      mermaidReady = new Promise(function (resolve, reject) {
        var s = document.createElement('script');
        s.src = 'https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js';
        s.onload = function () {
          window.mermaid.initialize({ startOnLoad: false, theme: 'dark', themeVariables: { fontFamily: 'IBM Plex Mono, monospace' } });
          resolve();
        };
        s.onerror = reject;
        document.head.appendChild(s);
      });
    }
    mermaidReady.then(function () {
      return window.mermaid.run({ nodes: nodes });
    }).then(function () {
      // diagrams change the page height; re-land any pending deep-link anchor
      if (pendingAnchor) scrollToAnchor(pendingAnchor);
    }).catch(function () { /* the raw definition stays visible as text */ });
  }

  /* ---------- TOC ---------- */

  function buildToc() {
    $toc.textContent = '';
    if (tocObserver) { tocObserver.disconnect(); tocObserver = null; }
    var hs = $article.querySelectorAll('h2');
    if (hs.length < 2) return;
    $toc.appendChild(el('h6', null, 'On this page'));
    var links = {};
    hs.forEach(function (h) {
      var a = el('a', null, h.textContent);
      a.href = '#' + location.hash.replace(/^#/, '').split('/').slice(0, 2).join('/') + '/' + h.id;
      a.dataset.target = h.id;
      a.addEventListener('click', function (ev) {
        ev.preventDefault();
        h.scrollIntoView({ behavior: 'smooth' });
        history.replaceState(null, '', a.getAttribute('href'));
      });
      $toc.appendChild(a);
      links[h.id] = a;
    });
    if ('IntersectionObserver' in window) {
      var current = null;
      tocObserver = new IntersectionObserver(function (entries) {
        entries.forEach(function (en) {
          if (en.isIntersecting) {
            if (current) current.classList.remove('active');
            current = links[en.target.id];
            if (current) current.classList.add('active');
          }
        });
      }, { rootMargin: '-60px 0px -70% 0px' });
      hs.forEach(function (h) { tocObserver.observe(h); });
    }
  }

  /* ---------- pager + crumb ---------- */

  function buildChrome(doc) {
    var crumb = el('div', 'crumb');
    crumb.appendChild(el('span', null, 'docs / ' + doc.file));
    var src = el('a', 'src', 'view source on GitHub');
    src.href = BLOB + doc.file; src.target = '_blank'; src.rel = 'noopener';
    crumb.appendChild(src);
    $article.insertBefore(crumb, $article.firstChild);

    var i = DOCS.indexOf(doc);
    var pager = el('nav', 'pager');
    if (i > 0) {
      var prev = el('a', 'prev');
      prev.href = '#/' + DOCS[i - 1].slug;
      prev.appendChild(el('div', 'dir', '← previous'));
      prev.appendChild(el('div', 'ttl', DOCS[i - 1].title));
      pager.appendChild(prev);
    }
    if (i < DOCS.length - 1) {
      var next = el('a', 'next');
      next.href = '#/' + DOCS[i + 1].slug;
      next.appendChild(el('div', 'dir', 'next →'));
      next.appendChild(el('div', 'ttl', DOCS[i + 1].title));
      pager.appendChild(next);
    }
    if (pager.children.length) $article.appendChild(pager);
  }

  /* ---------- router ---------- */

  function parseHash() {
    var h = location.hash.replace(/^#\/?/, '');
    var parts = h.split('/');
    return { slug: parts[0] || DOCS[0].slug, anchor: parts.slice(1).join('/') || null };
  }

  var currentSlug = null;
  var pendingAnchor = null;

  function route() {
    var r = parseHash();
    var doc = bySlug[r.slug] || DOCS[0];
    pendingAnchor = r.anchor;
    document.body.classList.remove('nav-open');
    document.getElementById('nav-toggle').setAttribute('aria-expanded', 'false');
    if (doc.slug === currentSlug) {
      scrollToAnchor(r.anchor);
      return;
    }
    currentSlug = doc.slug;
    buildSidebar(doc.slug);
    document.title = 'shotgate docs · ' + doc.title.toLowerCase();
    $article.innerHTML = '<div class="loading mono">fetching ' + doc.file + ' from main …</div>';
    $toc.textContent = '';

    fetchDoc(doc.file).then(function (md) {
      if (currentSlug !== doc.slug) return; // user navigated away mid-fetch
      var html = window.marked.parse(md, { mangle: false, headerIds: false });
      $article.innerHTML = window.DOMPurify.sanitize(html, { ADD_ATTR: ['target'] });
      process(doc);
      buildChrome(doc);
      buildToc();
      landAnchor(doc.slug);
    }).catch(function (err) {
      if (currentSlug !== doc.slug) return;
      $article.innerHTML = '';
      var box = el('div', 'callout warn load-err');
      box.innerHTML = '<div class="callout-body"><strong>Could not load ' + doc.file + '</strong> (' + (err && err.message ? err.message : 'network error') + '). Read it directly on <a href="' + BLOB + doc.file + '" target="_blank" rel="noopener">GitHub</a> instead.</div>';
      $article.appendChild(box);
    });
  }

  /* ---------- chrome behaviour ---------- */

  // theme toggle, persisted
  var THEME_KEY = 'sg-theme';
  try {
    if (localStorage.getItem(THEME_KEY) === 'light') document.documentElement.setAttribute('data-theme', 'light');
  } catch (e) { /* private mode */ }
  document.getElementById('theme-toggle').addEventListener('click', function () {
    var root = document.documentElement;
    var light = root.getAttribute('data-theme') === 'light';
    if (light) root.removeAttribute('data-theme'); else root.setAttribute('data-theme', 'light');
    try { localStorage.setItem(THEME_KEY, light ? 'dark' : 'light'); } catch (e) { /* ignore */ }
  });

  // mobile nav toggle
  document.getElementById('nav-toggle').addEventListener('click', function () {
    var open = document.body.classList.toggle('nav-open');
    this.setAttribute('aria-expanded', String(open));
  });

  window.addEventListener('hashchange', route);
  route();
})();
