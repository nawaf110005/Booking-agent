"""Minimal, dependency-light Markdown -> PDF renderer.

Parses Markdown with markdown-it-py and renders it to a professional-looking PDF
with ReportLab Platypus. Handles headings, paragraphs, bullet/ordered lists,
GitHub-style tables, fenced code, blockquotes, horizontal rules, and inline
bold / italic / code / links.

Usage:
    from md2pdf import render_markdown_to_pdf
    render_markdown_to_pdf(open("doc.md").read(), "doc.pdf")
"""

from __future__ import annotations

import re
from html import escape
from pathlib import Path

from markdown_it import MarkdownIt
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    ListFlowable,
    ListItem,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# Brand palette
INK = colors.HexColor("#1F2933")
ACCENT = colors.HexColor("#2E7D5B")  # green — matches the seat-map "available"
MUTED = colors.HexColor("#52606D")
RULE = colors.HexColor("#C7D0D9")
HEADER_BG = colors.HexColor("#E8F1EC")
CODE_BG = colors.HexColor("#F4F6F8")

CONTENT_WIDTH = letter[0] - 2 * inch  # 1in margins


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    fonts = {"body": "Helvetica", "bold": "Helvetica-Bold", "mono": "Courier"}
    s: dict[str, ParagraphStyle] = {}
    s["body"] = ParagraphStyle("body", parent=base["Normal"], fontName=fonts["body"],
                               fontSize=10, leading=14.5, textColor=INK, spaceAfter=7,
                               alignment=TA_LEFT)
    s["h1"] = ParagraphStyle("h1", parent=s["body"], fontName=fonts["bold"], fontSize=19,
                             leading=23, textColor=ACCENT, spaceBefore=4, spaceAfter=10)
    s["h2"] = ParagraphStyle("h2", parent=s["body"], fontName=fonts["bold"], fontSize=14,
                             leading=18, textColor=INK, spaceBefore=14, spaceAfter=6)
    s["h3"] = ParagraphStyle("h3", parent=s["body"], fontName=fonts["bold"], fontSize=11.5,
                             leading=15, textColor=ACCENT, spaceBefore=10, spaceAfter=4)
    s["h4"] = ParagraphStyle("h4", parent=s["body"], fontName=fonts["bold"], fontSize=10.5,
                             leading=14, textColor=MUTED, spaceBefore=8, spaceAfter=3)
    s["li"] = ParagraphStyle("li", parent=s["body"], spaceAfter=3)
    s["cell"] = ParagraphStyle("cell", parent=s["body"], fontSize=8.7, leading=11.5, spaceAfter=0)
    s["cellh"] = ParagraphStyle("cellh", parent=s["cell"], fontName=fonts["bold"], textColor=INK)
    s["quote"] = ParagraphStyle("quote", parent=s["body"], leftIndent=14, textColor=MUTED,
                                fontName="Helvetica-Oblique", borderPadding=0)
    s["code"] = ParagraphStyle("code", parent=base["Code"], fontName=fonts["mono"], fontSize=8.3,
                               leading=11, textColor=INK, backColor=CODE_BG, borderPadding=6,
                               spaceBefore=2, spaceAfter=8)
    return s


def _inline(token, st: dict) -> str:
    """Render a markdown-it inline token's children to ReportLab mini-markup."""
    out: list[str] = []
    for c in token.children or []:
        t = c.type
        if t == "text":
            out.append(escape(c.content))
        elif t == "code_inline":
            out.append(f'<font face="Courier" backColor="#EEF1F3"> {escape(c.content)} </font>')
        elif t in ("strong_open",):
            out.append("<b>")
        elif t in ("strong_close",):
            out.append("</b>")
        elif t in ("em_open",):
            out.append("<i>")
        elif t in ("em_close",):
            out.append("</i>")
        elif t in ("s_open",):
            out.append("<strike>")
        elif t in ("s_close",):
            out.append("</strike>")
        elif t == "link_open":
            href = dict(c.attrs).get("href", "")
            out.append(f'<a href="{escape(href)}"><font color="#2E7D5B">')
        elif t == "link_close":
            out.append("</font></a>")
        elif t in ("softbreak", "hardbreak"):
            out.append("<br/>")
        elif t == "image":
            out.append(escape(c.content or dict(c.attrs).get("alt", "")))
    text = "".join(out)
    # ReportLab dislikes literal emoji/control; keep it simple
    return text


def render_markdown_to_pdf(md_text: str, out_path: str | Path, title: str | None = None) -> Path:
    st = _styles()
    md = MarkdownIt("commonmark").enable("table").enable("strikethrough")
    tokens = md.parse(md_text)

    story: list = []
    if title:
        story.append(Paragraph(escape(title), st["h1"]))
        story.append(HRFlowable(width="100%", thickness=1.2, color=ACCENT, spaceAfter=10))

    i = 0
    n = len(tokens)

    def collect_inline(idx: int) -> tuple[str, int]:
        """At a *_open token, find the inline token and return (markup, index_after_close)."""
        # idx points to *_open; next is inline; then *_close
        markup = ""
        j = idx + 1
        while j < n and tokens[j].type != "inline":
            j += 1
        if j < n:
            markup = _inline(tokens[j], st)
        # advance to matching close
        k = j
        while k < n and not tokens[k].type.endswith("_close"):
            k += 1
        return markup, k + 1

    def parse_list(idx: int, ordered: bool) -> tuple[ListFlowable, int]:
        items: list[ListItem] = []
        j = idx + 1  # after list_open
        while j < n and tokens[j].type not in ("bullet_list_close", "ordered_list_close"):
            if tokens[j].type == "list_item_open":
                # gather flowables until list_item_close
                item_flow: list = []
                j += 1
                while j < n and tokens[j].type != "list_item_close":
                    tt = tokens[j].type
                    if tt == "paragraph_open":
                        markup, j = collect_inline(j)
                        item_flow.append(Paragraph(markup, st["li"]))
                    elif tt in ("bullet_list_open", "ordered_list_open"):
                        sub, j = parse_list(j, tt == "ordered_list_open")
                        item_flow.append(sub)
                    elif tt == "fence":
                        item_flow.append(_code_block(tokens[j].content, st))
                        j += 1
                    else:
                        j += 1
                items.append(ListItem(item_flow, leftIndent=10))
                j += 1  # skip list_item_close
            else:
                j += 1
        bullet = "1" if ordered else "bulletchar"
        lf = ListFlowable(
            items,
            bulletType="1" if ordered else "bullet",
            start="1" if ordered else None,
            bulletColor=ACCENT,
            bulletFontSize=9,
            leftIndent=16,
            spaceBefore=2,
            spaceAfter=8,
        )
        return lf, j + 1  # skip list_close

    def parse_table(idx: int) -> tuple[Table, int]:
        rows: list[list[str]] = []
        header_rows = 0
        j = idx + 1
        in_head = False
        while j < n and tokens[j].type != "table_close":
            tt = tokens[j].type
            if tt == "thead_open":
                in_head = True
            elif tt == "thead_close":
                in_head = False
            elif tt == "tr_open":
                cells: list[str] = []
                j += 1
                while j < n and tokens[j].type != "tr_close":
                    if tokens[j].type in ("th_open", "td_open"):
                        markup, j = collect_inline(j)
                        cells.append(markup)
                    else:
                        j += 1
                rows.append(cells)
                if in_head:
                    header_rows += 1
                continue
            j += 1
        # build table
        ncols = max(len(r) for r in rows) if rows else 1
        # column widths proportional to max char length, clamped
        widths_chars = [1] * ncols
        for r in rows:
            for ci, cell in enumerate(r):
                plain = re.sub(r"<[^>]+>", "", cell)
                widths_chars[ci] = max(widths_chars[ci], min(len(plain), 60))
        total = sum(widths_chars) or 1
        col_widths = [max(0.6 * inch, CONTENT_WIDTH * w / total) for w in widths_chars]
        # rescale to fit content width
        scale = CONTENT_WIDTH / sum(col_widths)
        col_widths = [w * scale for w in col_widths]

        data = []
        for ri, r in enumerate(rows):
            style = st["cellh"] if ri < header_rows else st["cell"]
            row_cells = [Paragraph(c or "", style) for c in (r + [""] * (ncols - len(r)))]
            data.append(row_cells)

        tbl = Table(data, colWidths=col_widths, repeatRows=header_rows)
        ts = [
            ("GRID", (0, 0), (-1, -1), 0.5, RULE),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]
        if header_rows:
            ts.append(("BACKGROUND", (0, 0), (-1, header_rows - 1), HEADER_BG))
        tbl.setStyle(TableStyle(ts))
        return tbl, j + 1

    while i < n:
        tok = tokens[i]
        tt = tok.type
        if tt == "heading_open":
            level = int(tok.tag[1])
            markup, i = collect_inline(i)
            story.append(Paragraph(markup, st.get(f"h{min(level,4)}", st["h4"])))
        elif tt == "paragraph_open":
            markup, i = collect_inline(i)
            if markup.strip():
                story.append(Paragraph(markup, st["body"]))
        elif tt in ("bullet_list_open", "ordered_list_open"):
            lf, i = parse_list(i, tt == "ordered_list_open")
            story.append(lf)
        elif tt == "table_open":
            tbl, i = parse_table(i)
            story.append(tbl)
            story.append(Spacer(1, 6))
        elif tt == "fence" or tt == "code_block":
            story.append(_code_block(tok.content, st))
            i += 1
        elif tt == "blockquote_open":
            # render contained paragraphs as quote style
            i += 1
            while i < n and tokens[i].type != "blockquote_close":
                if tokens[i].type == "paragraph_open":
                    markup, i = collect_inline(i)
                    story.append(Paragraph(markup, st["quote"]))
                else:
                    i += 1
            i += 1
        elif tt == "hr":
            story.append(HRFlowable(width="100%", thickness=0.6, color=RULE,
                                    spaceBefore=6, spaceAfter=8))
            i += 1
        else:
            i += 1

    doc = SimpleDocTemplate(
        str(out_path), pagesize=letter,
        leftMargin=inch, rightMargin=inch, topMargin=0.9 * inch, bottomMargin=0.9 * inch,
        title=title or "Document", author="Booking-Agent Group 12",
    )
    doc.build(story)
    return Path(out_path)


def _code_block(text: str, st: dict) -> Preformatted:
    text = text.rstrip("\n")
    # wrap very long lines crudely so they don't overflow
    return Preformatted(text, st["code"], maxLineLength=92)


if __name__ == "__main__":
    import sys
    src, dst = sys.argv[1], sys.argv[2]
    ttl = sys.argv[3] if len(sys.argv) > 3 else None
    p = render_markdown_to_pdf(Path(src).read_text(encoding="utf-8"), dst, ttl)
    print("Wrote", p)
