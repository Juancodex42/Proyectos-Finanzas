import React from 'react';
import { resolveIibbBracket } from './TaxConfigDrawer';

export function TaxThresholdScale({ report, scopeFilter = 'all', selectedYear, formatARS, baseIibb, tramoIibb, alicuotaIibb, activeMetrics: activeMetricsProp }) {
    if (!report || !report.settings) return null;

    const activeMetrics = activeMetricsProp || (
        scopeFilter === 'certified'
            ? { ...report.certified, sells_volume: report.certified?.sells_volume ?? report.certified?.sells_ars }
            : scopeFilter === 'provisional'
                ? { ...report.provisional, sells_volume: report.provisional?.sells_volume ?? report.provisional?.sells_ars }
                : report
    );

    const sellsVolume = scopeFilter === 'all'
        ? (report.total_sells_ars ?? report.total_ventas ?? 0)
        : (activeMetrics.sells_volume ?? activeMetrics.base_imponible_iibb ?? 0);

    const isDiferencial = report.settings.iibb_base_calculo === 'diferencial';
    const effectiveBaseIibb = baseIibb !== undefined
        ? baseIibb
        : isDiferencial
            ? Math.max(0, scopeFilter === 'certified'
                ? (report.certified?.ganancia_neta || 0)
                : scopeFilter === 'provisional'
                    ? (report.provisional?.ganancia_neta || 0)
                    : (report.base_iibb ?? report.ganancia_neta ?? 0))
            : sellsVolume;

    const tramo1Pct = report.settings.iibb_tramo1_limite > 0
        ? Math.min(100, (sellsVolume / report.settings.iibb_tramo1_limite) * 100)
        : 0;

    const bracketInfo = resolveIibbBracket(sellsVolume, report);
    let currentTramo = bracketInfo.tramo_iibb;
    if (tramoIibb !== undefined && tramoIibb !== null) {
        if (typeof tramoIibb === 'number') {
            currentTramo = tramoIibb;
        } else if (String(tramoIibb).includes('3')) {
            currentTramo = 3;
        } else if (String(tramoIibb).includes('2')) {
            currentTramo = 2;
        } else {
            currentTramo = 1;
        }
    }
    const currentAlicuota = alicuotaIibb ?? bracketInfo.alicuota_iibb;

    return (
        <div className="card-surface" style={{ padding: '1.5rem', marginBottom: '1.75rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '0.75rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <div style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#818CF8' }} />
                    <h3 style={{ fontSize: '1.1rem', color: '#F8FAFC', margin: 0, fontWeight: 700 }}>
                        Monitor de Tramos y Alícuotas IIBB ({report.settings.iibb_provincia} {selectedYear})
                    </h3>
                </div>
                <span className="badge badge-indigo">
                    Escala Progresiva Activa {scopeFilter !== 'all' ? `(${scopeFilter === 'certified' ? 'Auditado' : 'Provisorio'})` : ''} — Tramo {currentTramo} ({currentAlicuota}%)
                </span>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '0.6rem', flexWrap: 'wrap', gap: '0.75rem' }}>
                <span>
                    Volumen Bruto (Determina Tramo): <strong style={{ color: '#F8FAFC' }} className="tabular-nums">{formatARS(sellsVolume)}</strong>
                </span>
                {isDiferencial && (
                    <span>
                        Base Imponible Efectiva (Régimen Diferencial): <strong style={{ color: '#34D399' }} className="tabular-nums">{formatARS(effectiveBaseIibb)}</strong>
                    </span>
                )}
                <span>
                    Tope Tramo 1: <strong style={{ color: '#818CF8' }} className="tabular-nums">{formatARS(report.settings.iibb_tramo1_limite)}</strong>
                </span>
            </div>

            {/* Progress Bar */}
            <div style={{ width: '100%', height: '10px', background: 'var(--bg-panel)', borderRadius: 'var(--radius-full)', overflow: 'hidden', border: '1px solid var(--border-subtle)', position: 'relative' }}>
                <div
                    style={{
                        width: `${Math.min(100, tramo1Pct)}%`,
                        height: '100%',
                        background: tramo1Pct < 80 ? 'linear-gradient(90deg, #10B981, #818CF8)' : 'linear-gradient(90deg, #F59E0B, #F43F5E)',
                        borderRadius: 'var(--radius-full)',
                        transition: 'width 0.8s ease-in-out'
                    }}
                />
            </div>

            {isDiferencial && (
                <p style={{ margin: '0.55rem 0 0 0', fontSize: '0.76rem', color: 'var(--text-secondary)' }}>
                    En {report.settings.iibb_provincia} bajo régimen diferencial, el volumen bruto de ventas ({formatARS(sellsVolume)}) determina el tramo de alícuota (Tramo {currentTramo}), pero dicha alícuota se aplica sobre la base imponible diferencial efectiva ({formatARS(effectiveBaseIibb)}).
                </p>
            )}

            {/* Scale Footnotes */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.75rem', fontSize: '0.78rem', color: 'var(--text-secondary)', marginTop: '0.85rem' }}>
                <div style={{ background: 'var(--bg-panel)', padding: '0.45rem 0.75rem', borderRadius: 'var(--radius-sm)', border: currentTramo === 1 ? '1px solid var(--brand-indigo)' : '1px solid var(--border-subtle)' }}>
                    <strong style={{ color: currentTramo === 1 ? '#818CF8' : '#F8FAFC' }}>Tramo 1 ({report.settings.iibb_tramo1_alicuota}%):</strong> Hasta {formatARS(report.settings.iibb_tramo1_limite)}
                </div>
                <div style={{ background: 'var(--bg-panel)', padding: '0.45rem 0.75rem', borderRadius: 'var(--radius-sm)', border: currentTramo === 2 ? '1px solid var(--brand-indigo)' : '1px solid var(--border-subtle)' }}>
                    <strong style={{ color: currentTramo === 2 ? '#818CF8' : '#F8FAFC' }}>Tramo 2 ({report.settings.iibb_tramo2_alicuota}%):</strong> Hasta {formatARS(report.settings.iibb_tramo2_limite)}
                </div>
                <div style={{ background: 'var(--bg-panel)', padding: '0.45rem 0.75rem', borderRadius: 'var(--radius-sm)', border: currentTramo === 3 ? '1px solid var(--brand-indigo)' : '1px solid var(--border-subtle)' }}>
                    <strong style={{ color: currentTramo === 3 ? '#818CF8' : '#F8FAFC' }}>Tramo 3 ({report.settings.iibb_tramo3_alicuota}%):</strong> &gt; {formatARS(report.settings.iibb_tramo2_limite)}
                </div>
            </div>
        </div>
    );
}

export default TaxThresholdScale;
