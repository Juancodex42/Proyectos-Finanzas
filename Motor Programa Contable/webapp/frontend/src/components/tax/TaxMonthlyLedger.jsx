import React from 'react';

export function TaxMonthlyLedger({ report, scopeFilter = 'all', selectedYear, formatARS, activeMetrics }) {
    if (!report) return null;

    let filteredMonths = report.monthly_data || [];
    if (scopeFilter === 'certified') {
        filteredMonths = filteredMonths.filter(m => (m.certified_count || 0) > 0);
    } else if (scopeFilter === 'provisional') {
        filteredMonths = filteredMonths.filter(m => (m.provisional_count || 0) > 0);
    }

    const effectiveAlicuotaIibb = activeMetrics?.alicuota_iibb ?? report.alicuota_iibb ?? 0;

    const totalBuys = scopeFilter === 'certified'
        ? (report.certified?.buys_ars || 0)
        : scopeFilter === 'provisional'
            ? (report.provisional?.buys_ars || 0)
            : (report.total_buys_ars || 0);

    const totalSells = scopeFilter === 'certified'
        ? (report.certified?.sells_ars || 0)
        : scopeFilter === 'provisional'
            ? (report.provisional?.sells_ars || 0)
            : (report.total_sells_ars || 0);

    const totalPnl = scopeFilter === 'certified'
        ? (report.certified?.ganancia_neta || 0)
        : scopeFilter === 'provisional'
            ? (report.provisional?.ganancia_neta || 0)
            : (report.ganancia_neta || 0);

    const totalGanancias = scopeFilter === 'certified'
        ? (report.certified?.impuesto_ganancias || 0)
        : scopeFilter === 'provisional'
            ? (report.provisional?.impuesto_ganancias || 0)
            : (report.impuesto_ganancias || 0);

    const baseIIBB = report.settings?.iibb_base_calculo === 'diferencial' ? totalPnl : totalSells;
    const totalIIBB = Math.max(0, baseIIBB * ((effectiveAlicuotaIibb || 5.0) / 100));

    return (
        <div className="card-surface" style={{ overflow: 'hidden' }}>
            <div style={{ padding: '1.25rem 1.5rem', borderBottom: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <div style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#10B981' }} />
                    <h3 style={{ fontSize: '1.1rem', color: '#F8FAFC', margin: 0, fontWeight: 700 }}>
                        Desglose Mensual para Declaración Jurada (DDJJ)
                    </h3>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span className="badge badge-slate">
                        {filteredMonths.length} meses computados
                    </span>
                    {scopeFilter !== 'all' && (
                        <span className={`badge ${scopeFilter === 'certified' ? 'badge-emerald' : 'badge-amber'}`}>
                            Vista: {scopeFilter === 'certified' ? 'Solo Auditados CPN' : 'Solo Provisorios'}
                        </span>
                    )}
                </div>
            </div>

            {filteredMonths.length === 0 ? (
                <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', textAlign: 'center', padding: '3rem 1.5rem', margin: 0 }}>
                    No se registraron operaciones para el alcance seleccionado en el ejercicio fiscal {selectedYear}.
                </p>
            ) : (
                <div style={{ overflowX: 'auto' }}>
                    <table className="table-ledger">
                        <thead>
                            <tr>
                                <th>Período</th>
                                <th>Estado Auditoría</th>
                                <th style={{ textAlign: 'right' }}>Compras (ARS)</th>
                                <th style={{ textAlign: 'right' }}>Ventas (ARS)</th>
                                <th style={{ textAlign: 'right' }}>Ganancia Neta (PnL)</th>
                                <th style={{ textAlign: 'right' }}>Est. Ganancias (ARS)</th>
                                <th style={{ textAlign: 'right' }}>Est. IIBB (ARS)</th>
                            </tr>
                        </thead>
                        <tbody>
                            {filteredMonths.map((m, idx) => {
                                const displayBuys = scopeFilter === 'certified' && m.certified_buys_ars !== undefined
                                    ? m.certified_buys_ars
                                    : (scopeFilter === 'uncertified' || scopeFilter === 'provisional') && m.provisional_buys_ars !== undefined
                                        ? m.provisional_buys_ars
                                        : m.buys_ars;
                                const displaySells = scopeFilter === 'certified' && m.certified_sells_ars !== undefined
                                    ? m.certified_sells_ars
                                    : (scopeFilter === 'uncertified' || scopeFilter === 'provisional') && m.provisional_sells_ars !== undefined
                                        ? m.provisional_sells_ars
                                        : m.sells_ars;
                                const m_pnl = scopeFilter === 'certified' ? (m.certified_pnl_ars ?? m.pnl_ars) : scopeFilter === 'provisional' ? (m.provisional_pnl_ars ?? m.pnl_ars) : m.pnl_ars;
                                const m_base_iibb = report.settings?.iibb_base_calculo === 'diferencial' ? m_pnl : displaySells;
                                const m_iibb = Math.max(0, m_base_iibb * ((effectiveAlicuotaIibb || 5.0) / 100));
                                const m_ganancias = Math.max(0, m_pnl * ((report.settings?.ganancias_alicuota || 15.0) / 100));

                                return (
                                    <tr key={idx}>
                                        <td style={{ fontWeight: 600, color: '#818CF8' }}>{m.month}</td>
                                        <td>
                                            <span className={`badge ${
                                                m.status === 'CERTIFIED'
                                                    ? 'badge-emerald'
                                                    : m.status === 'MIXED'
                                                        ? 'badge-amber'
                                                        : 'badge-indigo'
                                            }`} style={{ fontSize: '11px' }}>
                                                {m.status === 'CERTIFIED'
                                                    ? '✓ Auditado CPN'
                                                    : m.status === 'MIXED'
                                                        ? `⚖ Mixto (${m.certified_count} cert / ${m.provisional_count} prov)`
                                                        : 'Provisorio'}
                                            </span>
                                        </td>
                                        <td style={{ textAlign: 'right' }} className="tabular-nums">{formatARS(displayBuys)}</td>
                                        <td style={{ textAlign: 'right' }} className="tabular-nums">{formatARS(displaySells)}</td>
                                        <td style={{ textAlign: 'right', color: m_pnl >= 0 ? '#34D399' : '#FB7185', fontWeight: 600 }} className="tabular-nums">
                                            {m_pnl >= 0 ? '+' : ''}{formatARS(m_pnl)}
                                        </td>
                                        <td style={{ textAlign: 'right', color: '#FBBF24' }} className="tabular-nums">{formatARS(m_ganancias)}</td>
                                        <td style={{ textAlign: 'right', color: '#818CF8' }} className="tabular-nums">{formatARS(m_iibb)}</td>
                                    </tr>
                                );
                            })}
                        </tbody>
                        <tfoot>
                            <tr
                                style={{ background: 'var(--bg-panel)', borderTop: '2px solid var(--border-strong)', fontWeight: 700 }}
                                title="Los importes mensuales son estimaciones pre-deducción. El total anual aplica la deducción especial anual y la compensación de quebrantos entre meses."
                            >
                                <td colSpan={2} style={{ padding: '0.85rem 1rem', color: '#F8FAFC' }}>
                                    Total {scopeFilter === 'certified' ? 'Auditado CPN' : scopeFilter === 'provisional' ? 'Provisorio' : 'Ejercicio'} {selectedYear} *
                                </td>
                                <td style={{ padding: '0.85rem 1rem', textAlign: 'right' }} className="tabular-nums">{formatARS(totalBuys)}</td>
                                <td style={{ padding: '0.85rem 1rem', textAlign: 'right' }} className="tabular-nums">{formatARS(totalSells)}</td>
                                <td style={{ padding: '0.85rem 1rem', textAlign: 'right', color: totalPnl >= 0 ? '#34D399' : '#FB7185' }} className="tabular-nums">
                                    {totalPnl >= 0 ? '+' : ''}{formatARS(totalPnl)}
                                </td>
                                <td style={{ padding: '0.85rem 1rem', textAlign: 'right', color: '#FBBF24' }} className="tabular-nums">{formatARS(totalGanancias)}</td>
                                <td style={{ padding: '0.85rem 1rem', textAlign: 'right', color: '#818CF8' }} className="tabular-nums">{formatARS(totalIIBB)}</td>
                            </tr>
                            <tr>
                                <td colSpan={7} style={{ padding: '0.6rem 1rem', fontSize: '0.76rem', color: 'var(--text-secondary)', background: 'rgba(13, 19, 31, 0.6)', borderTop: '1px solid var(--border-subtle)' }}>
                                    * Nota aclaratoria: Los importes mensuales son estimaciones operativas pre-deducción. El total anual aplica la deducción especial anual y la compensación de quebrantos entre meses del ejercicio.
                                </td>
                            </tr>
                        </tfoot>
                    </table>
                </div>
            )}
        </div>
    );
}

export default TaxMonthlyLedger;
