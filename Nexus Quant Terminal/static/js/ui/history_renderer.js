/**
 * history_renderer.js - Backtest & Campaign History DOM Renderer
 * Handles interactive cards rendering for saved backtests and auto-optimization campaigns,
 * modal inspection, and strategy deployment bridges to Dual-Bot terminal.
 * Nexus Quant Terminal
 */

import { getHistory, getSaved, saveBacktestById, deleteBacktestById, loadBacktestState } from './history_manager.js';

/**
 * Generates HTML markup for an individual backtest or campaign history card.
 * @param {Object} item 
 * @param {string} type - 'history' | 'saved'
 * @returns {string} HTML string
 */
export function renderBacktestItemHtml(item, type) {
    const currentState = window.state || {};
    const activeClass = currentState.loadedBacktestId === item.id ? 'active' : '';
    const dateStr = new Date(item.timestamp).toLocaleString('es-ES', { 
        day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit'
    });
    
    const isCampaign = item.type === 'campaign_bundle' || item.inputs?.is_campaign || item.id.startsWith('campaign_');
    const stratName = item.inputs?.strategy_display || item.inputs?.strategy || 'Estrategia';
    const pairStr = item.inputs?.pair || 'BTCUSDT';
    
    const pnl = item.results?.summary?.net_pnl || 0;
    const wr = item.results?.summary?.win_rate || item.results?.summary?.win_rate_oos || 0;
    const pf = item.results?.summary?.profit_factor || 1.0;
    const trades = item.results?.summary?.total_trades || (item.results?.trades ? item.results.trades.length : 0);
    const pnlClass = pnl > 0 ? 'text-green' : 'text-red';
    const pnlSign = pnl > 0 ? '+' : '';

    let badgeHtml = '';
    let extraActions = '';
    let metaSubtitle = '';

    if (isCampaign) {
        const isApproved = item.is_approved ?? (pnl > 0 && pf >= 1.25);
        const approvedCount = item.approved_count ?? (isApproved ? 1 : 0);
        const totalCount = item.total_strategies || (item.top_strategies ? item.top_strategies.length : 5);
        
        const statusBadge = isApproved
            ? `<span style="font-size: 0.78rem; font-weight: 800; background: rgba(16, 185, 129, 0.2); color: #10b981; border: 1.5px solid #10b981; padding: 2px 7px; border-radius: 5px;">✅ APROBADA (${approvedCount}/${totalCount})</span>`
            : `<span style="font-size: 0.78rem; font-weight: 800; background: rgba(239, 68, 68, 0.2); color: #ef4444; border: 1.5px solid #ef4444; padding: 2px 7px; border-radius: 5px;">⚠️ RECHAZADA</span>`;

        badgeHtml = `
            <span style="font-size: 0.78rem; font-weight: 800; background: rgba(192, 132, 252, 0.2); color: var(--accent-purple); border: 1.5px solid rgba(192, 132, 252, 0.4); padding: 2px 7px; border-radius: 5px;">⚡ CAMPAÑA</span>
            ${statusBadge}
        `;

        metaSubtitle = `📅 ${dateStr} · Líder: <strong>${stratName}</strong> (${pairStr})`;
        extraActions = `<button type="button" class="btn-secondary" onclick="event.stopPropagation(); window.openCampaignModal('${item.id}')" style="padding: 4px 10px; font-size: 0.8rem; font-weight: 700; color: var(--accent-primary); border-color: var(--accent-primary); background: rgba(56, 189, 248, 0.12);">📂 Ver Estrategias (${item.top_strategies ? item.top_strategies.length : totalCount})</button>`;
    } else {
        const isSmart = item.inputs?.is_smart || item.id.startsWith('bt_smart_');
        badgeHtml = isSmart 
            ? `<span style="font-size: 0.78rem; font-weight: 700; background: rgba(192, 132, 252, 0.2); color: var(--accent-purple); border: 1.5px solid rgba(192, 132, 252, 0.4); padding: 2px 7px; border-radius: 5px;">⚡ AUTO-OPTIMIZACIÓN</span>`
            : `<span style="font-size: 0.78rem; font-weight: 700; background: rgba(56, 189, 248, 0.18); color: var(--accent-primary); border: 1.5px solid rgba(56, 189, 248, 0.4); padding: 2px 7px; border-radius: 5px;">⚙️ BACKTEST MANUAL</span>`;
        metaSubtitle = `${dateStr} | Expiración: ${item.inputs?.expiry_candles || 1}v | Racha N=${item.inputs?.n_consecutive || 3}`;
    }

    let actionsHtml = '';
    if (extraActions) {
        actionsHtml += extraActions;
    }
    if (type === 'history') {
        actionsHtml += `<button type="button" class="btn-save-item" data-id="${item.id}">⭐ Favorito</button>`;
    }
    actionsHtml += `<button type="button" class="btn-delete-item" data-id="${item.id}" data-type="${type}">Eliminar</button>`;

    return `
        <div class="backtest-item ${activeClass}" data-id="${item.id}" data-type="${type}">
            <div class="backtest-item-info">
                <div style="margin-bottom: 6px; display: flex; align-items: center; flex-wrap: wrap; gap: 6px;">
                    ${badgeHtml}
                    <span class="backtest-item-title" style="margin: 0; font-weight: 800;">${isCampaign ? 'Campaña ' + dateStr : stratName + ' [' + pairStr + ']'}</span>
                </div>
                <div class="backtest-item-meta" style="margin-bottom: 6px; font-size: 0.82rem; color: #94a3b8;">${metaSubtitle}</div>
                <div class="backtest-item-metrics">
                    <span>P&L: <strong class="${pnlClass}">${pnlSign}$${pnl.toFixed(2)}</strong></span>
                    <span>Profit Factor: <strong>${pf.toFixed(2)}</strong></span>
                    <span>Win Rate: <strong>${(wr * 100).toFixed(1)}%</strong></span>
                    <span>Trades: <strong>${trades}</strong></span>
                </div>
            </div>
            <div class="backtest-item-actions" style="display: flex; gap: 6px; align-items: center; flex-wrap: wrap;">
                ${actionsHtml}
            </div>
        </div>
    `;
}

/**
 * Opens campaign modal showing ranked strategies from multi-asset optimization.
 * @param {string} campaignId 
 */
export function openCampaignModal(campaignId) {
    const history = getHistory();
    const saved = getSaved();
    const campaign = history.find(x => x.id === campaignId) || saved.find(x => x.id === campaignId);
    
    if (!campaign) {
        alert('Campaña no encontrada en el almacenamiento.');
        return;
    }

    const modal = document.getElementById('campaign-modal');
    const titleEl = document.getElementById('campaign-modal-title');
    const subtitleEl = document.getElementById('campaign-modal-subtitle');
    const bodyEl = document.getElementById('campaign-modal-body');
    if (!modal || !bodyEl) return;

    const dateStr = new Date(campaign.timestamp).toLocaleString('es-ES');
    if (titleEl) titleEl.textContent = `🚀 Campaña Multi-Activo — ${dateStr}`;
    
    const stratCount = campaign.top_strategies ? campaign.top_strategies.length : 0;
    const approvedCount = campaign.top_strategies ? campaign.top_strategies.filter(s => s.validation?.approved).length : 0;
    
    if (subtitleEl) {
        subtitleEl.innerHTML = `Estrategias extraídas: <strong>${stratCount}</strong> | Validadas Walk-Forward: <strong style="color: #10b981;">${approvedCount}</strong>`;
    }

    let cardsHtml = '';
    (campaign.top_strategies || []).forEach((st, idx) => {
        const rank = idx + 1;
        const rankEmoji = rank === 1 ? '🥇' : rank === 2 ? '🥈' : rank === 3 ? '🥉' : '🎖️';
        const isApproved = st.validation?.approved ?? false;
        const statusTag = isApproved
            ? '<span style="font-size: 0.75rem; font-weight: 800; color: #10b981; background: rgba(16, 185, 129, 0.15); border: 1px solid #10b981; padding: 2px 6px; border-radius: 4px;">✅ APROBADA OOS</span>'
            : '<span style="font-size: 0.75rem; font-weight: 800; color: #ef4444; background: rgba(239, 68, 68, 0.15); border: 1px solid #ef4444; padding: 2px 6px; border-radius: 4px;">⚠️ FALLÓ WF</span>';

        const pnl = st.sim_summary?.net_pnl ?? 0;
        const pf = st.sim_summary?.profit_factor ?? 1.0;
        const wr = ((st.sim_summary?.win_rate_oos ?? st.sim_summary?.win_rate ?? 0) * 100).toFixed(1);
        const trades = st.sim_summary?.total_trades ?? 0;
        const pnlColor = pnl >= 0 ? '#10b981' : '#ef4444';
        
        const assetLabel = st.target_asset || st.asset || 'MULTI';
        const tfLabel = st.timeframe || '1D';

        cardsHtml += `
            <div style="background: rgba(255,255,255,0.03); border: 1.5px solid ${rank === 1 ? '#f59e0b' : 'rgba(255,255,255,0.08)'}; border-radius: 10px; padding: 14px 16px; margin-bottom: 12px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; flex-wrap: wrap; gap: 8px;">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span style="font-size: 1.05rem; font-weight: 800; color: #f8fafc;">${rankEmoji} ${st.name}</span>
                        <span style="font-size: 0.75rem; color: var(--accent-primary); font-family: var(--font-mono); font-weight: 700;">[${assetLabel} · ${tfLabel}]</span>
                    </div>
                    <div>${statusTag}</div>
                </div>
                <div style="font-size: 0.8rem; color: #94a3b8; margin-bottom: 10px;">${st.natural_description || ''}</div>
                <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; background: rgba(0,0,0,0.25); border-radius: 6px; padding: 8px 12px; margin-bottom: 12px; font-family: var(--font-mono); font-size: 0.82rem;">
                    <div><span style="color: #64748b; display: block; font-size: 0.7rem;">P&L NETO</span><strong style="color: ${pnlColor}; font-size: 0.92rem;">${pnl >= 0 ? '+' : ''}$${pnl.toFixed(2)}</strong></div>
                    <div><span style="color: #64748b; display: block; font-size: 0.7rem;">PROFIT FACTOR</span><strong style="color: #f8fafc; font-size: 0.92rem;">${pf.toFixed(2)}</strong></div>
                    <div><span style="color: #64748b; display: block; font-size: 0.7rem;">WIN RATE OOS</span><strong style="color: #38bdf8; font-size: 0.92rem;">${wr}%</strong></div>
                    <div><span style="color: #64748b; display: block; font-size: 0.7rem;">TRADES</span><strong style="color: #f8fafc; font-size: 0.92rem;">${trades} ops</strong></div>
                </div>
                <div style="display: flex; justify-content: flex-end; gap: 8px; flex-wrap: wrap;">
                    <button type="button" class="btn-secondary" onclick="window.loadStrategyFromCampaign('${campaignId}', ${idx})" style="padding: 6px 12px; font-size: 0.78rem; font-weight: 700;">📊 Ver en Terminal</button>
                    <button type="button" class="btn-secondary" onclick="window.activateStrategyInBot1('${st.type}', '${st.name}')" style="padding: 6px 12px; font-size: 0.78rem; font-weight: 700; color: #34d399; border-color: rgba(52, 211, 153, 0.4); background: rgba(52, 211, 153, 0.1);">🟢 Activar en Radar Bot 1</button>
                    <button type="button" class="btn-secondary" onclick="window.sendStrategyToBot2('${st.type}', '${st.name}')" style="padding: 6px 12px; font-size: 0.78rem; font-weight: 700; color: #38bdf8; border-color: rgba(56, 189, 248, 0.4); background: rgba(56, 189, 248, 0.1);">🔵 Asignar a Bot 2</button>
                </div>
            </div>
        `;
    });
    bodyEl.innerHTML = cardsHtml;
    modal.style.display = 'flex';
}

/**
 * Closes modal inspection of campaign strategies.
 */
export function closeCampaignModal() {
    const modal = document.getElementById('campaign-modal');
    if (modal) modal.style.display = 'none';
}

/**
 * Loads a selected strategy from campaign bundle into active backtest state and UI.
 * @param {string} campaignId 
 * @param {number} stratIdx 
 */
export function loadStrategyFromCampaign(campaignId, stratIdx) {
    const history = getHistory();
    const saved = getSaved();
    const campaign = history.find(x => x.id === campaignId) || saved.find(x => x.id === campaignId);
    if (!campaign || !campaign.top_strategies || !campaign.top_strategies[stratIdx]) return;
    
    const strat = campaign.top_strategies[stratIdx];
    const s = window.state || {};
    s.currentBacktestData = {
        id: 'strat_' + Date.now(),
        timestamp: Date.now(),
        inputs: {
            strategy: strat.type,
            strategy_display: strat.name,
            pair: strat.target_asset || campaign.inputs?.pair || 'BTCUSDT',
            interval: strat.timeframe || '1d',
            params: strat.best_genome || {}
        },
        results: {
            summary: strat.sim_summary || {},
            trades: strat.trades || [],
            equity_curve: strat.equity_curve || [],
            stats: strat.stats || {},
            signals: strat.signals || []
        },
        optimizer: strat.streak_plan || {},
        montecarlo: {
            final_equity: strat.mc_discrete || {},
            ruin_probability: strat.mc_discrete?.ruin_probability || 0.0
        }
    };
    
    closeCampaignModal();
    if (typeof window.renderDashboard === 'function') {
        window.renderDashboard(s.currentBacktestData.results.summary);
    }
    if (typeof window.showToast === 'function') {
        window.showToast(`✅ Estrategia "${strat.name}" cargada en el panel.`, 'success');
    }
}

/**
 * Enables strategy checkbox in Bot 1 radar and navigates to bot tab.
 * @param {string} stratType 
 * @param {string} stratName 
 */
export function activateStrategyInBot1(stratType, stratName) {
    const cb = document.querySelector(`input[name="b1_strat"][value="${stratType}"]`);
    if (cb) {
        cb.checked = true;
        cb.dispatchEvent(new Event('change'));
    }
    closeCampaignModal();
    const botTabBtn = document.querySelector('[data-tab="bot"]');
    if (botTabBtn) botTabBtn.click();
    if (typeof window.showToast === 'function') {
        window.showToast(`🟢 Estrategia "${stratName}" activada en el Radar de BOT 1.`, 'success');
    }
}

/**
 * Sinks the top approved campaign strategies into Bot 1 radar checkboxes.
 * @param {string} campaignId 
 */
export function applyTopCampaignToBot1(campaignId) {
    const history = getHistory();
    const saved = getSaved();
    const campaign = history.find(x => x.id === campaignId) || saved.find(x => x.id === campaignId);
    if (!campaign || !campaign.top_strategies) return;

    let targetStrats = campaign.top_strategies.filter(s => s.validation?.approved);
    if (targetStrats.length === 0) {
        targetStrats = campaign.top_strategies.slice(0, 3);
    }
    const targetTypes = targetStrats.map(s => s.type);

    document.querySelectorAll('input[name="b1_strat"]').forEach(cb => {
        cb.checked = targetTypes.includes(cb.value);
        cb.dispatchEvent(new Event('change'));
    });

    closeCampaignModal();
    const botTabBtn = document.querySelector('[data-tab="bot"]');
    if (botTabBtn) botTabBtn.click();
    if (typeof window.showToast === 'function') {
        window.showToast(`🎯 Radar de BOT 1 sincronizado con ${targetTypes.length} estrategias de la campaña.`, 'success');
    }
}

/**
 * Assigns campaign strategy directly to Bot 2 dropdown.
 * @param {string} stratType 
 * @param {string} stratName 
 */
export function sendStrategyToBot2(stratType, stratName) {
    const botSelect = document.getElementById('b2-strategy-select');
    if (botSelect) {
        let opt = Array.from(botSelect.options).find(o => o.value === stratType);
        if (!opt) {
            opt = document.createElement('option');
            opt.value = stratType;
            opt.textContent = `🥇 ${stratName} (Campaña)`;
            botSelect.appendChild(opt);
        }
        botSelect.value = stratType;
        botSelect.dispatchEvent(new Event('change'));
    }
    closeCampaignModal();
    const botTabBtn = document.querySelector('[data-tab="bot"]');
    if (botTabBtn) botTabBtn.click();
    if (typeof window.showToast === 'function') {
        window.showToast(`🔵 Estrategia "${stratName}" asignada a BOT 2.`, 'success');
    }
}

export const sendStrategyToBot = sendStrategyToBot2;

/**
 * Renders both History and Saved lists into DOM containers and binds click actions.
 */
export function renderResultsLists() {
    const history = getHistory();
    const saved = getSaved();
    
    const historyList = document.getElementById('history-list');
    const savedList = document.getElementById('saved-list');
    
    if (historyList) {
        if (history.length === 0) {
            historyList.innerHTML = '<p class="empty-text">No hay optimizaciones automáticas registradas en el historial.</p>';
        } else {
            historyList.innerHTML = history.map(item => renderBacktestItemHtml(item, 'history')).join('');
        }
    }
    
    if (savedList) {
        if (saved.length === 0) {
            savedList.innerHTML = '<p class="empty-text">No hay simulaciones manuales o favoritas guardadas.</p>';
        } else {
            savedList.innerHTML = saved.map(item => renderBacktestItemHtml(item, 'saved')).join('');
        }
    }
    
    // Bind item click listeners
    document.querySelectorAll('.backtest-item').forEach(el => {
        el.addEventListener('click', (e) => {
            if (e.target.tagName === 'BUTTON') return;
            const id = el.dataset.id;
            const type = el.dataset.type;
            const list = type === 'history' ? getHistory() : getSaved();
            const item = list.find(x => x.id === id);
            if (item) loadBacktestState(item);
        });
    });
    
    // Bind action button listeners
    document.querySelectorAll('.btn-save-item').forEach(el => {
        el.addEventListener('click', () => {
            const id = el.dataset.id;
            saveBacktestById(id);
        });
    });
    
    document.querySelectorAll('.btn-delete-item').forEach(el => {
        el.addEventListener('click', () => {
            const id = el.dataset.id;
            const type = el.dataset.type;
            deleteBacktestById(id, type);
        });
    });
}

// Global browser window bindings
if (typeof window !== 'undefined') {
    window.renderBacktestItemHtml = renderBacktestItemHtml;
    window.openCampaignModal = openCampaignModal;
    window.closeCampaignModal = closeCampaignModal;
    window.loadStrategyFromCampaign = loadStrategyFromCampaign;
    window.activateStrategyInBot1 = activateStrategyInBot1;
    window.applyTopCampaignToBot1 = applyTopCampaignToBot1;
    window.sendStrategyToBot2 = sendStrategyToBot2;
    window.sendStrategyToBot = sendStrategyToBot2;
    window.renderResultsLists = renderResultsLists;
}
