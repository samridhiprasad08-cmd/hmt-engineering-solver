
import math

import cantera as ct
import CoolProp.CoolProp as CP
from scipy.optimize import brentq


# =========================================================
# CONSTANTS
# =========================================================

N2_O2_RATIO = 3.76
WATER = "Water"


# =========================================================
# WATER PROPERTY FUNCTIONS
# =========================================================

def water_enthalpy(T, pressure_bar):
    """Return water specific enthalpy in kJ/kg."""
    pressure_pa = pressure_bar * 1e5
    enthalpy_j_kg = CP.PropsSI(
        "Hmass", "T", T, "P", pressure_pa, WATER
    )
    return enthalpy_j_kg / 1000.0


def water_temperature(enthalpy_kj_kg, pressure_bar):
    """Return water temperature in K from specific enthalpy."""
    pressure_pa = pressure_bar * 1e5
    return CP.PropsSI(
        "T",
        "P", pressure_pa,
        "Hmass", enthalpy_kj_kg * 1000.0,
        WATER,
    )


def water_phase(enthalpy_kj_kg, pressure_bar):
    """Classify water state using saturation enthalpies."""
    pressure_pa = pressure_bar * 1e5

    try:
        h_liquid = CP.PropsSI(
            "Hmass", "P", pressure_pa, "Q", 0, WATER
        ) / 1000.0

        h_vapor = CP.PropsSI(
            "Hmass", "P", pressure_pa, "Q", 1, WATER
        ) / 1000.0

        if enthalpy_kj_kg < h_liquid:
            return "Compressed liquid"
        elif enthalpy_kj_kg <= h_vapor:
            return "Two-phase mixture"
        else:
            return "Superheated steam"

    except Exception:
        return "Single-phase water"


# =========================================================
# COMBUSTION MODEL
# =========================================================

def prepare_combustion(
    air_ratio,
    reactant_temperature,
    combustion_pressure_bar,
):
    """
    Prepare a fixed-composition, complete-combustion model.

    Reaction per kmol of methane:

        CH4 + 2*lambda*O2 + 2*lambda*3.76*N2
        -> CO2 + 2*H2O + 2*(lambda-1)*O2
           + 2*lambda*3.76*N2

    This model does not calculate equilibrium dissociation.
    """

    if air_ratio < 1.0:
        raise ValueError(
            "Air ratio must be at least 1.0 for this "
            "complete-combustion model."
        )

    if reactant_temperature <= 0:
        raise ValueError("Reactant temperature must be positive.")

    if combustion_pressure_bar <= 0:
        raise ValueError("Combustion pressure must be positive.")

    pressure_pa = combustion_pressure_bar * 1e5

    n_ch4 = 1.0
    n_o2_in = 2.0 * air_ratio
    n_n2_in = n_o2_in * N2_O2_RATIO

    n_co2 = 1.0
    n_h2o = 2.0
    n_o2_out = 2.0 * (air_ratio - 1.0)
    n_n2_out = n_n2_in

    reactants = {
        "CH4": n_ch4,
        "O2": n_o2_in,
        "N2": n_n2_in,
    }

    products = {
        "CO2": n_co2,
        "H2O": n_h2o,
        "O2": n_o2_out,
        "N2": n_n2_out,
    }

    gas = ct.Solution("gri30.yaml")

    # Total reactant enthalpy per kmol of methane.
    reactant_enthalpy = 0.0

    for species, amount in reactants.items():
        gas.TPX = (
            reactant_temperature,
            pressure_pa,
            {species: 1.0},
        )
        reactant_enthalpy += amount * gas.enthalpy_mole

    total_product_kmol = sum(products.values())

    product_mole_fractions = {
        species: amount / total_product_kmol
        for species, amount in products.items()
        if amount > 0
    }

    # Product mass per kmol of methane, numerically kg/kmol.
    product_mass = 0.0

    for species, amount in products.items():
        if amount > 0:
            product_mass += amount * gas.molecular_weights[
                gas.species_index(species)
            ]

    def energy_residual(T):
        gas.TPX = (
            T,
            pressure_pa,
            product_mole_fractions,
        )

        product_enthalpy = (
            gas.enthalpy_mass * product_mass
        )

        return product_enthalpy - reactant_enthalpy

    flame_temperature = brentq(
        energy_residual,
        500.0,
        3500.0,
    )

    def gas_specific_enthalpy(T):
        """Product-mixture enthalpy in kJ/kg."""
        gas.TPX = (
            T,
            pressure_pa,
            product_mole_fractions,
        )
        return gas.enthalpy_mass / 1000.0

    h_gas_in = gas_specific_enthalpy(flame_temperature)

    return {
        "flame_T": flame_temperature,
        "gas_specific_enthalpy": gas_specific_enthalpy,
        "h_gas_in": h_gas_in,
        "product_mass": product_mass,
        "products": products,
        "reactants": reactants,
        "pressure_pa": pressure_pa,
    }


# =========================================================
# LMTD FUNCTION
# =========================================================

def lmtd(delta_1, delta_2):
    """Calculate log mean temperature difference in K."""

    if delta_1 <= 0 or delta_2 <= 0:
        raise ValueError(
            "Invalid temperature differences: both terminal "
            "temperature differences must be positive."
        )

    if math.isclose(delta_1, delta_2, rel_tol=1e-10):
        return 0.5 * (delta_1 + delta_2)

    return (
        (delta_1 - delta_2)
        / math.log(delta_1 / delta_2)
    )


# =========================================================
# MAIN CALCULATION FUNCTION
# =========================================================

def calculate(
    mode,
    air_ratio,
    combustion_pressure_bar,
    reactant_temperature,
    gas_mass_flow,
    gas_outlet_temperature,
    water_mass_flow,
    water_inlet_temperature,
    water_outlet_temperature,
    water_pressure_bar,
    overall_U,
    specified_area,
):
    """
    Run the selected heat-exchanger calculation mode.

    Supported modes:
      1. Given gas outlet temperature
      2. Given water outlet temperature
      3. Given heat-exchanger area
      4. Given both outlet temperatures
    """

    if gas_mass_flow <= 0:
        raise ValueError("Gas mass flow rate must be positive.")

    if water_mass_flow <= 0:
        raise ValueError("Water mass flow rate must be positive.")

    if overall_U <= 0:
        raise ValueError(
            "Overall heat-transfer coefficient must be positive."
        )

    if specified_area <= 0:
        raise ValueError("Heat-exchanger area must be positive.")

    if water_pressure_bar <= 0:
        raise ValueError("Water pressure must be positive.")

    # Combustion calculations
    combustion = prepare_combustion(
        air_ratio=air_ratio,
        reactant_temperature=reactant_temperature,
        combustion_pressure_bar=combustion_pressure_bar,
    )

    flame_T = combustion["flame_T"]
    gas_h = combustion["gas_specific_enthalpy"]
    h_gas_in = gas_h(flame_T)

    # Water inlet properties
    h_water_in = water_enthalpy(
        water_inlet_temperature,
        water_pressure_bar,
    )

    # -----------------------------------------------------
    # MODE 1: GIVEN GAS OUTLET TEMPERATURE
    # -----------------------------------------------------

    if mode == "Given gas outlet temperature":

        gas_out_T = float(gas_outlet_temperature)

        if gas_out_T >= flame_T:
            raise ValueError(
                "Gas outlet temperature must be below the "
                "adiabatic flame temperature."
            )

        h_gas_out = gas_h(gas_out_T)

        Q_kW = gas_mass_flow * (
            h_gas_in - h_gas_out
        )

        if Q_kW <= 0:
            raise ValueError(
                "Calculated heat-transfer rate must be positive."
            )

        h_water_out = (
            h_water_in + Q_kW / water_mass_flow
        )

        water_out_T = water_temperature(
            h_water_out,
            water_pressure_bar,
        )

        water_out_C = water_out_T - 273.15

        phase = water_phase(
            h_water_out,
            water_pressure_bar,
        )

    # -----------------------------------------------------
    # MODE 2: GIVEN WATER OUTLET TEMPERATURE
    # -----------------------------------------------------

    elif mode == "Given water outlet temperature":

        water_out_T = float(water_outlet_temperature)

        if water_out_T <= water_inlet_temperature:
            raise ValueError(
                "Water outlet temperature must be higher "
                "than water inlet temperature."
            )

        h_water_out = water_enthalpy(
            water_out_T,
            water_pressure_bar,
        )

        Q_kW = water_mass_flow * (
            h_water_out - h_water_in
        )

        if Q_kW <= 0:
            raise ValueError(
                "Calculated heat-transfer rate must be positive."
            )

        target_h_gas_out = (
            h_gas_in - Q_kW / gas_mass_flow
        )

        def gas_out_residual(T):
            return gas_h(T) - target_h_gas_out

        lower_T = max(200.0, reactant_temperature * 0.5)

        if target_h_gas_out >= h_gas_in:
            raise ValueError(
                "The specified water outlet state requires "
                "zero or negative heat transfer."
            )

        if gas_h(lower_T) > target_h_gas_out:
            raise ValueError(
                "The specified water outlet temperature "
                "requires an infeasible gas outlet state."
            )

        gas_out_T = brentq(
            gas_out_residual,
            lower_T,
            flame_T - 1e-6,
        )

        water_out_C = water_out_T - 273.15

        phase = water_phase(
            h_water_out,
            water_pressure_bar,
        )

    # -----------------------------------------------------
    # MODE 3: GIVEN HEAT-EXCHANGER AREA
    # -----------------------------------------------------

    elif mode == "Given heat-exchanger area":

        area = float(specified_area)

        def residual(Q):
            h_gas_out_local = (
                h_gas_in - Q / gas_mass_flow
            )

            h_water_out_local = (
                h_water_in + Q / water_mass_flow
            )

            try:
                gas_out_local = brentq(
                    lambda T: gas_h(T) - h_gas_out_local,
                    max(200.0, reactant_temperature * 0.5),
                    flame_T - 1e-6,
                )

                water_out_local = water_temperature(
                    h_water_out_local,
                    water_pressure_bar,
                )

                dt1 = flame_T - water_inlet_temperature
                dt2 = gas_out_local - water_out_local

                lmtd_local = lmtd(dt1, dt2)

                return Q - overall_U * area * lmtd_local

            except (ValueError, RuntimeError):
                return float("nan")

        # Establish a physically feasible upper heat-duty bound.
        q_max_gas = gas_mass_flow * (
            h_gas_in - gas_h(
                max(200.0, reactant_temperature * 0.5)
            )
        )

        q_max_water = 0.0

        # Restrict the search to positive terminal temperature
        # differences. A binary search finds a conservative upper bound.
        lo = 1e-8
        hi = max(1e-6, q_max_gas)

        for _ in range(100):
            mid = 0.5 * (lo + hi)

            try:
                h_gas_out_mid = h_gas_in - mid / gas_mass_flow
                h_water_out_mid = h_water_in + mid / water_mass_flow

                gas_out_mid = brentq(
                    lambda T: gas_h(T) - h_gas_out_mid,
                    max(200.0, reactant_temperature * 0.5),
                    flame_T - 1e-6,
                )

                water_out_mid = water_temperature(
                    h_water_out_mid,
                    water_pressure_bar,
                )

                if (
                    gas_out_mid > water_out_mid
                    and flame_T > water_inlet_temperature
                ):
                    lo = mid
                else:
                    hi = mid

            except (ValueError, RuntimeError):
                hi = mid

        q_max_water = lo

        # Search for a sign-changing interval for the area equation.
        samples = [
            q_max_water * i / 500.0
            for i in range(1, 501)
        ]

        valid_points = []

        for q in samples:
            value = residual(q)
            if math.isfinite(value):
                valid_points.append((q, value))

        bracket = None

        for i in range(len(valid_points) - 1):
            q1, f1 = valid_points[i]
            q2, f2 = valid_points[i + 1]

            if f1 == 0:
                bracket = (q1, q1)
                break

            if f1 * f2 < 0:
                bracket = (q1, q2)
                break

        if bracket is None:
            raise ValueError(
                "No physically feasible solution was found for "
                "the specified heat-exchanger area. Try a different "
                "area or check the input conditions."
            )

        if bracket[0] == bracket[1]:
            Q_kW = bracket[0]
        else:
            Q_kW = brentq(
                residual,
                bracket[0],
                bracket[1],
            )

        h_gas_out = h_gas_in - Q_kW / gas_mass_flow
        h_water_out = h_water_in + Q_kW / water_mass_flow

        gas_out_T = brentq(
            lambda T: gas_h(T) - h_gas_out,
            max(200.0, reactant_temperature * 0.5),
            flame_T - 1e-6,
        )

        water_out_T = water_temperature(
            h_water_out,
            water_pressure_bar,
        )

        water_out_C = water_out_T - 273.15

        phase = water_phase(
            h_water_out,
            water_pressure_bar,
        )

    # -----------------------------------------------------
    # MODE 4: GIVEN BOTH OUTLET TEMPERATURES
    # -----------------------------------------------------

    elif mode == "Given both outlet temperatures":

        gas_out_T = float(gas_outlet_temperature)
        water_out_T = float(water_outlet_temperature)

        if gas_out_T >= flame_T:
            raise ValueError(
                "Gas outlet temperature must be below "
                "the adiabatic flame temperature."
            )

        if water_out_T <= water_inlet_temperature:
            raise ValueError(
                "Water outlet temperature must be above "
                "the water inlet temperature."
            )

        h_gas_out = gas_h(gas_out_T)

        h_water_out = water_enthalpy(
            water_out_T,
            water_pressure_bar,
        )

        Q_gas = gas_mass_flow * (
            h_gas_in - h_gas_out
        )

        Q_water = water_mass_flow * (
            h_water_out - h_water_in
        )

        if Q_gas <= 0 or Q_water <= 0:
            raise ValueError(
                "Both gas-side heat loss and water-side heat gain "
                "must be positive."
            )

        # Use gas-side duty for area calculation and report
        # both duties separately to show the energy-balance mismatch.
        Q_kW = Q_gas

        water_out_C = water_out_T - 273.15

        phase = water_phase(
            h_water_out,
            water_pressure_bar,
        )

    else:
        raise ValueError(
            f"Unknown calculation mode: {mode}"
        )

    # -----------------------------------------------------
    # LMTD AND REQUIRED AREA
    # -----------------------------------------------------

    delta_1 = flame_T - water_inlet_temperature
    delta_2 = gas_out_T - water_out_T

    LMTD = lmtd(delta_1, delta_2)

    if LMTD <= 0:
        raise ValueError("Calculated LMTD must be positive.")

    if mode != "Given heat-exchanger area":
        area = Q_kW / (overall_U * LMTD)

    # -----------------------------------------------------
    # ENERGY BALANCE DETAILS
    # -----------------------------------------------------

    gas_side_Q_kW = gas_mass_flow * (
        h_gas_in - gas_h(gas_out_T)
    )

    water_side_Q_kW = water_mass_flow * (
        water_enthalpy(water_out_T, water_pressure_bar)
        - h_water_in
    )

    energy_balance_difference_kW = (
        gas_side_Q_kW - water_side_Q_kW
    )

    # -----------------------------------------------------
    # RETURN VALUES USED BY app.py
    # -----------------------------------------------------

    result = {
        "mode": mode,

        "flame_T": flame_T,

        "gas_in_T": flame_T,
        "gas_out_T": gas_out_T,

        "water_in_T": water_inlet_temperature,
        "water_out_T": water_out_T,
        "water_out_C": water_out_C,
        "water_phase": phase,

        "Q_kW": Q_kW,
        "area": area,
        "U": overall_U,

        "LMTD": LMTD,
        "delta_1": delta_1,
        "delta_2": delta_2,

        "gas_mass_flow": gas_mass_flow,
        "water_mass_flow": water_mass_flow,

        "gas_side_Q_kW": gas_side_Q_kW,
        "water_side_Q_kW": water_side_Q_kW,
        "energy_balance_difference_kW":
            energy_balance_difference_kW,

        "h_gas_in_kJ_kg": h_gas_in,
        "h_gas_out_kJ_kg": gas_h(gas_out_T),
        "h_water_in_kJ_kg": h_water_in,
        "h_water_out_kJ_kg": water_enthalpy(
            water_out_T,
            water_pressure_bar,
        ),
    }

    return result


