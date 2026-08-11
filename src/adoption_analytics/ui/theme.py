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

        /* --- Sidebar & Navigation Styling --- */
        section[data-testid="stSidebar"] {{
            width: 230px !important;
            min-width: 230px !important;
            background-color: {SURFACE};
            border-right: 1px solid {BORDER};
        }}
        
        /* Stylize the radio buttons in the sidebar as navigation links */
        section[data-testid="stSidebar"] div[role="radiogroup"] > label {{
            display: flex !important;
            width: 100% !important;
            padding: 10px 16px !important;
            border-radius: 8px !important;
            margin-bottom: 4px !important;
            background-color: transparent !important;
            color: {MUTED} !important;
            font-weight: 500 !important;
            transition: background-color 0.2s ease-in-out, color 0.2s ease-in-out;
            cursor: pointer;
            box-sizing: border-box;
        }}

        section[data-testid="stSidebar"] div[role="radiogroup"] > label:hover {{
            background-color: #f9fafb !important;
            color: {TEXT} !important;
        }}

        section[data-testid="stSidebar"] div[role="radiogroup"] > label[data-checked="true"],
        section[data-testid="stSidebar"] div[role="radiogroup"] > label[aria-checked="true"],
        section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) {{
            background-color: #ffefe8 !important;
            color: {UM6P_ORANGE} !important;
            font-weight: 700 !important;
        }}
        
        /* Hide the native radio circle completely */
        section[data-testid="stSidebar"] div[role="radiogroup"] > label > div:first-of-type,
        section[data-testid="stSidebar"] div[role="radiogroup"] > label > input[type="radio"] + div {{
            display: none !important;
        }}

        /* Filter container styling */
        .filter-container {{
            background: {SURFACE};
            border: 1px solid {BORDER};
            border-radius: 12px;
            padding: 16px 20px;
            margin-bottom: 24px;
            box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        }}
        </style>
        ''',
        unsafe_allow_html=True,
    )
