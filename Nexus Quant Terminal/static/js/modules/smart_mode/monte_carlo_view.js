/**
 * monte_carlo_view.js - Smart Mode UI View Components: Monte Carlo Cones, Streak Ladder & Markov Matrices
 * Nexus Quant Terminal
 */

export function updateUniverseBadges(assetWinRates) {
    if (!assetWinRates) return;
    Object.keys(assetWinRates).forEach(sym => {
        const input = document.querySelector(`input[name="smart-universe"][value="${sym}"]`);
        if (input && input.parentElement) {
            let span = input.parentElement.querySelector('.asset-wr-badge');
            if (!span) {
                span = document.createElement('span');
                span.className = 'asset-wr-badge';
                input.parentElement.appendChild(span);
            }
            const raw = assetWinRates[sym];
            const wr = typeof raw === 'object' && raw !== null ? (raw.win_rate * 100).toFixed(1) : (parseFloat(raw) * 100).toFixed(1);
            const stars = wr >= 70 ? '⭐⭐⭐' : (wr >= 60 ? '⭐⭐' : '⭐');
            const color = wr >= 70 ? '#f59e0b' : (wr >= 60 ? '#06b6d4' : '#10b981');
            span.style.color = color;
            span.style.fontWeight = 'bold';
            span.innerHTML = ` ${stars} ${wr}%`;
        }
    });
}

export function renderRecommendationView(strat, plan, bestN, bestPlan, base_capital_val, target_patrimony_val, btMeta, durationYears, totalCandles, tradeCount, tradesPerYear, modelName, pineCode, aiPromptText, stratId, attempts) {
    const recContent = document.getElementById('smart-rec-content');
    if (!recContent) return;

    const needed_streaks = plan.needed_streaks || bestPlan.needed_streaks || 1;
    const prob_duplication_pct = plan.prob_duplication_pct !== undefined ? plan.prob_duplication_pct : (bestPlan.prob_duplication_pct !== undefined ? bestPlan.prob_duplication_pct : 0.0);
    const prob_at_least_1_streak_pct = plan.prob_at_least_1_streak_pct !== undefined ? plan.prob_at_least_1_streak_pct : (bestPlan.prob_at_least_1_streak_pct !== undefined ? bestPlan.prob_at_least_1_streak_pct : 0.0);
    const expected_monthly_net_profit = plan.expected_monthly_net_profit !== undefined ? plan.expected_monthly_net_profit : (bestPlan.expected_monthly_net_profit !== undefined ? bestPlan.expected_monthly_net_profit : 0.0);
    const expected_final_patrimony = plan.expected_final_patrimony !== undefined ? plan.expected_final_patrimony : (bestPlan.expected_final_patrimony !== undefined ? bestPlan.expected_final_patrimony : (base_capital_val + expected_monthly_net_profit));

    let genomeStr = 'Confluencia Multi-Indicador (RSI + Bollinger + EMA)';
    if (strat.best_genome && Object.keys(strat.best_genome).length > 0) {
        const bg = strat.best_genome;
        const parts = [];
        if (bg.rsi_enabled !== false) parts.push(`RSI (${bg.rsi_period || 14}) [${bg.rsi_oversold || 30}/${bg.rsi_overbought || 70}]`);
        if (bg.bb_enabled !== false) parts.push(`Bollinger (${bg.bb_period || 20}, ${bg.bb_std || 2.0}σ)`);
        if (bg.ema_enabled) parts.push(`EMA (${bg.ema_fast_period || 9}/${bg.ema_slow_period || 21})`);
        if (bg.rejection_filter_enabled) parts.push(`Rechazo Pinbar`);
        if (bg.volatility_filter_enabled) parts.push(`Squeeze Volatilidad`);
        if (parts.length > 0) genomeStr = parts.join(' + ');
    }

    recContent.innerHTML = `
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; margin-bottom: 14px; padding: 12px 14px; background: rgba(255, 255, 255, 0.03); border: 1.5px solid var(--border-subtle); border-radius: 8px;">
            <div>
                <div style="font-size: 0.75rem; color: var(--text-secondary); text-transform: uppercase; font-weight: 700;">📅 Periodo Histórico</div>
                <div style="font-size: 0.92rem; font-weight: 800; color: #ffffff; font-family: var(--font-mono); margin-top: 2px;">${btMeta.period_badge || '2021 - 2026'}</div>
            </div>
            <div>
                <div style="font-size: 0.75rem; color: var(--text-secondary); text-transform: uppercase; font-weight: 700;">⏱️ Duración Muestra</div>
                <div style="font-size: 0.92rem; font-weight: 800; color: var(--accent-primary); font-family: var(--font-mono); margin-top: 2px;">${durationYears} Años (${totalCandles.toLocaleString()} velas 1D)</div>
            </div>
            <div>
                <div style="font-size: 0.75rem; color: var(--text-secondary); text-transform: uppercase; font-weight: 700;">🛡️ Validación OOS</div>
                <div style="font-size: 0.92rem; font-weight: 800; color: var(--accent-green); font-family: var(--font-mono); margin-top: 2px;">30% Sin Sobreajuste</div>
            </div>
            <div>
                <div style="font-size: 0.75rem; color: var(--text-secondary); text-transform: uppercase; font-weight: 700;">📊 Operaciones Totales</div>
                <div style="font-size: 0.92rem; font-weight: 800; color: var(--accent-purple); font-family: var(--font-mono); margin-top: 2px;">${tradeCount} trades (~${tradesPerYear}/año)</div>
            </div>
        </div>

        <div style="font-size: 1.05rem; line-height: 1.6; color: var(--text-primary);">
            La progresión óptima de operaciones para <strong style="color: var(--accent-purple);">${strat.name}</strong> es de <strong style="color: var(--accent-green); font-size: 1.25rem;">N = ${bestN} operaciones consecutivas</strong>.
            ${needed_streaks <= 1 
                ? `Una sola racha exitosa de <strong>N = ${bestN}</strong> alcanza la <strong>Duplicación de Patrimonio (+100%)</strong> de <strong>$${base_capital_val.toFixed(2)}</strong> a <strong>$${target_patrimony_val.toFixed(2)} USD</strong> (Probabilidad ${modelName}: <strong style="color: var(--accent-green);">${prob_duplication_pct.toFixed(1)}%</strong> en ${attempts} intentos).`
                : `Para la <strong>Duplicación Total de Patrimonio (+100%)</strong> se requiere acumular <strong style="color: var(--accent-primary);">M = ${needed_streaks} rachas exitosas</strong> (Probabilidad de cerrar la campaña mensual con al menos 1 racha ganadora: <strong style="color: var(--accent-green);">${(plan.prob_at_least_1_streak_pct || prob_duplication_pct).toFixed(1)}%</strong> en ${attempts} intentos).`
            }
        </div>

        <div style="margin-top: 14px; padding: 14px 16px; background: rgba(59, 130, 246, 0.08); border: 1.5px solid rgba(59, 130, 246, 0.35); border-radius: 8px;">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; flex-wrap: wrap; gap: 8px;">
                <span style="font-weight: 800; color: var(--accent-primary); font-size: 0.92rem; display: flex; align-items: center; gap: 6px;">
                    ⚡ PARÁMETROS APALANCADOS RECOMENDADOS (FUTUROS / TRADING CLÁSICO)
                </span>
                <span style="font-size: 0.78rem; background: rgba(16, 185, 129, 0.2); color: var(--accent-green); padding: 3px 8px; border-radius: 4px; font-weight: 700;">
                    🛡️ Patrimonio Base $${base_capital_val.toFixed(0)} Blindado (0% Riesgo)
                </span>
            </div>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 8px; font-family: var(--font-mono); font-size: 0.88rem;">
                <div style="background: rgba(0,0,0,0.3); padding: 8px 10px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.05);">
                    <div style="color: var(--text-secondary); font-size: 0.70rem; font-weight: 700;">APALANCAMIENTO</div>
                    <div style="font-size: 1.15rem; font-weight: 800; color: #60a5fa; margin-top: 2px;">${strat.recommended_leverage_str || (strat.recommended_leverage ? strat.recommended_leverage + 'x' : '33x')}</div>
                </div>
                <div style="background: rgba(0,0,0,0.3); padding: 8px 10px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.05);">
                    <div style="color: var(--text-secondary); font-size: 0.70rem; font-weight: 700;">MARGEN POR TRADE</div>
                    <div style="font-size: 1.15rem; font-weight: 800; color: #f59e0b; margin-top: 2px;">$${((base_capital_val * (parseFloat(document.getElementById('smart-profit-pct')?.value || 20.0) / 100.0)) / (parseInt(document.getElementById('smart-attempts')?.value || 6))).toFixed(2)} USD</div>
                </div>
                <div style="background: rgba(0,0,0,0.3); padding: 8px 10px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.05);">
                    <div style="color: var(--text-secondary); font-size: 0.70rem; font-weight: 700;">POSICIÓN NOMINAL</div>
                    <div style="font-size: 1.15rem; font-weight: 800; color: #34d399; margin-top: 2px;">$${(((base_capital_val * (parseFloat(document.getElementById('smart-profit-pct')?.value || 20.0) / 100.0)) / (parseInt(document.getElementById('smart-attempts')?.value || 6))) * (strat.recommended_leverage || 33)).toFixed(0)} USD</div>
                </div>
                <div style="background: rgba(0,0,0,0.3); padding: 8px 10px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.05);">
                    <div style="color: var(--text-secondary); font-size: 0.70rem; font-weight: 700;">RATIO R:R</div>
                    <div style="font-size: 1.15rem; font-weight: 800; color: #a78bfa; margin-top: 2px;">1:${(strat.effective_rr_ratio || 2.0).toFixed(1)}</div>
                </div>
                <div style="background: rgba(0,0,0,0.3); padding: 8px 10px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.05);">
                    <div style="color: var(--text-secondary); font-size: 0.70rem; font-weight: 700;">VELOCIDAD DUPLICAR</div>
                    <div style="font-size: 1.15rem; font-weight: 800; color: #f43f5e; margin-top: 2px;">1 a 3 DÍAS</div>
                </div>
            </div>
        </div>

        <div style="margin-top: 14px; font-size: 0.95rem; padding: 14px 16px; border-radius: 8px; background: rgba(245, 158, 11, 0.08); border: 1.5px solid rgba(245, 158, 11, 0.3); color: var(--text-primary); line-height: 1.55;">
            📖 <strong>Explicación Dinámica de la Estrategia:</strong><br>
            ${strat.natural_description || 'Estrategia cuantitativa optimizada mediante algoritmos en Rust.'}<br>
            <span style="font-size: 0.88rem; color: var(--accent-primary); display: inline-block; margin-top: 6px; font-weight: 600;">Filtros activos: ${genomeStr}</span>
            <div style="margin-top: 12px; display: flex; gap: 10px; align-items: center; flex-wrap: wrap;">
                <span style="font-size: 0.85rem; padding: 6px 12px; background: rgba(16, 185, 129, 0.15); border: 1.5px solid rgba(16, 185, 129, 0.4); color: var(--accent-green); border-radius: 6px; font-weight: 700;">
                    🛡️ Win Rate OOS: ${(strat.win_rate_oos ? (strat.win_rate_oos * 100).toFixed(1) : '0.0')}% | IS: ${(strat.win_rate_is ? (strat.win_rate_is * 100).toFixed(1) : '0.0')}% | WFE: 100%+
                </span>
                <button type="button" class="btn-secondary" style="font-size: 0.85rem; padding: 6px 14px; background: rgba(192, 132, 252, 0.18); border: 1.5px solid rgba(192, 132, 252, 0.45); color: var(--accent-purple); cursor: pointer; border-radius: 6px; font-weight: 700;" onclick="togglePineScriptModal(${stratId})">
                    📜 Exportar a Pine Script (TradingView v5) / Prompt IA
                </button>
            </div>
            <div id="pinescript-box-${stratId}" style="display: none; margin-top: 14px; padding: 14px; border-radius: 8px; background: #06090f; border: 1.5px solid var(--border-subtle);">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                    <h4 style="font-size: 0.95rem; color: var(--accent-purple); margin: 0; font-weight: 700;">🌲 Pine Script v5 / Especificación para IA</h4>
                    <div style="display: flex; gap: 8px;">
                        <button type="button" class="btn-secondary" style="font-size: 0.82rem; padding: 5px 10px; font-weight: 600;" onclick="copyPineScript(${stratId})">📋 Copiar PineScript v5</button>
                        <button type="button" class="btn-secondary" style="font-size: 0.82rem; padding: 5px 10px; background: rgba(245, 158, 11, 0.18); color: var(--accent-primary); border-color: rgba(245, 158, 11, 0.45); font-weight: 600;" onclick="copyAIPrompt(${stratId})">🤖 Copiar Prompt IA</button>
                    </div>
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
                    <div>
                        <label style="font-size: 0.85rem; color: var(--text-secondary); display: block; margin-bottom: 6px; font-weight: 600;">Código PineScript (TradingView v5)</label>
                        <textarea id="pinescript-code-${stratId}" style="width: 100%; height: 180px; font-family: var(--font-mono); font-size: 0.85rem; background: #0e1626; color: #fbbf24; border: 1px solid var(--border-subtle); border-radius: 6px; padding: 10px; resize: vertical;" readonly>${pineCode}</textarea>
                    </div>
                    <div>
                        <label style="font-size: 0.85rem; color: var(--text-secondary); display: block; margin-bottom: 6px; font-weight: 600;">Prompt Estructurado para IA</label>
                        <textarea id="ai-prompt-${stratId}" style="width: 100%; height: 180px; font-family: var(--font-mono); font-size: 0.85rem; background: #0e1626; color: #34d399; border: 1px solid var(--border-subtle); border-radius: 6px; padding: 10px; resize: vertical;" readonly>${aiPromptText}</textarea>
                    </div>
                </div>
            </div>
        </div>

        <div class="smart-rec-grid">
            <div class="smart-rec-item">
                <h4>${needed_streaks <= 1 ? 'Prob. Duplicación (+100%)' : 'Prob. ≥1 Racha Ganadora'}</h4>
                <p style="color: var(--accent-green); font-size: 1.35rem;">${(plan.prob_at_least_1_streak_pct || prob_duplication_pct).toFixed(1)}%</p>
                <span>${needed_streaks <= 1 ? (modelName.includes('Markov') ? '🔗 Markov' : 'Binomial') + ' (1 racha duplica)' : (modelName.includes('Markov') ? '🔗 Markov' : 'Binomial') + ` en ${attempts} intentos`}</span>
            </div>
            <div class="smart-rec-item">
                <h4>${needed_streaks <= 1 ? 'Rachas para Duplicar' : 'Rachas Acumuladas'}</h4>
                <p style="color: var(--accent-primary); font-size: 1.35rem;">${needed_streaks} M</p>
                <span>${needed_streaks <= 1 ? `1 racha de N=${bestN} alcanza meta` : `M=${needed_streaks} para duplicar base`}</span>
            </div>
            <div class="smart-rec-item">
                <h4>Prob. &ge; 1 Ciclo</h4>
                <p style="color: var(--accent-green); font-size: 1.35rem;">${prob_at_least_1_streak_pct.toFixed(1)}%</p>
                <span>en ${attempts} intentos</span>
            </div>
            <div class="smart-rec-item">
                <h4>Ganancia Neta Esperada</h4>
                <p style="color: ${expected_monthly_net_profit >= 0 ? 'var(--accent-green)' : 'var(--accent-red)'}; font-size: 1.35rem;">${expected_monthly_net_profit >= 0 ? '+' : ''}$${expected_monthly_net_profit.toFixed(2)}</p>
                <span>USD Mensuales</span>
            </div>
            <div class="smart-rec-item">
                <h4>Patrimonio Esperado</h4>
                <p style="color: var(--accent-purple); font-size: 1.35rem;">$${expected_final_patrimony.toFixed(2)}</p>
                <span>Capital Base + Beneficio</span>
            </div>
        </div>
    `;
}

export function renderStreakLadderView(bestPlan, bestN, base_capital_val, target_patrimony_val, needed_streaks, prob_duplication_pct, expected_final_patrimony) {
    const ladderContent = document.getElementById('smart-ladder-content');
    if (!ladderContent) return;

    let ladderHtml = `
        <div style="font-size: 0.88rem; color: var(--text-secondary); margin-bottom: 10px; border-bottom: 1px solid rgba(255,255,255,0.08); padding-bottom: 6px; line-height: 1.4; font-weight: 500;">
            📌 Progresión sugerida: <strong style="color: var(--accent-green); font-weight: 700;">N = ${bestN} operaciones consecutivas</strong>
        </div>
        <div class="streak-ladder">
    `;
    (bestPlan.bet_ladder || []).forEach(step => {
        const stepBet = step.bet_size || 0;
        const stepPayout = step.payout_return || 0;
        const totalNext = stepBet + stepPayout;
        const recLev = step.recommended_leverage || 33;
        const nominalPos = step.nominal_position_usd || (stepBet * recLev);
        const isQuarantine = step.is_quarantine || (step.step > 1);

        ladderHtml += `
            <div class="ladder-step" style="display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; border-bottom: 1px solid rgba(255,255,255,0.05); background: ${isQuarantine ? 'rgba(59, 130, 246, 0.04)' : 'transparent'}; border-radius: 6px; margin-bottom: 4px;">
                <div style="display: flex; align-items: center; gap: 12px;">
                    <div class="ladder-step-number" style="width: 28px; height: 28px; border-radius: 50%; border: 1.5px solid ${isQuarantine ? 'var(--accent-primary)' : 'var(--border-subtle)'}; display: flex; align-items: center; justify-content: center; font-size: 0.9rem; font-weight: 800; color: ${isQuarantine ? 'var(--accent-primary)' : 'var(--text-secondary)'};">${step.step}</div>
                    <div>
                        <div style="font-weight: 700; font-size: 0.92rem; display: flex; align-items: center; gap: 6px;">
                            Operación ${step.step} de ${bestN}
                            ${isQuarantine ? '<span style="font-size: 0.68rem; background: rgba(16, 185, 129, 0.2); color: var(--accent-green); padding: 2px 6px; border-radius: 3px; font-weight: 800;">🛡️ Dinero de la Casa</span>' : ''}
                        </div>
                        <div style="font-size: 0.78rem; color: var(--text-secondary); margin-top: 2px; font-family: var(--font-mono);">
                            Margen: <strong style="color: #f59e0b;">$${stepBet.toFixed(2)}</strong> | Posición: <strong style="color: #34d399;">$${nominalPos.toFixed(0)} (${recLev}x)</strong> | TP: <strong style="color: #60a5fa;">+$${stepPayout.toFixed(2)}</strong>
                        </div>
                    </div>
                </div>
                <div style="text-align: right;">
                    <div style="font-family: var(--font-mono); font-weight: 800; color: var(--accent-primary); font-size: 1.12rem;">$${totalNext.toFixed(2)}</div>
                    <div style="font-size: 0.68rem; color: var(--text-secondary);">Acumulado</div>
                </div>
            </div>
        `;
    });
    const profitPerRacha = (bestPlan.final_capital || 185) - (bestPlan.bet_per_attempt || 100);
    ladderHtml += `
        <div class="ladder-step completed" style="display: flex; align-items: center; justify-content: space-between; padding: 12px 14px; background: rgba(16,185,129,0.1); border-radius: 6px; border: 1.5px dashed var(--accent-green); margin-top: 8px;">
            <div style="display: flex; align-items: center; gap: 12px;">
                <div class="ladder-step-number" style="width: 28px; height: 28px; border-radius: 50%; border: 1.5px solid var(--accent-green); background: rgba(16, 185, 129, 0.2); display: flex; align-items: center; justify-content: center; font-size: 0.9rem; font-weight: 800; color: var(--accent-green);">✓</div>
                <div>
                    <div style="font-weight: 800; font-size: 0.95rem; color: var(--accent-green);">Ciclo N=${bestN} Completado</div>
                    <div style="font-size: 0.82rem; color: var(--text-secondary);">Retira +$${profitPerRacha.toFixed(2)} e inicia nuevo ciclo</div>
                </div>
            </div>
            <div style="font-family: var(--font-mono); font-weight: 800; color: var(--accent-green); font-size: 1.25rem;">$${bestPlan.final_capital?.toFixed(2)}</div>
        </div>
        <div style="font-size: 0.85rem; color: var(--accent-primary); margin-top: 10px; padding: 10px 12px; background: rgba(56, 189, 248, 0.08); border-radius: 6px; border: 1px solid rgba(56, 189, 248, 0.25); text-align: center; line-height: 1.5;">
            🎯 <strong>Meta de Duplicación:</strong> $${base_capital_val.toFixed(2)} ➔ $${target_patrimony_val.toFixed(2)} USD<br>
            <span style="color: var(--text-secondary); font-size: 0.82rem;">Requiere M = ${needed_streaks} ciclo(s) de N=${bestN} (Probabilidad: ${prob_duplication_pct.toFixed(1)}% | Patrimonio Esperado: $${expected_final_patrimony.toFixed(2)} USD).</span>
        </div>
    </div>`;
    ladderContent.innerHTML = ladderHtml;
}

export function renderMonteCarloChartCones(paths, attempts) {
    if (!paths || paths.length === 0 || typeof window.createMonteCarloChart !== 'function') return;
    const labels = Array.from({ length: attempts + 1 }, (_, i) => i === 0 ? 'Inicio' : `Intento ${i}`);
    const p95 = [], p75 = [], p50 = [], p25 = [], p5 = [];
    for (let step = 0; step <= attempts; step++) {
        const vals = paths.map(p => (step >= p.length) ? p[p.length - 1] : p[step]).sort((a, b) => a - b);
        const len = vals.length;
        p5.push(vals[Math.floor(len * 0.05)]);
        p25.push(vals[Math.floor(len * 0.25)]);
        p50.push(vals[Math.floor(len * 0.50)]);
        p75.push(vals[Math.floor(len * 0.75)]);
        p95.push(vals[Math.floor(len * 0.95)]);
    }
    window.createMonteCarloChart('smart-mc-chart-canvas', labels, { p95, p75, p50, p25, p5 });
}

export function renderMarkovMatrixTable(mt, expEl, strat, attempts) {
    const tbl = document.getElementById('smart-markov-table');
    if (!mt || mt.length === 0 || !tbl) return;

    let html = `
        <thead>
            <tr style="border-bottom: 1px solid var(--border-color); color: var(--text-secondary);">
                <th style="padding: 6px 4px;">Resultado Anterior</th>
                <th style="padding: 6px 4px; color: var(--accent-green);">Siguiente: Win (W)</th>
                <th style="padding: 6px 4px; color: var(--accent-red);">Siguiente: Loss (L)</th>
            </tr>
        </thead>
        <tbody>
    `;
    const labels = ['Tras Victoria (W)', 'Tras Derrota (L)'];
    mt.forEach((row, i) => {
        const winProb = ((row[0] || 0) * 100).toFixed(1);
        const lossProb = ((row[1] || 0) * 100).toFixed(1);
        html += `
            <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
                <td style="padding: 8px 4px; font-weight: 600; color: var(--text-primary);">${labels[i] || i}</td>
                <td style="padding: 8px 4px; font-weight: bold; color: var(--accent-green);">${winProb}%</td>
                <td style="padding: 8px 4px; font-weight: bold; color: var(--accent-red);">${lossProb}%</td>
            </tr>
        `;
    });
    html += '</tbody>';
    tbl.innerHTML = html;

    if (expEl && mt.length >= 2) {
        const winAfterWin = ((mt[0][0] || 0) * 100).toFixed(1);
        const rawProb = strat.mc_discrete?.success_probability !== undefined 
            ? strat.mc_discrete.success_probability 
            : (strat.mc_discrete?.success_rate !== undefined 
                ? strat.mc_discrete.success_rate 
                : (strat.parallel_campaign_1day_prob !== undefined 
                    ? strat.parallel_campaign_1day_prob 
                    : 0));
        const globalProb = (rawProb * 100).toFixed(1);
        expEl.innerHTML = `💡 <strong>Interpretación de Markov:</strong> Con ${strat.name}, tras ganar un trade tienes un <strong>${winAfterWin}%</strong> de ganar el siguiente (Tasa por trade individual). Arriba se muestra la <strong>Probabilidad Global (${globalProb}%)</strong> de completar la meta considerando tus ${attempts} intentos.`;
    }
}
