
import math
import re

import numpy as np
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Flat-Plate Convection Solver",
    page_icon="🌡️",
    layout="wide",
)

st.title("Forced Convection over an Isothermal Flat Plate")
st.caption(
    "Property-table lookup • Reynolds number • Skin friction and drag "
    "• Heat transfer • Correlation-validity checks"
)


# ============================================================
# NUMBER PARSING
# ============================================================

def num(value):
    """Convert ordinary or scientific-notation values to floats."""
    if pd.isna(value):
        return None

    if isinstance(value, (int, float, np.number)):
        result = float(value)
        return result if math.isfinite(result) else None

    s = (
        str(value).strip()
        .replace(",", "")
        .replace("−", "-")
        .replace("–", "-")
        .replace(" ", "")
    )

    s = s.replace("×10", "e").replace("x10", "e").replace("X10", "e")

    try:
        result = float(s)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


# ============================================================
# TEXTBOOK EXCEL PROPERTY TABLE IMPORT
# ============================================================

def read_engine_oil_from_book(file):
    """
    Read the Engine Oil (unused) section from Table 1.

    Expected workbook structure:
    - A row containing Engine Oil (unused)
    - The next row contains newline-separated values in each column
    """

    xls = pd.ExcelFile(file)

    sheet = next(
        (name for name in xls.sheet_names if name.lower() == "table 1"),
        xls.sheet_names[0],
    )

    raw = pd.read_excel(file, sheet_name=sheet, header=None)

    hits = raw.index[
        raw.iloc[:, 0].astype(str).str.contains(
            "Engine Oil", case=False, na=False
        )
    ].tolist()

    if not hits:
        return None

    row_index = hits[0]

    if row_index + 1 >= len(raw):
        return None

    def split_column(value):
        if pd.isna(value):
            return []

        return [
            item.strip()
            for item in str(value).split("\n")
            if item.strip()
        ]

    columns = [
        split_column(raw.iloc[row_index + 1, j])
        for j in range(min(9, raw.shape[1]))
    ]

    names = [
        "Temperature_C",
        "rho_kg_m3",
        "cp_J_kgK",
        "k_W_mK",
        "alpha_m2_s",
        "mu_Pa_s",
        "nu_m2_s",
        "Pr",
        "beta_1_K",
    ]

    parsed = {
        name: [num(value) for value in col]
        for name, col in zip(names, columns)
    }

    if not parsed:
        return None

    # Use the shortest column to avoid misaligning table rows.
    n = min((len(values) for values in parsed.values()), default=0)

    if n == 0:
        return None

    df = pd.DataFrame({
        name: values[:n]
        for name, values in parsed.items()
    })

    required = [
        "Temperature_C",
        "rho_kg_m3",
        "k_W_mK",
        "mu_Pa_s",
    ]

    return (
        df.dropna(subset=required)
        .sort_values("Temperature_C")
        .drop_duplicates("Temperature_C")
        .reset_index(drop=True)
    )


# ============================================================
# CSV / ORDINARY EXCEL TABLE IMPORT
# ============================================================

def normalize_tidy(df):
    """Map common column headings to the solver's standard names."""

    aliases = {
        "Temperature_C": [
            "temperature_c", "temperature", "temp_c", "t_c", "temp"
        ],
        "rho_kg_m3": [
            "rho_kg_m3", "density_kg_m3", "density", "rho"
        ],
        "mu_Pa_s": [
            "mu_pa_s", "dynamic_viscosity_pa_s",
            "dynamic_viscosity", "viscosity", "mu"
        ],
        "k_W_mK": [
            "k_w_mk", "thermal_conductivity_w_mk",
            "thermal_conductivity", "conductivity", "k"
        ],
        "cp_J_kgK": [
            "cp_j_kgk", "specific_heat_j_kgk",
            "specific_heat", "cp"
        ],
        "Pr": ["pr", "prandtl", "prandtl_number"],
        "nu_m2_s": [
            "nu_m2_s", "kinematic_viscosity_m2_s",
            "kinematic_viscosity", "nu"
        ],
        "alpha_m2_s": [
            "alpha_m2_s", "thermal_diffusivity_m2_s",
            "thermal_diffusivity", "alpha"
        ],
    }

    lookup = {
        str(column).strip().lower().replace(" ", "_"): column
        for column in df.columns
    }

    output = pd.DataFrame()

    for target, possible_names in aliases.items():
        source = next(
            (lookup[name] for name in possible_names if name in lookup),
            None,
        )

        if source is not None:
            output[target] = df[source].map(num)

    required = {
        "Temperature_C",
        "rho_kg_m3",
        "mu_Pa_s",
        "k_W_mK",
    }

    if not required.issubset(output.columns):
        raise ValueError(
            "The table must contain temperature, density, dynamic "
            "viscosity, and thermal conductivity. Optional columns: "
            "specific heat cp, Prandtl number Pr, kinematic viscosity "
            "nu, and thermal diffusivity alpha."
        )

    return (
        output.dropna(subset=list(required))
        .sort_values("Temperature_C")
        .drop_duplicates("Temperature_C")
        .reset_index(drop=True)
    )


# ============================================================
# PROPERTY INTERPOLATION
# ============================================================

def interp_props(df, temperature):
    """
    Linearly interpolate available properties.
    Extrapolation beyond the table range is prohibited.
    """

    minimum = df["Temperature_C"].min()
    maximum = df["Temperature_C"].max()

    if temperature < minimum or temperature > maximum:
        raise ValueError(
            f"Film temperature {temperature:.2f} °C is outside "
            f"the table range ({minimum:g} to {maximum:g} °C). "
            "Extrapolation is disabled."
        )

    props = {}

    for column in df.columns:
        if column == "Temperature_C":
            continue

        valid = (
            df[["Temperature_C", column]]
            .dropna()
            .drop_duplicates("Temperature_C")
            .sort_values("Temperature_C")
        )

        if len(valid) == 0:
            continue

        if len(valid) == 1:
            props[column] = float(valid[column].iloc[0])
        else:
            props[column] = float(
                np.interp(
                    temperature,
                    valid["Temperature_C"],
                    valid[column],
                )
            )

    rho = props["rho_kg_m3"]
    mu = props["mu_Pa_s"]
    k = props["k_W_mK"]

    if rho <= 0 or mu <= 0 or k <= 0:
        raise ValueError(
            "Density, viscosity, and thermal conductivity must be positive."
        )

    if not props.get("nu_m2_s") or props["nu_m2_s"] <= 0:
        props["nu_m2_s"] = mu / rho

    if not props.get("Pr") or props["Pr"] <= 0:
        cp = props.get("cp_J_kgK")

        if cp is not None and cp > 0:
            props["Pr"] = cp * mu / k

    if not props.get("alpha_m2_s") or props["alpha_m2_s"] <= 0:
        cp = props.get("cp_J_kgK")

        if cp is not None and cp > 0:
            props["alpha_m2_s"] = k / (rho * cp)

    if not props.get("Pr") or props["Pr"] <= 0:
        alpha = props.get("alpha_m2_s")

        if alpha is not None and alpha > 0:
            props["Pr"] = props["nu_m2_s"] / alpha

    if not props.get("Pr") or props["Pr"] <= 0:
        raise ValueError(
            "A valid Prandtl number could not be obtained. "
            "Include Pr, or provide specific heat cp or diffusivity alpha."
        )

    return props


# ============================================================
# CORRELATION VALIDITY CHECKS
# ============================================================

def check_correlation_validity(Re, Pr, regime):
    """
    Screening checks for common flat-plate correlations.

    These are practical warnings, not a replacement for the
    applicability limits in the original correlation reference.
    """

    warnings = []

    if Re <= 0:
        warnings.append("Reynolds number must be positive.")
        return warnings

    if Pr <= 0:
        warnings.append("Prandtl number must be positive.")
        return warnings

    if Pr < 0.6 or Pr > 60:
        warnings.append(
            f"Pr = {Pr:.4g} is outside the common screening range "
            "0.6–60 for the selected basic flat-plate heat-transfer "
            "correlations. Verify a correlation suitable for this fluid."
        )

    if Re > 1e7:
        warnings.append(
            f"Re = {Re:.4g} is very high. Check the applicable "
            "Reynolds-number range and assumptions of the selected correlation."
        )

    if regime == "Laminar over plate" and Re > 5e5:
        warnings.append(
            "The flow is labelled laminar even though Reynolds number "
            "exceeds the usual approximate flat-plate transition value."
        )

    if regime == "Mixed laminar–turbulent boundary layer" and Re < 5e5:
        warnings.append(
            "The mixed-flow correlation is being used below the usual "
            "approximate transition Reynolds number."
        )

    return warnings


# ============================================================
# SIDEBAR INPUTS
# ============================================================

with st.sidebar:
    st.header("1. Property data")

    upload = st.file_uploader(
        "Upload property table (.xlsx or .csv)",
        type=["xlsx", "xls", "csv"],
    )

    st.caption(
        "For the textbook workbook, the app searches Table 1 for "
        "'Engine Oil (unused)'. Other files should contain one row "
        "per temperature."
    )

    st.header("2. Flow and plate")

    U = st.number_input(
        "Free-stream velocity, U (m/s)",
        min_value=0.001,
        value=2.0,
        step=0.1,
    )

    L = st.number_input(
        "Plate length, L (m)",
        min_value=0.001,
        value=5.0,
        step=0.5,
    )

    width = st.number_input(
        "Plate width, b (m)",
        min_value=0.001,
        value=1.0,
        step=0.5,
    )

    Tinf = st.number_input(
        "Fluid free-stream temperature (°C)",
        value=60.0,
        step=1.0,
    )

    Ts = st.number_input(
        "Plate surface temperature (°C)",
        value=20.0,
        step=1.0,
    )

    Recrit = st.number_input(
        "Transition Reynolds number",
        min_value=10000.0,
        value=500000.0,
        step=50000.0,
        format="%.0f",
    )

    both_sides = st.checkbox(
        "Both plate sides exposed",
        value=False,
    )


# ============================================================
# PROBLEM SETUP
# ============================================================

film = (Tinf + Ts) / 2

st.subheader("Problem setup")

c1, c2, c3 = st.columns(3)

c1.metric("Film temperature", f"{film:.2f} °C")
c2.metric("Temperature difference", f"{abs(Tinf - Ts):.2f} K")
c3.metric("Plate area (one side)", f"{L * width:.3f} m²")


# ============================================================
# LOAD PROPERTY DATA
# ============================================================

props_df = None
source = ""

if upload is not None:
    try:
        if upload.name.lower().endswith(".csv"):
            raw = pd.read_csv(upload)
            props_df = normalize_tidy(raw)
            source = f"Uploaded CSV: {upload.name}"

        else:
            try:
                props_df = read_engine_oil_from_book(upload)
            except Exception:
                props_df = None

            if props_df is not None:
                source = (
                    f"{upload.name} → Table A–13 → Engine Oil (unused)"
                )
            else:
                raw = pd.read_excel(upload)
                props_df = normalize_tidy(raw)
                source = f"Uploaded Excel table: {upload.name}"

    except Exception as error:
        st.error(f"Could not read the property table: {error}")


if props_df is not None:
    st.success(f"Property data loaded from: {source}")

    with st.expander("Inspect imported property table", expanded=False):
        st.dataframe(
            props_df,
            use_container_width=True,
            hide_index=True,
        )

    try:
        p = interp_props(props_df, film)

        st.caption(
            f"Properties interpolated at {film:.2f} °C. "
            "No extrapolation is performed."
        )

        with st.expander("Fluid properties at film temperature", expanded=True):
            st.write(f"Density: {p['rho_kg_m3']:.5g} kg/m³")
            st.write(f"Dynamic viscosity: {p['mu_Pa_s']:.5g} Pa·s")
            st.write(f"Kinematic viscosity: {p['nu_m2_s']:.5g} m²/s")
            st.write(f"Thermal conductivity: {p['k_W_mK']:.5g} W/(m·K)")
            st.write(f"Prandtl number: {p['Pr']:.5g}")

    except Exception as error:
        st.error(str(error))
        p = None

else:
    p = None
    st.info(
        "Upload the textbook workbook or a tidy CSV/Excel property table "
        "to calculate results. Missing properties are not guessed."
    )


# ============================================================
# CALCULATIONS
# ============================================================

if p is not None and st.button(
    "Calculate drag and heat transfer",
    type="primary",
):
    rho = p["rho_kg_m3"]
    nu = p["nu_m2_s"]
    k = p["k_W_mK"]
    Pr = p["Pr"]

    ReL = U * L / nu
    dT = Tinf - Ts

    exposed_sides = 2 if both_sides else 1
    area_one_side = L * width
    total_area = area_one_side * exposed_sides

    # --------------------------------------------------------
    # FLOW REGIME AND AVERAGE CORRELATIONS
    # --------------------------------------------------------

    if ReL <= Recrit:
        Cf = 1.328 / math.sqrt(ReL)

        Nu = 0.664 * math.sqrt(ReL) * Pr ** (1 / 3)

        regime = "Laminar over plate"
        correlation = "Laminar average correlations"

    else:
        # Mixed laminar-turbulent average flat-plate correlations.
        Cf = 0.074 * ReL ** (-0.2) - 1742 / ReL

        C = 0.037 * Recrit ** 0.8 - 0.664 * math.sqrt(Recrit)

        Nu = (
            0.037 * ReL ** 0.8 - C
        ) * Pr ** (1 / 3)

        regime = "Mixed laminar–turbulent boundary layer"
        correlation = "Mixed-flow average correlations"

    h = Nu * k / L

    # Drag force on all exposed surfaces.
    drag = Cf * 0.5 * rho * U ** 2 * total_area

    # Signed heat transfer: positive when fluid is hotter than plate.
    Q_total = h * area_one_side * dT * exposed_sides

    Q_per_width = Q_total / (width * exposed_sides)

    # --------------------------------------------------------
    # VALIDITY WARNINGS
    # --------------------------------------------------------

    st.subheader("Correlation-validity checks")

    validity_warnings = check_correlation_validity(
        ReL,
        Pr,
        regime,
    )

    if validity_warnings:
        for warning in validity_warnings:
            st.warning(warning)

        st.caption(
            "The warnings are screening checks. Consult the original "
            "correlation source before treating the result as validated."
        )
    else:
        st.success(
            "No warning was triggered by the basic screening checks. "
            "This does not guarantee that every correlation assumption is met."
        )

    # --------------------------------------------------------
    # RESULTS
    # --------------------------------------------------------

    st.subheader("Calculated results")

    a, b, c, d = st.columns(4)

    a.metric("Reynolds number, Reₗ", f"{ReL:,.5g}")
    b.metric("Flow regime", regime)
    c.metric("Total drag force", f"{drag:.5g} N")
    d.metric("Average skin-friction coefficient", f"{Cf:.6g}")

    e, f, g = st.columns(3)

    e.metric("Average Nusselt number", f"{Nu:.5g}")
    f.metric("Average heat-transfer coefficient", f"{h:.5g} W/(m²·K)")
    g.metric("Total heat-transfer rate", f"{Q_total / 1000:.5g} kW")

    st.metric(
        "Heat-transfer rate per unit width",
        f"{Q_per_width / 1000:.5g} kW/m",
    )

    st.caption(
        f"Correlation used: {correlation}. "
        f"Total exposed area: {total_area:.3f} m². "
        f"Drag is calculated for "
        f"{'both sides' if both_sides else 'one side'} of the plate."
    )

    if dT > 0:
        st.info("The fluid is hotter than the plate: heat flows to the plate.")
    elif dT < 0:
        st.info("The plate is hotter than the fluid: heat flows to the fluid.")
    else:
        st.info("There is no temperature difference, so the calculated heat transfer is zero.")

    # --------------------------------------------------------
    # EQUATIONS USED
    # --------------------------------------------------------

    with st.expander("Equations used in the calculation"):
        st.latex(r"Re_L = \frac{UL}{\nu}")

        if ReL <= Recrit:
            st.latex(
                r"\bar C_f = \frac{1.328}{\sqrt{Re_L}}"
            )
            st.latex(
                r"\overline{Nu}_L = 0.664 Re_L^{1/2} Pr^{1/3}"
            )
        else:
            st.latex(
                r"\bar C_f = 0.074 Re_L^{-0.2} - \frac{1742}{Re_L}"
            )
            st.latex(
                r"\overline{Nu}_L = "
                r"(0.037 Re_L^{0.8} - C)Pr^{1/3}"
            )
            st.latex(
                r"C = 0.037 Re_{\mathrm{crit}}^{0.8}"
                r"- 0.664 Re_{\mathrm{crit}}^{1/2}"
            )

        st.latex(
            r"\bar h = \frac{\overline{Nu}_L k}{L}"
        )
        st.latex(
            r"F_D = \bar C_f \left(\frac{\rho U^2}{2}\right) A"
        )
        st.latex(
            r"\dot Q = \bar h A (T_\infty - T_s)"
        )
        st.latex(
            r"\frac{\dot Q}{b} = \bar h L (T_\infty - T_s)"
        )

    # --------------------------------------------------------
    # LOCAL HEAT-TRANSFER COEFFICIENT PROFILE
    # --------------------------------------------------------

    st.subheader("Local heat-transfer coefficient along the plate")

    xs = np.linspace(L / 500, L, 500)

    local_h = []
    local_Re = []

    xcrit = Recrit * nu / U

    for x in xs:
        Rex = U * x / nu
        local_Re.append(Rex)

        if Rex <= Recrit:
            Nux = 0.332 * math.sqrt(Rex) * Pr ** (1 / 3)
        else:
            Nux = 0.0296 * Rex ** 0.8 * Pr ** (1 / 3)

        local_h.append(Nux * k / x)

    fig, ax = plt.subplots()

    ax.plot(xs, local_h, label="Local heat-transfer coefficient")

    if 0 < xcrit < L:
        ax.axvline(
            xcrit,
            linestyle="--",
            label=f"Transition estimate x = {xcrit:.3g} m",
        )

    ax.set_xlabel("Distance from leading edge, x (m)")
    ax.set_ylabel("Local heat-transfer coefficient, hₓ (W/m²·K)")
    ax.set_title("Local heat-transfer coefficient along the plate")
    ax.grid(True, alpha=0.3)
    ax.legend()

    st.pyplot(fig)
    plt.close(fig)

    profile = pd.DataFrame({
        "x_m": xs,
        "Re_x": local_Re,
        "h_local_W_m2K": local_h,
    })

    st.download_button(
        "Download local profile CSV",
        data=profile.to_csv(index=False).encode("utf-8"),
        file_name="flat_plate_local_profile.csv",
        mime="text/csv",
    )

    # --------------------------------------------------------
    # DOWNLOAD SUMMARY RESULTS
    # --------------------------------------------------------

    summary = pd.DataFrame([{
        "film_temperature_C": film,
        "temperature_difference_K": dT,
        "density_kg_m3": rho,
        "kinematic_viscosity_m2_s": nu,
        "thermal_conductivity_W_mK": k,
        "Prandtl_number": Pr,
        "velocity_m_s": U,
        "plate_length_m": L,
        "plate_width_m": width,
        "exposed_sides": exposed_sides,
        "total_area_m2": total_area,
        "Reynolds_number": ReL,
        "flow_regime": regime,
        "skin_friction_coefficient": Cf,
        "drag_force_N": drag,
        "average_Nusselt_number": Nu,
        "average_h_W_m2K": h,
        "heat_transfer_W": Q_total,
        "heat_transfer_per_width_W_m": Q_per_width,
        "correlation": correlation,
        "validity_warnings": " | ".join(validity_warnings),
    }])

    st.download_button(
        "Download calculation results CSV",
        data=summary.to_csv(index=False).encode("utf-8"),
        file_name="flat_plate_results.csv",
        mime="text/csv",
    )

