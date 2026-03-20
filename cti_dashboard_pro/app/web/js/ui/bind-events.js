import { INPUT_IDS, isCurveAffectingInput } from './constants.js';

export function bindEvents(ui) {
    const debouncedUpdateAll = ui.debounce(ui.updateAll, 300);

    // ── Sidebar inputs (desktop) ──────────────────────────────────────────────
    INPUT_IDS.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('input', (e) => {
                let val = e.target.value;
                if (e.target.type === 'number') {
                    const parsed = Number.parseFloat(e.target.value);
                    if (!Number.isFinite(parsed)) return;
                    val = parsed;
                }
                ui.inputs[id] = val;
                ui.saveInputs();

                // Keep mobile mirror in sync (value only, no re-trigger)
                const mirror = document.querySelector(`[data-mobile-mirror="${id}"]`);
                if (mirror && mirror !== e.target) mirror.value = val;

                ui.updateFastMetrics();
                if (isCurveAffectingInput(id)) debouncedUpdateAll();
            });
        }
    });

    // ── Mobile mirror inputs (inline panel — mobile/tablet only) ──────────────
    // These use data-mobile-mirror="<inputId>" instead of id to avoid duplicates.
    document.querySelectorAll('[data-mobile-mirror]').forEach(mirrorEl => {
        const id = mirrorEl.dataset.mobileMirror;
        if (!id) return;

        // Seed initial value from loaded inputs
        if (ui.inputs[id] !== undefined) mirrorEl.value = ui.inputs[id];

        mirrorEl.addEventListener('input', (e) => {
            let val = e.target.value;
            if (e.target.type === 'number') {
                const parsed = Number.parseFloat(e.target.value);
                if (!Number.isFinite(parsed)) return;
                val = parsed;
            }
            ui.inputs[id] = val;
            ui.saveInputs();

            // Keep sidebar canonical input in sync (value only, no re-trigger)
            const canonical = document.getElementById(id);
            if (canonical && canonical !== e.target) canonical.value = val;

            ui.updateFastMetrics();
            if (isCurveAffectingInput(id)) debouncedUpdateAll();
        });
    });

    // ── Desktop export buttons (sidebar) ─────────────────────────────────────
    document.getElementById('exportExcel')?.addEventListener('click', () => ui.exportData());
    document.getElementById('exportPDF')?.addEventListener('click',  () => window.print());
    document.getElementById('resetDefaults')?.addEventListener('click', () => {
        if (confirm('Are you sure you want to reset all parameters to default values?')) {
            localStorage.removeItem('sarma_thermal_inputs');
            location.reload();
        }
    });

    // ── Mobile export buttons (inline panel) ─────────────────────────────────
    document.getElementById('exportExcelMobile')?.addEventListener('click', () => ui.exportData());
    document.getElementById('exportPDFMobile')?.addEventListener('click',  () => window.print());

    // ── Tab navigation ───────────────────────────────────────────────────────
    document.getElementById('tabThermal')?.addEventListener('click',    () => ui.switchTab('thermal'));
    document.getElementById('tabPrediction')?.addEventListener('click', () => {
        ui.switchTab('prediction');
        ui.calculatePrediction();
    });
    document.getElementById('tabPsychro')?.addEventListener('click', () => ui.switchTab('psychro'));
    document.getElementById('tabFilter')?.addEventListener('click',   () => ui.switchTab('filter'));

    // ── Filter tool ──────────────────────────────────────────────────────────
    document.getElementById('runFilterAction')?.addEventListener('click', () => ui.runFilterTool());
    document.getElementById('filterSourcePath')?.addEventListener('input', (e) => {
        ui.filterSettings.sourcePath = e.target.value.trim();
        ui.saveFilterSettings();
    });
    document.getElementById('filterStartTime')?.addEventListener('input', (e) => {
        ui.filterSettings.startTime = e.target.value;
        ui.saveFilterSettings();
    });
    document.getElementById('filterEndTime')?.addEventListener('input', (e) => {
        ui.filterSettings.endTime = e.target.value;
        ui.saveFilterSettings();
    });

    // ── Psychrometric calculator ──────────────────────────────────────────────
    ['p-dbt', 'p-wbt', 'p-alt'].forEach((id) => {
        document.getElementById(id)?.addEventListener('input', ui.debounce(ui.calculatePsychrometrics, 150));
    });

    // ── Performance prediction ────────────────────────────────────────────────
    ['pred-wbt', 'pred-range', 'pred-lg', 'pred-c', 'pred-m'].forEach((id) => {
        document.getElementById(id)?.addEventListener('input', ui.debounce(ui.calculatePrediction, 100));
    });

    // ── Print mode ───────────────────────────────────────────────────────────
    window.onbeforeprint = () => { ui.isPrinting = true;  ui.updateCharts(); };
    window.onafterprint  = () => { ui.isPrinting = false; ui.updateCharts(); };

    // ── Initialise ───────────────────────────────────────────────────────────
    ui.initMobileNavigation();
    ui.updateExportUiState('Calculating curves...');
    ui.updateFilterUiState('Filter tool ready.');
    ui.switchTab('thermal');
    ui.syncFilterSettingsToUi();
    ui.calculatePsychrometrics();
}
