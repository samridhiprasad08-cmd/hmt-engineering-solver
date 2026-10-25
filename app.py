import streamlit as st
import runpy
from pathlib import Path
from io import BytesIO

import matplotlib.pyplot as plt

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import (
    getSampleStyleSheet,
    ParagraphStyle,
)
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image as PDFImage,
    PageBreak,
)


# =========================================================
# GRAPH GENERATION
# =========================================================

def make_methane_graphs(result):
    """Generate engineering graphs from calculated results."""

    figures = []

    # -----------------------------------------------------
    # GRAPH 1: TERMINAL TEMPERATURE COMPARISON
    # -----------------------------------------------------

    fig, ax = plt.subplots(figsize=(8.2, 4.6))

    x = [0, 1]

    ax.plot(
        x,
        [result["gas_in_T"], result["gas_out_T"]],
        marker="o",
        linewidth=2.6,
        label="Combustion gas",
    )

    ax.plot(
        x,
        [result["water_in_T"], result["water_out_T"]],
        marker="o",
        linewidth=2.6,
        label="Water",
    )

    ax.set_xticks(x, ["Inlet", "Outlet"])
    ax.set_ylabel("Temperature (K)")
    ax.set_title("Heat-exchanger terminal temperatures")

    ax.grid(True, alpha=0.28)
    ax.legend()

    fig.tight_layout()

    figures.append(
        ("Terminal temperature comparison", fig)
    )

    # -----------------------------------------------------
    # GRAPH 2: ENERGY BALANCE
    # -----------------------------------------------------

    fig, ax = plt.subplots(figsize=(8.2, 4.6))

    labels = [
        "Gas-side heat lost",
        "Water-side heat gained",
    ]

    values = [
        result["gas_side_Q_kW"],
        result["water_side_Q_kW"],
    ]

    bars = ax.bar(
        labels,
        values,
        width=0.55,
    )

    ax.set_ylabel("Heat-transfer rate (kW)")
    ax.set_title("Energy-balance check")

    ax.grid(axis="y", alpha=0.28)

    ax.bar_label(
        bars,
        fmt="%.3f kW",
        padding=4,
    )

    fig.tight_layout()

    figures.append(
        ("Energy balance", fig)
    )

    # -----------------------------------------------------
    # GRAPH 3: LMTD TERMINAL TEMPERATURE DIFFERENCES
    # -----------------------------------------------------

    fig, ax = plt.subplots(figsize=(8.2, 4.6))

    labels = [
        "Hot-end ΔT₁",
        "Cold-end ΔT₂",
    ]

    values = [
        result["delta_1"],
        result["delta_2"],
    ]

    bars = ax.bar(
        labels,
        values,
        width=0.55,
    )

    ax.set_ylabel("Temperature difference (K)")

    ax.set_title(
        f"LMTD terminal differences "
        f"(LMTD = {result['LMTD']:.3f} K)"
    )

    ax.grid(axis="y", alpha=0.28)

    ax.bar_label(
        bars,
        fmt="%.2f K",
        padding=4,
    )

    fig.tight_layout()

    figures.append(
        ("LMTD terminal differences", fig)
    )

    return figures


# =========================================================
# PDF REPORT GENERATION
# =========================================================

def make_pdf_report(result, inputs, graphs):
    """Generate a PDF report containing inputs, results and graphs."""

    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.6 * cm,
        leftMargin=1.6 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )

    styles = getSampleStyleSheet()

    styles.add(
        ParagraphStyle(
            name="SubheadBlue",
            parent=styles["Heading2"],
            textColor=colors.HexColor("#1D609F"),
            spaceBefore=10,
        )
    )

    story = [
        Paragraph(
            "HMT Engineering Solver",
            styles["Title"],
        ),
        Paragraph(
            "Methane Combustion & Parallel-Flow Heat Exchanger Report",
            styles["Heading2"],
        ),
        Spacer(1, 10),
        Paragraph(
            "Input conditions",
            styles["SubheadBlue"],
        ),
    ]

    # -----------------------------------------------------
    # INPUT TABLE
    # -----------------------------------------------------

    input_rows = [
        ["Parameter", "Value"]
    ]

    for key, value in inputs.items():
        input_rows.append(
            [str(key), str(value)]
        )

    input_table = Table(
        input_rows,
        colWidths=[8.5 * cm, 8.0 * cm],
        repeatRows=1,
    )

    input_table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor("#DCEEFF"),
                ),
                (
                    "TEXTCOLOR",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor("#19324B"),
                ),
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.4,
                    colors.HexColor("#B8CDE2"),
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP",
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    7,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    7,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
            ]
        )
    )

    story.extend(
        [
            input_table,
            Spacer(1, 12),
            Paragraph(
                "Calculated results",
                styles["SubheadBlue"],
            ),
        ]
    )

    # -----------------------------------------------------
    # RESULTS TABLE
    # -----------------------------------------------------

    result_rows = [
        ["Result", "Value"],
        [
            "Adiabatic flame temperature",
            f"{result['flame_T']:.2f} K",
        ],
        [
            "Heat-transfer rate",
            f"{result['Q_kW']:.3f} kW",
        ],
        [
            "Required heat-transfer area",
            f"{result['area']:.4f} m²",
        ],
        [
            "Gas outlet temperature",
            f"{result['gas_out_T']:.2f} K",
        ],
        [
            "Water outlet temperature",
            (
                f"{result['water_out_T']:.2f} K "
                f"({result['water_out_C']:.2f} °C)"
            ),
        ],
        [
            "LMTD",
            f"{result['LMTD']:.3f} K",
        ],
        [
            "Gas-side heat transfer",
            f"{result['gas_side_Q_kW']:.3f} kW",
        ],
        [
            "Water-side heat transfer",
            f"{result['water_side_Q_kW']:.3f} kW",
        ],
        [
            "Energy-balance difference",
            f"{result['energy_balance_difference_kW']:.4f} kW",
        ],
        [
            "Water phase",
            str(result["water_phase"]),
        ],
    ]

    result_table = Table(
        result_rows,
        colWidths=[8.5 * cm, 8.0 * cm],
        repeatRows=1,
    )

    result_table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor("#DCEEFF"),
                ),
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.4,
                    colors.HexColor("#B8CDE2"),
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP",
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    7,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
            ]
        )
    )

    story.extend(
        [
            result_table,
            PageBreak(),
            Paragraph(
                "Graphs",
                styles["Title"],
            ),
        ]
    )

    # -----------------------------------------------------
    # ADD GRAPHS TO PDF
    # -----------------------------------------------------

    for graph_title, fig in graphs:

        image_buffer = BytesIO()

        fig.savefig(
            image_buffer,
            format="png",
            dpi=160,
            bbox_inches="tight",
        )

        image_buffer.seek(0)

        story.extend(
            [
                Paragraph(
                    graph_title,
                    styles["Heading2"],
                ),
                PDFImage(
                    image_buffer,
                    width=16.5 * cm,
                    height=9.0 * cm,
                ),
                Spacer(1, 8),
            ]
        )

    doc.build(story)

    buffer.seek(0)

    return buffer.getvalue()


# =========================================================
# STREAMLIT PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="HMT Engineering Solver",
    page_icon="🌡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

BASE_DIR = Path(__file__).resolve().parent


# =========================================================
# LIGHT BLUE AND WHITE THEME
# =========================================================


# =========================================================
# LIGHT BLUE AND WHITE THEME — GLOBAL CONTRAST FIX
# =========================================================

st.markdown(
    """
    <style>
    /* Main page */
    .stApp,
    [data-testid="stAppViewContainer"],
    [data-testid="stMain"] {
        background-color: #F4F8FF !important;
        color: #19324B !important;
    }

    [data-testid="stMain"] .block-container {
        color: #19324B !important;
    }

    /* Sidebar */
    [data-testid="stSidebar"],
    [data-testid="stSidebar"] > div {
        background-color: #E5F0FF !important;
        color: #19324B !important;
    }

    /* All ordinary text */
    .stApp p,
    .stApp label,
    .stApp li,
    .stApp span,
    .stApp .stMarkdown,
    .stApp [data-testid="stCaptionContainer"],
    .stApp [data-testid="stHeader"],
    .stApp h1,
    .stApp h2,
    .stApp h3,
    .stApp h4,
    .stApp h5,
    .stApp h6 {
        color: #19324B;
    }

    /* Markdown links */
    .stApp a {
        color: #155DA8 !important;
    }

    /* Primary and ordinary buttons */
    .stApp div.stButton > button,
    .stApp div.stDownloadButton > button,
    .stApp [data-testid="stBaseButton-primary"],
    .stApp [data-testid="stBaseButton-secondary"],
    .stApp [data-testid="stDownloadButton"] button {
        background-color: #2878C8 !important;
        color: #FFFFFF !important;
        border: 1px solid #2878C8 !important;
        border-radius: 9px !important;
        font-weight: 600 !important;
        opacity: 1 !important;
    }

    .stApp div.stButton > button *,
    .stApp div.stDownloadButton > button *,
    .stApp [data-testid="stBaseButton-primary"] *,
    .stApp [data-testid="stBaseButton-secondary"] *,
    .stApp [data-testid="stDownloadButton"] button * {
        color: #FFFFFF !important;
        fill: #FFFFFF !important;
    }

    .stApp div.stButton > button:hover,
    .stApp div.stDownloadButton > button:hover,
    .stApp [data-testid="stBaseButton-primary"]:hover,
    .stApp [data-testid="stBaseButton-secondary"]:hover,
    .stApp [data-testid="stDownloadButton"] button:hover {
        background-color: #155DA8 !important;
        color: #FFFFFF !important;
        border-color: #155DA8 !important;
    }

    /* Input fields */
    .stApp input,
    .stApp textarea,
    .stApp [data-baseweb="input"] input,
    .stApp [data-baseweb="textarea"] textarea {
        background-color: #FFFFFF !important;
        color: #19324B !important;
        -webkit-text-fill-color: #19324B !important;
        border-color: #B8CDE2 !important;
    }

    /* Number inputs and input containers */
    .stApp [data-baseweb="input"],
    .stApp [data-baseweb="textarea"] {
        background-color: #FFFFFF !important;
    }

    /* Dropdowns and selected values */
    .stApp [data-baseweb="select"] > div {
        background-color: #FFFFFF !important;
        color: #19324B !important;
        border-color: #B8CDE2 !important;
    }

    .stApp [data-baseweb="select"] *,
    .stApp [role="listbox"],
    .stApp [role="option"] {
        color: #19324B !important;
    }

    /* Dropdown menu */
    [data-baseweb="popover"],
    [data-baseweb="menu"] {
        background-color: #FFFFFF !important;
    }

    /* Radio buttons, checkboxes and sliders */
    .stApp [data-testid="stRadio"],
    .stApp [data-testid="stCheckbox"],
    .stApp [data-testid="stSlider"] {
        color: #19324B !important;
    }

    /* Expanders */
    .stApp [data-testid="stExpander"] {
        background-color: #FFFFFF !important;
        border: 1px solid #D5E5F7 !important;
        border-radius: 10px !important;
        overflow: hidden;
    }

    .stApp [data-testid="stExpander"] summary,
    .stApp [data-testid="stExpander"] summary p,
    .stApp [data-testid="stExpander"] summary span {
        background-color: #FFFFFF !important;
        color: #19324B !important;
    }

    .stApp [data-testid="stExpander"] details,
    .stApp [data-testid="stExpander"] details > div {
        background-color: #FFFFFF !important;
        color: #19324B !important;
    }

    /* Metric cards */
    .stApp [data-testid="stMetric"] {
        background-color: #FFFFFF !important;
        color: #19324B !important;
        border: 1px solid #D5E5F7 !important;
        border-radius: 12px !important;
        padding: 14px !important;
    }

    .stApp [data-testid="stMetric"] label,
    .stApp [data-testid="stMetric"] [data-testid="stMetricValue"],
    .stApp [data-testid="stMetric"] [data-testid="stMetricLabel"],
    .stApp [data-testid="stMetric"] [data-testid="stMetricDelta"] {
        color: #19324B !important;
        -webkit-text-fill-color: #19324B !important;
    }

    /* Tables and dataframes */
    .stApp [data-testid="stTable"],
    .stApp [data-testid="stDataFrame"] {
        background-color: #FFFFFF !important;
        color: #19324B !important;
    }

    /* Status messages */
    .stApp [data-testid="stAlert"] {
        color: #19324B !important;
    }

    /* Hero banner */
    .hero {
        background: linear-gradient(120deg, #DCEEFF, #FFFFFF);
        border: 1px solid #CFE2F6;
        border-radius: 18px;
        padding: 28px;
        margin-bottom: 24px;
    }

    .hero h1 {
        color: #19324B !important;
        margin: 0 0 10px 0;
        font-size: 2.2rem;
    }

    .hero p {
        color: #334F69 !important;
        margin: 0;
        font-size: 1.05rem;
    }

    /* Homepage solver cards */
    .solver-card {
        background-color: #FFFFFF !important;
        color: #19324B !important;
        border: 1px solid #D5E5F7;
        border-radius: 16px;
        padding: 24px;
        min-height: 220px;
        box-shadow: 0 3px 12px rgba(35, 85, 130, 0.06);
    }

    .solver-card h3 {
        color: #19324B !important;
        margin-top: 12px;
    }

    .solver-card p {
        color: #334F69 !important;
        line-height: 1.6;
    }

    /* Dividers */
    .stApp hr {
        border-color: #D5E5F7 !important;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# SESSION STATE
# =========================================================

if "solver_choice" not in st.session_state:
    st.session_state["solver_choice"] = "Home"

if "pending_solver_choice" in st.session_state:
    st.session_state["solver_choice"] = (
        st.session_state.pop("pending_solver_choice")
    )


# =========================================================
# SIDEBAR NAVIGATION
# =========================================================

st.sidebar.markdown("## 🌡️ HMT Solver")

st.sidebar.caption(
    "Heat & Mass Transfer Engineering"
)

st.sidebar.divider()

choice = st.sidebar.radio(
    "Choose a problem",
    [
        "Home",
        "Methane Heat Exchanger",
        "Forced Convection",
    ],
    key="solver_choice",
)

st.sidebar.divider()

st.sidebar.caption(
    "Light blue · White · Dark text"
)


# =========================================================
# HOMEPAGE
# =========================================================

if choice == "Home":

    st.markdown(
        """
        <div class="hero">
            <h1>HMT Engineering Solver</h1>
            <p>
                One workspace for combustion, heat exchangers,
                and forced-convection engineering problems.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        "## Choose a problem to solve"
    )

    col1, col2 = st.columns(
        2,
        gap="large",
    )

    # -----------------------------------------------------
    # METHANE SOLVER CARD
    # -----------------------------------------------------

    with col1:

        st.markdown(
            """
            <div class="solver-card">
                <div style="font-size: 2.8rem;">🔥</div>
                <h3>Methane Combustion &amp; Heat Exchanger</h3>
                <p>
                    Open your existing methane combustion and
                    parallel-flow heat-exchanger solver.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button(
            "Open Methane Heat Exchanger",
            key="open_methane",
            use_container_width=True,
        ):

            st.session_state["pending_solver_choice"] = (
                "Methane Heat Exchanger"
            )

            st.rerun()

    # -----------------------------------------------------
    # FORCED CONVECTION CARD
    # -----------------------------------------------------

    with col2:

        st.markdown(
            """
            <div class="solver-card">
                <div style="font-size: 2.8rem;">🌬️</div>
                <h3>Forced Convection over a Flat Plate</h3>
                <p>
                    Open your existing forced-convection solver
                    for flow, drag, and heat-transfer calculations.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button(
            "Open Forced Convection",
            key="open_convection",
            use_container_width=True,
        ):

            st.session_state["pending_solver_choice"] = (
                "Forced Convection"
            )

            st.rerun()

    st.divider()

    st.caption(
        "Select a solver from the sidebar or use the buttons above."
    )


# =========================================================
# FORCED CONVECTION SOLVER
# =========================================================

elif choice == "Forced Convection":

    st.title(
        "🌬️ Forced Convection over a Flat Plate"
    )

    convection_file = (
        BASE_DIR / "convection_app.py"
    )

    if not convection_file.exists():

        st.error(
            "convection_app.py was not found in the same folder as app.py."
        )

    else:

        try:

            runpy.run_path(
                str(convection_file),
                run_name="__main__",
            )

        except Exception as exc:

            st.error(
                "The existing convection interface could not be "
                "embedded directly in this app."
            )

            st.code(str(exc))

            st.info(
                "Your original convection_app.py and flat_plate.py "
                "have not been modified. The interface may need "
                "to expose a render function for reliable integration."
            )


# =========================================================
# METHANE COMBUSTION AND HEAT EXCHANGER
# =========================================================

elif choice == "Methane Heat Exchanger":

    st.title(
        "🔥 Methane Combustion & Heat Exchanger"
    )

    st.caption(
        "Complete combustion of methane and parallel-flow "
        "heat-exchanger analysis."
    )

    try:

        from calculations import calculate

        # -------------------------------------------------
        # SECTION 1: COMBUSTION SETTINGS
        # -------------------------------------------------

        st.subheader(
            "1. Combustion settings"
        )

        c1, c2, c3 = st.columns(3)

        with c1:

            air_ratio = st.number_input(
                "Air ratio, λ",
                min_value=1.0,
                value=1.5,
                step=0.1,
            )

            reactant_temperature = st.number_input(
                "Reactant temperature (K)",
                min_value=1.0,
                value=300.0,
            )

        with c2:

            combustion_pressure_bar = st.number_input(
                "Combustion pressure (bar)",
                min_value=0.01,
                value=1.01325,
                format="%.5f",
            )

            gas_mass_flow = st.number_input(
                "Gas mass flow (kg/s)",
                min_value=0.001,
                value=0.20,
            )

        with c3:

            water_mass_flow = st.number_input(
                "Water mass flow (kg/s)",
                min_value=0.001,
                value=0.10,
            )

            water_inlet_temperature = st.number_input(
                "Water inlet temperature (K)",
                min_value=1.0,
                value=300.0,
            )

        # -------------------------------------------------
        # SECTION 2: HEAT EXCHANGER SETTINGS
        # -------------------------------------------------

        st.subheader(
            "2. Heat exchanger settings"
        )

        c1, c2, c3 = st.columns(3)

        with c1:

            water_pressure_bar = st.number_input(
                "Water pressure (bar)",
                min_value=0.01,
                value=2.1,
            )

        with c2:

            overall_U = st.number_input(
                "Overall U (kW/m²·K)",
                min_value=0.0001,
                value=0.100,
                format="%.4f",
            )

        with c3:

            mode = st.selectbox(
                "Calculation mode",
                [
                    "Given gas outlet temperature",
                    "Given water outlet temperature",
                    "Given heat-exchanger area",
                    "Given both outlet temperatures",
                ],
            )

        # Default values for mode-specific inputs.
        gas_outlet_temperature = 665.8
        water_outlet_temperature = 500.0
        specified_area = 5.0

        if mode in [
            "Given gas outlet temperature",
            "Given both outlet temperatures",
        ]:

            gas_outlet_temperature = st.number_input(
                "Gas outlet temperature (K)",
                min_value=1.0,
                value=665.8,
            )

        if mode in [
            "Given water outlet temperature",
            "Given both outlet temperatures",
        ]:

            water_outlet_temperature = st.number_input(
                "Water outlet temperature (K)",
                min_value=1.0,
                value=500.0,
            )

        if mode == "Given heat-exchanger area":

            specified_area = st.number_input(
                "Heat-exchanger area (m²)",
                min_value=0.001,
                value=5.0,
            )

        # -------------------------------------------------
        # SECTION 3: CALCULATION BUTTON
        # -------------------------------------------------

        if st.button(
            "Calculate heat exchanger",
            type="primary",
            use_container_width=True,
        ):

            try:

                result = calculate(
                    mode=mode,
                    air_ratio=air_ratio,
                    combustion_pressure_bar=combustion_pressure_bar,
                    reactant_temperature=reactant_temperature,
                    gas_mass_flow=gas_mass_flow,
                    gas_outlet_temperature=gas_outlet_temperature,
                    water_mass_flow=water_mass_flow,
                    water_inlet_temperature=water_inlet_temperature,
                    water_outlet_temperature=water_outlet_temperature,
                    water_pressure_bar=water_pressure_bar,
                    overall_U=overall_U,
                    specified_area=specified_area,
                )

                # -----------------------------------------
                # STORE RESULTS AND INPUTS
                # -----------------------------------------

                st.session_state["methane_result"] = result

                st.session_state["methane_inputs"] = {
                    "Calculation mode": mode,
                    "Air ratio, λ": air_ratio,
                    "Combustion pressure (bar)": combustion_pressure_bar,
                    "Reactant temperature (K)": reactant_temperature,
                    "Gas mass flow (kg/s)": gas_mass_flow,

                    "Gas outlet temperature input (K)": (
                        gas_outlet_temperature
                        if mode in [
                            "Given gas outlet temperature",
                            "Given both outlet temperatures",
                        ]
                        else "Not specified"
                    ),

                    "Water mass flow (kg/s)": water_mass_flow,
                    "Water inlet temperature (K)": water_inlet_temperature,

                    "Water outlet temperature input (K)": (
                        water_outlet_temperature
                        if mode in [
                            "Given water outlet temperature",
                            "Given both outlet temperatures",
                        ]
                        else "Not specified"
                    ),

                    "Water pressure (bar)": water_pressure_bar,
                    "Overall U (kW/m²·K)": overall_U,

                    "Specified area (m²)": (
                        specified_area
                        if mode == "Given heat-exchanger area"
                        else "Calculated"
                    ),
                }

                st.success(
                    "Calculation completed successfully."
                )

                # -----------------------------------------
                # SECTION 4: MAIN RESULTS
                # -----------------------------------------

                st.subheader(
                    "3. Results"
                )

                c1, c2, c3 = st.columns(3)

                c1.metric(
                    "Adiabatic flame temperature",
                    f"{result['flame_T']:.2f} K",
                )

                c2.metric(
                    "Heat-transfer rate",
                    f"{result['Q_kW']:.3f} kW",
                )

                c3.metric(
                    "Required heat-transfer area",
                    f"{result['area']:.4f} m²",
                )

                c1, c2, c3 = st.columns(3)

                c1.metric(
                    "Gas outlet temperature",
                    f"{result['gas_out_T']:.2f} K",
                )

                c2.metric(
                    "Water outlet temperature",
                    f"{result['water_out_T']:.2f} K",
                )

                c3.metric(
                    "Water outlet temperature",
                    f"{result['water_out_C']:.2f} °C",
                )

                # -----------------------------------------
                # SECTION 5: HEAT-TRANSFER DETAILS
                # -----------------------------------------

                st.subheader(
                    "4. Heat-transfer details"
                )

                c1, c2, c3 = st.columns(3)

                c1.metric(
                    "LMTD",
                    f"{result['LMTD']:.3f} K",
                )

                c2.metric(
                    "Gas-side heat transfer",
                    f"{result['gas_side_Q_kW']:.3f} kW",
                )

                c3.metric(
                    "Water-side heat transfer",
                    f"{result['water_side_Q_kW']:.3f} kW",
                )

                st.write(
                    "**Water phase:**",
                    result["water_phase"],
                )

                st.write(
                    "**Energy-balance difference:** "
                    f"{result['energy_balance_difference_kW']:.4f} kW"
                )

                if (
                    abs(
                        result["energy_balance_difference_kW"]
                    ) > 0.1
                ):

                    st.warning(
                        "The gas-side and water-side heat duties differ. "
                        "Check the specified outlet conditions."
                    )

                # -----------------------------------------
                # SECTION 6: GRAPHS
                # -----------------------------------------

                st.subheader(
                    "5. Graphs"
                )

                graph_items = make_methane_graphs(
                    result
                )

                for graph_title, graph_fig in graph_items:

                    st.markdown(
                        f"**{graph_title}**"
                    )

                    st.pyplot(
                        graph_fig,
                        use_container_width=True,
                    )

                # -----------------------------------------
                # SECTION 7: PDF REPORT
                # -----------------------------------------

                report_bytes = make_pdf_report(
                    result,
                    st.session_state["methane_inputs"],
                    graph_items,
                )

                st.download_button(
                    label="Download complete PDF report",
                    data=report_bytes,
                    file_name="methane_heat_exchanger_report.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )

                # Close figures after displaying and preparing PDF.
                for _, graph_fig in graph_items:
                    plt.close(graph_fig)

                # -----------------------------------------
                # SECTION 8: FULL CALCULATION DATA
                # -----------------------------------------

                with st.expander(
                    "View complete calculation results"
                ):

                    st.json(result)

            except Exception as exc:

                st.error(
                    f"Calculation failed: {exc}"
                )

    except ImportError as exc:

        st.error(
            f"Could not import calculations.py: {exc}"
        )

        st.info(
            "Ensure calculations.py is in the same folder as app.py "
            "and that all required packages are installed."
        )


# =========================================================
# FOOTER
# =========================================================

st.divider()

st.caption(
    "HMT Engineering Solver | Educational engineering workspace"
)