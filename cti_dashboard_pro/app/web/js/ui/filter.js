export function updateFilterUiState(ui, message = '') {
    const filterStatus = document.getElementById('filterStatus');
    const panelStatus = document.getElementById('filterPanelStatus');
    const runBtn = document.getElementById('runFilterAction');

    if (runBtn) {
        runBtn.disabled = ui.isFiltering;
        runBtn.classList.toggle('opacity-50', ui.isFiltering);
        runBtn.classList.toggle('cursor-not-allowed', ui.isFiltering);
        runBtn.innerText = ui.isFiltering ? 'Processing...' : 'Generate Filtered Excel';
    }

    const resolvedMessage = message || (ui.isFiltering ? 'Processing uploaded files...' : 'Filter tool ready.');
    if (filterStatus) filterStatus.innerText = resolvedMessage;
    if (panelStatus) panelStatus.innerText = resolvedMessage;
}

function _applyProcessAllState(isAll) {
    const startInput = document.getElementById('filterStartTime');
    const endInput = document.getElementById('filterEndTime');
    const timeGrid = startInput?.closest('.grid');
    if (startInput) {
        startInput.disabled = isAll;
        startInput.style.opacity = isAll ? '0.35' : '';
    }
    if (endInput) {
        endInput.disabled = isAll;
        endInput.style.opacity = isAll ? '0.35' : '';
    }
    if (timeGrid) {
        timeGrid.style.pointerEvents = isAll ? 'none' : '';
    }
}

export function bindFilterProcessAllToggle() {
    const chk = document.getElementById('filterProcessAll');
    if (chk) {
        chk.addEventListener('change', () => _applyProcessAllState(chk.checked));
    }
}

export function syncFilterSettingsToUi(ui) {
    const pathInput = document.getElementById('filterSourcePath');
    const destPathInput = document.getElementById('filterDestPath');
    const startInput = document.getElementById('filterStartTime');
    const endInput = document.getElementById('filterEndTime');
    const processAllChk = document.getElementById('filterProcessAll');

    if (pathInput) pathInput.value = ui.filterSettings.sourcePath || '';
    if (destPathInput) destPathInput.value = ui.filterSettings.destPath || '';
    if (startInput) startInput.value = ui.filterSettings.startTime || '16:00';
    if (endInput) endInput.value = ui.filterSettings.endTime || '17:00';
    if (processAllChk) {
        processAllChk.checked = ui.filterSettings.processAll || false;
        _applyProcessAllState(processAllChk.checked);
    }
}

export async function runFilterTool(ui) {
    if (ui.isFiltering) return;

    const startInput = document.getElementById('filterStartTime');
    const endInput = document.getElementById('filterEndTime');
    const sourcePathInput = document.getElementById('filterSourcePath');
    const destPathInput = document.getElementById('filterDestPath');
    const folderInput = document.getElementById('filterExcelFolder');
    const filesInput = document.getElementById('filterExcelFiles');
    const processAllChk = document.getElementById('filterProcessAll');

    const processAll = processAllChk?.checked || false;
    const startTime = processAll ? '' : (startInput?.value || '');
    const endTime = processAll ? '' : (endInput?.value || '');
    const sourcePath = sourcePathInput?.value?.trim() || '';
    const destPath = destPathInput?.value?.trim() || '';
    const folderFiles = folderInput?.files ? Array.from(folderInput.files) : [];
    const manualFiles = filesInput?.files ? Array.from(filesInput.files) : [];
    const files = folderFiles.length > 0 ? folderFiles : manualFiles;
    const SUPPORTED_EXT = ['.xlsx', '.xls'];
    const excelFiles = files.filter((file) => SUPPORTED_EXT.some(ext => file.name.toLowerCase().endsWith(ext)));

    if (!processAll && (!startTime || !endTime)) {
        ui.updateFilterUiState('Please choose both start and end time, or enable "Process All".');
        return;
    }
    if (!sourcePath && excelFiles.length === 0) {
        ui.updateFilterUiState('Please provide source folder path or select files.');
        return;
    }

    ui.filterSettings = {
        sourcePath,
        destPath,
        startTime,
        endTime,
        processAll
    };
    ui.saveFilterSettings();

    ui.isFiltering = true;
    let finalMessage = '';
    ui.updateFilterUiState(sourcePath
        ? 'Scanning saved source folder and filtering data...'
        : `Scanning ${excelFiles.length} file(s) and filtering data...`);

    try {
        let response;
        if (sourcePath) {
            response = await fetch('/api/filter-excel-local', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ startTime, endTime, sourcePath, destPath })
            });
        } else {
            const formData = new FormData();
            formData.append('startTime', startTime);
            formData.append('endTime', endTime);
            excelFiles.forEach((file) => formData.append('files', file, file.name));
            response = await fetch('/api/filter-excel', {
                method: 'POST',
                body: formData
            });
        }

        if (!response.ok) {
            let message = `Filter failed with status ${response.status}`;
            const errorText = await response.text();
            if (errorText) {
                try {
                    const errorJson = JSON.parse(errorText);
                    message = errorJson.detail || errorJson.error || message;
                } catch (parseError) {
                    message = errorText;
                }
            }
            throw new Error(message);
        }

        const contentType = response.headers.get('content-type') || '';
        if (contentType.includes('application/json')) {
            const result = await response.json();
            finalMessage = result.message || 'Filtered master Excel securely saved to destination.';
        } else {
            const blob = await response.blob();
            const fileName = ui.getDownloadFileName(response.headers.get('content-disposition')) || 'Master_Filtered.xlsx';
            ui.downloadBlob(blob, fileName);
            finalMessage = 'Filtered master Excel downloaded successfully.';
        }
        
        if (folderInput) folderInput.value = '';
        if (filesInput) filesInput.value = '';
    } catch (error) {
        console.error('Filter export failed', error);
        finalMessage = error.message || 'Filtering failed. Please try again.';
    } finally {
        ui.isFiltering = false;
        ui.updateFilterUiState(finalMessage);
    }
}
