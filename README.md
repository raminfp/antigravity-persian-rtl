# Antigravity RTL & Custom Font Studio

A lightweight, zero-dependency, **update-resilient** patcher and smart launcher for **Right-to-Left (RTL) typography** and **custom system fonts** in **Antigravity Desktop (2.0)** and **Antigravity IDE** — supporting both **Windows** and **Linux**.

![Antigravity RTL & Custom Font Toolbar Preview](docs/preview.png)

---

## Features

- **Custom Font Support (Any System Font):** Switch live between built-in presets (`Vazirmatn`, `Noto Sans Arabic`, `Cairo`, `Inter`, `Tahoma`, `Segoe UI`) or enter **any font installed on your system** (e.g., `IRANSansX`, `IBM Plex Sans Arabic`, `Rubik`, `JetBrains Mono`, etc.).
- **Smart BiDi / RTL Direction Detection:** Automatically aligns paragraphs, headings, lists, blockquotes, tables, question cards, and chat inputs for RTL languages (Arabic, Persian, Hebrew, Urdu, etc.) — even when a sentence starts with an English word like `React` or `Antigravity` — while keeping purely English messages `LTR`.
- **Strict `LTR` Isolation for Code & Terminals:** Code blocks (`pre`), inline code (`code`), the Monaco editor, `xterm` terminals, `KaTeX` math formulas, and the embedded browser remain strictly left-to-right.
- **In-App Control Toolbar (`RTL ⚙`):**
  - Instant enable/disable toggle + keyboard shortcut `Alt + Shift + R`
  - 3 direction modes: **Smart**, **Auto**, and **Force RTL**
  - Live font family selector + custom system font input
  - Live font size scaling (`85%` – `135%`) and paragraph line height (`Compact`, `Standard`, `Relaxed`)
  - Copy-safe localized digits (`ss01` OpenType feature)
  - Persistent settings across sessions with automatic Light/Dark theme matching
- **Update-Resilient Smart Launcher (Windows & Linux):**
  - Creates dedicated **`Antigravity RTL`** shortcuts (Windows Desktop/Start Menu `.lnk` and Linux `~/.local/share/applications/*.desktop`).
  - Checks patch state in ~2 ms on launch; if Antigravity updates, it automatically backs up the new version, re-applies the patch, and launches the app.
  - On Linux, automatically detects installations via `PATH` (including shell wrappers like `~/.local/bin/antigravity`) and preserves custom wrapper flags (e.g. `--proxy-server`, `--no-sandbox`).
- **Zero External Dependencies:** Pure Python 3 standard library — rebuilds `app.asar` headers and `SHA-256` integrity hashes without needing Node.js at runtime.

---

## Requirements

- **OS:** Windows 10/11 or Linux
- **Python 3**
- *(Optional)* Any custom fonts you want to use installed on your system (`Vazirmatn` falls back to Google Fonts if not installed locally)

---

## Quick Start

Clone the repository:

```bash
git clone https://github.com/raminfp/antigravity-persian-rtl.git
cd antigravity-persian-rtl
```

### Linux

```bash
chmod +x install-rtl.sh patch-now.sh uninstall-rtl.sh antigravity_rtl.py
./install-rtl.sh
```

- Launch **`Antigravity RTL`** from your application menu (or Desktop) so future Antigravity updates are patched automatically.
- If Antigravity is installed in a system directory like `/opt/antigravity`, patch with `sudo` and create user shortcuts separately:
  ```bash
  sudo python3 antigravity_rtl.py patch --target all --no-shortcuts
  python3 antigravity_rtl.py install-shortcuts
  ```

### Windows

Double-click **`Install-RTL.bat`**:
- Creates **`Antigravity RTL`** and **`Antigravity IDE RTL`** shortcuts on your Desktop and Start Menu.
- Patches Antigravity Desktop and IDE and launches the app.

---

## Adding Your Own Custom Font

1. Install any font you like on your OS (`.ttf` / `.otf` / `.woff2`).
2. Open Antigravity and click **`RTL ⚙`** in the top header bar.
3. Under **Display Font**, select **`Custom installed system font...`**.
4. Type the exact font family name (e.g. `Cairo`, `IBM Plex Sans Arabic`, `Inter`, `IRANSansX`) — changes apply live immediately.

---

## Project Files

| File | Purpose |
| --- | --- |
| `install-rtl.sh` / `Install-RTL.bat` | Install shortcuts and apply the initial patch (Linux / Windows) |
| `patch-now.sh` / `Patch-Now.bat` | Force re-apply the latest patch immediately (Linux / Windows) |
| `uninstall-rtl.sh` / `Uninstall-RTL.bat` | Remove RTL shortcuts and restore original files byte-for-byte |
| `antigravity_rtl.py` | Pure-Python cross-platform ASAR & IDE patcher, cache, and launcher |
| `assets/agy-rtl.css` | Typography, RTL layout, and toolbar styles |
| `assets/agy-rtl.js` | `MutationObserver` BiDi engine and live settings popover (Trusted Types safe) |
| `launch-desktop.vbs` / `launch-ide.vbs` | Silent Windows launchers (no console flash) |
| `test_antigravity_rtl.py` | Automated verification suite (ASAR integrity, update simulation, DOM, Linux shortcuts) |

---

## CLI Usage

```bash
# Check current patch status
python3 antigravity_rtl.py status

# Force patch both Desktop and IDE
python3 antigravity_rtl.py patch --target all --force

# Specify custom installation path (or use ANTIGRAVITY_DESKTOP_DIR / ANTIGRAVITY_IDE_DIR)
python3 antigravity_rtl.py patch --desktop-dir /path/to/antigravity

# Restore original files byte-for-byte
python3 antigravity_rtl.py restore --target all

# Run automated verification suite
python3 test_antigravity_rtl.py
```

---

## License

MIT License — see [LICENSE](LICENSE) for details.
