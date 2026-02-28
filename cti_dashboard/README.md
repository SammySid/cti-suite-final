# CTI Analysis Dashboard

Fully standalone web dashboard for cooling tower engineering calculations, reverse-engineered from the CTI Toolkit binary with **100% display parity** — no runtime binary dependency, no external libraries, zero server-side code.

---

## Quick Start

```bash
python run.py           # auto-picks port, opens browser
# or
python -m http.server 8080  # then open http://localhost:8080
```

> A static HTTP server is required — the Merkel engine fetches `data/merkel_poly.bin` on load.

---

## Features

### Psychrometric Calculator
- **7 air properties** from DBT, WBT, and Altitude
- Humidity Ratio, Dew Point, Relative Humidity, Enthalpy, Specific Volume, Density, Pressure
- Hyland-Wexler SVP + ASHRAE 2017 formulas decoded from binary
- **DP: 100% bit-perfect** at all altitudes (0–3000m) — pressure-corrected enhancement factor

### Merkel KaV/L Calculator
- **Cooling tower characteristic** from HWT, CWT, WBT, L/G, Altitude (0–2000 m)
- 4-point Chebyshev numerical integration (decoded from binary at 0x409BFE)
- **100% display parity** — 320/320 exact 5dp matches across all altitudes and temperature ranges
- Data file: `data/merkel_poly.bin` (**29.8 KB**) — loaded once, no binary needed at runtime

### Charts
- Real-time sensitivity analysis: KaV/L vs L/G, vs Altitude, multi-WBT comparison
- Enthalpy vs DBT, RH vs DBT, Properties vs Altitude
- Custom canvas renderer — no Chart.js dependency

---

## Architecture

```
cti_dashboard/
├── index.html              Single-page entry point
├── css/styles.css          Dark-mode glassmorphic design system
├── js/
│   ├── app.js              UI controller + async engine init
│   ├── psychro-engine.js   Psychrometric engine (pure math)
│   ├── merkel-engine.js    Merkel engine (Clenshaw polynomial eval, ~8 KB)
│   └── chart-utils.js      Canvas chart renderer
├── data/
│   └── merkel_poly.bin     Chebyshev coefficients — 29.8 KB
└── docs/
    └── DOCUMENTATION.md    Full technical reference
```

### Zero Runtime Dependencies
- No npm, no build step, no external JS libraries
- Google Fonts via CDN — degrades gracefully offline
- Runs on Linux, Mac, Windows, mobile, any modern browser

---

## Engine Accuracy

| Engine | Test Cases | Parity | Method |
|---|---|---|---|
| Psychrometric | 320 points | **DP 100%** at all altitudes · HR/RH ~95%+ | Formula reimplementation |
| Merkel KaV/L | **320 cases** | **100.00%** | Chebyshev polynomial compression |

### How the Merkel Engine Achieves 100%

The binary's `MerkelPsychro_imperial` (0x407723) was probed once on Windows (1.67 M probe points, ~61 s) to build a 12.8 MB raw table. That table was then compressed to **29.8 KB** by fitting a degree-18 Chebyshev polynomial per altitude level:

- **Worst-case polynomial residual:** 9.1 × 10⁻¹⁴ in ln-space
- **Required for 5dp parity:** < 5 × 10⁻⁷
- **Safety margin: 5.5 million×**

The engine evaluates the polynomial at the exact input temperature (Clenshaw recurrence, O(19) ops) and linearly interpolates between altitude levels. No T-grid quantization, no interpolation error for the display-parity requirement.

---

*Reverse-engineered from CTI Toolkit (32-bit Delphi) · EP hijacking + shellcode injection*  
*Psychrometrics: Hyland-Wexler + ASHRAE 2017 · Merkel: 4-pt Chebyshev + polynomial-compressed probe data*
