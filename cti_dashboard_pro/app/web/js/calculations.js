/**
 * Calculation Core for Cooling Tower Performance
 * Includes Psychrometric properties and Merkel Method (CTI ATC 105)
 */

import { psychrometrics, initPsychroEngine } from './psychro-engine.js';
import { merkelKaVL, initMerkelEngine } from './merkel-engine.js';

export const calculations = {
    init: async (psychroLibPath = './data/psychro_f_alt.bin', merkelLibPath = './data/merkel_poly.bin') => {
        await Promise.all([
            initPsychroEngine(psychroLibPath),
            initMerkelEngine(merkelLibPath)
        ]);
    },

    /**
     * Psychrometric properties calculation using the new engine
     */
    getPsychrometricProps: (twb) => {
        try {
            const props = psychrometrics(twb, twb);
            return { ws: props.HR, hs: props.H, pws: props.P };
        } catch (e) {
            return { ws: 0, hs: 0, pws: 0 };
        }
    },

    /**
     * CTI Merkel demand calculation using new merkelKaVL engine
     */
    calculateDemandKaVL: (twb, hwt, cwt, lgRatio) => {
        try {
            const result = merkelKaVL(hwt, cwt, twb, lgRatio);
            if (result && result.valid) {
                return result.kavl;
            }
            return NaN;
        } catch (e) {
            return NaN;
        }
    },

    calculateSupplyKaVL: (lgRatio, constantC, constantM) => {
        return constantC * Math.pow(lgRatio, -constantM);
    },

    /**
     * Find CWT for given WBT and range percentage
     */
    findCWT: (inputs, wbt, rangePercent, flowPercent) => {
        const designRange = inputs.designHWT - inputs.designCWT;
        const actualRange = designRange * rangePercent / 100;
        const actualLG = inputs.lgRatio * (flowPercent / 100);

        const supplyKaVL = calculations.calculateSupplyKaVL(actualLG, inputs.constantC, inputs.constantM);

        let bestCWT = wbt + 1;
        let minDiff = Infinity;

        for (let approach = 0.5; approach < 30; approach += 0.02) {
            const cwtGuess = wbt + approach;
            const hwt = cwtGuess + actualRange;

            if (hwt > 80 || cwtGuess < wbt) continue;

            try {
                const demandKaVL = calculations.calculateDemandKaVL(wbt, hwt, cwtGuess, actualLG);
                if (isNaN(demandKaVL) || demandKaVL <= 0 || demandKaVL > 100) continue;

                const diff = Math.abs(supplyKaVL - demandKaVL);
                if (diff < minDiff) {
                    minDiff = diff;
                    bestCWT = cwtGuess;
                }
            } catch (e) {
                continue;
            }
        }

        return bestCWT;
    },

    /**
     * Solves for the predicted CWT (Performance Prediction Off-Design capability)
     * Given WBT, Range, L/G, C, and m, find the CWT that balances Demand/Supply
     */
    solveOffDesignCWT: (wbt, range, lg, constC, constM) => {
        // First get the physical tower's supply capability
        const supplyKavl = calculations.calculateSupplyKaVL(lg, constC, constM);
        if (isNaN(supplyKavl) || supplyKavl <= 0) {
            return null;
        }

        // We will guess the Approach (CWT - WBT). Common range is 0.5 to 30 as a fallback.
        // The relationship is invariant: HWT = CWT + Range 
        // We want Demand KaV/L to exactly equal the Supply KaV/L
        
        let bestCwt = NaN;
        let bestDiff = Infinity;
        let matchedDemand = NaN;
        
        // Scan with a simple linear loop initially (we can use a bisect method if it's too slow but this is usually fast enough in JS)
        // From 0.5 deg approach up to a max 30 deg approach
        for (let approach = 0.5; approach <= 30.0; approach += 0.01) {
            const guessCwt = wbt + approach;
            const guessHwt = guessCwt + range;

            try {
                // To avoid breaking the engine, ensure valid temps
                if (guessHwt > 80 || guessCwt < wbt) continue;

                const demandKavl = calculations.calculateDemandKaVL(wbt, guessHwt, guessCwt, lg);
                if (isNaN(demandKavl) || demandKavl <= 0) continue;

                const diff = Math.abs(demandKavl - supplyKavl);
                if (diff < bestDiff) {
                    bestDiff = diff;
                    bestCwt = guessCwt;
                    matchedDemand = demandKavl;
                }
                
                // Since demand kaV/L decreases as approach increases, once we cross it we can optionally stop, 
                // but diff scanning over the entire window guarantees we find the absolute minimum safely without getting stuck on local anomalies
            } catch (e) {
                continue;
            }
        }

        if (isNaN(bestCwt) || bestDiff > 0.5) return null; // Unsolvable

        return {
            cwt: bestCwt,
            approach: bestCwt - wbt,
            hwt: bestCwt + range,
            demandKavl: matchedDemand,
            supplyKavl: supplyKavl
        };
    }
};
