import { calculations } from './calculations.js';
import { charts } from './charts.js';
import { bindEvents } from './ui/bind-events.js';
import { switchTab } from './ui/tabs.js';
import { setSidebarOpen, initMobileNavigation } from './ui/mobile-nav.js';
import { formatPsychroValue, calculatePsychrometrics } from './ui/psychro.js';
import { updateFilterUiState, syncFilterSettingsToUi, runFilterTool } from './ui/filter.js';
import { updateExportUiState, getDownloadFileName, downloadBlob, exportData } from './ui/export.js';
import { calculatePrediction } from './ui/prediction.js';

export const ui = {
    inputs: {
        companyName: 'SS Cooling tower LTD',
        engineerName: 'Suresh Sarma',
        projectName: 'IDCT Thermal Performance Curves',
        date: new Date().toISOString().split('T')[0],
        lgRatio: 1.5,
        designWBT: 27,
        designCWT: 32,
        designHWT: 37,
        designWaterFlow: 1000,
        constantC: 1.2,
        constantM: 0.6,
        axXMin: 18,
        axXMax: 30,
        axYMin: 25,
        axYMax: 38
    },
    filterSettings: {
        sourcePath: '',
        startTime: '16:00',
        endTime: '17:00'
    },
    workerReady: false,
    enginesReady: false,
    isPrinting: false,
    isCalculating: false,
    isExporting: false,
    isFiltering: false,
    isSidebarOpen: false,
    curveRequestId: 0,
    activeTab: 'thermal',
    curveData: { 90: [], 100: [], 110: [] },
    lastCurveSignature: '',
    pendingFlows: new Set(),
    curveReadyResolvers: [],

    init: async () => {
        ui.loadInputs();
        ui.loadFilterSettings();
        try {
            await calculations.init();
            ui.enginesReady = true;
        } catch (error) {
            console.error('Failed to initialize calculation engines on main thread', error);
            ui.enginesReady = false;
        }
        ui.bindEvents();

        // Setup the calculation Web Worker
        ui.worker = new Worker('./js/worker.js', { type: 'module' });

        // Listen for computation results
        ui.worker.onmessage = (e) => {
            if (e.data.type === 'READY') {
                ui.workerReady = true;
                ui.updateAll();
            } else if (e.data.type === 'ERROR') {
                ui.isCalculating = false;
                ui.resolveCurveWaiters(false);
                ui.updateExportUiState(e.data.payload?.message || 'Engine error. Please refresh and retry.');
            } else if (e.data.type === 'CURVE_RESULT') {
                const { flowPercent, data, requestId } = e.data.payload;
                if (requestId !== ui.curveRequestId) {
                    return;
                }

                const index = flowPercent === 90 ? 0 : flowPercent === 100 ? 1 : 2;
                ui.curveData[flowPercent] = data;
                ui.pendingFlows.delete(flowPercent);

                charts.render(
                    `chart${index + 1}`,
                    data,
                    `Curve ${index + 1} (${flowPercent}% Flow)`,
                    ui.inputs.axXMin,
                    ui.inputs.axXMax,
                    ui.inputs.axYMin,
                    ui.inputs.axYMax,
                    ui.isPrinting || false
                );

                if (ui.pendingFlows.size === 0) {
                    ui.isCalculating = false;
                    ui.resolveCurveWaiters(true);
                    ui.updateExportUiState('Curves ready. Export is enabled.');
                } else {
                    const completed = 3 - ui.pendingFlows.size;
                    ui.updateExportUiState(`Calculating curves (${completed}/3 complete)...`);
                }
            }
        };
        ui.worker.onerror = (error) => {
            console.error('Worker runtime error', error);
            ui.isCalculating = false;
            ui.resolveCurveWaiters(false);
            ui.updateExportUiState('Engine crashed. Refresh the dashboard to recover.');
        };

        // Initialize worker databases
        ui.worker.postMessage({
            type: 'INIT',
            payload: { psychroLibPath: '../data/psychro_f_alt.bin', merkelLibPath: '../data/merkel_poly.bin' }
        });

        ui.updateExportUiState('Initializing calculation engine...');
    },

    saveInputs: () => {
        localStorage.setItem('sarma_thermal_inputs', JSON.stringify(ui.inputs));
    },

    loadInputs: () => {
        const saved = localStorage.getItem('sarma_thermal_inputs');
        if (saved) {
            try {
                const parsed = JSON.parse(saved);
                // Merge saved values into defaults to handle schema updates
                ui.inputs = { ...ui.inputs, ...parsed };

                // Update DOM elements to reflect loaded values
                Object.keys(ui.inputs).forEach(id => {
                    const el = document.getElementById(id);
                    if (el) {
                        if (el.type === 'date') el.value = ui.inputs[id];
                        else el.value = ui.inputs[id];
                    }
                });
            } catch (e) {
                console.error('Error loading saved inputs', e);
            }
        }
    },

    saveFilterSettings: () => {
        localStorage.setItem('sarma_filter_settings', JSON.stringify(ui.filterSettings));
    },

    loadFilterSettings: () => {
        const saved = localStorage.getItem('sarma_filter_settings');
        if (saved) {
            try {
                const parsed = JSON.parse(saved);
                ui.filterSettings = { ...ui.filterSettings, ...parsed };
            } catch (e) {
                console.error('Error loading filter settings', e);
            }
        }
    },

    debounce: (fn, ms) => {
        let timer;
        return (...args) => {
            clearTimeout(timer);
            timer = setTimeout(() => fn(...args), ms);
        };
    },

    bindEvents: () => bindEvents(ui),

    updateFastMetrics: () => {
        const designKaVL = calculations.calculateDemandKaVL(
            ui.inputs.designWBT,
            ui.inputs.designHWT,
            ui.inputs.designCWT,
            ui.inputs.lgRatio
        );
        const supplyKaVL = calculations.calculateSupplyKaVL(
            ui.inputs.lgRatio,
            ui.inputs.constantC,
            ui.inputs.constantM
        );
        const approach = ui.inputs.designCWT - ui.inputs.designWBT;
        const range = ui.inputs.designHWT - ui.inputs.designCWT;

        // Update display values synchronously so they feel instantly snappy
        document.getElementById('displaySupply').innerText = Number.isFinite(supplyKaVL) ? supplyKaVL.toFixed(5) : '--';
        document.getElementById('displayDemand').innerText = Number.isFinite(designKaVL) ? designKaVL.toFixed(5) : '--';
        document.getElementById('displayApproach').innerText = Number.isFinite(approach) ? approach.toFixed(2) : '--';
        document.getElementById('displayRange').innerText = Number.isFinite(range) ? range.toFixed(2) : '--';

        // Sync Professional Print Header
        document.getElementById('printProject').innerText = ui.inputs.projectName;
        document.getElementById('printClient').innerText = ui.inputs.companyName;
        document.getElementById('printEngineer').innerText = ui.inputs.engineerName;
        document.getElementById('printDate').innerText = ui.inputs.date;
    },

    updateAll: () => {
        ui.updateFastMetrics();
        // Generate and update charts asynchronously via worker
        ui.updateCharts();
    },

    updateCharts: () => {
        if (!ui.workerReady) return;

        const flows = [90, 100, 110];
        const requestId = ++ui.curveRequestId;

        const axisInputs = ['axXMin', 'axXMax', 'axYMin', 'axYMax'];
        if (axisInputs.some((id) => Number.isNaN(ui.inputs[id]))) {
            ui.updateExportUiState('Axis values must be numeric.');
            return;
        }
        if (ui.inputs.axXMin >= ui.inputs.axXMax) {
            [ui.inputs.axXMin, ui.inputs.axXMax] = [ui.inputs.axXMax - 1, ui.inputs.axXMax];
        }
        if (ui.inputs.axYMin >= ui.inputs.axYMax) {
            [ui.inputs.axYMin, ui.inputs.axYMax] = [ui.inputs.axYMax - 1, ui.inputs.axYMax];
        }

        const curveSignature = JSON.stringify({
            lgRatio: ui.inputs.lgRatio,
            designWBT: ui.inputs.designWBT,
            designCWT: ui.inputs.designCWT,
            designHWT: ui.inputs.designHWT,
            designWaterFlow: ui.inputs.designWaterFlow,
            constantC: ui.inputs.constantC,
            constantM: ui.inputs.constantM,
            axXMin: ui.inputs.axXMin,
            axXMax: ui.inputs.axXMax,
            axYMin: ui.inputs.axYMin,
            axYMax: ui.inputs.axYMax,
            isPrinting: ui.isPrinting
        });
        if (ui.areCurvesReady() && ui.lastCurveSignature === curveSignature) {
            return;
        }
        ui.lastCurveSignature = curveSignature;

        ui.isCalculating = true;
        ui.curveData = { 90: [], 100: [], 110: [] };
        ui.pendingFlows = new Set(flows);
        ui.updateExportUiState('Calculating curves (0/3 complete)...');

        flows.forEach((flow) => {
            // Offload the massive iterative integration logic to a background worker
            // Prevents UI freezes on large resolution charts
            ui.worker.postMessage({
                type: 'CALCULATE_CURVE',
                payload: { inputs: ui.inputs, flowPercent: flow, requestId }
            });
        });
    },

    areCurvesReady: () => {
        return (
            ui.workerReady &&
            !ui.isCalculating &&
            ui.curveData[90].length > 0 &&
            ui.curveData[100].length > 0 &&
            ui.curveData[110].length > 0
        );
    },

    waitForCurves: (timeoutMs = 120000) => {
        if (ui.areCurvesReady()) {
            return Promise.resolve(true);
        }

        return new Promise((resolve, reject) => {
            const waiter = {
                complete: (success) => {
                    clearTimeout(timer);
                    resolve(success);
                }
            };

            const timer = setTimeout(() => {
                ui.curveReadyResolvers = ui.curveReadyResolvers.filter((w) => w !== waiter);
                reject(new Error('Timed out while waiting for curves to finish.'));
            }, timeoutMs);

            ui.curveReadyResolvers.push(waiter);
        });
    },

    resolveCurveWaiters: (success) => {
        const waiters = ui.curveReadyResolvers.splice(0);
        waiters.forEach((waiter) => waiter.complete(success));
    },

    updateExportUiState: (statusMessage = '') => updateExportUiState(ui, statusMessage),
    getDownloadFileName,
    downloadBlob,
    switchTab: (tabId) => switchTab(ui, tabId),
    updateFilterUiState: (message = '') => updateFilterUiState(ui, message),
    syncFilterSettingsToUi: () => syncFilterSettingsToUi(ui),
    formatPsychroValue,
    calculatePsychrometrics: () => calculatePsychrometrics(ui),
    calculatePrediction: () => calculatePrediction(ui),
    runFilterTool: () => runFilterTool(ui),
    exportData: () => exportData(ui),
    setSidebarOpen: (open) => setSidebarOpen(ui, open),
    initMobileNavigation: () => initMobileNavigation(ui)
};

window.addEventListener('DOMContentLoaded', ui.init);
