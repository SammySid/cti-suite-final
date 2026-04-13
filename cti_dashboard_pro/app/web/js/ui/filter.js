// ── 12-hour custom time picker helpers ───────────────────────────────────────
// Returns a string like "4:00 PM" from the three select elements.
// Always 12h format — never influenced by OS/browser locale.
function _getPickerTime(hourId, minId, ampmId) {
    const h  = document.getElementById(hourId)?.value  || '04';
    const m  = document.getElementById(minId)?.value   || '00';
    const ap = document.getElementById(ampmId)?.value  || 'PM';
    const hNum = parseInt(h, 10) || 4;
    const mPad = String(parseInt(m, 10) || 0).padStart(2, '0');
    return `${hNum}:${mPad} ${ap}`;   // e.g. "4:00 PM"
}

// Parses any time string ("4:00 PM", "16:00", "4pm") and sets the selects.
function _setPickerTime(hourId, minId, ampmId, timeStr) {
    if (!timeStr) return;
    const str = String(timeStr).trim().toLowerCase();
    let hours = 4, mins = 0, ampm = 'PM';

    const hasPm = str.includes('pm');
    const hasAm = str.includes('am');
    const is12h = hasPm || hasAm;
    ampm = hasPm ? 'PM' : 'AM';

    const timePart = str.replace(/[apm]/g, '').trim();
    const [hStr, mStr] = timePart.split(':');
    hours = parseInt(hStr, 10) || 0;
    mins  = parseInt(mStr, 10) || 0;

    if (!is12h) {
        // 24h input → convert
        ampm  = hours >= 12 ? 'PM' : 'AM';
        hours = hours % 12 || 12;
    } else {
        if (hours === 0) hours = 12;
        if (hours > 12)  hours = hours % 12 || 12;
    }

    // Snap minutes to nearest 5
    mins = Math.round(mins / 5) * 5;
    if (mins >= 60) mins = 55;

    const hEl  = document.getElementById(hourId);
    const mEl  = document.getElementById(minId);
    const apEl = document.getElementById(ampmId);

    if (hEl)  hEl.value  = String(hours).padStart(2, '0');
    if (mEl)  mEl.value  = String(mins).padStart(2, '0');
    if (apEl) apEl.value = ampm;
}

// ── UI state ─────────────────────────────────────────────────────────────────
export function updateFilterUiState(ui, message = '') {
    const filterStatus = document.getElementById('filterStatus');
    const panelStatus  = document.getElementById('filterPanelStatus');
    const runBtn       = document.getElementById('runFilterAction');

    if (runBtn) {
        runBtn.disabled = ui.isFiltering;
        runBtn.classList.toggle('opacity-50',        ui.isFiltering);
        runBtn.classList.toggle('cursor-not-allowed', ui.isFiltering);
        runBtn.innerText = ui.isFiltering ? 'Processing...' : 'Generate Filtered Excel';
    }

    const resolvedMessage = message || (ui.isFiltering ? 'Processing uploaded files...' : 'Filter tool ready.');
    if (filterStatus) filterStatus.innerText = resolvedMessage;
    if (panelStatus)  panelStatus.innerText  = resolvedMessage;
}

// ── Process-All toggle ────────────────────────────────────────────────────────
function _applyProcessAllState(isAll) {
    ['filterStartTimeGroup', 'filterEndTimeGroup'].forEach(id => {
        const group = document.getElementById(id);
        if (!group) return;
        group.querySelectorAll('select').forEach(s => {
            s.disabled = isAll;
        });
        group.style.opacity      = isAll ? '0.35' : '';
        group.style.pointerEvents = isAll ? 'none'  : '';
    });
}

export function bindFilterProcessAllToggle() {
    const chk = document.getElementById('filterProcessAll');
    if (chk) {
        chk.addEventListener('change', () => _applyProcessAllState(chk.checked));
    }
}

// ── Sync stored settings → UI ─────────────────────────────────────────────────
export function syncFilterSettingsToUi(ui) {
    const pathInput    = document.getElementById('filterSourcePath');
    const destPathInput = document.getElementById('filterDestPath');
    const processAllChk = document.getElementById('filterProcessAll');

    if (pathInput)    pathInput.value    = ui.filterSettings.sourcePath || '';
    if (destPathInput) destPathInput.value = ui.filterSettings.destPath || '';

    // Restore pickers (fall back to 4:00 PM / 5:00 PM if nothing stored)
    _setPickerTime('filterStartHour', 'filterStartMin', 'filterStartAmPm',
        ui.filterSettings.startTime || '16:00');
    _setPickerTime('filterEndHour',   'filterEndMin',   'filterEndAmPm',
        ui.filterSettings.endTime   || '17:00');

    if (processAllChk) {
        processAllChk.checked = ui.filterSettings.processAll || false;
        _applyProcessAllState(processAllChk.checked);
    }
}

// ── Main filter action ────────────────────────────────────────────────────────
export async function runFilterTool(ui) {
    if (ui.isFiltering) return;

    const sourcePathInput = document.getElementById('filterSourcePath');
    const destPathInput   = document.getElementById('filterDestPath');
    const folderInput     = document.getElementById('filterExcelFolder');
    const filesInput      = document.getElementById('filterExcelFiles');
    const processAllChk   = document.getElementById('filterProcessAll');

    const processAll = processAllChk?.checked || false;
    const startTime  = processAll ? '' : _getPickerTime('filterStartHour', 'filterStartMin', 'filterStartAmPm');
    const endTime    = processAll ? '' : _getPickerTime('filterEndHour',   'filterEndMin',   'filterEndAmPm');
    const sourcePath = sourcePathInput?.value?.trim() || '';
    const destPath   = destPathInput?.value?.trim()   || '';

    const folderFiles = folderInput?.files ? Array.from(folderInput.files) : [];
    const manualFiles = filesInput?.files  ? Array.from(filesInput.files)  : [];
    const files       = folderFiles.length > 0 ? folderFiles : manualFiles;
    const SUPPORTED_EXT = ['.xlsx', '.xls'];
    const excelFiles  = files.filter(f => SUPPORTED_EXT.some(ext => f.name.toLowerCase().endsWith(ext)));

    if (!processAll && (!startTime || !endTime)) {
        ui.updateFilterUiState('Please choose both start and end time, or enable "Process All".');
        return;
    }
    if (!sourcePath && excelFiles.length === 0) {
        ui.updateFilterUiState('Please provide source folder path or select files.');
        return;
    }

    ui.filterSettings = { sourcePath, destPath, startTime, endTime, processAll };
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
                method:  'POST',
                headers: { 'Content-Type': 'application/json' },
                body:    JSON.stringify({ startTime, endTime, sourcePath, destPath })
            });
        } else {
            const formData = new FormData();
            formData.append('startTime', startTime);
            formData.append('endTime',   endTime);
            excelFiles.forEach(f => formData.append('files', f, f.name));
            response = await fetch('/api/filter-excel', { method: 'POST', body: formData });
        }

        if (!response.ok) {
            let message = `Filter failed with status ${response.status}`;
            const errorText = await response.text();
            if (errorText) {
                try {
                    const errorJson = JSON.parse(errorText);
                    message = errorJson.detail || errorJson.error || message;
                } catch { message = errorText; }
            }
            throw new Error(message);
        }

        const contentType = response.headers.get('content-type') || '';
        if (contentType.includes('application/json')) {
            const result = await response.json();
            finalMessage = result.message || 'Filtered master Excel securely saved to destination.';
        } else {
            const blob     = await response.blob();
            const fileName = ui.getDownloadFileName(response.headers.get('content-disposition')) || 'Master_Filtered.xlsx';
            ui.downloadBlob(blob, fileName);
            finalMessage = 'Filtered master Excel downloaded successfully.';
        }

        if (folderInput) folderInput.value = '';
        if (filesInput)  filesInput.value  = '';
    } catch (error) {
        console.error('Filter export failed', error);
        finalMessage = error.message || 'Filtering failed. Please try again.';
    } finally {
        ui.isFiltering = false;
        ui.updateFilterUiState(finalMessage);
    }
}
