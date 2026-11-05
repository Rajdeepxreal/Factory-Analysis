"""Shared look and feel for every page: colours, headers, cards and footer."""

import hashlib

import streamlit as st

import colmap

_RULES = """
#MainMenu, footer { visibility: hidden; }
header[data-testid="stHeader"] { background: transparent; }
.block-container { padding-top: 1.5rem; padding-bottom: 3rem; max-width: 1240px; }

h1, h2, h3 { color: #0F172A; letter-spacing: -0.01em; }
h2 {
    font-size: 1.3rem; margin-top: 2rem; padding-bottom: .4rem;
    border-bottom: 1px solid #E2E8F0;
}
h3 { font-size: 1.05rem; }

[data-testid="stSidebar"] { background: #FFFFFF; border-right: 1px solid #E2E8F0; }
[data-testid="stSidebar"] h2 { font-size: 1rem; border-bottom: none; margin-top: 1rem; }

[data-testid="stMetric"] {
    background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 14px;
    padding: 16px 18px; box-shadow: 0 1px 3px rgba(15, 23, 42, .05);
}
[data-testid="stMetricLabel"] p {
    color: #64748B; font-size: .78rem; font-weight: 600;
    text-transform: uppercase; letter-spacing: .05em;
}
[data-testid="stMetricValue"] { color: #0F172A; font-weight: 700; }

[data-testid="stDataFrame"] { border: 1px solid #E2E8F0; border-radius: 12px; overflow: hidden; }
[data-testid="stAlert"] { border-radius: 12px; }
.stButton > button, .stDownloadButton > button {
    border-radius: 10px; font-weight: 600; border: 1px solid #0F766E;
}
.stDownloadButton > button { background: #FFFFFF; color: #0F766E; }

.hero {
    background: linear-gradient(135deg, #0F172A 0%, #134E4A 55%, #0F766E 100%);
    color: #FFFFFF; padding: 30px 34px; border-radius: 18px; margin-bottom: 1.5rem;
    box-shadow: 0 8px 24px rgba(15, 23, 42, .15);
}
.hero h1 { color: #FFFFFF; margin: 0; font-size: 2.05rem; }
.hero p { color: #CBD5E1; margin: .5rem 0 0 0; font-size: 1.02rem; max-width: 780px; }
.hero .tag {
    display: inline-block; background: rgba(255, 255, 255, .14); color: #CCFBF1;
    padding: 4px 11px; border-radius: 999px; font-size: .72rem; font-weight: 600;
    letter-spacing: .06em; text-transform: uppercase; margin-bottom: 12px;
}

.card {
    background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 16px;
    padding: 22px 24px; box-shadow: 0 1px 3px rgba(15, 23, 42, .05); margin-bottom: .75rem;
}
.card .icon { font-size: 1.6rem; }
.card h3 { margin: .35rem 0 .4rem 0; }
.card p { color: #475569; margin: 0; line-height: 1.55; }
.card ul { color: #475569; margin: .7rem 0 0 1.1rem; padding: 0; }
.card li { margin-bottom: .25rem; }

.step { display: flex; gap: 14px; align-items: flex-start; margin: .4rem 0 .9rem 0; }
.step .n {
    flex: 0 0 30px; height: 30px; border-radius: 999px; background: #CCFBF1; color: #0F766E;
    font-weight: 700; display: flex; align-items: center; justify-content: center;
}
.step p { margin: 0; color: #334155; line-height: 1.5; }

.footer {
    margin-top: 3rem; padding-top: 1rem; border-top: 1px solid #E2E8F0;
    color: #64748B; font-size: .82rem; text-align: center;
}
"""


def inject_css() -> None:
    """Apply the shared stylesheet. Call once per page, right after st.set_page_config."""
    st.markdown(f"<style>{_RULES}</style>", unsafe_allow_html=True)


def page_header(icon: str, title: str, subtitle: str, tag: str = "") -> None:
    """Branded banner at the top of a page."""
    tag_html = f'<span class="tag">{tag}</span>' if tag else ""
    st.markdown(
        f'<div class="hero">{tag_html}<h1>{icon} {title}</h1><p>{subtitle}</p></div>',
        unsafe_allow_html=True,
    )


def card(title: str, body: str, bullets: list[str] | None = None) -> str:
    """HTML for a feature card. Pass the result to st.markdown(..., unsafe_allow_html=True)."""
    items = ""
    if bullets:
        items = "<ul>" + "".join(f"<li>{b}</li>" for b in bullets) + "</ul>"
    return f'<div class="card"><h3>{title}</h3><p>{body}</p>{items}</div>'


def step(number: int, text: str) -> str:
    """HTML for one numbered step in a 'How it works' row."""
    return f'<div class="step"><div class="n">{number}</div><p>{text}</p></div>'


def footer() -> None:
    st.markdown(
        '<div class="footer">Factory Analytics · Python, pandas and Streamlit</div>',
        unsafe_allow_html=True,
    )


def column_mapping(source, required: list[str], optional: list[str], key: str) -> dict | None:
    """Sidebar panel that matches the file's columns to the ones the analysis needs.

    Returns {analysis column: file column or None}. Returns None if the file could not be read,
    so the page can show the usual read error.
    """
    columns = colmap.read_columns(source)
    if not columns:
        return None
    wanted = required + optional
    suggested = colmap.suggest(columns, wanted)
    sig = hashlib.md5(",".join(columns).encode()).hexdigest()[:8]
    mapping = {}
    with st.sidebar.expander("Check column mapping"):
        st.caption("Columns were matched automatically. Change any that are wrong.")
        for canon in wanted:
            label = canon if canon in required else f"{canon} (optional)"
            options = [colmap.NOT_IN_FILE] + columns
            default = suggested[canon]
            index = options.index(default) if default in columns else 0
            choice = st.selectbox(label, options, index=index, key=f"map_{key}_{canon}_{sig}")
            mapping[canon] = None if choice == colmap.NOT_IN_FILE else choice
    chosen = [v for v in mapping.values() if v]
    if len(chosen) != len(set(chosen)):
        st.sidebar.warning("The same file column is chosen twice. Pick a different one.")
    missing = [c for c in required if mapping[c] is None]
    if missing:
        st.sidebar.warning("Not matched yet: " + ", ".join(missing))
    return mapping
