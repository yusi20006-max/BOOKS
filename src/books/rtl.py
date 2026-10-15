"""Shared RTL-first stylesheet for the Streamlit user interface."""

RTL_STYLESHEET = """
<style>
:root { color-scheme: light dark; }

/* Keep Streamlit's document canvas LTR so native sidebar transforms work.
   Apply RTL to content regions, not to the application root. */
.stApp { direction: ltr; }
.stApp .main .block-container {
    direction: rtl;
    text-align: right;
}
.stApp [data-testid="stSidebarContent"] {
    direction: rtl;
}
.stApp [data-testid="stSidebarContent"] * {
    text-align: right;
}

/* Persian text and form controls default to RTL. Explicitly restore LTR for
   machine-oriented values and isolate bidirectional runs from surrounding text. */
.stApp p,
.stApp label,
.stApp h1,
.stApp h2,
.stApp h3,
.stApp li,
.stApp th,
.stApp td,
.stApp [data-testid="stMarkdownContainer"] {
    text-align: right;
    line-height: 1.9;
}
.stApp input,
.stApp textarea,
.stApp [data-baseweb="select"] {
    direction: rtl;
    text-align: right;
}
.stApp input[type="number"],
.stApp input[type="url"],
.stApp input[type="email"],
.stApp input[type="password"],
.stApp input[type="date"],
.stApp input[type="time"],
.stApp code,
.stApp pre,
.stApp kbd,
.stApp samp,
.stApp [dir="ltr"],
.stApp .ltr {
    direction: ltr;
    text-align: left;
    unicode-bidi: isolate;
}
.stApp .stButton > button,
.stApp .stDownloadButton > button {
    direction: rtl;
}
.stApp table,
.stApp [data-testid="stDataFrame"],
.stApp [data-testid="stTable"] {
    direction: rtl;
}
.block-container {
    max-width: 1200px;
    padding: 2rem 1rem 4rem;
}
@media (max-width: 900px) {
    .block-container {
        padding: 1rem .75rem 3rem;
    }
    .stApp [data-testid="stDataFrame"],
    .stApp [data-testid="stTable"] {
        max-width: 100%;
        overflow-x: auto;
    }
    .stApp img {
        max-width: 100%;
        height: auto;
    }
}
@media (min-width: 641px) and (max-width: 900px) {
    .stApp [data-testid="stHorizontalBlock"] {
        flex-wrap: wrap;
        gap: .75rem;
    }
    .stApp [data-testid="stHorizontalBlock"] > [data-testid="column"] {
        flex: 1 1 calc(50% - .75rem) !important;
        min-width: calc(50% - .75rem) !important;
    }
}
@media (max-width: 640px) {
    .stApp .main .block-container {
        padding-inline: .65rem;
    }
    .stApp [data-testid="stHorizontalBlock"] {
        flex-wrap: wrap;
        gap: .5rem;
    }
    .stApp [data-testid="stHorizontalBlock"] > [data-testid="column"] {
        flex: 1 1 100% !important;
        width: 100% !important;
        min-width: 100% !important;
    }
    .stApp .stButton > button,
    .stApp .stDownloadButton > button,
    .stApp .stFormSubmitButton > button {
        width: 100%;
        min-height: 2.75rem;
        white-space: normal;
    }
    .stApp input,
    .stApp textarea,
    .stApp [data-baseweb="select"] {
        min-height: 2.75rem;
    }
    .stApp [data-testid="stDataFrame"],
    .stApp [data-testid="stTable"] {
        max-width: 100%;
        overflow-x: auto;
    }
}
</style>
"""
