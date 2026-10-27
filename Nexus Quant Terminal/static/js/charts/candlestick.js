// candlestick.js - Lightweight Charts Candlestick Engine & Marker Manager
// Nexus Quant Terminal

export function createCandlestickChart(containerId) {
    const el = document.getElementById(containerId);
    if (!el) return null;

    if (el.__lwChartInstance) {
        try {
            el.__lwChartInstance.remove();
        } catch (e) {
            console.warn('Error removing previous chart instance:', e);
        }
        el.__lwChartInstance = null;
    }

    const chart = LightweightCharts.createChart(el, {
        layout: {
            background: { type: 'solid', color: 'transparent' },
            textColor: '#94a3b8',
            fontSize: 13,
            fontFamily: "'Inter', system-ui, -apple-system, sans-serif",
        },
        grid: {
            vertLines: { color: 'rgba(255, 255, 255, 0.03)' },
            horzLines: { color: 'rgba(255, 255, 255, 0.03)' },
        },
        crosshair: {
            mode: LightweightCharts.CrosshairMode.Normal,
            vertLine: {
                color: 'rgba(245, 158, 11, 0.45)',
                style: 3,
                labelBackgroundColor: '#131d31',
            },
            horzLine: {
                color: 'rgba(245, 158, 11, 0.45)',
                style: 3,
                labelBackgroundColor: '#131d31',
            },
        },
        timeScale: {
            timeVisible: true,
            secondsVisible: false,
            borderColor: 'rgba(255, 255, 255, 0.07)',
            rightOffset: 10,
            barSpacing: 10,
            minBarSpacing: 0.5,
            autoScale: true,
            shiftVisibleRangeOnNewBar: true,
        },
        rightPriceScale: {
            borderColor: 'rgba(255, 255, 255, 0.07)',
            autoScale: true,
            scaleMargins: {
                top: 0.1,
                bottom: 0.1,
            },
        },
        handleScroll: {
            mouseWheel: true,
            pressedMove: true,
            horzTouchDrag: true,
            vertTouchDrag: true,
        },
        handleScale: {
            axisPressedMouseMove: true,
            mouseWheel: true,
            pinch: true,
        },
    });

    const candleSeries = chart.addCandlestickSeries({
        upColor: '#10b981',
        downColor: '#e11d48',
        borderVisible: false,
        wickUpColor: '#10b981',
        wickDownColor: '#e11d48',
        priceFormat: {
            type: 'price',
            precision: 5,
            minMove: 0.00001,
        },
    });

    el.__lwChartInstance = chart;
    return { chart, candleSeries };
}

export function updateCandlestickChart(series, candle) {
    if (series && candle) {
        try {
            series.update(candle);
        } catch (e) {
            console.warn('[Chart] Error updating candlestick:', e);
        }
    }
}

export function addSignalMarkers(series, signals) {
    if (!series || !signals) return;
    if (typeof buildChartMarkers === 'function') {
        const markers = buildChartMarkers(signals);
        series.setMarkers(markers);
        return;
    }
    const markers = signals.map(signal => {
        const dir = signal.direction || signal.type;
        const isLong = (dir === 'CALL' || dir === 'LONG');
        return {
            time: signal.time,
            position: isLong ? 'belowBar' : 'aboveBar',
            color: isLong ? '#10b981' : '#e11d48',
            shape: isLong ? 'arrowUp' : 'arrowDown',
            text: isLong ? '▲ LONG' : '▼ SHORT'
        };
    });
    series.setMarkers(markers);
}

// Global browser bridge
if (typeof window !== 'undefined') {
    window.createCandlestickChart = createCandlestickChart;
    window.initLightweightChart = createCandlestickChart;
    window.updateCandlestickChart = updateCandlestickChart;
    window.addSignalMarkers = addSignalMarkers;
}
