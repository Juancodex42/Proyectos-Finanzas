// calculators.js - Monte Carlo simulation and streak planning module for Nexus Quant Terminal

export function simulateCampaignMonteCarlo(winRate, payout, n, riskCapital, targetCapital, attempts) {
    const numSimulations = 5000;
    const betPerAttempt = riskCapital / attempts;
    const singleSuccessProb = Math.pow(winRate, n);
    const finalAttemptCapital = betPerAttempt * Math.pow(1 + payout, n);
    
    const paths = [];
    for (let i = 0; i < numSimulations; i++) {
        let capital = riskCapital;
        const path = [capital];
        
        for (let attempt = 1; attempt <= attempts; attempt++) {
            capital -= betPerAttempt;
            const isSuccess = Math.random() < singleSuccessProb;
            if (isSuccess) {
                capital += finalAttemptCapital;
                path.push(capital);
                break;
            } else {
                path.push(capital);
            }
        }
        paths.push(path);
    }
    return paths;
}

export function updateCycleProbability() {
    const nConsecInput = document.getElementById('backtest-n-consecutive');
    if (!nConsecInput) return;
    const n = parseInt(nConsecInput.value) || 5;
    const wr = (window.state && window.state.lastWinRate) ? window.state.lastWinRate : 0.5;
    const prob = Math.pow(wr, n);
    const probEl = document.getElementById('backtest-cycle-prob');
    if (probEl) {
        probEl.textContent = `Probabilidad de éxito del ciclo: ${(prob * 100).toFixed(2)}% (basado en Win Rate de ${(wr * 100).toFixed(1)}%)`;
    }
}

export async function runStreakPlanner() {
    const btn = document.getElementById('btn-calc-streak');
    if (!btn) return;
    btn.textContent = 'Calculando...';
    btn.disabled = true;

    const winRate = parseFloat(document.getElementById('opt-winrate').value) / 100;
    const payout = parseFloat(document.getElementById('opt-payout').value) || 0.85;
    const baseCapital = parseFloat(document.getElementById('opt-base-capital').value) || 1000;
    const profitPct = parseFloat(document.getElementById('opt-profit-pct').value) || 20;
    const riskCapital = baseCapital * profitPct / 100;
    const targetCapital = parseFloat(document.getElementById('opt-target-capital').value) || 1000;
    const attempts = parseInt(document.getElementById('opt-attempts').value) || 5;

    if (isNaN(winRate) || winRate <= 0) {
        alert('Por favor, ingresa un Win Rate o ejecuta primero un Backtest.');
        btn.textContent = 'Calcular Plan de Rachas';
        btn.disabled = false;
        return;
    }

    const progressContainer = document.getElementById('streak-progress-container');
    const progressBarFill = document.getElementById('streak-progress-fill');
    const progressText = document.getElementById('streak-progress-text');
    const progressEta = document.getElementById('streak-progress-eta');

    if (progressContainer) progressContainer.style.display = 'block';
    if (progressBarFill) progressBarFill.style.width = '50%';
    if (progressText) progressText.textContent = 'Calculando plan...';
    if (progressEta) progressEta.textContent = 'En proceso';

    const body = {
        win_rate: winRate,
        payout: payout,
        risk_capital: riskCapital,
        target_capital: targetCapital,
        attempts: attempts
    };

    try {
        const res = await fetch('/api/optimize-streak', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        const data = await res.json();
        if (progressContainer) progressContainer.style.display = 'none';

        if (data.error) {
            alert('Error: ' + data.error);
            btn.textContent = 'Calcular Plan de Rachas';
            btn.disabled = false;
            return;
        }

        const results = data.results_by_n || [];
        const bestN = data.best_n_for_target;
        const bestPlan = results.find(r => r.n === bestN);

        // 1. Render Recommendation
        const recDiv = document.getElementById('streak-recommendation-content');
        if (recDiv && bestPlan) {
            const isMarkov = !!(data.markov_mode || bestPlan.p_ww_used);
            const modelLabel = isMarkov ? `Markov Dinámico (P(W|W): ${(bestPlan.p_ww_used * 100).toFixed(1)}%)` : 'Binomial';
            const successProb = (bestPlan.p_success_campaign * 100).toFixed(1);
            const probDup = bestPlan.prob_duplication_pct !== undefined ? bestPlan.prob_duplication_pct.toFixed(1) : (bestPlan.p_success_campaign * 100).toFixed(1);
            const neededM = bestPlan.needed_streaks || 1;
            const expNetProfit = bestPlan.expected_monthly_net_profit !== undefined ? bestPlan.expected_monthly_net_profit : bestPlan.expected_value;
            const expPatrimony = bestPlan.expected_final_patrimony !== undefined ? bestPlan.expected_final_patrimony : (baseCapital + expNetProfit);
            const evClass = expNetProfit >= 0 ? 'green' : 'red';
            const statusIndicator = expNetProfit >= 0 ? '🟢 Esperanza Matemática Positiva' : '⚠️ Esperanza Matemática Negativa';
            
            recDiv.innerHTML = `
                <div style="font-size: 1.05rem; line-height: 1.6; color: var(--text-primary);">
                    Para tu capital de riesgo de <strong>$${riskCapital.toFixed(2)} USD</strong> dividido en <strong>${attempts} intentos</strong> de <strong>$${bestPlan.bet_per_attempt.toFixed(2)} USD</strong>:
                    La racha óptima es de <strong style="color: var(--accent-green); font-size: 1.2rem;">N = ${bestN} victorias consecutivas</strong> (Requiere <strong>M = ${neededM} racha(s)</strong> para duplicación).
                </div>
                <div class="recommendation-banner" style="margin-top: 16px; display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 12px;">
                    <div class="recommendation-stat">
                        <h4>${neededM <= 1 ? 'Prob. Duplicación' : 'Prob. Éxito Campaña'}</h4>
                        <p class="green">${probDup}%</p>
                        <span style="font-size: 0.85rem; color: var(--text-secondary); font-weight: 500;">${isMarkov ? '🔗 Markov Dinámico' : 'Binomial'} ${neededM <= 1 ? '(1 racha duplica)' : `(≥ 1 racha en ${attempts} intentos)`}</span>
                    </div>
                    <div class="recommendation-stat">
                        <h4>${neededM <= 1 ? 'Rachas para Duplicar' : 'Rachas Acumuladas'}</h4>
                        <p class="blue">${neededM}</p>
                        <span style="font-size: 0.85rem; color: var(--text-secondary); font-weight: 500;">${neededM <= 1 ? '¡1 racha alcanza meta!' : 'para duplicar base'}</span>
                    </div>
                    <div class="recommendation-stat">
                        <h4>Prob. &ge;1 Racha</h4>
                        <p class="green">${successProb}%</p>
                        <span style="font-size: 0.85rem; color: var(--text-secondary); font-weight: 500;">en ${attempts} intentos</span>
                    </div>

                    <div class="recommendation-stat">
                        <h4>Ganancia Neta</h4>
                        <p class="${evClass}">${expNetProfit >= 0 ? '+' : ''}$${expNetProfit.toFixed(2)}</p>
                        <span style="font-size: 0.85rem; color: var(--text-secondary); font-weight: 500;">USD esperados</span>
                    </div>
                    <div class="recommendation-stat">
                        <h4>Patrimonio Final</h4>
                        <p class="blue">$${expPatrimony.toFixed(2)}</p>
                        <span style="font-size: 0.85rem; color: var(--text-secondary); font-weight: 500;">USD esperados</span>
                    </div>
                </div>
                <div style="margin-top: 16px; font-size: 0.92rem; padding: 12px 14px; border-radius: 8px; background: rgba(255,255,255,0.03); border: 1px solid var(--border-subtle); color: var(--text-secondary); line-height: 1.5;">
                    ${statusIndicator}. Con un win rate de <strong>${(winRate*100).toFixed(1)}%</strong> y un payout del <strong>${(payout*100).toFixed(0)}%</strong>, la probabilidad (${modelLabel}) de completar las <strong>M = ${neededM} racha(s)</strong> requeridas es del <strong>${probDup}%</strong>.
                </div>
            `;
        }

        // 2. Render Bet Ladder
        const ladderDiv = document.getElementById('bet-ladder-container');
        if (ladderDiv && bestPlan) {
            let ladderHtml = '<div class="streak-ladder">';
            bestPlan.bet_ladder.forEach(step => {
                const stepBet = step.bet_size || 0;
                const stepPayout = step.payout_return || 0;
                const recLev = step.recommended_leverage || 33;
                const nominalPos = step.nominal_position_usd || (stepBet * recLev);
                const isQuarantine = step.is_quarantine || (step.step > 1);

                ladderHtml += `
                    <div class="ladder-step" style="display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; border-bottom: 1px solid rgba(255,255,255,0.05); background: ${isQuarantine ? 'rgba(59, 130, 246, 0.04)' : 'transparent'}; border-radius: 6px; margin-bottom: 4px;">
                        <div style="display: flex; align-items: center; gap: 12px;">
                            <div class="ladder-step-number" style="width: 28px; height: 28px; border-radius: 50%; border: 1.5px solid ${isQuarantine ? 'var(--accent-primary)' : 'var(--border-subtle)'}; display: flex; align-items: center; justify-content: center; font-size: 0.9rem; font-weight: 800; color: ${isQuarantine ? 'var(--accent-primary)' : 'var(--text-secondary)'};">${step.step}</div>
                            <div class="ladder-step-info">
                                <div class="ladder-step-title" style="font-weight: 700; font-size: 0.92rem; display: flex; align-items: center; gap: 6px;">
                                    Operación ${step.step}
                                    ${isQuarantine ? '<span style="font-size: 0.68rem; background: rgba(16, 185, 129, 0.2); color: var(--accent-green); padding: 2px 6px; border-radius: 3px; font-weight: 800;">🛡️ Dinero de la Casa</span>' : ''}
                                </div>
                                <div class="ladder-step-meta" style="font-size: 0.78rem; color: var(--text-secondary); margin-top: 2px; font-family: var(--font-mono);">
                                    Margen: <strong style="color: #f59e0b;">$${stepBet.toFixed(2)}</strong> | Posición: <strong style="color: #34d399;">$${nominalPos.toFixed(0)} (${recLev}x)</strong> | TP: <strong style="color: #60a5fa;">+$${stepPayout.toFixed(2)}</strong>
                                </div>
                            </div>
                        </div>
                        <div class="ladder-step-amount" style="text-align: right; font-family: var(--font-mono); font-weight: 800; color: var(--accent-primary); font-size: 1.12rem;">$${(stepBet + stepPayout).toFixed(2)}</div>
                    </div>
                `;
            });
            ladderHtml += `
                <div class="ladder-step completed" style="display: flex; align-items: center; justify-content: space-between; padding: 12px 14px; background: rgba(16, 185, 129, 0.1); border-radius: 6px; border: 1.5px dashed var(--accent-green); margin-top: 8px;">
                    <div style="display: flex; align-items: center; gap: 12px;">
                        <div class="ladder-step-number" style="width: 28px; height: 28px; border-radius: 50%; border: 1.5px solid var(--accent-green); background: rgba(16, 185, 129, 0.2); display: flex; align-items: center; justify-content: center; font-size: 0.9rem; font-weight: 800; color: var(--accent-green);">✓</div>
                        <div class="ladder-step-info">
                            <div class="ladder-step-title" style="color: var(--accent-green); font-weight: 800; font-size: 0.95rem;">¡Meta de Duplicación Alcanzada!</div>
                            <div class="ladder-step-meta" style="color: var(--text-secondary); font-size: 0.80rem;">Retira ganancias y consolida tu capital base de arbitraje</div>
                        </div>
                    </div>
                    <div class="ladder-step-amount" style="font-family: var(--font-mono); font-weight: 800; color: var(--accent-green); font-size: 1.25rem;">$${bestPlan.final_capital.toFixed(2)}</div>
                </div>
            `;
            ladderHtml += '</div>';
            ladderDiv.innerHTML = ladderHtml;
        }

        // 3. Render Alternatives Table
        const nTable = document.getElementById('streak-alternatives-table').getElementsByTagName('tbody')[0];
        if (nTable) {
            let tableHtml = '';
            results.forEach(r => {
                const isOpt = r.n === bestN;
                const netProfit = r.expected_monthly_net_profit !== undefined ? r.expected_monthly_net_profit : r.expected_value;
                const isPositive = netProfit >= 0;
                const dupProb = r.prob_duplication_pct !== undefined ? r.prob_duplication_pct.toFixed(1) : (r.p_success_campaign * 100).toFixed(1);
                const neededM = r.needed_streaks !== undefined ? r.needed_streaks : 1;
                tableHtml += `
                    <tr style="${isOpt ? 'background: rgba(16, 185, 129, 0.12); border: 1px solid var(--accent-green);' : ''}">
                        <td><strong>${isOpt ? '>> ' : ''}${r.n}</strong></td>
                        <td>${(r.p_success_single * 100).toFixed(1)}%</td>
                        <td>${neededM}</td>
                        <td>${dupProb}%</td>
                        <td>$${r.bet_per_attempt.toFixed(0)}</td>
                        <td>$${r.final_capital.toFixed(0)}</td>
                        <td class="${isPositive ? 'text-green' : 'text-red'}" style="font-weight: 500;">
                            ${isPositive ? '+' : ''}$${netProfit.toFixed(1)}
                        </td>
                    </tr>
                `;
            });
            nTable.innerHTML = tableHtml;
        }

        // 4. Run Campaign Monte Carlo Simulation
        const paths = simulateCampaignMonteCarlo(winRate, payout, bestN, riskCapital, targetCapital, attempts);
        if (paths.length > 0 && typeof window.createMonteCarloChart === 'function') {
            const labels = Array.from({ length: attempts + 1 }, (_, i) => i === 0 ? 'Inicio' : `Intento ${i}`);
            
            const p95 = [], p75 = [], p50 = [], p25 = [], p5 = [];
            for (let step = 0; step <= attempts; step++) {
                const vals = paths.map(p => {
                    if (step >= p.length) {
                        return p[p.length - 1];
                    }
                    return p[step];
                }).sort((a, b) => a - b);
                
                const len = vals.length;
                p5.push(vals[Math.floor(len * 0.05)]);
                p25.push(vals[Math.floor(len * 0.25)]);
                p50.push(vals[Math.floor(len * 0.50)]);
                p75.push(vals[Math.floor(len * 0.75)]);
                p95.push(vals[Math.floor(len * 0.95)]);
            }
            window.createMonteCarloChart('mc-chart', labels, { p95, p75, p50, p25, p5 });
        }

    } catch (e) {
        console.error('Streak planner error:', e);
        alert('Error calculando el plan de rachas: ' + e.message);
    }

    btn.textContent = 'Calcular Plan de Rachas';
    btn.disabled = false;
}

// Attach to window for standard HTML script usage
if (typeof window !== 'undefined') {
    window.runStreakPlanner = runStreakPlanner;
    window.simulateCampaignMonteCarlo = simulateCampaignMonteCarlo;
    window.updateCycleProbability = updateCycleProbability;
}
