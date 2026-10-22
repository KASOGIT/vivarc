"""Read-only export of Arc spaces to Netscape bookmark files (one per space) plus a site-icon seed.

Each file contains `Arc - <space>` with Favorites, Pinned (folder tree kept) and Unpinned (today).
Import a file into the matching Vivaldi profile: Cmd+Shift+B > Import Bookmarks and Settings > HTML file.
Nothing in Arc's folders is modified.
"""
import base64
import glob
import html
import json
import os
import re
import shutil
import sqlite3
import tempfile
from urllib.parse import urlsplit

MAX_ICON_BYTES = 12000


def _escape(text):
    return html.escape(text or "", quote=True)


def _container(sidebar):
    for c in sidebar["sidebar"]["containers"]:
        if isinstance(c, dict) and "spaces" in c:
            return c
    raise ValueError("no spaces found in StorableSidebar.json")


def spaces_to_html(sidebar):
    """Return {space title: (html text, [urls])}."""
    c = _container(sidebar)
    by_id = {i["id"]: i for i in c["items"] if isinstance(i, dict)}
    kind = lambda item: next(iter(item.get("data", {})), "?")

    def entries(item_id, out, urls, depth):
        item = by_id[item_id]
        pad = "    " * depth
        k = kind(item)
        if k == "tab":
            tab = item["data"]["tab"]
            if tab.get("savedURL"):
                urls.append(tab["savedURL"])
                title = item.get("title") or tab.get("savedTitle") or tab["savedURL"]
                out.append(f'{pad}<DT><A HREF="{_escape(tab["savedURL"])}">{_escape(title)}</A>')
            return
        if k == "list":
            out.append(f'{pad}<DT><H3>{_escape(item.get("title") or "Untitled")}</H3>')
            out.append(f"{pad}<DL><p>")
            for child in item.get("childrenIds", []):
                if child in by_id:
                    entries(child, out, urls, depth + 1)
            out.append(f"{pad}</DL><p>")
        else:  # split views and anything else: flatten the children
            for child in item.get("childrenIds", []):
                if child in by_id:
                    entries(child, out, urls, depth)

    def folder(name, node, out, urls, depth):
        pad = "    " * depth
        out.append(f"{pad}<DT><H3>{_escape(name)}</H3>")
        out.append(f"{pad}<DL><p>")
        for child in node.get("childrenIds", []):
            if child in by_id:
                entries(child, out, urls, depth + 1)
        out.append(f"{pad}</DL><p>")

    top = c.get("topAppsContainerIDs", [])
    # profile markers are strings or small dicts (e.g. {"default": true}), so compare with ==
    favorites = [(top[i], by_id[top[i + 1]]) for i in range(0, len(top) - 1, 2) if top[i + 1] in by_id]
    result = {}
    for space in (s for s in c["spaces"] if isinstance(s, dict)):
        ids = [x for x in space["newContainerIDs"] if isinstance(x, str)]
        out = ["<!DOCTYPE NETSCAPE-Bookmark-file-1>",
               '<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">',
               "<TITLE>Bookmarks</TITLE>", "<H1>Bookmarks</H1>", "<DL><p>",
               f'    <DT><H3>Arc - {_escape(space["title"])}</H3>', "    <DL><p>"]
        urls = []
        fav = next((node for profile, node in favorites if profile == space.get("profile")), None)
        if fav is not None:
            folder("Favorites", fav, out, urls, 2)
        else:
            out += ["        <DT><H3>Favorites</H3>", "        <DL><p>", "        </DL><p>"]
        folder("Pinned", by_id[ids[0]], out, urls, 2)
        folder("Unpinned (today)", by_id[ids[1]], out, urls, 2)
        out += ["    </DL><p>", "</DL><p>"]
        result[space["title"]] = ("\n".join(out) + "\n", urls)
    return result


def origin(url):
    p = urlsplit(url)
    return f"{p.scheme}://{p.netloc}" if p.scheme and p.netloc else ""


def collect_icons(arc_user_data, wanted_origins):
    """Best PNG per origin from Arc's Favicons databases (opened as copies)."""
    best = {}
    tmp = tempfile.mkdtemp()
    try:
        for db_path in glob.glob(os.path.join(arc_user_data, "*", "Favicons")):
            copy = os.path.join(tmp, re.sub(r"\W", "_", db_path) + ".db")
            shutil.copy(db_path, copy)
            db = sqlite3.connect(copy)
            try:
                rows = db.execute(
                    "select m.page_url, b.image_data, b.width from icon_mapping m "
                    "join favicon_bitmaps b on b.icon_id = m.icon_id where b.image_data is not null")
                for page_url, data, width in rows:
                    o = origin(page_url)
                    if o not in wanted_origins or not data or data[:4] != b"\x89PNG" or len(data) > MAX_ICON_BYTES:
                        continue
                    score = abs((width or 0) - 32) - (0 if page_url.rstrip("/") == o else 0.5)
                    if o not in best or score < best[o][0]:
                        best[o] = (score, data)
            except sqlite3.Error:
                continue
            finally:
                db.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return {o: "data:image/png;base64," + base64.b64encode(d).decode() for o, (_, d) in best.items()}


def run(arc_dir, out_dir, home_dir):
    with open(os.path.join(arc_dir, "StorableSidebar.json"), encoding="utf8") as f:
        sidebar = json.load(f)
    os.makedirs(out_dir, exist_ok=True)
    all_urls = set()
    for title, (text, urls) in spaces_to_html(sidebar).items():
        name = re.sub(r"[^\w.-]+", "-", title.lower()).strip("-") or "space"
        path = os.path.join(out_dir, f"arc-{name}.html")
        with open(path, "w", encoding="utf8") as f:
            f.write(text)
        all_urls.update(urls)
        print(f"{title}: {len(urls)} links -> {path}")
    icons = collect_icons(os.path.join(arc_dir, "User Data"), {origin(u) for u in all_urls} - {""})
    with open(os.path.join(home_dir, "icons.js"), "w", encoding="utf8") as f:
        f.write("window.__vmIcons = " + json.dumps(icons, separators=(",", ":")) + ";\n")
    print(f"{len(icons)} site icons saved. Import each HTML file in the matching Vivaldi profile,"
          " then run: ./vivarc.py apply")
