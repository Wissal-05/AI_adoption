import streamlit as st

UM6P_ORANGE = "#E94B00"
BACKGROUND = "#F5F6F8"
SURFACE = "#FFFFFF"
TEXT = "#111318"
MUTED = "#667085"
BORDER = "#E3E6EA"
POSITIVE = "#2E7D32"
WARNING = "#B76A00"
CRITICAL = "#C62828"
INFO = "#2563EB"

def apply_um6p_theme() -> None:
    st.markdown(
        f'''
        <style>
        /* Base Typography */
        @import url("https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap");

        .stApp, .stApp :not(i):not(.material-icons):not(.material-symbols-rounded):not(.stIcon) {{
            font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        }}

        .stApp {{
            background-color: {BACKGROUND};
            color: {TEXT};
        }}

        /* Réduction des grands espaces verticaux inutiles */
        .block-container {{
            max-width: 1450px;
            padding-top: 1.5rem !important;
            padding-bottom: 3rem !important;
        }}
        div[data-testid="stVerticalBlock"] {{
            gap: 1rem !important;
        }}

        /* Headings */
        h1 {{
            color: {TEXT};
            font-size: 26px !important;
            font-weight: 750 !important;
            line-height: 1.2 !important;
            letter-spacing: -0.02em;
            margin-bottom: 2px !important;
            padding-bottom: 0 !important;
        }}

        h2, h3, h4 {{
            color: {TEXT};
            font-weight: 650 !important;
            letter-spacing: -0.01em;
            margin-bottom: 8px !important;
            padding-bottom: 0 !important;
        }}

        h2 {{
            font-size: 20px !important;
            margin-top: 12px !important;
        }}

        h3 {{
            font-size: 16px !important;
            margin-top: 12px !important;
        }}

        .um6p-eyebrow {{
            color: {UM6P_ORANGE};
            font-weight: 700;
            font-size: 0.7rem;
            letter-spacing: 0.06em;
            text-transform: uppercase;
        }}

        .page-subtitle {{
            font-size: 14px;
            color: {MUTED};
            font-weight: 400;
            margin-bottom: 12px;
        }}

        /* Specific Cards */
        .strategic-card, .data-quality-card {{
            background: {SURFACE};
            border: 1px solid {BORDER};
            border-radius: 12px;
            padding: 16px 20px;
            margin-bottom: 8px;
            box-shadow: 0 1px 6px rgba(16, 24, 40, 0.04);
        }}

        .next-action {{
            background: #FFF3ED;
            border-radius: 10px;
            padding: 12px 16px;
            margin-top: 12px;
        }}

        /* Attention Card */
        .attention-card {{
            background: {SURFACE};
            border: 1px solid {BORDER};
            border-radius: 12px;
            padding: 14px 18px;
            margin-bottom: 0px;
            box-shadow: 0 1px 6px rgba(16, 24, 40, 0.04);
            border-left-width: 4px;
            border-left-style: solid;
            height: 100%;
        }}
        .attention-card.attention-warning {{ border-left-color: #f59e0b; }}
        .attention-card.attention-info {{ border-left-color: #3b82f6; }}
        .attention-card.attention-error {{ border-left-color: #ef4444; }}
        .attention-card.attention-success {{ border-left-color: #10b981; }}

        .attention-card-eyebrow {{
            font-size: 11px;
            font-weight: 650;
            color: {MUTED};
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 4px;
        }}
        .attention-card h4 {{
            margin: 0 0 4px 0 !important;
            font-size: 13px !important;
            font-weight: 700 !important;
            color: {TEXT};
            line-height: 1.4 !important;
        }}
        .attention-card p {{
            margin: 0 !important;
            font-size: 12px !important;
            color: {MUTED};
            line-height: 1.4 !important;
        }}

        /* ── Sidebar & Navigation ───────────────────────────────────── */
        section[data-testid="stSidebar"] {{
            width: 240px !important;
            min-width: 240px !important;
            background-color: {SURFACE};
            border-right: 1px solid {BORDER};
        }}

        /* Nav radio labels */
        section[data-testid="stSidebar"] div[role="radiogroup"] > label {{
            display: flex !important;
            align-items: center !important;
            width: 100% !important;
            padding: 9px 14px !important;
            border-radius: 8px !important;
            margin-bottom: 3px !important;
            background-color: transparent !important;
            color: {MUTED} !important;
            font-weight: 500 !important;
            font-size: 13.5px !important;
            transition: background-color 0.15s ease, color 0.15s ease;
            cursor: pointer;
            box-sizing: border-box;
        }}
        section[data-testid="stSidebar"] div[role="radiogroup"] > label:hover {{
            background-color: {BACKGROUND} !important;
            color: {TEXT} !important;
        }}
        /* Active nav item — three selectors for reliability across Streamlit versions */
        section[data-testid="stSidebar"] div[role="radiogroup"] > label[data-checked="true"],
        section[data-testid="stSidebar"] div[role="radiogroup"] > label[aria-checked="true"],
        section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) {{
            background-color: #ffede3 !important;
            color: {UM6P_ORANGE} !important;
            font-weight: 650 !important;
        }}

        /* Hide default radio dot — the highlight IS the indicator */
        section[data-testid="stSidebar"] div[role="radiogroup"] > label > div:first-child {{
            display: none !important;
        }}

        /* Refresh button in sidebar */
        section[data-testid="stSidebar"] .stButton > button {{
            background-color: {SURFACE} !important;
            color: {TEXT} !important;
            border: 1px solid {BORDER} !important;
            border-radius: 8px !important;
            font-size: 13px !important;
            font-weight: 500 !important;
            padding: 8px 14px !important;
            width: 100% !important;
            transition: background-color 0.15s ease, border-color 0.15s ease;
        }}
        section[data-testid="stSidebar"] .stButton > button:hover {{
            background-color: {BACKGROUND} !important;
            border-color: #c5c9d0 !important;
        }}

        /* ── KPI Cards ───────────────────────────────────────────────── */
        .kpi-card {{
            background: {SURFACE};
            border: 1px solid {BORDER};
            border-radius: 14px;
            padding: 18px 20px;
            display: flex;
            flex-direction: column;
            gap: 3px;
            box-shadow: 0 1px 6px rgba(16, 24, 40, 0.04);
            height: 100%;
        }}
        /* Title: readable sentence-case, not shouted uppercase */
        .kpi-card-title {{
            color: {MUTED};
            font-size: 12px;
            font-weight: 600;
            text-transform: none;
            letter-spacing: 0;
            margin: 0;
            line-height: 1.3;
        }}
        .kpi-card-value {{
            color: {TEXT};
            font-size: 28px;
            font-weight: 750;
            line-height: 1.15;
            margin: 4px 0 0 0;
        }}
        .kpi-card-subtitle {{
            color: {MUTED};
            font-size: 12px;
            margin: 0;
            line-height: 1.3;
        }}

        /* Filter container styling */
        .filter-container {{
            background: {SURFACE};
            border: 1px solid {BORDER};
            border-radius: 12px;
            padding: 10px 18px;
            margin-bottom: 12px;
            box-shadow: 0 1px 6px rgba(16, 24, 40, 0.04);
            display: flex;
            gap: 16px;
        }}

        .filter-label {{
            font-size: 11px;
            font-weight: 600;
            color: {MUTED};
            text-transform: uppercase;
            letter-spacing: 0.04em;
            margin-bottom: 4px;
        }}

        /* ── Streamlit native metric override ───────────────────────── */
        div[data-testid="stMetric"] {{
            background: {SURFACE};
            border: 1px solid {BORDER};
            border-radius: 14px;
            padding: 18px 20px;
            box-shadow: 0 1px 6px rgba(16, 24, 40, 0.04);
        }}
        div[data-testid="stMetricLabel"] {{
            color: {MUTED};
            font-weight: 600;
            font-size: 12px;
            text-transform: none;
            letter-spacing: 0;
        }}
        div[data-testid="stMetricValue"] {{
            color: {TEXT};
            font-weight: 750;
            font-size: 28px;
        }}

        /* ── Badges ──────────────────────────────────────────────────── */
        .badge {{
            display: inline-block;
            border-radius: 999px;
            padding: 3px 9px;
            font-size: 11.5px;
            font-weight: 600;
            line-height: 1.5;
            white-space: nowrap;
        }}
        .badge-success {{ background-color: #ECFDF3; color: #027A48; }}
        .badge-warning {{ background-color: #FFFAEB; color: #B54708; }}
        .badge-danger  {{ background-color: #FEF3F2; color: #B42318; }}
        .badge-info    {{ background-color: #EFF8FF; color: #175CD3; }}
        .badge-neutral {{ background-color: #F2F4F7; color: #344054; }}

        /* ── Tables ──────────────────────────────────────────────────── */
        /* Scrollable wrapper for HTML tables rendered via st.markdown */
        div[data-testid="stMarkdownContainer"] .scrollable-table-wrapper {{
            overflow-y: auto;
            max-height: 400px;
            border: 1px solid {BORDER};
            border-radius: 10px;
        }}

        div[data-testid="stDataFrame"] table,
        div[data-testid="stMarkdownContainer"] table {{
            border-collapse: collapse;
            width: 100%;
        }}
        div[data-testid="stDataFrame"] th,
        div[data-testid="stMarkdownContainer"] th {{
            color: {MUTED};
            font-weight: 600 !important;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            border-bottom: 1px solid {BORDER} !important;
            padding: 10px 14px !important;
            position: sticky;
            top: 0;
            background: {SURFACE};
            z-index: 1;
        }}
        div[data-testid="stDataFrame"] td,
        div[data-testid="stMarkdownContainer"] td {{
            font-size: 13px;
            border-bottom: 1px solid {BORDER} !important;
            padding: 10px 14px !important;
        }}
        div[data-testid="stMarkdownContainer"] tr:last-child td {{
            border-bottom: none !important;
        }}

        /* ── Unavailable data placeholder ───────────────────────────── */
        .data-unavailable {{
            display: flex;
            align-items: center;
            gap: 8px;
            background: {BACKGROUND};
            border: 1px dashed {BORDER};
            border-radius: 10px;
            padding: 14px 18px;
            font-size: 13px;
            color: {MUTED};
        }}
        .data-unavailable .unavail-icon {{
            font-size: 18px;
            flex-shrink: 0;
        }}

        /* ── AI chat area ────────────────────────────────────────────── */
        div[data-testid="stChatMessageContent"] p {{
            font-size: 14px;
            line-height: 1.6;
        }}

        </style>
        ''',
        unsafe_allow_html=True,
    )
