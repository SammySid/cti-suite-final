export async function generateReport(ui) {
    const btn = document.getElementById('generateReportBtn');
    const originalText = btn.innerHTML;
    
    // Set loading state
    btn.innerHTML = `<svg class="animate-spin -ml-1 mr-3 h-5 w-5 text-cyan-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg> GENERATING PDF...`;
    btn.disabled = true;
    
    // Construct the mega payload, combining manual inputs with calculation context
    const payload = {
        client: document.getElementById('rep-client')?.value || "Client",
        asset: document.getElementById('rep-asset')?.value || "Asset",
        test_date: document.getElementById('rep-test-date')?.value || ui.inputs.date,
        report_date: document.getElementById('rep-report-date')?.value || new Date().toISOString().split('T')[0],
        
        preamble_paragraphs: [document.getElementById('rep-preamble')?.value || "Engineered testing report"],
        conclusions: [document.getElementById('rep-conclusions')?.value || "Evaluation complete."],
        
        // Using some hardcoded fallback geometry for demo isolation sake when worker isn't fully spooled
        test_range: ui.inputs.designHWT - ui.inputs.designCWT,
        math_results: {
            adj_flow: document.getElementById('rep-flow')?.value || 3000,
            pred_cwt: (ui.inputs.designCWT - 1.5).toFixed(2),
            test_cwt: document.getElementById('rep-cwt')?.value || ui.inputs.designCWT,
            shortfall: 1.5,
            capability: "74.8"
        },
        
        // Static table mappings for dummy structural demonstration to replicate dhariwal
        members_client: ["Mr Shrikant Shrivastava ( Remote)", "Mr GAURAV HANTODKAR", "Mr PAWAN GAWANDE"],
        members_ssctc: ["Mr SURESH SARMA", "Mr SANJAY GORAD", "Mr MRADUL VISHWAKARMA", "Mr PARAG VISHWAKARMA", "Mr RAHUL MANKE"],
        assessment_method: [
            "Pre test was conducted on 27 March 2026.",
            "Cell no 2 has been isolated at the basin level for collection of cold water directly from the rain zone."
        ],
        instrument_placement: [
            "Air flow was measured using Data Logging anemometer.",
            "Hot water – was taken at inlet of the hot water to the cooling tower which is common for all cells."
        ],
        suggestions: [
            "With 3 pumps operating and one cell under higher flow velocities through the duct would be higher by 1.23% this would naturally cause a higher static pressure at the back end."
        ],
        final_data_table: [
            {"name": "Water Flow", "unit": "M3/hr", "test1": "2998", "test2": "3067", "test3": document.getElementById('rep-flow')?.value || "3680"},
            {"name": "WBT", "unit": "Deg.C", "test1": "25.25", "test2": "24.22", "test3": ui.inputs.designWBT},
            {"name": "HWT", "unit": "Deg.C", "test1": "44.67", "test2": "43.21", "test3": document.getElementById('rep-hwt')?.value || "42.13"},
            {"name": "CWT", "unit": "Deg.C", "test1": "35.08", "test2": "32.89", "test3": document.getElementById('rep-cwt')?.value || "32.40"},
            {"name": "Fan Power At Motor Inlet", "unit": "KW", "test1": "97.04", "test2": "116.24", "test3": "117"},
            {"name": "Fan Air Flow", "unit": "M3/s", "test1": "405.97", "test2": "499", "test3": document.getElementById('rep-air')?.value || "485"},
            {"name": "Range", "unit": "Deg.C", "test1": "9.59", "test2": "10.32", "test3": ui.inputs.designHWT - ui.inputs.designCWT}
        ],
        data_notes: [
            "Improvement of 1.5 appears high in \"TEST 2\" so we consider that as 0.7 Deg C",
            "single cell isolated testing involves UNCERAINITY in measurement due to turbulent water flow"
        ],
        airflow: {
            "avg_velocity": "4.99",
            "area": "92.25",
            "total_flow": document.getElementById('rep-air')?.value || "459.84"
        },
        intersect: {
            "f90_flow": "3477", "f90_cwt": "27.84",
            "f100_flow": "3864", "f100_cwt": "28.83",
            "f110_flow": "4250", "f110_cwt": "30.21"
        }
    };

    try:
        const response = await fetch('/api/generate-pdf-report', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            throw new Error(`Server returned ${response.status}: ${await response.text()}`);
        }

        // Convert the byte stream to a blob and trigger browser download
        const blob = await response.blob();
        if (window.navigator && window.navigator.msSaveOrOpenBlob) {
            window.navigator.msSaveOrOpenBlob(blob, "ATC105_Performance_Report.pdf");
        } else {
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = url;
            a.download = "ATC105_Performance_Report.pdf";
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            a.remove();
        }
    } catch (err) {
        console.error("Failed to generate PDF Report", err);
        alert("Failed to generate report: " + err.message);
    } finally {
        // Restore button state
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
}
