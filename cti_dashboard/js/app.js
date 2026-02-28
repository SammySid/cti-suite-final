/**
 * ============================================================
 * CTI DASHBOARD — Main Application Controller
 * ============================================================
 *
 * Orchestrates the UI, binds inputs to calculation engines,
 * manages tab navigation, and renders all output panels.
 *
 * Architecture:
 *   - Psychrometric Engine (psychro-engine.js) for air properties
 *   - Merkel Engine (merkel-engine.js) for cooling tower KaV/L
 *   - Chart Utilities (chart-utils.js) for data visualization
 *   - This file: UI binding, event handling, output rendering
 *
 * @module app
 * @version 2.1.0 — both engines async binary table load (psychro + merkel)
 */

import { initPsychroEngine, psychrometrics } from './psychro-engine.js';
import { initMerkelEngine, merkelKaVL } from './merkel-engine.js';
import { drawLineChart, drawMultiLineChart, CHART_COLORS } from './chart-utils.js';

// ============================================================
// STATE
// ============================================================

/** Current active tab: 'psychro' or 'merkel' */
let activeTab = 'psychro';

/** Ordered tab ids for direction detection */
const TAB_ORDER = ['psychro', 'merkel'];

/** Last computed results for charting */
let lastPsychroResult = null;
let lastMerkelResult = null;

/** True once the psychro f-table binary has finished loading */
let psychroReady = false;

/** True once the binary Merkel table has finished loading */
let merkelReady = false;

// ============================================================
// INITIALIZATION
// ============================================================

document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    initInputListeners();
    initRangeSliders();
    initFormulaToggles();

    // Load both binary tables in parallel, then run initial calculations
    setPsychroStatus('loading');
    setMerkelStatus('loading');

    initPsychroEngine('data/psychro_f_alt.bin')
        .then(() => {
            psychroReady = true;
            setPsychroStatus('ready');
            calculatePsychrometrics();
        })
        .catch(err => {
            setPsychroStatus('error');
            console.error('Psychro engine failed to load:', err);
        });

    initMerkelEngine('data/merkel_poly.bin')
        .then(() => {
            merkelReady = true;
            setMerkelStatus('ready');
            calculateMerkel();
        })
        .catch(err => {
            setMerkelStatus('error');
            console.error('Merkel engine failed to load:', err);
        });

    // Responsive chart resize
    window.addEventListener('resize', debounce(() => {
        if (activeTab === 'psychro') {
            updatePsychroCharts();
        } else {
            updateMerkelCharts();
        }
    }, 200));
});

/**
 * Update the Merkel loading status indicator in the UI.
 * @param {'loading'|'ready'|'error'} state
 */
function setPsychroStatus(state) {
    const el = document.getElementById('psychro-status');
    if (!el) return;
    const messages = {
        loading: '⏳ Loading f-table…',
        ready:   '',
        error:   '⚠ Table failed to load — refresh to retry'
    };
    el.textContent = messages[state] ?? '';
    el.dataset.state = state;
}

function setMerkelStatus(state) {
    const el = document.getElementById('merkel-status');
    if (!el) return;
    const messages = {
        loading: '⏳ Loading precision table…',
        ready:   '',
        error:   '⚠ Table failed to load — refresh to retry'
    };
    el.textContent = messages[state] ?? '';
    el.dataset.state = state;
}

// ============================================================
// FORMULA COLLAPSE
// ============================================================

/**
 * Initialize collapsible formula reference panels.
 * Auto-collapses on tablet/mobile (≤1100px) for better usability.
 */
function initFormulaToggles() {
    const isMobile = window.innerWidth <= 1100;

    document.querySelectorAll('.formula-toggle').forEach(btn => {
        const targetId = btn.dataset.target;
        const formulaRef = document.getElementById(targetId);
        if (!formulaRef) return;

        // Auto-collapse on mobile/tablet on first load
        if (isMobile) {
            formulaRef.classList.add('collapsed');
            btn.setAttribute('aria-expanded', 'false');
        }

        btn.addEventListener('click', () => {
            const isCollapsed = formulaRef.classList.toggle('collapsed');
            btn.setAttribute('aria-expanded', String(!isCollapsed));
        });
    });
}

// ============================================================
// TAB MANAGEMENT
// ============================================================

/**
 * Initialize tab switching behavior with direction-aware slide animation.
 * Sliding right (→) when moving forward in TAB_ORDER, left (←) when going back.
 */
function initTabs() {
    const tabs = document.querySelectorAll('[data-tab]');
    const panels = document.querySelectorAll('.tab-panel');

    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const target = tab.dataset.tab;
            if (target === activeTab) return;

            // Determine slide direction
            const fromIdx = TAB_ORDER.indexOf(activeTab);
            const toIdx = TAB_ORDER.indexOf(target);
            const slideClass = toIdx > fromIdx ? 'slide-from-right' : 'slide-from-left';

            // Update tab buttons
            tabs.forEach(t => {
                t.classList.remove('active');
                t.setAttribute('aria-selected', 'false');
            });
            tab.classList.add('active');
            tab.setAttribute('aria-selected', 'true');

            // Update panels with directional animation
            panels.forEach(p => {
                p.classList.remove('active', 'slide-from-right', 'slide-from-left');
                if (p.id === `panel-${target}`) {
                    p.classList.add('active', slideClass);
                }
            });

            activeTab = target;

            // Scroll to top of content on mobile tab switch
            if (window.innerWidth <= 768) {
                window.scrollTo({ top: 0, behavior: 'smooth' });
            }

            // Refresh charts for the active tab
            requestAnimationFrame(() => {
                if (target === 'psychro') {
                    updatePsychroCharts();
                } else {
                    updateMerkelCharts();
                }
            });
        });
    });
}

// ============================================================
// INPUT HANDLING
// ============================================================

/**
 * Bind all input fields to their respective calculation functions.
 */
function initInputListeners() {
    // Psychrometric inputs
    const psychroInputs = ['p-dbt', 'p-wbt', 'p-alt'];
    psychroInputs.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('input', debounce(calculatePsychrometrics, 150));
        }
    });

    // Merkel inputs
    const merkelInputs = ['m-hwt', 'm-cwt', 'm-wbt', 'm-lg', 'm-alt'];
    merkelInputs.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('input', debounce(calculateMerkel, 150));
        }
    });
}

/**
 * Initialize range slider sync with number inputs.
 * Also maintains --slider-fill CSS custom property for the filled-track effect.
 */
function initRangeSliders() {
    document.querySelectorAll('.slider-input').forEach(slider => {
        const targetId = slider.dataset.target;
        const target = document.getElementById(targetId);

        if (target) {
            slider.addEventListener('input', () => {
                target.value = slider.value;
                updateSliderFill(slider);
                target.dispatchEvent(new Event('input'));
            });

            // Sync on first load
            slider.value = target.value;
            updateSliderFill(slider);

            // Keep slider in sync when number input changes
            target.addEventListener('input', () => {
                slider.value = target.value;
                updateSliderFill(slider);
            });
        }
    });
}

/**
 * Update the --slider-fill CSS custom property so the track
 * renders a filled portion behind the thumb (native-app style).
 * @param {HTMLInputElement} slider
 */
function updateSliderFill(slider) {
    const min = parseFloat(slider.min) || 0;
    const max = parseFloat(slider.max) || 100;
    const val = parseFloat(slider.value) || 0;
    const pct = Math.max(0, Math.min(100, ((val - min) / (max - min)) * 100));
    slider.style.setProperty('--slider-fill', pct.toFixed(1) + '%');
}

// ============================================================
// PSYCHROMETRIC CALCULATION & RENDERING
// ============================================================

/**
 * Read inputs, run psychrometric calculation, and update the UI.
 */
function calculatePsychrometrics() {
    if (!psychroReady) return;
    const dbt = parseFloat(document.getElementById('p-dbt')?.value) || 35;
    const wbt = parseFloat(document.getElementById('p-wbt')?.value) || 25;
    const alt = parseFloat(document.getElementById('p-alt')?.value) || 0;

    // Validation
    const errorEl = document.getElementById('p-error');
    if (wbt > dbt) {
        if (errorEl) {
            errorEl.textContent = 'WBT cannot exceed DBT';
            errorEl.style.display = 'block';
        }
        return;
    }
    if (errorEl) errorEl.style.display = 'none';

    // Calculate
    const result = psychrometrics(dbt, wbt, alt);
    lastPsychroResult = { dbt, wbt, alt, ...result };

    // Update result cards with animation
    animateValue('out-hr', result.HR, 5, 'kg/kg');
    animateValue('out-dp', result.DP, 2, '°C');
    animateValue('out-rh', result.RH, 2, '%');
    animateValue('out-h', result.H, 4, 'kJ/kg');
    animateValue('out-sv', result.SV, 4, 'm³/kg');
    animateValue('out-dens', result.Dens, 5, 'kg/m³');
    animateValue('out-p', result.P, 3, 'kPa');

    // Update charts
    requestAnimationFrame(updatePsychroCharts);
}

/**
 * Generate and render psychrometric sensitivity charts.
 * Shows how properties change with DBT and altitude.
 */
function updatePsychroCharts() {
    if (!lastPsychroResult) return;

    const { wbt, alt, dbt } = lastPsychroResult;

    // Chart 1: Enthalpy vs DBT (boss's requirement — shows DBT effect on H)
    const enthalpyCanvas = document.getElementById('chart-enthalpy-dbt');
    if (enthalpyCanvas) {
        const data = [];
        const startDBT = Math.max(wbt, -5);
        const endDBT = Math.min(60, wbt + 40);
        for (let t = startDBT; t <= endDBT; t += 0.5) {
            const r = psychrometrics(t, wbt, alt);
            data.push({ x: t, y: r.H });
        }
        drawLineChart(enthalpyCanvas, {
            data,
            color: CHART_COLORS.primary,
            xLabel: 'Dry Bulb Temperature (°C)',
            yLabel: 'Enthalpy (kJ/kg)',
            highlightX: dbt,
            unit: 'kJ/kg'
        });
    }

    // Chart 2: Properties vs Altitude (boss's requirement — altitude effect)
    const altCanvas = document.getElementById('chart-altitude-effect');
    if (altCanvas) {
        const series = [];
        const hrData = [], hData = [], rhData = [];

        for (let a = 0; a <= 3000; a += 100) {
            const r = psychrometrics(dbt, wbt, a);
            hrData.push({ x: a, y: r.HR * 1000 }); // g/kg for readability
            hData.push({ x: a, y: r.H });
            rhData.push({ x: a, y: r.RH });
        }

        drawMultiLineChart(altCanvas, {
            series: [
                { data: rhData, color: CHART_COLORS.secondary, label: 'RH (%)' },
                { data: hData, color: CHART_COLORS.primary, label: 'H (kJ/kg)' },
            ],
            xLabel: 'Altitude (m)',
            yLabel: 'Value'
        });
    }

    // Chart 3: HR vs DBT (humidity ratio sensitivity)
    const hrCanvas = document.getElementById('chart-hr-dbt');
    if (hrCanvas) {
        const data = [];
        const startDBT = Math.max(wbt, -5);
        const endDBT = Math.min(60, wbt + 40);
        for (let t = startDBT; t <= endDBT; t += 0.5) {
            const r = psychrometrics(t, wbt, alt);
            data.push({ x: t, y: r.RH });
        }
        drawLineChart(hrCanvas, {
            data,
            color: CHART_COLORS.tertiary,
            xLabel: 'Dry Bulb Temperature (°C)',
            yLabel: 'Relative Humidity (%)',
            highlightX: dbt,
            unit: '%'
        });
    }
}

// ============================================================
// MERKEL CALCULATION & RENDERING
// ============================================================

/**
 * Read inputs, run Merkel KaV/L calculation, and update the UI.
 * No-op until the binary table has finished loading.
 */
function calculateMerkel() {
    if (!merkelReady) return;

    const hwt = parseFloat(document.getElementById('m-hwt')?.value) || 40;
    const cwt = parseFloat(document.getElementById('m-cwt')?.value) || 28;
    const wbt = parseFloat(document.getElementById('m-wbt')?.value) || 20;
    const lg = parseFloat(document.getElementById('m-lg')?.value) || 1.0;
    const alt = parseFloat(document.getElementById('m-alt')?.value) || 0;

    const errorEl = document.getElementById('m-error');

    // Calculate
    const result = merkelKaVL(hwt, cwt, wbt, lg, alt);
    lastMerkelResult = { hwt, cwt, wbt, lg, alt, ...result };

    // Show/hide error
    if (!result.valid) {
        if (errorEl) {
            errorEl.textContent = result.error;
            errorEl.style.display = 'block';
        }
    } else {
        if (errorEl) errorEl.style.display = 'none';
    }

    // Update output cards
    animateValue('out-kavl', result.kavl, -5, '');
    animateValue('out-range', result.range, 2, '°C');
    animateValue('out-approach', result.approach, 2, '°C');
    animateValue('out-m-pressure', result.P_kPa, 3, 'kPa');

    // Update charts
    requestAnimationFrame(updateMerkelCharts);
}

/**
 * Generate and render Merkel sensitivity charts.
 * Shows how KaV/L changes with L/G, altitude, and WBT.
 */
function updateMerkelCharts() {
    if (!lastMerkelResult) return;

    const { hwt, cwt, wbt, lg, alt } = lastMerkelResult;

    // Chart 1: KaV/L vs L/G ratio
    const lgCanvas = document.getElementById('chart-kavl-lg');
    if (lgCanvas) {
        const data = [];
        for (let l = 0.5; l <= 3.0; l += 0.05) {
            const r = merkelKaVL(hwt, cwt, wbt, l, alt);
            if (r.valid) data.push({ x: l, y: r.kavl });
        }
        drawLineChart(lgCanvas, {
            data,
            color: CHART_COLORS.quaternary,
            xLabel: 'L/G Ratio',
            yLabel: 'KaV/L',
            highlightX: lg,
            unit: ''
        });
    }

    // Chart 2: KaV/L vs Altitude
    const altCanvas = document.getElementById('chart-kavl-alt');
    if (altCanvas) {
        const data = [];
        for (let a = 0; a <= 2500; a += 50) {
            const r = merkelKaVL(hwt, cwt, wbt, lg, a);
            if (r.valid) data.push({ x: a, y: r.kavl });
        }
        drawLineChart(altCanvas, {
            data,
            color: CHART_COLORS.quinary,
            xLabel: 'Altitude (m)',
            yLabel: 'KaV/L',
            highlightX: alt,
            unit: ''
        });
    }

    // Chart 3: KaV/L at different WBTs (multi-line)
    const wbtCanvas = document.getElementById('chart-kavl-wbt');
    if (wbtCanvas) {
        const series = [];
        const wbts = [15, 20, 25, 30];
        const colors = [CHART_COLORS.secondary, CHART_COLORS.primary,
        CHART_COLORS.tertiary, CHART_COLORS.senary];

        for (let w = 0; w < wbts.length; w++) {
            const testWbt = wbts[w];
            if (testWbt >= cwt) continue; // Skip invalid WBTs

            const data = [];
            for (let l = 0.5; l <= 3.0; l += 0.05) {
                const r = merkelKaVL(hwt, cwt, testWbt, l, alt);
                if (r.valid) data.push({ x: l, y: r.kavl });
            }
            if (data.length > 0) {
                series.push({
                    data,
                    color: colors[w],
                    label: `WBT=${testWbt}°C`
                });
            }
        }

        drawMultiLineChart(wbtCanvas, {
            series,
            xLabel: 'L/G Ratio',
            yLabel: 'KaV/L'
        });
    }
}

// ============================================================
// UI UTILITIES
// ============================================================

/**
 * Animate a value change in an output element.
 * @param {string} id - Element ID
 * @param {number} value - Target value
 * @param {number} decimals - Decimal places
 * @param {string} unit - Unit label
 */
function animateValue(id, value, decimals, unit) {
    const el = document.getElementById(id);
    if (!el) return;

    const valueSpan = el.querySelector('.result-value') || el;
    const unitSpan = el.querySelector('.result-unit');

    // Flash animation
    el.closest('.result-card')?.classList.add('flash');
    setTimeout(() => {
        el.closest('.result-card')?.classList.remove('flash');
    }, 300);

    if (value === undefined || value === null || isNaN(value)) {
        valueSpan.textContent = '—';
    } else if (decimals < 0) {
        // Strip trailing zeros (matches CTI display: 2.22240 → "2.2224", 4.20495 → "4.20495")
        valueSpan.textContent = parseFloat(value.toFixed(-decimals)).toString();
    } else {
        valueSpan.textContent = value.toFixed(decimals);
    }

    if (unitSpan && unit) {
        unitSpan.textContent = unit;
    }
}

/**
 * Simple debounce function.
 * @param {Function} fn - Function to debounce
 * @param {number} ms - Delay in milliseconds
 * @returns {Function} Debounced function
 */
function debounce(fn, ms) {
    let timer;
    return (...args) => {
        clearTimeout(timer);
        timer = setTimeout(() => fn(...args), ms);
    };
}
