/**
 * smart_mode.js - Pilot / Smart Mode & Barbell Preset Engine Module
 * Handles automated multi-asset genetic optimization streaming via SSE,
 * dynamic Barbell risk presets, and strategy ranking presentation.
 * Nexus Quant Terminal
 */

import { state, setActiveEventSource, closeActiveEventSource } from './state.js';
import { generatePineScriptV5, generateAIPrompt } from './modals/export_modal.js';
import {
    updateUniverseBadges,
    renderRecommendationView,
    renderStreakLadderView,
    renderMonteCarloChartCones,
    renderMarkovMatrixTable
} from './smart_mode/monte_carlo_view.js';

const API = '/api';

export function updateInputsFromPreset(val) {
    const attemptsInput = document.getElementById('smart-attempts');
    const streakInput = document.getElementById('smart-streak-length');
    const payoutInput = document.getElementById('smart-payout');
    if (val === 'preset_33_6' || val === 'preset_33_6_n4') {
        if (attemptsInput) attemptsInput.value = 6;
        if (streakInput) streakInput.value = 3;
        if (payoutInput) payoutInput.value = 2.0;
    } else if (val === 'preset_25_8' || val === 'preset_25_8_n4') {
        if (attemptsInput) attemptsInput.value = 8;
        if (streakInput) streakInput.value = 3;
        if (payoutInput) payoutInput.value = 2.0;
    } else if (val === 'preset_200_1') {
        if (attemptsInput) attemptsInput.value = 1;
        if (streakInput) streakInput.value = 2;
        if (payoutInput) payoutInput.value = 2.0;
    } else if (val === 'preset_classic_fast') {
        if (attemptsInput) attemptsInput.value = 2;
        if (streakInput) streakInput.value = 2;
        if (payoutInput) payoutInput.value = 2.0;
    }
}

export function initSmartModePresets() {
    const presetSelect = document.getElementById('smart-preset-select');
    if (presetSelect) {
        updateInputsFromPreset(presetSelect.value);
        presetSelect.addEventListener('change', (e) => {
            updateInputsFromPreset(e.target.value);
        });
    }
}

export async function runSmartOptimization() {
    const btn = document.getElementById('btn-smart-run');
    const consoleBox = document.getElementById('smart-console-box');
    const consoleLogs = document.getElementById('smart-console-logs');
    const bar = document.getElementById('smart-progress-bar-fill');
    if (!btn) return;
    
    const originalBtnText = '⚡ Auto-Optimizar Estrategia';
    btn.innerHTML = '⚡ Optimizando...';
    btn.disabled = true;
    btn.style.opacity = '0.75';
    btn.style.cursor = 'not-allowed';
    
    const cleanup = () => {
        btn.innerHTML = originalBtnText;
        btn.disabled = false;
        btn.style.opacity = '1';
        btn.style.cursor = 'pointer';
    };
    
    if (consoleBox) {
        consoleBox.style.display = 'block';
        consoleBox.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
    if (consoleLogs) consoleLogs.innerHTML = '';
    if (bar) bar.style.width = '0%';
    const setProgress = (pct) => { if (bar) bar.style.width = `${pct}%`; };
    
    const log = (text, type = 'info') => {
        if (!consoleLogs) return;
        const time = new Date().toLocaleTimeString('es-ES', { hour12: false });
        const line = document.createElement('div');
        line.className = `console-log-line ${type}`;
        line.innerHTML = `[${time}] ${text}`;
        consoleLogs.appendChild(line);
        consoleLogs.scrollTop = consoleLogs.scrollHeight;
    };
    
    log('⚡ Inicializando procesador cuantitativo de Nexus Quant Terminal...', 'success');
    const checkedCheckboxes = document.querySelectorAll('input[name="smart-universe"]:checked');
    const universe = Array.from(checkedCheckboxes).map(cb => cb.value);
    
    if (universe.length < 3) {
        log('❌ Error: Debes seleccionar al menos 3 activos en el universo para diversificación.', 'error');
        alert('Selecciona al menos 3 activos para diversificación de correlación.');
        cleanup();
        return;
    }
    
    try {
        const base_capital = parseFloat(document.getElementById('smart-base-capital')?.value) || 1000.0;
        const profit_pct = parseFloat(document.getElementById('smart-profit-pct')?.value) || 20.0;
        const attempts = parseInt(document.getElementById('smart-attempts')?.value) || 6;
        const payout = parseFloat(document.getElementById('smart-payout')?.value) || 0.85;
        const streak_length = parseInt(document.getElementById('smart-streak-length')?.value) || 3;
        const generations = parseInt(document.getElementById('smart-generations')?.value) || 50;
        const population = parseInt(document.getElementById('smart-population')?.value) || 150;
        
        log(`Parámetros cargados: Capital $${base_capital}, Payout ${(payout * 100).toFixed(0)}%, Intentos ${attempts}, Racha N=${streak_length}`, 'info');
        log(`Configuración Genética Rust: Generaciones ${generations}, Población ${population}`, 'info');
        log(`Universo inicial: ${universe.join(', ')}`, 'info');
        
        const queryParams = new URLSearchParams({
            base_capital: base_capital, profit_pct: profit_pct, attempts: attempts, payout: payout,
            streak_length: streak_length, generations: generations, population: population, universe: JSON.stringify(universe)
        });
        
        closeActiveEventSource();
        const eventSource = new EventSource(`${API}/smart-optimize-v2-stream?${queryParams.toString()}`);
        setActiveEventSource(eventSource);
        
        eventSource.onerror = (err) => {
            console.error('Error de conexión con SSE stream:', err);
            closeActiveEventSource();
            cleanup();
            log('❌ Error de conexión streaming con el servidor.', 'error');
        };
        
        eventSource.onmessage = async (event) => {
            const item = JSON.parse(event.data);
            if (item.type === 'log') {
                log(item.message, 'info');
            } else if (item.type === 'asset_winrates') {
                if (item.message) log(item.message, 'info');
            } else if (item.type === 'progress') {
                setProgress(item.progress);
                const etaStr = item.eta ? ` | ETA: ${item.eta.toFixed(1)}s` : '';
                log(`[${item.progress.toFixed(1)}%] ${item.log}${etaStr}`, 'success');
            } else if (item.type === 'error') {
                setProgress(0);
                log(`❌ Error: ${item.message}`, 'error');
                alert('Error: ' + item.message);
                closeActiveEventSource();
                cleanup();
            } else if (item.type === 'result') {
                closeActiveEventSource();
                cleanup();
                setProgress(100);
                log('⚡ ¡Proceso de optimización multi-activo finalizado con éxito!', 'success');
                
                const data = item.data;
                const plan = data.streak_plan || {};
                const bestN = plan.best_n_for_target || 3;
                const bet_fraction = 1.0 / attempts;
                const results = plan.results_by_n || [];
                const bestPlan = results.find(r => r.n === bestN) || {};

                if (data.asset_win_rates) updateUniverseBadges(data.asset_win_rates);

                const topBox = document.getElementById('smart-top-5-box');
                const topList = document.getElementById('smart-top-5-list');
                
                const renderStrategyView = (strat) => {
                    try {
                        const stratPlan = strat.streak_plan || {};
                        const sBestN = stratPlan.best_n_for_target || 3;
                        const sResults = stratPlan.results_by_n || [];
                        const sBestPlan = sResults.find(r => r.n === sBestN) || {};
                        const needed_streaks = stratPlan.needed_streaks || sBestPlan.needed_streaks || 1;
                        const prob_dup = stratPlan.prob_duplication_pct !== undefined ? stratPlan.prob_duplication_pct : (sBestPlan.prob_duplication_pct || 0.0);
                        const base_cap = parseFloat(document.getElementById('smart-base-capital')?.value) || stratPlan.base_capital || 1000.0;
                        const target_patrimony = base_cap * 2.0;

                        const btMeta = strat.backtest_period || data.backtest_period || { period_str: '2021 - 2026', duration_years: 5.0, total_candles: 1260, period_badge: '2021 - 2026' };
                        const durYears = btMeta.duration_years || 5.0;
                        const totCandles = btMeta.total_candles || 1260;
                        const trdCount = strat.total_trades || (strat.trades ? strat.trades.length : 0);
                        const trdsPerYr = durYears > 0 ? (trdCount / durYears).toFixed(1) : (trdCount / 5.0).toFixed(1);

                        const rankingPeriodBadge = document.getElementById('smart-ranking-period-badge');
                        if (rankingPeriodBadge && btMeta.period_str) rankingPeriodBadge.innerHTML = `📅 ${btMeta.period_str}`;
                        if (strat.asset_win_rates) updateUniverseBadges(strat.asset_win_rates);

                        const pineCode = generatePineScriptV5(strat);
                        const aiPromptText = generateAIPrompt(strat);
                        const stratId = strat.id || 1;
                        const isMarkov = !!(stratPlan.markov_mode || sBestPlan.p_ww_used || stratPlan.p_ww_used);
                        const pWw = stratPlan.p_ww_used || sBestPlan.p_ww_used;
                        const modelName = isMarkov ? `Markov Dinámico${pWw ? ` (P(W|W): ${(pWw * 100).toFixed(1)}%)` : ''}` : 'Binomial';

                        renderRecommendationView(strat, stratPlan, sBestN, sBestPlan, base_cap, target_patrimony, btMeta, durYears, totCandles, trdCount, trdsPerYr, modelName, pineCode, aiPromptText, stratId, attempts);
                        renderStreakLadderView(sBestPlan, sBestN, base_cap, target_patrimony, needed_streaks, prob_dup, sBestPlan.expected_final_patrimony);

                        if (strat.equity_curve && strat.equity_curve.length > 0 && typeof createEquityCurve === 'function') {
                            createEquityCurve('smart-equity-chart-canvas', strat.equity_curve);
                        }
                        if (data.mc_paths && data.mc_paths.length > 0) {
                            renderMonteCarloChartCones(data.mc_paths, attempts);
                        }

                        const selectedAssetsList = (data.selected_assets && data.selected_assets.length > 0) ? data.selected_assets : ['GBPJPY', 'WTI', 'NASDAQ', 'XAUUSD', 'BTCUSDT', 'ETHUSDT', 'DOGEUSDT', 'ADAUSDT'];
                        const assetSelectEl = document.getElementById('smart-asset-selector');
                        if (assetSelectEl) {
                            assetSelectEl.innerHTML = selectedAssetsList.map(a => `<option value="${a}">${a} (1d)</option>`).join('');
                            assetSelectEl.value = strat.target_asset || selectedAssetsList[0];
                            const loadAssetCandles = (chosenAsset) => {
                                if (typeof smartCandleSeries !== 'undefined' && smartCandleSeries) {
                                    fetch(`${API}/data/candles?pair=${chosenAsset}&interval=1d&limit=5000`)
                                        .then(res => res.json())
                                        .then(resData => {
                                            const rawCandles = resData.candles || (Array.isArray(resData) ? resData : []);
                                            if (rawCandles.length > 0) {
                                                const cleanCandles = typeof prepareCandles === 'function' ? prepareCandles(rawCandles) : rawCandles;
                                                smartCandleSeries.setData(cleanCandles);
                                                const assetSignals = (strat.signals_by_asset && strat.signals_by_asset[chosenAsset]) || strat.signals;
                                                if (assetSignals && cleanCandles.length > 0) {
                                                    const minT = cleanCandles[0].time, maxT = cleanCandles[cleanCandles.length - 1].time;
                                                    const inRange = assetSignals.filter(s => s && s.time >= minT && s.time <= maxT);
                                                    if (typeof buildChartMarkers === 'function') smartCandleSeries.setMarkers(buildChartMarkers(inRange));
                                                }
                                                const emptyOverlay = document.getElementById('smart-tv-chart-empty');
                                                if (emptyOverlay) emptyOverlay.style.display = 'none';
                                                if (typeof smartChart !== 'undefined' && smartChart) {
                                                    const totalBars = cleanCandles.length;
                                                    smartChart.timeScale().setVisibleLogicalRange({ from: totalBars - Math.min(120, totalBars), to: totalBars + 5 });
                                                }
                                            }
                                        }).catch(err => console.error('Error cargando velas:', err));
                                }
                            };
                            assetSelectEl.onchange = e => loadAssetCandles(e.target.value);
                            loadAssetCandles(assetSelectEl.value);
                        }

                        renderMarkovMatrixTable(strat.stats?.markov?.transition_matrix || [], document.getElementById('smart-markov-explanation'), strat, attempts);
                    } catch (renderErr) {
                        console.error('Error rendering strategy view:', renderErr);
                    }
                };
                
                if (data.top_strategies && data.top_strategies.length > 0) {
                    if (topBox) topBox.style.display = 'block';
                    if (topList) {
                        let pillsHtml = '';
                        data.top_strategies.forEach((strat, index) => {
                            const rank = index + 1;
                            const wrPct = (strat.win_rate_oos * 100).toFixed(1);
                            const tradeCnt = strat.total_trades || (strat.trades ? strat.trades.length : 0);
                            const isActive = index === 0;
                            const pPlan = strat.streak_plan || {};
                            const streakProb = pPlan.prob_at_least_1_streak_pct !== undefined ? pPlan.prob_at_least_1_streak_pct.toFixed(1) : '85.0';
                            const simSummary = strat.sim_summary || {};
                            const netPnl = simSummary.net_pnl !== undefined ? simSummary.net_pnl : 0.0;
                            const pfVal = simSummary.profit_factor !== undefined ? simSummary.profit_factor : 1.0;
                            const pnlFormatted = (netPnl >= 0 ? '+' : '') + '$' + (Math.abs(netPnl) >= 1000 ? (netPnl / 1000).toFixed(1) + 'k' : netPnl.toFixed(0));
                            const pfFormatted = 'PF ' + pfVal.toFixed(2);
                            const btMeta = strat.backtest_period || data.backtest_period || { duration_years: 5.0, period_badge: '2021-2026' };
                            const opsPerYear = btMeta.duration_years > 0 ? (tradeCnt / btMeta.duration_years).toFixed(1) : (tradeCnt / 5.0).toFixed(1);
                            
                            let topDetailBadge = `<span style="font-size: 0.72rem; padding: 2px 6px; background: rgba(255,255,255,0.06); border: 1px solid var(--border-subtle); color: var(--text-secondary); border-radius: 4px; font-family: var(--font-mono); font-weight: 700;">${pfFormatted} (${pnlFormatted})</span>`;
                            let rankBorder = 'var(--border-subtle)';
                            let rankBg = isActive ? 'rgba(192, 132, 252, 0.22)' : 'rgba(255, 255, 255, 0.04)';
                            let rankBadge = `#${rank}`;
                            if (rank === 1) { rankBadge = '🥇 #1'; rankBorder = '#f59e0b'; topDetailBadge = `<span style="font-size: 0.72rem; padding: 2px 8px; background: rgba(245, 158, 11, 0.2); border: 1px solid #f59e0b; color: #f59e0b; border-radius: 4px; font-weight: 800;">🔥 TOP ALPHA (${pfFormatted} | ${pnlFormatted})</span>`; }
                            else if (rank === 2) { rankBadge = '🥈 #2'; rankBorder = '#06b6d4'; topDetailBadge = `<span style="font-size: 0.72rem; padding: 2px 8px; background: rgba(6, 182, 212, 0.2); border: 1px solid #06b6d4; color: #06b6d4; border-radius: 4px; font-weight: 800;">⚡ RENDIMIENTO (${pfFormatted} | ${pnlFormatted})</span>`; }
                            else if (rank === 3) { rankBadge = '🥉 #3'; rankBorder = '#10b981'; topDetailBadge = `<span style="font-size: 0.72rem; padding: 2px 8px; background: rgba(16, 185, 129, 0.2); border: 1px solid #10b981; color: #10b981; border-radius: 4px; font-weight: 800;">🛡️ ROBUSTA (${pfFormatted} | ${pnlFormatted})</span>`; }
                            
                            const assetLabel = strat.target_asset || strat.asset || 'MULTI';
                            const tfLabel = strat.timeframe || '1D';

                            pillsHtml += `
                                <button type="button" class="top-strat-pill ${isActive ? 'active' : ''}" data-strat-idx="${index}" style="background: ${isActive ? 'rgba(192, 132, 252, 0.22)' : rankBg}; border: 1.5px solid ${isActive ? 'var(--accent-purple)' : rankBorder}; color: ${isActive ? '#ffffff' : 'var(--text-secondary)'}; border-radius: 12px; padding: 12px 14px; cursor: pointer; text-align: left; transition: all 0.2s ease;">
                                    <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 6px;">
                                        <div style="font-weight: 800; font-size: 0.98rem; white-space: normal; line-height: 1.3; color: ${isActive ? '#ffffff' : 'var(--text-primary)'};">
                                            ${rankBadge} ${strat.name}
                                            <span style="font-size: 0.78rem; font-weight: 700; color: var(--accent-primary); margin-left: 6px; font-family: var(--font-mono);">[${assetLabel} · ${tfLabel}]</span>
                                        </div>
                                        <div style="flex-shrink: 0;">${topDetailBadge}</div>
                                    </div>
                                    <div style="display: flex; align-items: center; justify-content: space-between; gap: 6px; font-size: 0.78rem; color: var(--accent-primary); font-weight: 600; margin-bottom: 6px;">
                                        <span>${strat.badge_label || strat.type} · ${assetLabel}</span>
                                        <span style="color: var(--text-muted); font-family: var(--font-mono); font-weight: 700;">📅 ${btMeta.period_badge || '2021-2026'}</span>
                                    </div>
                                    <div style="font-size: 0.85rem; display: flex; justify-content: space-between; align-items: center; margin-top: 4px; gap: 6px; flex-wrap: wrap; border-top: 1px solid rgba(255,255,255,0.06); padding-top: 6px;">
                                        <span style="color: var(--accent-green); font-weight: 800; font-family: var(--font-mono);">${wrPct}% OOS</span>
                                        <span style="color: var(--text-secondary); font-weight: 600; font-family: var(--font-mono);">${tradeCnt} ops (~${opsPerYear}/año)</span>
                                        <span style="color: var(--accent-purple); font-weight: 800; font-family: var(--font-mono);">Ciclo: ${streakProb}%</span>
                                    </div>
                                </button>
                            `;
                        });
                        topList.innerHTML = pillsHtml;

                        topList.querySelectorAll('.top-strat-pill').forEach(pill => {
                            pill.addEventListener('click', (e) => {
                                const idx = parseInt(e.currentTarget.dataset.stratIdx);
                                const selectedStrat = data.top_strategies[idx];
                                if (!selectedStrat) return;
                                topList.querySelectorAll('.top-strat-pill').forEach((p, i) => {
                                    p.classList.toggle('active', i === idx);
                                    p.style.background = i === idx ? 'rgba(192, 132, 252, 0.25)' : 'rgba(255, 255, 255, 0.04)';
                                    p.style.borderColor = i === idx ? 'var(--accent-purple)' : 'var(--border-subtle)';
                                    p.style.color = i === idx ? '#ffffff' : 'var(--text-secondary)';
                                });
                                renderStrategyView(selectedStrat);
                            });
                        });
                    }
                    renderStrategyView(data.top_strategies[0]);
                } else if (topBox) {
                    topBox.style.display = 'none';
                }

                if (data.correlation_matrix && typeof createCorrelationHeatmap === 'function') {
                    window._corrMatrix = data.correlation_matrix.matrix;
                    window._corrLabels = data.correlation_matrix.labels;
                    createCorrelationHeatmap('smart-correlation-canvas', data.correlation_matrix.matrix, data.correlation_matrix.labels);
                }
                
                const selectedBody = document.getElementById('smart-selected-assets-body');
                if (selectedBody && data.selected_assets) {
                    let html = '';
                    data.selected_assets.forEach(asset => {
                        let wrDisplay = '--';
                        if (data.asset_win_rates && data.asset_win_rates[asset] !== undefined) {
                            const raw = data.asset_win_rates[asset];
                            if (typeof raw === 'object' && raw !== null) {
                                const pct = (raw.win_rate * 100).toFixed(1);
                                wrDisplay = `${pct}%<span style="font-size:0.82rem; font-weight:normal; color:var(--text-secondary); display:block;">(${raw.wins}/${raw.trades} ops)</span>`;
                            } else {
                                wrDisplay = `${(parseFloat(raw) * 100).toFixed(1)}%`;
                            }
                        } else {
                            wrDisplay = `${(data.win_rate_oos * 100).toFixed(1)}%`;
                        }
                        const info = data.asset_info && data.asset_info[asset];
                        html += `
                            <tr style="border-bottom: 1px solid rgba(255,255,255,0.06);" title="${info ? info.period_str : ''}">
                                <td style="padding: 8px 6px; font-weight: 700; color: var(--text-primary);">${asset}<div style="font-size: 0.82rem; color: var(--text-secondary); font-weight: normal; margin-top: 2px;">📅 ${info ? `${info.start} - ${info.end}` : '2021 - 2026'}</div></td>
                                <td style="padding: 8px 6px; color: var(--accent-green); vertical-align: middle; font-weight: 600;">No Correlacionado</td>
                                <td style="padding: 8px 6px; text-align: right; font-weight: 800; color: var(--accent-primary); vertical-align: middle; font-family: var(--font-mono); font-size: 0.95rem;">${wrDisplay}</td>
                            </tr>
                        `;
                    });
                    const excluded = universe.filter(a => !data.selected_assets.includes(a));
                    excluded.forEach(asset => {
                        const info = data.asset_info && data.asset_info[asset];
                        html += `
                            <tr style="border-bottom: 1px solid rgba(255,255,255,0.06); opacity: 0.55;">
                                <td style="padding: 8px 6px; font-weight: 700; color: var(--text-secondary);">${asset}<div style="font-size: 0.82rem; color: var(--text-secondary); font-weight: normal; margin-top: 2px;">📅 ${info ? `${info.start} - ${info.end}` : '2021 - 2026'}</div></td>
                                <td style="padding: 8px 6px; color: var(--accent-red); vertical-align: middle; font-weight: 600;">Descartado (Correlacionado)</td>
                                <td style="padding: 8px 6px; text-align: right; vertical-align: middle; font-family: var(--font-mono);">--</td>
                            </tr>
                        `;
                    });
                    selectedBody.innerHTML = html;
                }
            
                const optWr = document.getElementById('opt-winrate');
                if (optWr) optWr.value = (data.win_rate_oos * 100).toFixed(2);
                const optPay = document.getElementById('opt-payout');
                if (optPay) optPay.value = payout;
                const optBase = document.getElementById('opt-base-capital');
                if (optBase) optBase.value = base_capital;
                const optProf = document.getElementById('opt-profit-pct');
                if (optProf) optProf.value = profit_pct;
                const optAtt = document.getElementById('opt-attempts');
                if (optAtt) optAtt.value = attempts;
                
                const leader = data.top_strategies && data.top_strategies.length > 0 ? data.top_strategies[0] : null;
                const isApproved = data.campaign_status?.is_approved ?? (leader?.validation?.approved ?? (leader?.sim_summary?.net_pnl > 0));

                state.currentBacktestData = {
                    id: 'campaign_' + Date.now(),
                    timestamp: Date.now(),
                    type: 'campaign_bundle',
                    campaign_name: `Campaña Multi-Activo [${(data.selected_assets || []).slice(0, 3).join(', ')}${(data.selected_assets || []).length > 3 ? ' +' + ((data.selected_assets || []).length - 3) : ''}]`,
                    is_approved: isApproved,
                    approved_count: data.campaign_status?.approved_count ?? (isApproved ? 1 : 0),
                    total_strategies: data.top_strategies ? data.top_strategies.length : 1,
                    campaign_status: data.campaign_status || {},
                    top_strategies: data.top_strategies || [],
                    inputs: {
                        is_smart: true, is_campaign: true, strategy: leader?.type || 'multi_asset_portfolio', strategy_display: leader?.name || 'Campaña Multi-Activo',
                        badge_label: leader?.badge_label || '', params: leader?.best_genome || {}, pair: (data.selected_assets || []).join(', '),
                        interval: '1d', expiry_candles: 2, payout: payout, mode: 'BARBELL', n_consecutive: bestN, bet_fraction: bet_fraction
                    },
                    results: { summary: leader?.sim_summary || data.sim_summary, trades: leader?.trades || data.trades, equity_curve: leader?.equity_curve || data.equity_curve, stats: leader?.stats || data.stats, signals: leader?.signals || data.signals },
                    optimizer: leader?.streak_plan || data.streak_plan,
                    montecarlo: { paths: data.mc_paths, final_equity: leader?.mc_discrete || data.mc_discrete, ruin_probability: (leader?.mc_discrete?.ruin_probability ?? data.mc_discrete?.ruin_probability) || 0.0, max_drawdowns: leader?.stats?.drawdown || data.stats?.drawdown || {} }
                };
                
                if (typeof getHistory === 'function' && typeof setHistory === 'function') {
                    const historyList = getHistory();
                    historyList.unshift(state.currentBacktestData);
                    if (historyList.length > 50) historyList.pop();
                    setHistory(historyList);
                }
                if (typeof renderResultsLists === 'function') renderResultsLists();
            }
        };
    } catch (e) {
        setProgress(0);
        log(`❌ Error: ${e.message}`, 'error');
        console.error(e);
        alert('Error ejecutando la optimización inteligente.');
        cleanup();
    }
}

// Global browser bridge compatibility
if (typeof window !== 'undefined') {
    window.BinSimModules = window.BinSimModules || {};
    window.BinSimModules.smart_mode = { runSmartOptimization, updateInputsFromPreset, initSmartModePresets };
    window.runSmartOptimization = runSmartOptimization;
    window.updateInputsFromPreset = updateInputsFromPreset;
}
