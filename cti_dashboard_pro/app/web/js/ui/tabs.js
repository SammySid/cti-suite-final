export function switchTab(ui, tabId) {
    ui.activeTab = tabId;
    const thermalTab = document.getElementById('tabThermal');
    const psychroTab = document.getElementById('tabPsychro');
    const predictionTab = document.getElementById('tabPrediction');
    const filterTab = document.getElementById('tabFilter');
    const reportTab = document.getElementById('tabReport');
    const thermalPanel = document.getElementById('thermalTabPanel');
    const psychroPanel = document.getElementById('psychroTabPanel');
    const filterPanel = document.getElementById('filterTabPanel');
    const predictionPanel = document.getElementById('predictionTabPanel');
    const reportPanel = document.getElementById('reportTabPanel');
    const thermalSidebarInputs = document.getElementById('thermalSidebarInputs');
    const thermalSidebarExport = document.getElementById('thermalSidebarExport');

    const setTabActive = (tabEl, active) => {
        if (!tabEl) return;
        tabEl.classList.toggle('bg-cyan-500/20', active);
        tabEl.classList.toggle('text-cyan-300', active);
        tabEl.classList.toggle('border-cyan-500/30', active);
        tabEl.classList.toggle('text-slate-300', !active);
        tabEl.classList.toggle('border-white/10', !active);
        tabEl.classList.toggle('hover:bg-white/5', !active);
    };

    setTabActive(thermalTab, tabId === 'thermal');
    setTabActive(predictionTab, tabId === 'prediction');
    setTabActive(psychroTab, tabId === 'psychro');
    setTabActive(filterTab, tabId === 'filter');
    setTabActive(reportTab, tabId === 'report');
    thermalPanel?.classList.toggle('hidden', tabId !== 'thermal');
    psychroPanel?.classList.toggle('hidden', tabId !== 'psychro');
    filterPanel?.classList.toggle('hidden', tabId !== 'filter');
    predictionPanel?.classList.toggle('hidden', tabId !== 'prediction');
    reportPanel?.classList.toggle('hidden', tabId !== 'report');

    // Sidebar controls (desktop): show only on thermal tab
    thermalSidebarInputs?.classList.toggle('hidden', tabId !== 'thermal');
    thermalSidebarExport?.classList.toggle('hidden', tabId !== 'thermal');

    // Mobile inline input panel: show only on thermal tab (lg:hidden keeps it off desktop)
    const thermalMobileInputPanel = document.getElementById('thermalMobileInputPanel');
    thermalMobileInputPanel?.classList.toggle('hidden', tabId !== 'thermal');

    if (tabId === 'psychro') {
        ui.calculatePsychrometrics();
    }
    if (window.matchMedia('(max-width: 1023px)').matches) {
        ui.setSidebarOpen(false);
    }
}
