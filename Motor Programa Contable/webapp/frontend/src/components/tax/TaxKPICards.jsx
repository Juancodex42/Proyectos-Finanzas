import React from 'react';
import { TrendingUp, ShieldCheck, Layers, DollarSign } from 'lucide-react';
import { resolveIibbBracket } from './TaxConfigDrawer';

export function TaxKPICards({ report, scopeFilter = 'all', formatARS, tramoIibb, alicuotaIibb }) {
    if (!report) return null;

    let gananciaNeta = report.ganancia_neta;
    let impuestoGanancias = report.impuesto_ganancias;
    let totalSells = report.total_sells_ars;
    let totalBuys = report.total_buys_ars;
    let txCount = report.tx_count || 0;

    let baseIIBB = report.base_iibb ?? (report.settings?.iibb_base_calculo === 'diferencial' ? Math.max(0, gananciaNeta || 0) : (totalSells || 0));
    if (scopeFilter === 'certified') {
        gananciaNeta = report.certified?.ganancia_neta || 0;
        impuestoGanancias = report.certified?.impuesto_ganancias || 0;
        totalSells = report.certified?.sells_ars || 0;
        totalBuys = report.certified?.buys_ars || 0;
        txCount = report.certified_tx_count || 0;
        baseIIBB = report.certified?.base_iibb ?? (report.settings?.iibb_base_calculo === 'diferencial' ? Math.max(0, gananciaNeta) : totalSells);
    } else if (scopeFilter === 'provisional') {
        gananciaNeta = report.provisional?.ganancia_neta || 0;
        impuestoGanancias = report.provisional?.impuesto_ganancias || 0;
        totalSells = report.provisional?.sells_ars || 0;
        totalBuys = report.provisional?.buys_ars || 0;
        txCount = report.provisional_tx_count || 0;
        baseIIBB = report.provisional?.base_iibb ?? (report.settings?.iibb_base_calculo === 'diferencial' ? Math.max(0, gananciaNeta) : totalSells);
    }

    const bracket = resolveIibbBracket(baseIIBB, report);
    const effectiveTramo = tramoIibb ?? (scopeFilter === 'all' && report.tramo_iibb ? report.tramo_iibb : bracket.tramo_iibb);
    const effectiveAlicuota = alicuotaIibb ?? (scopeFilter === 'all' && report.alicuota_iibb ? report.alicuota_iibb : bracket.alicuota_iibb);
    const impuestoIIBB = Math.max(0, baseIIBB * (effectiveAlicuota / 100));

    return (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '1rem', marginBottom: '1.75rem' }}>
            {/* KPI 1: Ganancia Neta Imponible */}
            <div className="card-surface" style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <span style={{ fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-secondary)', fontWeight: 600 }}>
                        Ganancia Neta Imponible (FIFO)
                    </span>
                    <div style={{ background: gananciaNeta >= 0 ? 'var(--accent-emerald-subtle)' : 'var(--accent-rose-subtle)', padding: '0.45rem', borderRadius: 'var(--radius-md)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <TrendingUp size={17} color={gananciaNeta >= 0 ? '#34D399' : '#FB7185'} />
                    </div>
                </div>
                <div>
                    <h3 style={{ fontSize: '1.55rem', margin: 0, fontWeight: 800, color: gananciaNeta >= 0 ? '#34D399' : '#FB7185', letterSpacing: '-0.02em' }} className="tabular-nums">
                        {gananciaNeta >= 0 ? '+' : ''}{formatARS(gananciaNeta)}
                    </h3>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: 'auto', paddingTop: '0.25rem', flexWrap: 'wrap' }}>
                    <span className={`badge ${gananciaNeta >= 0 ? 'badge-emerald' : 'badge-rose'}`}>
                        {gananciaNeta >= 0 ? 'Rendimiento Positivo' : 'Quebranto Impositivo'}
                    </span>
                    <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                        {txCount} operaciones {scopeFilter === 'certified' ? 'auditadas' : scopeFilter === 'provisional' ? 'provisorias' : 'totales'}
                    </span>
                </div>
            </div>

            {/* KPI 2: Impuesto a las Ganancias */}
            <div className="card-surface" style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <span style={{ fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.06em', color: '#FBBF24', fontWeight: 600 }}>
                        Impuesto a las Ganancias ({report.settings ? report.settings.ganancias_alicuota : 15}%)
                    </span>
                    <div style={{ background: 'var(--accent-amber-subtle)', padding: '0.45rem', borderRadius: 'var(--radius-md)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <ShieldCheck size={17} color="#FBBF24" />
                    </div>
                </div>
                <div>
                    <h3 style={{ fontSize: '1.55rem', margin: 0, fontWeight: 800, color: '#FBBF24', letterSpacing: '-0.02em' }} className="tabular-nums">
                        {formatARS(impuestoGanancias)}
                    </h3>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: 'auto', paddingTop: '0.25rem', flexWrap: 'wrap' }}>
                    <span className="badge badge-amber">Cédula Criptoactivo</span>
                    <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                        {scopeFilter === 'all' && report.certified_tx_count > 0 && report.provisional_tx_count > 0
                          ? `Auditado: ${formatARS(report.certified?.impuesto_ganancias)} | Prov: ${formatARS(report.provisional?.impuesto_ganancias)}`
                          : `Deduc. Esp: ${formatARS(report.settings ? report.settings.ganancias_deduccion : 0)}`}
                    </span>
                </div>
            </div>

            {/* KPI 3: IIBB Provincia */}
            <div className="card-surface" style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <span style={{ fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.06em', color: '#818CF8', fontWeight: 600 }}>
                        IIBB {report.settings ? report.settings.iibb_provincia : 'Catamarca'}
                    </span>
                    <div style={{ background: 'var(--brand-indigo-subtle)', padding: '0.45rem', borderRadius: 'var(--radius-md)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <Layers size={17} color="#818CF8" />
                    </div>
                </div>
                <div>
                    <h3 style={{ fontSize: '1.55rem', margin: 0, fontWeight: 800, color: '#818CF8', letterSpacing: '-0.02em' }} className="tabular-nums">
                        {formatARS(impuestoIIBB)}
                    </h3>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: 'auto', paddingTop: '0.25rem', flexWrap: 'wrap' }}>
                    <span className="badge badge-indigo">
                        Tramo #{effectiveTramo} ({effectiveAlicuota}%)
                    </span>
                    <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                        Base: {report.settings?.iibb_base_calculo === 'diferencial' ? 'Ganancia' : 'Ventas'}
                    </span>
                </div>
            </div>

            {/* KPI 4: Ventas vs Compras Brutas */}
            <div className="card-surface" style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <span style={{ fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-secondary)', fontWeight: 600 }}>
                        Volumen Bruto de Ventas
                    </span>
                    <div style={{ background: 'rgba(148, 163, 184, 0.12)', padding: '0.45rem', borderRadius: 'var(--radius-md)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <DollarSign size={17} color="#94A3B8" />
                    </div>
                </div>
                <div>
                    <h3 style={{ fontSize: '1.55rem', margin: 0, fontWeight: 800, color: '#F8FAFC', letterSpacing: '-0.02em' }} className="tabular-nums">
                        {formatARS(totalSells)}
                    </h3>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: 'auto', paddingTop: '0.25rem', flexWrap: 'wrap' }}>
                    <span className="badge badge-slate">Compras:</span>
                    <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }} className="tabular-nums">
                        {formatARS(totalBuys)}
                    </span>
                </div>
            </div>
        </div>
    );
}

export default TaxKPICards;
