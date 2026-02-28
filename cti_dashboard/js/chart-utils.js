/**
 * ============================================================
 * CHART UTILITIES — Interactive Visualization
 * ============================================================
 * 
 * Provides chart drawing and animation utilities using
 * HTML5 Canvas for rendering psychrometric and Merkel data.
 * 
 * Features:
 *   - Smooth line charts with gradient fills
 *   - Animated data point transitions
 *   - Responsive canvas sizing
 *   - Tooltip support
 *   - Dark-theme optimized color palette
 * 
 * @module chart-utils
 * @version 1.0.0
 */

/**
 * Color palette for charts — designed for dark backgrounds.
 */
const CHART_COLORS = {
    primary: '#6C63FF',    // Purple accent
    secondary: '#00D9FF',    // Cyan
    tertiary: '#FF6B8A',    // Rose
    quaternary: '#FFD93D',    // Gold
    quinary: '#4ADE80',    // Green
    senary: '#F97316',    // Orange
    grid: 'rgba(255, 255, 255, 0.06)',
    gridLabel: 'rgba(255, 255, 255, 0.4)',
    axis: 'rgba(255, 255, 255, 0.15)',
    tooltip: 'rgba(15, 15, 30, 0.95)',
};

/**
 * Draw a responsive line chart on a canvas element.
 * 
 * @param {HTMLCanvasElement} canvas - Target canvas element
 * @param {Object} config - Chart configuration
 * @param {Array<{x: number, y: number}>} config.data - Data points
 * @param {string} [config.color] - Line color
 * @param {string} [config.label] - Data label
 * @param {string} [config.xLabel] - X-axis label
 * @param {string} [config.yLabel] - Y-axis label
 * @param {number} [config.highlightX] - X value to highlight
 * @param {string} [config.unit] - Unit string for tooltip
 */
function drawLineChart(canvas, config) {
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();

    // Set up high-DPI canvas
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    const W = rect.width;
    const H = rect.height;
    const pad = { top: 20, right: 20, bottom: 40, left: 55 };
    const plotW = W - pad.left - pad.right;
    const plotH = H - pad.top - pad.bottom;

    const { data, color = CHART_COLORS.primary, label = '',
        xLabel = '', yLabel = '', highlightX = null, unit = '' } = config;

    if (!data || data.length < 2) {
        ctx.fillStyle = 'rgba(255,255,255,0.3)';
        ctx.font = '13px Inter, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('No data', W / 2, H / 2);
        return;
    }

    // Calculate bounds with padding
    const xs = data.map(d => d.x);
    const ys = data.map(d => d.y);
    const xMin = Math.min(...xs);
    const xMax = Math.max(...xs);
    const yMin = Math.min(...ys);
    const yMax = Math.max(...ys);
    const yRange = yMax - yMin || 1;
    const yPad = yRange * 0.08;
    const yLo = yMin - yPad;
    const yHi = yMax + yPad;

    // Mapping functions
    const mapX = x => pad.left + (x - xMin) / (xMax - xMin || 1) * plotW;
    const mapY = y => pad.top + (1 - (y - yLo) / (yHi - yLo)) * plotH;

    // Clear
    ctx.clearRect(0, 0, W, H);

    // --- Grid lines ---
    ctx.strokeStyle = CHART_COLORS.grid;
    ctx.lineWidth = 1;
    const gridLines = 5;

    for (let i = 0; i <= gridLines; i++) {
        const y = pad.top + (plotH / gridLines) * i;
        ctx.beginPath();
        ctx.moveTo(pad.left, y);
        ctx.lineTo(W - pad.right, y);
        ctx.stroke();

        // Y labels
        const val = yHi - (yHi - yLo) * (i / gridLines);
        ctx.fillStyle = CHART_COLORS.gridLabel;
        ctx.font = '11px Inter, sans-serif';
        ctx.textAlign = 'right';
        ctx.fillText(formatChartValue(val), pad.left - 8, y + 4);
    }

    // X labels
    const xSteps = Math.min(6, data.length);
    for (let i = 0; i < xSteps; i++) {
        const idx = Math.floor(i * (data.length - 1) / (xSteps - 1));
        const x = mapX(data[idx].x);
        ctx.fillStyle = CHART_COLORS.gridLabel;
        ctx.font = '11px Inter, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(formatChartValue(data[idx].x), x, H - pad.bottom + 18);
    }

    // Axis labels
    ctx.fillStyle = 'rgba(255,255,255,0.5)';
    ctx.font = '12px Inter, sans-serif';
    ctx.textAlign = 'center';
    if (xLabel) {
        ctx.fillText(xLabel, pad.left + plotW / 2, H - 3);
    }
    if (yLabel) {
        ctx.save();
        ctx.translate(12, pad.top + plotH / 2);
        ctx.rotate(-Math.PI / 2);
        ctx.fillText(yLabel, 0, 0);
        ctx.restore();
    }

    // --- Gradient fill under line ---
    const gradient = ctx.createLinearGradient(0, pad.top, 0, pad.top + plotH);
    gradient.addColorStop(0, hexToRgba(color, 0.25));
    gradient.addColorStop(1, hexToRgba(color, 0.0));

    ctx.beginPath();
    ctx.moveTo(mapX(data[0].x), pad.top + plotH);
    for (const d of data) {
        ctx.lineTo(mapX(d.x), mapY(d.y));
    }
    ctx.lineTo(mapX(data[data.length - 1].x), pad.top + plotH);
    ctx.closePath();
    ctx.fillStyle = gradient;
    ctx.fill();

    // --- Line ---
    ctx.beginPath();
    ctx.moveTo(mapX(data[0].x), mapY(data[0].y));
    for (let i = 1; i < data.length; i++) {
        ctx.lineTo(mapX(data[i].x), mapY(data[i].y));
    }
    ctx.strokeStyle = color;
    ctx.lineWidth = 2.5;
    ctx.lineJoin = 'round';
    ctx.stroke();

    // --- Highlight point ---
    if (highlightX !== null) {
        // Find nearest data point
        let nearestIdx = 0;
        let nearestDist = Infinity;
        for (let i = 0; i < data.length; i++) {
            const dist = Math.abs(data[i].x - highlightX);
            if (dist < nearestDist) {
                nearestDist = dist;
                nearestIdx = i;
            }
        }

        const px = mapX(data[nearestIdx].x);
        const py = mapY(data[nearestIdx].y);

        // Glow
        const glowGrad = ctx.createRadialGradient(px, py, 0, px, py, 12);
        glowGrad.addColorStop(0, hexToRgba(color, 0.4));
        glowGrad.addColorStop(1, hexToRgba(color, 0));
        ctx.beginPath();
        ctx.arc(px, py, 12, 0, Math.PI * 2);
        ctx.fillStyle = glowGrad;
        ctx.fill();

        // Dot
        ctx.beginPath();
        ctx.arc(px, py, 4, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.fill();
        ctx.strokeStyle = '#fff';
        ctx.lineWidth = 1.5;
        ctx.stroke();

        // Value tooltip
        const tooltipText = `${formatChartValue(data[nearestIdx].y)}${unit ? ' ' + unit : ''}`;
        ctx.font = 'bold 12px Inter, sans-serif';
        const textW = ctx.measureText(tooltipText).width;
        const tooltipX = Math.max(pad.left, Math.min(px - textW / 2 - 8, W - pad.right - textW - 16));
        const tooltipY = py - 28;

        // Tooltip background
        ctx.fillStyle = CHART_COLORS.tooltip;
        roundRect(ctx, tooltipX, tooltipY, textW + 16, 22, 6);
        ctx.fill();
        ctx.strokeStyle = hexToRgba(color, 0.5);
        ctx.lineWidth = 1;
        roundRect(ctx, tooltipX, tooltipY, textW + 16, 22, 6);
        ctx.stroke();

        // Tooltip text
        ctx.fillStyle = color;
        ctx.textAlign = 'left';
        ctx.fillText(tooltipText, tooltipX + 8, tooltipY + 16);
    }
}

/**
 * Draw a multi-line comparison chart.
 * 
 * @param {HTMLCanvasElement} canvas - Target canvas element
 * @param {Object} config - Chart configuration
 * @param {Array<{data: Array, color: string, label: string}>} config.series - Data series
 * @param {string} [config.xLabel] - X-axis label
 * @param {string} [config.yLabel] - Y-axis label
 */
function drawMultiLineChart(canvas, config) {
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();

    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    const W = rect.width;
    const H = rect.height;
    const pad = { top: 25, right: 15, bottom: 40, left: 55 };
    const plotW = W - pad.left - pad.right;
    const plotH = H - pad.top - pad.bottom;

    const { series, xLabel = '', yLabel = '' } = config;

    if (!series || series.length === 0) return;

    // Calculate global bounds
    let xMin = Infinity, xMax = -Infinity, yMin = Infinity, yMax = -Infinity;
    for (const s of series) {
        for (const d of s.data) {
            xMin = Math.min(xMin, d.x);
            xMax = Math.max(xMax, d.x);
            yMin = Math.min(yMin, d.y);
            yMax = Math.max(yMax, d.y);
        }
    }

    const yRange = yMax - yMin || 1;
    const yPad = yRange * 0.08;
    const yLo = yMin - yPad;
    const yHi = yMax + yPad;

    const mapX = x => pad.left + (x - xMin) / (xMax - xMin || 1) * plotW;
    const mapY = y => pad.top + (1 - (y - yLo) / (yHi - yLo)) * plotH;

    ctx.clearRect(0, 0, W, H);

    // Grid
    ctx.strokeStyle = CHART_COLORS.grid;
    ctx.lineWidth = 1;
    for (let i = 0; i <= 5; i++) {
        const y = pad.top + (plotH / 5) * i;
        ctx.beginPath();
        ctx.moveTo(pad.left, y);
        ctx.lineTo(W - pad.right, y);
        ctx.stroke();

        const val = yHi - (yHi - yLo) * (i / 5);
        ctx.fillStyle = CHART_COLORS.gridLabel;
        ctx.font = '11px Inter, sans-serif';
        ctx.textAlign = 'right';
        ctx.fillText(formatChartValue(val), pad.left - 8, y + 4);
    }

    // X labels
    if (series[0] && series[0].data.length > 0) {
        const refData = series[0].data;
        const xSteps = Math.min(6, refData.length);
        for (let i = 0; i < xSteps; i++) {
            const idx = Math.floor(i * (refData.length - 1) / (xSteps - 1));
            const x = mapX(refData[idx].x);
            ctx.fillStyle = CHART_COLORS.gridLabel;
            ctx.font = '11px Inter, sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(formatChartValue(refData[idx].x), x, H - pad.bottom + 18);
        }
    }

    // Axis labels
    ctx.fillStyle = 'rgba(255,255,255,0.5)';
    ctx.font = '12px Inter, sans-serif';
    ctx.textAlign = 'center';
    if (xLabel) ctx.fillText(xLabel, pad.left + plotW / 2, H - 3);
    if (yLabel) {
        ctx.save();
        ctx.translate(12, pad.top + plotH / 2);
        ctx.rotate(-Math.PI / 2);
        ctx.fillText(yLabel, 0, 0);
        ctx.restore();
    }

    // Draw each series
    for (const s of series) {
        if (!s.data || s.data.length < 2) continue;

        ctx.beginPath();
        ctx.moveTo(mapX(s.data[0].x), mapY(s.data[0].y));
        for (let i = 1; i < s.data.length; i++) {
            ctx.lineTo(mapX(s.data[i].x), mapY(s.data[i].y));
        }
        ctx.strokeStyle = s.color;
        ctx.lineWidth = 2;
        ctx.lineJoin = 'round';
        ctx.stroke();
    }

    // Legend
    const legendY = pad.top - 5;
    let legendX = pad.left;
    ctx.font = '11px Inter, sans-serif';
    for (const s of series) {
        ctx.fillStyle = s.color;
        ctx.fillRect(legendX, legendY - 8, 14, 3);
        ctx.fillStyle = 'rgba(255,255,255,0.7)';
        ctx.textAlign = 'left';
        ctx.fillText(s.label, legendX + 18, legendY);
        legendX += ctx.measureText(s.label).width + 35;
    }
}

// ============================================================
// HELPER FUNCTIONS
// ============================================================

/**
 * Convert hex color to RGBA string.
 * @param {string} hex - Hex color string (e.g., '#6C63FF')
 * @param {number} alpha - Opacity (0–1)
 * @returns {string} RGBA color string
 */
function hexToRgba(hex, alpha) {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

/**
 * Draw a rounded rectangle path.
 * @param {CanvasRenderingContext2D} ctx - Canvas context
 * @param {number} x - X position
 * @param {number} y - Y position
 * @param {number} w - Width
 * @param {number} h - Height
 * @param {number} r - Border radius
 */
function roundRect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.lineTo(x + w - r, y);
    ctx.quadraticCurveTo(x + w, y, x + w, y + r);
    ctx.lineTo(x + w, y + h - r);
    ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
    ctx.lineTo(x + r, y + h);
    ctx.quadraticCurveTo(x, y + h, x, y + h - r);
    ctx.lineTo(x, y + r);
    ctx.quadraticCurveTo(x, y, x + r, y);
    ctx.closePath();
}

/**
 * Format a number for chart display.
 * @param {number} val - Value to format
 * @returns {string} Formatted string
 */
function formatChartValue(val) {
    if (Math.abs(val) >= 1000) return val.toFixed(0);
    if (Math.abs(val) >= 100) return val.toFixed(1);
    if (Math.abs(val) >= 1) return val.toFixed(2);
    return val.toFixed(4);
}

export { drawLineChart, drawMultiLineChart, CHART_COLORS, hexToRgba };
