#!/usr/bin/env python3
from __future__ import annotations

import html
import re
import uuid
import zipfile
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
CHAPTER_DIR = ROOT / "chapters"
DIST = ROOT / "dist"
BOOK_TITLE = "novel09"
LANG = "zh-CN"

VOLUMES = [
    (1, 104, "第一卷"),
    (105, 190, "第二卷"),
    (191, 238, "第三卷"),
    (239, 285, "第四卷·故人归来"),
    (286, 330, "第五卷·迟到了四百年的真相"),
    (331, 370, "第六卷"),
    (371, 412, "第七卷"),
    (413, 450, "第八卷·终局"),
]

CSS = """
html { writing-mode: horizontal-tb; }
body {
  font-family: serif;
  line-height: 1.85;
  margin: 5%;
  text-align: justify;
}
h1 { font-size: 1.65em; text-align: center; margin: 2.5em 0 1.8em; }
h2 { font-size: 1.35em; text-align: center; margin: 2em 0 1.5em; }
p { margin: 0.72em 0; text-indent: 2em; }
p.noindent, p.separator { text-indent: 0; text-align: center; }
.cover { text-align: center; margin-top: 30%; }
.cover h1 { font-size: 2.3em; margin-bottom: 1em; }
.cover p { text-indent: 0; color: #666; }
nav ol { list-style-type: none; padding-left: 1em; }
nav li { margin: 0.35em 0; }
a { text-decoration: none; }
""".strip()


def chapter_number(path: Path) -> int:
    m = re.match(r"(\d{3})_", path.name)
    if not m:
        raise ValueError(path.name)
    return int(m.group(1))


def clean_inline(s: str) -> str:
    s = re.sub(r"\*\*(.*?)\*\*", r"\1", s)
    s = re.sub(r"\*(.*?)\*", r"\1", s)
    s = re.sub(r"`([^`]*)`", r"\1", s)
    return html.escape(s, quote=False)


def parse_markdown(md: str, fallback_title: str):
    lines = md.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    title = fallback_title
    start = 0
    for i, raw in enumerate(lines):
        s = raw.strip()
        if not s:
            continue
        if s.startswith("# "):
            title = s[2:].strip()
            start = i + 1
        break

    blocks = []
    buf = []

    def flush():
        nonlocal buf
        if buf:
            text = " ".join(x.strip() for x in buf if x.strip()).strip()
            if text:
                blocks.append(("p", text))
            buf = []

    for raw in lines[start:]:
        s = raw.strip()
        if not s:
            flush()
            continue
        if s in {"---", "——", "***", "* * *"}:
            flush()
            blocks.append(("sep", "——"))
            continue
        if s.startswith("#"):
            flush()
            heading = s.lstrip("#").strip()
            if heading:
                blocks.append(("h2", heading))
            continue
        if s.startswith("> "):
            s = s[2:].strip()
        buf.append(s)
    flush()
    return title, blocks


def xhtml_doc(title: str, body: str) -> str:
    return f'''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="{LANG}" lang="{LANG}">
<head>
  <meta charset="utf-8" />
  <title>{html.escape(title)}</title>
  <link rel="stylesheet" type="text/css" href="style.css" />
</head>
<body>
{body}
</body>
</html>'''


def render_chapter(title: str, blocks) -> str:
    out = [f"<h1>{clean_inline(title)}</h1>"]
    for kind, text in blocks:
        if kind == "sep":
            out.append('<p class="separator">——</p>')
        elif kind == "h2":
            out.append(f"<h2>{clean_inline(text)}</h2>")
        else:
            out.append(f"<p>{clean_inline(text)}</p>")
    return "\n".join(out)


def volume_for(n: int):
    for start, end, name in VOLUMES:
        if start <= n <= end:
            return start, end, name
    return None


def main():
    DIST.mkdir(exist_ok=True)
    chapters = sorted(CHAPTER_DIR.glob("[0-9][0-9][0-9]_*.md"), key=chapter_number)
    if not chapters:
        raise SystemExit("No chapter files found")

    nums = [chapter_number(p) for p in chapters]
    expected = list(range(nums[0], nums[-1] + 1))
    missing = sorted(set(expected) - set(nums))
    if missing:
        raise SystemExit(f"Missing chapters: {missing}")
    if nums[0] != 1 or nums[-1] != 450:
        raise SystemExit(f"Expected chapters 1..450, got {nums[0]}..{nums[-1]}")

    parsed = []
    txt_parts = []
    for p in chapters:
        n = chapter_number(p)
        md = p.read_text(encoding="utf-8")
        fallback = p.stem.split("_", 1)[-1]
        title, blocks = parse_markdown(md, fallback)
        parsed.append((n, title, blocks))
        plain = [title, ""]
        for kind, text in blocks:
            if kind == "sep":
                plain.extend(["——", ""])
            else:
                plain.extend([re.sub(r"[*`#>]", "", text), ""])
        txt_parts.append("\n".join(plain).strip())

    txt_path = DIST / f"{BOOK_TITLE}_全文_1-450章.txt"
    txt_path.write_text("\n\n\n".join(txt_parts) + "\n", encoding="utf-8")

    book_id = f"urn:uuid:{uuid.uuid4()}"
    modified = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    epub_path = DIST / f"{BOOK_TITLE}_全文_1-450章.epub"

    manifest = [
        '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
        '<item id="css" href="style.css" media-type="text/css"/>',
        '<item id="cover" href="cover.xhtml" media-type="application/xhtml+xml"/>',
        '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>',
    ]
    spine = ['<itemref idref="cover"/>']
    for n, _, _ in parsed:
        manifest.append(f'<item id="ch{n:03d}" href="ch{n:03d}.xhtml" media-type="application/xhtml+xml"/>')
        spine.append(f'<itemref idref="ch{n:03d}"/>')

    package = f'''<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid" xml:lang="{LANG}">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="bookid">{book_id}</dc:identifier>
    <dc:title>{BOOK_TITLE}</dc:title>
    <dc:language>{LANG}</dc:language>
    <dc:description>长篇东方玄幻小说，正文第1—450章。</dc:description>
    <meta property="dcterms:modified">{modified}</meta>
  </metadata>
  <manifest>
    {' '.join(manifest)}
  </manifest>
  <spine toc="ncx">
    {' '.join(spine)}
  </spine>
</package>'''

    container_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>'''

    cover_body = f'''<div class="cover">
<h1>{BOOK_TITLE}</h1>
<p>长篇东方玄幻小说</p>
<p>正文 · 第1—450章</p>
</div>'''

    nav_lines = ['<nav epub:type="toc" xmlns:epub="http://www.idpf.org/2007/ops" id="toc">', '<h1>目录</h1>', '<ol>']
    for start, end, vname in VOLUMES:
        nav_lines.append(f'<li><span>{html.escape(vname)}（第{start}—{end}章）</span><ol>')
        for n, title, _ in parsed:
            if start <= n <= end:
                nav_lines.append(f'<li><a href="ch{n:03d}.xhtml">{html.escape(title)}</a></li>')
        nav_lines.append('</ol></li>')
    nav_lines.extend(['</ol>', '</nav>'])
    nav = xhtml_doc("目录", "\n".join(nav_lines))

    play_order = 1
    navpoints = []
    for start, end, vname in VOLUMES:
        children = []
        for n, title, _ in parsed:
            if start <= n <= end:
                play_order += 1
                children.append(f'''<navPoint id="ch{n:03d}" playOrder="{play_order}">
<navLabel><text>{html.escape(title)}</text></navLabel>
<content src="ch{n:03d}.xhtml"/>
</navPoint>''')
        play_order += 1
        navpoints.append(f'''<navPoint id="vol{start}" playOrder="{play_order}">
<navLabel><text>{html.escape(vname)}</text></navLabel>
<content src="ch{start:03d}.xhtml"/>
{''.join(children)}
</navPoint>''')

    ncx = f'''<?xml version="1.0" encoding="UTF-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
<head><meta name="dtb:uid" content="{book_id}"/></head>
<docTitle><text>{BOOK_TITLE}</text></docTitle>
<navMap>{''.join(navpoints)}</navMap>
</ncx>'''

    with zipfile.ZipFile(epub_path, "w") as z:
        z.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml", container_xml, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/style.css", CSS, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/content.opf", package, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/cover.xhtml", xhtml_doc(BOOK_TITLE, cover_body), compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/nav.xhtml", nav, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/toc.ncx", ncx, compress_type=zipfile.ZIP_DEFLATED)
        for n, title, blocks in parsed:
            chapter_xhtml = xhtml_doc(title, render_chapter(title, blocks))
            z.writestr(f"OEBPS/ch{n:03d}.xhtml", chapter_xhtml, compress_type=zipfile.ZIP_DEFLATED)

    print(f"Built {epub_path}")
    print(f"Built {txt_path}")
    print(f"Chapters: {len(parsed)} ({nums[0]}..{nums[-1]})")


if __name__ == "__main__":
    main()
