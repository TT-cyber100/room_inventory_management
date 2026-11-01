<div align="center">

# 🏡 Roomly

### Your room, your things — all in one cozy pixel world.

A playful desktop inventory manager that helps you organize your belongings, remember where you put them, and keep track of what you bought.

**🍬 Pixel-art design · 🛏️ Interactive room · 📦 Personal inventory · 💗 Built with Python**

[**Download Roomly for macOS**](../../releases) · [Report a bug](../../issues/new) · [Share feedback](../../issues/new)

</div>

---

## ✨ About Roomly

Ever forgotten where you stored something or how much it cost? **Roomly** combines practical home inventory tracking with a colorful, interactive room. Arrange furniture, add items to their storage locations, and keep purchase details together in one place.

Roomly is an **early beta project**. I'm sharing it to learn from real users and improve the experience — feedback is very welcome!

## 🌷 Features

- **Explore your room:** View and rotate a charming, pixel-style room scene.
- **Organize by furniture:** Add and manage beds, desks, wardrobes, bookshelves, and storage boxes.
- **Track your belongings:** Save item names, categories, quantities, and notes.
- **Keep purchase information:** Record prices, dates, shops, and purchase URLs.
- **Find items quickly:** Search by item name, category, notes, or furniture location.
- **See an overview:** Check item counts and purchase-value summaries in the dashboard.
- **Save locally:** Inventory is stored as JSON on your computer; no account is required.

## 📸 Preview

> Screenshots coming soon! Add an image at `assets/roomly-preview.png`, then uncomment the line below.

<!-- ![Roomly desktop preview](assets/roomly-preview.png) -->

## ⬇️ Download & install (macOS)

1. Open the [**Releases**](../../releases) page.
2. Download `Roomly.app.zip` from the latest release.
3. Unzip it and move **Roomly.app** into your Applications folder (optional).
4. Open Roomly and start organizing!

**Note:** This is an early beta build. The macOS package has not yet been verified on every Mac model or macOS version. Because the app may not be Apple-notarized, macOS may show a security warning. Only open software from sources you trust; consult [Apple's guidance on opening apps safely](https://support.apple.com/guide/mac-help/open-a-mac-app-from-an-unidentified-developer-mh40616/mac) if you encounter a warning.

> **Windows / Linux:** Prebuilt downloads aren't available yet. You can try running the Python source locally if Python and Tkinter are installed.

## 🐍 Run from source

The project is currently a single Python file and uses Python's standard library (including Tkinter).

```bash
# Clone your repository and enter its folder
# Then run:
python3 roomly.py
```

On some systems, Tkinter needs to be installed separately. Run `python3 -m tkinter` to check whether it is available.

By default, Roomly saves your data at:

```text
~/.roomly/room-3d.json
```

To choose a different data file:

```bash
python3 roomly.py --data ./my-room.json
```

**Tip:** Back up your JSON file before upgrading or experimenting with beta builds. Don't publish your personal inventory JSON to a public repository.

## 💬 Help shape Roomly

I'm especially interested in feedback on:

- Is it easy to add furniture and items?
- Does the room interaction feel intuitive?
- What features would make Roomly useful in your everyday life?
- Have you encountered bugs, display issues, or installation problems?

**[💌 Share a suggestion or report a bug →](../../issues/new)**

When submitting a bug, please include your macOS version, what you expected, what happened, and steps to reproduce it. Please avoid including sensitive information about your belongings.

## 🛠️ Built with

- **Python 3** — application logic and data models
- **Tkinter** — desktop interface and interactions
- **Custom Python pixel renderer** — room graphics and sprites
- **JSON** — local data storage
- **PyInstaller** — macOS application packaging

## 🌱 Project status

**v0.1.0 · Early beta** — currently focused on usability testing, feedback, and improving the desktop experience. A browser-based edition is an idea for the future, not a released feature.

---

<div align="center">

Made with curiosity and a love for turning ideas into useful little products. ✨

**If you try Roomly, I'd love to hear what you think!**

</div>
