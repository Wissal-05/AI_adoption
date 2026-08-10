import streamlit as st


UM6P_ORANGE = "#E54700"
BACKGROUND = "#F6F7F9"
SURFACE = "#FFFFFF"
TEXT = "#161616"
MUTED = "#666B74"
BORDER = "#E6E8EC"
POSITIVE = "#2E7D32"
WARNING = "#B66A00"
CRITICAL = "#B3261E"
INFO = "#2B65D9"


def apply_um6p_theme() -> None:
    st.markdown(
        f'''
        <style>
        .stApp {{
            background-color: {BACKGROUND};
            color: {TEXT};
        }}

        .block-container {{
            max-width: 1450px;
            padding-top: 2rem;
            padding-bottom: 4rem;
        }}

        h1, h2, h3 {{
            color: {TEXT};
            letter-spacing: -0.02em;
        }}

        div[data-testid="stMetric"] {{
            background: {SURFACE};
            border: 1px solid {BORDER};
            border-radius: 16px;
            padding: 18px;
        }}

        div[data-testid="stMetricLabel"] {{
            color: {MUTED};
        }}

        div[data-testid="stMetricValue"] {{
            color: {TEXT};
        }}

        div[data-testid="stSelectbox"] > div {{
            background: {SURFACE};
        }}

        .um6p-eyebrow {{
            color: {UM6P_ORANGE};
            font-weight: 700;
            font-size: 0.75rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
        }}

        .strategic-card {{
            background: {SURFACE};
            border: 1px solid {BORDER};
            border-radius: 16px;
            padding: 18px;
            margin-bottom: 12px;
        }}

        .next-action {{
            background: #FFF3ED;
            border-radius: 12px;
            padding: 14px;
            margin-top: 12px;
        }}

        .data-quality-card {{
            background: {SURFACE};
            border: 1px solid {BORDER};
            border-radius: 16px;
            padding: 18px;
        }}
        </style>
        ''',
        unsafe_allow_html=True,
    )
