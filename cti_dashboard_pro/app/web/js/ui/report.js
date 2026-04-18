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

            // ── Auto-fill fields ──────────────────────────────────────────────
            const fills = [
                { id: 'rep-cwt',      val: data.cwt,      label: 'CWT',  unit: '°C' },
                { id: 'rep-hwt',      val: data.hwt,      label: 'HWT',  unit: '°C' },
                { id: 'rep-test-wbt', val: data.wbt,      label: 'WBT',  unit: '°C' },
                { id: 'rep-flow',     val: data.flow,     label: 'Flow', unit: 'm³/hr' },
                { id: 'rep-test-fanpow', val: data.fan_power, label: 'Fan Power', unit: 'kW' },
            ];

            let filled = 0;
            previewEl.innerHTML = '';
            for (const { id, val, label, unit } of fills) {
                if (val == null) continue;
                const el = document.getElementById(id);
                if (el) { el.value = val; filled++; }

                // Show card in preview
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

            // Re-trigger ATC-105 preview with new values
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

/** Split a multiline textarea into a trimmed array, dropping blank lines. */
function _lines(id) {
    return _v(id, '').split('\n').map(s => s.trim()).filter(Boolean);
}

// ── Live ATC-105 Preview ───────────────────────────────────────────────────

/**
 * Called on input change in the report tab.
 * Runs the ATC-105 endpoint and updates the preview cards.
 */
export async function updateAtcPreview(ui) {
    const previewEl = document.getElementById('atcPreview');
    if (!previewEl) return;

    const payload = _buildAtc105Payload(ui);
    if (!payload) { previewEl.classList.add('hidden'); return; }

    try {
        const resp = await fetch('/api/calculate/atc105', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        if (!resp.ok) return;
        const r = await resp.json();

        document.getElementById('atc-prev-range').innerText      = `${r.test_range?.toFixed(2) ?? '—'} °C`;
        document.getElementById('atc-prev-adjflow').innerText    = r.adj_flow?.toFixed(1)  ?? '—';
        document.getElementById('atc-prev-predcwt').innerText    = r.pred_cwt?.toFixed(2)  ?? '—';
        document.getElementById('atc-prev-shortfall').innerText  = r.shortfall?.toFixed(2) ?? '—';
        document.getElementById('atc-prev-capability').innerText = r.capability != null ? `${r.capability.toFixed(1)} %` : '—';

        previewEl.classList.remove('hidden');
    } catch (_) {
        // Silently ignore preview errors
    }
}

// ── Build ATC-105 payload ──────────────────────────────────────────────────

function _buildAtc105Payload(ui) {
    const lg = _n('rep-design-lg', ui?.inputs?.lgRatio ?? 1.5);
    const c  = _n('rep-design-c',  ui?.inputs?.constantC ?? 1.2);
    const m  = _n('rep-design-m',  ui?.inputs?.constantM ?? 0.6);
    const designFlow = _n('rep-design-flow', 3863.6);
    if (!designFlow) return null;

    return {
        design_wbt:       _n('rep-design-wbt', 29),
        design_cwt:       _n('rep-design-cwt', 33),
        design_hwt:       _n('rep-design-hwt', 43),
        design_flow:      designFlow,
        design_fan_power: _n('rep-design-fanpow', 117),
        test_wbt:         _n('rep-test-wbt', 21.7),
        test_cwt:         _n('rep-cwt',  32.4),
        test_hwt:         _n('rep-hwt',  42.13),
        test_flow:        _n('rep-flow', 3680),
        test_fan_power:   _n('rep-test-fanpow', 117),
        lg_ratio:  lg,
        constant_c: c,
        constant_m: m,
    };
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

    btn.innerHTML = `<svg class="animate-spin w-5 h-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path></svg> Calculating ATC-105…`;
    btn.disabled = true;
    setStatus('Running ATC-105 calculation on backend…');

    try {
        // ── Step A: Compute ATC-105 results ──────────────────────────────────
        const atcPayload = _buildAtc105Payload(ui);
        if (!atcPayload) throw new Error('Design flow is required.');

        const atcResp = await fetch('/api/calculate/atc105', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(atcPayload),
        });
        if (!atcResp.ok) {
            const err = await atcResp.json().catch(() => ({}));
            throw new Error(err.detail || `ATC-105 API error ${atcResp.status}`);
        }
        const atc = await atcResp.json();

        // Update live preview
        const pv = document.getElementById('atcPreview');
        if (pv) {
            document.getElementById('atc-prev-range').innerText      = `${atc.test_range?.toFixed(2) ?? '—'} °C`;
            document.getElementById('atc-prev-adjflow').innerText    = atc.adj_flow?.toFixed(1)  ?? '—';
            document.getElementById('atc-prev-predcwt').innerText    = atc.pred_cwt?.toFixed(2)  ?? '—';
            document.getElementById('atc-prev-shortfall').innerText  = atc.shortfall?.toFixed(2) ?? '—';
            document.getElementById('atc-prev-capability').innerText = atc.capability != null ? `${atc.capability.toFixed(1)} %` : '—';
            pv.classList.remove('hidden');
        }

        btn.innerHTML = `<svg class="animate-spin w-5 h-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path></svg> Generating PDF…`;
        setStatus('ATC-105 calculated. Rendering PDF…');

        // ── Step B: Build test data values (convenience refs) ─────────────
        const testFlow  = _n('rep-flow',  3680);
        const testCwt   = _n('rep-cwt',   32.4);
        const testHwt   = _n('rep-hwt',   42.13);
        const testWbt   = _n('rep-test-wbt', 21.7);
        const testRange = parseFloat((testHwt - testCwt).toFixed(2));
        const airFlow   = _n('rep-air',   485);
        const airArea   = _n('rep-fan-area', 92.25);
        const fanAvgVel = airArea > 0 ? parseFloat((airFlow / airArea).toFixed(2)) : '—';

        // Historical tests
        const t1 = {
            flow:   _n('rep-t1-flow', 2998),
            wbt:    _n('rep-t1-wbt',  25.25),
            hwt:    _n('rep-t1-hwt',  44.67),
            cwt:    _n('rep-t1-cwt',  35.08),
            fanpow: _n('rep-t1-fanpow', 97.04),
            air:    _n('rep-t1-air',  405.97),
        };
        const t2 = {
            flow:   _n('rep-t2-flow', 3067),
            wbt:    _n('rep-t2-wbt',  24.22),
            hwt:    _n('rep-t2-hwt',  43.21),
            cwt:    _n('rep-t2-cwt',  32.89),
            fanpow: _n('rep-t2-fanpow', 116.24),
            air:    _n('rep-t2-air',  499),
        };

        // ── Step C: Build full PDF payload ────────────────────────────────
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

            // ATC-105 computed results (drives plots + tables)
            atc105: atc,

            // Standard narrative sections
            assessment_method: [
                `Pre test was conducted on ${_v('rep-test-date')}.`,
                'Cell has been isolated at the basin level for collection of cold water directly from the rain zone.',
                'All required data was collected and report has been given.',
            ],
            instrument_placement: [
                'Air flow was measured using Data Logging anemometer as per CTI ATC-143 Method of equal area.',
                `Hot water temperature was taken at inlet of the hot water to the cooling tower.`,
                'Cold water temperature: RTD sensors placed at both air-inlet sides of the isolated cell.',
                'Water flow was measured using UFM on the riser.',
                'WBT/DBT was measured using wet-bulb automatic stations recording every minute.',
                'Power to the fan motor was noted from the client MCC.',
            ],
            suggestions: [
                'With 3 pumps operating and one cell under higher flow, velocities through the duct would be higher by 1.23%; a one-size smaller ferrul (orifice) can be provided at the last 3 pipes of the cell away from the riser.',
            ],

            // Multi-test comparison table (computed from inputs)
            final_data_table: [
                { name: 'Water Flow', unit: 'M3/hr',
                  test1: t1.flow, test2: t2.flow, test3: testFlow },
                { name: 'WBT', unit: 'Deg.C',
                  test1: t1.wbt, test2: t2.wbt, test3: testWbt },
                { name: 'HWT', unit: 'Deg.C',
                  test1: t1.hwt, test2: t2.hwt, test3: testHwt },
                { name: 'CWT', unit: 'Deg.C',
                  test1: t1.cwt, test2: t2.cwt, test3: testCwt },
                { name: 'Fan Power At Motor Inlet', unit: 'KW',
                  test1: t1.fanpow, test2: t2.fanpow, test3: _n('rep-test-fanpow', 117) },
                { name: 'Fan Air Flow', unit: 'M3/s',
                  test1: t1.air, test2: t2.air, test3: airFlow },
                { name: 'Range', unit: 'Deg.C',
                  test1: parseFloat((t1.hwt - t1.cwt).toFixed(2)),
                  test2: parseFloat((t2.hwt - t2.cwt).toFixed(2)),
                  test3: testRange },
                { name: 'Approach', unit: 'Deg.C',
                  test1: parseFloat((t1.cwt - t1.wbt).toFixed(2)),
                  test2: parseFloat((t2.cwt - t2.wbt).toFixed(2)),
                  test3: parseFloat((testCwt - testWbt).toFixed(2)) },
                { name: 'CWT Deviation from Design',  unit: 'Deg.C',
                  test1: '—', test2: '—',
                  test3: atc.shortfall != null ? atc.shortfall.toFixed(2) : '—' },
            ],
            data_notes: _lines('rep-data-notes'),

            airflow: {
                avg_velocity: fanAvgVel,
                area:         airArea,
                total_flow:   airFlow,
            },
        };

        // ── Step D: POST to generate PDF ─────────────────────────────────
        const pdfResp = await fetch('/api/generate-pdf-report', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(pdfPayload),
        });

        if (!pdfResp.ok) {
            const err = await pdfResp.text();
            throw new Error(`PDF generation failed (${pdfResp.status}): ${err}`);
        }

        const blob = await pdfResp.blob();
        const safeName = _v('rep-client', 'Report').replace(/[^a-zA-Z0-9]/g, '_').slice(0, 40);
        const filename  = `ATC105_${safeName}_${_v('rep-test-date', '').replace(/\s/g, '_')}.pdf`;

        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.style.display = 'none';
        document.body.appendChild(a);
        a.click();
        URL.revokeObjectURL(url);
        a.remove();

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
