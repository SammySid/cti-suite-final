import { INPUT_IDS, isCurveAffectingInput } from './constants.js';

export function bindEvents(ui) {
    const debouncedUpdateAll = ui.debounce(ui.updateAll, 300);

    INPUT_IDS.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('input', (e) => {
                let val = e.target.value;
                if (e.target.type === 'number') {
                    const parsed = Number.parseFloat(e.target.value);
                    if (!Number.isFinite(parsed)) {
                        return;
                    }
                    val = parsed;
                }
                ui.inputs[id] = val;
                ui.saveInputs();

                // Run the fast math right now to update big numbers
                ui.updateFastMetrics();
                if (isCurveAffectingInput(id)) {
                    // Debounce the heavy chart math only for curve-related inputs.
                    debouncedUpdateAll();
                }
            });
        }
    });

    document.getElementById('exportExcel')?.addEventListener('click', () => {
        ui.exportData();
    });
    document.getElementById('tabThermal')?.addEventListener('click', () => ui.switchTab('thermal'));
    document.getElementById('tabPrediction')?.addEventListener('click', () => {
        ui.switchTab('prediction');
        ui.calculatePrediction(); // initial calc
    });
    document.getElementById('tabPsychro')?.addEventListener('click', () => ui.switchTab('psychro'));
    document.getElementById('tabFilter')?.addEventListener('click', () => ui.switchTab('filter'));
    document.getElementById('runFilterAction')?.addEventListener('click', () => {
        ui.runFilterTool();
    });
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
    ['p-dbt', 'p-wbt', 'p-alt'].forEach((id) => {
        document.getElementById(id)?.addEventListener('input', ui.debounce(ui.calculatePsychrometrics, 150));
    });

    ['pred-wbt', 'pred-range', 'pred-lg', 'pred-c', 'pred-m'].forEach((id) => {
        document.getElementById(id)?.addEventListener('input', ui.debounce(ui.calculatePrediction, 100)); // extremely fast real-time feedback
    });
    document.getElementById('exportPDF')?.addEventListener('click', () => window.print());
    document.getElementById('resetDefaults')?.addEventListener('click', () => {
        if (confirm('Are you sure you want to reset all parameters to default values?')) {
            localStorage.removeItem('sarma_thermal_inputs');
            location.reload();
        }
    });

    // Professional Print Mode Switch
    window.onbeforeprint = () => {
        ui.isPrinting = true;
        ui.updateCharts(); // Trigger synchronous style redraw
    };
    window.onafterprint = () => {
        ui.isPrinting = false;
        ui.updateCharts();
    };

    ui.initMobileNavigation();
    ui.updateExportUiState('Calculating curves...');
    ui.updateFilterUiState('Filter tool ready.');
    ui.switchTab('thermal');
    ui.syncFilterSettingsToUi();
    ui.calculatePsychrometrics();
}
