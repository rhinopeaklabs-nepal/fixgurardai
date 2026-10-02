// Progressive enhancement only. Every page reads and works with this file
// blocked: the console lines, bars and cards simply appear finished.
(function () {
  var root = document.documentElement;
  root.classList.add("js");

  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Nav: hairline once scrolled, and the phone menu.
  var nav = document.querySelector("[data-nav-root]");
  var onScroll = function () {
    if (nav) nav.classList.toggle("is-scrolled", window.scrollY > 8);
  };
  onScroll();
  window.addEventListener("scroll", onScroll, { passive: true });

  var burger = document.querySelector("[data-burger]");
  var sheet = document.querySelector("[data-sheet]");
  if (burger && sheet) {
    var setOpen = function (open) {
      burger.setAttribute("aria-expanded", String(open));
      burger.setAttribute("aria-label", open ? "Close menu" : "Open menu");
      sheet.hidden = !open;
    };
    burger.addEventListener("click", function () {
      setOpen(burger.getAttribute("aria-expanded") !== "true");
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") setOpen(false);
    });
  }

  // Reveal on scroll, once.
  var targets = document.querySelectorAll(".reveal, .console");
  if (reduced || !("IntersectionObserver" in window)) {
    targets.forEach(function (el) { el.classList.add("is-in"); });
  } else {
    var io = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) return;
          entry.target.classList.add("is-in");
          io.unobserve(entry.target);
          countUp(entry.target);
        });
      },
      { threshold: 0.2 }
    );
    targets.forEach(function (el) { io.observe(el); });
  }

  // Numbers marked data-count climb from zero when their block appears.
  function countUp(scope) {
    if (reduced) return;
    scope.querySelectorAll("[data-count]").forEach(function (el) {
      var to = Number(el.getAttribute("data-count"));
      var delay = scope.classList.contains("console") ? 2600 : 300;
      var t0 = 0;
      el.textContent = "0";
      setTimeout(function () {
        var tick = function (t) {
          if (!t0) t0 = t;
          var p = Math.min(1, (t - t0) / 1400);
          el.textContent = String(Math.round(to * (1 - Math.pow(1 - p, 3))));
          if (p < 1) requestAnimationFrame(tick);
        };
        requestAnimationFrame(tick);
      }, delay);
    });
  }
})();
