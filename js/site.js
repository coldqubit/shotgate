// shotgate.coldqubit.org · surface behavior
// Two effects only: the scroll-reveal navbar name and the hero terminal demo.

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
