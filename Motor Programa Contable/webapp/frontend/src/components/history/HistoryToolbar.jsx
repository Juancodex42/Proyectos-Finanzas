import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
    Database, RefreshCw, Layers, FileText, AlertTriangle, Sparkles,
    ShieldCheck, Search, X, ArrowDownLeft, ArrowUpRight
} from 'lucide-react';

export const formatFileSize = (bytes) => {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
};

export const detectExchangeHint = (filename) => {
    const lower = (filename || '').toLowerCase();
    if (lower.includes('okx')) return 'OKX';
    if (lower.includes('binance') && lower.includes('p2p')) return 'Binance P2P';
    if (lower.includes('binance')) return 'Binance Spot';
    if (lower.includes('bitso')) return 'Bitso Alpha';
    if (lower.includes('fiwind')) return 'Fiwind';
    if (lower.includes('ripio') && lower.includes('trade')) return 'Ripio Trade';
    if (lower.includes('ripio')) return 'Ripio Classic';
    if (lower.includes('bitget')) return 'Bitget';
    if (lower.includes('lemon')) return 'Lemon Cash';
    if (lower.includes('consolidada') || lower.includes('manual')) return 'Planilla Consolidada';
    return 'Auto-detectar (Firma)';
};

export const formatCurrency = (val) => {
    if (val === undefined || val === null || isNaN(val)) return '$ 0,00';
    return new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(val);
};

export const formatCryptoQty = (qty) => {
    if (qty === undefined || qty === null || qty === '') return '-';
    const strVal = typeof qty === 'string' ? qty.replace(',', '.') : qty;
    const num = parseFloat(strVal);
    return isNaN(num) ? qty : num.toLocaleString('es-AR', { maximumFractionDigits: 8 });
};

export function HistoryToolbar({
    loading, onRefresh, viewMode, setViewMode,
    transactionsCount = 0, historyCount = 0, gaps = [],
    filteredCount = 0, allCount = 0, filteredTotalARS = 0,
    certifiedCount = 0, uncertifiedCount = 0,
    txSearch, setTxSearch, statusFilter, setStatusFilter,
    selectedExchange, setSelectedExchange, availableExchanges = [],
    typeFilter, setTypeFilter
}) {
    const navigate = useNavigate();

    return (
        <>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.75rem', flexWrap: 'wrap', gap: '1rem' }}>
                <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                        <div style={{ width: '36px', height: '36px', borderRadius: 'var(--radius-md)', background: 'var(--brand-indigo-subtle)', display: 'flex', alignItems: 'center', justifyContent: 'center', border: '1px solid var(--brand-indigo-border)' }}>
                            <Database color="var(--brand-indigo-light)" size={18} />
                        </div>
                        <h1 style={{ fontSize: '1.75rem', fontWeight: 800, color: '#F8FAFC', margin: 0, letterSpacing: '-0.02em' }}>
                            Historial & Respaldo Legal de Operaciones
                        </h1>
                    </div>
                    <p style={{ color: 'var(--text-secondary)', margin: '0.35rem 0 0 0', fontSize: '0.88rem', paddingLeft: '2.85rem' }}>
                        Historial contable: transacciones auditadas por Certificación C.P.N. vs operaciones provisorias en vivo.
                    </p>
                </div>
                <button onClick={onRefresh} className="btn-secondary" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.85rem', padding: '0.5rem 0.9rem' }}>
                    <RefreshCw size={14} className={loading ? "spin" : ""} />
                    <span>Actualizar</span>
                </button>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '1.25rem' }}>
                <div style={{ display: 'inline-flex', background: '#0D131F', padding: '0.25rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)', boxShadow: 'var(--shadow-sm)' }}>
                    <button
                        onClick={() => setViewMode('transactions')}
                        style={{ padding: '0.45rem 0.95rem', borderRadius: 'var(--radius-sm)', border: 'none', background: viewMode === 'transactions' ? 'var(--brand-indigo)' : 'transparent', color: viewMode === 'transactions' ? '#FFFFFF' : 'var(--text-secondary)', fontWeight: 600, fontSize: '0.82rem', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.4rem' }}
                    >
                        <Layers size={14} /> Detalle de Transacciones ({transactionsCount})
                    </button>
                    <button
                        onClick={() => setViewMode('files')}
                        style={{ padding: '0.45rem 0.95rem', borderRadius: 'var(--radius-sm)', border: 'none', background: viewMode === 'files' ? 'var(--brand-indigo)' : 'transparent', color: viewMode === 'files' ? '#FFFFFF' : 'var(--text-secondary)', fontWeight: 600, fontSize: '0.82rem', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.4rem' }}
                    >
                        <FileText size={14} /> Archivos por Exchange ({historyCount})
                    </button>
                </div>
            </div>

            {gaps && gaps.length > 0 && (
                <div style={{ background: 'linear-gradient(135deg, rgba(245, 158, 11, 0.12), rgba(217, 119, 6, 0.05))', border: '1px solid var(--accent-amber-border)', borderRadius: 'var(--radius-lg)', padding: '0.9rem 1.25rem', marginBottom: '1.25rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem', boxShadow: 'var(--shadow-sm)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
                        <div style={{ background: 'var(--accent-amber-subtle)', padding: '0.45rem', borderRadius: 'var(--radius-md)', color: 'var(--accent-amber-light)', display: 'flex', alignItems: 'center' }}>
                            <AlertTriangle size={20} />
                        </div>
                        <div>
                            <div style={{ fontSize: '0.92rem', color: '#FDE68A', fontWeight: 700 }}>
                                Se detectaron {gaps.length} faltante(s) de historial (huecos FIFO)
                            </div>
                            <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: '0.15rem' }}>
                                Faltan comprobantes de compra para calcular el costo de adquisición de forma exacta.
                            </div>
                        </div>
                    </div>
                    <button
                        onClick={() => {
                            const targetYear = gaps?.[0]?.date ? String(gaps[0].date).slice(0, 4) : '';
                            navigate(targetYear ? `/calendar?tab=warnings&year=${targetYear}` : '/calendar?tab=warnings');
                        }}
                        style={{ background: 'linear-gradient(135deg, #F59E0B, #D97706)', color: '#FFFFFF', border: 'none', borderRadius: 'var(--radius-md)', padding: '0.5rem 1rem', fontSize: '0.82rem', fontWeight: 600, cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: '0.4rem', whiteSpace: 'nowrap' }}
                    >
                        <Sparkles size={15} /> Resolver en Calendario →
                    </button>
                </div>
            )}

            {viewMode === 'transactions' && (
                <>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem', marginBottom: '1.25rem' }}>
                        <div className="card-surface" style={{ padding: '0.85rem 1.15rem' }}>
                            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>Total Registros</span>
                            <div style={{ fontSize: '1.35rem', fontWeight: 700, color: '#F8FAFC', marginTop: '0.2rem', fontFamily: 'JetBrains Mono, monospace' }}>
                                {filteredCount} <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 400 }}>de {allCount}</span>
                            </div>
                        </div>
                        <div className="card-surface" style={{ padding: '0.85rem 1.15rem' }}>
                            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>Volumen Filtrado (ARS)</span>
                            <div style={{ fontSize: '1.35rem', fontWeight: 700, color: 'var(--brand-indigo-light)', marginTop: '0.2rem', fontFamily: 'JetBrains Mono, monospace' }}>
                                {formatCurrency(filteredTotalARS)}
                            </div>
                        </div>
                        <div className="card-surface" style={{ padding: '0.85rem 1.15rem' }}>
                            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>Auditado vs Provisorio</span>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.35rem' }}>
                                <span className="badge badge-emerald" style={{ fontSize: '0.72rem' }}><ShieldCheck size={12} /> {certifiedCount} C.P.N.</span>
                                <span className="badge badge-amber" style={{ fontSize: '0.72rem' }}>{uncertifiedCount} Provisorias</span>
                            </div>
                        </div>
                    </div>

                    <div className="card-surface" style={{ padding: '1rem 1.25rem', marginBottom: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
                            <div style={{ position: 'relative', flex: 1, minWidth: '260px' }}>
                                <Search size={16} color="var(--text-muted)" style={{ position: 'absolute', left: '0.75rem', top: '50%', transform: 'translateY(-50%)' }} />
                                <input
                                    type="text"
                                    placeholder="Buscar por exchange, criptomoneda (BTC, USDT), hash o fecha..."
                                    value={txSearch}
                                    onChange={(e) => setTxSearch(e.target.value)}
                                    className="input-field"
                                    style={{ paddingLeft: '2.35rem', paddingRight: txSearch ? '2rem' : '0.875rem' }}
                                />
                                {txSearch && (
                                    <button onClick={() => setTxSearch('')} style={{ position: 'absolute', right: '0.6rem', top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', display: 'flex', alignItems: 'center' }} title="Limpiar búsqueda">
                                        <X size={14} />
                                    </button>
                                )}
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', flexWrap: 'wrap' }}>
                                <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', fontWeight: 600, marginRight: '0.2rem' }}>Respaldo:</span>
                                <button onClick={() => setStatusFilter('all')} className={`chip ${statusFilter === 'all' ? 'active' : ''}`}>Todas ({allCount})</button>
                                <button onClick={() => setStatusFilter('certified')} className={`chip ${statusFilter === 'certified' ? 'active-emerald' : ''}`}><ShieldCheck size={13} /> Certificadas ({certifiedCount})</button>
                                <button onClick={() => setStatusFilter('uncertified')} className={`chip ${statusFilter === 'uncertified' ? 'active-amber' : ''}`}>Provisorias ({uncertifiedCount})</button>
                            </div>
                        </div>

                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem', paddingTop: '0.65rem', borderTop: '1px solid var(--border-subtle)' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', flexWrap: 'wrap' }}>
                                <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', fontWeight: 600 }}>Exchange:</span>
                                <button onClick={() => setSelectedExchange('ALL')} className={`chip ${selectedExchange === 'ALL' ? 'active' : ''}`} style={{ fontSize: '0.75rem', padding: '0.25rem 0.65rem' }}>Todos</button>
                                {availableExchanges.map(ex => (
                                    <button key={ex} onClick={() => setSelectedExchange(ex)} className={`chip ${selectedExchange === ex ? 'active' : ''}`} style={{ fontSize: '0.75rem', padding: '0.25rem 0.65rem' }}>{ex}</button>
                                ))}
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                                <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', fontWeight: 600 }}>Tipo:</span>
                                <button onClick={() => setTypeFilter('ALL')} className={`chip ${typeFilter === 'ALL' ? 'active' : ''}`} style={{ fontSize: '0.75rem', padding: '0.25rem 0.65rem' }}>Todos</button>
                                <button onClick={() => setTypeFilter('Compra')} className={`chip ${typeFilter === 'Compra' ? 'active-emerald' : ''}`} style={{ fontSize: '0.75rem', padding: '0.25rem 0.65rem' }}><ArrowDownLeft size={12} /> Compras</button>
                                <button onClick={() => setTypeFilter('Venta')} className={`chip ${typeFilter === 'Venta' ? 'active-amber' : ''}`} style={{ fontSize: '0.75rem', padding: '0.25rem 0.65rem' }}><ArrowUpRight size={12} /> Ventas</button>
                            </div>
                        </div>
                    </div>
                </>
            )}
        </>
    );
}

export default HistoryToolbar;
