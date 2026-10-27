// charts.js - Binary Options Quantitative Terminal Charting Engine (Milestone 3)

// Default Chart.js defaults
Chart.defaults.color = '#94a3b8';
Chart.defaults.font.family = "'Inter', system-ui, -apple-system, sans-serif";
if (Chart.defaults.plugins && Chart.defaults.plugins.tooltip) {
    Chart.defaults.plugins.tooltip.backgroundColor = 'rgba(19, 29, 49, 0.96)';
    Chart.defaults.plugins.tooltip.titleColor = '#f8fafc';
    Chart.defaults.plugins.tooltip.bodyColor = '#94a3b8';
    Chart.defaults.plugins.tooltip.borderColor = 'rgba(245, 158, 11, 0.25)';
    Chart.defaults.plugins.tooltip.borderWidth = 1;
    Chart.defaults.plugins.tooltip.padding = 12;
    Chart.defaults.plugins.tooltip.cornerRadius = 8;
    Chart.defaults.plugins.tooltip.titleFont = { size: 13, weight: '700', family: "'JetBrains Mono', monospace" };
    Chart.defaults.plugins.tooltip.bodyFont = { size: 13, family: "'JetBrains Mono', monospace" };
}

function createCandlestickChart(containerId) {
    if (typeof window !== 'undefined' && window.createCandlestickChart && window.createCandlestickChart !== createCandlestickChart) {
        return window.createCandlestickChart(containerId);
    }
    const el = document.getElementById(containerId);
    if (!el) return null;
    if (el.__lwChartInstance) {
        try { el.__lwChartInstance.remove(); } catch (e) { console.warn('Error removing chart:', e); }
        el.__lwChartInstance = null;
    }
    const chart = LightweightCharts.createChart(el, {
        layout: { background: { type: 'solid', color: 'transparent' }, textColor: '#94a3b8', fontSize: 13, fontFamily: "'Inter', sans-serif" },
        grid: { vertLines: { color: 'rgba(255, 255, 255, 0.03)' }, horzLines: { color: 'rgba(255, 255, 255, 0.03)' } },
        crosshair: { mode: LightweightCharts.CrosshairMode.Normal, vertLine: { color: 'rgba(245, 158, 11, 0.45)', style: 3, labelBackgroundColor: '#131d31' }, horzLine: { color: 'rgba(245, 158, 11, 0.45)', style: 3, labelBackgroundColor: '#131d31' } },
        timeScale: { timeVisible: true, secondsVisible: false, borderColor: 'rgba(255, 255, 255, 0.07)', rightOffset: 10, barSpacing: 10, minBarSpacing: 0.5, autoScale: true, shiftVisibleRangeOnNewBar: true },
        rightPriceScale: { borderColor: 'rgba(255, 255, 255, 0.07)', autoScale: true, scaleMargins: { top: 0.1, bottom: 0.1 } },
        handleScroll: { mouseWheel: true, pressedMove: true, horzTouchDrag: true, vertTouchDrag: true },
        handleScale: { axisPressedMouseMove: true, mouseWheel: true, pinch: true }
    });
    const candleSeries = chart.addCandlestickSeries({
        upColor: '#10b981', downColor: '#e11d48', borderVisible: false, wickUpColor: '#10b981', wickDownColor: '#e11d48',
        priceFormat: { type: 'price', precision: 5, minMove: 0.00001 }
    });
    el.__lwChartInstance = chart;
    return { chart, candleSeries };
}

function updateCandlestickChart(series, candle) {
    if (series && candle) {
        try {
            series.update(candle);
        } catch (e) {
            console.warn('[Chart] Error updating candlestick:', e);
        }
    }
}

function addSignalMarkers(series, signals) {
    if (!series || !signals) return;
    if (typeof buildChartMarkers === 'function') {
        series.setMarkers(buildChartMarkers(signals));
        return;
    }
    series.setMarkers(signals.map(s => {
        const isLong = (s.direction === 'CALL' || s.direction === 'LONG' || s.type === 'CALL');
        return { time: s.time, position: isLong ? 'belowBar' : 'aboveBar', color: isLong ? '#10b981' : '#e11d48', shape: isLong ? 'arrowUp' : 'arrowDown', text: isLong ? '▲ LONG' : '▼ SHORT' };
    }));
}

function formatYAxisTick(value, useLog) {
    if (value === 0) return '$0.00';
    const absVal = Math.abs(value);
    if (useLog) {
        const log10 = Math.log10(absVal);
        if (Math.abs(log10 - Math.round(log10)) > 1e-4) return null;
    }
    const prefix = value < 0 ? '-$' : '$';
    if (absVal >= 1000000) return prefix + (absVal / 1000000).toFixed(absVal % 1000000 === 0 ? 0 : 1) + 'M';
    if (absVal >= 1000) return prefix + (absVal / 1000).toFixed(absVal % 1000 === 0 ? 0 : 1) + 'k';
    if (absVal >= 1) return prefix + (absVal % 1 === 0 ? absVal.toFixed(0) : absVal.toFixed(2));
    return prefix + absVal.toFixed(2);
}

function createEquityCurve(canvasId, equityPoints, rawLabels) {
    const el = document.getElementById(canvasId);
    if (!el) return;
    const ctx = el.getContext('2d');
    window[canvasId + '_data'] = { equityPoints, rawLabels };
    if (window[canvasId + 'Inst']) window[canvasId + 'Inst'].destroy();
    
    let values = [], labels = [];
    if (Array.isArray(equityPoints) && equityPoints.length > 0 && typeof equityPoints[0] === 'object' && equityPoints[0] !== null) {
        values = equityPoints.map(e => e.equity !== undefined ? e.equity : (e.y !== undefined ? e.y : 0));
        labels = equityPoints.map((e, i) => {
            if (e.time) {
                const d = new Date(e.time < 2e9 ? e.time * 1000 : e.time);
                const yr = d.getFullYear(), mo = String(d.getMonth() + 1).padStart(2, '0'), da = String(d.getDate()).padStart(2, '0');
                const hr = String(d.getHours()).padStart(2, '0'), mi = String(d.getMinutes()).padStart(2, '0');
                return (hr !== '00' || mi !== '00') ? `${yr}-${mo}-${da} ${hr}:${mi}` : `${yr}-${mo}-${da}`;
            }
            return `#${i + 1}`;
        });
    } else {
        values = equityPoints || [];
        labels = (rawLabels && rawLabels.length === values.length) ? rawLabels : values.map((_, i) => `#${i + 1}`);
    }
    const maxVal = values.length > 0 ? Math.max(...values) : 1000;
    const minVal = values.length > 0 ? Math.min(...values) : 0;
    const autoLog = (maxVal / Math.max(minVal, 0.01)) > 100 && minVal >= 1.0;
    const scalePref = window[canvasId + '_scaleMode'] || 'auto';
    const useLog = (scalePref === 'log') ? (minVal >= 1.0) : (scalePref === 'linear' ? false : autoLog);
    const cleanedData = useLog ? values.map(v => Math.max(v, 1.0)) : values;
    const valRange = maxVal - minVal;
    const padding = valRange > 0 ? valRange * 0.05 : 10;
    const dynamicSuggestedMin = !useLog && minVal >= 0 ? Math.max(0, minVal - padding) : (minVal < 0 ? minVal - padding : undefined);
    const dynamicSuggestedMax = !useLog ? maxVal + padding : undefined;

    window[canvasId + 'Inst'] = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Capital',
                data: cleanedData,
                borderColor: '#06b6d4',
                backgroundColor: function(context) {
                    const { ctx: c, chartArea: ca } = context.chart;
                    if (!ca) return 'rgba(6, 182, 212, 0.12)';
                    const grad = c.createLinearGradient(0, ca.top, 0, ca.bottom);
                    grad.addColorStop(0, 'rgba(6, 182, 212, 0.22)');
                    grad.addColorStop(1, 'rgba(6, 182, 212, 0.00)');
                    return grad;
                },
                borderWidth: 2, fill: true, tension: 0.15, pointRadius: 0, pointHoverRadius: 4,
                pointHoverBackgroundColor: '#06b6d4', pointHoverBorderColor: '#ffffff', pointHoverBorderWidth: 2
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            scales: {
                x: { display: true, grid: { color: 'rgba(255, 255, 255, 0.03)' }, ticks: { color: '#94a3b8', maxTicksLimit: 8, font: { size: 10, family: "'Inter', sans-serif" } }, title: { display: true, text: 'Línea de Tiempo (Fechas / Histórico)', color: '#94a3b8', font: { size: 10, weight: '500', family: "'Inter', sans-serif" } } },
                y: {
                    type: useLog ? 'logarithmic' : 'linear', grid: { color: 'rgba(255, 255, 255, 0.03)' },
                    min: useLog ? Math.max(1, Math.pow(10, Math.floor(Math.log10(Math.max(minVal, 1))))) : undefined,
                    suggestedMin: dynamicSuggestedMin, suggestedMax: dynamicSuggestedMax,
                    ticks: { color: '#94a3b8', maxTicksLimit: 6, font: { size: 10, family: "'JetBrains Mono', monospace" }, callback: (v) => formatYAxisTick(v, useLog) }
                }
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: 'rgba(19, 29, 49, 0.96)', titleColor: '#f8fafc', bodyColor: '#94a3b8', borderColor: 'rgba(245, 158, 11, 0.25)', borderWidth: 1, padding: 10, cornerRadius: 6,
                    titleFont: { size: 11, weight: '600', family: "'JetBrains Mono', monospace" }, bodyFont: { size: 11, family: "'JetBrains Mono', monospace" },
                    callbacks: {
                        title: items => items && items.length ? `Op. #${items[0].dataIndex + 1} (${items[0].label})` : '',
                        label: ctx => `Capital Acumulado: $${Number(ctx.raw).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
                    }
                }
            }
        }
    });
}

function createBarChart(canvasId, labels, values, title, color = '#f59e0b') {
    const el = document.getElementById(canvasId);
    if (!el) return;
    const ctx = el.getContext('2d');
    if (window[canvasId + 'Inst']) window[canvasId + 'Inst'].destroy();
    window[canvasId + 'Inst'] = new Chart(ctx, {
        type: 'bar',
        data: { labels: labels, datasets: [{ label: title, data: values, backgroundColor: color, borderRadius: 4 }] },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: { backgroundColor: 'rgba(19, 29, 49, 0.96)', titleColor: '#f8fafc', bodyColor: '#94a3b8', borderColor: 'rgba(245, 158, 11, 0.25)', borderWidth: 1, padding: 10, cornerRadius: 6, titleFont: { size: 11, weight: '600', family: "'JetBrains Mono', monospace" }, bodyFont: { size: 11, family: "'JetBrains Mono', monospace" } }
            },
            scales: {
                x: { grid: { color: 'rgba(255, 255, 255, 0.03)' }, ticks: { color: '#94a3b8', font: { size: 10, family: "'Inter', sans-serif" } } },
                y: { grid: { color: 'rgba(255, 255, 255, 0.03)' }, ticks: { color: '#94a3b8', font: { size: 10, family: "'JetBrains Mono', monospace" } } }
            }
        }
    });
}

function createGrowthRateChart(canvasId, ns, g_values, optimal_n) {
    const el = document.getElementById(canvasId);
    if (!el) return;
    const ctx = el.getContext('2d');
    if (window.gnChartInst) window.gnChartInst.destroy();
    if (window[canvasId + 'Inst']) window[canvasId + 'Inst'].destroy();
    const colors = ns.map(n => n === optimal_n ? '#10b981' : '#06b6d4');
    const inst = new Chart(ctx, {
        type: 'bar',
        data: { labels: ns, datasets: [{ label: 'G(N)', data: g_values, backgroundColor: colors, borderRadius: 4 }] },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: { backgroundColor: 'rgba(19, 29, 49, 0.96)', titleColor: '#f8fafc', bodyColor: '#94a3b8', borderColor: 'rgba(245, 158, 11, 0.25)', borderWidth: 1, padding: 10, cornerRadius: 6, titleFont: { size: 11, weight: '600', family: "'JetBrains Mono', monospace" }, bodyFont: { size: 11, family: "'JetBrains Mono', monospace" }, callbacks: { label: c => `G(${c.label}): ${Number(c.raw).toFixed(4)}` } }
            },
            scales: {
                x: { grid: { color: 'rgba(255, 255, 255, 0.03)' }, ticks: { color: '#94a3b8', font: { size: 10, family: "'Inter', sans-serif" } } },
                y: { grid: { color: 'rgba(255, 255, 255, 0.03)' }, ticks: { color: '#94a3b8', font: { size: 10, family: "'JetBrains Mono', monospace" } } }
            }
        }
    });
    window.gnChartInst = inst;
    window[canvasId + 'Inst'] = inst;
}

function createMonteCarloChart(canvasId, labels, percentiles, initialCapital) {
    const el = document.getElementById(canvasId);
    if (!el) return;
    const ctx = el.getContext('2d');
    if (window[canvasId + 'Inst']) {
        try { window[canvasId + 'Inst'].destroy(); } catch (e) {}
        window[canvasId + 'Inst'] = null;
    }
    const clean = arr => (arr || []).map(v => v <= 0.01 ? 0.01 : v);
    const p95_clean = clean(percentiles?.p95);
    const p75_clean = clean(percentiles?.p75);
    const p50_clean = clean(percentiles?.p50);
    const p25_clean = clean(percentiles?.p25);
    const p5_clean = clean(percentiles?.p5);
    const allValues = [...p95_clean, ...p75_clean, ...p50_clean, ...p25_clean, ...p5_clean];
    const maxVal = allValues.length > 0 ? Math.max(...allValues) : 1000;
    const minVal = allValues.length > 0 ? Math.min(...allValues) : 1;
    const useLog = (maxVal / (minVal || 1)) > 50 && minVal > 0.01;
    const datasets = [
        { label: 'P95 (Top 5%)', data: p95_clean, borderColor: 'rgba(16, 185, 129, 0.85)', borderDash: [5, 5], borderWidth: 1.5, fill: '+1', backgroundColor: 'rgba(16, 185, 129, 0.05)', pointRadius: 0 },
        { label: 'P75 (Cuartil Superior)', data: p75_clean, borderColor: 'rgba(16, 185, 129, 0.45)', borderWidth: 1.5, fill: '+1', backgroundColor: 'rgba(16, 185, 129, 0.08)', pointRadius: 0 },
        { label: 'Mediana (P50)', data: p50_clean, borderColor: '#f59e0b', borderWidth: 2.5, fill: false, pointRadius: 0 },
        { label: 'P25 (Cuartil Inferior)', data: p25_clean, borderColor: 'rgba(225, 29, 72, 0.45)', borderWidth: 1.5, fill: '+1', backgroundColor: 'rgba(225, 29, 72, 0.05)', pointRadius: 0 },
        { label: 'P5 (Riesgo Cola 5%)', data: p5_clean, borderColor: 'rgba(225, 29, 72, 0.85)', borderDash: [5, 5], borderWidth: 1.5, fill: false, pointRadius: 0 }
    ];
    if (initialCapital !== undefined && initialCapital !== null) {
        datasets.push({ label: 'Capital Inicial', data: Array(labels.length).fill(initialCapital), borderColor: 'rgba(255, 255, 255, 0.35)', borderDash: [6, 6], borderWidth: 1, fill: false, pointRadius: 0 });
    }
    const inst = new Chart(ctx, {
        type: 'line',
        data: { labels: labels, datasets: datasets },
        options: {
            responsive: true, maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            scales: {
                x: { grid: { color: 'rgba(255, 255, 255, 0.03)' }, ticks: { color: '#94a3b8', font: { size: 10, family: "'Inter', sans-serif" } } },
                y: {
                    type: useLog ? 'logarithmic' : 'linear', grid: { color: 'rgba(255, 255, 255, 0.03)' },
                    ticks: { color: '#94a3b8', font: { size: 10, family: "'JetBrains Mono', monospace" }, callback: (v) => formatYAxisTick(v, useLog) }
                }
            },
            plugins: {
                legend: { display: true, position: 'top', labels: { color: '#94a3b8', font: { size: 10, family: "'Inter', sans-serif" }, boxWidth: 12, padding: 10 } },
                tooltip: {
                    backgroundColor: 'rgba(19, 29, 49, 0.96)', titleColor: '#f8fafc', bodyColor: '#94a3b8', borderColor: 'rgba(245, 158, 11, 0.25)', borderWidth: 1, padding: 10, cornerRadius: 6,
                    titleFont: { size: 11, weight: '600', family: "'JetBrains Mono', monospace" }, bodyFont: { size: 11, family: "'JetBrains Mono', monospace" },
                    callbacks: { label: c => `${c.dataset.label}: $${Number(c.raw).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` }
                }
            }
        }
    });
    window[canvasId + 'Inst'] = inst;
    if (canvasId === 'mc-chart') window.mcChartInst = inst;
}

function createCorrelationHeatmap(canvasId, matrix, labels) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const parent = canvas.parentElement;
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    canvas._lastMatrix = matrix;
    canvas._lastLabels = labels;
    const width = parent ? parent.clientWidth : (canvas.clientWidth || 400);
    const height = parent ? parent.clientHeight : (canvas.clientHeight || 280);
    canvas.style.width = width + 'px';
    canvas.style.height = height + 'px';
    canvas.width = (width || 400) * dpr;
    canvas.height = (height || 280) * dpr;
    ctx.scale(dpr, dpr);
    const w = width || 400, h = height || 280;
    ctx.clearRect(0, 0, w, h);
    if (!matrix || matrix.length === 0 || !labels || labels.length === 0) {
        ctx.fillStyle = '#94a3b8';
        ctx.font = '13px "Inter", sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('Sin datos de correlación', w / 2, h / 2);
        return;
    }
    const n = Math.min(matrix.length, labels.length);
    const leftMargin = 70, topMargin = 15, rightMargin = 15, bottomMargin = 35;
    const cellW = Math.max(100, w - leftMargin - rightMargin) / n;
    const cellH = Math.max(100, h - topMargin - bottomMargin) / n;
    for (let i = 0; i < n; i++) {
        for (let j = 0; j < n; j++) {
            const val = (matrix[i] && matrix[i][j] !== undefined) ? matrix[i][j] : null;
            let colorStr = 'rgba(19, 29, 49, 0.95)';
            if (val !== null && val !== undefined && !isNaN(val)) {
                const intensity = Math.pow(Math.abs(val), 1.2);
                if (val >= 0) {
                    const r = Math.round(19 + intensity * (225 - 19));
                    const g = Math.round(29 + intensity * (29 - 29));
                    const b = Math.round(49 + intensity * (72 - 49));
                    colorStr = `rgb(${r}, ${g}, ${b})`;
                } else {
                    const r = Math.round(19 + intensity * (6 - 19));
                    const g = Math.round(29 + intensity * (182 - 29));
                    const b = Math.round(49 + intensity * (212 - 49));
                    colorStr = `rgb(${r}, ${g}, ${b})`;
                }
            }
            ctx.fillStyle = colorStr;
            const cx = leftMargin + j * cellW, cy = topMargin + i * cellH, cw = cellW - 1.5, ch = cellH - 1.5;
            if (typeof ctx.roundRect === 'function') {
                ctx.beginPath();
                ctx.roundRect(cx, cy, cw, ch, 3);
                ctx.fill();
            } else {
                ctx.fillRect(cx, cy, cw, ch);
            }
            if (cellW > 18 && cellH > 14 && val !== null && val !== undefined && !isNaN(val)) {
                ctx.fillStyle = Math.abs(val) > 0.35 ? '#ffffff' : '#cbd5e1';
                ctx.font = `bold ${Math.min(13, Math.max(10, Math.floor(cellH * 0.48)))}px "JetBrains Mono", monospace`;
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillText(val.toFixed(2), cx + cellW / 2, cy + cellH / 2);
            }
        }
    }
    ctx.fillStyle = '#cbd5e1';
    ctx.font = `bold ${Math.min(13, Math.max(10, Math.floor(cellH * 0.46)))}px "Inter", sans-serif`;
    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';
    for (let i = 0; i < n; i++) {
        ctx.fillText(labels[i].replace('USDT', '').replace('=X', ''), leftMargin - 8, topMargin + i * cellH + cellH / 2);
    }
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    for (let j = 0; j < n; j++) {
        ctx.fillText(labels[j].replace('USDT', '').replace('=X', ''), leftMargin + j * cellW + cellW / 2, h - bottomMargin + 8);
    }
}

function renderDiagnosticsCharts(statsData) {
    if (!statsData) return;
    const ac = statsData.dependency?.autocorrelation || [];
    if (ac.length > 0 && document.getElementById('autocorr-chart')) {
        createBarChart('autocorr-chart', ac.map((_, i) => `Lag ${i + 1}`), ac, 'Autocorrelación', ac.map(v => v >= 0 ? '#a855f7' : '#e11d48'));
    }
    const sd = statsData.streaks?.streak_distribution || {};
    if (Object.keys(sd).length > 0 && document.getElementById('streaks-chart')) {
        const sorted = Object.keys(sd).map(Number).sort((a, b) => a - b);
        createBarChart('streaks-chart', sorted.map(String), sorted.map(k => sd[k]), 'Frecuencia de Rachas', '#f59e0b');
    }
    const bh = statsData.temporal?.by_hour || {};
    if (Object.keys(bh).length > 0 && document.getElementById('hourly-chart')) {
        const hours = Object.keys(bh).map(Number).sort((a, b) => a - b);
        const values = hours.map(h => bh[h]);
        const colors = values.map(wr => (wr > 1 ? wr : wr * 100) >= 58.8 ? '#10b981' : ((wr > 1 ? wr : wr * 100) >= 50.0 ? '#06b6d4' : '#e11d48'));
        createBarChart('hourly-chart', hours.map(h => h + 'h'), values, 'Win Rate por Hora', colors);
    }
    const ms = statsData.market_state || {};
    if (Object.values(ms).some(v => v > 0) && document.getElementById('market-state-chart')) {
        createBarChart('market-state-chart', ['Alta Vol', 'Baja Vol', 'Tendencia', 'Rango'], [ms.high_vol_wr || 0, ms.low_vol_wr || 0, ms.trending_wr || 0, ms.ranging_wr || 0], 'Win Rate por Régimen', ['#f59e0b', '#06b6d4', '#10b981', '#a855f7']);
    }
}

// Global window export aliases
window.createCandlestickChart = createCandlestickChart;
window.initLightweightChart = createCandlestickChart;
window.updateCandlestickChart = updateCandlestickChart;
window.addSignalMarkers = addSignalMarkers;
window.formatYAxisTick = formatYAxisTick;
window.createEquityCurve = createEquityCurve;
window.renderEquityCurve = createEquityCurve;
window.createBarChart = createBarChart;
window.createGrowthRateChart = createGrowthRateChart;
window.createMonteCarloChart = createMonteCarloChart;
window.renderMonteCarloCones = createMonteCarloChart;
window.createCorrelationHeatmap = createCorrelationHeatmap;
window.renderCorrelationHeatmap = createCorrelationHeatmap;
window.renderDiagnosticsCharts = renderDiagnosticsCharts;
