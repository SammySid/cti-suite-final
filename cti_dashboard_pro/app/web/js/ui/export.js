export function updateExportUiState(ui, statusMessage = '') {
    const exportBtn       = document.getElementById('exportExcel');
    const exportBtnMobile = document.getElementById('exportExcelMobile');
    const label           = document.getElementById('exportExcelLabel');
    const statusEl        = document.getElementById('exportStatus');
    const statusMobile    = document.getElementById('exportStatusMobile');
    if (!exportBtn) return;

    const isDisabled = !ui.workerReady || ui.isCalculating || ui.isExporting;
    exportBtn.disabled = isDisabled;
    exportBtn.classList.toggle('opacity-50', isDisabled);
    exportBtn.classList.toggle('cursor-not-allowed', isDisabled);

    if (exportBtnMobile) {
        exportBtnMobile.disabled = isDisabled;
        exportBtnMobile.classList.toggle('opacity-50', isDisabled);
        exportBtnMobile.classList.toggle('cursor-not-allowed', isDisabled);
    }

    if (label) {
        label.innerText = ui.isExporting ? 'Generating Excel...' : 'Export Data & Curves';
    }

    let resolvedMessage = statusMessage;
    if (!resolvedMessage) {
        if (ui.isExporting)           resolvedMessage = 'Generating report...';
        else if (ui.areCurvesReady()) resolvedMessage = 'Curves ready. Export is enabled.';
        else if (!ui.workerReady)     resolvedMessage = 'Initializing calculation engine...';
        else                          resolvedMessage = 'Calculating curves...';
    }

    if (statusEl)     statusEl.innerText     = resolvedMessage;
    if (statusMobile) statusMobile.innerText = resolvedMessage;
}

export function getDownloadFileName(contentDispositionHeader) {
    if (!contentDispositionHeader) {
        return 'Professional_Report.xlsx';
    }

    const fileNameMatch = contentDispositionHeader.match(/filename="?([^";]+)"?/i);
    return fileNameMatch?.[1] || 'Professional_Report.xlsx';
}

export function downloadBlob(blob, fileName) {
    const fileUrl = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = fileUrl;
    a.download = fileName;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(fileUrl);
}

export async function exportData(ui) {
    if (ui.isExporting) return;

    ui.isExporting = true;
    let finalMessage = '';
    ui.updateExportUiState('Preparing export payload...');

    try {
        if (!ui.areCurvesReady()) {
            ui.updateCharts();
            await ui.waitForCurves();
        }

        const payload = {
            inputs: { ...ui.inputs },
            data90: ui.curveData[90],
            data100: ui.curveData[100],
            data110: ui.curveData[110]
        };

        ui.updateExportUiState('Generating Excel report...');

        const response = await fetch('/api/export-excel', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            let message = `Export failed with status ${response.status}`;
            const errorText = await response.text();
            if (errorText) {
                try {
                    const errorJson = JSON.parse(errorText);
                    message = errorJson.error || message;
                } catch (parseError) {
                    message = errorText;
                }
            }
            throw new Error(message);
        }

        const blob = await response.blob();
        const fileName = ui.getDownloadFileName(response.headers.get('content-disposition'));
        ui.downloadBlob(blob, fileName);

        finalMessage = 'Excel report downloaded successfully.';
        ui.updateExportUiState(finalMessage);
    } catch (error) {
        console.error('Export failed', error);
        finalMessage = error.message || 'Export failed. Please try again.';
        ui.updateExportUiState(finalMessage);
    } finally {
        ui.isExporting = false;
        if (!finalMessage) {
            ui.updateExportUiState();
        } else {
            setTimeout(() => ui.updateExportUiState(), 2200);
        }
    }
}
