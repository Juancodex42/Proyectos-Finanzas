/**
 * Milestone 3 Charts & Micro-Interactions Adversarial Stress Test Suite (Node.js)
 * Exhaustively tests edge cases, malformed inputs, numerical boundaries, and memory cleanup.
 */

const fs = require('fs');
const path = require('path');
const assert = require('assert');

// 1. Setup Mock DOM & Canvas Environment
class MockContext2D {
    constructor(canvas) {
        this.canvas = canvas;
        this.fillStyle = '';
        this.font = '';
        this.textAlign = '';
        this.textBaseline = '';
        this.calls = [];
    }
    clearRect(x, y, w, h) {
        this.calls.push({ method: 'clearRect', args: [x, y, w, h] });
    }
    scale(sx, sy) {
        this.calls.push({ method: 'scale', args: [sx, sy] });
    }
    beginPath() {
        this.calls.push({ method: 'beginPath', args: [] });
    }
    roundRect(x, y, w, h, r) {
        this.calls.push({ method: 'roundRect', args: [x, y, w, h, r] });
    }
    fillRect(x, y, w, h) {
        this.calls.push({ method: 'fillRect', args: [x, y, w, h] });
    }
    fill() {
        this.calls.push({ method: 'fill', args: [] });
    }
    fillText(text, x, y) {
        this.calls.push({ method: 'fillText', args: [text, x, y] });
    }
    createLinearGradient(x0, y0, x1, y1) {
        this.calls.push({ method: 'createLinearGradient', args: [x0, y0, x1, y1] });
        return {
            addColorStop: (offset, color) => {
                this.calls.push({ method: 'addColorStop', args: [offset, color] });
            }
        };
    }
}

class MockElement {
    constructor(id) {
        this.id = id;
        this.style = {};
        this.clientWidth = 600;
        this.clientHeight = 300;
        this.parentElement = { clientWidth: 600, clientHeight: 300 };
        this._ctx = new MockContext2D(this);
    }
    getContext(type) {
        return this._ctx;
    }
}

const elements = {};
function getOrCreateElement(id) {
    if (!elements[id]) {
        elements[id] = new MockElement(id);
    }
    return elements[id];
}

const mockDocument = {
    getElementById: (id) => {
        if (id === 'non-existent') return null;
        return getOrCreateElement(id);
    }
};

const mockWindow = {
    devicePixelRatio: 2.0,
    document: mockDocument
};

global.window = mockWindow;
global.document = mockDocument;

// Mock Chart.js
class MockChart {
    constructor(ctx, config) {
        this.ctx = ctx;
        this.config = config;
        this.chartArea = { top: 10, bottom: 290, left: 10, right: 590 };
        MockChart.instances.push(this);
    }
    destroy() {
        this.destroyed = true;
    }
}
MockChart.instances = [];
MockChart.defaults = {
    color: '#94a3b8',
    font: { family: "'Inter', sans-serif" },
    plugins: {
        tooltip: {}
    }
};
global.Chart = MockChart;

// Mock LightweightCharts
const mockLightweightCharts = {
    CrosshairMode: { Normal: 0, Magnet: 1 },
    createChart: (container, options) => {
        return {
            container,
            options,
            addCandlestickSeries: (seriesOpts) => {
                return {
                    seriesOpts,
                    markers: [],
                    candles: [],
                    setMarkers: function(m) { this.markers = m; },
                    update: function(c) {
                        if (c && (isNaN(c.open) || c.time === undefined)) {
                            throw new Error('Invalid candle data');
                        }
                        this.candles.push(c);
                    }
                };
            }
        };
    }
};
global.LightweightCharts = mockLightweightCharts;

// Mock helper functions used in app.js
global.formatPrice = (p) => Number(p).toFixed(5);

// Load charts.js and app.js into global scope
const chartsCode = fs.readFileSync(path.join(__dirname, '..', 'static', 'js', 'charts.js'), 'utf-8');
eval(chartsCode);

const appCode = fs.readFileSync(path.join(__dirname, '..', 'static', 'js', 'app.js'), 'utf-8');
// Extract buildChartMarkers from app.js safely
const buildChartMarkersMatch = appCode.match(/function buildChartMarkers\(signals\) \{[\s\S]*?\n\}/);
if (buildChartMarkersMatch) {
    eval(buildChartMarkersMatch[0]);
}

console.log('=== RUNNING ADVERSARIAL STRESS TESTS ON CHARTS ENGINE ===');

let passCount = 0;
let totalCount = 0;

function test(name, fn) {
    totalCount++;
    try {
        fn();
        console.log(`  [PASS] ${name}`);
        passCount++;
    } catch (err) {
        console.error(`  [FAIL] ${name}:`, err.message);
        throw err;
    }
}

// -------------------------------------------------------------
// Test Group 1: Candlestick Chart Edge Cases
// -------------------------------------------------------------
test('createCandlestickChart handles non-existent DOM container gracefully', () => {
    const result = createCandlestickChart('non-existent');
    assert.strictEqual(result, null);
});

test('createCandlestickChart creates valid chart and series with semantic tokens', () => {
    const result = createCandlestickChart('chart-container-1');
    assert(result !== null);
    assert(result.chart !== undefined);
    assert(result.candleSeries !== undefined);
    assert.strictEqual(result.candleSeries.seriesOpts.upColor, '#10b981');
    assert(['#e11d48', '#f43f5e'].includes(result.candleSeries.seriesOpts.downColor));
    assert.strictEqual(result.candleSeries.seriesOpts.wickUpColor, '#10b981');
    assert(['#e11d48', '#f43f5e'].includes(result.candleSeries.seriesOpts.wickDownColor));
    assert.strictEqual(result.chart.options.layout.background.color, 'transparent');
    assert.strictEqual(result.chart.options.grid.vertLines.color, 'rgba(255, 255, 255, 0.03)');
});

test('updateCandlestickChart handles null series or null candle without throwing', () => {
    assert.doesNotThrow(() => updateCandlestickChart(null, null));
    assert.doesNotThrow(() => updateCandlestickChart(null, { time: 100, open: 1, high: 2, low: 0.5, close: 1.5 }));
    const { candleSeries } = createCandlestickChart('chart-container-2');
    assert.doesNotThrow(() => updateCandlestickChart(candleSeries, null));
});

test('updateCandlestickChart catches internal errors on malformed candles without crashing', () => {
    const { candleSeries } = createCandlestickChart('chart-container-3');
    // Candle with missing time / NaN will trigger error inside mock series.update
    assert.doesNotThrow(() => {
        updateCandlestickChart(candleSeries, { time: undefined, open: NaN, high: 1, low: 1, close: 1 });
    });
});

// -------------------------------------------------------------
// Test Group 2: formatYAxisTick Edge Cases
// -------------------------------------------------------------
test('formatYAxisTick handles zero correctly', () => {
    assert.strictEqual(formatYAxisTick(0, false), '$0.00');
    assert.strictEqual(formatYAxisTick(0, true), '$0.00');
});

test('formatYAxisTick handles linear positive and negative formatting', () => {
    assert.strictEqual(formatYAxisTick(1500000, false), '$1.5M');
    assert.strictEqual(formatYAxisTick(2000000, false), '$2M');
    assert.strictEqual(formatYAxisTick(-1500000, false), '-$1.5M');
    assert.strictEqual(formatYAxisTick(2500, false), '$2.5k');
    assert.strictEqual(formatYAxisTick(1000, false), '$1k');
    assert.strictEqual(formatYAxisTick(-2500, false), '-$2.5k');
    assert.strictEqual(formatYAxisTick(42, false), '$42');
    assert.strictEqual(formatYAxisTick(42.75, false), '$42.75');
    assert.strictEqual(formatYAxisTick(-42.75, false), '-$42.75');
    assert.strictEqual(formatYAxisTick(0.25, false), '$0.25');
});

test('formatYAxisTick in log mode filters out non-decade intermediate ticks', () => {
    // Only exact powers of 10 should return a label in log mode
    assert.strictEqual(formatYAxisTick(1, true), '$1');
    assert.strictEqual(formatYAxisTick(10, true), '$10');
    assert.strictEqual(formatYAxisTick(100, true), '$100');
    assert.strictEqual(formatYAxisTick(1000, true), '$1k');
    assert.strictEqual(formatYAxisTick(10000, true), '$10k');
    assert.strictEqual(formatYAxisTick(100000, true), '$100k');
    assert.strictEqual(formatYAxisTick(1000000, true), '$1M');
    // Intermediate ticks return null
    assert.strictEqual(formatYAxisTick(2, true), null);
    assert.strictEqual(formatYAxisTick(5, true), null);
    assert.strictEqual(formatYAxisTick(50, true), null);
    assert.strictEqual(formatYAxisTick(500, true), null);
    assert.strictEqual(formatYAxisTick(5000, true), null);
});

// -------------------------------------------------------------
// Test Group 3: createEquityCurve Adversarial Cases
// -------------------------------------------------------------
test('createEquityCurve handles missing DOM element', () => {
    assert.doesNotThrow(() => createEquityCurve('non-existent', [100, 200]));
});

test('createEquityCurve handles empty array, null, undefined', () => {
    assert.doesNotThrow(() => createEquityCurve('equity-canvas-1', []));
    assert.doesNotThrow(() => createEquityCurve('equity-canvas-1', null));
    assert.doesNotThrow(() => createEquityCurve('equity-canvas-1', undefined));
});

test('createEquityCurve handles single data point without NaN/Inf', () => {
    createEquityCurve('equity-canvas-2', [1000]);
    const chart = window['equity-canvas-2Inst'];
    assert(chart !== undefined);
    assert.strictEqual(chart.config.options.scales.y.type, 'linear');
    assert.strictEqual(chart.config.data.datasets[0].data[0], 1000);
});

test('createEquityCurve handles negative and zero capital safely (no log of non-positive)', () => {
    // 0 capital must NOT activate log scale
    createEquityCurve('equity-canvas-3', [0, 50, 100, 5000]);
    let chart = window['equity-canvas-3Inst'];
    assert.strictEqual(chart.config.options.scales.y.type, 'linear');

    // Negative capital must NOT activate log scale
    createEquityCurve('equity-canvas-4', [-200, -50, 100, 10000]);
    chart = window['equity-canvas-4Inst'];
    assert.strictEqual(chart.config.options.scales.y.type, 'linear');
});

test('createEquityCurve activates log scale when range > 100x and minVal >= 1.0', () => {
    createEquityCurve('equity-canvas-5', [10, 100, 500, 50000]);
    const chart = window['equity-canvas-5Inst'];
    assert.strictEqual(chart.config.options.scales.y.type, 'logarithmic');
    assert.strictEqual(chart.config.options.scales.y.min, 10);
});

test('createEquityCurve handles object array with timestamps and fallback values', () => {
    const points = [
        { time: 1672531199, equity: 1000 },
        { time: 1672531259, y: 1050 },
        { equity: 1100 }, // missing time
        { foo: 'bar' } // missing equity and y -> fallback to 0
    ];
    createEquityCurve('equity-canvas-6', points);
    const chart = window['equity-canvas-6Inst'];
    assert.strictEqual(chart.config.data.datasets[0].data[0], 1000);
    assert.strictEqual(chart.config.data.datasets[0].data[1], 1050);
    assert.strictEqual(chart.config.data.datasets[0].data[2], 1100);
    assert.strictEqual(chart.config.data.datasets[0].data[3], 0);
});

test('createEquityCurve background gradient function executes safely with/without chartArea', () => {
    createEquityCurve('equity-canvas-7', [100, 200, 300]);
    const chart = window['equity-canvas-7Inst'];
    const bgFn = chart.config.data.datasets[0].backgroundColor;
    // Call with empty chartArea
    const fallbackBg = bgFn({ chart: { ctx: chart.ctx, chartArea: null } });
    assert(['rgba(6, 182, 212, 0.12)', 'rgba(56, 189, 248, 0.12)'].includes(fallbackBg));
    // Call with valid chartArea
    const gradientBg = bgFn({ chart: { ctx: chart.ctx, chartArea: { top: 0, bottom: 200 } } });
    assert(gradientBg !== null && typeof gradientBg === 'object');
});

test('createEquityCurve tooltip callbacks format numbers with currency formatting', () => {
    createEquityCurve('equity-canvas-8', [1234.567]);
    const chart = window['equity-canvas-8Inst'];
    const titleFn = chart.config.options.plugins.tooltip.callbacks.title;
    const labelFn = chart.config.options.plugins.tooltip.callbacks.label;
    
    assert.strictEqual(titleFn(null), '');
    assert.strictEqual(titleFn([]), '');
    assert.strictEqual(titleFn([{ dataIndex: 0, label: '2026-01-01' }]), 'Op. #1 (2026-01-01)');
    
    assert.strictEqual(labelFn({ raw: 1234.56 }), 'Capital Acumulado: $1,234.56');
});

// -------------------------------------------------------------
// Test Group 4: createMonteCarloChart Adversarial Cases
// -------------------------------------------------------------
test('createMonteCarloChart handles non-existent DOM container', () => {
    assert.doesNotThrow(() => createMonteCarloChart('non-existent', ['1', '2'], {}));
});

test('createMonteCarloChart handles null/undefined percentiles object', () => {
    assert.doesNotThrow(() => createMonteCarloChart('mc-canvas-1', ['1', '2'], null));
    assert.doesNotThrow(() => createMonteCarloChart('mc-canvas-1', ['1', '2'], undefined));
    assert.doesNotThrow(() => createMonteCarloChart('mc-canvas-1', ['1', '2'], {}));
});

test('createMonteCarloChart clamps zero and negative percentile values to 0.01', () => {
    const percentiles = {
        p95: [1000, 1200, 1500],
        p75: [1000, 1100, 1200],
        p50: [1000, 1000, 1000],
        p25: [1000, 900, 800],
        p5: [1000, 0, -500] // contains zero and negative
    };
    createMonteCarloChart('mc-canvas-2', ['1', '2', '3'], percentiles, 1000);
    const chart = window['mc-canvas-2Inst'];
    
    // Dataset 4 is P5
    const p5Data = chart.config.data.datasets[4].data;
    assert.strictEqual(p5Data[0], 1000);
    assert.strictEqual(p5Data[1], 0.01);
    assert.strictEqual(p5Data[2], 0.01);
});

test('createMonteCarloChart renders 5 probability cones with fills and initial capital baseline', () => {
    const percentiles = {
        p95: [100, 150],
        p75: [100, 130],
        p50: [100, 100],
        p25: [100, 80],
        p5: [100, 60]
    };
    createMonteCarloChart('mc-canvas-3', ['1', '2'], percentiles, 100);
    const chart = window['mc-canvas-3Inst'];
    
    assert.strictEqual(chart.config.data.datasets.length, 6); // 5 cones + 1 baseline
    assert.strictEqual(chart.config.data.datasets[0].label, 'P95 (Top 5%)');
    assert.strictEqual(chart.config.data.datasets[1].label, 'P75 (Cuartil Superior)');
    assert.strictEqual(chart.config.data.datasets[1].fill, '+1');
    assert.strictEqual(chart.config.data.datasets[2].label, 'Mediana (P50)');
    assert.strictEqual(chart.config.data.datasets[3].label, 'P25 (Cuartil Inferior)');
    assert.strictEqual(chart.config.data.datasets[3].fill, '+1');
    assert.strictEqual(chart.config.data.datasets[4].label, 'P5 (Riesgo Cola 5%)');
    assert.strictEqual(chart.config.data.datasets[5].label, 'Capital Inicial');
    assert.deepStrictEqual(chart.config.data.datasets[5].data, [100, 100]);
});

test('createMonteCarloChart tooltip callback formats currency', () => {
    const percentiles = { p50: [5000.75] };
    createMonteCarloChart('mc-canvas-4', ['1'], percentiles, 5000);
    const chart = window['mc-canvas-4Inst'];
    const labelFn = chart.config.options.plugins.tooltip.callbacks.label;
    const res = labelFn({ dataset: { label: 'Mediana (P50)' }, raw: 5000.75 });
    assert.strictEqual(res, 'Mediana (P50): $5,000.75');
});

// -------------------------------------------------------------
// Test Group 5: createCorrelationHeatmap Adversarial Cases
// -------------------------------------------------------------
test('createCorrelationHeatmap handles missing DOM canvas', () => {
    assert.doesNotThrow(() => createCorrelationHeatmap('non-existent', [[1]], ['A']));
});

test('createCorrelationHeatmap handles empty or null matrix/labels gracefully', () => {
    createCorrelationHeatmap('corr-canvas-1', [], []);
    const canvas = getOrCreateElement('corr-canvas-1');
    const ctx = canvas.getContext('2d');
    const fillTextCall = ctx.calls.find(c => c.method === 'fillText' && c.args[0] === 'Sin datos de correlación');
    assert(fillTextCall !== undefined, 'Must display "Sin datos de correlación"');

    createCorrelationHeatmap('corr-canvas-2', null, null);
    const canvas2 = getOrCreateElement('corr-canvas-2');
    const ctx2 = canvas2.getContext('2d');
    const fillTextCall2 = ctx2.calls.find(c => c.method === 'fillText' && c.args[0] === 'Sin datos de correlación');
    assert(fillTextCall2 !== undefined, 'Must display "Sin datos de correlación" when null');
});

test('createCorrelationHeatmap handles 1x1 matrix without division by zero', () => {
    assert.doesNotThrow(() => {
        createCorrelationHeatmap('corr-canvas-3', [[1.0]], ['BTCUSDT']);
    });
    const canvas = getOrCreateElement('corr-canvas-3');
    assert(canvas.style.width !== undefined);
    assert(canvas.style.height !== undefined);
});

test('createCorrelationHeatmap handles NaN, null, and undefined values in matrix', () => {
    const jaggedMatrix = [
        [1.0, NaN, null],
        [undefined, 1.0, -0.85],
        [0.45] // missing elements in row
    ];
    const labels = ['EURUSD=X', 'GBPUSD=X', 'AUDUSD=X'];
    
    assert.doesNotThrow(() => {
        createCorrelationHeatmap('corr-canvas-4', jaggedMatrix, labels);
    });
});

test('createCorrelationHeatmap cleans USDT and =X suffixes from labels', () => {
    const matrix = [
        [1.0, 0.5],
        [0.5, 1.0]
    ];
    const labels = ['BTCUSDT', 'EURUSD=X'];
    createCorrelationHeatmap('corr-canvas-5', matrix, labels);
    const canvas = getOrCreateElement('corr-canvas-5');
    const ctx = canvas.getContext('2d');
    const labelCalls = ctx.calls.filter(c => c.method === 'fillText');
    const btcFound = labelCalls.some(c => c.args[0] === 'BTC');
    const eurusdFound = labelCalls.some(c => c.args[0] === 'EURUSD');
    assert(btcFound, 'BTC label must be cleaned of USDT suffix');
    assert(eurusdFound, 'EURUSD label must be cleaned of =X suffix');
});

// -------------------------------------------------------------
// Test Group 6: buildChartMarkers Adversarial Cases
// -------------------------------------------------------------
test('buildChartMarkers handles null, undefined, and empty array', () => {
    assert.deepStrictEqual(buildChartMarkers(null), []);
    assert.deepStrictEqual(buildChartMarkers(undefined), []);
    assert.deepStrictEqual(buildChartMarkers([]), []);
});

test('buildChartMarkers builds CALL, PUT, EXIT WIN and EXIT LOSS markers correctly', () => {
    const signals = [
        { time: 100, direction: 'CALL', entry_price: 1.08500 },
        { time: 200, direction: 'PUT', entry_price: 1.08600 },
        { time: 300, direction: 'EXIT', result: 'WIN', trade_direction: 'CALL', exit_price: 1.08700, pnl: 85.0 },
        { time: 400, direction: 'EXIT', result: 'LOSS', trade_direction: 'CALL', exit_price: 1.08400, pnl: -100.0 },
        { time: 500, direction: 'EXIT', result: 'WIN', trade_direction: 'PUT', exit_price: 1.08300, pnl: 85.0 },
        { time: 600, direction: 'EXIT', result: 'LOSS', trade_direction: 'PUT', exit_price: 1.08800, pnl: -100.0 }
    ];

    const markers = buildChartMarkers(signals);
    assert.strictEqual(markers.length, 6);

    // CALL
    assert.strictEqual(markers[0].shape, 'arrowUp');
    assert.strictEqual(markers[0].position, 'belowBar');
    assert.strictEqual(markers[0].color, '#10b981');
    assert.strictEqual(markers[0].text, 'CALL @ 1.08500');

    // PUT
    assert.strictEqual(markers[1].shape, 'arrowDown');
    assert.strictEqual(markers[1].position, 'aboveBar');
    assert(['#e11d48', '#f43f5e'].includes(markers[1].color));
    assert.strictEqual(markers[1].text, 'PUT @ 1.08600');

    // EXIT WIN CALL -> aboveBar
    assert.strictEqual(markers[2].shape, 'circle');
    assert.strictEqual(markers[2].position, 'aboveBar');
    assert.strictEqual(markers[2].color, '#10b981');
    assert.strictEqual(markers[2].text, 'WIN @ 1.08700 (+85.00$)');

    // EXIT LOSS CALL -> belowBar
    assert.strictEqual(markers[3].shape, 'circle');
    assert.strictEqual(markers[3].position, 'belowBar');
    assert(['#e11d48', '#f43f5e'].includes(markers[3].color));
    assert.strictEqual(markers[3].text, 'LOSS @ 1.08400 (-100.00$)');

    // EXIT WIN PUT -> belowBar
    assert.strictEqual(markers[4].shape, 'circle');
    assert.strictEqual(markers[4].position, 'belowBar');
    assert.strictEqual(markers[4].color, '#10b981');
    assert.strictEqual(markers[4].text, 'WIN @ 1.08300 (+85.00$)');

    // EXIT LOSS PUT -> aboveBar
    assert.strictEqual(markers[5].shape, 'circle');
    assert.strictEqual(markers[5].position, 'aboveBar');
    assert(['#e11d48', '#f43f5e'].includes(markers[5].color));
    assert.strictEqual(markers[5].text, 'LOSS @ 1.08800 (-100.00$)');
});

test('buildChartMarkers deduplicates identical timestamps and handles missing prices/pnl', () => {
    const signals = [
        { time: 500, direction: 'CALL' }, // missing entry_price
        { time: 500, direction: 'CALL' }, // duplicate
        { time: 600, direction: 'EXIT', result: 'WIN' }, // missing pnl, exit_price, trade_direction
        { time: 200, direction: 'PUT' } // out of order time
    ];

    const markers = buildChartMarkers(signals);
    assert.strictEqual(markers.length, 3);
    // Verified sorting by time: 200, 500, 600
    assert.strictEqual(markers[0].time, 200);
    assert.strictEqual(markers[1].time, 500);
    assert.strictEqual(markers[1].text, 'CALL');
    assert.strictEqual(markers[2].time, 600);
    assert.strictEqual(markers[2].text, 'WIN');
});

// -------------------------------------------------------------
// Test Group 7: Diagnostic Panels Stress Cases
// -------------------------------------------------------------
test('renderDiagnosticsCharts handles null and empty statistics gracefully', () => {
    assert.doesNotThrow(() => renderDiagnosticsCharts(null));
    assert.doesNotThrow(() => renderDiagnosticsCharts({}));
    assert.doesNotThrow(() => renderDiagnosticsCharts({
        dependency: { autocorrelation: [] },
        streaks: { streak_distribution: {} },
        temporal: { by_hour: {} },
        market_state: {}
    }));
});

test('createGrowthRateChart highlights optimal_n in emerald and others in sky', () => {
    createGrowthRateChart('gn-chart-1', [1, 2, 3, 4], [0.01, 0.05, 0.03, 0.00], 2);
    const chart = window['gn-chart-1Inst'];
    assert.strictEqual(chart.config.data.datasets[0].backgroundColor[1], '#10b981');
    assert(['#06b6d4', '#38bdf8'].includes(chart.config.data.datasets[0].backgroundColor[0]));
    assert(['#06b6d4', '#38bdf8'].includes(chart.config.data.datasets[0].backgroundColor[2]));
});

console.log(`\n=== ADVERSARIAL STRESS TEST RESULTS: ${passCount}/${totalCount} PASSED (100%) ===\n`);
