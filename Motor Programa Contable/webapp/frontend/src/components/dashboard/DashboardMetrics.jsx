import React from 'react';
import { Activity, ArrowDownRight, ArrowUpRight, Percent, Layers } from 'lucide-react';

export function DashboardMetrics({ kpis, modalSpread, formatCurrency }) {
    if (!kpis) return null;

    return (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '1rem', marginBottom: '1.75rem' }}>
            {/* KPI 1: Volumen Total Operado */}
            <div className="card-surface" style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <span style={{ fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-secondary)', fontWeight: 600 }}>
                        Volumen Total Movido
                    </span>
                    <div style={{ background: 'var(--brand-indigo-subtle)', padding: '0.45rem', borderRadius: 'var(--radius-md)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <Activity color="#818CF8" size={18} />
                    </div>
                </div>
                <div>
                    <h3 style={{ fontSize: '1.55rem', margin: 0, fontWeight: 800, color: '#F8FAFC', letterSpacing: '-0.02em' }} className="tabular-nums">
                        {formatCurrency(kpis.total_volume_ars)}
                    </h3>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: 'auto', paddingTop: '0.25rem' }}>
                    <span className="badge badge-indigo">Consolidado</span>
                    <span style={{ fontSize: '12px', color: 'var(--text-muted)' }} className="tabular-nums">
                        {kpis.tx_count ?? 0} operaciones
                    </span>
                </div>
            </div>

            {/* KPI 2: Compras Fiat (Egresos) */}
            <div className="card-surface" style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <span style={{ fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-secondary)', fontWeight: 600 }}>
                        Compras Fiat (Egresos)
                    </span>
                    <div style={{ background: 'var(--accent-amber-subtle)', padding: '0.45rem', borderRadius: 'var(--radius-md)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <ArrowDownRight color="#FBBF24" size={18} />
                    </div>
                </div>
                <div>
                    <h3 style={{ fontSize: '1.55rem', margin: 0, fontWeight: 800, color: '#FBBF24', letterSpacing: '-0.02em' }} className="tabular-nums">
                        - {formatCurrency(kpis.total_buys_ars)}
                    </h3>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: 'auto', paddingTop: '0.25rem' }}>
                    <span className="badge badge-amber">Capital Invertido</span>
                    <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Costo base FIFO</span>
                </div>
            </div>

            {/* KPI 3: Ventas Fiat (Ingresos) */}
            <div className="card-surface" style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <span style={{ fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-secondary)', fontWeight: 600 }}>
                        Ventas Fiat (Ingresos)
                    </span>
                    <div style={{ background: 'var(--accent-emerald-subtle)', padding: '0.45rem', borderRadius: 'var(--radius-md)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <ArrowUpRight color="#34D399" size={18} />
                    </div>
                </div>
                <div>
                    <h3 style={{ fontSize: '1.55rem', margin: 0, fontWeight: 800, color: '#34D399', letterSpacing: '-0.02em' }} className="tabular-nums">
                        + {formatCurrency(kpis.total_sells_ars)}
                    </h3>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: 'auto', paddingTop: '0.25rem' }}>
                    <span className="badge badge-emerald">Flujo Realizado</span>
                    <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Ingreso devengado</span>
                </div>
            </div>

            {/* KPI 4: Spread Modal */}
            {modalSpread && (
                <div className="card-surface" style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                        <span style={{ fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-secondary)', fontWeight: 600 }}>
                            Spread Más Frecuente
                        </span>
                        <div style={{ background: 'var(--brand-indigo-subtle)', padding: '0.45rem', borderRadius: 'var(--radius-md)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                            <Percent color="#818CF8" size={18} />
                        </div>
                    </div>
                    <div>
                        <h3 style={{ fontSize: '1.55rem', margin: 0, fontWeight: 800, color: '#818CF8', letterSpacing: '-0.02em' }} className="tabular-nums">
                            +{modalSpread.modal_spread}%
                        </h3>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: 'auto', paddingTop: '0.25rem' }}>
                        <span className="badge badge-indigo">Moda Estadística</span>
                        <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Margen típico</span>
                    </div>
                </div>
            )}

            {/* KPI 5: Total Operaciones */}
            <div className="card-surface" style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <span style={{ fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-secondary)', fontWeight: 600 }}>
                        Registros en Ledger
                    </span>
                    <div style={{ background: 'rgba(148, 163, 184, 0.12)', padding: '0.45rem', borderRadius: 'var(--radius-md)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <Layers color="#94A3B8" size={18} />
                    </div>
                </div>
                <div>
                    <h3 style={{ fontSize: '1.55rem', margin: 0, fontWeight: 800, color: '#F8FAFC', letterSpacing: '-0.02em' }} className="tabular-nums">
                        {(kpis.tx_count ?? 0).toLocaleString()}
                    </h3>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: 'auto', paddingTop: '0.25rem' }}>
                    <span className="badge badge-slate">FIFO Estricto</span>
                    <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Auditabilidad continua</span>
                </div>
            </div>
        </div>
    );
}

export default DashboardMetrics;
