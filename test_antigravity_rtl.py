#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Automated verification suite for Antigravity Persian RTL & Vazirmatn Patcher (V2 Studio Edition)."""

import hashlib
import json
import os
import shutil
import struct
import subprocess
import tempfile
import time
from pathlib import Path

import antigravity_rtl as rtl


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        while True:
            b = f.read(1024 * 1024)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def verify_all_asar_integrities(asar_path: Path) -> int:
    raw = asar_path.read_bytes()
    u0, header_size, u2, json_size = struct.unpack("<IIII", raw[:16])
    assert u0 == 4, f"Expected u0=4, got {u0}"
    padded_json_len = (json_size + 3) & ~3
    assert u2 == 4 + padded_json_len, f"Expected u2={4 + padded_json_len}, got {u2}"
    assert header_size == 8 + padded_json_len, f"Expected header_size={8 + padded_json_len}, got {header_size}"

    header = json.loads(raw[16 : 16 + json_size].decode("utf-8"))
    payload_start = 8 + header_size
    checked = 0

    def walk(node, prefix=""):
        nonlocal checked
        for name, child in node.get("files", {}).items():
            p = f"{prefix}/{name}" if prefix else name
            if "files" in child:
                walk(child, p)
            elif not child.get("unpacked"):
                off = payload_start + int(child["offset"])
                sz = int(child["size"])
                data = raw[off : off + sz]
                assert len(data) == sz, f"Size mismatch for {p}"
                if "integrity" in child:
                    expected = rtl.compute_integrity(data)
                    assert child["integrity"]["hash"] == expected["hash"], f"SHA256 mismatch for {p}"
                    assert child["integrity"]["blocks"] == expected["blocks"], f"Block hash mismatch for {p}"
                checked += 1

    walk(header)
    return checked


def test_desktop_asar_roundtrip_and_update() -> None:
    desk_res = rtl.default_desktop_dir() / "resources"
    clean_bak = desk_res / "app.asar.orig.bak"
    source_asar = clean_bak if clean_bak.exists() else (desk_res / "app.asar")
    assert source_asar.exists(), f"Source app.asar not found at {source_asar}"
    orig_hash = sha256_file(source_asar)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        mock_desk = tmp_root / "antigravity"
        (mock_desk / "resources").mkdir(parents=True)
        state_dir = tmp_root / "state"
        test_asar = mock_desk / "resources" / "app.asar"
        shutil.copy2(source_asar, test_asar)

        t0 = time.perf_counter()
        ok, msg = rtl.patch_desktop(mock_desk, state_dir, force=False)
        dt_patch = (time.perf_counter() - t0) * 1000
        assert ok, msg
        print(f"  [PASS] Initial ASAR patch succeeded in {dt_patch:.1f} ms: {msg}")

        bak = mock_desk / "resources" / "app.asar.orig.bak"
        assert bak.exists() and sha256_file(bak) == orig_hash, "Backup SHA256 mismatch"

        checked_files = verify_all_asar_integrities(test_asar)
        print(f"  [PASS] Verified ASAR binary structure & SHA-256 integrity across all {checked_files} packed files")

        header, payload_start = rtl.parse_asar_header(test_asar)
        for rel_js in ("dist/main.js", "dist/preload.js"):
            js_code = rtl.read_asar_text_file(test_asar, header, payload_start, rel_js)
            assert js_code and rtl.JS_START in js_code, f"Marker missing in {rel_js}"
            assert js_code.count(rtl.JS_START) == 1, f"Duplicate marker in {rel_js}"
            js_tmp = tmp_root / Path(rel_js).name
            js_tmp.write_text(js_code, encoding="utf-8")
            proc = subprocess.run(["node", "--check", str(js_tmp)], capture_output=True, text=True)
            assert proc.returncode == 0, f"node --check failed on {rel_js}: {proc.stderr}"
        print("  [PASS] node --check passed with 0 syntax errors on patched main.js & preload.js")

        t1 = time.perf_counter()
        ok2, msg2 = rtl.patch_desktop(mock_desk, state_dir, force=False)
        dt_cache = (time.perf_counter() - t1) * 1000
        assert ok2 and "cache hit" in msg2, msg2
        print(f"  [PASS] Smart Launcher cached check ran in {dt_cache:.2f} ms")

        ok3, _ = rtl.patch_desktop(mock_desk, state_dir, force=True)
        assert ok3
        h3, ps3 = rtl.parse_asar_header(test_asar)
        main3 = rtl.read_asar_text_file(test_asar, h3, ps3, "dist/main.js") or ""
        assert main3.count(rtl.JS_START) == 1, "Idempotency check failed"
        print("  [PASS] Force re-patch is strictly idempotent")

        time.sleep(0.02)
        shutil.copy2(source_asar, test_asar)
        os.utime(test_asar, None)
        assert not rtl.is_desktop_asar_patched(test_asar)
        ok_upd, msg_upd = rtl.patch_desktop(mock_desk, state_dir, force=False)
        assert ok_upd and rtl.is_desktop_asar_patched(test_asar), f"Update auto-repatch failed: {msg_upd}"
        print("  [PASS] Simulated Antigravity update -> Smart Launcher re-patched automatically")

        ok_res, msg_res = rtl.restore_desktop(mock_desk, state_dir)
        assert ok_res, msg_res
        assert sha256_file(test_asar) == orig_hash, "Restored app.asar does not match original SHA256!"
        print(f"  [PASS] Restore verified: byte-for-byte SHA-256 match ({orig_hash[:16]}...)")


def test_rtl_dom_and_header_toolbar() -> None:
    js_path = rtl.ASSETS_DIR / "agy-rtl.js"
    css_path = rtl.ASSETS_DIR / "agy-rtl.css"
    # Verify zero innerHTML usage in agy-rtl.js (Trusted Types compliance)
    raw_js = js_path.read_text(encoding="utf-8")
    assert "innerHTML" not in raw_js and "outerHTML" not in raw_js and "insertAdjacentHTML" not in raw_js, (
        "agy-rtl.js must not use innerHTML/outerHTML for Trusted Types safety!"
    )
    print("  [PASS] Verified zero innerHTML/TrustedHTML violations in agy-rtl.js")

    raw_css = css_path.read_text(encoding="utf-8")
    for token in (
        "@keyframes agy-shimmer-text-mask-rtl",
        "@keyframes agy-shimmer-text-content-rtl",
        "@keyframes agy-shimmer-text-rtl",
        "animation-name: agy-shimmer-text-mask-rtl !important;",
        "animation-name: agy-shimmer-text-content-rtl !important;",
        "[data-agy-fa=\"1\"] [data-slot-out]",
    ):
        assert token in raw_css, f"Missing expected RTL shimmer CSS rule: {token}"
    print("  [PASS] Verified RTL shimmer keyframes & slot-out alignment rules in agy-rtl.css")

    harness = r"""
const fs = require('fs');
const assert = require('assert');

const store = {};
global.localStorage = {
  getItem: (k) => Object.prototype.hasOwnProperty.call(store, k) ? store[k] : null,
  setItem: (k, v) => { store[k] = String(v); }
};

class FakeNode {
  constructor(nodeType, tagOrText) {
    this.nodeType = nodeType;
    if (nodeType === 3) {
      this.nodeValue = tagOrText;
    } else {
      this.tagName = tagOrText.toUpperCase();
      this.attrs = {};
      this.childNodes = [];
      this.className = '';
      this.id = '';
      this.value = '';
      this.listeners = {};
      this.style = { setProperty(k, v) { this[k] = v; } };
    }
    this.parentElement = null;
  }
  get firstChild() { return this.childNodes[0] || null; }
  get nextSibling() {
    if (!this.parentElement) return null;
    const idx = this.parentElement.childNodes.indexOf(this);
    return idx >= 0 ? (this.parentElement.childNodes[idx + 1] || null) : null;
  }
  get children() { return this.childNodes.filter(c => c.nodeType === 1); }
  get textContent() {
    if (this.nodeType === 3) return this.nodeValue;
    return this.childNodes.map(c => c.textContent).join('');
  }
  set textContent(v) {
    this.childNodes = [new FakeNode(3, String(v))];
    this.childNodes[0].parentElement = this;
  }
  appendChild(child) {
    if (child.parentElement) {
      const idx = child.parentElement.childNodes.indexOf(child);
      if (idx !== -1) child.parentElement.childNodes.splice(idx, 1);
    }
    child.parentElement = this;
    this.childNodes.push(child);
    return child;
  }
  insertBefore(newNode, refNode) {
    if (!refNode) return this.appendChild(newNode);
    if (newNode.parentElement) {
      const oldIdx = newNode.parentElement.childNodes.indexOf(newNode);
      if (oldIdx !== -1) newNode.parentElement.childNodes.splice(oldIdx, 1);
    }
    const idx = this.childNodes.indexOf(refNode);
    newNode.parentElement = this;
    if (idx === -1) this.childNodes.push(newNode);
    else this.childNodes.splice(idx, 0, newNode);
    return newNode;
  }
  contains(other) {
    let cur = other;
    while (cur) {
      if (cur === this) return true;
      cur = cur.parentElement;
    }
    return false;
  }
  getBoundingClientRect() { return { top: 8, bottom: 32, left: 800, right: 876 }; }
  setAttribute(k, v) {
    if (k === 'id') this.id = String(v);
    this.attrs[k] = String(v);
  }
  getAttribute(k) {
    if (k === 'id') return this.id || null;
    return Object.prototype.hasOwnProperty.call(this.attrs, k) ? this.attrs[k] : null;
  }
  hasAttribute(k) {
    if (k === 'id') return Boolean(this.id);
    return Object.prototype.hasOwnProperty.call(this.attrs, k);
  }
  removeAttribute(k) {
    if (k === 'id') this.id = '';
    delete this.attrs[k];
  }
  addEventListener(ev, fn) { (this.listeners[ev] = this.listeners[ev] || []).push(fn); }
  dispatchEvent(ev, payload = {}) {
    for (const fn of (this.listeners[ev] || [])) {
      fn(Object.assign({ stopPropagation() {}, preventDefault() {}, target: this }, payload));
    }
  }
  matchesSimple(sel) {
    sel = sel.trim();
    if (sel.startsWith('#')) return this.id === sel.slice(1);
    if (sel === 'input:not([type])') return this.tagName === 'INPUT' && !this.hasAttribute('type');
    if (sel.startsWith('input[type="')) return this.tagName === 'INPUT' && this.getAttribute('type') === sel.slice(12, -2);
    if (sel === '[data-testid^="open-editor"]') {
      const tid = this.getAttribute('data-testid') || '';
      return tid.startsWith('open-editor');
    }
    if (sel.startsWith('[data-testid="')) return this.getAttribute('data-testid') === sel.slice(14, -2);
    if (sel === '[contenteditable="true"]') return this.getAttribute('contenteditable') === 'true';
    if (sel.startsWith('[role="')) return this.getAttribute('role') === sel.slice(7, -2);
    if (sel === '[data-agy-fa="1"]') return this.getAttribute('data-agy-fa') === '1';
    if (sel === '[data-browser-hole]') return this.hasAttribute('data-browser-hole');
    if (sel.includes('.')) {
      const [tagPart, ...classes] = sel.split('.');
      if (tagPart && this.tagName !== tagPart.toUpperCase()) return false;
      const myClasses = (this.className || '').split(/\s+/);
      return classes.every(c => myClasses.includes(c));
    }
    return this.tagName === sel.toUpperCase();
  }
  matches(selectorGroup) {
    return selectorGroup.split(',').some(s => {
      const parts = s.trim().split(/\s+/).filter(p => p !== '>');
      if (parts.length === 1) return this.matchesSimple(parts[0]);
      if (!this.matchesSimple(parts[parts.length - 1])) return false;
      let cur = this.parentElement;
      for (let i = parts.length - 2; i >= 0; i--) {
        while (cur && !cur.matchesSimple(parts[i])) cur = cur.parentElement;
        if (!cur) return false;
        cur = cur.parentElement;
      }
      return true;
    });
  }
  closest(selectorGroup) {
    let cur = this;
    while (cur && cur.nodeType === 1) {
      if (cur.matches(selectorGroup)) return cur;
      cur = cur.parentElement;
    }
    return null;
  }
  querySelectorAll(selectorGroup) {
    const out = [];
    const visit = (n) => {
      for (const c of n.children) {
        if (c.matches(selectorGroup)) out.push(c);
        visit(c);
      }
    };
    visit(this);
    return out;
  }
  querySelector(selectorGroup) {
    return this.querySelectorAll(selectorGroup)[0] || null;
  }
}

const el = (tag, attrs = {}, ...kids) => {
  const n = new FakeNode(1, tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === 'class') n.className = v;
    else n.setAttribute(k, v);
  }
  for (const k of kids) {
    n.appendChild(typeof k === 'string' ? new FakeNode(3, k) : k);
  }
  return n;
};

const html = el('html');
const body = el('body');
html.appendChild(body);

// Simulate exact Antigravity 2.0 TitleBarRight DOM from screenshot
const headerActionRow = el('div', { class: 'flex items-center gap-1' },
  el('button', { 'data-testid': 'open-editor-single' }, 'Open IDE')
);
const headerRightOuter = el('div', { class: 'flex items-center justify-end shrink-0' }, headerActionRow);
body.appendChild(headerRightOuter);

// Chat elements
const pFa = el('p', {}, 'این یک متن فارسی همراه با ', el('code', {}, 'app.asar'), ' است.');
const pEngFirstFa = el('p', {}, 'Antigravity یک محیط توسعه هوشمند است.');
const pEn = el('p', {}, 'Run ', el('code', {}, 'npm test'), ' to verify.');
const slashCmdBubble = el('div', { class: 'user-msg' },
  el('div', { class: 'slash-chip' }, el('svg', {}), el('span', {}, 'plan')),
  'شروع کن و هرجا نیاز بود سوال کن و تائیدیه بگیر'
);
body.appendChild(pFa);
body.appendChild(pEngFirstFa);
body.appendChild(pEn);
body.appendChild(slashCmdBubble);

// Animated shimmer status bars (Persian vs English + deeply nested GSc transition slot)
const shimmerFaInner = el('span', { class: 'text-muted-foreground' }, 'بررسی process_auto_delivery و سازوکار قیمت‌گذاری');
const shimmerFaContent = el('span', { class: 'shimmer-text-content' }, shimmerFaInner);
const shimmerFaMask = el('span', { class: 'shimmer-text-mask' }, shimmerFaContent);
const shimmerFa = el('span', { class: 'animate-shimmer-text text-muted-foreground truncate min-w-0' }, shimmerFaMask);

const shimmerEnSlotIn = el('span', { 'data-slot-in': '' }, 'Working');
const shimmerEnSlot = el('span', { 'data-slot': '' }, shimmerEnSlotIn);
const shimmerEnInner = el('span', { class: 'text-muted-foreground' }, shimmerEnSlot);
const shimmerEnContent = el('span', { class: 'shimmer-text-content' }, shimmerEnInner);
const shimmerEnMask = el('span', { class: 'shimmer-text-mask' }, shimmerEnContent);
const shimmerEn = el('span', { class: 'animate-shimmer-text text-muted-foreground truncate min-w-0' }, shimmerEnMask);

body.appendChild(shimmerFa);
body.appendChild(shimmerEn);

const docListeners = {};
global.document = {
  readyState: 'complete',
  documentElement: html,
  body: body,
  createElement: (t) => new FakeNode(1, t),
  createElementNS: (_ns, t) => new FakeNode(1, t),
  createTextNode: (t) => new FakeNode(3, t),
  querySelector: (s) => html.querySelector(s),
  querySelectorAll: (s) => html.querySelectorAll(s),
  addEventListener: (ev, fn) => { (docListeners[ev] = docListeners[ev] || []).push(fn); }
};
global.window = {
  innerWidth: 1280,
  getComputedStyle: () => ({ backgroundColor: 'rgb(19, 19, 19)' }),
  addEventListener: () => {}
};
global.location = { protocol: 'https:', hostname: '127.0.0.1' };
let activeObserverCb = null;
global.MutationObserver = class {
  constructor(cb) { activeObserverCb = cb; }
  observe() {}
};
global.requestAnimationFrame = (fn) => fn();

eval(fs.readFileSync(process.argv[2], 'utf8'));

// 1. Verify Toolbar mounted right before headerActionRow (to the left of Open IDE!)
assert.strictEqual(headerRightOuter.children[0].id, 'agy-rtl-toolbar-host', 'Toolbar must mount right before Open IDE action group');
assert.strictEqual(headerRightOuter.children[1], headerActionRow);

// 2. Verify Popover created on body & opens on button click
const pop = body.querySelector('#agy-rtl-popover');
assert.ok(pop, 'Popover must exist on body');
assert.strictEqual(pop.hasAttribute('hidden'), true, 'Popover starts hidden');

const trigger = headerRightOuter.children[0].children[0];
trigger.dispatchEvent('click');
assert.strictEqual(pop.hasAttribute('hidden'), false, 'Popover opens on trigger click');

// 3. Verify Smart BiDi Shimmer (RTL for Persian, LTR for English, and live switching)
assert.strictEqual(shimmerFa.getAttribute('data-agy-fa'), '1', 'Persian shimmer root must get data-agy-fa=1');
assert.strictEqual(shimmerFa.getAttribute('dir'), 'rtl', 'Persian shimmer root must get dir=rtl');
assert.strictEqual(shimmerFaMask.getAttribute('data-agy-fa'), null, 'shimmer-text-mask must never own data-agy-fa');
assert.strictEqual(shimmerFaContent.getAttribute('data-agy-fa'), null, 'shimmer-text-content must never own data-agy-fa');

assert.strictEqual(shimmerEn.getAttribute('data-agy-fa'), null, 'English shimmer root must stay LTR');
assert.strictEqual(shimmerEn.getAttribute('dir'), null, 'English shimmer root must not have dir=rtl');

// Simulate live transition inside deeply nested [data-slot-in]: English -> Persian
shimmerEnSlotIn.textContent = 'تحلیل معماری پایگاه داده';
activeObserverCb([{ type: 'characterData', target: shimmerEnSlotIn.firstChild }]);
assert.strictEqual(shimmerEn.getAttribute('data-agy-fa'), '1', 'Live English->Persian shimmer update must switch root to RTL');
assert.strictEqual(shimmerEn.getAttribute('dir'), 'rtl', 'Live English->Persian shimmer update must set dir=rtl');
assert.strictEqual(shimmerEnMask.getAttribute('data-agy-fa'), null, 'Inner mask must remain clean after live update');
assert.strictEqual(shimmerEnSlotIn.getAttribute('data-agy-fa'), null, 'Inner data-slot-in must remain clean after live update');

// Simulate live transition back: Persian -> English
shimmerEnSlotIn.textContent = 'Running verification suite';
activeObserverCb([{ type: 'characterData', target: shimmerEnSlotIn.firstChild }]);
assert.strictEqual(shimmerEn.getAttribute('data-agy-fa'), null, 'Live Persian->English shimmer update must revert to LTR');
assert.strictEqual(shimmerEn.getAttribute('dir'), null, 'Live Persian->English shimmer update must clear dir');

// 4. Verify Alt+Shift+R hotkey toggles master RTL switch & updates DOM live
assert.strictEqual(html.getAttribute('data-agy-rtl-enabled'), '1');
assert.strictEqual(pFa.getAttribute('dir'), 'rtl');
for (const fn of (docListeners['keydown'] || [])) {
  fn({ altKey: true, shiftKey: true, code: 'KeyR', preventDefault() {} });
}
assert.strictEqual(html.getAttribute('data-agy-rtl-enabled'), '0', 'Alt+Shift+R should pause RTL');
assert.strictEqual(pFa.getAttribute('data-agy-fa'), null, 'Pausing RTL clears data-agy-fa');
for (const fn of (docListeners['keydown'] || [])) {
  fn({ altKey: true, shiftKey: true, code: 'KeyR', preventDefault() {} });
}
assert.strictEqual(html.getAttribute('data-agy-rtl-enabled'), '1', 'Alt+Shift+R re-enables RTL');
assert.strictEqual(pEngFirstFa.getAttribute('dir'), 'rtl');
assert.strictEqual(pEn.getAttribute('data-agy-fa'), null);
assert.strictEqual(slashCmdBubble.getAttribute('dir'), 'rtl', 'Slash-command (/plan) bubble with Persian text must be RTL');
assert.strictEqual(slashCmdBubble.getAttribute('data-agy-fa'), '1', 'Slash-command (/plan) bubble must get Vazirmatn RTL marker');

console.log('ALL_V2_TOOLBAR_AND_DOM_ASSERTIONS_PASSED');
"""
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as tf:
        tf.write(harness)
        harness_path = tf.name
    try:
        proc = subprocess.run(["node", harness_path, str(js_path)], capture_output=True, text=True)
        assert proc.returncode == 0 and "ALL_V2_TOOLBAR_AND_DOM_ASSERTIONS_PASSED" in proc.stdout, (
            f"V2 Toolbar & DOM test failed:\nSTDOUT: {proc.stdout}\nSTDERR: {proc.stderr}"
        )
        print("  [PASS] Header Toolbar anchoring (next to Open IDE), Popover toggle, localStorage, and Alt+Shift+R verified")
    finally:
        os.unlink(harness_path)


def test_linux_wrapper_and_desktop_shortcuts() -> None:
    import stat

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        desk_dir = root / "Antigravity-x64"
        ide_dir = root / "Antigravity-IDE"
        state_dir = root / "state"
        apps_dir = root / "applications"
        user_desk = root / "Desktop"
        user_desk.mkdir(parents=True, exist_ok=True)

        exe = desk_dir / "antigravity"
        exe.parent.mkdir(parents=True, exist_ok=True)
        exe.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        exe.chmod(exe.stat().st_mode | stat.S_IXUSR)

        wrapper = root / "antigravity-wrapper"
        wrapper.write_text(f'#!/bin/bash\nexec "{exe}" --no-sandbox "$@"\n', encoding="utf-8")
        assert rtl._extract_exec_target_from_wrapper(wrapper) == exe.resolve(), "Wrapper target extraction failed"

        ok, msg = rtl.install_linux_shortcuts(
            desk_dir, ide_dir, state_dir, apps_dir=apps_dir, user_desktop_dir=user_desk
        )
        assert ok, msg
        app_entry = apps_dir / "antigravity-rtl.desktop"
        desk_entry = user_desk / "antigravity-rtl.desktop"
        assert app_entry.exists() and desk_entry.exists(), "Linux .desktop shortcuts not created"
        assert "Name=Antigravity RTL" in app_entry.read_text(encoding="utf-8")

        ok2, msg2 = rtl.restore_linux_shortcuts(apps_dir=apps_dir, user_desktop_dir=user_desk)
        assert ok2, msg2
        assert not app_entry.exists() and not desk_entry.exists(), "Linux .desktop shortcuts not removed"
        print("  [PASS] Linux wrapper extraction & .desktop shortcut install/restore verified")


if __name__ == "__main__":
    print("=== Running Antigravity Persian RTL V2 Studio Verification Suite ===")
    test_desktop_asar_roundtrip_and_update()
    test_rtl_dom_and_header_toolbar()
    test_linux_wrapper_and_desktop_shortcuts()
    print("=== ALL V2 TESTS PASSED SUCCESSFULLY ===")
