/**
 * static/js/modules/dual_bot.js
 * Controlador Frontend para la Terminal de Ejecución Binance (Dual-Bot Engine).
 * Soporta gráfico de velas en tiempo real, marcadores de órdenes, HUD de posiciones y curvas de equidad.
 */

import {
    populateCampaignStrategies,
    updateActivePositionHUD,
    clearActivePositionHUD,
    updateFloatingPnL,
    initDualEquityChart,
    renderDualEquityChart,
    updateDualBotUI
} from './dual_bot/dual_bot_ui.js';

class DualBotController {
    constructor() {
        this.status = null;
        this.equityChart = null;
        this.lwChart = null;
        this.candleSeries = null;
        this.eventSource = null;
        this.activeChartTab = 'combined';
        this.currentPair = 'BTCUSDT';
        this.currentInterval = '1h';
        this.activeMarkers = [];
        this.priceLines = [];
        this.candlesData = [];
        this.currentOpenPosition = null;
    }

    init() {
        this.bindEvents();
        this.populateCampaignStrategies();
        this.initEquityChart();
        this.initCandleChart();
        this.fetchStatus();
        this.startSSE();
        this.startHeartbeat();
    }

    bindEvents() {
        const btnSaveApi = document.getElementById('btn-save-binance-api');
        if (btnSaveApi) btnSaveApi.addEventListener('click', () => this.saveApiCredentials());

        const btnSaveTg = document.getElementById('btn-save-telegram-config');
        if (btnSaveTg) btnSaveTg.addEventListener('click', () => this.saveTelegramConfig());
        const btnTestTg = document.getElementById('btn-test-telegram');
        if (btnTestTg) btnTestTg.addEventListener('click', () => this.testTelegram());

        const btnPanic = document.getElementById('btn-panic-close-all');
        if (btnPanic) btnPanic.addEventListener('click', () => this.panicClose());

        const btnB1Run = document.getElementById('btn-b1-run');
        const btnB1Pause = document.getElementById('btn-b1-pause');
        const btnB1Stop = document.getElementById('btn-b1-stop');
        const btnB1Reset = document.getElementById('btn-b1-reset');
        if (btnB1Run) btnB1Run.addEventListener('click', () => this.toggleBot('bot_1', 'RUNNING'));
        if (btnB1Pause) btnB1Pause.addEventListener('click', () => this.toggleBot('bot_1', 'PAUSED'));
        if (btnB1Stop) btnB1Stop.addEventListener('click', () => this.toggleBot('bot_1', 'STOPPED'));
        if (btnB1Reset) btnB1Reset.addEventListener('click', () => this.resetBot1Streak());

        const btnB2Run = document.getElementById('btn-b2-run');
        const btnB2Pause = document.getElementById('btn-b2-pause');
        const btnB2Stop = document.getElementById('btn-b2-stop');
        if (btnB2Run) btnB2Run.addEventListener('click', () => this.toggleBot('bot_2', 'RUNNING'));
        if (btnB2Pause) btnB2Pause.addEventListener('click', () => this.toggleBot('bot_2', 'PAUSED'));
        if (btnB2Stop) btnB2Stop.addEventListener('click', () => this.toggleBot('bot_2', 'STOPPED'));

        const stratCheckboxes = document.querySelectorAll('input[name="b1_strat"]');
        const symCheckboxes = document.querySelectorAll('input[name="b1_sym"]');
        const syncRadarConfig = () => {
            const selectedStrats = Array.from(document.querySelectorAll('input[name="b1_strat"]:checked')).map(cb => cb.value);
            const selectedSyms = Array.from(document.querySelectorAll('input[name="b1_sym"]:checked')).map(cb => cb.value);
            const countEl = document.getElementById('b1-radar-sensor-count');
            if (countEl) {
                const total = selectedStrats.length * selectedSyms.length;
                countEl.textContent = `Cobertura: ${selectedStrats.length} Estrategias × ${selectedSyms.length} Pares = ${total} Sensores Activos`;
                const freqEl = countEl.nextElementSibling;
                if (freqEl) freqEl.textContent = `Frecuencia estimada: ~${(total * 0.3).toFixed(1)} señales/día`;
            }
            if (selectedSyms.length > 0) {
                this.currentPair = selectedSyms[0].replace('/', '');
                const symBadge = document.getElementById('dual-chart-symbol-badge');
                if (symBadge) symBadge.textContent = this.currentPair;
                this.loadCandles();
            }
            this.updateConfig('bot_1', { strategies: selectedStrats, symbols: selectedSyms });
        };

        stratCheckboxes.forEach(cb => cb.addEventListener('change', syncRadarConfig));
        symCheckboxes.forEach(cb => cb.addEventListener('change', syncRadarConfig));

        const btnAllStrats = document.getElementById('btn-select-all-strats');
        const btnTop3Strats = document.getElementById('btn-select-top3-strats');
        if (btnAllStrats) btnAllStrats.addEventListener('click', () => { stratCheckboxes.forEach(cb => cb.checked = true); syncRadarConfig(); });
        if (btnTop3Strats) btnTop3Strats.addEventListener('click', () => {
            const top3 = ['daily_confluence', 'climax_reversal', 'rsi_extremes'];
            stratCheckboxes.forEach(cb => cb.checked = top3.includes(cb.value));
            syncRadarConfig();
        });

        const selB1Mode = document.getElementById('b1-mode-select');
        const inpB1Bullet = document.getElementById('b1-bullet-input');
        if (selB1Mode) selB1Mode.addEventListener('change', e => this.updateConfig('bot_1', { mode: e.target.value }));
        if (inpB1Bullet) inpB1Bullet.addEventListener('change', e => {
            const val = parseFloat(e.target.value) || 5.0;
            this.updateConfig('bot_1', { daily_bullet_usd: val, current_bullet_usd: val });
        });

        const selB2Strat = document.getElementById('b2-strategy-select');
        const inpB2Risk = document.getElementById('b2-risk-input');
        if (selB2Strat) selB2Strat.addEventListener('change', e => this.updateConfig('bot_2', { strategy: e.target.value }));
        if (inpB2Risk) inpB2Risk.addEventListener('change', e => this.updateConfig('bot_2', { risk_per_trade_pct: parseFloat(e.target.value) || 1.5 }));

        const selInterval = document.getElementById('dual-candle-interval');
        if (selInterval) selInterval.addEventListener('change', e => { this.currentInterval = e.target.value; this.loadCandles(); });

        document.querySelectorAll('.dual-chart-tab').forEach(tab => {
            tab.addEventListener('click', e => {
                document.querySelectorAll('.dual-chart-tab').forEach(t => t.classList.remove('active'));
                e.target.classList.add('active');
                this.activeChartTab = e.target.dataset.chart;
                this.renderEquityChart();
            });
        });

        const btnSimB1Win = document.getElementById('btn-sim-b1-win');
        const btnSimB1Loss = document.getElementById('btn-sim-b1-loss');
        const btnSimB2Win = document.getElementById('btn-sim-b2-win');
        const btnSimB2Loss = document.getElementById('btn-sim-b2-loss');
        if (btnSimB1Win) btnSimB1Win.addEventListener('click', () => this.simulateTrade('bot_1', true, 12.50));
        if (btnSimB1Loss) btnSimB1Loss.addEventListener('click', () => this.simulateTrade('bot_1', false, 0.0));
        if (btnSimB2Win) btnSimB2Win.addEventListener('click', () => this.simulateTrade('bot_2', true, 25.00));
        if (btnSimB2Loss) btnSimB2Loss.addEventListener('click', () => this.simulateTrade('bot_2', false, -15.00));

        const btnCloseHud = document.getElementById('btn-hud-close-position');
        if (btnCloseHud) btnCloseHud.addEventListener('click', () => this.clearActivePositionHUD());

        const botTabBtn = document.querySelector('[data-tab="bot"]');
        if (botTabBtn) botTabBtn.addEventListener('click', () => this.populateCampaignStrategies());
    }

    populateCampaignStrategies() {
        populateCampaignStrategies(document.getElementById('b2-strategy-select'));
    }

    initCandleChart() {
        const container = document.getElementById('dual-bot-candles-container');
        if (!container || typeof LightweightCharts === 'undefined') return;
        const chartObj = createCandlestickChart('dual-bot-candles-container');
        if (chartObj) {
            this.lwChart = chartObj.chart;
            this.candleSeries = chartObj.candleSeries;
            new ResizeObserver(entries => {
                if (entries.length === 0) return;
                const r = entries[0].contentRect;
                if (this.lwChart && r.width > 0 && r.height > 0) {
                    this.lwChart.applyOptions({ height: r.height, width: r.width });
                }
            }).observe(container);
            this.loadCandles();
        }
    }

    async loadCandles() {
        try {
            const pair = this.currentPair.replace('/', '').toUpperCase();
            const res = await fetch(`/api/data/candles?pair=${pair}&interval=${this.currentInterval || '1h'}&limit=200`);
            if (res.ok) {
                const data = await res.json();
                if (data.candles && this.candleSeries) {
                    this.candlesData = data.candles;
                    this.candleSeries.setData(data.candles);
                    this.lwChart.timeScale().fitContent();
                    this.renderMarkers();
                }
            }
        } catch (e) {
            console.warn("Error cargando velas:", e);
        }
    }

    renderMarkers() {
        if (!this.candleSeries) return;
        this.candleSeries.setMarkers(this.activeMarkers);
    }

    addOrderMarker(side, price, sizeUsd, text) {
        if (!this.candlesData || this.candlesData.length === 0) return;
        const lastCandle = this.candlesData[this.candlesData.length - 1];
        const time = lastCandle ? lastCandle.time : Math.floor(Date.now() / 1000);
        this.activeMarkers.push({
            time: time, position: side === 'BUY' ? 'belowBar' : 'aboveBar',
            color: side === 'BUY' ? '#10b981' : '#e11d48',
            shape: side === 'BUY' ? 'arrowUp' : 'arrowDown',
            text: `${side === 'BUY' ? '🟢 LONG' : '🔴 SHORT'} $${sizeUsd.toFixed(2)} (${text})`
        });
        if (this.activeMarkers.length > 20) this.activeMarkers.shift();
        this.renderMarkers();
        this.updateActivePositionHUD(side, price, sizeUsd);
    }

    updateActivePositionHUD(side, entryPrice, sizeUsd) {
        this.currentOpenPosition = updateActivePositionHUD(side, entryPrice, sizeUsd, this.candleSeries, this.priceLines);
    }

    updateFloatingPnL(currentPrice) {
        updateFloatingPnL(currentPrice, this.currentOpenPosition);
    }

    clearPriceLines() {
        if (this.candleSeries && this.priceLines) {
            this.priceLines.forEach(pl => { try { this.candleSeries.removePriceLine(pl); } catch (e) {} });
            this.priceLines = [];
        }
    }

    clearActivePositionHUD() {
        this.currentOpenPosition = null;
        clearActivePositionHUD(this.candleSeries, this.priceLines);
    }

    async fetchStatus() {
        try {
            const res = await fetch('/api/execution/status');
            if (res.ok) {
                this.status = await res.json();
                this.updateUI();
            }
        } catch (e) {
            console.error("Error al obtener estado de bots:", e);
        }
    }

    startSSE() {
        try {
            if (this.eventSource) this.eventSource.close();
            this.eventSource = new EventSource('/api/execution/stream');
            this.eventSource.onmessage = event => {
                try {
                    this.status = JSON.parse(event.data);
                    this.updateUI();
                } catch (err) { console.error("Error parsing SSE:", err); }
            };
        } catch (e) {
            console.warn("SSE no disponible, usando polling:", e);
            setInterval(() => this.fetchStatus(), 3000);
        }
    }

    startHeartbeat() {
        if (this.heartbeatInterval) clearInterval(this.heartbeatInterval);
        this.heartbeatInterval = setInterval(async () => {
            try {
                const res = await fetch('/api/execution/ping');
                if (res.ok) {
                    const data = await res.json();
                    const connBadge = document.getElementById('binance-conn-status');
                    if (connBadge) {
                        if (data.connected) {
                            connBadge.className = 'badge-live-connected'; connBadge.innerHTML = `● Binance Futuros Conectado | Latencia: ${data.latency_ms} ms`;
                        } else if (data.mock_mode) {
                            connBadge.className = 'badge-live-mock'; connBadge.innerHTML = `● Sandbox Seguro Activo | Latencia: ${data.latency_ms} ms`;
                        } else {
                            connBadge.className = 'badge-live-disconnected'; connBadge.innerHTML = `⚠️ Error de Conexión: ${data.error || 'Desconectado'}`;
                        }
                    }
                }
            } catch (e) {
                const connBadge = document.getElementById('binance-conn-status');
                if (connBadge) { connBadge.className = 'badge-live-disconnected'; connBadge.innerHTML = `⚠️ Error de Red Local`; }
            }
        }, 3000);
    }

    async saveApiCredentials() {
        const apiKey = document.getElementById('binance-api-key')?.value?.trim();
        const apiSecret = document.getElementById('binance-api-secret')?.value?.trim();
        const isTestnet = document.getElementById('binance-testnet-toggle')?.checked ?? true;
        if (!apiKey || !apiSecret) { alert("Por favor ingresa tanto la API Key como el API Secret."); return; }
        const btn = document.getElementById('btn-save-binance-api');
        if (btn) btn.textContent = "Conectando...";
        try {
            const res = await fetch('/api/execution/config', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ api_key: apiKey, api_secret: apiSecret, testnet: isTestnet })
            });
            const data = await res.json();
            if (data.success) { alert(`¡Conexión Exitosa con Binance! Balance USDT: $${(data.usdt_balance || 0).toFixed(2)}`); }
            else { alert(`Error al conectar con Binance: ${data.error}`); }
            this.fetchStatus();
        } catch (e) { alert(`Error de red: ${e.message}`); }
        finally { if (btn) btn.textContent = "🔒 Guardar y Conectar API"; }
    }

    async saveTelegramConfig() {
        const token = document.getElementById('telegram-bot-token')?.value?.trim();
        const chatId = document.getElementById('telegram-chat-id')?.value?.trim();
        if (!token || !chatId) { alert("Por favor ingresa tanto el Token del Bot como tu Chat ID de Telegram."); return; }
        const btn = document.getElementById('btn-save-telegram-config');
        if (btn) btn.textContent = "Conectando...";
        try {
            const res = await fetch('/api/execution/telegram/config', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ token: token, chat_ids: [chatId] })
            });
            const data = await res.json();
            if (data.success) { alert("¡Telegram Bot Vinculado con Éxito! Revisa tu celular."); }
            else { alert(`Error al vincular Telegram: ${data.error}`); }
            this.fetchStatus();
        } catch (e) { alert(`Error de red con Telegram: ${e.message}`); }
        finally { if (btn) btn.textContent = "📲 Conectar Telegram"; }
    }

    async testTelegram() {
        try {
            const res = await fetch('/api/execution/telegram/test', { method: 'POST' });
            const data = await res.json();
            if (data.success) { alert("¡Mensaje de prueba enviado a tu Telegram!"); }
            else { alert(data.error || "No se pudo enviar el mensaje."); }
        } catch (e) { alert(`Error enviando prueba: ${e.message}`); }
    }

    async toggleBot(botId, state) {
        try {
            const res = await fetch('/api/execution/toggle-bot', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ bot_id: botId, state })
            });
            const data = await res.json();
            if (!data.success) alert(data.error || "No se pudo cambiar el estado.");
            this.fetchStatus();
        } catch (e) { console.error("Error toggleBot:", e); }
    }

    async resetBot1Streak() {
        if (!confirm("¿Deseas resetear la racha actual del Bot 1 y transferir ganancias a la base?")) return;
        try {
            await fetch('/api/execution/bot1-reset-streak', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ deposit_to_base: true })
            });
            this.clearActivePositionHUD();
            this.fetchStatus();
        } catch (e) { console.error("Error resetBot1Streak:", e); }
    }

    async updateConfig(botId, updates) {
        try {
            await fetch('/api/execution/update-config', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ bot_id: botId, updates })
            });
            this.fetchStatus();
        } catch (e) { console.error("Error updateConfig:", e); }
    }

    async panicClose() {
        if (!confirm("⚠️ ¿ESTÁS SEGURO? Esto apagará ambos bots y cerrará todas las posiciones a mercado.")) return;
        try {
            await fetch('/api/execution/panic-close', { method: 'POST' });
            this.clearActivePositionHUD();
            alert("Protocolo de Pánico ejecutado. Bots apagados y posiciones cerradas.");
            this.fetchStatus();
        } catch (e) { console.error("Error panicClose:", e); }
    }

    async simulateTrade(botId, isWin, pnl) {
        try {
            const lastCandle = (this.candlesData && this.candlesData.length > 0) ? this.candlesData[this.candlesData.length - 1] : { close: 64250.0 };
            const price = lastCandle.close || 64250.0;
            const size = (botId === 'bot_1' && this.status) ? (this.status.bot1.current_bullet_usd || 5.0) : 15.0;
            await fetch('/api/execution/simulate-trade', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ bot_id: botId, is_win: isWin, pnl, symbol: 'BTC/USDT' })
            });
            if (isWin) {
                this.addOrderMarker('BUY', price, size, `WIN +$${pnl.toFixed(2)}`);
            } else {
                this.addOrderMarker('BUY', price, size, `LOSS -$${size.toFixed(2)}`);
                setTimeout(() => this.clearActivePositionHUD(), 2000);
            }
            this.fetchStatus();
        } catch (e) { console.error("Error simulateTrade:", e); }
    }

    updateUI() {
        if (!this.status) return;
        updateDualBotUI(this.status);
        this.renderEquityChart();
    }

    initEquityChart() {
        this.equityChart = initDualEquityChart('dual-bot-equity-canvas');
    }

    renderEquityChart() {
        renderDualEquityChart(this.equityChart, this.status, this.activeChartTab);
    }
}

// Instancia global
window.dualBotController = new DualBotController();
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => window.dualBotController.init());
} else {
    window.dualBotController.init();
}
