
"""Reusable forced-convection calculations for an isothermal flat plate."""

import math


def calculate_flat_plate(
    *,
    velocity_m_s,
    plate_length_m,
    plate_width_m,
    free_stream_temperature_K,
    surface_temperature_K,
    kinematic_viscosity_m2_s,
    thermal_diffusivity_m2_s,
    conductivity_W_mK,
    transition_reynolds=5.0e5,
):
    """Calculate average drag-related and heat-transfer quantities."""

    values = [
        velocity_m_s,
        plate_length_m,
        plate_width_m,
        free_stream_temperature_K,
        surface_temperature_K,
        kinematic_viscosity_m2_s,
        thermal_diffusivity_m2_s,
        conductivity_W_mK,
        transition_reynolds,
    ]

    if not all(math.isfinite(float(v)) for v in values):
        raise ValueError("All inputs must be finite numbers.")

    if any(v <= 0 for v in [
        velocity_m_s,
        plate_length_m,
        plate_width_m,
        kinematic_viscosity_m2_s,
        thermal_diffusivity_m2_s,
        conductivity_W_mK,
        transition_reynolds,
    ]):
        raise ValueError("Flow and property inputs must be positive.")

    if free_stream_temperature_K <= 0 or surface_temperature_K <= 0:
        raise ValueError("Temperatures must be above absolute zero.")

    Re_L = (
        velocity_m_s
        * plate_length_m
        / kinematic_viscosity_m2_s
    )

    Pr = (
        kinematic_viscosity_m2_s
        / thermal_diffusivity_m2_s
    )

    area = plate_length_m * plate_width_m
    delta_T = free_stream_temperature_K - surface_temperature_K

    if Re_L <= transition_reynolds:
        Cf = 1.328 / math.sqrt(Re_L)
        Nu_avg = 0.664 * math.sqrt(Re_L) * Pr ** (1 / 3)
        regime = "Laminar"
        correlation = "Laminar average correlations"
    else:
        Cf = 0.074 * Re_L ** (-0.2) - 1742 / Re_L

        correction = (
            0.037 * transition_reynolds ** 0.8
            - 0.664 * math.sqrt(transition_reynolds)
        )

        Nu_avg = (
            0.037 * Re_L ** 0.8 - correction
        ) * Pr ** (1 / 3)

        regime = "Mixed laminar–turbulent"
        correlation = "Mixed-flow average correlations"

    if Cf <= 0 or Nu_avg <= 0:
        raise ValueError("The selected correlation produced an invalid result.")

    h_avg = Nu_avg * conductivity_W_mK / plate_length_m

    drag_N = (
        Cf
        * 0.5
        * 1.0  # Density must be supplied for drag; see note below.
        * velocity_m_s**2
        * area
    )

    q_W = h_avg * area * delta_T

    profile = []

    for i in range(1, 101):
        x = plate_length_m * i / 100
        Re_x = velocity_m_s * x / kinematic_viscosity_m2_s

        if Re_x <= transition_reynolds:
            Nu_x = 0.332 * math.sqrt(Re_x) * Pr ** (1 / 3)
        else:
            Nu_x = 0.0296 * Re_x ** 0.8 * Pr ** (1 / 3)

        h_x = Nu_x * conductivity_W_mK / x

        profile.append({
            "x_m": x,
            "Re_x": Re_x,
            "h_local_W_m2K": h_x,
        })

    return {
        "Re_L": Re_L,
        "Pr": Pr,
        "Cf": Cf,
        "Nu_avg": Nu_avg,
        "h_avg_W_m2K": h_avg,
        "drag_N": drag_N,
        "q_W": q_W,
        "q_per_width_W_m": q_W / plate_width_m,
        "flow_regime": regime,
        "correlation": correlation,
        "profile": profile,
    }

