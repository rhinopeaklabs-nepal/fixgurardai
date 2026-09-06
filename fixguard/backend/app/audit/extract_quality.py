"""In-page JavaScript for the quality detectors: performance, accessibility,
and mobile layout.

Kept separate from ``extract_js`` so the audit-correctness checks and the
quality checks can be read independently.
"""

# --------------------------------------------------------------------------
# Core Web Vitals. Installed as an init script so the observers are watching
# before first paint - otherwise LCP and CLS have already happened.
# --------------------------------------------------------------------------
INSTALL_VITALS = r"""
(() => {
  if (window.__fgVitals) return;
  const v = { lcp: 0, cls: 0, fcp: 0, longTasks: 0, longTaskMs: 0 };
  window.__fgVitals = v;
  const obs = (type, cb) => {
    try {
      new PerformanceObserver(cb).observe({ type, buffered: true });
    } catch (e) { /* entry type unsupported here */ }
  };
  obs('largest-contentful-paint', (l) => {
    for (const e of l.getEntries()) v.lcp = Math.max(v.lcp, e.startTime);
  });
  obs('layout-shift', (l) => {
    for (const e of l.getEntries()) if (!e.hadRecentInput) v.cls += e.value;
  });
  obs('paint', (l) => {
    for (const e of l.getEntries()) {
      if (e.name === 'first-contentful-paint') v.fcp = e.startTime;
    }
  });
  obs('longtask', (l) => {
    for (const e of l.getEntries()) {
      v.longTasks += 1;
      // Total Blocking Time counts only the part of a task beyond 50ms.
      v.longTaskMs += Math.max(0, e.duration - 50);
    }
  });
})();
"""

READ_VITALS = r"""
() => {
  const v = window.__fgVitals || { lcp: 0, cls: 0, fcp: 0, longTasks: 0, longTaskMs: 0 };
  const nav = performance.getEntriesByType('navigation')[0] || {};
  const round = (n) => (typeof n === 'number' && isFinite(n) ? Math.round(n) : null);
  return {
    lcp_ms: round(v.lcp),
    fcp_ms: round(v.fcp),
    cls: Math.round((v.cls || 0) * 1000) / 1000,
    tbt_ms: round(v.longTaskMs),
    long_tasks: v.longTasks,
    ttfb_ms: round(nav.responseStart),
    dom_content_loaded_ms: round(nav.domContentLoadedEventEnd),
    load_ms: round(nav.loadEventEnd),
    transfer_bytes: nav.transferSize || 0,
    dom_nodes: document.querySelectorAll('*').length,
  };
}
"""

# --------------------------------------------------------------------------
# Accessibility. Only checks things decidable from the DOM without judgement,
# so every finding is defensible rather than a matter of opinion.
# --------------------------------------------------------------------------
A11Y_AUDIT = r"""
() => {
  const issues = [];
  const describe = (el) => {
    if (!el) return '';
    if (el.id) return '#' + el.id;
    const cls = (typeof el.className === 'string' && el.className.trim())
      ? '.' + el.className.trim().split(/\s+/)[0] : '';
    return el.tagName.toLowerCase() + cls;
  };
  const add = (rule, impact, message, el, extra) => {
    if (issues.length >= 60) return;
    issues.push(Object.assign({
      rule, impact, message,
      selector: describe(el),
      snippet: el ? (el.outerHTML || '').slice(0, 120) : '',
    }, extra || {}));
  };
  const visible = (el) => {
    const s = getComputedStyle(el);
    if (s.display === 'none' || s.visibility === 'hidden') return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };

  // 1. Images with no alternative text.
  document.querySelectorAll('img').forEach((img) => {
    if (visible(img) && img.getAttribute('alt') === null) {
      add('img-alt', 'serious',
          'Image has no alt attribute, so screen readers read out its file name.', img);
    }
  });

  // 2. Form controls with no accessible name.
  document.querySelectorAll('input, textarea, select').forEach((el) => {
    const type = (el.getAttribute('type') || '').toLowerCase();
    if (['hidden', 'submit', 'button', 'reset', 'image'].indexOf(type) !== -1) return;
    if (!visible(el)) return;
    const named =
      (el.id && document.querySelector('label[for="' + CSS.escape(el.id) + '"]')) ||
      el.closest('label') ||
      el.getAttribute('aria-label') ||
      el.getAttribute('aria-labelledby') ||
      el.getAttribute('title');
    if (!named) {
      add('form-label', 'critical',
          'Form field has no label, so its purpose is never announced.', el);
    }
  });

  // 3. Controls with no discernible text.
  document.querySelectorAll('button, a[href], [role="button"]').forEach((el) => {
    if (!visible(el)) return;
    const img = el.querySelector('img');
    const name = (el.innerText || '').trim() ||
      el.getAttribute('aria-label') ||
      el.getAttribute('title') ||
      (img && img.getAttribute('alt'));
    if (!name) {
      add('empty-control', 'serious',
          'Control has no text, so it is announced only as "button" or "link".', el);
    }
  });

  // 4. Document language.
  if (!document.documentElement.getAttribute('lang')) {
    add('html-lang', 'serious',
        'The page declares no language, so screen readers may use the wrong voice.',
        document.documentElement);
  }

  // 5. Document title.
  if (!(document.title || '').trim()) {
    add('page-title', 'serious', 'The page has no title.', null);
  }

  // 6. Heading structure.
  const heads = [].slice.call(
    document.querySelectorAll('h1,h2,h3,h4,h5,h6')).filter(visible);
  const h1s = heads.filter((h) => h.tagName === 'H1');
  if (heads.length > 0 && h1s.length === 0) {
    add('heading-order', 'moderate', 'The page has headings but no <h1>.', heads[0]);
  } else if (h1s.length > 1) {
    add('heading-order', 'moderate',
        'The page has ' + h1s.length + ' <h1> headings; there should be one.', h1s[1]);
  }
  let prev = 0;
  for (const h of heads) {
    const lvl = Number(h.tagName[1]);
    if (prev && lvl > prev + 1) {
      add('heading-order', 'moderate',
          'Heading level jumps from h' + prev + ' to h' + lvl +
          ', which breaks the page outline.', h);
      break;
    }
    prev = lvl;
  }

  // 7. Duplicate ids break label-for and every aria reference.
  const seen = {}, dupes = [];
  document.querySelectorAll('[id]').forEach((el) => {
    if (seen[el.id]) { if (dupes.indexOf(el.id) === -1) dupes.push(el.id); }
    else seen[el.id] = 1;
  });
  dupes.slice(0, 5).forEach((id) => {
    add('duplicate-id', 'moderate', 'The id "' + id + '" is used more than once.', null);
  });

  // 8. Contrast against the nearest opaque ancestor background.
  const parseRGB = (s) => {
    const m = (s || '').match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const p = m[1].split(',').map(parseFloat);
    return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 };
  };
  const lum = (c) => {
    const f = (v) => {
      v /= 255;
      return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
    };
    return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b);
  };
  // Returns null when no ancestor declares an opaque background. The previous
  // version assumed white, which is usually right for body text and exactly
  // wrong for light text: white-on-assumed-white measures 1.07:1 and gets
  // reported as a serious failure on markup that is perfectly readable. Four
  // such findings appeared on this project's own sign-in page, all of them
  // white text sitting on a dark panel.
  const bgOf = (el) => {
    let n = el;
    while (n && n.nodeType === 1) {
      const c = parseRGB(getComputedStyle(n).backgroundColor);
      if (c && c.a > 0.5) return c;
      n = n.parentElement;
    }
    return null;
  };

  // Opacity on any ancestor makes text render lighter than its own colour
  // says, and the audit runs while a page with scroll-reveal animations is
  // still fading its sections in. Ignoring that reported text at a genuine
  // 5.5:1 as a 3.6:1 failure - fourteen of them on one site, thirteen of
  // which did not exist. Confident false findings are the most expensive
  // thing this tool can produce, so the effective colour is composited
  // through the cumulative opacity before anything is measured.
  const effectiveAlpha = (el) => {
    let a = 1, n = el;
    while (n && n.nodeType === 1) {
      const o = parseFloat(getComputedStyle(n).opacity);
      if (!isNaN(o)) a *= o;
      n = n.parentElement;
    }
    return a;
  };
  const composite = (fg, bg, a) => ({
    r: fg.r * a + bg.r * (1 - a),
    g: fg.g * a + bg.g * (1 - a),
    b: fg.b * a + bg.b * (1 - a),
    a: 1,
  });

  let checked = 0;
  const textish = document.querySelectorAll(
    'p,span,a,li,h1,h2,h3,h4,h5,h6,label,button,td');
  for (const el of textish) {
    if (checked >= 120) break;
    if (!visible(el)) continue;
    if (el.children.length > 0) continue;
    if (!(el.textContent || '').trim()) continue;
    const s = getComputedStyle(el);
    const fg = parseRGB(s.color);
    if (!fg) continue;
    // Text mid-fade is not a contrast failure; it is a moment. Skipped
    // before the budget is spent, or a page that animates everything would
    // burn all 120 checks on elements it then declines to judge.
    const alpha = effectiveAlpha(el) * (fg.a === undefined ? 1 : fg.a);
    if (alpha < 0.85) continue;
    let bg = bgOf(el);
    if (!bg) {
      // Nothing up the tree declared an opaque background. Assuming white is
      // right for dark text on a plain page, which is the common case and
      // worth keeping. It is exactly wrong for light text: white-on-assumed-
      // white measures about 1.07:1 and gets reported as serious on markup
      // that is perfectly readable, which is what happened to four elements
      // of white text on this project's own sign-in page. When the text is
      // light and the background is unknown, say nothing.
      if (lum(fg) > 0.5) continue;
      bg = { r: 255, g: 255, b: 255, a: 1 };
    }
    checked += 1;
    const shown = composite(fg, bg, alpha);
    const l1 = lum(shown), l2 = lum(bg);
    const ratio = (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
    const size = parseFloat(s.fontSize);
    const bold = parseInt(s.fontWeight, 10) >= 700;
    const large = size >= 24 || (size >= 18.66 && bold);
    const need = large ? 3 : 4.5;
    if (ratio < need) {
      add('contrast', 'serious',
          'Text contrast is ' + ratio.toFixed(2) + ':1 against its background; ' +
          need + ':1 is the minimum at this size.',
          el, { ratio: Math.round(ratio * 100) / 100, required: need });
    }
  }

  return { issues: issues, contrast_samples: checked };
}
"""

# --------------------------------------------------------------------------
# Mobile layout. Run with the viewport already emulated at phone width.
# --------------------------------------------------------------------------
MOBILE_AUDIT = r"""
() => {
  const vw = window.innerWidth;
  const docW = document.documentElement.scrollWidth;
  const issues = [];
  const describe = (el) => {
    if (!el) return '';
    if (el.id) return '#' + el.id;
    const cls = (typeof el.className === 'string' && el.className.trim())
      ? '.' + el.className.trim().split(/\s+/)[0] : '';
    return el.tagName.toLowerCase() + cls;
  };
  const add = (rule, impact, message, el, extra) => {
    if (issues.length >= 40) return;
    issues.push(Object.assign({
      rule, impact, message,
      selector: describe(el),
      snippet: el ? (el.outerHTML || '').slice(0, 100) : '',
    }, extra || {}));
  };
  const visible = (el) => {
    const s = getComputedStyle(el);
    if (s.display === 'none' || s.visibility === 'hidden') return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };

  // 1. Without a viewport meta, phones render the desktop layout shrunk down.
  const meta = document.querySelector('meta[name="viewport"]');
  if (!meta) {
    add('viewport-meta', 'critical',
        'No viewport meta tag, so phones render the desktop layout zoomed out.', null);
  } else {
    const c = (meta.getAttribute('content') || '').toLowerCase();
    if (/user-scalable\s*=\s*no/.test(c) || /maximum-scale\s*=\s*1(\.0)?\b/.test(c)) {
      add('viewport-zoom', 'serious',
          'The viewport tag blocks pinch-zoom, which people with low vision rely on.',
          meta);
    }
  }

  // 2. Content wider than the screen forces sideways scrolling.
  if (docW > vw + 2) {
    const wide = [].slice.call(document.querySelectorAll('body *'))
      .filter((el) => visible(el) && el.getBoundingClientRect().right > vw + 2)
      .sort((a, b) => b.getBoundingClientRect().right - a.getBoundingClientRect().right)
      .slice(0, 3);
    add('horizontal-overflow', 'critical',
        'The page is ' + docW + 'px wide on a ' + vw + 'px screen, so it scrolls sideways.',
        wide[0] || null, { page_width: docW, viewport_width: vw });
    wide.slice(1).forEach((el) => {
      add('horizontal-overflow', 'serious',
          'This element reaches ' + Math.round(el.getBoundingClientRect().right) +
          'px, past the ' + vw + 'px screen edge.', el);
    });
  }

  // 3. Tap targets below roughly 44px are hard to hit accurately.
  const placed = {};
  document.querySelectorAll('a[href], button, input[type=submit], [role="button"]')
    .forEach((el) => {
      if (!visible(el)) return;
      const r = el.getBoundingClientRect();
      const key = Math.round(r.top) + ':' + Math.round(r.left);
      if (placed[key]) return;
      if (r.height < 44 || r.width < 24) {
        placed[key] = 1;
        add('tap-target', 'moderate',
            'Tap target is ' + Math.round(r.width) + 'x' + Math.round(r.height) +
            'px; 44px tall is the usual minimum.', el,
            { width: Math.round(r.width), height: Math.round(r.height) });
      }
    });

  // 4. Body text under 12px is unreadable on a phone.
  let small = 0, sample = null;
  document.querySelectorAll('p, li, span, td, label').forEach((el) => {
    if (!visible(el) || !(el.textContent || '').trim()) return;
    const size = parseFloat(getComputedStyle(el).fontSize);
    if (size && size < 12) { small += 1; if (!sample) sample = el; }
  });
  if (small) {
    add('small-text', 'moderate',
        small + ' text element(s) render below 12px on a phone.', sample);
  }

  return { issues: issues, viewport_width: vw, page_width: docW };
}
"""
