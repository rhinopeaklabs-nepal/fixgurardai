// Progressive enhancement only. With this file blocked every page reads
// and works: the console, bars, pins and cards simply appear finished.
(function () {
  var root = document.documentElement;
  root.classList.add("js");

  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Island: firmer shadow once the page has moved.
  var nav = document.querySelector("[data-nav-root]");
  var onScroll = function () {
    if (nav) nav.classList.toggle("is-scrolled", window.scrollY > 12);
  };
  onScroll();
  window.addEventListener("scroll", onScroll, { passive: true });

  // Full-screen menu on phones: scroll lock, Escape, closes on navigation.
  var burger = document.querySelector("[data-burger]");
  var sheet = document.querySelector("[data-sheet]");
  if (burger && sheet) {
    var setOpen = function (open) {
      burger.setAttribute("aria-expanded", String(open));
      burger.setAttribute("aria-label", open ? "Close menu" : "Open menu");
      sheet.hidden = !open;
      document.body.style.overflow = open ? "hidden" : "";
    };
    burger.addEventListener("click", function () {
      setOpen(burger.getAttribute("aria-expanded") !== "true");
    });
    sheet.addEventListener("click", function (e) {
      if (e.target.closest("a")) setOpen(false);
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") setOpen(false);
    });
  }

  // Reveal on scroll, once. The hero visual plays its sequence the same way.
  var targets = document.querySelectorAll(".reveal, .hero-visual, .shot, .pipeline");
  if (reduced || !("IntersectionObserver" in window)) {
    targets.forEach(function (el) { el.classList.add("is-in"); });
    return;
  }

  var io = new IntersectionObserver(
    function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("is-in");
        io.unobserve(entry.target);
        countUp(entry.target);
      });
    },
    { threshold: 0.18 }
  );
  targets.forEach(function (el) { io.observe(el); });

  // Numbers marked data-count climb from zero when their block appears.
  function countUp(scope) {
    scope.querySelectorAll("[data-count]").forEach(function (el) {
      var to = Number(el.getAttribute("data-count"));
      var delay = scope.classList.contains("hero-visual") ? 2900 : 250;
      var t0 = 0;
      el.textContent = "0";
      setTimeout(function () {
        var tick = function (t) {
          if (!t0) t0 = t;
          var p = Math.min(1, (t - t0) / 1300);
          el.textContent = String(Math.round(to * (1 - Math.pow(1 - p, 3))));
          if (p < 1) requestAnimationFrame(tick);
        };
        requestAnimationFrame(tick);
      }, delay);
    });
  }
})();
