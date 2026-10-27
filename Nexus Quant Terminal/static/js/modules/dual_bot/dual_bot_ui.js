/**
 * dual_bot_ui.js - Dual Bot Execution Terminal HUD, Charting & DOM Presentation Engine
 * Nexus Quant Terminal
 */

export function populateCampaignStrategies(selB2Strat) {
    if (!selB2Strat) return;
    try {
        const history = JSON.parse(localStorage.getItem('binsim_history')) || [];
        const saved = JSON.parse(localStorage.getItem('binsim_saved')) || [];
        const allItems = [...saved, ...history];
        const campaigns = allItems.filter(x => x.type === 'campaign_bundle' || (x.top_strategies && x.top_strategies.length > 0));
        if (campaigns.length > 0) {
            let grp = selB2Strat.querySelector('optgroup[label="⚡ Estrategias de Campañas Optimizadas"]');
            if (!grp) {
                grp = document.createElement('optgroup');
                grp.label = "⚡ Estrategias de Campañas Optimizadas";
                selB2Strat.appendChild(grp);
            }
            grp.innerHTML = '';
            campaigns.slice(0, 5).forEach(camp => {
                const dateStr = new Date(camp.timestamp).toLocaleDateString('es-ES', { day: '2-digit', month: '2-digit' });
                const leader = camp.top_strategies && camp.top_strategies.length > 0 ? camp.top_strategies[0] : null;
                const stratName = leader ? leader.name : (camp.inputs?.strategy_display || 'Líder');
                const stratType = leader ? leader.type : (camp.inputs?.strategy || 'volatility_squeeze_ml');
                const wr = leader ? (leader.win_rate_oos * 100).toFixed(1) : '65.0';
                const opt = document.createElement('option');
                opt.value = stratType;
                opt.textContent = `🥇 ${stratName} (${dateStr} · ${wr}% OOS)`;
                grp.appendChild(opt);
            });
        }
    } catch (e) {
        console.warn('Error poblando estrategias de campaña en Bot 2:', e);
    }
}

export function updateActivePositionHUD(side, entryPrice, sizeUsd, candleSeries, priceLines) {
    const hudSide = document.getElementById('hud-pos-side');
    const hudSize = document.getElementById('hud-pos-size');
    const hudEntry = document.getElementById('hud-pos-entry');
    const hudSl = document.getElementById('hud-pos-sl');
    const hudTp = document.getElementById('hud-pos-tp');
    const hudPnl = document.getElementById('hud-pos-pnl');
    const btnClose = document.getElementById('btn-hud-close-position');
    if (!hudSide) return null;

    const isLong = (side === 'BUY');
    const slPrice = isLong ? entryPrice * 0.985 : entryPrice * 1.015;
    const tpPrice = isLong ? entryPrice * 1.0375 : entryPrice * 0.9625;

    hudSide.innerHTML = isLong ? '<span style="color: #34d399;">🟢 ENTRADA LONG (COMPRADO)</span>' : '<span style="color: #f87171;">🔴 ENTRADA SHORT (VENDIDO)</span>';
    hudSize.textContent = `$${sizeUsd.toFixed(2)} USD`;
    hudEntry.textContent = `$${entryPrice.toFixed(2)}`;
    hudSl.textContent = `$${slPrice.toFixed(2)} (-1.5%)`;
    hudTp.textContent = `$${tpPrice.toFixed(2)} (+3.75%)`;
    hudPnl.innerHTML = '<span style="color: #34d399;">+$0.00 (+0.0%)</span>';

    if (btnClose) btnClose.style.display = 'inline-block';

    if (candleSeries && priceLines) {
        priceLines.forEach(pl => { try { candleSeries.removePriceLine(pl); } catch (e) {} });
        priceLines.length = 0;
        priceLines.push(candleSeries.createPriceLine({ price: entryPrice, color: '#38bdf8', lineWidth: 1, lineStyle: 0, title: 'ENTRADA' }));
        priceLines.push(candleSeries.createPriceLine({ price: slPrice, color: '#ef4444', lineWidth: 1, lineStyle: 2, title: 'STOP LOSS' }));
        priceLines.push(candleSeries.createPriceLine({ price: tpPrice, color: '#10b981', lineWidth: 1, lineStyle: 2, title: 'TAKE PROFIT (2.5R)' }));
    }

    return { side, entryPrice, sizeUsd, isLong };
}

export function clearActivePositionHUD(candleSeries, priceLines) {
    const hudSide = document.getElementById('hud-pos-side');
    const hudSize = document.getElementById('hud-pos-size');
    const hudEntry = document.getElementById('hud-pos-entry');
    const hudSl = document.getElementById('hud-pos-sl');
    const hudTp = document.getElementById('hud-pos-tp');
    const hudPnl = document.getElementById('hud-pos-pnl');
    const btnClose = document.getElementById('btn-hud-close-position');

    if (hudSide) hudSide.textContent = 'SIN POSICIÓN ABIERTA (FLAT)';
    if (hudSize) hudSize.textContent = '--';
    if (hudEntry) hudEntry.textContent = '--';
    if (hudSl) hudSl.textContent = '--';
    if (hudTp) hudTp.textContent = '--';
    if (hudPnl) hudPnl.textContent = '--';
    if (btnClose) btnClose.style.display = 'none';

    if (candleSeries && priceLines) {
        priceLines.forEach(pl => { try { candleSeries.removePriceLine(pl); } catch (e) {} });
        priceLines.length = 0;
    }
}

export function updateFloatingPnL(currentPrice, pos) {
    if (!pos) return;
    const pnlUsd = pos.isLong
        ? (currentPrice - pos.entryPrice) * (pos.sizeUsd / pos.entryPrice)
        : (pos.entryPrice - currentPrice) * (pos.sizeUsd / pos.entryPrice);
    const pnlPct = (pnlUsd / pos.sizeUsd) * 100.0;
    const hudPnl = document.getElementById('hud-pos-pnl');
    if (hudPnl) {
        const isPos = pnlUsd >= 0;
        const sign = isPos ? '+' : '';
        const color = isPos ? '#34d399' : '#f87171';
        hudPnl.innerHTML = `<span style="color: ${color}; font-weight: 800;">${sign}$${pnlUsd.toFixed(2)} USD (${sign}${pnlPct.toFixed(1)}%)</span>`;
    }
}

export function initDualEquityChart(canvasId) {
    const ctx = document.getElementById(canvasId)?.getContext('2d');
    if (!ctx) return null;
    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{ label: 'Curva de Equidad ($ USD)', data: [], borderColor: '#10b981', backgroundColor: 'rgba(16, 185, 129, 0.08)', fill: true, tension: 0.3, pointRadius: 2 }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { display: false }, tooltip: { mode: 'index', intersect: false } },
            scales: { x: { display: false }, y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#94a3b8', font: { family: 'JetBrains Mono' } } } }
        }
    });
}

export function renderDualEquityChart(chart, status, activeTab) {
    if (!chart || !status || !status.equity_history) return;
    const hist = status.equity_history;
    const labels = hist.map(h => new Date(h.timestamp * 1000).toLocaleTimeString());
    let data = [], color = '#10b981';
    if (activeTab === 'bot1') {
        data = hist.map(h => h.bot1_equity); color = '#f59e0b';
    } else if (activeTab === 'bot2') {
        data = hist.map(h => h.bot2_equity); color = '#38bdf8';
    } else {
        data = hist.map(h => h.combined_equity); color = '#10b981';
    }
    chart.data.labels = labels;
    chart.data.datasets[0].data = data;
    chart.data.datasets[0].borderColor = color;
    chart.data.datasets[0].backgroundColor = color + '15';
    chart.update('none');
}

export function updateDualBotUI(status) {
    if (!status) return;
    const { connected, mock_mode, bot1, bot2, events_log } = status;
    const connBadge = document.getElementById('binance-conn-status');
    if (connBadge) {
        if (connected) { connBadge.className = 'badge-live-connected'; connBadge.innerHTML = '● Binance Futuros Conectado (En Vivo)'; }
        else if (mock_mode) { connBadge.className = 'badge-live-mock'; connBadge.innerHTML = '● Modo Simulación / Sandbox Seguro'; }
        else { connBadge.className = 'badge-live-disconnected'; connBadge.innerHTML = '● Desconectado'; }
    }

    const b1StatePill = document.getElementById('b1-state-pill');
    if (b1StatePill) { b1StatePill.textContent = bot1.state; b1StatePill.className = `bot-state-badge state-${bot1.state.toLowerCase()}`; }
    const b1Step = document.getElementById('b1-step-text'); if (b1Step) b1Step.textContent = `Paso ${bot1.current_step} / ${bot1.streak_target}`;
    const b1Bullet = document.getElementById('b1-bullet-text'); if (b1Bullet) b1Bullet.textContent = `$${(bot1.current_bullet_usd || 5).toFixed(2)} USD`;
    const b1Profit = document.getElementById('b1-profit-text'); if (b1Profit) b1Profit.textContent = `+$${(bot1.accumulated_profit_usd || 0).toFixed(2)} USD`;
    const b1Pnl = document.getElementById('b1-today-pnl'); if (b1Pnl) b1Pnl.textContent = `${bot1.today_pnl_usd >= 0 ? '+' : ''}$${(bot1.today_pnl_usd || 0).toFixed(2)} USD`;
    const b1Streaks = document.getElementById('b1-streaks-completed'); if (b1Streaks) b1Streaks.textContent = `${bot1.streaks_completed || 0} completadas`;

    const b1Progress = document.getElementById('b1-streak-progress-bar');
    if (b1Progress) b1Progress.style.width = `${(bot1.current_step / bot1.streak_target) * 100.0}%`;

    const mutexPill = document.getElementById('b1-mutex-pill');
    if (mutexPill && bot1) {
        if (bot1.active_trade || bot1.mutex_state === 'LOCKED_IN_TRADE') {
            const sym = bot1.active_trade ? bot1.active_trade.symbol : 'MERCADO';
            mutexPill.style.background = 'rgba(239,68,68,0.2)'; mutexPill.style.color = '#f87171'; mutexPill.style.borderColor = 'rgba(239,68,68,0.4)';
            mutexPill.textContent = `🔒 MUTEX: BLOQUEADO (${sym} PASO ${bot1.current_step + 1})`;
        } else {
            mutexPill.style.background = 'rgba(16,185,129,0.15)'; mutexPill.style.color = '#34d399'; mutexPill.style.borderColor = 'rgba(16,185,129,0.3)';
            mutexPill.textContent = `🟢 MUTEX: LIBRE (BUSCANDO PASO ${bot1.current_step + 1})`;
        }
    }

    const b2StatePill = document.getElementById('b2-state-pill');
    if (b2StatePill) { b2StatePill.textContent = bot2.state; b2StatePill.className = `bot-state-badge state-${bot2.state.toLowerCase()}`; }
    const b2Eq = document.getElementById('b2-equity-text'); if (b2Eq) b2Eq.textContent = `$${(bot2.current_equity_usd || 1000).toFixed(2)} USD`;
    const b2Dd = document.getElementById('b2-drawdown-text'); if (b2Dd) b2Dd.textContent = `${(bot2.current_drawdown_pct || 0).toFixed(1)}% / ${bot2.drawdown_limit_pct}%`;
    const b2Pnl = document.getElementById('b2-month-pnl'); if (b2Pnl) b2Pnl.textContent = `${bot2.month_pnl_usd >= 0 ? '+' : ''}$${(bot2.month_pnl_usd || 0).toFixed(2)} USD`;

    const b2DdBar = document.getElementById('b2-dd-progress-bar');
    if (b2DdBar) {
        b2DdBar.style.width = `${Math.min(100.0, (bot2.current_drawdown_pct / bot2.drawdown_limit_pct) * 100.0)}%`;
        b2DdBar.style.backgroundColor = bot2.current_drawdown_pct > 5.0 ? '#ef4444' : '#10b981';
    }

    const logTbody = document.getElementById('dual-bot-events-tbody');
    if (logTbody && events_log) {
        logTbody.innerHTML = events_log.slice().reverse().map(ev => `
            <tr>
                <td style="color: var(--text-secondary); font-size: 0.8rem;">${ev.time}</td>
                <td><span class="source-tag">${ev.source}</span></td>
                <td style="font-size: 0.85rem;">${ev.message}</td>
            </tr>
        `).join('');
    }
}
