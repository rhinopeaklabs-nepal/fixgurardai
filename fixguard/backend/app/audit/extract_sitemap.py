"""In-page JavaScript for mapping the structure of the site under audit.

This answers "what is this website actually made of" - the pages it links to,
the services it depends on, the libraries it ships, and where its forms send
data. Everything here is observed from the loaded page, never guessed from the
URL or a fingerprint database.
"""

SITE_STRUCTURE = r"""
() => {
  const origin = location.origin;

  const abs = (href) => {
    try { return new URL(href, location.href); } catch (e) { return null; }
  };

  // ---- links, split by where they go -------------------------------------
  const internal = new Map();
  const external = new Map();
  let mailto = 0, tel = 0;

  document.querySelectorAll('a[href]').forEach((a) => {
    const raw = a.getAttribute('href') || '';
    if (/^mailto:/i.test(raw)) { mailto += 1; return; }
    if (/^tel:/i.test(raw))    { tel += 1; return; }
    if (/^(javascript:|#)/i.test(raw)) return;
    const u = abs(raw);
    if (!u) return;
    const label = (a.innerText || '').trim().slice(0, 50);
    if (u.origin === origin) {
      const path = u.pathname || '/';
      if (!internal.has(path)) internal.set(path, { path, label, count: 0 });
      internal.get(path).count += 1;
    } else {
      const host = u.hostname;
      if (!external.has(host)) external.set(host, { host, label, count: 0 });
      external.get(host).count += 1;
    }
  });

  // ---- forms and where they send ----------------------------------------
  const forms = [...document.querySelectorAll('form')].map((f, i) => {
    const action = f.getAttribute('action') || '';
    const target = action ? abs(action) : null;
    const fields = [...f.querySelectorAll('input, textarea, select')]
      .filter((el) => !['submit', 'button', 'reset', 'image']
        .includes((el.getAttribute('type') || '').toLowerCase()))
      .map((el) => ({
        name: el.getAttribute('name') || el.id || '',
        type: (el.getAttribute('type') || el.tagName.toLowerCase()),
        required: el.hasAttribute('required'),
      }));
    const heading = f.closest('section, div, main')?.querySelector('h1,h2,h3,h4');
    return {
      index: i,
      name: (heading && heading.innerText.trim().slice(0, 60)) || f.id || `Form ${i + 1}`,
      method: (f.getAttribute('method') || 'get').toUpperCase(),
      action: action || null,
      action_host: target && target.origin !== origin ? target.hostname : null,
      handled_by_script: !action,
      field_count: fields.length,
      fields: fields.slice(0, 12),
    };
  });

  // ---- content outline ---------------------------------------------------
  const outline = [...document.querySelectorAll('h1,h2,h3')]
    .filter((h) => {
      const s = getComputedStyle(h);
      return s.display !== 'none' && s.visibility !== 'hidden' && h.innerText.trim();
    })
    .slice(0, 30)
    .map((h) => ({ level: Number(h.tagName[1]), text: h.innerText.trim().slice(0, 80) }));

  // ---- what the page ships ----------------------------------------------
  // Detected from globals and script URLs actually present, not guessed.
  const libs = [];
  const seen = new Set();
  const note = (name, how) => {
    if (seen.has(name)) return;
    seen.add(name);
    libs.push({ name, evidence: how });
  };

  if (document.querySelector('#root, #app, [data-reactroot]') || window.React) {
    note('React', window.React ? 'React global' : 'React root element');
  }
  if (window.__NEXT_DATA__) note('Next.js', '__NEXT_DATA__');
  if (window.__NUXT__) note('Nuxt', '__NUXT__');
  if (window.Vue || document.querySelector('[data-v-app], [v-cloak]')) note('Vue', 'Vue marker');
  if (window.angular || document.querySelector('[ng-version]')) note('Angular', 'ng-version');
  if (window.jQuery || window.$ && window.$.fn) {
    note('jQuery', 'jQuery global' + (window.jQuery && window.jQuery.fn
      ? ' v' + window.jQuery.fn.jquery : ''));
  }
  if (window.Alpine) note('Alpine.js', 'Alpine global');
  if (window.htmx) note('htmx', 'htmx global');
  if (window.dataLayer || window.gtag) note('Google Tag Manager / gtag', 'dataLayer');
  if (window.ga || window.GoogleAnalyticsObject) note('Google Analytics', 'ga global');
  if (window.fbq) note('Meta Pixel', 'fbq global');
  if (window.Shopify) note('Shopify', 'Shopify global');
  if (document.querySelector('meta[name="generator"]')) {
    const g = document.querySelector('meta[name="generator"]').getAttribute('content');
    if (g) note(g.slice(0, 40), 'generator meta tag');
  }
  [...document.scripts].forEach((s) => {
    const src = s.src || '';
    if (/tailwind/i.test(src)) note('Tailwind CSS', 'script URL');
    if (/bootstrap/i.test(src)) note('Bootstrap', 'script URL');
    if (/wp-includes|wp-content/i.test(src)) note('WordPress', 'wp- path');
  });
  if (document.querySelector('link[href*="wp-content"], link[href*="wp-includes"]')) {
    note('WordPress', 'wp- stylesheet path');
  }

  // ---- page identity -----------------------------------------------------
  const metaOf = (sel, attr) => {
    const el = document.querySelector(sel);
    return el ? (el.getAttribute(attr || 'content') || '').slice(0, 200) : null;
  };

  return {
    origin,
    path: location.pathname,
    title: (document.title || '').slice(0, 140),
    description: metaOf('meta[name="description"]'),
    og_image: metaOf('meta[property="og:image"]'),
    canonical: metaOf('link[rel="canonical"]', 'href'),
    lang: document.documentElement.getAttribute('lang'),
    has_viewport_meta: !!document.querySelector('meta[name="viewport"]'),
    internal_links: [...internal.values()].sort((a, b) => b.count - a.count).slice(0, 40),
    external_links: [...external.values()].sort((a, b) => b.count - a.count).slice(0, 25),
    mailto_links: mailto,
    tel_links: tel,
    forms,
    outline,
    libraries: libs,
    counts: {
      elements: document.querySelectorAll('*').length,
      images: document.images.length,
      scripts: document.scripts.length,
      stylesheets: document.querySelectorAll('link[rel="stylesheet"]').length,
      iframes: document.querySelectorAll('iframe').length,
    },
  };
}
"""
