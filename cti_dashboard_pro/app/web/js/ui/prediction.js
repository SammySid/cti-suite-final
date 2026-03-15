import { calculations } from '../calculations.js';

export function calculatePrediction(ui) {
    // Only calculate if all inputs are valid numbers
    const wbt = parseFloat(document.getElementById('pred-wbt').value);
    const range = parseFloat(document.getElementById('pred-range').value);
    const lg = parseFloat(document.getElementById('pred-lg').value);
    const constC = parseFloat(document.getElementById('pred-c').value);
    const constM = parseFloat(document.getElementById('pred-m').value);

    const inputsValid = [wbt, range, lg, constC, constM].every(val => Number.isFinite(val));
    if (!inputsValid) return; // Wait for valid input

    const result = calculations.solveOffDesignCWT(wbt, range, lg, constC, constM);

    if (result && result.cwt) {
        // Update Results Cards
        document.getElementById('pred-out-cwt').innerText = result.cwt.toFixed(2);
        document.getElementById('pred-out-app').innerText = result.approach.toFixed(2);
        document.getElementById('pred-out-hwt').innerText = result.hwt.toFixed(2) + '°C';
        document.getElementById('pred-out-demand').innerText = result.demandKavl.toFixed(4);
        document.getElementById('pred-out-supply').innerText = result.supplyKavl.toFixed(4);
    } else {
        // Unsolvable state (e.g., physically impossible inputs)
        document.getElementById('pred-out-cwt').innerText = "ERR";
        document.getElementById('pred-out-app').innerText = "ERR";
        document.getElementById('pred-out-hwt').innerText = "--";
        document.getElementById('pred-out-demand').innerText = "--";
        document.getElementById('pred-out-supply').innerText = "--";
    }
}
