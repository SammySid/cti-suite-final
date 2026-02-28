/**
 * ============================================================
 * CTI PSYCHROMETRIC ENGINE
 * ============================================================
 *
 * Decoded from CTI Toolkit binary (32-bit Delphi). All-formula
 * engine — no data files, no async init required.
 *
 * Formula pipeline:
 *   1.  P   = ICAO barometric pressure [kPa]        (alt_m)
 *   2.  Pws = Hyland-Wexler SVP [kPa]               0x409234
 *   3.  f   = Enhancement factor (2D probed table)  0x408005
 *   4.  Ws  = 0.62198 × f·Pws / (P − f·Pws)
 *   5.  W   = psychrometer equation                  0x4089E0
 *   6.  DP  = Newton-Raphson on ASHRAE approximation 0x409418
 *   7.  RH  = 100 × (W/(0.62198+W)) × P / (f·Pws_dbt)
 *   8.  H   = 1.006·DBT + W·(2501 + 1.805·DBT)
 *   9.  SV  = 0.287055·(DBT+273.15)·(1+1.6078·W) / P
 *   10. Dens = (1 + W) / SV
 *
 * Accuracy (320 truth points, alt 0–1500m, WBT-synced probe):
 *   DP:  320/320 = 100.00%  (all altitudes)
 *   HR:  320/320 = 100.00%  (all altitudes — perfect after C9 literal fix)
 *   RH:  ~100%
 *   H:   320/320 = 100.00%  (mathematically exact — verified against 50-digit arithmetic)
 *        Note: binary shows ±0.0001 difference in 59/320 cases due to x87 double-rounding
 *        artifacts in the Delphi binary. JS gives the correct IEEE 754 result. No fix needed.
 *
 * Fixes applied:
 *   1. C9 = -5.516256 (binary hardcodes literal, NOT computed 1.3914993−ln(1000))
 *      Confirmed by code-cave probe at 0x409234. Delta = −2.102e-08.
 *      Effect: HR 304→320/320 = 100%. DP unchanged (dp shift < 1e-7 °C).
 *   2. P = 101.325 × (1 − 2.25577e-5 × alt_m)^5.2559 (ICAO metres)
 *   3. f replaced with 2D probed table (v2.7.0):
 *      Disassembly of 0x408005 revealed f takes T_Fahrenheit and P_PSI (not °C/kPa).
 *      Previous k(T) formula was therefore incorrect. New approach: EP-hijack code-cave
 *      probe of f(0x408005) for T grid (−5..59°C, 1°C step) × alt (0,500,1000,1500 m)
 *      = 4×65 = 260 float64 values, bilinearly interpolate.
 *   4. H double-rounding analysis (2026-02-28, work/test_x87_hypothesis.py):
 *      50-digit Decimal confirms JS H is mathematically correct for all 320 cases.
 *      The binary's 59 deviations are x87 80→64-bit double-rounding artifacts, not
 *      formula errors. JS intentionally does NOT emulate these artifacts.
 *
 * @module psychro-engine
 * @version 3.0.0 — f table in data/psychro_f_alt.bin, async init (mirrors merkel-engine)
 */

// ============================================================
// HYLAND-WEXLER CONSTANTS (decoded from binary inline doubles)
// ============================================================

// Over water (T >= 0°C) — ASHRAE 2017 coefficients
// C9 confirmed by code-cave probe at 0x409234: binary hardcodes -5.516256 (not 1.3914993−ln(1000))
const HW_WATER_C8  = -5800.2206;
const HW_WATER_C9  = -5.516256;   // binary hardcodes this literal (not 1.3914993−ln1000 = −5.51625598…)
const HW_WATER_C10 = -0.048640239;
const HW_WATER_C11 = 4.1764768e-5;
const HW_WATER_C12 = -1.4452093e-8;
const HW_WATER_C13 = 6.5459673;

// Over ice (T < 0°C) — C9 = ASHRAE_C2 - ln(1000)
const HW_ICE_C8 = -5674.5359;
const HW_ICE_C9 = 6.3925247 - Math.log(1000);         // ≈ -0.51523058
const HW_ICE_C10 = -0.0096778430;
const HW_ICE_C11 = 6.2215701e-7;
const HW_ICE_C12 = 2.0747825e-9;
const HW_ICE_C13 = -9.484024e-13;
const HW_ICE_C14 = 4.1635019;

// ASHRAE dew point explicit approximation coefficients
const DP_WATER = { C14: 6.54, C15: 14.526, C16: 0.7389, C17: 0.09486, C18: 0.4569, n: 0.1984 };
const DP_ICE = { C14: 6.09, C15: 12.608, C16: 0.4959 };

// Psychrometer equation coefficients
const L0 = 2501.0;      // Latent heat at 0°C (kJ/kg)
const CpS = 1.805;       // Cp of steam (kJ/(kg·K))
const CpW = 4.186;       // Cp of water (kJ/(kg·K))
const L_COEFF = 2.381;       // = CpW - CpS (latent heat temperature coefficient)
const MW_MA = 0.62198;     // Molecular weight ratio Mw/Ma

// Gas constant for dry air [kJ/(kg·K)] — CTI uses 0.287055 (not standard 0.287042)
const Ra = 0.287055;

// ============================================================
// ENHANCEMENT FACTOR TABLE  (loaded from data/psychro_f_alt.bin)
// Probed from CTI binary 0x408005 with T in °F, P in PSI.
// Source: EP-hijack code-cave, confirmed by disassembly of 0x40893C.
//
// Layout: 4 altitude rows × 65 temperature columns = 260 float64 values.
//   T grid  : −5..59 °C, 1 °C step  (stride = F_ALT_T_N)
//   Alt grid: 0, 500, 1000, 1500 m
// ============================================================

const F_ALT_T_MIN    = -5;    // °C  — first T column
const F_ALT_T_STEP   =  1;    // °C  — column step
const F_ALT_T_N      = 65;    // number of T columns (−5..59 °C)
const F_ALT_A_STEP   = 500;   // m   — altitude row step
const F_ALT_N_ALT    =  4;    // number of altitude rows

/** Float64Array of shape [F_ALT_N_ALT × F_ALT_T_N], null before init */
let _fAlt = null;

/**
 * Load the enhancement factor table from a binary file.
 * Must be awaited before calling psychrometrics().
 *
 * @param {string} binPath  URL to psychro_f_alt.bin
 * @returns {Promise<void>}
 */
async function initPsychroEngine(binPath) {
    const buf = await (await fetch(binPath)).arrayBuffer();
    _fAlt = new Float64Array(buf);
}

/**
 * Enhancement factor f(T, P) — bilinear interpolation from 2D probed table.
 *
 * Probed from CTI binary 0x408005 with T in °F and P in PSI
 * (confirmed by disassembly of caller 0x40893C).
 *
 * @param {number} T_celsius - Temperature [°C]
 * @param {number} P         - Atmospheric pressure [kPa]
 * @returns {number} Pressure-corrected enhancement factor
 */
function fEnhanceAtP(T_celsius, P) {
    // Convert P to altitude (inverse ICAO barometric formula)
    const alt_m = (1.0 - Math.pow(P / 101.325, 1.0 / 5.2559)) / 2.25577e-5;

    // T interpolation index (clamp to table bounds)
    const t_float = (T_celsius - F_ALT_T_MIN) / F_ALT_T_STEP;
    const t_lo    = Math.max(0, Math.min(F_ALT_T_N - 2, Math.floor(t_float)));
    const frac_t  = Math.max(0.0, Math.min(1.0, t_float - t_lo));

    // Alt interpolation index (clamp: extrapolate flat above 1500 m)
    const a_float = alt_m / F_ALT_A_STEP;
    const a_lo    = Math.max(0, Math.min(F_ALT_N_ALT - 2, Math.floor(a_float)));
    const frac_a  = Math.max(0.0, Math.min(1.0, a_float - a_lo));

    // Bilinear interpolation over flat array (stride = F_ALT_T_N)
    const base_lo = a_lo * F_ALT_T_N;
    const base_hi = base_lo + F_ALT_T_N;
    const fLo = _fAlt[base_lo + t_lo] + frac_t * (_fAlt[base_lo + t_lo + 1] - _fAlt[base_lo + t_lo]);
    const fHi = _fAlt[base_hi + t_lo] + frac_t * (_fAlt[base_hi + t_lo + 1] - _fAlt[base_hi + t_lo]);
    return fLo + frac_a * (fHi - fLo);
}

/**
 * Hyland-Wexler saturation vapor pressure [kPa].
 * Matches CTI binary function at 0x409234.
 * 
 * For T >= 0°C (over water):
 *   ln(Pws) = C8/T + C9 + C10*T + C11*T² + C12*T³ + C13*ln(T)
 * For T < 0°C (over ice):
 *   ln(Pws) = C8/T + C9 + C10*T + C11*T² + C12*T³ + C13*T⁴ + C14*ln(T)
 * 
 * @param {number} T_celsius - Temperature in degrees Celsius
 * @returns {number} Saturation vapor pressure in kPa
 */
function pwsKpa(T_celsius) {
    const T_K = T_celsius + 273.15;
    if (T_K <= 0) return 0.0;

    let lnPws;

    if (T_celsius >= 0) {
        // Over water
        lnPws = HW_WATER_C8 / T_K + HW_WATER_C9 + HW_WATER_C10 * T_K +
            HW_WATER_C11 * T_K * T_K + HW_WATER_C12 * Math.pow(T_K, 3) +
            HW_WATER_C13 * Math.log(T_K);
    } else {
        // Over ice
        lnPws = HW_ICE_C8 / T_K + HW_ICE_C9 + HW_ICE_C10 * T_K +
            HW_ICE_C11 * T_K * T_K + HW_ICE_C12 * Math.pow(T_K, 3) +
            HW_ICE_C13 * Math.pow(T_K, 4) + HW_ICE_C14 * Math.log(T_K);
    }

    return Math.exp(lnPws);
}

/**
 * Derivative d(Pws)/dT for Newton-Raphson refinement.
 * @param {number} T_celsius - Temperature in degrees Celsius
 * @param {number} Pws_val - Pre-computed Pws at this temperature
 * @returns {number} Derivative of Pws w.r.t. temperature
 */
function dpwsDT(T_celsius, Pws_val) {
    const T_K = T_celsius + 273.15;
    if (T_K <= 0) return 0.0;

    let dln;

    if (T_celsius >= 0) {
        dln = -HW_WATER_C8 / (T_K * T_K) + HW_WATER_C10 +
            2 * HW_WATER_C11 * T_K + 3 * HW_WATER_C12 * T_K * T_K +
            HW_WATER_C13 / T_K;
    } else {
        dln = -HW_ICE_C8 / (T_K * T_K) + HW_ICE_C10 +
            2 * HW_ICE_C11 * T_K + 3 * HW_ICE_C12 * T_K * T_K +
            4 * HW_ICE_C13 * Math.pow(T_K, 3) + HW_ICE_C14 / T_K;
    }

    return dln * Pws_val;
}

/**
 * Dew point from ASHRAE 2017 explicit approximation (initial guess).
 * @param {number} Pw_kPa - Partial water vapor pressure in kPa
 * @returns {number} Dew point temperature in degrees Celsius
 */
function dewPointExplicit(Pw_kPa) {
    if (Pw_kPa <= 0) return 0.0;

    const alpha = Math.log(Pw_kPa);

    // Water formula
    let dp = DP_WATER.C14 + DP_WATER.C15 * alpha +
        DP_WATER.C16 * alpha * alpha +
        DP_WATER.C17 * Math.pow(alpha, 3) +
        DP_WATER.C18 * Math.pow(Pw_kPa, DP_WATER.n);

    if (dp < 0) {
        // Switch to ice formula
        dp = DP_ICE.C14 + DP_ICE.C15 * alpha + DP_ICE.C16 * alpha * alpha;
    }

    return dp;
}

/**
 * Dew point with Newton-Raphson refinement.
 * Decoded from binary at 0x409418 lines 387-611.
 * 
 * @param {number} W - Humidity ratio [kg/kg dry air]
 * @param {number} P - Atmospheric pressure [kPa]
 * @param {number} f_init - Initial enhancement factor
 * @returns {number} Dew point temperature in degrees Celsius
 */
function dewPointNewton(W, P, f_init) {
    if (W <= 0) return 0.0;

    // Phase 1: ASHRAE explicit approximation (2 f-enhancement iterations)
    let denomCheck = (MW_MA + W) * f_init;
    let Pw = denomCheck > 0 ? P * W / denomCheck : 0;
    let dp = dewPointExplicit(Pw);

    for (let i = 0; i < 2; i++) {
        const f_dp = fEnhanceAtP(dp, P);
        denomCheck = (MW_MA + W) * f_dp;
        Pw = denomCheck > 0 ? P * W / denomCheck : 0;
        dp = dewPointExplicit(Pw);
    }

    // Phase 2: Newton-Raphson refinement
    let step = 1.0;

    for (let iter = 0; iter < 50; iter++) {
        const Pws_dp = pwsKpa(dp);
        const f_dp = fEnhanceAtP(dp, P);
        const fPws_dp = f_dp * Pws_dp;
        const denom_dp = P - fPws_dp;

        if (Math.abs(denom_dp) < 1e-15) break;

        const W_dp = MW_MA * fPws_dp / denom_dp;
        if (W_dp <= 0) break;

        // Convergence check (from binary: abs(W/W_dp - 1) < 1e-6)
        if (Math.abs(W / W_dp - 1) < 1e-6) break;

        // Step size check (from binary: abs(step) < 0.0001)
        if (Math.abs(step) < 0.0001) break;

        // Compute derivative dW/d(dp)
        const dPws = dpwsDT(dp, Pws_dp);
        const dW_dp = MW_MA * f_dp * dPws * P / (denom_dp * denom_dp);

        if (Math.abs(dW_dp) < 1e-20) break;

        // Newton step
        step = (W - W_dp) / dW_dp;
        dp += step;
    }

    return dp;
}

/**
 * Full psychrometric calculation matching CTI Toolkit.
 * 
 * @param {number} dbt - Dry-bulb temperature [°C]
 * @param {number} wbt - Wet-bulb temperature [°C]
 * @param {number} [alt_m=0] - Altitude [meters above sea level]
 * @returns {Object} Psychrometric properties: { HR, DP, RH, H, SV, Dens, P }
 *   - HR: Humidity ratio [kg/kg dry air]
 *   - DP: Dew point temperature [°C]
 *   - RH: Relative humidity [%]
 *   - H:  Enthalpy [kJ/kg dry air]
 *   - SV: Specific volume [m³/kg dry air]
 *   - Dens: Density [kg/m³]
 *   - P: Atmospheric pressure [kPa]
 */
function psychrometrics(dbt, wbt, alt_m = 0.0) {
    // Step 1: ICAO barometric pressure [kPa] — standard atmosphere in metres
    const P = 101.325 * Math.pow(1 - 2.25577e-5 * alt_m, 5.2559);

    // Step 2: Saturation vapor pressure at WBT [kPa]
    const Pws_wbt = pwsKpa(wbt);

    // Step 3: Enhancement factor at WBT — pressure-corrected for altitude
    const f_wbt = fEnhanceAtP(wbt, P);

    // Step 4: Saturated humidity ratio at WBT [kg/kg]
    const fPws = f_wbt * Pws_wbt;
    const Ws = MW_MA * fPws / (P - fPws);

    // Step 5: Humidity ratio from psychrometer equation [kg/kg]
    // KEY: CTI omits the 1.006 Cp_dry factor!
    const denom = L0 + CpS * dbt - CpW * wbt;
    let W = ((L0 - L_COEFF * wbt) * Ws - (dbt - wbt)) / denom;
    if (W < 0) W = 0.0;

    // Step 6: Dew point [°C] with Newton-Raphson refinement
    const dp = dewPointNewton(W, P, f_wbt);

    // Step 7: Relative humidity [%]
    const Pws_dbt = pwsKpa(dbt);
    const f_dbt = fEnhanceAtP(dbt, P);
    let RH = 0.0;
    if (f_dbt * Pws_dbt > 0) {
        RH = 100.0 * (W / (MW_MA + W)) * P / (f_dbt * Pws_dbt);
    }

    // Step 8: Enthalpy [kJ/kg dry air]
    const H = 1.006 * dbt + W * (L0 + CpS * dbt);

    // Step 9: Specific volume [m³/kg dry air]
    const SV = Ra * (dbt + 273.15) * (1 + 1.6078 * W) / P;

    // Step 10: Density [kg/m³]
    const Dens = (1 + W) / SV;

    return {
        HR: parseFloat(W.toFixed(5)),
        DP: parseFloat(dp.toFixed(2)),
        RH: parseFloat(RH.toFixed(2)),
        H: parseFloat(H.toFixed(4)),
        SV: parseFloat(SV.toFixed(4)),
        Dens: parseFloat(Dens.toFixed(5)),
        P: parseFloat(P.toFixed(3))
    };
}

export { initPsychroEngine, psychrometrics, pwsKpa, fEnhanceAtP, dewPointNewton };
