"""In-page JavaScript used by the audit engine.

Each form and field is stamped with a ``data-fixguard-*`` attribute so the
Python side can address elements by a stable selector instead of guessing at
CSS paths that break on re-render.
"""

# Stamps every form/field and returns structured descriptors.
EXTRACT_FORMS = r"""
() => {
  const labelFor = (el) => {
    if (el.id) {
      const l = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
      if (l) return l.innerText.trim().slice(0, 120);
    }
    const wrap = el.closest('label');
    if (wrap) return wrap.innerText.trim().slice(0, 120);
    const aria = el.getAttribute('aria-label');
    if (aria) return aria.trim().slice(0, 120);
    return '';
  };

  const visible = (el) => {
    const r = el.getBoundingClientRect();
    const s = getComputedStyle(el);
    return s.display !== 'none' && s.visibility !== 'hidden' &&
           (r.width > 0 || r.height > 0 || el.type === 'hidden');
  };

  const forms = Array.from(document.querySelectorAll('form'));
  const out = [];

  forms.forEach((form, fi) => {
    form.setAttribute('data-fixguard-form', String(fi));

    const controls = Array.from(
      form.querySelectorAll('input, textarea, select')
    );
    const fields = [];

    controls.forEach((el, ci) => {
      const tag = el.tagName.toLowerCase();
      const type = (el.getAttribute('type') || (tag === 'select' ? 'select' : 'text'))
                     .toLowerCase();
      if (['submit', 'button', 'image', 'reset'].includes(type)) return;

      const fid = `${fi}-${ci}`;
      el.setAttribute('data-fixguard-field', fid);

      const options = tag === 'select'
        ? Array.from(el.options)
            .map(o => ({ value: o.value, text: (o.text || '').trim() }))
            .filter(o => o.value !== '')
        : [];

      fields.push({
        fid,
        tag,
        type,
        name: el.getAttribute('name') || '',
        id: el.id || '',
        placeholder: el.getAttribute('placeholder') || '',
        autocomplete: el.getAttribute('autocomplete') || '',
        label: labelFor(el),
        required: el.hasAttribute('required'),
        visible: visible(el),
        options,
      });
    });

    // Locate a plausible submit control.
    let submit = form.querySelector(
      'button[type="submit"], input[type="submit"], button:not([type])'
    );
    if (!submit) {
      const candidates = Array.from(
        form.querySelectorAll('button, a[role="button"], div[role="button"]')
      );
      submit = candidates.find(b =>
        /send|submit|sign up|subscribe|book|request|get in touch|contact|apply/i
          .test(b.innerText || b.value || '')
      ) || candidates[0] || null;
    }
    if (submit) submit.setAttribute('data-fixguard-submit', String(fi));

    out.push({
      index: fi,
      action: form.getAttribute('action') || '',
      method: (form.getAttribute('method') || 'get').toLowerCase(),
      id: form.id || '',
      name: form.getAttribute('name') || '',
      field_count: fields.length,
      fields,
      has_submit: !!submit,
      submit_text: submit ? (submit.innerText || submit.value || '').trim().slice(0, 80) : '',
      visible: visible(form),
      heading: (() => {
        const h = form.closest('section, div, main')?.querySelector('h1,h2,h3,h4');
        return h ? h.innerText.trim().slice(0, 100) : '';
      })(),
    });
  });

  return out;
}
"""

# Visible text snapshot, used to diff before/after a submit.
VISIBLE_TEXT = r"""
() => (document.body ? document.body.innerText : '')
"""

# Count of client-side route markers, helps identify SPA vs static site.
DETECT_SPA = r"""
() => ({
  hasReactRoot: !!document.querySelector('#root, #app, [data-reactroot]'),
  historyLength: history.length,
  scripts: Array.from(document.scripts).length,
})
"""


# FR-3.2: rolling-window DOM mutation counter. Installed as an init script so
# it re-arms on every navigation, including client-side route changes.
INSTALL_MUTATION_OBSERVER = r"""
(() => {
  if (window.__fixguardMO) return;
  const WINDOW_MS = 2000;
  const state = { stamps: [], peak: 0, total: 0, windowMs: WINDOW_MS };
  window.__fixguardMO = state;
  try {
    const obs = new MutationObserver((records) => {
      const now = performance.now();
      state.total += records.length;
      for (let i = 0; i < records.length; i++) state.stamps.push(now);
      while (state.stamps.length && now - state.stamps[0] > WINDOW_MS) {
        state.stamps.shift();
      }
      if (state.stamps.length > state.peak) state.peak = state.stamps.length;
    });
    obs.observe(document.documentElement || document, {
      childList: true, subtree: true, attributes: true, characterData: true,
    });
  } catch (e) { /* observer unsupported */ }
})();
"""

READ_MUTATIONS = r"""
() => {
  const s = window.__fixguardMO;
  return s ? { peak: s.peak, total: s.total, window_ms: s.windowMs }
           : { peak: 0, total: 0, window_ms: 2000 };
}
"""

# FR-3.1: same-origin links, for route crawling.
EXTRACT_LINKS = r"""
() => {
  const out = new Set();
  const skip = /\.(pdf|zip|rar|jpe?g|png|gif|svg|webp|mp4|mp3|docx?|xlsx?|csv)$/i;
  document.querySelectorAll('a[href]').forEach((a) => {
    const raw = a.getAttribute('href') || '';
    if (/^(mailto:|tel:|javascript:|#)/i.test(raw)) return;
    try {
      const u = new URL(raw, location.href);
      if (u.origin !== location.origin) return;
      if (skip.test(u.pathname)) return;
      u.hash = '';
      out.add(u.href);
    } catch (e) { /* unparseable href */ }
  });
  return Array.from(out).slice(0, 40);
}
"""

# Heuristic "this route is a 404 page" signal for client-side routers, which
# serve HTTP 200 for missing paths.
SOFT_404 = r"""
() => {
  const t = (document.body ? document.body.innerText : '').trim();
  return {
    text_length: t.length,
    looks_404: /\b(404|page not found|not found|doesn'?t exist|no such page)\b/i
                 .test(t.slice(0, 2000)),
    title: (document.title || '').slice(0, 120),
  };
}
"""

# Zeroes the mutation counters. Called after first paint so that building the
# page initially is not mistaken for a re-render loop.
RESET_MUTATIONS = r"""
() => {
  const s = window.__fixguardMO;
  if (s) { s.stamps = []; s.peak = 0; s.total = 0; }
  return true;
}
"""


# Module 1: candidate elements the user might mean, plus the global styling
# the surgical prompt has to freeze.
EXTRACT_STYLE_CONTEXT = r"""
() => {
  const MAX = 140;
  const interesting = 'a,button,input,textarea,select,h1,h2,h3,h4,h5,h6,p,img,' +
                      'nav,header,footer,section,form,li,span,div[role=button],' +
                      'label,blockquote,figcaption';

  const visible = (el) => {
    const r = el.getBoundingClientRect();
    const s = getComputedStyle(el);
    return s.display !== 'none' && s.visibility !== 'hidden' &&
           s.opacity !== '0' && r.width > 0 && r.height > 0;
  };

  // How many elements share each class, so the prompt can warn about blast
  // radius when the only available selector is a shared class.
  const classUse = {};
  document.querySelectorAll('*').forEach((el) => {
    (el.classList || []).forEach((c) => {
      classUse[c] = (classUse[c] || 0) + 1;
    });
  });

  const cssPath = (el) => {
    if (el.id) return '#' + CSS.escape(el.id);
    const unique = Array.from(el.classList || []).find((c) => classUse[c] === 1);
    if (unique) return '.' + CSS.escape(unique);
    const parts = [];
    let node = el;
    for (let depth = 0; node && node.nodeType === 1 && depth < 4; depth++) {
      let seg = node.tagName.toLowerCase();
      if (node.id) { parts.unshift('#' + CSS.escape(node.id)); break; }
      const parent = node.parentElement;
      if (parent) {
        const sameTag = Array.from(parent.children)
          .filter((c) => c.tagName === node.tagName);
        if (sameTag.length > 1) {
          seg += `:nth-of-type(${sameTag.indexOf(node) + 1})`;
        }
      }
      parts.unshift(seg);
      node = node.parentElement;
    }
    return parts.join(' > ');
  };

  const els = Array.from(document.querySelectorAll(interesting))
    .filter(visible)
    .slice(0, MAX);

  const candidates = els.map((el) => {
    const s = getComputedStyle(el);
    const parent = el.parentElement;
    const ps = parent ? getComputedStyle(parent) : null;
    const classes = Array.from(el.classList || []);
    return {
      tag: el.tagName.toLowerCase(),
      role: el.getAttribute('role') || '',
      type: el.getAttribute('type') || '',
      id: el.id || '',
      classes,
      shared_classes: classes.filter((c) => classUse[c] > 1)
                             .map((c) => ({ name: c, used_by: classUse[c] })),
      text: (el.innerText || el.value || el.getAttribute('alt') || '')
              .trim().slice(0, 90),
      name: el.getAttribute('name') || '',
      placeholder: el.getAttribute('placeholder') || '',
      aria_label: el.getAttribute('aria-label') || '',
      label_text: (() => {
        if (el.id) {
          const l = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
          if (l) return (l.innerText || '').trim().slice(0, 60);
        }
        const wrap = el.closest('label');
        return wrap ? (wrap.innerText || '').trim().slice(0, 60) : '';
      })(),
      selector: cssPath(el),
      styles: {
        color: s.color,
        'background-color': s.backgroundColor,
        'font-size': s.fontSize,
        'font-weight': s.fontWeight,
        'font-family': s.fontFamily.slice(0, 90),
        'border-radius': s.borderRadius,
        padding: s.padding,
        margin: s.margin,
        display: s.display,
        'text-align': s.textAlign,
        width: s.width,
        height: s.height,
        border: s.border.slice(0, 60),
      },
      parent: parent ? {
        tag: parent.tagName.toLowerCase(),
        selector: cssPath(parent),
        display: ps.display,
        'flex-direction': ps.flexDirection,
        'justify-content': ps.justifyContent,
        'align-items': ps.alignItems,
        gap: ps.gap,
        'grid-template-columns': ps.gridTemplateColumns.slice(0, 60),
      } : null,
    };
  });

  // Global design tokens declared on :root / html / body.
  const tokens = {};
  for (const sheet of Array.from(document.styleSheets)) {
    let rules;
    try { rules = sheet.cssRules; } catch (e) { continue; }  // cross-origin
    for (const rule of Array.from(rules || [])) {
      if (!rule.selectorText || !rule.style) continue;
      if (!/^(:root|html|body)$/i.test(rule.selectorText.trim())) continue;
      for (const prop of Array.from(rule.style)) {
        if (prop.startsWith('--')) {
          tokens[prop] = rule.style.getPropertyValue(prop).trim().slice(0, 60);
        }
      }
    }
  }

  const rootStyle = getComputedStyle(document.documentElement);
  const bodyStyle = getComputedStyle(document.body);

  return {
    candidates,
    tokens,
    globals: {
      'font-family': bodyStyle.fontFamily.slice(0, 120),
      'root-font-size': rootStyle.fontSize,
      'body-background': bodyStyle.backgroundColor,
      'body-color': bodyStyle.color,
    },
    title: (document.title || '').slice(0, 120),
    element_count: document.querySelectorAll('*').length,
  };
}
"""
