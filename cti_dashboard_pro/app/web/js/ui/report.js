// ── Filter-Excel Parser (auto-fill test conditions) ───────────────────────

/**
 * Wire the filter-excel upload UI in the Report Builder tab.
 * Call once from bindEvents.
 */
export function bindFilterUpload(ui) {
    const fileInput  = document.getElementById('rep-filter-upload');
    const parseBtn   = document.getElementById('rep-parse-excel-btn');
    const uploadLbl  = document.getElementById('rep-filter-upload-label');
    const previewEl  = document.getElementById('rep-parsed-preview');
    const statusEl   = document.getElementById('rep-parse-status');

    if (!fileInput || !parseBtn) return;

    fileInput.addEventListener('change', () => {
        const f = fileInput.files[0];
        if (f) {
            uploadLbl.textContent = f.name;
            parseBtn.disabled = false;
        } else {
            uploadLbl.textContent = 'Click to select Master Filtered Excel (.xlsx)';
            parseBtn.disabled = true;
        }
        previewEl.classList.add('hidden');
        if (statusEl) { statusEl.classList.add('hidden'); }
    });

    parseBtn.addEventListener('click', async () => {
        const f = fileInput.files[0];
        if (!f) return;

        parseBtn.textContent = 'Parsing…';
        parseBtn.disabled = true;
        previewEl.classList.add('hidden');
        if (statusEl) { statusEl.classList.add('hidden'); statusEl.className = 'text-[10px] hidden'; }

        try {
            const formData = new FormData();
            formData.append('file', f);

            const resp = await fetch('/api/parse-filter-excel', { method: 'POST', body: formData });
            if (!resp.ok) {
                const err = await resp.json().catch(() => ({}));
                throw new Error(err.detail || `Server error ${resp.status}`);
            }
            const data = await resp.json();

            const fills = [
                { id: 'rep-cwt',      val: data.cwt,       label: 'CWT',       unit: '°C' },
                { id: 'rep-hwt',      val: data.hwt,       label: 'HWT',       unit: '°C' },
                { id: 'rep-test-wbt', val: data.wbt,       label: 'WBT',       unit: '°C' },
                { id: 'rep-flow',     val: data.flow,      label: 'Flow',      unit: 'm³/hr' },
                { id: 'rep-test-fanpow', val: data.fan_power, label: 'Fan Power', unit: 'kW' },
            ];

            let filled = 0;
            previewEl.innerHTML = '';
            for (const { id, val, label, unit } of fills) {
                if (val == null) continue;
                const el = document.getElementById(id);
                if (el) { el.value = val; filled++; }

                const card = document.createElement('div');
                card.className = 'bg-slate-900/60 rounded-xl p-2 border border-cyan-500/20 text-center';
                card.innerHTML = `<p class="text-[9px] text-slate-500 uppercase tracking-widest font-bold">${label}</p>
                                  <p class="text-sm font-black text-cyan-300 font-mono">${val} <span class="text-[10px] text-slate-500">${unit}</span></p>`;
                previewEl.appendChild(card);
            }

            previewEl.classList.toggle('hidden', filled === 0);

            if (statusEl) {
                statusEl.textContent = filled > 0
                    ? `Filled ${filled} field(s) from ${f.name}. Review before generating.`
                    : 'No CWT/HWT/WBT columns found in this file. Please fill test conditions manually.';
                statusEl.className = `text-[10px] ${filled > 0 ? 'text-cyan-400' : 'text-amber-400'}`;
                statusEl.classList.remove('hidden');
            }

            updateAtcPreview(ui);

        } catch (err) {
            if (statusEl) {
                statusEl.textContent = `Parse error: ${err.message}`;
                statusEl.className = 'text-[10px] text-rose-400';
                statusEl.classList.remove('hidden');
            }
        } finally {
            parseBtn.textContent = 'Parse & Auto-Fill';
            parseBtn.disabled = false;
        }
    });
}


// ── Helpers ────────────────────────────────────────────────────────────────

function _v(id, fallback = '') {
    const el = document.getElementById(id);
    if (!el) return fallback;
    return el.value ?? fallback;
}

function _n(id, fallback = 0) {
    const v = parseFloat(_v(id, String(fallback)));
    return isFinite(v) ? v : fallback;
}

function _lines(id) {
    return _v(id, '').split('\n').map(s => s.trim()).filter(Boolean);
}

// ── Build shared design params object ──────────────────────────────────────

function _getDesign(ui) {
    const designFlow = _n('rep-design-flow', 3863.6);
    return {
        wbt:              _n('rep-design-wbt',    29),
        cwt:              _n('rep-design-cwt',    33),
        hwt:              _n('rep-design-hwt',    43),
        flow:             designFlow,
        fan_power:        _n('rep-design-fanpow', 117),
        lg:               _n('rep-design-lg',     ui?.inputs?.lgRatio ?? 1.5),
        constant_c:       _n('rep-design-c',      ui?.inputs?.constantC ?? 1.2),
        constant_m:       _n('rep-design-m',      ui?.inputs?.constantM ?? 0.6),
        density_override: _n('rep-density-override', 0) || null,
    };
}

// ── Build ATC-105 API payload for one test ─────────────────────────────────
// C and M come from Step 3 design fields (synced from Thermal Analysis tab),
// making the cross-plots tower-specific rather than using generic defaults.

function _buildPayloadForTest(design, test) {
    return {
        design_wbt:             design.wbt,
        design_cwt:             design.cwt,
        design_hwt:             design.hwt,
        design_flow:            design.flow,
        design_fan_power:       design.fan_power,
        test_wbt:               test.wbt,
        test_cwt:               test.cwt,
        test_hwt:               test.hwt,
        test_flow:              test.flow,
        test_fan_power:         test.fan_power,
        lg_ratio:               design.lg,
        constant_c:             design.constant_c,
        constant_m:             design.constant_m,
        density_ratio_override: design.density_override,
    };
}

// ── Live ATC-105 Preview (current test = Test 3 / distribution) ────────────

export async function updateAtcPreview(ui) {
    const previewEl = document.getElementById('atcPreview');
    if (!previewEl) return;

    const design = _getDesign(ui);
    if (!design.flow) { previewEl.classList.add('hidden'); return; }

    const currentTest = {
        wbt:       _n('rep-test-wbt',    21.7),
        cwt:       _n('rep-cwt',         32.4),
        hwt:       _n('rep-hwt',         42.13),
        flow:      _n('rep-flow',        3680),
        fan_power: _n('rep-test-fanpow', 117),
    };

    try {
        const resp = await fetch('/api/calculate/atc105', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(_buildPayloadForTest(design, currentTest)),
        });
        if (!resp.ok) return;
        const r = await resp.json();

        document.getElementById('atc-prev-range').innerText      = `${r.test_range?.toFixed(2) ?? '—'} °C`;
        document.getElementById('atc-prev-adjflow').innerText    = r.adj_flow?.toFixed(1)  ?? '—';
        document.getElementById('atc-prev-predcwt').innerText    = r.pred_cwt?.toFixed(2)  ?? '—';
        document.getElementById('atc-prev-shortfall').innerText  = r.shortfall?.toFixed(2) ?? '—';
        document.getElementById('atc-prev-capability').innerText = r.capability != null ? `${r.capability.toFixed(1)} %` : '—';

        previewEl.classList.remove('hidden');
    } catch (_) { /* silently ignore preview errors */ }
}

// ── Sync design params from Thermal Analysis tab ──────────────────────────

export function syncDesignFromThermal(ui) {
    const map = {
        'rep-design-wbt':  'designWBT',
        'rep-design-cwt':  'designCWT',
        'rep-design-hwt':  'designHWT',
        'rep-design-flow': 'designWaterFlow',
        'rep-design-lg':   'lgRatio',
        'rep-design-c':    'constantC',
        'rep-design-m':    'constantM',
    };
    Object.entries(map).forEach(([repId, uiKey]) => {
        const el = document.getElementById(repId);
        if (el && ui.inputs[uiKey] !== undefined) {
            el.value = ui.inputs[uiKey];
        }
    });
    updateAtcPreview(ui);
}

// ── Fetch ATC-105 result for one test ──────────────────────────────────────

async function _calcAtc(design, test) {
    const resp = await fetch('/api/calculate/atc105', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(_buildPayloadForTest(design, test)),
    });
    if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail || `ATC-105 API error ${resp.status}`);
    }
    return resp.json();
}

// ── Calculation walkthrough builder ───────────────────────────────────────

function _buildCalcHtml(d, t, r) {
    if (r.adj_flow == null || r.pred_cwt == null) return '';
    const f2 = v => (v != null ? Number(v).toFixed(2) : '—');
    const f1 = v => (v != null ? Number(v).toFixed(1) : '—');
    const f4 = v => (v != null ? Number(v).toFixed(4) : '—');

    const sfColor  = r.shortfall >= 0 ? 'text-rose-400' : 'text-emerald-400';
    const capColor = r.capability >= 100 ? 'text-emerald-400' : r.capability >= 95 ? 'text-amber-400' : 'text-rose-400';

    // Combined flow correction = (P_fan_design/P_fan_test)^(1/3) × (ρ_test/ρ_design)^(1/3)
    const totalCorr  = r.adj_flow / t.flow;
    const avgTestT   = (t.hwt + t.cwt) / 2;
    const avgDesignT = (d.hwt + d.cwt) / 2;

    return `
<div class="mt-1 pt-3 border-t border-violet-500/15 space-y-3 text-[10px] font-mono">
  <p class="text-[8px] font-black uppercase tracking-widest text-violet-400/60 mb-1">— ATC-105 Calculation Steps —</p>

  <div class="space-y-0.5">
    <p class="text-[8px] font-bold uppercase tracking-widest text-violet-400/80">① Test Range</p>
    <p class="text-slate-400">HWT − CWT = <span class="text-slate-300">${f2(t.hwt)}</span> − <span class="text-slate-300">${f2(t.cwt)}</span> = <span class="text-white font-bold">${f2(r.test_range)} °C</span></p>
    <p class="text-[9px] text-slate-600">Actual temperature drop across the tower during this test.</p>
  </div>

  <div class="space-y-0.5">
    <p class="text-[8px] font-bold uppercase tracking-widest text-violet-400/80">② Adjusted Water Flow</p>
    <p class="text-slate-400">Mean test water = (${f2(t.hwt)} + ${f2(t.cwt)}) / 2 = <span class="text-slate-300">${f2(avgTestT)} °C</span></p>
    <p class="text-slate-400">Mean design water = (${f2(d.hwt)} + ${f2(d.cwt)}) / 2 = <span class="text-slate-300">${f2(avgDesignT)} °C</span></p>
    <p class="text-slate-400">Correction = (P_fan_des/P_fan_test)^⅓ × (ρ_test/ρ_des)^⅓ = <span class="text-slate-300">${f4(totalCorr)}</span></p>
    <p class="text-slate-400 pl-2 text-[9px] text-slate-500">= (${f2(d.fan_power)}/${f2(t.fan_power)})^⅓ × Kell-density-ratio^⅓</p>
    <p class="text-slate-400">Q_adj = ${f1(t.flow)} × ${f4(totalCorr)} = <span class="text-white font-bold">${f1(r.adj_flow)} m³/hr</span></p>
    <p class="text-[9px] text-slate-600">Normalises flow to design fan power and water density conditions.</p>
  </div>

  <div class="space-y-0.5">
    <p class="text-[8px] font-bold uppercase tracking-widest text-violet-400/80">③ Predicted CWT — Cross Plot 1</p>
    <p class="text-slate-400">Tower curve: KaV/L = C × (L/G)^−m = <span class="text-violet-300">${f2(d.constant_c)}</span> × (L/G)^−<span class="text-violet-300">${f2(d.constant_m)}</span></p>
    <p class="text-slate-400">Merkel KaV/L computed at: WBT=${f2(t.wbt)}°C · HWT=${f2(t.hwt)}°C · CWT=${f2(t.cwt)}°C · L/G=${f2(d.lg)}</p>
    <p class="text-slate-400">At Q_adj = ${f1(r.adj_flow)} m³/hr on Cross Plot 1:</p>
    <p class="text-slate-400">→ Pred. CWT = <span class="text-cyan-300 font-bold">${f2(r.pred_cwt)} °C</span></p>
    <p class="text-[9px] text-slate-600">Cross-plot built from this tower's own C &amp; M — synced from Thermal Analysis.</p>
  </div>

  <div class="space-y-0.5">
    <p class="text-[8px] font-bold uppercase tracking-widest text-violet-400/80">④ Shortfall</p>
    <p class="text-slate-400">Test CWT − Pred. CWT = <span class="text-slate-300">${f2(t.cwt)}</span> − <span class="text-slate-300">${f2(r.pred_cwt)}</span> = <span class="${sfColor} font-bold">${f2(r.shortfall)} °C</span></p>
    <p class="text-[9px] text-slate-600">+ve = actual CWT higher than tower should achieve → underperforming.</p>
  </div>

  <div class="space-y-0.5">
    <p class="text-[8px] font-bold uppercase tracking-widest text-violet-400/80">⑤ Capability — Cross Plot 2 (ATC-105 Appendix C)</p>
    <p class="text-slate-400">Horizontal from Test CWT (${f2(t.cwt)} °C) → intersects curve → pred_flow</p>
    <p class="text-slate-400">(Q_adj / pred_flow) × 100 = <span class="${capColor} font-bold">${f1(r.capability)} %</span></p>
    <p class="text-[9px] text-slate-600">≥100% = adjusted flow exceeds predicted flow → tower meets specification.</p>
  </div>
</div>`;
}

// ── Results preview (all 3 tests, no PDF) ─────────────────────────────────

export async function previewAllTests(ui) {
    const btn      = document.getElementById('previewAllTestsBtn');
    const panel    = document.getElementById('previewResultsPanel');
    const errorEl  = document.getElementById('previewError');
    const origHtml = btn.innerHTML;

    const _set = (id, val) => { const el = document.getElementById(id); if (el) el.innerText = val; };

    const _imp = (delta) => {
        if (delta == null || !isFinite(delta)) return { text: '—', cls: 'text-slate-500' };
        const sign = delta >= 0 ? '+' : '';
        const cls  = delta > 0 ? 'text-emerald-400' : delta < 0 ? 'text-rose-400' : 'text-slate-400';
        return { text: `${sign}${delta.toFixed(2)} °C`, cls };
    };

    btn.innerHTML = `<svg class="animate-spin w-4 h-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path></svg> Calculating…`;
    btn.disabled = true;
    if (errorEl) errorEl.classList.add('hidden');

    try {
        const design = _getDesign(ui);
        if (!design.flow) throw new Error('Design flow (Step 3) is required.');

        const t1 = { flow: _n('rep-t1-flow',2998),    wbt: _n('rep-t1-wbt',25.25),  hwt: _n('rep-t1-hwt',44.67), cwt: _n('rep-t1-cwt',35.08), fan_power: _n('rep-t1-fanpow',97.04) };
        const t2 = { flow: _n('rep-t2-flow',3067.21),  wbt: _n('rep-t2-wbt',24.22),  hwt: _n('rep-t2-hwt',43.21), cwt: _n('rep-t2-cwt',32.89), fan_power: _n('rep-t2-fanpow',116.24) };
        const t3 = { flow: _n('rep-flow',3680),         wbt: _n('rep-test-wbt',21.7), hwt: _n('rep-hwt',42.13),   cwt: _n('rep-cwt',32.4),     fan_power: _n('rep-test-fanpow',117) };

        const [r1, r2, r3] = await Promise.all([
            _calcAtc(design, t1), _calcAtc(design, t2), _calcAtc(design, t3),
        ]);

        // Populate TEST 1
        _set('pv1-range',    r1.test_range  != null ? `${r1.test_range.toFixed(2)} °C`  : '—');
        _set('pv1-flow',     r1.adj_flow    != null ? `${r1.adj_flow.toFixed(1)} m³/hr` : '—');
        _set('pv1-cwt',      r1.pred_cwt    != null ? `${r1.pred_cwt.toFixed(2)} °C`    : '—');
        _set('pv1-shortfall',r1.shortfall   != null ? `${r1.shortfall.toFixed(2)} °C`   : '—');
        _set('pv1-cap',      r1.capability  != null ? `${r1.capability.toFixed(1)} %`   : '—');

        // Colour capability
        ['pv1-cap','pv2-cap','pv3-cap'].forEach(id => {
            const el = document.getElementById(id); if (!el) return;
            const v = parseFloat(el.innerText);
            el.className = `font-mono font-bold ${v >= 100 ? 'text-emerald-400' : v >= 95 ? 'text-amber-400' : 'text-rose-400'}`;
        });

        // Populate TEST 2
        _set('pv2-range',    r2.test_range  != null ? `${r2.test_range.toFixed(2)} °C`  : '—');
        _set('pv2-flow',     r2.adj_flow    != null ? `${r2.adj_flow.toFixed(1)} m³/hr` : '—');
        _set('pv2-cwt',      r2.pred_cwt    != null ? `${r2.pred_cwt.toFixed(2)} °C`    : '—');
        _set('pv2-shortfall',r2.shortfall   != null ? `${r2.shortfall.toFixed(2)} °C`   : '—');
        _set('pv2-cap',      r2.capability  != null ? `${r2.capability.toFixed(1)} %`   : '—');

        // Populate TEST 3
        _set('pv3-range',    r3.test_range  != null ? `${r3.test_range.toFixed(2)} °C`  : '—');
        _set('pv3-flow',     r3.adj_flow    != null ? `${r3.adj_flow.toFixed(1)} m³/hr` : '—');
        _set('pv3-cwt',      r3.pred_cwt    != null ? `${r3.pred_cwt.toFixed(2)} °C`    : '—');
        _set('pv3-shortfall',r3.shortfall   != null ? `${r3.shortfall.toFixed(2)} °C`   : '—');
        _set('pv3-cap',      r3.capability  != null ? `${r3.capability.toFixed(1)} %`   : '—');

        // Re-colour capability after all are set
        [['pv1-cap', r1.capability], ['pv2-cap', r2.capability], ['pv3-cap', r3.capability]].forEach(([id, v]) => {
            const el = document.getElementById(id); if (!el || v == null) return;
            el.className = `font-mono font-bold ${v >= 100 ? 'text-emerald-400' : v >= 95 ? 'text-amber-400' : 'text-rose-400'}`;
        });

        // Improvement deltas
        const imp21 = (r1.shortfall != null && r2.shortfall != null) ? r1.shortfall - r2.shortfall : null;
        const imp32 = (r2.shortfall != null && r3.shortfall != null) ? r2.shortfall - r3.shortfall : null;
        const imp31 = (r1.shortfall != null && r3.shortfall != null) ? r1.shortfall - r3.shortfall : null;

        const d21 = _imp(imp21); const d32 = _imp(imp32); const d31 = _imp(imp31);

        const pv2imp = document.getElementById('pv2-imp');
        if (pv2imp) { pv2imp.innerText = d21.text; pv2imp.className = `text-[11px] font-mono font-black ${d21.cls}`; }

        const pv3imp = document.getElementById('pv3-imp');
        if (pv3imp) { pv3imp.innerText = d32.text; pv3imp.className = `text-[11px] font-mono font-black ${d32.cls}`; }

        const pvCum = document.getElementById('pv-cumulative');
        if (pvCum) { pvCum.innerText = d31.text; pvCum.className = `text-2xl font-black font-mono ${d31.cls}`; }

        if (panel) panel.classList.remove('hidden');

        // Inject calculation breakdowns and wire toggle buttons
        [
            ['pv1', design, t1, r1],
            ['pv2', design, t2, r2],
            ['pv3', design, t3, r3],
        ].forEach(([prefix, d, t, r]) => {
            const calcDiv = document.getElementById(`${prefix}-calc`);
            const calcBtn = document.getElementById(`${prefix}-calc-btn`);
            if (!calcDiv || !calcBtn) return;
            calcDiv.innerHTML = _buildCalcHtml(d, t, r);
            calcBtn.classList.remove('hidden');
            calcBtn.classList.add('inline-flex');
            calcBtn.onclick = () => {
                const collapsed = calcDiv.classList.toggle('hidden');
                calcBtn.querySelector('span').textContent = collapsed ? '∑ Calc' : '∑ Hide';
                calcBtn.style.opacity = collapsed ? '' : '1';
                calcBtn.style.borderColor = collapsed ? '' : 'rgb(167 139 250 / 0.6)';
            };
        });

        // Also update the live Test-3 preview card at top of Step 3
        ['atc-prev-range','atc-prev-adjflow','atc-prev-predcwt','atc-prev-shortfall','atc-prev-capability'].forEach(id => {
            const el = document.getElementById(id); if (!el) return;
        });
        const pv = document.getElementById('atcPreview');
        if (pv) {
            _set('atc-prev-range',      r3.test_range  != null ? `${r3.test_range.toFixed(2)} °C` : '—');
            _set('atc-prev-adjflow',    r3.adj_flow    != null ? r3.adj_flow.toFixed(1)           : '—');
            _set('atc-prev-predcwt',    r3.pred_cwt    != null ? r3.pred_cwt.toFixed(2)           : '—');
            _set('atc-prev-shortfall',  r3.shortfall   != null ? r3.shortfall.toFixed(2)          : '—');
            _set('atc-prev-capability', r3.capability  != null ? `${r3.capability.toFixed(1)} %`  : '—');
            pv.classList.remove('hidden');
        }

    } catch (err) {
        if (errorEl) { errorEl.innerText = `Preview failed: ${err.message}`; errorEl.classList.remove('hidden'); }
    } finally {
        btn.innerHTML = origHtml;
        btn.disabled = false;
    }
}

// ── Main report generator ──────────────────────────────────────────────────

export async function generateReport(ui) {
    const btn = document.getElementById('generateReportBtn');
    const statusEl = document.getElementById('reportStatus');
    const originalHtml = btn.innerHTML;

    const setStatus = (msg, isError = false) => {
        if (statusEl) {
            statusEl.innerText = msg;
            statusEl.classList.remove('hidden', 'text-cyan-400', 'text-rose-400');
            statusEl.classList.add(isError ? 'text-rose-400' : 'text-cyan-400');
        }
    };

    btn.innerHTML = `<svg class="animate-spin w-5 h-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path></svg>
        Calculating ATC-105 (3 tests)…`;
    btn.disabled = true;
    setStatus('Running ATC-105 calculations for all 3 tests…');

    try {
        // ── Shared design conditions ──────────────────────────────────────
        const design = _getDesign(ui);
        if (!design.flow) throw new Error('Design flow is required.');

        // ── Three test datasets ───────────────────────────────────────────
        const t1 = {
            flow:      _n('rep-t1-flow',   2998),
            wbt:       _n('rep-t1-wbt',    25.25),
            hwt:       _n('rep-t1-hwt',    44.67),
            cwt:       _n('rep-t1-cwt',    35.08),
            fan_power: _n('rep-t1-fanpow', 97.04),
        };
        const t2 = {
            flow:      _n('rep-t2-flow',   3067.21),
            wbt:       _n('rep-t2-wbt',    24.22),
            hwt:       _n('rep-t2-hwt',    43.21),
            cwt:       _n('rep-t2-cwt',    32.89),
            fan_power: _n('rep-t2-fanpow', 116.24),
        };
        const t3 = {
            flow:      _n('rep-flow',        3680),
            wbt:       _n('rep-test-wbt',    21.7),
            hwt:       _n('rep-hwt',         42.13),
            cwt:       _n('rep-cwt',         32.4),
            fan_power: _n('rep-test-fanpow', 117),
        };

        // ── Run all 3 ATC-105 calculations in parallel ────────────────────
        const [atc_pre, atc_post, atc_dist] = await Promise.all([
            _calcAtc(design, t1),
            _calcAtc(design, t2),
            _calcAtc(design, t3),
        ]);

        // Annotate fan powers (not in API response; needed for Step 4 table)
        atc_pre.fan_power_design  = design.fan_power;
        atc_pre.fan_power_test    = t1.fan_power;
        atc_post.fan_power_design = design.fan_power;
        atc_post.fan_power_test   = t2.fan_power;
        atc_dist.fan_power_design = design.fan_power;
        atc_dist.fan_power_test   = t3.fan_power;

        // Update live preview with Test 3 (current / distribution)
        const pv = document.getElementById('atcPreview');
        if (pv) {
            document.getElementById('atc-prev-range').innerText      = `${atc_dist.test_range?.toFixed(2) ?? '—'} °C`;
            document.getElementById('atc-prev-adjflow').innerText    = atc_dist.adj_flow?.toFixed(1)  ?? '—';
            document.getElementById('atc-prev-predcwt').innerText    = atc_dist.pred_cwt?.toFixed(2)  ?? '—';
            document.getElementById('atc-prev-shortfall').innerText  = atc_dist.shortfall?.toFixed(2) ?? '—';
            document.getElementById('atc-prev-capability').innerText = atc_dist.capability != null ? `${atc_dist.capability.toFixed(1)} %` : '—';
            pv.classList.remove('hidden');
        }

        btn.innerHTML = `<svg class="animate-spin w-5 h-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path></svg>
            Generating PDF…`;
        setStatus('ATC-105 calculated for all tests. Rendering PDF…');

        // ── Derived values ────────────────────────────────────────────────
        // Air flow is no longer a UI input; fan area is still collected for
        // velocity calculation if needed, but air flow rows are omitted from table.
        const airArea = _n('rep-fan-area', 92.25);

        const sf1 = atc_pre.shortfall;
        const sf2 = atc_post.shortfall;
        const sf3 = atc_dist.shortfall;

        const imp_2v1  = (sf1 != null && sf2 != null) ? parseFloat((sf1 - sf2).toFixed(2)) : '—';
        const imp_3v2  = (sf2 != null && sf3 != null) ? parseFloat((sf2 - sf3).toFixed(2)) : '—';
        const imp_3v1  = (sf1 != null && sf3 != null) ? parseFloat((sf1 - sf3).toFixed(2)) : '—';

        // ── Multi-test comparison table (all 3 shortfalls now populated) ──
        const final_data_table = [
            { name: 'Water Flow',               unit: 'M3/hr',
              test1: t1.flow,   test2: t2.flow,   test3: t3.flow },
            { name: 'WBT',                      unit: 'Deg.C',
              test1: t1.wbt,    test2: t2.wbt,    test3: t3.wbt },
            { name: 'HWT',                      unit: 'Deg.C',
              test1: t1.hwt,    test2: t2.hwt,    test3: t3.hwt },
            { name: 'CWT',                      unit: 'Deg.C',
              test1: t1.cwt,    test2: t2.cwt,    test3: t3.cwt },
            { name: 'Fan Power At Motor Inlet', unit: 'KW',
              test1: t1.fan_power, test2: t2.fan_power, test3: t3.fan_power },
            { name: 'Range',                    unit: 'Deg.C',
              test1: parseFloat((t1.hwt - t1.cwt).toFixed(2)),
              test2: parseFloat((t2.hwt - t2.cwt).toFixed(2)),
              test3: parseFloat((t3.hwt - t3.cwt).toFixed(2)) },
            { name: 'Approach',                 unit: 'Deg.C',
              test1: parseFloat((t1.cwt - t1.wbt).toFixed(2)),
              test2: parseFloat((t2.cwt - t2.wbt).toFixed(2)),
              test3: parseFloat((t3.cwt - t3.wbt).toFixed(2)) },
            { name: 'CWT Deviation from Design', unit: 'Deg.C',
              test1: sf1 != null ? sf1.toFixed(2) : '—',
              test2: sf2 != null ? sf2.toFixed(2) : '—',
              test3: sf3 != null ? sf3.toFixed(2) : '—' },
            { name: 'Capability',               unit: '%',
              test1: atc_pre.capability  != null ? atc_pre.capability.toFixed(1)  : '—',
              test2: atc_post.capability != null ? atc_post.capability.toFixed(1) : '—',
              test3: atc_dist.capability != null ? atc_dist.capability.toFixed(1) : '—' },
            { name: 'Improvement vs Previous Test', unit: 'Deg.C',
              test1: '—', test2: imp_2v1, test3: imp_3v2 },
            { name: 'Cumulative Improvement vs Test 1', unit: 'Deg.C',
              test1: '—', test2: imp_2v1, test3: imp_3v1 },
        ];

        // ── Full PDF payload ──────────────────────────────────────────────
        const pdfPayload = {
            // Cover
            report_title: _v('rep-title', 'CT PERFORMANCE EVALUATION REPORT'),
            client:       _v('rep-client'),
            asset:        _v('rep-asset'),
            test_date:    _v('rep-test-date'),
            report_date:  _v('rep-report-date'),

            // Narrative
            preamble_paragraphs: _lines('rep-preamble'),
            conclusions:         _lines('rep-conclusions'),
            members_client:      _lines('rep-members-client'),
            members_ssctc:       _lines('rep-members-ssctc'),

            // Standard sections
            assessment_method: [
                `Pre test was conducted on ${_v('rep-test-date')}.`,
                'Cell has been isolated at the basin level for collection of cold water directly from the rain zone.',
                'All required data was collected and reports have been prepared for each test stage.',
                'Since different conditions apply in each test, both pre and post tests have been compared to the design conditions. The difference between pre and post tests has been established accordingly.',
            ],
            instrument_placement: [
                'Air flow was measured using Data Logging anemometer as per CTI ATC-143 Method of equal area — 10 traverses per quadrant (40 readings total for one fan).',
                'Hot water temperature was taken at inlet of the hot water to the cooling tower.',
                'Cold water temperature: 24 RTD sensors placed at air-inlet sides of the isolated cell (12 per side).',
                'Water flow was measured using UFM (GE Make) on the riser.',
                'WBT/DBT was measured using wet-bulb automatic stations recording every minute.',
                'Power to the fan motor was noted from the client MCC.',
            ],
            suggestions: _lines('rep-data-notes'),

            // Three independent ATC-105 analyses
            atc105_pre:  atc_pre,
            atc105_post: atc_post,
            atc105_dist: atc_dist,

            // Comparison table (all three shortfalls populated)
            final_data_table,
            data_notes: _lines('rep-data-notes'),

            // Fan area (air flow no longer collected as UI input)
            airflow: {
                area: airArea,
            },
        };

        // ── POST to generate PDF (Step 1: server stores PDF, returns token) ─
        // We use a two-step token download instead of a blob:// URL so that
        // external download managers like IDM can fetch the file via a real
        // HTTP GET URL without running into the blob:// sandbox restriction.
        const safeName = _v('rep-client', 'Report').replace(/[^a-zA-Z0-9]/g, '_').slice(0, 40);
        const filename  = `ATC105_${safeName}_${_v('rep-test-date', '').replace(/\s/g, '_')}.pdf`;
        pdfPayload._filename = filename;  // tell backend what filename to serve

        const pdfResp = await fetch('/api/generate-pdf-report', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(pdfPayload),
        });

        if (!pdfResp.ok) {
            const err = await pdfResp.text();
            throw new Error(`PDF generation failed (${pdfResp.status}): ${err}`);
        }

        const { token } = await pdfResp.json();

        // Step 2: navigate to the real GET URL — IDM/browsers download this
        // as a normal file without any blob:// sandbox restriction.
        window.location.href = `/api/download-pdf/${token}`;

        setStatus(`PDF generated successfully — ${filename}`);

    } catch (err) {
        console.error('Report generation failed:', err);
        setStatus(`Error: ${err.message}`, true);
        alert(`Failed to generate report:\n${err.message}`);
    } finally {
        btn.innerHTML = originalHtml;
        btn.disabled = false;
    }
}
