"""Tema visual de INKubiertos.

Concentra los tokens de diseño extraídos del mockup y el CSS que adapta
Streamlit a la identidad visual del proyecto. No contiene lógica de negocio.
"""
import streamlit as st

COLORS = {
    "sidebar": "#0E0E0F",
    "sidebar_hover": "#1A1A1D",
    "sidebar_border": "#26262A",
    "surface": "#FFFFFF",
    "canvas": "#F9F9FB",
    "border": "#D1D1D6",
    "border_soft": "#E7E7EA",
    "wine": "#800020",
    "wine_dark": "#5C0017",
    "wine_soft": "#F7E9ED",
    "amber": "#E58E19",
    "amber_soft": "#FDF3E3",
    "red": "#C6282D",
    "red_soft": "#FBEAEA",
    "green": "#1E7F47",
    "green_soft": "#E8F7ED",
    "text": "#111113",
    "muted": "#6B6B70",
    "muted_soft": "#9A9AA1",
}

CSS = """
<style>
    :root {
        --ink-sidebar: #0E0E0F;
        --ink-sidebar-hover: #1A1A1D;
        --ink-sidebar-border: #26262A;
        --ink-surface: #FFFFFF;
        --ink-canvas: #F9F9FB;
        --ink-border: #D1D1D6;
        --ink-border-soft: #E7E7EA;
        --ink-wine: #800020;
        --ink-wine-dark: #5C0017;
        --ink-wine-soft: #F7E9ED;
        --ink-amber: #E58E19;
        --ink-amber-soft: #FDF3E3;
        --ink-red: #C6282D;
        --ink-red-soft: #FBEAEA;
        --ink-green: #1E7F47;
        --ink-green-soft: #E8F7ED;
        --ink-text: #111113;
        --ink-muted: #6B6B70;
        --ink-muted-soft: #9A9AA1;
    }

    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    .stApp {
        background: var(--ink-canvas);
    }

    #MainMenu, footer {
        visibility: hidden;
    }

    [data-testid="stHeader"] {
        background: transparent;
        height: 2.25rem;
    }

    [data-testid="stToolbar"],
    [data-testid="stDecoration"] {
        display: none;
    }

    .block-container {
        max-width: 1280px;
        padding: 1.25rem 2.5rem 3rem 2.5rem;
    }

    /* ---------------------------------------------------------------
       Sidebar
       --------------------------------------------------------------- */
    [data-testid="stSidebar"] {
        background: var(--ink-sidebar);
        border-right: 1px solid var(--ink-sidebar-border);
        min-width: 220px !important;
        max-width: 220px !important;
    }

    [data-testid="stSidebar"] > div {
        width: 220px;
    }

    [data-testid="stSidebar"] [data-testid="stSidebarContent"] {
        padding: 1rem 0.75rem 1.25rem 0.75rem;
        min-height: calc(100vh - 2.25rem);
        display: flex;
        flex-direction: column;
    }

    [data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {
        padding: 0;
    }

    .ink-sidebar-brand {
        padding: 0.25rem 0.5rem 0.9rem 0.5rem;
    }

    .ink-sidebar-wordmark {
        color: #FFFFFF;
        font-size: 1.35rem;
        font-weight: 800;
        letter-spacing: -0.035em;
        line-height: 1.1;
    }

    .ink-sidebar-subtitle {
        color: #9A9AA1;
        font-size: 0.72rem;
        margin-top: 0.2rem;
        letter-spacing: 0.01em;
    }

    .ink-sidebar-user {
        background: #151517;
        border: 1px solid #242427;
        border-radius: 10px;
        padding: 0.7rem 0.75rem;
        margin: 0 0.15rem 1rem 0.15rem;
    }

    .ink-sidebar-user-name {
        color: #FFFFFF;
        font-size: 0.84rem;
        font-weight: 600;
        line-height: 1.2;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    .ink-sidebar-user-role {
        color: #A6A6AD;
        font-size: 0.72rem;
        margin-top: 0.15rem;
    }

    .ink-sidebar-label {
        color: #6F6F77;
        font-size: 0.64rem;
        font-weight: 700;
        letter-spacing: 0.09em;
        text-transform: uppercase;
        padding: 0 0.55rem;
        margin: 0.25rem 0 0.4rem 0;
    }

    .ink-sidebar-rule {
        border-top: 1px solid #242427;
        margin: 0.8rem 0.35rem 0.8rem 0.35rem;
    }

    .ink-sidebar-spacer {
        flex: 1 1 auto;
        min-height: 1.25rem;
    }

    [data-testid="stSidebar"] .stButton > button {
        background: transparent;
        color: #C7C7CE;
        border: 1px solid transparent;
        border-radius: 8px;
        text-align: left;
        justify-content: flex-start;
        padding: 0.55rem 0.65rem;
        font-weight: 500;
        font-size: 0.86rem;
        min-height: 2.35rem;
        margin-bottom: 0.1rem;
        transition: background 120ms ease, color 120ms ease;
    }

    [data-testid="stSidebar"] .stButton > button:hover {
        background: var(--ink-sidebar-hover);
        color: #FFFFFF;
        border-color: transparent;
    }

    [data-testid="stSidebar"] .stButton > button[kind="primary"],
    [data-testid="stSidebar"] .stButton > button[data-testid="stBaseButton-primary"] {
        background: var(--ink-wine);
        color: #FFFFFF;
        border-color: var(--ink-wine);
        font-weight: 600;
    }

    [data-testid="stSidebar"] .stButton > button[kind="primary"]:hover,
    [data-testid="stSidebar"] .stButton > button[data-testid="stBaseButton-primary"]:hover {
        background: var(--ink-wine-dark);
        border-color: var(--ink-wine-dark);
    }

    [data-testid="stSidebar"] .stButton > button p {
        font-size: 0.86rem;
    }

    /* ---------------------------------------------------------------
       Tipografía y encabezados
       --------------------------------------------------------------- */
    h1, h2, h3, h4 {
        color: var(--ink-text);
        letter-spacing: -0.02em;
    }

    h1 {
        font-size: 1.9rem;
        font-weight: 800;
        margin-bottom: 0.15rem;
    }

    h2 {
        font-size: 1.25rem;
        font-weight: 700;
        margin-top: 1.75rem;
        margin-bottom: 0.8rem;
    }

    h3 {
        font-size: 1.02rem;
        font-weight: 650;
    }

    p {
        color: var(--ink-text);
    }

    .ink-page-head {
        margin: 0.15rem 0 1.4rem 0;
    }

    .ink-page-title {
        color: var(--ink-text);
        font-size: 1.9rem;
        font-weight: 800;
        letter-spacing: -0.03em;
        line-height: 1.15;
        margin: 0;
    }

    .ink-page-subtitle {
        color: var(--ink-muted);
        font-size: 0.92rem;
        margin: 0.3rem 0 0 0;
        line-height: 1.45;
    }

    /* Tarjetas métricas heredadas */
    .metric-card {
        background: var(--ink-surface);
        border: 1px solid var(--ink-border-soft);
        border-radius: 12px;
        padding: 1.1rem 1.2rem;
        box-shadow: 0 1px 2px rgba(17, 17, 19, 0.03);
    }

    .metric-label {
        color: var(--ink-muted);
        font-size: 0.7rem;
        font-weight: 700;
        margin-bottom: 0.35rem;
        text-transform: uppercase;
        letter-spacing: 0.055em;
    }

    .metric-value {
        color: var(--ink-text);
        font-size: 1.9rem;
        font-weight: 800;
        line-height: 1.1;
        letter-spacing: -0.03em;
    }

    /* Barra superior de contexto */
    .ink-topbar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1rem;
        padding: 0.15rem 0 1rem 0;
        border-bottom: 1px solid var(--ink-border-soft);
        margin-bottom: 1.5rem;
    }

    .ink-topbar-brand {
        color: var(--ink-text);
        font-size: 1.02rem;
        font-weight: 800;
        letter-spacing: -0.035em;
    }

    .ink-topbar-right {
        display: flex;
        align-items: center;
        gap: 0.65rem;
        color: var(--ink-muted);
        font-size: 0.78rem;
    }

    .ink-topbar-user {
        font-weight: 600;
        color: var(--ink-text);
    }

    .ink-topbar-role {
        background: var(--ink-canvas);
        border: 1px solid var(--ink-border);
        border-radius: 999px;
        padding: 0.18rem 0.55rem;
        font-size: 0.7rem;
        color: var(--ink-muted);
        white-space: nowrap;
    }

    /* ---------------------------------------------------------------
       Botones, formularios e inputs
       --------------------------------------------------------------- */
    .stButton > button,
    [data-testid="stFormSubmitButton"] > button {
        border-radius: 8px;
        font-weight: 600;
        font-size: 0.86rem;
        min-height: 2.5rem;
        transition: background 120ms ease, border-color 120ms ease, color 120ms ease;
    }

    .stButton > button[kind="primary"],
    [data-testid="stFormSubmitButton"] > button[kind="primary"],
    .stButton > button[data-testid="stBaseButton-primary"],
    [data-testid="stFormSubmitButton"] > button[data-testid="stBaseButton-primary"] {
        background: var(--ink-wine);
        color: #FFFFFF;
        border: 1px solid var(--ink-wine);
    }

    .stButton > button[kind="primary"]:hover,
    [data-testid="stFormSubmitButton"] > button[kind="primary"]:hover,
    .stButton > button[data-testid="stBaseButton-primary"]:hover,
    [data-testid="stFormSubmitButton"] > button[data-testid="stBaseButton-primary"]:hover {
        background: var(--ink-wine-dark);
        border-color: var(--ink-wine-dark);
        color: #FFFFFF;
    }

    .stButton > button[kind="secondary"],
    [data-testid="stFormSubmitButton"] > button[kind="secondary"] {
        background: var(--ink-surface);
        color: var(--ink-text);
        border: 1px solid var(--ink-border);
    }

    .stButton > button[kind="secondary"]:hover,
    [data-testid="stFormSubmitButton"] > button[kind="secondary"]:hover {
        background: var(--ink-canvas);
        border-color: #B9B9C1;
    }

    .stButton > button[kind="tertiary"],
    [data-testid="stFormSubmitButton"] > button[kind="tertiary"] {
        background: transparent;
        color: var(--ink-muted);
        border: 1px solid transparent;
        font-weight: 500;
    }

    .stButton > button[kind="tertiary"]:hover,
    [data-testid="stFormSubmitButton"] > button[kind="tertiary"]:hover {
        color: var(--ink-wine);
        background: var(--ink-wine-soft);
    }

    [data-testid="stForm"] {
        background: var(--ink-surface);
        border: 1px solid var(--ink-border-soft);
        border-radius: 12px;
        padding: 1.25rem 1.35rem;
        box-shadow: 0 1px 2px rgba(17, 17, 19, 0.03);
    }

    [data-baseweb="input"],
    [data-baseweb="textarea"],
    [data-baseweb="select"] > div {
        border-radius: 8px !important;
        border-color: var(--ink-border) !important;
        background: #FFFFFF !important;
    }

    [data-baseweb="input"]:focus-within,
    [data-baseweb="textarea"]:focus-within,
    [data-baseweb="select"] > div:focus-within {
        border-color: var(--ink-wine) !important;
        box-shadow: 0 0 0 1px var(--ink-wine) !important;
    }

    [data-testid="stWidgetLabel"] p,
    .stTextInput label,
    .stSelectbox label,
    .stNumberInput label,
    .stTextArea label {
        color: var(--ink-text);
        font-size: 0.82rem;
        font-weight: 600;
    }

    [data-testid="stCaptionContainer"] {
        color: var(--ink-muted);
    }

    [data-testid="stAlert"] {
        border-radius: 10px;
    }

    hr {
        border-color: var(--ink-border-soft);
    }

    /* ---------------------------------------------------------------
       Login
       --------------------------------------------------------------- */
    .ink-login-wrap {
        padding-top: 1.1rem;
    }

    .ink-login-brand {
        background: var(--ink-sidebar);
        border: 1px solid #242427;
        border-radius: 16px;
        min-height: 560px;
        padding: 3rem 2.6rem 2.4rem 2.6rem;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        box-shadow: 0 10px 30px rgba(14, 14, 15, 0.10);
    }

    .ink-login-wordmark {
        color: #FFFFFF;
        font-size: 2.7rem;
        font-weight: 800;
        letter-spacing: -0.05em;
        line-height: 1;
    }

    .ink-login-tagline {
        color: #C3C3CA;
        font-size: 1.02rem;
        margin-top: 0.65rem;
        max-width: 15rem;
        line-height: 1.45;
    }

    .ink-login-brand-copy {
        color: #8E8E96;
        font-size: 0.86rem;
        line-height: 1.6;
        max-width: 17rem;
        margin-bottom: 0.25rem;
    }

    .ink-login-brand-rule {
        border-top: 1px solid #2A2A2E;
        margin: 1.4rem 0;
    }

    .ink-login-brand-foot {
        color: #6F6F77;
        font-size: 0.72rem;
        letter-spacing: 0.01em;
    }

    .ink-login-panel {
        padding: 1.4rem 0.5rem 0.5rem 1.4rem;
    }

    .ink-login-title {
        color: var(--ink-text);
        font-size: 2rem;
        font-weight: 800;
        letter-spacing: -0.035em;
        margin: 0;
    }

    .ink-login-subtitle {
        color: var(--ink-muted);
        font-size: 0.92rem;
        margin: 0.35rem 0 1.5rem 0;
        line-height: 1.5;
    }

    .ink-login-alt {
        color: var(--ink-muted);
        font-size: 0.8rem;
        text-align: center;
        margin-top: 0.9rem;
    }

    .ink-login-divider {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        color: var(--ink-muted-soft);
        font-size: 0.72rem;
        margin: 1.1rem 0 0.35rem 0;
    }

    .ink-login-divider::before,
    .ink-login-divider::after {
        content: "";
        height: 1px;
        background: var(--ink-border-soft);
        flex: 1;
    }

    .ink-auth-note {
        background: var(--ink-canvas);
        border: 1px solid var(--ink-border-soft);
        border-radius: 10px;
        padding: 1rem 1.1rem;
        color: var(--ink-muted);
        font-size: 0.84rem;
        line-height: 1.55;
    }

    /* ---------------------------------------------------------------
       Estados y placeholders
       --------------------------------------------------------------- */
    .ink-placeholder {
        background: var(--ink-surface);
        border: 1px solid var(--ink-border-soft);
        border-radius: 12px;
        padding: 2.2rem 1.75rem;
        text-align: center;
    }

    .ink-placeholder-badge {
        display: inline-block;
        background: var(--ink-wine-soft);
        color: var(--ink-wine);
        border: 1px solid #E9CCD5;
        border-radius: 999px;
        padding: 0.2rem 0.65rem;
        font-size: 0.68rem;
        font-weight: 700;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        margin-bottom: 0.8rem;
    }

    .ink-placeholder-title {
        color: var(--ink-text);
        font-size: 1.1rem;
        font-weight: 700;
        margin: 0 0 0.35rem 0;
    }

    .ink-placeholder-text {
        color: var(--ink-muted);
        font-size: 0.86rem;
        line-height: 1.55;
        max-width: 34rem;
        margin: 0 auto;
    }

    .ink-empty-state {
        background: var(--ink-surface);
        border: 1px dashed var(--ink-border);
        border-radius: 12px;
        padding: 2rem 1.5rem;
        text-align: center;
        color: var(--ink-muted);
        font-size: 0.86rem;
    }

    /* ---------------------------------------------------------------
       Dashboard e inventario
       --------------------------------------------------------------- */
    .ink-scope {
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        background: var(--ink-wine-soft);
        border: 1px solid #E9CCD5;
        color: var(--ink-wine);
        border-radius: 999px;
        padding: 0.22rem 0.65rem;
        font-size: 0.72rem;
        font-weight: 600;
        margin: 0 0 1rem 0;
    }

    .ink-metrics {
        display: grid;
        grid-template-columns: repeat(5, minmax(0, 1fr));
        gap: 0.85rem;
        margin: 0.2rem 0 1.15rem 0;
    }

    .ink-metric {
        background: var(--ink-surface);
        border: 1px solid var(--ink-border-soft);
        border-top: 3px solid var(--ink-border);
        border-radius: 12px;
        padding: 0.95rem 1rem 1rem 1rem;
        box-shadow: 0 1px 2px rgba(17, 17, 19, 0.03);
        min-width: 0;
    }

    .ink-metric--wine { border-top-color: var(--ink-wine); }
    .ink-metric--green { border-top-color: var(--ink-green); }
    .ink-metric--amber { border-top-color: var(--ink-amber); }
    .ink-metric--red { border-top-color: var(--ink-red); }
    .ink-metric--muted { border-top-color: var(--ink-muted-soft); }

    .ink-metric-label {
        color: var(--ink-muted);
        font-size: 0.67rem;
        font-weight: 700;
        letter-spacing: 0.055em;
        text-transform: uppercase;
        line-height: 1.3;
        margin-bottom: 0.35rem;
    }

    .ink-metric-value {
        color: var(--ink-text);
        font-size: 1.72rem;
        font-weight: 800;
        line-height: 1.1;
        letter-spacing: -0.03em;
        font-variant-numeric: tabular-nums;
    }

    .ink-metric-hint {
        color: var(--ink-muted);
        font-size: 0.71rem;
        line-height: 1.35;
        margin-top: 0.35rem;
    }

    .ink-panel {
        background: var(--ink-surface);
        border: 1px solid var(--ink-border-soft);
        border-radius: 12px;
        padding: 1.15rem 1.25rem;
        box-shadow: 0 1px 2px rgba(17, 17, 19, 0.03);
        height: 100%;
        margin-bottom: 1rem;
    }

    .ink-panel--value {
        border-left: 3px solid var(--ink-wine);
    }

    .ink-panel-label {
        color: var(--ink-muted);
        font-size: 0.68rem;
        font-weight: 700;
        letter-spacing: 0.055em;
        text-transform: uppercase;
        margin-bottom: 0.4rem;
    }

    .ink-panel-value {
        color: var(--ink-text);
        font-size: 1.9rem;
        font-weight: 800;
        letter-spacing: -0.035em;
        line-height: 1.15;
        font-variant-numeric: tabular-nums;
    }

    .ink-panel-value--muted {
        color: var(--ink-muted-soft);
    }

    .ink-panel-stamp {
        color: var(--ink-text);
        font-size: 1.05rem;
        font-weight: 700;
        letter-spacing: -0.01em;
        line-height: 1.35;
        font-variant-numeric: tabular-nums;
    }

    .ink-panel-hint {
        color: var(--ink-muted);
        font-size: 0.76rem;
        line-height: 1.45;
        margin-top: 0.3rem;
    }

    .ink-table-meta {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1rem;
        flex-wrap: wrap;
        color: var(--ink-muted);
        font-size: 0.76rem;
        margin: 0.1rem 0 0.7rem 0;
    }

    .ink-table-wrap {
        background: var(--ink-surface);
        border: 1px solid var(--ink-border-soft);
        border-radius: 12px;
        overflow-x: auto;
        box-shadow: 0 1px 2px rgba(17, 17, 19, 0.03);
    }

    .ink-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.82rem;
    }

    .ink-table th {
        background: #FCFCFD;
        border-bottom: 1px solid var(--ink-border-soft);
        color: var(--ink-muted);
        font-size: 0.66rem;
        font-weight: 700;
        letter-spacing: 0.06em;
        padding: 0.75rem 1rem;
        text-align: left;
        text-transform: uppercase;
        white-space: nowrap;
    }

    .ink-table td {
        border-bottom: 1px solid var(--ink-border-soft);
        color: var(--ink-text);
        padding: 0.72rem 1rem;
        vertical-align: middle;
    }

    .ink-table tr:last-child td {
        border-bottom: none;
    }

    .ink-table tbody tr:hover {
        background: #FAFAFC;
    }

    .ink-table .is-num {
        text-align: right;
        white-space: nowrap;
        font-variant-numeric: tabular-nums;
    }

    .ink-table .is-date {
        white-space: nowrap;
        color: var(--ink-muted);
    }

    .ink-product-name {
        font-weight: 600;
    }

    .ink-muted {
        color: var(--ink-muted);
    }

    .ink-row--bajo { background: #FFFCF5; }
    .ink-row--critico { background: #FDF7F7; }
    .ink-row--sin-stock { background: #FAFAFB; }

    .ink-table tbody tr.ink-row--bajo:hover { background: #FFF9EC; }
    .ink-table tbody tr.ink-row--critico:hover { background: #FCEFEF; }
    .ink-table tbody tr.ink-row--sin-stock:hover { background: #F4F4F7; }

    .ink-status {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        border-radius: 999px;
        padding: 0.2rem 0.55rem;
        font-size: 0.7rem;
        font-weight: 700;
        line-height: 1.2;
        white-space: nowrap;
    }

    .ink-status::before {
        content: "";
        width: 0.38rem;
        height: 0.38rem;
        border-radius: 50%;
        background: currentColor;
        flex: 0 0 auto;
    }

    .ink-status--green { color: var(--ink-green); background: var(--ink-green-soft); }
    .ink-status--amber { color: var(--ink-amber); background: var(--ink-amber-soft); }
    .ink-status--red { color: var(--ink-red); background: var(--ink-red-soft); }
    .ink-status--wine { color: var(--ink-wine); background: var(--ink-wine-soft); }
    .ink-status--muted { color: var(--ink-muted); background: var(--ink-canvas); }

    .ink-metrics--2 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .ink-metrics--3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
    .ink-metrics--4 { grid-template-columns: repeat(4, minmax(0, 1fr)); }

    .ink-stock-preview {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1rem;
        flex-wrap: wrap;
        background: var(--ink-canvas);
        border: 1px solid var(--ink-border-soft);
        border-radius: 10px;
        padding: 0.85rem 1rem;
        margin: 0.4rem 0 0.9rem 0;
    }

    .ink-stock-preview-label {
        color: var(--ink-muted);
        font-size: 0.7rem;
        font-weight: 700;
        letter-spacing: 0.05em;
        text-transform: uppercase;
    }

    .ink-stock-preview-value {
        color: var(--ink-text);
        font-size: 1.25rem;
        font-weight: 800;
        line-height: 1.2;
        font-variant-numeric: tabular-nums;
    }

    .ink-stock-preview-value--danger { color: var(--ink-red); }
    .ink-stock-preview-value--ok { color: var(--ink-green); }

    .ink-delta {
        font-weight: 700;
        font-variant-numeric: tabular-nums;
        white-space: nowrap;
    }

    .ink-delta.is-pos { color: var(--ink-green); }
    .ink-delta.is-neg { color: var(--ink-red); }

    .ink-stock-preview-detail {
        color: var(--ink-muted);
        font-size: 0.78rem;
        margin-top: 0.15rem;
    }

    .ink-data-note {
        background: var(--ink-wine-soft);
        border-left: 3px solid var(--ink-wine);
        border-radius: 8px;
        color: var(--ink-wine-dark);
        font-size: 0.8rem;
        line-height: 1.5;
        padding: 0.7rem 0.9rem;
        margin: 0.2rem 0 1rem 0;
    }

    @media (max-width: 1100px) {
        .ink-metrics {
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }
    }

    @media (max-width: 640px) {
        .ink-metrics {
            grid-template-columns: 1fr;
        }

        .ink-panel-value {
            font-size: 1.55rem;
        }
    }

    @media (max-width: 900px) {
        .block-container {
            padding: 1rem 1rem 2rem 1rem;
        }

        .ink-login-brand {
            min-height: auto;
            padding: 2rem 1.75rem;
        }

        .ink-login-panel {
            padding: 0.5rem 0 0 0;
        }

        .ink-topbar {
            align-items: flex-start;
            flex-direction: column;
            gap: 0.35rem;
        }
    }
</style>
"""


def inject_theme() -> None:
    """Inyecta el CSS global. Debe llamarse después de set_page_config."""
    st.markdown(CSS, unsafe_allow_html=True)
