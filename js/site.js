// shotgate.coldqubit.org · surface behavior
// Three effects: the scroll-reveal navbar name, the hero terminal demo, and
// the repo-synced hero badges.

// Navbar name appears only while the hero "shotgate" is off screen.
(function () {
  var nav = document.getElementById('topnav');
  var heroName = document.querySelector('.hero h1');
  if (nav && heroName && 'IntersectionObserver' in window) {
    new IntersectionObserver(function (entries) {
      nav.classList.toggle('scrolled', !entries[0].isIntersecting);
    }, { threshold: 0 }).observe(heroName);
  }
})();

// Hero terminal: type the command, then reveal the report.
(function () {
  var cmd = 'shotgate run examples/bell-state/workflow.yaml';
  var typed = document.getElementById('typed');
  var cursor = document.getElementById('cursor');
  var report = document.getElementById('report');
  if (!typed || !cursor || !report) return;
  var reduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (reduced) { typed.textContent = cmd; report.hidden = false; cursor.remove(); return; }
  var i = 0;
  var id = setInterval(function () {
    i += 1;
    typed.textContent = cmd.slice(0, i);
    if (i >= cmd.length) {
      clearInterval(id);
      setTimeout(function () { report.hidden = false; cursor.remove(); }, 450);
    }
  }, 34);
})();

// Hero badges, synced with the repo. The HTML values are static fallbacks;
// anything that fails (offline, rate limit) keeps the baked-in value.
// Responses cache in sessionStorage for 10 minutes to respect the
// unauthenticated GitHub API limit (60 req/h per IP).
(function () {
  var REPO = 'coldqubit/shotgate';
  var API = 'https://api.github.com/repos/' + REPO;
  var RAW = 'https://raw.githubusercontent.com/' + REPO + '/main/';
  var TTL = 10 * 60 * 1000;

  function cached(url, asText) {
    var key = 'sg:' + url;
    try {
      var hit = JSON.parse(sessionStorage.getItem(key));
      if (hit && Date.now() - hit.t < TTL) return Promise.resolve(hit.v);
    } catch (e) { /* fall through to network */ }
    return fetch(url).then(function (r) {
      if (!r.ok) throw new Error(String(r.status));
      return asText ? r.text() : r.json();
    }).then(function (v) {
      try { sessionStorage.setItem(key, JSON.stringify({ t: Date.now(), v: v })); } catch (e) { /* quota */ }
      return v;
    });
  }

  function setBadge(id, value, color) {
    var el = document.querySelector('#' + id + ' .v');
    if (!el || !value) return;
    el.textContent = value;
    if (color) el.className = 'v ' + color;
  }

  // CI: conclusion of the latest completed ci.yml run on main.
  cached(API + '/actions/workflows/ci.yml/runs?branch=main&status=completed&per_page=1').then(function (r) {
    var run = r.workflow_runs && r.workflow_runs[0];
    if (!run || !run.conclusion) return;
    var ok = run.conclusion === 'success';
    setBadge('b-ci', ok ? 'passing' : run.conclusion, ok ? 'green' : 'red');
  }).catch(function () {});

  // Release: latest tag.
  cached(API + '/releases/latest').then(function (r) {
    if (r.tag_name) setBadge('b-release', r.tag_name);
  }).catch(function () {});

  // License: SPDX id from the repo.
  cached(API).then(function (r) {
    var spdx = r.license && r.license.spdx_id;
    if (spdx && spdx !== 'NOASSERTION') setBadge('b-license', spdx);
  }).catch(function () {});

  // Python floor + dev status, from pyproject.toml on main.
  cached(RAW + 'pyproject.toml', true).then(function (t) {
    var py = t.match(/requires-python\s*=\s*"\s*>=\s*([\d.]+)/);
    if (py) setBadge('b-python', py[1] + '+');
    var st = t.match(/Development Status :: \d+ - ([A-Za-z/ ]+)"/);
    if (st) {
      var stage = st[1].trim().toLowerCase();
      setBadge('b-status', stage, /alpha|planning|pre/.test(stage) ? 'amber' : 'green');
    }
  }).catch(function () {});
})();
