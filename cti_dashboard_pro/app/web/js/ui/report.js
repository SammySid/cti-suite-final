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
                card.innerHTML = `<p class="text-[10px] text-slate-400 uppercase tracking-widest font-bold">${label}</p>
                                  <p class="text-sm font-black text-cyan-300 font-mono">${val} <span class="text-xs text-slate-400">${unit}</span></p>`;
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

// ── Preview chart registry — destroyed on each re-run ─────────────────────────
const _pvCharts = {};

function _pvChart(id, config) {
    if (_pvCharts[id]) { _pvCharts[id].destroy(); delete _pvCharts[id]; }
    const canvas = document.getElementById(id);
    if (!canvas) return;
    _pvCharts[id] = new Chart(canvas, config);
}

const _pvTheme = {
    grid:  'rgba(148,163,184,0.10)',
    tick:  '#475569',
    label: '#64748b',
    text:  '#94a3b8',
};

// ── Cross Plot 1: CWT vs Range (3 flow curves + test-range marker) ─────────────
function _pvRenderCp1(canvasId, cp1, testWbt) {
    const ranges = cp1.ranges_abs.map(Number);
    const y90    = cp1.cwt_90.map(Number);
    const y100   = cp1.cwt_100.map(Number);
    const y110   = cp1.cwt_110.map(Number);
    const testR  = Number(cp1.test_range);

    const allY = [...y90, ...y100, ...y110].filter(isFinite);
    const yMin = Math.floor(Math.min(...allY) - 0.5);
    const yMax = Math.ceil(Math.max(...allY)  + 0.5);
    const xMin = Math.min(...ranges) - 0.3;
    const xMax = Math.max(...ranges) + 0.3;

    const intPts = [
        cp1.f90_cwt  != null ? { x: testR, y: Number(cp1.f90_cwt)  } : null,
        cp1.f100_cwt != null ? { x: testR, y: Number(cp1.f100_cwt) } : null,
        cp1.f110_cwt != null ? { x: testR, y: Number(cp1.f110_cwt) } : null,
    ].filter(Boolean);

    _pvChart(canvasId, {
        type: 'scatter',
        data: { datasets: [
            { label: '90% Flow',  data: ranges.map((x,i) => ({x, y: y90[i]})),  borderColor: '#7c3aed', backgroundColor: '#7c3aed', showLine: true, borderWidth: 2, pointRadius: 3, tension: 0.3, fill: false },
            { label: '100% Flow', data: ranges.map((x,i) => ({x, y: y100[i]})), borderColor: '#16a34a', backgroundColor: '#16a34a', showLine: true, borderWidth: 2, pointRadius: 3, tension: 0.3, fill: false },
            { label: '110% Flow', data: ranges.map((x,i) => ({x, y: y110[i]})), borderColor: '#2563eb', backgroundColor: '#2563eb', showLine: true, borderWidth: 2, pointRadius: 3, tension: 0.3, fill: false },
            { label: `Test Range ${testR.toFixed(2)}°C`, data: [{x:testR,y:yMin},{x:testR,y:yMax}], borderColor: '#dc2626', showLine: true, borderWidth: 1.5, borderDash: [4,3], pointRadius: 0, fill: false },
            { label: 'CP1 → CP2 Points', data: intPts, borderColor: '#f59e0b', backgroundColor: '#f59e0b', showLine: false, pointRadius: 5, pointStyle: 'circle' },
        ]},
        options: {
            responsive: true, maintainAspectRatio: false, animation: false,
            plugins: {
                legend: { display: true, position: 'top', align: 'start', labels: { color: _pvTheme.text, usePointStyle: true, font: { size: 9 }, padding: 8 } },
                tooltip: { callbacks: { label: ctx => `${ctx.dataset.label}: (${ctx.parsed.x?.toFixed(2)}, ${ctx.parsed.y?.toFixed(2)})` } },
            },
            scales: {
                x: { type: 'linear', min: xMin, max: xMax, title: { display: true, text: 'Range (°C)', color: _pvTheme.label, font: { size: 9 } }, grid: { color: _pvTheme.grid }, ticks: { color: _pvTheme.tick, font: { size: 9 } } },
                y: { min: yMin, max: yMax,                  title: { display: true, text: 'CWT (°C)',   color: _pvTheme.label, font: { size: 9 } }, grid: { color: _pvTheme.grid }, ticks: { color: _pvTheme.tick, font: { size: 9 } } },
            },
        },
    });
}

// ── Cross Plot 2: Flow vs CWT (tower performance curve + crosshair annotations) ─
function _pvRenderCp2(canvasId, cp2) {
    const flows    = cp2.flows.map(Number);
    const cwts     = cp2.cwts.map(Number);
    const adjFlow  = Number(cp2.adj_flow);
    const predCwt  = Number(cp2.pred_cwt);
    const testCwt  = Number(cp2.test_cwt);
    const predFlow = cp2.pred_flow != null ? Number(cp2.pred_flow) : null;

    const allX = [adjFlow, predFlow ?? adjFlow, ...flows];
    const allY = [predCwt, testCwt, ...cwts];
    const xMin = Math.min(...allX) * 0.94;
    const xMax = Math.max(...allX) * 1.05;
    const yMin = Math.min(...allY) - 0.5;
    const yMax = Math.max(...allY) + 0.5;

    const datasets = [
        { label: 'Tower Perf. Curve', data: flows.map((x,i) => ({x, y:cwts[i]})), borderColor: '#06b6d4', backgroundColor: '#06b6d430', showLine: true, borderWidth: 2.5, pointRadius: 5, fill: false, tension: 0 },
        { label: `Q_adj = ${adjFlow.toFixed(1)} m³/hr`, data: [{x:adjFlow,y:yMin},{x:adjFlow,y:predCwt}], borderColor: '#ea580c', showLine: true, borderWidth: 1.5, borderDash: [5,3], pointRadius: 0, fill: false },
        { label: `Pred. CWT = ${predCwt.toFixed(2)} °C`, data: [{x:xMin,y:predCwt},{x:adjFlow,y:predCwt}], borderColor: '#06b6d4', showLine: true, borderWidth: 1.5, borderDash: [5,3], pointRadius: 0, fill: false },
        { label: `Test CWT = ${testCwt.toFixed(2)} °C`, data: predFlow != null ? [{x:xMin,y:testCwt},{x:predFlow,y:testCwt}] : [], borderColor: '#dc2626', showLine: true, borderWidth: 1.5, borderDash: [5,3], pointRadius: 0, fill: false },
        { label: 'Adj.Flow → Pred.CWT', data: [{x:adjFlow,y:predCwt}], borderColor: '#ea580c', backgroundColor: '#ea580c', showLine: false, pointRadius: 7, pointStyle: 'crossRot' },
    ];
    if (predFlow != null) {
        datasets.push({ label: `Pred. Flow = ${predFlow.toFixed(0)} m³/hr`, data: [{x:predFlow,y:yMin},{x:predFlow,y:testCwt}], borderColor: '#16a34a', showLine: true, borderWidth: 1.5, borderDash: [5,3], pointRadius: 0, fill: false });
        datasets.push({ label: 'Test CWT → Pred.Flow', data: [{x:predFlow,y:testCwt}], borderColor: '#dc2626', backgroundColor: '#dc2626', showLine: false, pointRadius: 7 });
    }

    _pvChart(canvasId, {
        type: 'scatter',
        data: { datasets },
        options: {
            responsive: true, maintainAspectRatio: false, animation: false,
            plugins: {
                legend: {
                    display: true, position: 'top', align: 'start',
                    labels: { color: _pvTheme.text, usePointStyle: true, font: { size: 9 }, padding: 8,
                        filter: item => !['Adj.Flow → Pred.CWT','Test CWT → Pred.Flow'].includes(item.text) },
                },
                tooltip: { callbacks: { label: ctx => `${ctx.dataset.label}: (${ctx.parsed.x?.toFixed(1)}, ${ctx.parsed.y?.toFixed(2)})` } },
            },
            scales: {
                x: { type: 'linear', min: xMin, max: xMax, title: { display: true, text: 'Water Flow (m³/hr)', color: _pvTheme.label, font: { size: 9 } }, grid: { color: _pvTheme.grid }, ticks: { color: _pvTheme.tick, font: { size: 9 } } },
                y: { min: yMin, max: yMax,                  title: { display: true, text: 'CWT (°C)',           color: _pvTheme.label, font: { size: 9 } }, grid: { color: _pvTheme.grid }, ticks: { color: _pvTheme.tick, font: { size: 9 } } },
            },
        },
    });
}

// ── Capability bar chart ───────────────────────────────────────────────────────
function _pvRenderCapChart(caps) {
    const colors = caps.map(v => v >= 100 ? '#16a34a' : v >= 95 ? '#d97706' : '#dc2626');
    _pvChart('pv-cap-chart', {
        type: 'bar',
        data: {
            labels: ['Test 1 — Pre-Baseline', 'Test 2 — Post Fan Pitch', 'Test 3 — Post Fill Dist.'],
            datasets: [{ label: 'Capability (%)', data: caps, backgroundColor: colors.map(c => c + '40'), borderColor: colors, borderWidth: 2, borderRadius: 4 }],
        },
        options: {
            responsive: true, maintainAspectRatio: false, animation: false,
            plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => `Capability: ${ctx.parsed.y.toFixed(1)}%` } } },
            scales: {
                x: { grid: { color: _pvTheme.grid }, ticks: { color: _pvTheme.tick, font: { size: 9 } } },
                y: { min: Math.min(80, ...caps) - 3, max: Math.max(110, ...caps) + 2, grid: { color: _pvTheme.grid }, ticks: { color: _pvTheme.tick, font: { size: 9 }, callback: v => v + '%' } },
            },
        },
    });
}

// ── Trend line: shortfall + capability across 3 tests ─────────────────────────
function _pvRenderTrendChart(shortfalls, caps) {
    _pvChart('pv-trend-chart', {
        type: 'line',
        data: {
            labels: ['Test 1 (Pre)', 'Test 2 (Post Fan)', 'Test 3 (Post Fill)'],
            datasets: [
                { label: 'Shortfall (°C)', data: shortfalls, borderColor: '#f59e0b', backgroundColor: '#f59e0b18', fill: true, borderWidth: 2, pointRadius: 5, tension: 0.3, yAxisID: 'y' },
                { label: 'Capability (%)', data: caps,       borderColor: '#06b6d4', backgroundColor: 'transparent', borderWidth: 2, pointRadius: 5, tension: 0.3, yAxisID: 'y2', borderDash: [4,3] },
            ],
        },
        options: {
            responsive: true, maintainAspectRatio: false, animation: false,
            plugins: { legend: { position: 'top', align: 'end', labels: { color: _pvTheme.text, usePointStyle: true, font: { size: 9 }, padding: 12 } } },
            scales: {
                x:  { grid: { color: _pvTheme.grid }, ticks: { color: _pvTheme.tick, font: { size: 9 } } },
                y:  { position: 'left',  title: { display: true, text: 'Shortfall (°C)', color: _pvTheme.label, font: { size: 9 } }, grid: { color: _pvTheme.grid }, ticks: { color: _pvTheme.tick, font: { size: 9 } } },
                y2: { position: 'right', title: { display: true, text: 'Capability (%)', color: _pvTheme.label, font: { size: 9 } }, grid: { display: false }, ticks: { color: _pvTheme.tick, font: { size: 9 }, callback: v => v + '%' } },
            },
        },
    });
}

// ── Verdict / colour helpers ───────────────────────────────────────────────────
function _capVerdict(v)   { return v >= 100 ? 'PASS' : v >= 95 ? 'MARGINAL' : 'FAIL'; }
function _capBadgeCls(v)  { return v >= 100 ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400' : v >= 95 ? 'border-amber-500/30 bg-amber-500/10 text-amber-400' : 'border-rose-500/30 bg-rose-500/10 text-rose-400'; }
function _capTextCls(v)   { return v >= 100 ? 'text-emerald-400' : v >= 95 ? 'text-amber-400' : 'text-rose-400'; }
function _sfTextCls(v)    { return v  > 0   ? 'text-rose-400'    : v  < 0  ? 'text-emerald-400' : 'text-slate-400'; }

// ── Per-test calculation walkthrough table (injected as innerHTML) ─────────────
function _buildPvCalcTable(d, t, r) {
    const f2 = v => v != null ? Number(v).toFixed(2) : '—';
    const f1 = v => v != null ? Number(v).toFixed(1) : '—';
    const sfCls  = r.shortfall  > 0 ? 'text-rose-400'    : 'text-emerald-400';
    const capCls = r.capability >= 100 ? 'text-emerald-400' : r.capability >= 95 ? 'text-amber-400' : 'text-rose-400';

    const rows = [
        ['①', 'Test Range',              'Actual temperature drop across the tower.',                                       `HWT − CWT = ${f2(t.hwt)} − ${f2(t.cwt)}`,                             `<span class="text-slate-200 font-bold">${f2(r.test_range)} °C</span>`],
        ['②', 'Adjusted Water Flow',     'Normalise measured flow to design fan power &amp; water density (Kell 1975).',   `${f1(t.flow)} × (${f2(d.fan_power)}/${f2(t.fan_power)})^⅓ × ρ^⅓`,    `<span class="text-slate-200 font-bold">${f1(r.adj_flow)} m³/hr</span>`],
        ['③', 'Cross Plot 1 → Table 2',  'Build 3×3 CWT grid at test WBT. Interpolate at actual test range % across 3 flows → 3 CP2 curve points.',  `test_range_pct = ${f2(r.test_range_pct)}% → see CP1 chart`,   `<span class="text-slate-400">3 pts →</span>`],
        ['④', 'Pred. CWT (Cross Plot 2)','Plot Flow vs CWT from CP1 intersections. Read Predicted CWT at Q_adj on the performance curve.',            `Q_adj = ${f1(r.adj_flow)} m³/hr → on curve`,                  `<span class="text-cyan-300 font-bold">${f2(r.pred_cwt)} °C</span>`],
        ['⑤', 'Shortfall',               '+ve = underperforming. −ve = tower exceeds spec.',                                                          `Test CWT ${f2(t.cwt)} − Pred. CWT ${f2(r.pred_cwt)}`,         `<span class="${sfCls} font-bold">${r.shortfall > 0 ? '+' : ''}${f2(r.shortfall)} °C</span>`],
        ['⑥', 'Capability (ATC-105 §C)', '≥ 100% = tower meets contractual thermal rating.',                                                          `Q_adj / Q_pred_at_testCWT × 100 = ${f1(r.adj_flow)} / ${f1(r.pred_flow)} × 100`, `<span class="${capCls} font-bold">${f1(r.capability)} %</span>`],
    ];

    return `<table class="w-full divide-y divide-white/5">
        <thead class="bg-slate-900/60">
            <tr>
                <th class="px-3 py-2 text-left text-[10px] font-black uppercase tracking-widest text-slate-500 w-6">#</th>
                <th class="px-3 py-2 text-left text-[10px] font-black uppercase tracking-widest text-slate-400">Step</th>
                <th class="px-3 py-2 text-left text-[10px] font-black uppercase tracking-widest text-slate-400 hidden md:table-cell">What It Means</th>
                <th class="px-3 py-2 text-left text-[10px] font-black uppercase tracking-widest text-slate-400 hidden lg:table-cell">Formula / Working</th>
                <th class="px-3 py-2 text-right text-[10px] font-black uppercase tracking-widest text-slate-400">Result</th>
            </tr>
        </thead>
        <tbody class="divide-y divide-white/[0.04]">
            ${rows.map(([n, step, meaning, formula, result]) => `
            <tr class="hover:bg-white/[0.02]">
                <td class="px-3 py-2.5 text-xs font-mono text-slate-500">${n}</td>
                <td class="px-3 py-2.5 text-xs font-mono text-slate-200 font-bold whitespace-nowrap">${step}</td>
                <td class="px-3 py-2.5 text-xs text-slate-400 hidden md:table-cell leading-relaxed">${meaning}</td>
                <td class="px-3 py-2.5 text-[11px] font-mono text-slate-400 hidden lg:table-cell">${formula}</td>
                <td class="px-3 py-2.5 text-xs font-mono text-right">${result}</td>
            </tr>`).join('')}
        </tbody>
    </table>`;
}

// ── Multi-test comparison table (injected as innerHTML) ────────────────────────
function _buildComparisonTable(t1, t2, t3, r1, r2, r3) {
    const f2 = v => v != null ? Number(v).toFixed(2) : '—';
    const f1 = v => v != null ? Number(v).toFixed(1) : '—';
    const imp21 = r1.shortfall != null && r2.shortfall != null ? (r1.shortfall - r2.shortfall).toFixed(2) : '—';
    const imp32 = r2.shortfall != null && r3.shortfall != null ? (r2.shortfall - r3.shortfall).toFixed(2) : '—';
    const imp31 = r1.shortfall != null && r3.shortfall != null ? (r1.shortfall - r3.shortfall).toFixed(2) : '—';

    const capCls = v => { const n = parseFloat(v); return n >= 100 ? 'text-emerald-400' : n >= 95 ? 'text-amber-400' : 'text-rose-400'; };
    const sfCls  = v => { const n = parseFloat(v); return n > 0 ? 'text-rose-400' : n < 0 ? 'text-emerald-400' : 'text-slate-400'; };
    const impCls = v => { const n = parseFloat(v); return n > 0 ? 'text-emerald-400' : n < 0 ? 'text-rose-400' : 'text-slate-400'; };

    const rows = [
        ['Water Flow',                   'm³/hr', f1(t1.flow),       f1(t2.flow),       f1(t3.flow),       ''],
        ['WBT — Wet Bulb Temp.',         '°C',    f2(t1.wbt),        f2(t2.wbt),        f2(t3.wbt),        ''],
        ['HWT — Hot Water Temp.',        '°C',    f2(t1.hwt),        f2(t2.hwt),        f2(t3.hwt),        ''],
        ['CWT — Cold Water Temp.',       '°C',    f2(t1.cwt),        f2(t2.cwt),        f2(t3.cwt),        ''],
        ['Fan Power at Motor Inlet',     'kW',    f2(t1.fan_power),  f2(t2.fan_power),  f2(t3.fan_power),  ''],
        ['Range (HWT−CWT)',              '°C',    f2(r1.test_range), f2(r2.test_range), f2(r3.test_range), ''],
        ['Approach (CWT−WBT)',           '°C',    f2(t1.cwt-t1.wbt),f2(t2.cwt-t2.wbt),f2(t3.cwt-t3.wbt),''],
        ['Adjusted Water Flow',          'm³/hr', f1(r1.adj_flow),   f1(r2.adj_flow),   f1(r3.adj_flow),   ''],
        ['Predicted CWT (CP2)',          '°C',    f2(r1.pred_cwt),   f2(r2.pred_cwt),   f2(r3.pred_cwt),   ''],
        ['CWT Shortfall (Deviation)',    '°C',    `${r1.shortfall > 0 ? '+' : ''}${f2(r1.shortfall)}`, `${r2.shortfall > 0 ? '+' : ''}${f2(r2.shortfall)}`, `${r3.shortfall > 0 ? '+' : ''}${f2(r3.shortfall)}`, 'sf'],
        ['Capability',                   '%',     f1(r1.capability), f1(r2.capability), f1(r3.capability), 'cap'],
        ['Improvement vs Previous Test', '°C',    '—',               imp21 !== '—' ? `+${imp21}` : '—', imp32 !== '—' ? `+${imp32}` : '—', 'imp'],
        ['Cumulative Improvement vs T1', '°C',    '—',               imp21 !== '—' ? `+${imp21}` : '—', imp31 !== '—' ? `+${imp31}` : '—', 'imp'],
    ];

    const rowHtml = rows.map(([param, unit, v1, v2, v3, type]) => {
        const bg   = type === 'sf' ? 'bg-yellow-500/5' : type === 'imp' ? 'bg-emerald-500/5' : '';
        const c1   = type === 'cap' ? capCls(v1) : type === 'sf' ? sfCls(v1)  : type === 'imp' ? impCls(v1) : 'text-slate-300';
        const c2   = type === 'cap' ? capCls(v2) : type === 'sf' ? sfCls(v2)  : type === 'imp' ? impCls(v2) : 'text-slate-300';
        const c3   = type === 'cap' ? capCls(v3) : type === 'sf' ? sfCls(v3)  : type === 'imp' ? impCls(v3) : 'text-slate-300';
        return `<tr class="hover:bg-white/[0.02] ${bg}">
            <td class="px-3 py-2 text-xs font-mono text-slate-300">${param}</td>
            <td class="px-3 py-2 text-xs font-mono text-center text-slate-500">${unit}</td>
            <td class="px-3 py-2 text-xs font-mono text-right ${c1}">${v1}</td>
            <td class="px-3 py-2 text-xs font-mono text-right ${c2}">${v2}</td>
            <td class="px-3 py-2 text-xs font-mono text-right ${c3} font-bold">${v3}</td>
        </tr>`;
    }).join('');

    return `<thead>
            <tr class="border-b border-white/10 bg-slate-900/60">
                <th class="px-3 py-2.5 text-left text-[10px] font-black uppercase tracking-widest text-slate-400">Parameter</th>
                <th class="px-3 py-2.5 text-center text-[10px] font-black uppercase tracking-widest text-slate-400">Unit</th>
                <th class="px-3 py-2.5 text-right text-[10px] font-black uppercase tracking-widest text-slate-300">Test 1<br><span class="text-slate-500 font-normal normal-case tracking-normal">Pre-Baseline</span></th>
                <th class="px-3 py-2.5 text-right text-[10px] font-black uppercase tracking-widest text-slate-300">Test 2<br><span class="text-slate-500 font-normal normal-case tracking-normal">Post Fan Pitch</span></th>
                <th class="px-3 py-2.5 text-right text-[10px] font-black uppercase tracking-widest text-cyan-400">Test 3 ★<br><span class="text-slate-500 font-normal normal-case tracking-normal">Post Fill Dist.</span></th>
            </tr>
        </thead>
        <tbody class="divide-y divide-white/[0.04]">${rowHtml}</tbody>`;
}

// ── Design conditions grid (injected as innerHTML) ─────────────────────────────
function _buildDesignGrid(design) {
    const f2 = v => v != null ? Number(v).toFixed(2) : '—';
    const items = [
        ['WBT °C',      f2(design.wbt),              'Design wet-bulb temperature'],
        ['CWT °C',      f2(design.cwt),              'Target cold water temperature'],
        ['HWT °C',      f2(design.hwt),              'Design hot water temperature'],
        ['Flow m³/hr',  Number(design.flow).toFixed(1), 'Water flow at 100% design'],
        ['Fan Power kW',f2(design.fan_power),         'Design fan shaft power'],
        ['L/G Ratio',   f2(design.lg),               'Liquid-to-gas ratio'],
    ];
    return items.map(([label, val, title]) =>
        `<div class="rounded-lg bg-slate-900/60 border border-white/5 p-2.5 text-center" title="${title}">
            <p class="text-[10px] font-black uppercase tracking-widest text-slate-500 mb-1">${label}</p>
            <p class="text-sm font-black font-mono text-slate-200">${val}</p>
        </div>`
    ).join('');
}

// ── Results preview — full in-browser report document ─────────────────────────
export async function previewAllTests(ui) {
    const btn      = document.getElementById('previewAllTestsBtn');
    const errorEl  = document.getElementById('previewError');
    const origHtml = btn.innerHTML;

    const _set  = (id, val) => { const el = document.getElementById(id); if (el) el.innerHTML = val; };
    const _text = (id, val) => { const el = document.getElementById(id); if (el) el.innerText  = val; };

    btn.innerHTML = `<svg class="animate-spin w-4 h-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path></svg> Calculating…`;
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

        // ── Document header ────────────────────────────────────────────────────
        _text('pv-doc-title',    _v('rep-title',       'CT PERFORMANCE EVALUATION REPORT'));
        _text('pv-doc-client',   _v('rep-client',      '—'));
        _text('pv-doc-asset',    _v('rep-asset',       '—'));
        _text('pv-doc-repdate',  _v('rep-report-date', '—'));
        _text('pv-doc-testdate', _v('rep-test-date',   '—'));

        const overallEl = document.getElementById('pv-overall-verdict');
        if (overallEl) {
            overallEl.textContent = r3.capability >= 100 ? 'OVERALL: PASS' : r3.capability >= 95 ? 'OVERALL: MARGINAL' : 'OVERALL: FAIL';
            overallEl.className   = `px-3 py-1.5 rounded-xl text-[10px] font-black uppercase tracking-widest border ${_capBadgeCls(r3.capability)}`;
        }

        // ── Executive summary ──────────────────────────────────────────────────
        [[r1,'pv-cap1','pv-verdict1'],[r2,'pv-cap2','pv-verdict2'],[r3,'pv-cap3','pv-verdict3']].forEach(([r, capId, verdId]) => {
            const capEl  = document.getElementById(capId);
            if (capEl)  { capEl.textContent  = `${r.capability?.toFixed(1) ?? '—'} %`;  capEl.className  = `text-2xl font-black font-mono ${_capTextCls(r.capability)}`; }
            const verdEl = document.getElementById(verdId);
            if (verdEl) { verdEl.textContent = _capVerdict(r.capability); verdEl.className = `text-[11px] font-black uppercase mt-1 ${_capTextCls(r.capability)}`; }
        });
        _pvRenderCapChart([r1.capability, r2.capability, r3.capability]);

        // ── Design conditions ──────────────────────────────────────────────────
        const designGrid = document.getElementById('pv-design-grid');
        if (designGrid) designGrid.innerHTML = _buildDesignGrid(design);
        _text('pv-design-note', `Merkel constants: C = ${design.constant_c}, m = ${design.constant_m} · Design range = ${(design.hwt - design.cwt).toFixed(2)} °C · 90% flow = ${(design.flow * 0.9).toFixed(1)} · 100% = ${design.flow.toFixed(1)} · 110% = ${(design.flow * 1.1).toFixed(1)} m³/hr · Density: Kell (1975)`);

        // ── Per-test sections ──────────────────────────────────────────────────
        const f2 = v => v != null ? Number(v).toFixed(2) : '—';
        const f1 = v => v != null ? Number(v).toFixed(1) : '—';

        [['1', t1, r1], ['2', t2, r2], ['3', t3, r3]].forEach(([p, t, r]) => {
            // Measured inputs
            _text(`pv${p}-in-wbt`,    `${f2(t.wbt)} °C`);
            _text(`pv${p}-in-hwt`,    `${f2(t.hwt)} °C`);
            _text(`pv${p}-in-cwt`,    `${f2(t.cwt)} °C`);
            _text(`pv${p}-in-flow`,   `${f1(t.flow)} m³/hr`);
            _text(`pv${p}-in-fanpow`, `${f2(t.fan_power)} kW`);

            // Calc walkthrough table
            const calcDiv = document.getElementById(`pv${p}-calc-table`);
            if (calcDiv) calcDiv.innerHTML = _buildPvCalcTable(design, t, r);

            // CP1 WBT label
            _text(`pv${p}-cp1-wbt`, `${f2(t.wbt)} °C`);

            // Charts
            if (r.cross_plot_1) _pvRenderCp1(`pv${p}-cp1`, r.cross_plot_1, t.wbt);
            if (r.cross_plot_2) _pvRenderCp2(`pv${p}-cp2`, r.cross_plot_2);

            // Results strip
            _text(`pv${p}-range`, `${f2(r.test_range)} °C`);
            _text(`pv${p}-flow`,  `${f1(r.adj_flow)} m³/hr`);
            _text(`pv${p}-cwt`,   `${f2(r.pred_cwt)} °C`);

            const sfEl = document.getElementById(`pv${p}-shortfall`);
            if (sfEl) { sfEl.textContent = `${r.shortfall > 0 ? '+' : ''}${f2(r.shortfall)} °C`; sfEl.className = `text-sm font-black font-mono ${_sfTextCls(r.shortfall)}`; }

            const capEl = document.getElementById(`pv${p}-cap`);
            if (capEl) { capEl.textContent = `${f1(r.capability)} %`; capEl.className = `text-sm font-black font-mono ${_capTextCls(r.capability)}`; }

            const badge = document.getElementById(`pv${p}-verdict-badge`);
            if (badge) { badge.textContent = _capVerdict(r.capability); badge.className = `px-2.5 py-1 rounded-lg text-[10px] font-black uppercase tracking-widest border ${_capBadgeCls(r.capability)}`; }
        });

        // ── Improvement deltas ─────────────────────────────────────────────────
        const imp21 = r1.shortfall != null && r2.shortfall != null ? r1.shortfall - r2.shortfall : null;
        const imp32 = r2.shortfall != null && r3.shortfall != null ? r2.shortfall - r3.shortfall : null;
        const imp31 = r1.shortfall != null && r3.shortfall != null ? r1.shortfall - r3.shortfall : null;

        const _setImp = (id, val, large = false) => {
            const el = document.getElementById(id); if (!el || val == null) return;
            const sign = val >= 0 ? '+' : '';
            el.textContent = `${sign}${val.toFixed(2)} °C`;
            el.className   = `${large ? 'text-2xl' : 'text-xl'} font-black font-mono ${val >= 0 ? 'text-emerald-400' : 'text-rose-400'}`;
        };
        _setImp('pv-imp21',     imp21);
        _setImp('pv-imp32',     imp32);
        _setImp('pv-cumulative',imp31, true);

        const _setTestImp = (id, val) => {
            const el = document.getElementById(id); if (!el || val == null) return;
            el.textContent = `${val >= 0 ? '+' : ''}${val.toFixed(2)} °C`;
            el.className   = `text-[11px] font-black font-mono ${val >= 0 ? 'text-emerald-400' : 'text-rose-400'}`;
        };
        _setTestImp('pv2-imp', imp21);
        _setTestImp('pv3-imp', imp32);

        // ── Trend chart ────────────────────────────────────────────────────────
        _pvRenderTrendChart([r1.shortfall, r2.shortfall, r3.shortfall], [r1.capability, r2.capability, r3.capability]);

        // ── Comparison table ───────────────────────────────────────────────────
        const compWrapper = document.getElementById('pv-comparison-table');
        if (compWrapper) compWrapper.innerHTML = _buildComparisonTable(t1, t2, t3, r1, r2, r3);

        // ── Show preview panel ────────────────────────────────────────────────
        // ── Update modal header ────────────────────────────────────────
        const modalSubtitle = [_v('rep-client',''), _v('rep-asset',''), _v('rep-test-date','')].filter(Boolean).join(' · ');
        _text('pv-modal-subtitle', modalSubtitle || 'ATC-105 Report Preview');
        const mvEl = document.getElementById('pv-modal-verdict');
        if (mvEl) {
            mvEl.textContent = r3.capability >= 100 ? 'OVERALL: PASS' : r3.capability >= 95 ? 'OVERALL: MARGINAL' : 'OVERALL: FAIL';
            mvEl.className   = `shrink-0 ml-1 px-2.5 py-1 rounded-lg text-[10px] font-black uppercase tracking-widest border ${_capBadgeCls(r3.capability)}`;
        }

        // ── Show "Re-open overlay" hint inside the step card ─────────
        const hintEl = document.getElementById('previewReadyHint');
        if (hintEl) { hintEl.classList.remove('hidden'); hintEl.classList.add('flex'); }

        // ── Open the preview modal ────────────────────────────────────
        if (typeof openPreviewModal === 'function') openPreviewModal();

        // ── Update live Test-3 mini-preview card in Step 3 ───────────────────
        const pvCard = document.getElementById('atcPreview');
        if (pvCard) {
            _text('atc-prev-range',      r3.test_range  != null ? `${r3.test_range.toFixed(2)} °C` : '—');
            _text('atc-prev-adjflow',    r3.adj_flow    != null ? r3.adj_flow.toFixed(1)            : '—');
            _text('atc-prev-predcwt',    r3.pred_cwt    != null ? r3.pred_cwt.toFixed(2)            : '—');
            _text('atc-prev-shortfall',  r3.shortfall   != null ? r3.shortfall.toFixed(2)           : '—');
            _text('atc-prev-capability', r3.capability  != null ? `${r3.capability.toFixed(1)} %`   : '—');
            pvCard.classList.remove('hidden');
        }

    } catch (err) {
        if (errorEl) { errorEl.innerText = `Preview failed: ${err.message}`; errorEl.classList.remove('hidden'); }
    } finally {
        btn.innerHTML = origHtml;
        btn.disabled  = false;
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
