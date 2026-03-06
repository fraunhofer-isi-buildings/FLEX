"""Shared 5R1C equation helpers used by both ref and opt implementations."""


def phi_m(am, atot, qi, q_solar):
    # ISO 13790 Eq. C.2
    return am / atot * (0.5 * qi + q_solar)


def phi_st(am, atot, htr_w, qi, q_solar):
    # ISO 13790 Eq. C.3
    return (1 - am / atot - htr_w / 9.1 / atot) * (0.5 * qi + q_solar)


def phi_mtot(
    phi_m_val,
    htr_em,
    t_outside,
    htr_3,
    phi_st_val,
    htr_w,
    htr_1,
    phi_ia,
    q_hc,
    hve,
    t_sup,
    htr_2,
):
    # ISO 13790 Eq. C.5
    return (
        phi_m_val
        + htr_em * t_outside
        + htr_3 * (phi_st_val + htr_w * t_outside + htr_1 * (((phi_ia + q_hc) / hve) + t_sup)) / htr_2
    )


def next_thermal_mass_temperature(tm_prev, cm, htr_3, htr_em, phi_mtot_val):
    # ISO 13790 Eq. C.4
    return (
        tm_prev * (cm / 3600 - 0.5 * (htr_3 + htr_em)) + phi_mtot_val
    ) / (cm / 3600 + 0.5 * (htr_3 + htr_em))


def mean_thermal_mass_temperature(tm_now, tm_prev):
    # ISO 13790 Eq. C.9
    return (tm_now + tm_prev) / 2


def surface_temperature(htr_ms, t_m, phi_st_val, htr_w, t_outside, htr_1, t_sup, phi_ia, q_hc, hve):
    # ISO 13790 Eq. C.10
    return (
        htr_ms * t_m
        + phi_st_val
        + htr_w * t_outside
        + htr_1 * (t_sup + (phi_ia + q_hc) / hve)
    ) / (htr_ms + htr_w + htr_1)


def room_temperature(htr_is, t_s, hve, t_sup, phi_ia, q_hc):
    # ISO 13790 Eq. C.11
    return (htr_is * t_s + hve * t_sup + phi_ia + q_hc) / (htr_is + hve)
