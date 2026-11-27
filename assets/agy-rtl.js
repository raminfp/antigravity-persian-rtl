/* AGY_PERSIAN_RTL_V1 */
(function () {
  'use strict';

  if (typeof document === 'undefined' || typeof MutationObserver === 'undefined') {
    return;
  }
  if (document.documentElement && document.documentElement.hasAttribute('data-agy-rtl-booted')) {
    return;
  }

  var STORAGE_KEY = 'agy_persian_rtl_prefs_v2';
  var DEFAULT_PREFS = {
    enabled: true,
    mode: 'smart', // 'smart' | 'auto' | 'force'
    font: 'Vazirmatn', // 'Vazirmatn' | 'Vazir' | 'Tahoma' | 'custom'
    customFont: '',
    fontScale: 100, // 85..135
    lineHeight: 1.85, // 1.6 | 1.85 | 2.1
    persianDigits: false,
    rtlInput: true,
    isolateInlineCode: true
  };

  var prefs = loadPrefs();

  var PERSIAN_RE = /[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]/;
  var STRONG_CHAR_RE = /[A-Za-z\u00C0-\u024F\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]/;

  var EXCLUDED_SELECTOR = [
    'pre',
    'code',
    'kbd',
    'samp',
    '.monaco-editor',
    '.monaco-diff-editor',
    '.xterm',
    '.katex',
    'mjx-container',
    'svg',
    'math',
    'webview',
    '[data-browser-hole]',
    '.part.statusbar',
    '.part.activitybar',
    '.part.titlebar',
    '.monaco-tl-row .monaco-icon-label',
    '.quick-input-widget',
    '#agy-rtl-toolbar-host',
    '#agy-rtl-popover'
  ].join(', ');

  var SKIP_SUBTREE_TAGS = {
    PRE: 1,
    CODE: 1,
    KBD: 1,
    SAMP: 1,
    SCRIPT: 1,
    STYLE: 1,
    SVG: 1,
    MATH: 1,
    WEBVIEW: 1,
    TEXTAREA: 1,
    INPUT: 1
  };

  var PROSE_TAGS = {
    P: 1,
    LI: 1,
    H1: 1,
    H2: 1,
    H3: 1,
    H4: 1,
    H5: 1,
    H6: 1,
    BLOCKQUOTE: 1,
    SUMMARY: 1,
    TD: 1,
    TH: 1,
    CAPTION: 1,
    DT: 1,
    DD: 1,
    FIGCAPTION: 1,
    LEGEND: 1
  };

  var LIST_OR_TABLE_TAGS = {
    UL: 1,
    OL: 1,
    TABLE: 1
  };

  var INLINE_PHRASING_TAGS = {
    STRONG: 1,
    B: 1,
    EM: 1,
    I: 1,
    CODE: 1,
    SPAN: 1,
    A: 1,
    KBD: 1,
    SAMP: 1,
    MARK: 1,
    SUB: 1,
    SUP: 1,
    BR: 1,
    SMALL: 1,
    DEL: 1,
    INS: 1,
    S: 1,
    U: 1,
    TIME: 1,
    ABBR: 1,
    CITE: 1,
    Q: 1
  };

  function cloneDefaults() {
    var out = {};
    for (var k in DEFAULT_PREFS) {
      if (Object.prototype.hasOwnProperty.call(DEFAULT_PREFS, k)) {
        out[k] = DEFAULT_PREFS[k];
      }
    }
    return out;
  }

  function loadPrefs() {
    var base = cloneDefaults();
    try {
      if (typeof localStorage !== 'undefined') {
        var raw = localStorage.getItem(STORAGE_KEY);
        if (raw) {
          var parsed = JSON.parse(raw);
          for (var k in base) {
            if (Object.prototype.hasOwnProperty.call(parsed, k) && typeof parsed[k] === typeof base[k]) {
              base[k] = parsed[k];
            }
          }
        }
      }
    } catch (_) {}
    return base;
  }

  function savePrefs() {
    try {
      if (typeof localStorage !== 'undefined') {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs));
      }
    } catch (_) {}
  }

  function resolveFontStack() {
    var primary = prefs.font === 'custom' && prefs.customFont.trim()
      ? "'" + prefs.customFont.trim().replace(/['"]/g, '') + "'"
      : "'" + prefs.font + "'";
    return primary + ", 'Vazirmatn', 'Vazir', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif";
  }

  function applyPrefsToRoot() {
    var root = document.documentElement;
    if (!root) return;
    setAttr(root, 'data-agy-rtl-enabled', prefs.enabled ? '1' : '0');
    setAttr(root, 'data-agy-rtl-mode', prefs.mode);
    setAttr(root, 'data-agy-fa-digits', prefs.persianDigits ? '1' : '0');
    setAttr(root, 'data-agy-rtl-input', prefs.rtlInput ? '1' : '0');
    setAttr(root, 'data-agy-inline-code', prefs.isolateInlineCode ? '1' : '0');
    if (root.style && typeof root.style.setProperty === 'function') {
      root.style.setProperty('--agy-persian-font', resolveFontStack());
      root.style.setProperty('--agy-font-scale', String((prefs.fontScale || 100) / 100));
      root.style.setProperty('--agy-line-height', String(prefs.lineHeight || 1.85));
    }
    syncToolbarVisualState();
  }

  function setAttr(el, name, val) {
    if (el && el.getAttribute && el.getAttribute(name) !== val) {
      el.setAttribute(name, val);
    }
  }

  function removeAttr(el, name) {
    if (el && el.hasAttribute && el.hasAttribute(name)) {
      el.removeAttribute(name);
    }
  }

  function hasClass(el, cls) {
    if (!el || typeof el.className !== 'string' || !el.className) return false;
    return (' ' + el.className + ' ').indexOf(' ' + cls + ' ') !== -1;
  }

  function isShimmerInnerNode(el) {
    if (!el || el.nodeType !== 1) return false;
    return (
      hasClass(el, 'shimmer-text-mask') ||
      hasClass(el, 'shimmer-text-content') ||
      (el.hasAttribute && (
        el.hasAttribute('data-slot') ||
        el.hasAttribute('data-slot-in') ||
        el.hasAttribute('data-slot-out')
      ))
    );
  }

  function isShimmerRoot(el) {
    if (!el || el.nodeType !== 1) return false;
    if (hasClass(el, 'animate-shimmer-text')) return true;
    var kids = el.children;
    if (kids && kids.length === 1 && hasClass(kids[0], 'shimmer-text-mask')) {
      return true;
    }
    return false;
  }

  function findShimmerRoot(el) {
    var cur = el;
    var depth = 0;
    while (cur && cur.nodeType === 1 && depth < 10) {
      if (isShimmerRoot(cur)) return cur;
      cur = cur.parentElement;
      depth++;
    }
    return null;
  }

  function isExcluded(el) {
    if (!el || el.nodeType !== 1) return true;
    if (SKIP_SUBTREE_TAGS[el.tagName]) return true;
    if (el.id === 'agy-rtl-toolbar-host' || el.id === 'agy-rtl-popover') return true;
    try {
      return Boolean(el.closest && el.closest(EXCLUDED_SELECTOR));
    } catch (_) {
      return false;
    }
  }

  function inspectTextOutsideCode(root) {
    var hasPersian = false;
    var firstStrongIsPersian = null;
    var hasAnyText = false;
    var stack = [root];
    while (stack.length > 0) {
      var node = stack.pop();
      if (!node) continue;
      if (node.nodeType === 3) {
        var val = node.nodeValue || '';
        if (val.trim().length > 0) {
          hasAnyText = true;
          if (firstStrongIsPersian === null) {
            var m = STRONG_CHAR_RE.exec(val);
            if (m) {
              firstStrongIsPersian = PERSIAN_RE.test(m[0]);
            }
          }
          if (!hasPersian && PERSIAN_RE.test(val)) {
            hasPersian = true;
            if (firstStrongIsPersian !== null) break;
          }
        }
        continue;
      }
      if (node.nodeType !== 1) continue;
      if (node !== root) {
        if (SKIP_SUBTREE_TAGS[node.tagName]) continue;
        var cls = typeof node.className === 'string' ? node.className : '';
        if (cls && (cls.indexOf('katex') !== -1 || cls.indexOf('monaco-editor') !== -1 || cls.indexOf('xterm') !== -1)) {
          continue;
        }
      }
      var children = node.childNodes;
      for (var i = children.length - 1; i >= 0; i--) {
        stack.push(children[i]);
      }
    }
    return {
      hasPersian: hasPersian,
      firstStrongIsPersian: Boolean(firstStrongIsPersian),
      hasAnyText: hasAnyText
    };
  }

  function shouldApplyRtl(el, isChromeSensitive) {
    if (!prefs.enabled) return false;
    var info = inspectTextOutsideCode(el);
    if (!info.hasAnyText) return false;
    if (prefs.mode === 'auto') {
      return info.firstStrongIsPersian;
    }
    if (prefs.mode === 'force' && !isChromeSensitive) {
      if (el.closest && el.closest('nav, aside, header, [role="navigation"], [role="menubar"], [role="tablist"], [role="tree"]')) {
        return info.hasPersian;
      }
      return true;
    }
    return info.hasPersian;
  }

  var LAYOUT_SHELL_TAGS = {
    SECTION: 1,
    MAIN: 1,
    ASIDE: 1,
    NAV: 1,
    HEADER: 1,
    FOOTER: 1,
    FORM: 1,
    TABLE: 1,
    UL: 1,
    OL: 1
  };

  function isLeafTextDivOrSpan(el) {
    var tag = el.tagName;
    if (tag !== 'DIV' && tag !== 'SPAN') return false;
    var childNodes = el.childNodes;
    if (!childNodes || childNodes.length === 0) return false;
    if (el.children && el.children.length > 20) return false;

    var hasDirectText = false;
    var hasDirectPersianText = false;
    var allChildrenInline = true;
    var hasLayoutShellChild = false;

    for (var i = 0; i < childNodes.length; i++) {
      var c = childNodes[i];
      if (c.nodeType === 3) {
        if (c.nodeValue && c.nodeValue.trim().length > 0) {
          hasDirectText = true;
          if (PERSIAN_RE.test(c.nodeValue)) {
            hasDirectPersianText = true;
          }
        }
      } else if (c.nodeType === 1) {
        if (LAYOUT_SHELL_TAGS[c.tagName]) {
          hasLayoutShellChild = true;
        }
        if (!INLINE_PHRASING_TAGS[c.tagName]) {
          allChildrenInline = false;
        }
      }
    }

    if (hasLayoutShellChild) return false;
    if (tag === 'SPAN' && el.parentElement && el.parentElement.closest('[data-agy-fa="1"]')) {
      return false;
    }
    // Accept message bubbles containing a slash-command (/plan) or @mention chip alongside direct Persian text
    if (hasDirectPersianText) return true;
    if (!allChildrenInline) return false;
    if (!hasDirectText && (!el.children || el.children.length === 0)) {
      return false;
    }
    return true;
  }

  function updateInputDirection(el) {
    if (!el || el.nodeType !== 1) return;
    if (el.closest && el.closest('.monaco-editor, .xterm, .quick-input-widget, #agy-rtl-popover')) return;
    if (!prefs.enabled || !prefs.rtlInput) {
      removeAttr(el, 'data-agy-fa');
      removeAttr(el, 'dir');
      return;
    }
    var text = '';
    if (el.tagName === 'TEXTAREA' || el.tagName === 'INPUT') {
      text = el.value || el.placeholder || '';
    } else {
      text = el.textContent || el.getAttribute('placeholder') || el.getAttribute('aria-placeholder') || '';
    }
    if (prefs.mode === 'force' || PERSIAN_RE.test(text)) {
      setAttr(el, 'data-agy-fa', '1');
      setAttr(el, 'dir', 'rtl');
    } else if (text.trim().length > 0) {
      removeAttr(el, 'data-agy-fa');
      setAttr(el, 'dir', 'ltr');
    } else {
      removeAttr(el, 'data-agy-fa');
      setAttr(el, 'dir', 'auto');
    }
  }

  function isInputElement(el) {
    if (!el || el.nodeType !== 1) return false;
    if (el.tagName === 'TEXTAREA') return true;
    if (el.tagName === 'INPUT') {
      var t = (el.getAttribute('type') || 'text').toLowerCase();
      return t === 'text' || t === 'search';
    }
    if (el.getAttribute('contenteditable') === 'true') return true;
    if (el.getAttribute('role') === 'textbox') return true;
    return false;
  }

  function bindInputListeners(el) {
    if (!el.__agyRtlBound) {
      el.__agyRtlBound = true;
      var handler = function () {
        updateInputDirection(el);
      };
      el.addEventListener('input', handler, { passive: true });
      el.addEventListener('keyup', handler, { passive: true });
    }
    updateInputDirection(el);
  }

  function processSingleElement(el) {
    if (!el || el.nodeType !== 1) return;

    if (isInputElement(el)) {
      bindInputListeners(el);
      return;
    }

    if (el.closest && el.closest('[contenteditable="true"]')) {
      var editorRoot = el.closest('[contenteditable="true"]');
      if (editorRoot) bindInputListeners(editorRoot);
      return;
    }

    if (isExcluded(el)) return;

    if (!prefs.enabled) {
      if (el.hasAttribute('data-agy-fa')) {
        removeAttr(el, 'data-agy-fa');
        removeAttr(el, 'dir');
      }
      if (el.hasAttribute('data-agy-fa-row')) {
        removeAttr(el, 'data-agy-fa-row');
        removeAttr(el, 'dir');
      }
      return;
    }

    // Animated shimmer / live status text root (must own dir & data-agy-fa so RTL/LTR animation matches text language)
    if (isShimmerRoot(el)) {
      if (shouldApplyRtl(el, true)) {
        setAttr(el, 'data-agy-fa', '1');
        setAttr(el, 'dir', 'rtl');
      } else if (el.hasAttribute('data-agy-fa') || el.getAttribute('dir') === 'rtl') {
        removeAttr(el, 'data-agy-fa');
        removeAttr(el, 'dir');
      }
      return;
    }

    // Inner shimmer/text-transition nodes must never hold independent data-agy-fa; delegate to shimmer root
    if (isShimmerInnerNode(el)) {
      if (el.hasAttribute('data-agy-fa')) {
        removeAttr(el, 'data-agy-fa');
        removeAttr(el, 'dir');
      }
      var sRoot = findShimmerRoot(el.parentElement);
      if (sRoot) processSingleElement(sRoot);
      return;
    }

    var tag = el.tagName;
    var role = el.getAttribute('role') || '';

    // Question / multiple-choice option rows
    if (tag === 'LABEL' || role === 'radio' || role === 'checkbox' || role === 'option') {
      if (!el.closest('nav, header, [role="menubar"], [role="tablist"], [role="tree"]')) {
        if (shouldApplyRtl(el, true)) {
          setAttr(el, 'data-agy-fa-row', '1');
          setAttr(el, 'dir', 'rtl');
        } else if (el.hasAttribute('data-agy-fa-row')) {
          removeAttr(el, 'data-agy-fa-row');
          removeAttr(el, 'dir');
        }
      }
      if (tag === 'LABEL') return;
    }

    // Lists & tables
    if (LIST_OR_TABLE_TAGS[tag]) {
      if (el.closest('nav, [role="menubar"], [role="tablist"], [role="tree"]')) return;
      if (shouldApplyRtl(el, false)) {
        setAttr(el, 'data-agy-fa', '1');
        setAttr(el, 'dir', 'rtl');
      } else if (el.hasAttribute('data-agy-fa')) {
        removeAttr(el, 'data-agy-fa');
        removeAttr(el, 'dir');
      }
      return;
    }

    var isProse = Boolean(PROSE_TAGS[tag]);
    var isLeafGeneric = !isProse && isLeafTextDivOrSpan(el);
    if (isProse || isLeafGeneric) {
      if (shouldApplyRtl(el, isLeafGeneric)) {
        setAttr(el, 'data-agy-fa', '1');
        setAttr(el, 'dir', 'rtl');
      } else if (el.hasAttribute('data-agy-fa')) {
        removeAttr(el, 'data-agy-fa');
        setAttr(el, 'dir', 'auto');
      }
    }
  }

  var CANDIDATE_SELECTOR = [
    'p', 'li', 'ul', 'ol', 'table', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'blockquote', 'summary', 'td', 'th', 'caption', 'dt', 'dd', 'figcaption',
    'label', 'legend', 'div', 'span',
    'textarea', 'input[type="text"]', 'input[type="search"]', 'input:not([type])',
    '[contenteditable="true"]', '[role="textbox"]',
    '[role="radio"]', '[role="checkbox"]', '[role="option"]'
  ].join(', ');

  function processSubtree(root) {
    if (!root) return;
    if (root.nodeType === 3) {
      if (root.parentElement) {
        processAncestorsAndElement(root.parentElement);
      }
      return;
    }
    if (root.nodeType !== 1) return;
    if (SKIP_SUBTREE_TAGS[root.tagName]) return;
    if (root.id === 'agy-rtl-toolbar-host' || root.id === 'agy-rtl-popover') return;

    processSingleElement(root);
    if (root.getAttribute && root.getAttribute('contenteditable') === 'true') {
      return;
    }

    if (!root.querySelectorAll) return;
    var list = root.querySelectorAll(CANDIDATE_SELECTOR);
    for (var i = 0; i < list.length; i++) {
      processSingleElement(list[i]);
    }
  }

  function processAncestorsAndElement(el) {
    var cur = el;
    var depth = 0;
    var handledShimmer = null;
    while (cur && cur.nodeType === 1 && depth < 5) {
      if (isShimmerRoot(cur)) handledShimmer = cur;
      processSingleElement(cur);
      cur = cur.parentElement;
      depth++;
    }
    if (!handledShimmer) {
      var sRoot = findShimmerRoot(el);
      if (sRoot) processSingleElement(sRoot);
    }
  }

  function rescanAll() {
    applyPrefsToRoot();
    if (document.body) {
      processSubtree(document.body);
    }
  }

  // =========================================================================
  // Top Header Toolbar & Studio Popover (DOM API only — Trusted Types Safe)
  // =========================================================================

  var toolbarHost = null;
  var triggerBtn = null;
  var popoverEl = null;
  var uiRefs = {};

  function dom(tag, attrs, children) {
    var node = document.createElement(tag);
    if (attrs) {
      for (var k in attrs) {
        if (!Object.prototype.hasOwnProperty.call(attrs, k)) continue;
        var v = attrs[k];
        if (k === 'className') node.className = v;
        else if (k === 'text') node.textContent = v;
        else if (k.indexOf('on') === 0 && typeof v === 'function') {
          node.addEventListener(k.slice(2).toLowerCase(), v);
        } else if (v !== null && v !== undefined) {
          node.setAttribute(k, String(v));
        }
      }
    }
    if (children) {
      for (var i = 0; i < children.length; i++) {
        var c = children[i];
        if (!c) continue;
        if (typeof c === 'string') node.appendChild(document.createTextNode(c));
        else node.appendChild(c);
      }
    }
    return node;
  }

  function createSlidersIcon() {
    if (typeof document.createElementNS !== 'function') {
      return dom('span', { text: '⚙' });
    }
    var ns = 'http://www.w3.org/2000/svg';
    var svg = document.createElementNS(ns, 'svg');
    svg.setAttribute('viewBox', '0 0 16 16');
    svg.setAttribute('fill', 'none');
    svg.setAttribute('class', 'agy-tb-icon');
    var paths = [
      'M2 4h7M12 4h2M10.5 2.5v3',
      'M2 8h3M8 8h6M6.5 6.5v3',
      'M2 12h8M13 12h1M11.5 10.5v3'
    ];
    for (var i = 0; i < paths.length; i++) {
      var p = document.createElementNS(ns, 'path');
      p.setAttribute('d', paths[i]);
      p.setAttribute('stroke', 'currentColor');
      p.setAttribute('stroke-width', '1.4');
      p.setAttribute('stroke-linecap', 'round');
      svg.appendChild(p);
    }
    return svg;
  }

  function detectThemeMode() {
    try {
      if (!window.getComputedStyle || !document.body) return 'dark';
      var bg = window.getComputedStyle(document.body).backgroundColor || '';
      var m = bg.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
      if (m) {
        var lum = (0.299 * Number(m[1]) + 0.587 * Number(m[2]) + 0.114 * Number(m[3])) / 255;
        if (lum > 0.55) return 'light';
      }
    } catch (_) {}
    return 'dark';
  }

  function syncToolbarVisualState() {
    var theme = detectThemeMode();
    if (toolbarHost) {
      setAttr(toolbarHost, 'data-theme', theme);
    }
    if (triggerBtn) {
      setAttr(triggerBtn, 'data-active', prefs.enabled ? '1' : '0');
    }
    if (!popoverEl) return;
    setAttr(popoverEl, 'data-theme', theme);

    if (uiRefs.masterSwitch) {
      setAttr(uiRefs.masterSwitch, 'data-on', prefs.enabled ? '1' : '0');
    }
    if (uiRefs.modeBtns) {
      for (var m in uiRefs.modeBtns) {
        setAttr(uiRefs.modeBtns[m], 'data-selected', prefs.mode === m ? '1' : '0');
      }
    }
    if (uiRefs.fontSelect && uiRefs.fontSelect.value !== prefs.font) {
      uiRefs.fontSelect.value = prefs.font;
    }
    if (uiRefs.customFontInput) {
      uiRefs.customFontInput.style.display = prefs.font === 'custom' ? 'block' : 'none';
      if (document.activeElement !== uiRefs.customFontInput) {
        uiRefs.customFontInput.value = prefs.customFont || '';
      }
    }
    if (uiRefs.scaleLabel) {
      uiRefs.scaleLabel.textContent = prefs.fontScale + '%';
    }
    if (uiRefs.lhBtns) {
      for (var k in uiRefs.lhBtns) {
        setAttr(uiRefs.lhBtns[k], 'data-selected', String(prefs.lineHeight) === k ? '1' : '0');
      }
    }
    if (uiRefs.digitsSwitch) {
      setAttr(uiRefs.digitsSwitch, 'data-on', prefs.persianDigits ? '1' : '0');
    }
    if (uiRefs.inputSwitch) {
      setAttr(uiRefs.inputSwitch, 'data-on', prefs.rtlInput ? '1' : '0');
    }
    if (uiRefs.codeSwitch) {
      setAttr(uiRefs.codeSwitch, 'data-on', prefs.isolateInlineCode ? '1' : '0');
    }
  }

  function createSwitch(initialOn, onToggle) {
    var knob = dom('span', { className: 'agy-switch-knob' });
    var btn = dom('button', {
      type: 'button',
      className: 'agy-switch',
      'data-on': initialOn ? '1' : '0',
      onClick: function (e) {
        e.stopPropagation();
        onToggle();
      }
    }, [knob]);
    return btn;
  }

  function buildToolbarAndPopover() {
    if (typeof document.createElement !== 'function' || !document.body) return;
    if (toolbarHost && popoverEl) return;

    triggerBtn = dom('button', {
      type: 'button',
      className: 'agy-tb-trigger',
      title: 'RTL & Custom Font Settings (Alt+Shift+R)',
      'data-active': prefs.enabled ? '1' : '0',
      'data-open': '0',
      onClick: function (e) {
        e.stopPropagation();
        togglePopover();
      }
    }, [
      dom('span', { className: 'agy-tb-dot' }),
      dom('span', { text: 'RTL' }),
      createSlidersIcon()
    ]);

    toolbarHost = dom('div', { id: 'agy-rtl-toolbar-host' }, [triggerBtn]);

    // Header
    uiRefs.masterSwitch = createSwitch(prefs.enabled, function () {
      prefs.enabled = !prefs.enabled;
      savePrefs();
      rescanAll();
    });
    var header = dom('div', { className: 'agy-pop-header' }, [
      dom('div', { className: 'agy-pop-title-wrap' }, [
        dom('div', { className: 'agy-pop-title', text: 'RTL & Font Studio' }),
        dom('div', { className: 'agy-pop-sub', text: 'Alt + Shift + R' })
      ]),
      uiRefs.masterSwitch
    ]);

    // Direction Mode
    uiRefs.modeBtns = {};
    var modes = [
      { id: 'smart', label: 'Smart' },
      { id: 'auto', label: 'Auto' },
      { id: 'force', label: 'Force RTL' }
    ];
    var modeChildren = [];
    modes.forEach(function (item) {
      var b = dom('button', {
        type: 'button',
        className: 'agy-seg-btn',
        text: item.label,
        onClick: function () {
          prefs.mode = item.id;
          savePrefs();
          rescanAll();
        }
      });
      uiRefs.modeBtns[item.id] = b;
      modeChildren.push(b);
    });
    var modeSec = dom('div', { className: 'agy-pop-section' }, [
      dom('div', { className: 'agy-pop-label' }, [dom('span', { text: 'Text Direction Mode' })]),
      dom('div', { className: 'agy-seg-group' }, modeChildren)
    ]);

    // Font Selector
    var fontSelect = dom('select', {
      className: 'agy-select',
      onChange: function (e) {
        prefs.font = e.target.value;
        savePrefs();
        applyPrefsToRoot();
      }
    }, [
      dom('option', { value: 'Vazirmatn', text: 'Vazirmatn (Recommended RTL)' }),
      dom('option', { value: 'Noto Sans Arabic', text: 'Noto Sans Arabic' }),
      dom('option', { value: 'Cairo', text: 'Cairo' }),
      dom('option', { value: 'Inter', text: 'Inter' }),
      dom('option', { value: 'Tahoma', text: 'Tahoma' }),
      dom('option', { value: 'Segoe UI', text: 'Segoe UI (System Default)' }),
      dom('option', { value: 'custom', text: 'Custom installed system font...' })
    ]);
    uiRefs.fontSelect = fontSelect;

    var customFontInput = dom('input', {
      type: 'text',
      className: 'agy-custom-input',
      placeholder: 'e.g., Inter, Cairo, IRANSansX, Noto Sans',
      onInput: function (e) {
        prefs.customFont = e.target.value;
        savePrefs();
        applyPrefsToRoot();
      }
    });
    uiRefs.customFontInput = customFontInput;

    var fontSec = dom('div', { className: 'agy-pop-section' }, [
      dom('div', { className: 'agy-pop-label' }, [dom('span', { text: 'Display Font' })]),
      dom('div', { className: 'agy-font-row' }, [fontSelect]),
      customFontInput
    ]);

    // Font Size Scale Stepper
    uiRefs.scaleLabel = dom('span', { className: 'agy-step-val', text: prefs.fontScale + '%' });
    var scaleSec = dom('div', { className: 'agy-pop-section' }, [
      dom('div', { className: 'agy-pop-label' }, [dom('span', { text: 'Font Size Scale' })]),
      dom('div', { className: 'agy-stepper' }, [
        dom('button', {
          type: 'button',
          className: 'agy-step-btn',
          text: '+',
          onClick: function () {
            prefs.fontScale = Math.min(135, (prefs.fontScale || 100) + 5);
            savePrefs();
            applyPrefsToRoot();
          }
        }),
        uiRefs.scaleLabel,
        dom('button', {
          type: 'button',
          className: 'agy-step-btn',
          text: '−',
          onClick: function () {
            prefs.fontScale = Math.max(85, (prefs.fontScale || 100) - 5);
            savePrefs();
            applyPrefsToRoot();
          }
        })
      ])
    ]);

    // Line Height
    uiRefs.lhBtns = {};
    var lhs = [
      { val: '1.6', label: 'Compact' },
      { val: '1.85', label: 'Standard' },
      { val: '2.1', label: 'Relaxed' }
    ];
    var lhChildren = [];
    lhs.forEach(function (item) {
      var b = dom('button', {
        type: 'button',
        className: 'agy-seg-btn',
        text: item.label,
        onClick: function () {
          prefs.lineHeight = Number(item.val);
          savePrefs();
          applyPrefsToRoot();
        }
      });
      uiRefs.lhBtns[item.val] = b;
      lhChildren.push(b);
    });
    var lhSec = dom('div', { className: 'agy-pop-section' }, [
      dom('div', { className: 'agy-pop-label' }, [dom('span', { text: 'Paragraph Line Height' })]),
      dom('div', { className: 'agy-seg-group' }, lhChildren)
    ]);

    // Toggles
    function makeToggleRow(label, key, needsRescan) {
      var sw = createSwitch(prefs[key], function () {
        prefs[key] = !prefs[key];
        savePrefs();
        if (needsRescan) rescanAll();
        else applyPrefsToRoot();
      });
      var row = dom('div', {
        className: 'agy-toggle-row',
        onClick: function () {
          prefs[key] = !prefs[key];
          savePrefs();
          if (needsRescan) rescanAll();
          else applyPrefsToRoot();
        }
      }, [
        dom('span', { className: 'agy-toggle-text', text: label }),
        sw
      ]);
      return { row: row, sw: sw };
    }

    var digitsRow = makeToggleRow('Localized Digits (copy-safe)', 'persianDigits', false);
    uiRefs.digitsSwitch = digitsRow.sw;

    var inputRow = makeToggleRow('Smart RTL Chat Input', 'rtlInput', true);
    uiRefs.inputSwitch = inputRow.sw;

    var codeRow = makeToggleRow('Isolate Inline Code (LTR)', 'isolateInlineCode', false);
    uiRefs.codeSwitch = codeRow.sw;

    // Footer Buttons
    var footer = dom('div', { className: 'agy-pop-footer' }, [
      dom('button', {
        type: 'button',
        className: 'agy-foot-btn',
        text: 'Rescan Page',
        onClick: function () {
          rescanAll();
        }
      }),
      dom('button', {
        type: 'button',
        className: 'agy-foot-btn',
        text: 'Reset Defaults',
        onClick: function () {
          prefs = cloneDefaults();
          savePrefs();
          rescanAll();
        }
      })
    ]);

    popoverEl = dom('div', {
      id: 'agy-rtl-popover',
      hidden: 'hidden',
      onClick: function (e) {
        e.stopPropagation();
      }
    }, [
      header,
      modeSec,
      fontSec,
      scaleSec,
      lhSec,
      digitsRow.row,
      inputRow.row,
      codeRow.row,
      footer
    ]);

    document.body.appendChild(popoverEl);
    syncToolbarVisualState();

    document.addEventListener('click', function (e) {
      if (!popoverEl || popoverEl.hasAttribute('hidden')) return;
      if (toolbarHost && toolbarHost.contains(e.target)) return;
      if (popoverEl.contains(e.target)) return;
      closePopover();
    }, true);

    document.addEventListener('keydown', function (e) {
      if (e.altKey && e.shiftKey && (e.code === 'KeyR' || e.key === 'R' || e.key === 'r')) {
        e.preventDefault();
        prefs.enabled = !prefs.enabled;
        savePrefs();
        rescanAll();
        return;
      }
      if (e.key === 'Escape' && popoverEl && !popoverEl.hasAttribute('hidden')) {
        closePopover();
      }
    });

    if (typeof window !== 'undefined' && window.addEventListener) {
      window.addEventListener('resize', function () {
        if (popoverEl && !popoverEl.hasAttribute('hidden')) {
          positionPopover();
        }
      });
    }
  }

  function positionPopover() {
    if (!triggerBtn || !popoverEl || typeof triggerBtn.getBoundingClientRect !== 'function') return;
    var rect = triggerBtn.getBoundingClientRect();
    var vw = (typeof window !== 'undefined' && window.innerWidth) || 1024;
    var popWidth = 296;
    var top = Math.max(8, Math.round(rect.bottom + 6));
    // Align right edge of popover with right edge of trigger button, clamped inside viewport
    var left = Math.round(rect.right - popWidth);
    if (left < 8) left = 8;
    if (left + popWidth > vw - 8) left = Math.max(8, vw - popWidth - 8);
    popoverEl.style.top = top + 'px';
    popoverEl.style.left = left + 'px';
  }

  function togglePopover() {
    if (!popoverEl) return;
    if (popoverEl.hasAttribute('hidden')) {
      syncToolbarVisualState();
      popoverEl.removeAttribute('hidden');
      setAttr(triggerBtn, 'data-open', '1');
      positionPopover();
    } else {
      closePopover();
    }
  }

  function closePopover() {
    if (!popoverEl) return;
    popoverEl.setAttribute('hidden', 'hidden');
    if (triggerBtn) setAttr(triggerBtn, 'data-open', '0');
  }

  function findHeaderSlot() {
    if (!document.querySelector) return null;

    // Tier 1: Antigravity 2.0 Hub Header right-side action cluster (next to ⋮ and Open IDE)
    var ideBtn = document.querySelector(
      '[data-testid^="open-editor"], [data-testid="install-editor"], [data-testid="editor-loading"]'
    );
    if (ideBtn) {
      var actionRow = ideBtn.closest('div.flex.items-center.gap-1') || ideBtn.parentElement;
      if (actionRow && actionRow.parentElement) {
        return { parent: actionRow.parentElement, before: actionRow, fallback: false };
      }
    }

    // Tier 1b: Any top header no-drag right action group when Open IDE button is hidden
    var candidates = document.querySelectorAll('div.flex.items-center.justify-end.shrink-0 > div.flex.items-center.gap-1');
    for (var i = 0; i < candidates.length; i++) {
      var c = candidates[i];
      if (c.getBoundingClientRect) {
        var r = c.getBoundingClientRect();
        if (r.top >= 0 && r.top < 68 && c.parentElement) {
          return { parent: c.parentElement, before: c, fallback: false };
        }
      }
    }

    // Tier 2: Antigravity IDE (VS Code Workbench Titlebar Right)
    var vscodeRight = document.querySelector('.part.titlebar .titlebar-right');
    if (vscodeRight) {
      var winControls = vscodeRight.querySelector('.window-controls-container');
      return { parent: vscodeRight, before: winControls || vscodeRight.firstChild, fallback: false };
    }

    return null;
  }

  function ensureToolbarMounted() {
    if (!document.body || typeof document.createElement !== 'function') return;
    if (!toolbarHost) {
      buildToolbarAndPopover();
    }
    if (!toolbarHost) return;

    var slot = findHeaderSlot();
    if (slot && slot.parent) {
      toolbarHost.className = '';
      if (toolbarHost.parentElement !== slot.parent || toolbarHost.nextSibling !== slot.before) {
        try {
          slot.parent.insertBefore(toolbarHost, slot.before || null);
        } catch (_) {}
      }
      return;
    }

    if (!toolbarHost.parentElement) {
      toolbarHost.className = 'agy-floating-fallback';
      document.body.appendChild(toolbarHost);
    }
  }

  // =========================================================================
  // MutationObserver Loop
  // =========================================================================

  var pendingNodes = new Set();
  var scheduled = false;

  function flushPending() {
    scheduled = false;
    ensureToolbarMounted();
    var items = Array.from(pendingNodes);
    pendingNodes.clear();
    for (var i = 0; i < items.length; i++) {
      processSubtree(items[i]);
    }
  }

  function scheduleFlush() {
    if (scheduled) return;
    scheduled = true;
    if (typeof requestAnimationFrame === 'function') {
      requestAnimationFrame(flushPending);
    } else {
      setTimeout(flushPending, 50);
    }
  }

  function boot() {
    if (!document.documentElement) return;
    if (document.documentElement.hasAttribute('data-agy-rtl-booted')) return;

    var proto = (typeof location !== 'undefined' && location && location.protocol) || '';
    var host = (typeof location !== 'undefined' && location && location.hostname) || '';
    var isAllowedSurface =
      proto === 'vscode-file:' ||
      proto === 'vscode-webview:' ||
      proto === 'file:' ||
      proto === 'app:' ||
      host === '127.0.0.1' ||
      host === 'localhost' ||
      host === '';
    if (!isAllowedSurface) return;

    document.documentElement.setAttribute('data-agy-rtl-booted', '1');
    applyPrefsToRoot();
    ensureToolbarMounted();

    if (document.body) {
      processSubtree(document.body);
    }

    var observer = new MutationObserver(function (mutations) {
      var needToolbarCheck = !toolbarHost || !toolbarHost.parentElement || toolbarHost.className === 'agy-floating-fallback';
      for (var i = 0; i < mutations.length; i++) {
        var m = mutations[i];
        if (m.type === 'characterData') {
          if (m.target && m.target.parentElement) {
            pendingNodes.add(m.target);
          }
        } else if (m.type === 'childList') {
          if (m.target && m.target.nodeType === 1) {
            if (m.target.id === 'agy-rtl-toolbar-host' || m.target.id === 'agy-rtl-popover') continue;
            pendingNodes.add(m.target);
          }
          var added = m.addedNodes;
          for (var j = 0; j < added.length; j++) {
            var n = added[j];
            if (n.nodeType === 1 || n.nodeType === 3) {
              if (n.id === 'agy-rtl-toolbar-host' || n.id === 'agy-rtl-popover') continue;
              pendingNodes.add(n);
            }
          }
        }
      }
      if (pendingNodes.size > 0 || needToolbarCheck) {
        scheduleFlush();
      }
    });

    observer.observe(document.documentElement, {
      childList: true,
      subtree: true,
      characterData: true
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot, { once: true });
  } else {
    boot();
  }
})();
