import streamlit as st


def inject_styles():
    """Dark theme polish + sticky map container on the right."""
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Russo+One&family=Sora:wght@400;600&display=swap');
        @import url("https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,400,0,0");

        .stApp {
            background: radial-gradient(120% 120% at 10% 20%, #0f172a 0%, #0b1020 45%, #050913 100%);
            color: #e2e8f0;
            font-family: "Russo One", "Sora", system-ui, -apple-system, sans-serif;
        }

        body, p, label, input, textarea, button, select, option, li, h1, h2, h3, h4, h5 {
            font-family: "Russo One", "Sora", system-ui, -apple-system, sans-serif !important;
            font-weight: 200;
        }

        h1, h2, h3, h4 {
            font-weight: 400;
            color: #f8fafc;
            letter-spacing: 0.01em;
        }

        /* Keep icon fonts intact */
        .material-icons,
        .material-symbols-outlined,
        .material-symbols-rounded,
        .material-symbols-sharp,
        [data-baseweb="icon"] {
            font-family: "Material Symbols Outlined" !important;
            font-weight: 400 !important;
            font-style: normal;
            line-height: 1;
            letter-spacing: normal;
            text-transform: none;
            display: inline-block;
            white-space: nowrap;
            word-wrap: normal;
            direction: ltr;
            -webkit-font-feature-settings: "liga";
            -webkit-font-smoothing: antialiased;
        }

        .block-container {
            padding: 1.25rem 1.25rem 2rem;
            max-width: 100%;
        }

        /* Buttons (muted pastel) */
        .stButton>button {
            background: linear-gradient(90deg, #dce3eb, #c7d2e2);
            color: #0f172a;
            border: 1px solid #cbd5e1;
            border-radius: 10px;
            padding: 0.55rem 1.05rem;
            font-weight: 600;
            transition: transform 120ms ease, box-shadow 120ms ease, background 120ms ease;
            width: auto;
            min-width: 150px;
        }
        .stButton>button:hover {
            transform: translateY(-1px);
            box-shadow: 0 10px 22px rgba(100,116,139,0.35);
            background: linear-gradient(90deg, #e5edf5, #d4deed);
        }

        /* Inputs */
        .stNumberInput input, .stTextInput input, textarea {
            background: #1f2937;
            color: #e2e8f0;
            border-radius: 10px;
            border: 1px solid #2b3545;
            width: 100%;
        }
        .stSelectbox div[data-baseweb="select"] {
            background: #1f2937;
            border: 1px solid #2b3545;
            border-radius: 10px;
            color: #e2e8f0;
        }
        .stSelectbox div[data-baseweb="popover"], .stSelectbox [data-baseweb="menu"] {
            background: #1f2937;
            border: 1px solid #2b3545;
            color: #e2e8f0;
        }
        .stTextArea textarea {
            background: #1f2937 !important;
            border: 1px solid #2b3545 !important;
            color: #e2e8f0;
        }

        /* Expander */
        details {
            background: #0d1524;
            border-radius: 10px;
            border: 1px solid #1f2937;
        }

        /* Right-hand map column sticks during left scroll */
        .sticky-map-col {
            position: sticky;
            top: 10px;
            align-self: flex-start;
        }
        /* Preserve card styling for the map panel */
        #map-sticky-anchor + div {
            height: calc(100vh - 16px);
            padding: 12px;
            border: 1px solid #1f2937;
            border-radius: 14px;
            background: #0d1524;
            overflow: hidden;
            position: relative;
        }
        /* Make pydeck fill wrapper, kill inner scroll */
        #map-sticky-anchor + div div[data-testid="stDeckGlChart"],
        #map-sticky-anchor + div div[data-testid="stDeckGlJsonChart"] {
            height: 100% !important;
            min-height: 100% !important;
            overflow: hidden !important;
        }
        #map-sticky-anchor + div div[data-testid="stDeckGlChart"] > div,
        #map-sticky-anchor + div div[data-testid="stDeckGlJsonChart"] > div {
            height: 100% !important;
        }
        #map-sticky-anchor + div iframe {
            height: 100% !important;
        }

        /* Progress bar */
        div[role="progressbar"] {
            background: #1f2937 !important;
            border-radius: 999px !important;
            overflow: hidden !important;
            border: 1px solid #2b3545 !important;
            height: 8px !important;
        }
        div[role="progressbar"] > div {
            background: linear-gradient(90deg, #0ea5e9, #7c3aed) !important;
            height: 100% !important;
        }

        /* Inline language toggle */
        div[data-testid="stButton"].lang-toggle {
            display: inline-flex;
            width: auto;
        }
        div[data-testid="stButton"].lang-toggle > button {
            width: 42px;
            height: 42px;
            padding: 0;
            border-radius: 50%;
            border: 1px solid #334155;
            background: rgba(15,23,42,0.6);
            color: #e2e8f0;
            box-shadow: 0 6px 18px rgba(0,0,0,0.35);
        }
        div[data-testid="stButton"].lang-toggle > button:hover {
            transform: translateY(-1px);
            border-color: #0ea5e9;
            box-shadow: 0 10px 24px rgba(14,165,233,0.35);
        }

        /* Smaller clear buttons inside #clear-actions */
        #clear-actions .stButton>button {
            min-width: 120px;
            padding: 0.4rem 0.75rem;
            font-size: 13px;
        }
        </style>
        <script>
        // Add sticky class to the column containing the map anchor
        const stickIsoMapColumn = () => {
          const anchor = document.getElementById("map-sticky-anchor");
          if (!anchor) {
            requestAnimationFrame(stickIsoMapColumn);
            return;
          }
          const col = anchor.closest("div[data-testid='column']");
          if (col && !col.classList.contains("sticky-map-col")) {
            col.classList.add("sticky-map-col");
          }
        };
        requestAnimationFrame(stickIsoMapColumn);
        </script>
        """,
        unsafe_allow_html=True,
    )


def mount_lang_toggle_class():
    """Tag the language toggle button after it's rendered so CSS can position it."""
    st.markdown(
        """
        <script>
        const tagLangBtn = () => {
          const buttons = Array.from(document.querySelectorAll('div[data-testid="stButton"]'));
          const btn = buttons.find(b => ['🌐','🇬🇧','🇷🇺'].includes(b.innerText.trim()));
          if (!btn) {
            requestAnimationFrame(tagLangBtn);
            return;
          }
          btn.classList.add('lang-toggle');
        };
        requestAnimationFrame(tagLangBtn);
        </script>
        """,
        unsafe_allow_html=True,
    )


def inject_toolbar_title():
    """Place ISOCHRONA label into Streamlit toolbar."""
    st.markdown(
        """
        <script>
        const mountIsoToolbarTitle = () => {
          const html = `
            <div id="iso-toolbar-title"
                 style="display:flex;align-items:center;gap:6px;
                        font-family:'Russo One','Sora',sans-serif;
                        font-size:18px; letter-spacing:1px; color:#e2e8f0;">
                ISOCHRONA
            </div>`;
          const target = document.querySelector("div.stAppToolbar.st-emotion-cache-14vh5up") ||
                         document.querySelector("div[data-testid='stToolbar']");
          if (!target) {
            requestAnimationFrame(mountIsoToolbarTitle);
            return;
          }
          if (!document.getElementById("iso-toolbar-title")) {
            const wrap = document.createElement("div");
            wrap.innerHTML = html.trim();
            target.prepend(wrap.firstChild);
          }
        };
        requestAnimationFrame(mountIsoToolbarTitle);
        </script>
        """,
        unsafe_allow_html=True,
    )
