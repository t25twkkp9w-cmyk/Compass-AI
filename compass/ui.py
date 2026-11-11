"""Presentation adapted from the user-selected AI-Compass-v2.html prototype."""
from html import escape
import streamlit as st

CSS='''
<style>
:root {--compass-ink:#23374f;--compass-muted:#728198;--compass-blue:#4b6f9e;--compass-line:#dce3ed}
html,body,[class*="css"],.stApp {font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;color:#23374f}
.stApp {background:#f3f6fa} .block-container {max-width:1510px;padding:1.5rem 2.5rem 3rem}
h1,h2,h3 {color:#23374f;letter-spacing:-.6px;font-weight:650} h1 {font-size:2rem} h2 {font-size:1.3rem} h3 {font-size:1.05rem}
p,li {line-height:1.75} [data-testid="stCaptionContainer"] {color:#728198}
[data-testid="stSidebar"] {background:#22354d;border-right:none;min-width:244px;max-width:280px}
[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {padding:1.7rem 1rem}
[data-testid="stSidebar"] p,[data-testid="stSidebar"] label,[data-testid="stSidebar"] .stCaption {color:#b6c6dc!important}
[data-testid="stSidebar"] h1 {color:white;font-size:1.4rem;letter-spacing:-.5px}
[data-testid="stSidebar"] hr {border-color:#ffffff16}
[data-testid="stSidebar"] [data-baseweb="select"]>div {background:#304863;color:#f4f7fc;border-color:#4a6383}
[data-testid="stSidebar"] [data-baseweb="select"] svg {fill:#b6c6dc}
[data-testid="stSidebar"] [data-testid="stRadio"] label {border-radius:6px;padding:8px 10px;margin:2px 0;font-size:12px;width:100%}
[data-testid="stSidebar"] [data-testid="stRadio"] label:hover {background:#304863}
[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) {background:#385171;border-left:2px solid #9db7da}
[data-testid="stSidebar"] [data-testid="stRadio"] label>div:first-child {display:none}
[data-testid="stSidebar"] [data-testid="stRadio"] label p {font-size:12px}
.brand-caption {font-size:9px;letter-spacing:1.8px;color:#a8bcd5;margin:-8px 0 25px 5px}
.workspace-card {display:flex;gap:12px;align-items:center;padding:17px 8px;border-top:1px solid #ffffff16;border-bottom:1px solid #ffffff16;margin-bottom:20px;color:#dce7f4;font-size:12px}
.workspace-avatar {display:grid;place-items:center;border:1px solid #617a9a;border-radius:6px;width:32px;height:32px;color:#b6c9e1;font-size:17px}
.workspace-card small {display:block;font-size:10px;color:#9bb0ca;margin-top:5px}
.nav-eyebrow {font-size:10px;letter-spacing:1.8px;color:#8fa7c6;margin:15px 10px 10px}
.compass-topbar {display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #dce3ed;padding:0 0 19px;margin-bottom:12px;font-size:12px;color:#728198}
.topbar-right {display:flex;gap:14px;align-items:center}.mode-pill {font-size:9px;letter-spacing:1px;background:#eaf0f8;border:1px solid #dbe4ef;padding:6px 9px;border-radius:4px;color:#6e829d}
.avatar {display:grid;place-items:center;width:32px;height:32px;border-radius:50%;background:#dfe7f2;color:#5e769a;font-size:11px}
.demo-banner {font-size:10px;padding:9px 14px;background:#eaf0f8;color:#7184a0;border:1px solid #dce5f1;border-radius:5px;margin-bottom:26px}
.hero {background:linear-gradient(125deg,#e6edf7,#edf2fa 70%,#e4ebf5);border:1px solid #d7e1ee;border-radius:12px;padding:32px 34px;position:relative;overflow:hidden;margin-bottom:16px}
.hero h1 {color:#23374f;font-size:36px;letter-spacing:-1.3px;line-height:1.2;font-weight:650;margin:0 0 16px;max-width:670px}
.hero p {max-width:630px;color:#61758e;margin:0;font-size:14px}.compass-art {position:absolute;right:40px;top:-10px;font-size:190px;color:#6e8fb51c;pointer-events:none}
.eyebrow {font-size:10px;color:#4b6f9e;letter-spacing:1.9px;font-weight:700;margin-bottom:13px}
.feature-card {background:white;border:1px solid #dce3ed;border-radius:12px;padding:23px;min-height:194px;box-shadow:0 3px 12px #28435f03}
.feature-card h3 {font-size:15px;margin:15px 0 8px;letter-spacing:-.2px}.feature-card p {color:#728198;font-size:12px;line-height:1.8;margin-bottom:0}
.iconbox {display:grid;place-items:center;width:35px;height:35px;background:#e9eff8;border-radius:7px;color:#597aab;font-size:19px}
.sectionhead {display:flex;align-items:center;justify-content:space-between;margin:28px 0 15px}.sectionhead h2 {font-size:20px;margin:0}.sectionhead span {color:#728198;font-size:11px}
.callout {padding:14px 17px;border-left:3px solid #88a4c9;background:#edf2fa;border-radius:0 6px 6px 0;color:#5f7696;font-size:12px;line-height:1.8;margin:18px 0}
.compass-footer {display:flex;justify-content:space-between;border-top:1px solid #dce3ed;margin-top:36px;padding-top:18px;font-size:10px;color:#8596ad}
[data-testid="stMetric"] {background:white;border:1px solid #dce3ed;padding:20px 23px;border-radius:12px;min-height:116px}
[data-testid="stMetricLabel"] p {font-size:10px!important;letter-spacing:.8px;text-transform:uppercase;color:#728198!important}
[data-testid="stMetricValue"] {font-size:27px!important;letter-spacing:-.7px;font-weight:650;color:#23374f}
[data-testid="stExpander"], [data-testid="stForm"], [data-testid="stVerticalBlockBorderWrapper"]>div {border-color:#dce3ed;border-radius:10px}
[data-testid="stExpander"], [data-testid="stForm"] {background:white}
[data-testid="stForm"] {padding:20px}
.stButton>button,[data-testid="stFormSubmitButton"]>button,.stDownloadButton>button {border-radius:6px;font-size:12px;padding:8px 15px;border-color:#dce3ed;color:#23374f}
button[kind="primary"],button[kind="primaryFormSubmit"] {background:#4c6e9a!important;color:white!important;border-color:#4c6e9a!important}
button[kind="primary"]:hover {background:#395b87!important}
[data-testid="stTextInput"] input,[data-testid="stTextArea"] textarea {background:#fafcfb;color:#23374f;font-size:13px}
[data-baseweb="tab-list"] {gap:22px;border-bottom:1px solid #dce3ed}
[data-baseweb="tab"] {font-size:12px;padding:12px 0;color:#728198}[aria-selected="true"][data-baseweb="tab"] {color:#4b6f9e}
[data-testid="stDataFrame"] {border:1px solid #dce3ed;border-radius:10px;overflow:hidden}
[data-testid="stAlert"] {font-size:12px;border-radius:8px}
@media(max-width:800px){.block-container{padding:1rem}.hero{padding:24px}.hero h1{font-size:29px}.compass-art{display:none}.compass-topbar{gap:10px}.topbar-right{gap:7px}.compass-footer{display:block}.feature-card{min-height:0}}
</style>'''

def install_theme():st.markdown(CSS+REFERENCE_REFINEMENTS,unsafe_allow_html=True)
def topbar(page,principal,mode,demo):
    initials=''.join(x[0] for x in principal.name.split()[:2])
    st.markdown(f'<div class="compass-topbar"><span>Workspace / {escape(page)}</span><div class="topbar-right"><span class="mode-pill">{"LOCAL EVIDENCE" if mode=="local" else "LIVE MODEL"}</span><span>{escape(principal.name)}</span><span class="avatar">{escape(initials)}</span></div></div>',unsafe_allow_html=True)
    if demo:st.markdown('<div class="demo-banner">SYNTHETIC DATA · Demo role switching simulates perspectives. Assigned case access and action gates are checked by the application.</div>',unsafe_allow_html=True)
def feature(icon,title,text):
    st.markdown(f'<div class="feature-card"><div class="iconbox">{escape(icon)}</div><h3>{escape(title)}</h3><p>{escape(text)}</p></div>',unsafe_allow_html=True)
def section(title,note=''):
    st.markdown(f'<div class="sectionhead"><h2>{escape(title)}</h2><span>{escape(note)}</span></div>',unsafe_allow_html=True)
def footer():
    st.markdown('<div class="compass-footer"><span>AI Compass · Right Tool. Right Policy. Right Guidance.</span><span>Enterprise guidance workspace · Guidance is not formal approval.</span></div>',unsafe_allow_html=True)

REFERENCE_REFINEMENTS='''<style>
.st-key-compass_header {background:#fbfcfe;border-bottom:1px solid #dce3ed;margin:-24px -40px 0;padding:16px 40px 14px;width:calc(100% + 80px)}
.st-key-compass_header [data-testid="stSelectbox"] {max-width:300px;margin-left:auto}
.st-key-compass_header [data-baseweb="select"]>div {background:white;border:1px solid #dce3ed;border-radius:6px;min-height:37px;font-size:12px}
.header-breadcrumb {color:#728198;font-size:12px}.st-key-compass_header .avatar {margin-left:auto}
.demo-banner {margin:0 -40px 26px;padding:9px 40px;width:calc(100% + 80px);border-radius:0;border-width:0 0 1px}
.st-key-overview_hero {background:linear-gradient(125deg,#e6edf7,#edf2fa 70%,#e4ebf5);border:1px solid #d7e1ee;border-radius:12px;padding:32px 34px 22px;position:relative;margin-bottom:24px}
.st-key-overview_hero .hero {background:transparent;border:0;padding:0;margin:0}
.st-key-overview_hero [data-testid="stForm"] {border:1px solid #ccd8e9;border-radius:9px;background:white;padding:8px;box-shadow:0 8px 20px #3a527009;max-width:860px}
.st-key-overview_hero [data-testid="stTextInput"] [data-baseweb="input"] {border:0;background:white}
.st-key-overview_hero [data-testid="stTextInput"] input {background:white;padding-left:12px}
.st-key-overview_hero [data-testid="stHorizontalBlock"] {gap:10px}
.st-key-overview_hero .stButton>button {border-radius:20px;background:#f8faff;border:1px solid #cdd9ea;color:#5e7696;font-size:11px;padding:6px 10px;white-space:nowrap}
[class*="st-key-featurecard_"] {background:white;border:1px solid #dce3ed;border-radius:12px;padding:22px;box-shadow:0 3px 12px #28435f03}
[class*="st-key-featurecard_"] .feature-card {border:0;padding:0;box-shadow:none;min-height:150px}
[class*="st-key-featurecard_"] .stButton>button {background:transparent;border:0;padding:4px 0;color:#4b6f9e;justify-content:flex-start;text-align:left;font-size:12px}
@media(max-width:800px){.st-key-compass_header{margin:-16px -16px 0;padding:12px 16px;width:calc(100% + 32px)}.demo-banner{margin:0 -16px 20px;padding:8px 16px;width:calc(100% + 32px)}.st-key-overview_hero{padding:24px 20px}.st-key-compass_header [data-testid="stSelectbox"]{max-width:100%}}
</style>'''
