"""
Impact Assessment System
DOST SETUP 4.0 iFund Program — Region VI

Tracks MSME project performance across three checkpoints:
  Pre-PIS (Baseline Target) -> Semestral Status Report (Mid-Year Progress) -> Annual PIS (Accomplished)

Output progress is stored as an append-only HISTORY (one record per output per
semestral cycle). The dashboard shows each output "as of" the selected evaluation
semester, marks the semester it was first accomplished, and plots progress per
semester on a line graph. See REVISION_output_progress_history.md.

Run with live data by adding SUPABASE_URL / SUPABASE_KEY to .streamlit/secrets.toml.
Falls back to bundled demo data otherwise.
"""

import math
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime


def html_block(s: str) -> str:
    """Strip leading whitespace from every line of an HTML snippet.

    Streamlit's markdown renderer follows CommonMark: any line indented by
    4+ spaces is treated as a literal code block, not HTML. Multi-line
    f-strings built inside nested `for`/`with` blocks pick up exactly that
    indentation, so without this the HTML tags get printed as visible text
    instead of being rendered. Stripping per-line indentation (safe here
    since these are HTML fragments, not content where whitespace matters)
    fixes that.
    """
    return "\n".join(line.lstrip() for line in s.strip("\n").split("\n"))


def render_html(s: str) -> None:
    """st.markdown() for HTML fragments, with the indentation fix applied."""
    st.markdown(html_block(s), unsafe_allow_html=True)

# --------------------------------------------------------------------------------------
# PAGE CONFIG & GLOBAL STYLES
# --------------------------------------------------------------------------------------

st.set_page_config(
    page_title="Impact Assessment System",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

NO_SUB = "No submission yet"   # output has no history record at or before the selected semester

STATUS_COLORS = {
    "Accomplished": "#1E9E6B",
    "Partially accomplished": "#E0A426",
    "Not accomplished": "#E0526B",
    "Not yet due": "#8B95A8",
    NO_SUB: "#8B95A8",
}

STATUS_BG = {
    "Accomplished": "#E7F7F0",
    "Partially accomplished": "#FDF3DF",
    "Not accomplished": "#FCE9EC",
    "Not yet due": "#EEF1F6",
    NO_SUB: "#EEF1F6",
}

STATUS_ICON = {
    "Accomplished": "✓",
    "Partially accomplished": "—",
    "Not accomplished": "✕",
    "Not yet due": "…",
    NO_SUB: "…",
}

# One colour per output line on the trend graph (status is shown by the marker fill instead)
LINE_COLORS = ["#2F6FED", "#0E8F9A", "#7B4FD6", "#16213E", "#C2417A", "#8A6D3B", "#6B7690"]

# Navy / blue palette to match the reference mobile-dashboard UI
NAVY = "#16213E"
BLUE = "#2F6FED"
LIGHT_BLUE = "#6EC6E8"
BG = "#F2F5FA"
TILE_COLORS = [NAVY, BLUE, LIGHT_BLUE, "#4B5A7A"]

CUSTOM_CSS = f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; }}

    .stApp {{ background: {BG}; }}
    .block-container {{padding-top: 1.5rem; padding-bottom: 3rem; max-width: 1150px;}}

    /* Native st.metric restyled as a soft rounded tile */
    div[data-testid="stMetric"] {{
        background: white;
        border: none;
        border-radius: 18px;
        padding: 16px 18px 14px 18px;
        box-shadow: 0 4px 16px rgba(22,33,62,0.06);
    }}
    div[data-testid="stMetricLabel"] {{color: #8B95A8; font-size: 0.8rem; font-weight: 600;}}
    div[data-testid="stMetricValue"] {{color: {NAVY}; font-weight: 800;}}

    .badge {{
        display: inline-block;
        padding: 4px 12px;
        border-radius: 999px;
        font-size: 0.76rem;
        font-weight: 700;
    }}
    .section-header {{
        font-size: 1.05rem;
        color: {NAVY};
        font-weight: 800;
        margin-top: 0.8rem;
        margin-bottom: 0.9rem;
        letter-spacing: -0.01em;
        display: flex;
        align-items: center;
        gap: 8px;
    }}
    .section-header .icon {{
        font-size: 1.1rem;
    }}
    .section-sub {{
        color: #8B95A8;
        font-size: 0.82rem;
        font-weight: 500;
        margin-top: -0.6rem;
        margin-bottom: 0.9rem;
    }}
    .legend-strip {{
        display:flex; flex-wrap:wrap; gap:10px; margin-bottom: 4px;
    }}
    .legend-chip {{
        display:flex; align-items:center; gap:6px;
        font-size: 0.78rem; font-weight: 600; color: {NAVY};
        background: white; border-radius: 999px; padding: 5px 12px;
        box-shadow: 0 2px 8px rgba(22,33,62,0.06);
    }}
    .legend-dot {{ width:8px; height:8px; border-radius:50%; }}
    .card {{
        border: none;
        border-radius: 18px;
        padding: 18px 20px;
        margin-bottom: 14px;
        background: white;
        box-shadow: 0 4px 16px rgba(22,33,62,0.06);
    }}
    .kpi-tile {{
        border-radius: 18px;
        padding: 16px 18px;
        color: white;
        box-shadow: 0 6px 18px rgba(22,33,62,0.14);
    }}
    .kpi-tile .kpi-label {{font-size: 0.78rem; opacity: 0.85; font-weight: 600;}}
    .kpi-tile .kpi-value {{font-size: 1.6rem; font-weight: 800; margin-top: 2px;}}
    .kpi-tile .kpi-sub {{font-size: 0.75rem; opacity: 0.85; margin-top: 4px;}}

    .ring-wrap {{display:flex; align-items:center; gap: 12px;}}
    .ring {{
        width: 54px; height: 54px; border-radius: 50%;
        display:flex; align-items:center; justify-content:center;
        font-size: 0.72rem; font-weight: 800; color: {NAVY};
        background: conic-gradient(var(--ring-color) calc(var(--pct) * 1%), #E9EDF5 0);
        flex-shrink: 0;
    }}
    .ring-inner {{
        width: 42px; height: 42px; border-radius: 50%; background: white;
        display:flex; align-items:center; justify-content:center;
    }}

    .obj-card-title {{font-weight: 700; font-size: 0.95rem; margin-bottom: 6px; color: {NAVY};}}
    .obj-card-sub {{color: {BLUE}; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.06em; font-weight: 700;}}
    .note-text {{color: #6B7690; font-size: 0.85rem; margin-top: 8px; line-height: 1.4;}}
    hr {{margin: 1.4rem 0; border-color: #E3E8F0;}}

    section[data-testid="stSidebar"] {{
        background: {NAVY};
    }}
    section[data-testid="stSidebar"] * {{ color: #E8ECF6 !important; }}
    section[data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] > div {{
        background: #22304F; border-color: #34446B; border-radius: 10px;
    }}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def kpi_tile_html(label, value, sub, color, icon=""):
    return f"""
    <div class="kpi-tile" style="background:{color};">
        <div class="kpi-label">{icon} {label}</div>
        <div class="kpi-value">{value}</div>
        <div class="kpi-sub">{sub}</div>
    </div>
    """


def ring_html(pct, status, size_label=""):
    pct = max(0, min(100, pct))
    color = STATUS_COLORS.get(status, BLUE)
    return f"""
    <div class="ring" style="--pct:{pct};--ring-color:{color};">
        <div class="ring-inner">{pct}%</div>
    </div>
    """


def section_header(icon, title, subtitle=None):
    render_html(f'<div class="section-header"><span class="icon">{icon}</span>{title}</div>')
    if subtitle:
        render_html(f'<div class="section-sub">{subtitle}</div>')


def status_legend(show_first=False, show_no_sub=False):
    chips = "".join(
        f'<div class="legend-chip"><span class="legend-dot" style="background:{STATUS_COLORS[s]};"></span>{s}</div>'
        for s in ["Accomplished", "Partially accomplished", "Not accomplished"]
    )
    if show_no_sub:
        chips += (f'<div class="legend-chip"><span class="legend-dot" style="background:{STATUS_COLORS[NO_SUB]};">'
                  f'</span>{NO_SUB}</div>')
    if show_first:
        chips += (f'<div class="legend-chip"><span class="legend-dot" '
                  f'style="width:6px;height:6px;background:transparent;border:2px solid {NAVY};"></span>'
                  f'First accomplished</div>')
    render_html(f'<div class="legend-strip">{chips}</div>')


# --------------------------------------------------------------------------------------
# DEMO DATA
# --------------------------------------------------------------------------------------
# Structure per project:
#   program, general_objective
#   specific_objectives: [{id, text, pre_pis_target, semestral: {status, progress, note}, annual: {status, progress, note}}]
#   quantifiable_outputs: [{id, name, unit, target, pre_pis, history: [H(...)]}]
#       history is APPEND-ONLY: one H() record per semestral cycle; a correction is a new
#       record with correction_reason, and the record it replaces is flagged superseded=True.
#       actual / status / note shown on the dashboard are DERIVED from history (see output_as_of).
#   non_quantifiable: [{name, note, status}]
#   periods: ordered list of checkpoint labels used in the PIS progression trend
#   financials: {metric: {period_label: value or None}}

def H(cycle, actual, status, note, submitted_at, superseded=False, correction_reason=None):
    """One append-only history record for a quantifiable output (illustrative demo values)."""
    return {"cycle": cycle, "actual": actual, "status": status, "note": note,
            "submitted_at": submitted_at, "superseded": superseded,
            "correction_reason": correction_reason}


def build_demo_data():
    S1_21, S2_21, S1_22 = "S1 2021 (Jan–Jun)", "S2 2021 (Jul–Dec)", "S1 2022 (Jan–Jun)"
    S2_22 = "S2 2022 (Jul–Dec)"
    PA, AC, NA = "Partially accomplished", "Accomplished", "Not accomplished"

    periods = [
        "Pre-PIS",
        "PIS 1 (Year 1)",
        "PIS 2 (Year 2)",
        "PIS 3 (Year 3)",
    ]

    honore = {
        "program": "DOST SETUP 4.0 iFund Program — Region VI",
        "general_objective": "This project aims to improve the production facilities of Honoré Café through the acquisition of S&T technologies.",
        "periods": periods,
        "semestral_cycles": ["S1 2021 (Jan–Jun)", "S2 2021 (Jul–Dec)", "S1 2022 (Jan–Jun)"],
        "current_semestral_cycle": "S2 2021 (Jul–Dec)",
        "specific_objectives": [
            {
                "id": 1,
                "text": "To improve product quality by producing consistent appearance of finished products through an evenly distributed temperature of the three-deck oven",
                "pre_pis_target": "Stainless LPG 3-deck oven acquired and operational",
                "semestral": {"status": "Accomplished", "progress": 100,
                              "note": "Stainless LPG oven in good working condition as of December 2021."},
                "annual": {"status": "Accomplished", "progress": 100,
                           "note": "Consistent product appearance sustained through Year 1."},
            },
            {
                "id": 2,
                "text": "To improve the production process by reducing baking time by at least 50% (four hours to two hours) and increasing baking capacity to 100%",
                "pre_pis_target": "Baking time: 4 hrs → 2 hrs · Capacity: 792 → 1,584 pcs/day",
                "semestral": {"status": "Partially accomplished", "progress": 57,
                              "note": "Baking time target met; capacity increase lagging due to COVID-19."},
                "annual": {"status": "Partially accomplished", "progress": 62,
                           "note": "Baking time sustained at 2 hrs; capacity still below target."},
            },
            {
                "id": 3,
                "text": "To improve the production management system and reduce production delays by introducing an inventory system software",
                "pre_pis_target": "POS / inventory system deployed and in active use",
                "semestral": {"status": "Not accomplished", "progress": 0,
                              "note": "POS not utilized due to lack of training for new employees."},
                "annual": {"status": "Partially accomplished", "progress": 40,
                           "note": "Staff training conducted; partial adoption of POS module."},
            },
            {
                "id": 4,
                "text": "To enhance compliance with food safety standards",
                "pre_pis_target": "Certified compliance with DOST-VI food safety standards",
                "semestral": {"status": "Accomplished", "progress": 100,
                              "note": "Enhanced compliance via procured stainless steel equipment and DOST-VI Food Safety Consultancy."},
                "annual": {"status": "Accomplished", "progress": 100,
                           "note": "Compliance maintained; no citations in Year 1 inspection."},
            },
        ],
        "quantifiable_outputs": [
            {"id": "h1", "name": "Improve product quality (consistent appearance via 3-deck oven)",
             "unit": "n/a", "target": 100, "pre_pis": 0, "history": [
                H(S1_21, 60, PA, "Oven delivered; installation and calibration still ongoing.", "2021-07-12"),
                H(S2_21, 100, AC, "Stainless LPG Oven in good working condition as of December 2021.", "2022-01-10"),
             ]},
            {"id": "h2", "name": "Reduce baking time by 50% (4 hrs → 2 hrs)",
             "unit": "%", "target": 50, "pre_pis": 0, "history": [
                H(S1_21, 25, PA, "Baking time reduced from 4 hrs to 3 hrs.", "2021-07-12"),
                H(S2_21, 50, AC, "Target baking time achieved and sustained.", "2022-01-10"),
             ]},
            {"id": "h3", "name": "Improve baking capacity by 100% (792 → 1,584 pcs/day)",
             "unit": "pcs/day", "target": 1584, "pre_pis": 792, "history": [
                H(S1_21, 120, NA, "Operations largely suspended during COVID-19 lockdown.", "2021-07-12"),
                H(S2_21, 214, NA, "COVID-19 significantly affected operations during the first year.", "2022-01-10"),
             ]},
            {"id": "h4", "name": "Increase production volume by 45% (247,200 → 358,320 pcs)",
             "unit": "pcs", "target": 358320, "pre_pis": 247200, "history": [
                H(S1_21, 52000, NA, "Production volume down due to COVID-19.", "2021-07-12"),
                H(S2_21, 77040, NA, "Production volume decreased by 69% due to COVID-19.", "2022-01-10"),
             ]},
            {"id": "h5", "name": "Increase sales by 78% (₱3.06M → ₱5.46M)",
             "unit": "₱", "target": 5455510, "pre_pis": 3060000, "history": [
                H(S1_21, 1250000, NA, "Sales decreased due to COVID-19 pandemic.", "2021-07-12", superseded=True),
                H(S1_21, 1350000, NA, "Sales decreased due to COVID-19 pandemic.", "2021-07-20",
                  correction_reason="Corrected after reconciling official receipts."),
                H(S2_21, 2404800, NA, "Sales decreased by 21% due to COVID-19 pandemic.", "2022-01-10"),
             ]},
            {"id": "h6", "name": "Establish at least 2 additional markets in Aklan",
             "unit": "outlets", "target": 2, "pre_pis": 0, "history": [
                H(S2_21, 1, PA, "Only one additional outlet established in Kalibo, Aklan.", "2022-01-10"),
             ]},
            {"id": "h7", "name": "Generate at least 1 additional worker",
             "unit": "workers", "target": 1, "pre_pis": 0, "history": [
                H(S1_21, 1, AC, "One additional worker hired.", "2021-07-12"),
                H(S2_21, 4, AC, "Four additional workers hired during the semester.", "2022-01-10"),
             ]},
        ],
        "non_quantifiable": [
            {"name": "Enhance compliance with food safety standards",
             "note": "Enhanced compliance via procured stainless steel equipment and DOST-VI Food Safety Consultancy.",
             "status": "Accomplished"},
            {"name": "Improve production management using inventory/POS system software",
             "note": "No improvement in production management. POS not utilized due to lack of training for new employees.",
             "status": "Not accomplished"},
        ],
        "financials": {
            "Assets": {"Pre-PIS": 2230000, "PIS 1 (Year 1)": 2230000, "PIS 2 (Year 2)": 2410000, "PIS 3 (Year 3)": None},
            "Employment": {"Pre-PIS": 17, "PIS 1 (Year 1)": 21, "PIS 2 (Year 2)": None, "PIS 3 (Year 3)": None},
            "Gross Sales": {"Pre-PIS": 58000000, "PIS 1 (Year 1)": 45820000, "PIS 2 (Year 2)": None, "PIS 3 (Year 3)": None},
        },
        "asset_breakdown": {
            "metric": ["Land", "Building", "Equipment", "Working Cap."],
            "pre_pis": [1500000, 250000, 375000, 100000],
            "current": [1500000, 250000, 375000, 100000],
        },
    }

    hanjim = {
        "program": "DOST SETUP 4.0 iFund Program — Region VI",
        "general_objective": "This project aims to modernize the meat-processing line of Han Jim Marketing Corporation through the acquisition of S&T technologies.",
        "periods": periods,
        "semestral_cycles": ["S1 2022 (Jan–Jun)", "S2 2022 (Jul–Dec)"],
        "current_semestral_cycle": "S2 2022 (Jul–Dec)",
        "specific_objectives": [
            {
                "id": 1,
                "text": "To improve product shelf life through acquisition of a vacuum sealing machine",
                "pre_pis_target": "Vacuum sealing machine installed and operational",
                "semestral": {"status": "Accomplished", "progress": 100, "note": "Vacuum sealer installed and running since Q2 2022."},
                "annual": {"status": "Accomplished", "progress": 100, "note": "Shelf life extended from 3 to 10 days as planned."},
            },
            {
                "id": 2,
                "text": "To increase production capacity by upgrading the chiller and freezer units",
                "pre_pis_target": "Capacity: 300 → 600 kg/day",
                "semestral": {"status": "Partially accomplished", "progress": 65, "note": "Chiller upgraded; freezer upgrade delayed by supplier backorder."},
                "annual": {"status": "Accomplished", "progress": 95, "note": "Freezer unit installed Q1; capacity near target by year-end."},
            },
            {
                "id": 3,
                "text": "To expand market reach to at least 3 new municipalities",
                "pre_pis_target": "3 new municipalities served",
                "semestral": {"status": "Not accomplished", "progress": 0, "note": "Focus remained on local market during equipment transition."},
                "annual": {"status": "Partially accomplished", "progress": 33, "note": "1 of 3 target municipalities reached."},
            },
        ],
        "quantifiable_outputs": [
            {"id": "j1", "name": "Increase production capacity by 100% (300 → 600 kg/day)",
             "unit": "kg/day", "target": 600, "pre_pis": 300, "history": [
                H(S1_22, 380, PA, "Chiller upgrade complete; freezer upgrade pending.", "2022-07-11"),
                H(S2_22, 480, PA, "Chiller upgrade complete; freezer upgrade completed late in the year.", "2023-01-09"),
             ]},
            {"id": "j2", "name": "Extend product shelf life (3 → 10 days)",
             "unit": "days", "target": 10, "pre_pis": 3, "history": [
                H(S1_22, 7, PA, "Vacuum sealing adopted on half of the product lines.", "2022-07-11"),
                H(S2_22, 10, AC, "Vacuum sealing fully adopted across product lines.", "2023-01-09"),
             ]},
            {"id": "j3", "name": "Increase sales by 40% (₱1.8M → ₱2.52M)",
             "unit": "₱", "target": 2520000, "pre_pis": 1800000, "history": [
                H(S1_22, 1950000, NA, "Sales held back during equipment transition.", "2022-07-11"),
                H(S2_22, 2350000, PA, "Strong Q4 sales narrowed the gap to target.", "2023-01-09"),
             ]},
            {"id": "j4", "name": "Generate at least 2 additional workers",
             "unit": "workers", "target": 2, "pre_pis": 0, "history": [
                H(S1_22, 2, AC, "Two new hires to support the expanded line.", "2022-07-11"),
                H(S2_22, 3, AC, "Three new hires to support the expanded line.", "2023-01-09"),
             ]},
        ],
        "non_quantifiable": [
            {"name": "Improve HACCP-aligned handling practices",
             "note": "Staff completed food-handling refresher training; documentation still pending sign-off.",
             "status": "Partially accomplished"},
        ],
        "financials": {
            "Assets": {"Pre-PIS": 1450000, "PIS 1 (Year 1)": 1980000, "PIS 2 (Year 2)": None, "PIS 3 (Year 3)": None},
            "Employment": {"Pre-PIS": 9, "PIS 1 (Year 1)": 12, "PIS 2 (Year 2)": None, "PIS 3 (Year 3)": None},
            "Gross Sales": {"Pre-PIS": 1800000, "PIS 1 (Year 1)": 2350000, "PIS 2 (Year 2)": None, "PIS 3 (Year 3)": None},
        },
        "asset_breakdown": {
            "metric": ["Land", "Building", "Equipment", "Working Cap."],
            "pre_pis": [500000, 300000, 500000, 150000],
            "current": [500000, 300000, 980000, 200000],
        },
    }

    return {
        "Honore Cafe": honore,
        "Han Jim Marketing Corporation": hanjim,
    }


DATA = build_demo_data()


# --------------------------------------------------------------------------------------
# HELPERS
# --------------------------------------------------------------------------------------

def peso(v):
    if v is None:
        return "—"
    if abs(v) >= 1_000_000:
        return f"₱{v/1_000_000:.2f}M"
    if abs(v) >= 1_000:
        return f"₱{v/1_000:.1f}K"
    return f"₱{v:,.0f}"


def fmt_value(v, unit):
    if v is None:
        return "—"
    if unit == "₱":
        return peso(v)
    if unit == "n/a":
        return "—"
    return f"{v:,.0f} {unit}".strip()


def badge_html(status):
    color = STATUS_COLORS.get(status, "#6b7280")
    bg = STATUS_BG.get(status, "#f3f4f6")
    icon = STATUS_ICON.get(status, "")
    return f'<span class="badge" style="color:{color};background:{bg};">{icon} {status}</span>'


def progress_bar_html(pct, status):
    pct = max(0, min(100, pct))
    color = STATUS_COLORS.get(status, "#6b7280")
    return f"""
    <div style="background:#e5e7eb;border-radius:6px;height:8px;width:100%;margin:6px 0;">
        <div style="background:{color};width:{pct}%;height:8px;border-radius:6px;"></div>
    </div>
    """


def pct_change(old, new):
    if old is None or new is None or old == 0:
        return None
    return round((new - old) / old * 100, 1)


def short_cycle(label):
    """'S2 2021 (Jul–Dec)' -> 'S2 2021'"""
    return label.split(" (")[0] if label else label


def cycle_index(project, cycle_label):
    """Position of a cycle in the project's ordered semestral_cycles list."""
    return project["semestral_cycles"].index(cycle_label)


def output_series(project, output, up_to_cycle):
    """Current (non-superseded) history records up to and including `up_to_cycle`, oldest first."""
    cutoff = cycle_index(project, up_to_cycle)
    rows = [h for h in output["history"]
            if not h.get("superseded") and cycle_index(project, h["cycle"]) <= cutoff]
    return sorted(rows, key=lambda h: cycle_index(project, h["cycle"]))


def output_as_of(project, output, cycle_label):
    """State of an output as of `cycle_label`, carrying forward the last reported value.
    Returns None if nothing has been reported at or before that cycle."""
    series = output_series(project, output, cycle_label)
    if not series:
        return None
    latest = series[-1]
    return {**latest, "carried_forward": latest["cycle"] != cycle_label, "reported_in": latest["cycle"]}


def first_achieved_cycle(project, output, up_to_cycle):
    """First cycle (at or before `up_to_cycle`) whose status is Accomplished, else None.
    Never reveals an achievement that happened after the selected semester."""
    for h in output_series(project, output, up_to_cycle):
        if h["status"] == "Accomplished":
            return h["cycle"]
    return None


def fmt_hist_value(v, unit):
    if v is None:
        return "—"
    return f"{v:,.0f}" if unit == "n/a" else fmt_value(v, unit)


def history_df(project, output, up_to_cycle):
    """Every submission for an output up to the selected semester, including superseded ones."""
    cutoff = cycle_index(project, up_to_cycle)
    first = first_achieved_cycle(project, output, up_to_cycle)
    entries = sorted(
        [h for h in output["history"] if cycle_index(project, h["cycle"]) <= cutoff],
        key=lambda h: (cycle_index(project, h["cycle"]), h["submitted_at"]),
    )
    rows = []
    for h in entries:
        superseded = h.get("superseded", False)
        status = f"{STATUS_ICON[h['status']]} {h['status']}"
        if not superseded and h["cycle"] == first:
            status += " (first)"
        if superseded:
            record = "Superseded"
        elif h.get("correction_reason"):
            record = f"Correction: {h['correction_reason']}"
        else:
            record = ""
        rows.append({
            "Semester": short_cycle(h["cycle"]),
            "Actual": fmt_hist_value(h["actual"], output["unit"]),
            "% of target": f"{h['actual'] / output['target'] * 100:.0f}%" if output["target"] else "—",
            "Status": status,
            "Submitted": h["submitted_at"][:10],
            "Record": record,
            "Note": h["note"],
        })
    return pd.DataFrame(rows)


def render_history(project, output, up_to_cycle):
    df = history_df(project, output, up_to_cycle)
    if df.empty:
        st.caption("No submissions yet.")
        return
    styler = df.style.apply(
        lambda r: ["color:#9AA3B5;" if r["Record"] == "Superseded" else ""] * len(r), axis=1)
    st.dataframe(styler, hide_index=True, use_container_width=True)
    st.caption("Oldest to newest, up to the selected semester. Superseded rows were replaced by a later correction "
               "and are kept for the audit trail.")


# --------------------------------------------------------------------------------------
# SIDEBAR — FILTERS
# --------------------------------------------------------------------------------------

with st.sidebar:
    st.markdown("### 📊 Impact Assessment")
    st.caption("DOST SETUP 4.0 iFund Program · Region VI")
    st.markdown("---")

    project_name = st.selectbox("Project / MSME", list(DATA.keys()))
    project = DATA[project_name]

    eval_cycle = st.selectbox(
        "Evaluation semester",
        project["semestral_cycles"],
        index=project["semestral_cycles"].index(project["current_semestral_cycle"]),
        help="Shows each output as of this semester.",
    )

    status_filter = st.multiselect(
        "Status filter",
        ["Accomplished", "Partially accomplished", "Not accomplished"],
        default=["Accomplished", "Partially accomplished", "Not accomplished"],
    )

    st.markdown("---")
    data_mode = st.radio("Data source", ["Demo data", "Live (Supabase)"], index=0,
                          help="Add SUPABASE_URL / SUPABASE_KEY to .streamlit/secrets.toml to enable live data.")
    if data_mode == "Live (Supabase)":
        if "SUPABASE_URL" not in st.secrets or "SUPABASE_KEY" not in st.secrets:
            st.warning("No Supabase credentials found in secrets.toml — showing demo data instead.")
        else:
            st.info("Live data wiring goes here — connect your Supabase client and replace `DATA`.")

    st.markdown("---")
    st.caption(f"Last refreshed: {datetime.now().strftime('%b %d, %Y %I:%M %p')}")


# --------------------------------------------------------------------------------------
# HEADER
# --------------------------------------------------------------------------------------

render_html(f"""
<div style="background:{NAVY};border-radius:20px;padding:20px 24px;margin-bottom:18px;
            box-shadow:0 8px 24px rgba(22,33,62,0.18);">
    <div style="color:#9FB0D6;font-size:0.75rem;font-weight:700;letter-spacing:0.06em;text-transform:uppercase;">
        {project["program"]}
    </div>
    <div style="color:white;font-size:1.5rem;font-weight:800;margin-top:4px;">Impact Assessment</div>
    <div style="color:#C4D0EA;font-size:0.85rem;margin-top:6px;">{project["general_objective"]}</div>
    <div style="margin-top:12px;">
        <span class="badge" style="background:{BLUE};color:white;">{eval_cycle}</span>
    </div>
</div>
""")


# --------------------------------------------------------------------------------------
# TOP — QUANTITATIVE EXPECTED OUTPUTS
# --------------------------------------------------------------------------------------

section_header("📈", "Quantitative Expected Outputs",
               "How results as of the selected evaluation semester compare against Pre-PIS targets")

# Outputs "as of" the selected semester (derived from the append-only history)
outputs = []
for o in project["quantifiable_outputs"]:
    state = output_as_of(project, o, eval_cycle)
    outputs.append({
        **o,
        "actual": state["actual"] if state else None,
        "status": state["status"] if state else NO_SUB,
        "note": state["note"] if state else "No submission has been reported for this semester or earlier.",
        "carried_forward": state["carried_forward"] if state else False,
        "reported_in": state["reported_in"] if state else None,
        "achieved_in": first_achieved_cycle(project, o, eval_cycle),
    })

status_legend(show_first=True, show_no_sub=any(o["status"] == NO_SUB for o in outputs))
st.write("")

# Outputs with no submission yet are always shown (the status filter only has the three real statuses)
filtered_outputs = [o for o in outputs if o["status"] in status_filter or o["status"] == NO_SUB]

total = len(outputs)
n_acc = sum(1 for o in outputs if o["status"] == "Accomplished")
n_partial = sum(1 for o in outputs if o["status"] == "Partially accomplished")
n_not = sum(1 for o in outputs if o["status"] == "Not accomplished")
as_of_txt = f"as of {short_cycle(eval_cycle)}"

k1, k2, k3, k4 = st.columns(4)
with k1:
    render_html(kpi_tile_html("Total outputs", total, as_of_txt, NAVY, "🎯"))
with k2:
    render_html(kpi_tile_html("Accomplished", n_acc,
                               f"{n_acc/total*100:.0f}% of outputs" if total else "—", BLUE, "✓"))
with k3:
    render_html(kpi_tile_html("Partial", n_partial,
                               f"{n_partial/total*100:.0f}% of outputs" if total else "—", LIGHT_BLUE, "—"))
with k4:
    render_html(kpi_tile_html("Not accomplished", n_not,
                               f"{n_not/total*100:.0f}% of outputs" if total else "—", "#4B5A7A", "✕"))

st.write("")

# Target vs Actual — line graph, one line per output, one point per semester with a submission
chart_outputs = [o for o in filtered_outputs if o["target"] and output_series(project, o, eval_cycle)]
focus_name = None

if chart_outputs:
    render_html(f"""
        <div class="card" style="margin-bottom:12px;">
            <div style="font-weight:800;color:{NAVY};font-size:1rem;">
                📈 Target vs. Actual Achievement — by Output
            </div>
            <div class="note-text" style="margin-top:4px;">
                % of target achieved, per semester, as of <b>{short_cycle(eval_cycle)}</b>. Each line is one output;
                the dashed line marks 100% (target fully met). Marker colour shows the status reported that semester,
                and a <b>ring</b> marks the semester the output was <b>first accomplished</b>.
                Click a legend entry to hide or show a line, or click a point to see that output's history.
            </div>
        </div>
        """)

    cycles = project["semestral_cycles"]
    cyc_short = [short_cycle(c) for c in cycles]
    sel_idx = cycles.index(eval_cycle)
    fig = go.Figure()
    all_pcts = [100]

    for n, o in enumerate(chart_outputs):
        color = LINE_COLORS[n % len(LINE_COLORS)]
        gid = f"out{n}"
        label = o["name"] if len(o["name"]) < 42 else o["name"][:39] + "…"
        series = output_series(project, o, eval_cycle)
        pts = [(cycle_index(project, h["cycle"]), h["actual"] / o["target"] * 100, h) for h in series]
        all_pcts += [p for _, p, _ in pts]

        # legend entry (line swatch) — toggles every trace in this output's legend group
        fig.add_trace(go.Scatter(x=[None], y=[None], mode="lines", name=label, legendgroup=gid,
                                 line=dict(color=color, width=3)))
        # line segments: solid between consecutive semesters, dashed across a semester with no submission
        for (i0, p0, _), (i1, p1, _) in zip(pts, pts[1:]):
            fig.add_trace(go.Scatter(
                x=[cyc_short[i0], cyc_short[i1]], y=[p0, p1], mode="lines",
                line=dict(color=color, width=3, dash="solid" if i1 - i0 == 1 else "dash"),
                legendgroup=gid, showlegend=False, hoverinfo="skip"))
        # points, filled by status
        fig.add_trace(go.Scatter(
            x=[cyc_short[i] for i, _, _ in pts], y=[p for _, p, _ in pts], mode="markers",
            marker=dict(size=11, color=[STATUS_COLORS[h["status"]] for _, _, h in pts],
                        line=dict(color="white", width=2)),
            customdata=[[o["name"], short_cycle(h["cycle"]), fmt_hist_value(h["actual"], o["unit"]),
                         f"{p:.0f}%", h["status"], h["note"], h["submitted_at"][:10]] for _, p, h in pts],
            hovertemplate=("<b>%{customdata[0]}</b><br>%{customdata[1]}<br>Actual: %{customdata[2]}"
                           "<br>% of target: %{customdata[3]}<br>Status: %{customdata[4]}"
                           "<br>%{customdata[5]}<br>Submitted: %{customdata[6]}<extra></extra>"),
            legendgroup=gid, showlegend=False))
        # ring + label on the first accomplished semester
        if o["achieved_in"]:
            ai = cycle_index(project, o["achieved_in"])
            ap = next(p for i, p, _ in pts if i == ai)
            fig.add_trace(go.Scatter(
                x=[cyc_short[ai]], y=[ap], mode="markers+text",
                marker=dict(symbol="circle-open", size=24, color=NAVY, line=dict(color=NAVY, width=2.5)),
                text=[f"Achieved {cyc_short[ai]}"], textposition="top center" if n % 2 == 0 else "bottom center",
                textfont=dict(size=11, color=NAVY), hoverinfo="skip", legendgroup=gid, showlegend=False))

    # target line, selected-semester guide, shaded semesters that have not been reached yet
    fig.add_hline(y=100, line_dash="dash", line_color=NAVY, line_width=1.5,
                  annotation_text="Target (100%)", annotation_position="top right",
                  annotation_font=dict(size=11, color=NAVY))
    fig.add_shape(type="line", xref="x", yref="paper", x0=sel_idx, x1=sel_idx, y0=0, y1=1,
                  line=dict(color=BLUE, width=1, dash="dot"))
    if sel_idx < len(cycles) - 1:
        fig.add_shape(type="rect", xref="x", yref="paper", x0=sel_idx + 0.5, x1=len(cycles) - 0.5,
                      y0=0, y1=1, fillcolor="#EEF1F6", opacity=0.8, line_width=0, layer="below")

    y_top = max(150, math.ceil(max(all_pcts) / 25) * 25)   # never capped: axis grows to fit
    fig.update_layout(
        height=470, margin=dict(l=10, r=10, t=15, b=10),
        plot_bgcolor="white", paper_bgcolor="white",
        font=dict(family="Inter, sans-serif", color=NAVY),
        yaxis=dict(title="% of target achieved", range=[0, y_top + 15], gridcolor="#EEF1F6",
                   ticksuffix="%", zeroline=False),
        xaxis=dict(type="category", categoryorder="array", categoryarray=cyc_short,
                   tickmode="array", tickvals=cyc_short,
                   ticktext=[f"<b>{c} (selected)</b>" if i == sel_idx else c for i, c in enumerate(cyc_short)],
                   range=[-0.5, len(cyc_short) - 0.5], gridcolor="#EEF1F6"),
        legend=dict(orientation="h", yanchor="top", y=-0.12, x=0),
        hovermode="closest",
    )
    try:
        event = st.plotly_chart(fig, use_container_width=True, on_select="rerun",
                                selection_mode="points", key="impact_trend")
    except TypeError:   # older Streamlit without chart selection events
        st.plotly_chart(fig, use_container_width=True)
        event = None
    st.caption("Solid line = consecutive semesters · dashed line = a semester in between had no submission · "
               "shaded area = semesters after the selected one.")

    if event is not None:
        try:
            pts_sel = event["selection"]["points"]
            if pts_sel and pts_sel[0].get("customdata"):
                focus_name = pts_sel[0]["customdata"][0]
        except (KeyError, TypeError, IndexError):
            pass

    # Achievement summary — the answer to "when was it achieved?" without hovering
    rows_html = "".join(
        '<div style="display:flex;justify-content:space-between;gap:12px;font-size:0.85rem;'
        'padding:7px 0;border-bottom:1px solid #EEF1F6;">'
        f'<span style="color:#4B5A7A;">{o["name"]}</span>'
        + (f'<span style="font-weight:700;color:{STATUS_COLORS["Accomplished"]};white-space:nowrap;">'
           f'✓ Achieved in {short_cycle(o["achieved_in"])}</span>' if o["achieved_in"]
           else '<span style="font-weight:600;color:#8B95A8;white-space:nowrap;">Not yet achieved</span>')
        + '</div>'
        for o in chart_outputs)
    render_html(f'<div class="card"><span class="obj-card-sub">Achievement summary</span>{rows_html}</div>')

    if focus_name:
        focus = next((o for o in outputs if o["name"] == focus_name), None)
        if focus:
            render_html(f'<div class="card" style="margin-bottom:6px;"><span class="obj-card-sub">'
                        f'History — selected point</span><div class="obj-card-title">{focus["name"]}</div></div>')
            render_history(project, focus, eval_cycle)
else:
    st.info("No outputs with submissions match the current status filter.")

st.write("")

# Detail cards, two per row
for i in range(0, len(filtered_outputs), 2):
    cols = st.columns(2)
    for col, o in zip(cols, filtered_outputs[i:i + 2]):
        has_value = o["target"] and o["actual"] is not None
        pct = min(100, round(o["actual"] / o["target"] * 100)) if has_value else 0
        if o["achieved_in"]:
            achieved_html = (f'<span style="font-size:0.8rem;font-weight:700;color:{STATUS_COLORS["Accomplished"]};">'
                             f'✓ Achieved in {short_cycle(o["achieved_in"])}</span>')
        else:
            achieved_html = '<span style="font-size:0.8rem;font-weight:600;color:#8B95A8;">Not yet achieved</span>'
        actual_label = f"Actual ({short_cycle(o['reported_in'])})" if o["carried_forward"] else "Actual"
        carry_html = (f'<div class="note-text" style="margin-top:6px;font-size:0.78rem;">'
                      f'Last reported in {short_cycle(o["reported_in"])}</div>') if o["carried_forward"] else ""
        n_sub = len([h for h in output_series(project, o, eval_cycle)])
        with col:
            render_html(f"""
                <div class="card" style="margin-bottom:6px;">
                    <div class="ring-wrap">
                        {ring_html(pct, o['status'])}
                        <div style="flex:1;">
                            <span class="obj-card-sub">Quantifiable</span>
                            <div class="obj-card-title">{o['name']}</div>
                        </div>
                    </div>
                    <div style="display:flex;justify-content:space-between;font-size:0.85rem;color:#4B5A7A;margin-top:10px;">
                        <span>Target</span><span style="font-weight:600;color:{NAVY};">{fmt_value(o['target'], o['unit'])}</span>
                    </div>
                    <div style="display:flex;justify-content:space-between;font-size:0.85rem;color:#4B5A7A;">
                        <span>{actual_label}</span><span style="font-weight:600;color:{NAVY};">{fmt_value(o['actual'], o['unit'])}</span>
                    </div>
                    <div style="margin-top:10px;display:flex;flex-wrap:wrap;align-items:center;gap:10px;">
                        {badge_html(o['status'])}{achieved_html}
                    </div>
                    {carry_html}
                    <div class="note-text">{o['note']}</div>
                </div>
                """)
            with st.expander(f"View history ({n_sub} submission{'s' if n_sub != 1 else ''})"):
                render_history(project, o, eval_cycle)
    st.write("")

# Non-quantifiable outputs
if project.get("non_quantifiable"):
    section_header("📝", "Non-Quantifiable Outputs")
    nq_filtered = [n for n in project["non_quantifiable"] if n["status"] in status_filter]
    if nq_filtered:
        cols = st.columns(2)
        for idx, n in enumerate(nq_filtered):
            with cols[idx % 2]:
                render_html(f"""
                    <div class="card">
                        <span class="obj-card-sub">Non-Quantifiable</span>
                        <div class="obj-card-title">{n['name']}</div>
                        <div class="note-text"><b>Actual accomplishment:</b> {n['note']}</div>
                        <div style="margin-top:10px;">{badge_html(n['status'])}</div>
                    </div>
                    """)
    else:
        st.info("No non-quantifiable outputs match the current status filter.")

st.markdown("---")


# --------------------------------------------------------------------------------------
# MIDDLE — SPECIFIC OBJECTIVES FROM PP (COMPARATIVE)
# --------------------------------------------------------------------------------------

section_header("🎯", "Specific Objectives — Pre-PIS vs Semestral vs Annual PIS",
               "Each row is one project objective, tracked at three checkpoints")

objs = [o for o in project["specific_objectives"]
        if o["semestral"]["status"] in status_filter or o["annual"]["status"] in status_filter]

if objs:
    rows = []
    for o in objs:
        rows.append({
            "#": o["id"],
            "Specific Objective": o["text"],
            "Pre-PIS Target": o["pre_pis_target"],
            "Semestral Status": f"{STATUS_ICON[o['semestral']['status']]} {o['semestral']['status']} ({o['semestral']['progress']}%)",
            "Annual PIS Status": f"{STATUS_ICON[o['annual']['status']]} {o['annual']['status']} ({o['annual']['progress']}%)",
        })
    df_obj = pd.DataFrame(rows)

    def highlight_status(val):
        for status, color in STATUS_COLORS.items():
            if status in val:
                bg = STATUS_BG[status]
                return f"background-color:{bg};color:{color};font-weight:600;"
        return ""

    styler = df_obj.style
    # pandas >= 2.1 renamed Styler.applymap -> Styler.map (applymap was
    # removed entirely in pandas 3.0, which is what caused the AttributeError).
    style_fn = styler.map if hasattr(styler, "map") else styler.applymap
    styled = style_fn(highlight_status, subset=["Semestral Status", "Annual PIS Status"])
    st.dataframe(styled, use_container_width=True, hide_index=True, row_height=44,
                 column_config={"#": st.column_config.NumberColumn(width="small")})
else:
    st.info("No objectives match the current status filter.")

st.markdown("---")


# --------------------------------------------------------------------------------------
# BOTTOM — PROGRESS CHECK / PIS MODULE PROGRESSION
# --------------------------------------------------------------------------------------

section_header("🔄", "Progress Check — PIS Module Progression",
               "Year-over-year pairwise comparisons, plus the full Pre-PIS → PIS-n trajectory")

periods = project["periods"]
financials = project["financials"]

view_mode = st.radio("View", ["Pairwise (Year-over-Year)", "Longitudinal (full trajectory)"],
                      horizontal=True, label_visibility="collapsed")

metric_options = list(financials.keys())

if view_mode == "Pairwise (Year-over-Year)":
    # Auto-generates one pair per consecutive checkpoint, however many PIS
    # cycles exist: Y1 = Pre-PIS vs PIS 1, Y2 = PIS 1 vs PIS 2, Y3 = PIS 2 vs
    # PIS 3, and so on — no hardcoded cap on the number of years.
    pair_labels = [
        (f"Year {i}", periods[i - 1], periods[i]) for i in range(1, len(periods))
    ]
    year_choice = st.selectbox("Comparison pair", [p[0] for p in pair_labels])
    _, base_period, comp_period = next(p for p in pair_labels if p[0] == year_choice)
    st.caption(f"📊 Comparing key financial/employment metrics between **{base_period}** and **{comp_period}**.")

    metric_cols = st.columns(len(metric_options))
    for col, metric in zip(metric_cols, metric_options):
        base_val = financials[metric].get(base_period)
        comp_val = financials[metric].get(comp_period)
        change = pct_change(base_val, comp_val)
        display_val = peso(comp_val) if metric != "Employment" else (f"{comp_val:,.0f}" if comp_val is not None else "—")
        delta = f"{change:+.1f}%" if change is not None else "not yet reported"
        col.metric(metric, display_val, delta)

    palette = [NAVY, BLUE, LIGHT_BLUE]
    fig2 = go.Figure()
    for i, metric in enumerate(metric_options):
        b = financials[metric].get(base_period)
        c = financials[metric].get(comp_period)
        if b is None and c is None:
            continue
        fig2.add_trace(go.Bar(name=metric, x=[base_period, comp_period], y=[b or 0, c or 0],
                               marker=dict(color=palette[i % len(palette)])))
    fig2.update_layout(
        barmode="group", height=380, margin=dict(l=10, r=10, t=30, b=10),
        title=f"{base_period} vs {comp_period}", plot_bgcolor="white", paper_bgcolor="white",
        font=dict(family="Inter, sans-serif", color=NAVY),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        yaxis=dict(gridcolor="#EEF1F6"),
    )
    st.plotly_chart(fig2, use_container_width=True)

else:
    metric_choice = st.selectbox("Metric", metric_options)
    st.caption(f"📈 **{metric_choice}** tracked across every checkpoint, from Pre-PIS through PIS 3.")
    series = financials[metric_choice]
    xs = [p for p in periods if series.get(p) is not None]
    ys = [series[p] for p in xs]

    fig3 = go.Figure()
    fig3.add_trace(go.Scatter(
        x=periods, y=[series.get(p) for p in periods],
        mode="lines+markers", connectgaps=True,
        line=dict(color=BLUE, width=3, shape="spline"), marker=dict(size=9, color=NAVY),
        fill="tozeroy", fillcolor="rgba(47,111,237,0.12)",
        name=metric_choice,
    ))
    fig3.update_layout(
        height=380, margin=dict(l=10, r=10, t=30, b=10),
        title=f"{metric_choice} — full trajectory (Pre-PIS → PIS 3)",
        plot_bgcolor="white", paper_bgcolor="white", yaxis_title=metric_choice,
        font=dict(family="Inter, sans-serif", color=NAVY),
        yaxis=dict(gridcolor="#EEF1F6"), xaxis=dict(gridcolor="#EEF1F6"),
    )
    st.plotly_chart(fig3, use_container_width=True)

    if len(xs) >= 2:
        overall_change = pct_change(ys[0], ys[-1])
        st.caption(f"Change from {xs[0]} to {xs[-1]}: "
                   f"{'+' if overall_change and overall_change > 0 else ''}{overall_change}%"
                   if overall_change is not None else "Insufficient data to compute overall change.")

# Asset breakdown table (kept from original design, tied to selected project)
with st.expander("Asset breakdown (Pre-PIS vs Current)"):
    ab = project["asset_breakdown"]
    df_assets = pd.DataFrame({
        "Metric": ab["metric"],
        "Pre-PIS": [peso(v) for v in ab["pre_pis"]],
        "Current": [peso(v) for v in ab["current"]],
        "Chg": [f"{pct_change(a, b):+.0f}%" if pct_change(a, b) is not None else "+0%"
                for a, b in zip(ab["pre_pis"], ab["current"])],
    })
    total_row = pd.DataFrame([{
        "Metric": "Total",
        "Pre-PIS": peso(sum(ab["pre_pis"])),
        "Current": peso(sum(ab["current"])),
        "Chg": f"{pct_change(sum(ab['pre_pis']), sum(ab['current'])):+.0f}%",
    }])
    st.dataframe(pd.concat([df_assets, total_row], ignore_index=True), hide_index=True, use_container_width=True)

st.markdown("---")
st.caption("DOST-VI SETUP 4.0 iFund Program · Region VI")
