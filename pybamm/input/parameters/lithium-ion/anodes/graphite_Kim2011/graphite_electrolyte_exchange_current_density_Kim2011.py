from pybamm import exp, constants, Parameter, Scalar


def graphite_electrolyte_exchange_current_density_Kim2011(c_e, c_s_surf, T):
    """
    Exchange-current density for Butler-Volmer reactions between graphite and LiPF6 in
    EC:DMC
    [1].

    References
    ----------
    .. [1] Kim, G. H., Smith, K., Lee, K. J., Santhanagopalan, S., & Pesaran, A.
    (2011). Multi-domain modeling of lithium-ion batteries encompassing
    multi-physics in varied length scales. Journal of The Electrochemical
    Society, 158(8), A955-A969.

    Parameters
    ----------
    c_e : :class:`pybamm.Symbol`
        Electrolyte concentration [mol.m-3]
    c_s_surf : :class:`pybamm.Symbol`
        Particle concentration [mol.m-3]
    T : :class:`pybamm.Symbol`
        Temperature [K]

    Returns
    -------
    :class:`pybamm.Symbol`
        Exchange-current density [A.m-2]
    """

    i0_ref = Scalar(36, "[A.m-2]")  # reference exchange current density at 100% SOC
    sto = 0.36  # stochiometry at 100% SOC
    c_s_n_max = Parameter("Maximum concentration in negative electrode [mol.m-3]")
    c_s_n_ref = sto * c_s_n_max  # reference electrode concentration
    c_e_ref = Parameter("Typical electrolyte concentration [mol.m-3]")
    alpha = 0.5  # charge transfer coefficient

    m_ref = i0_ref / (
        c_e_ref ** alpha * (c_s_n_max - c_s_n_ref) ** alpha * c_s_n_ref ** alpha
    )

    E_r = Scalar(3e4, "[J.mol-1]")
    arrhenius = exp(E_r / constants.R * (1 / Scalar(298.15, "[K]") - 1 / T))

    return (
        m_ref
        * arrhenius
        * c_e ** alpha
        * c_s_surf ** alpha
        * (c_s_n_max - c_s_surf) ** alpha
    )
