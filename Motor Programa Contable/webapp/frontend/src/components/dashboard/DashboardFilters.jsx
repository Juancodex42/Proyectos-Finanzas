import React from 'react';
import { Filter, Calendar, CheckSquare, Square, ShieldCheck, Scale } from 'lucide-react';

export function DashboardFilters({
    kpis,
    statusFilter,
    setStatusFilter,
    startDate,
    setStartDate,
    endDate,
    setEndDate,
    availableExchanges = [],
    selectedExchanges = [],
    handleToggleExchange,
    handleSelectAllExchanges
}) {
    const certPct = kpis ? (kpis.certified_pct ?? kpis.certified_coverage_pct) : undefined;
    const certCount = kpis ? (kpis.certified_count ?? kpis.certified_tx_count ?? 0) : 0;

    return (
        <>
            {/* LEGAL COVERAGE & CERTIFICATION BACKING BANNER */}
            {kpis && (
                <div style={{
                    background: 'var(--bg-card)',
                    border: '1px solid var(--border-color)',
                    borderRadius: 'var(--radius-lg)',
                    padding: '1.2rem 1.5rem',
                    marginBottom: '1.5rem',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    flexWrap: 'wrap',
                    gap: '1.25rem',
                    boxShadow: 'var(--shadow-md)'
                }}>
                    {certPct !== undefined && certPct > 0 ? (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                            <div style={{
                                width: '44px',
                                height: '44px',
                                borderRadius: '10px',
                                background: 'var(--brand-indigo-subtle)',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                border: '1px solid var(--brand-indigo-border)'
                            }}>
                                <ShieldCheck size={24} color="#818CF8" />
                            </div>
                            <div>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                                    <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 700, color: '#F8FAFC' }}>
                                        Dictamen de Auditoría & Certificaciones
                                    </h3>
                                    <span className={`badge ${certPct === 100 ? 'badge-emerald' : 'badge-indigo'}`}>
                                        {certPct}% Respaldado
                                    </span>
                                </div>
                                <p style={{ margin: '0.2rem 0 0 0', fontSize: '0.84rem', color: 'var(--text-secondary)' }}>
                                    {certCount} de {kpis.tx_count ?? 0} transacciones cuentan con certificación profesional C.P.N.
                                </p>
                            </div>
                        </div>
                    ) : (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                            <div style={{
                                width: '44px',
                                height: '44px',
                                borderRadius: '10px',
                                background: 'rgba(148, 163, 184, 0.12)',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                border: '1px solid var(--border-color)'
                            }}>
                                <ShieldCheck size={24} color="#94A3B8" />
                            </div>
                            <div>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                                    <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 700, color: '#F8FAFC' }}>
                                        Dictamen de Auditoría & Certificaciones
                                    </h3>
                                    <span className="badge badge-slate">0% Respaldado</span>
                                </div>
                                <p style={{ margin: '0.2rem 0 0 0', fontSize: '0.84rem', color: 'var(--text-secondary)' }}>
                                    {certCount} de {kpis.tx_count ?? 0} transacciones cuentan con certificación profesional C.P.N.
                                </p>
                            </div>
                        </div>
                    )}

                    <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.5rem',
                        background: 'var(--bg-panel)',
                        padding: '0.3rem',
                        borderRadius: 'var(--radius-md)',
                        border: '1px solid var(--border-subtle)'
                    }}>
                        <button
                            onClick={() => setStatusFilter('all')}
                            style={{
                                padding: '0.35rem 0.75rem',
                                borderRadius: 'var(--radius-sm)',
                                fontSize: '0.82rem',
                                fontWeight: 600,
                                border: statusFilter === 'all' ? '1px solid var(--brand-indigo)' : '1px solid transparent',
                                background: statusFilter === 'all' ? 'var(--brand-indigo-subtle)' : 'transparent',
                                color: statusFilter === 'all' ? '#FFFFFF' : 'var(--text-secondary)',
                                cursor: 'pointer',
                                transition: 'all 150ms ease'
                            }}
                        >
                            Vista Total
                        </button>
                        <button
                            onClick={() => setStatusFilter('certified')}
                            style={{
                                padding: '0.35rem 0.75rem',
                                borderRadius: 'var(--radius-sm)',
                                fontSize: '0.82rem',
                                fontWeight: 600,
                                border: statusFilter === 'certified' ? '1px solid var(--accent-emerald)' : '1px solid transparent',
                                background: statusFilter === 'certified' ? 'var(--accent-emerald-subtle)' : 'transparent',
                                color: statusFilter === 'certified' ? '#34D399' : 'var(--text-secondary)',
                                cursor: 'pointer',
                                transition: 'all 150ms ease'
                            }}
                        >
                            Verdad Legal (Certificado)
                        </button>
                        <button
                            onClick={() => setStatusFilter('uncertified')}
                            style={{
                                padding: '0.35rem 0.75rem',
                                borderRadius: 'var(--radius-sm)',
                                fontSize: '0.82rem',
                                fontWeight: 600,
                                border: statusFilter === 'uncertified' ? '1px solid var(--accent-amber)' : '1px solid transparent',
                                background: statusFilter === 'uncertified' ? 'var(--accent-amber-subtle)' : 'transparent',
                                color: statusFilter === 'uncertified' ? '#FBBF24' : 'var(--text-secondary)',
                                cursor: 'pointer',
                                transition: 'all 150ms ease'
                            }}
                        >
                            Provisorio (Al Día)
                        </button>
                    </div>
                </div>
            )}

            {/* FILTER PANEL */}
            <div className="panel-surface" style={{ padding: '1rem 1.25rem', marginBottom: '1.5rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--brand-indigo-light)', fontWeight: 600, fontSize: '0.9rem', minWidth: '160px' }}>
                        <Filter size={16} />
                        <span>Filtros de Análisis</span>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap', flex: 1 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                            <span style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', fontWeight: 500 }}>
                                <Calendar size={14} style={{ display: 'inline', marginRight: '3px', verticalAlign: '-2px' }} /> Desde:
                            </span>
                            <input
                                type="date"
                                value={startDate}
                                onChange={(e) => setStartDate(e.target.value)}
                                className="input-field"
                                style={{ padding: '0.35rem 0.65rem', fontSize: '0.85rem', width: 'auto' }}
                            />
                        </div>

                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                            <span style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', fontWeight: 500 }}>
                                <Calendar size={14} style={{ display: 'inline', marginRight: '3px', verticalAlign: '-2px' }} /> Hasta:
                            </span>
                            <input
                                type="date"
                                value={endDate}
                                onChange={(e) => setEndDate(e.target.value)}
                                className="input-field"
                                style={{ padding: '0.35rem 0.65rem', fontSize: '0.85rem', width: 'auto' }}
                            />
                        </div>

                        {availableExchanges.length > 0 && (
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', marginLeft: 'auto', flexWrap: 'wrap' }}>
                                <span style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', fontWeight: 500 }}>Exchanges:</span>
                                {availableExchanges.filter(e => e.toLowerCase().includes('binance')).length > 1 && (
                                    <button
                                        type="button"
                                        onClick={() => {
                                            const binanceExs = availableExchanges.filter(e => e.toLowerCase().includes('binance'));
                                            const allBinSelected = binanceExs.every(e => selectedExchanges.includes(e));
                                            binanceExs.forEach(b => {
                                                if (allBinSelected && selectedExchanges.includes(b)) handleToggleExchange(b);
                                                else if (!allBinSelected && !selectedExchanges.includes(b)) handleToggleExchange(b);
                                            });
                                        }}
                                        style={{
                                            padding: '0.2rem 0.5rem',
                                            borderRadius: 'var(--radius-sm)',
                                            border: '1px solid var(--brand-indigo-border)',
                                            background: 'var(--brand-indigo-subtle)',
                                            color: 'var(--brand-indigo-light)',
                                            fontSize: '0.75rem',
                                            fontWeight: 600,
                                            cursor: 'pointer'
                                        }}
                                        title="Alternar selección de todas las cuentas de Binance (Histórico CPN, Spot y P2P)"
                                    >
                                        ⚡ Todo Binance
                                    </button>
                                )}
                                {availableExchanges.map((exch) => {
                                    const isChecked = selectedExchanges.includes(exch);
                                    let displayLabel = exch;
                                    let subBadge = null;
                                    if (exch === 'Binance') {
                                        subBadge = <span style={{ fontSize: '9px', opacity: 0.7, marginLeft: '2px' }}>(CPN)</span>;
                                    } else if (exch === 'Binance P2P') {
                                        subBadge = <span style={{ fontSize: '9px', opacity: 0.7, marginLeft: '2px' }}>(P2P)</span>;
                                    } else if (exch === 'Binance Spot') {
                                        subBadge = <span style={{ fontSize: '9px', opacity: 0.7, marginLeft: '2px' }}>(Spot)</span>;
                                    }

                                    return (
                                        <button
                                            key={exch}
                                            onClick={() => handleToggleExchange(exch)}
                                            style={{
                                                display: 'flex',
                                                alignItems: 'center',
                                                gap: '0.35rem',
                                                padding: '0.3rem 0.65rem',
                                                borderRadius: 'var(--radius-sm)',
                                                border: isChecked ? '1px solid var(--brand-indigo)' : '1px solid var(--border-color)',
                                                background: isChecked ? 'var(--brand-indigo-subtle)' : 'var(--bg-card)',
                                                color: isChecked ? '#FFFFFF' : 'var(--text-secondary)',
                                                fontSize: '0.82rem',
                                                fontWeight: 600,
                                                cursor: 'pointer',
                                                transition: 'all 150ms ease'
                                            }}
                                        >
                                            {isChecked ? <CheckSquare size={13} color="#818CF8" /> : <Square size={13} />}
                                            <span>{displayLabel}</span>
                                            {subBadge}
                                        </button>
                                    );
                                })}
                                <button
                                    onClick={handleSelectAllExchanges}
                                    style={{ background: 'none', border: 'none', color: 'var(--brand-indigo-light)', cursor: 'pointer', fontSize: '0.8rem', textDecoration: 'underline', fontWeight: 600, paddingLeft: '0.3rem' }}
                                >
                                    {selectedExchanges.length === availableExchanges.length ? 'Desmarcar' : 'Todos'}
                                </button>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </>
    );
}

export default DashboardFilters;
