"""Turn drafts, emails and tool results into safe display strings. Pure functions, no Streamlit.

Same two rules as Project 1:
- Text shown with st.markdown goes through `safe_markdown`: '$' is escaped (Streamlit treats text between two '$' as
  LaTeX) and HTML is escaped, so an email containing <script> is shown as plain text.
- Text placed inside our own HTML (badges, chips, tables) goes through `esc`.
"""

import difflib
import html
import re

CITATION = re.compile(r"\[(P\d+)\]")


def escape_dollars(text: str) -> str:
    return text.replace("\\$", "$").replace("$", "\\$")


def safe_markdown(text: str) -> str:
    return escape_dollars(html.escape(text or "", quote=False))


def esc(text) -> str:
    return html.escape(str(text), quote=True)


def draft_html(text: str, titles: dict[str, str]) -> str:
    """The draft as escaped HTML with each [P1] marker shown as a small citation badge (title on hover)."""
    out = []
    pos = 0
    for m in CITATION.finditer(text or ""):
        out.append(esc(text[pos : m.start()]))
        pid = m.group(1)
        out.append(f'<span class="gra-cite" title="{esc(titles.get(pid, pid))}">{esc(pid)}</span>')
        pos = m.end()
    out.append(esc((text or "")[pos:]))
    return '<div class="gra-draft">' + "".join(out).replace("\n", "<br>") + "</div>"


def badge_html(text: str, tone: str) -> str:
    tone = tone if tone in {"ok", "warn", "error", "muted", "info"} else "muted"
    return f'<span class="gra-badge gra-badge-{tone}">{esc(text)}</span>'


def table_html(columns: list[str], rows: list[list[str]], raw_columns: set[int] = frozenset()) -> str:
    """Simple HTML table. Cells are escaped unless their column index is in `raw_columns` (cells we built ourselves)."""
    head = "".join(f"<th>{esc(c)}</th>" for c in columns)
    body = "".join(
        "<tr>" + "".join(f"<td>{cell if i in raw_columns else esc(cell)}</td>" for i, cell in enumerate(row)) + "</tr>"
        for row in rows
    )
    table = f'<table class="gra-table"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'
    return f'<div class="gra-table-wrap">{table}</div>'


def model_name(model_id: str | None) -> str:
    """'claude-haiku-5-5' -> 'Claude Haiku 5.5'."""
    m = re.match(r"claude-([a-z]+)-(\d+)-(\d+)", model_id or "")
    return f"Claude {m.group(1).title()} {m.group(2)}.{m.group(3)}" if m else (model_id or "unknown")


def diff_html(before: str, after: str) -> str:
    """Word-level diff of the agent's draft vs the text staff sent: removed words struck through, added underlined."""
    a, b = (before or "").split(" "), (after or "").split(" ")
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op == "equal":
            out.append(esc(" ".join(a[i1:i2])))
        if op in ("delete", "replace"):
            out.append(f"<del>{esc(' '.join(a[i1:i2]))}</del>")
        if op in ("insert", "replace"):
            out.append(f"<ins>{esc(' '.join(b[j1:j2]))}</ins>")
    return '<div class="gra-diff">' + " ".join(out).replace("\n", "<br>") + "</div>"


def changed(before: str, after: str) -> bool:
    return " ".join((before or "").split()) != " ".join((after or "").split())
