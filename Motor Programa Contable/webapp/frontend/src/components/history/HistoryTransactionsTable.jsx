import React from 'react';
import { Filter, ArrowDownLeft, ArrowUpRight, ShieldCheck, Check, Copy, ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from 'lucide-react';

export function HistoryTransactionsTable({
    filteredTxs = [],
    allCount = 0,
    copiedHash,
    copyToClipboard,
    formatCurrency,
    formatCryptoQty,
    currentPage = 1,
    setCurrentPage,
    pageSize = 50,
    setPageSize
}) {
    const isAll = pageSize === 'all' || pageSize === 0;
    const totalPages = isAll ? 1 : Math.max(1, Math.ceil(filteredTxs.length / pageSize));
    const safeCurrentPage = Math.min(Math.max(1, currentPage), totalPages);

    const startIndex = isAll ? 0 : (safeCurrentPage - 1) * pageSize;
    const endIndex = isAll ? filteredTxs.length : Math.min(startIndex + pageSize, filteredTxs.length);
    const paginatedTxs = isAll ? filteredTxs : filteredTxs.slice(startIndex, endIndex);

    return (
        <div>
            {/* Dense Accounting Table with Sticky Header */}
            <div className="sticky-table-container">
                <table className="table-ledger">
                    <thead>
                        <tr>
                            <th style={{ width: '135px' }}>Fecha & Hora</th>
                            <th style={{ width: '110px' }}>Exchange</th>
                            <th style={{ width: '90px' }}>Tipo</th>
                            <th style={{ width: '80px' }}>Moneda</th>
                            <th style={{ textAlign: 'right', width: '130px' }}>Cantidad</th>
                            <th style={{ textAlign: 'right', width: '150px' }}>Monto (ARS)</th>
                            <th style={{ width: '150px' }}>Hash / Referencia</th>
                            <th style={{ textAlign: 'center', width: '140px' }}>Capa Legal</th>
                        </tr>
                    </thead>
                    <tbody>
                        {filteredTxs.length === 0 ? (
                            <tr>
                                <td colSpan={8} style={{ padding: '3.5rem 1rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                                    <Filter size={32} style={{ margin: '0 auto 0.75rem', opacity: 0.5 }} />
                                    <div style={{ fontSize: '0.95rem', color: 'var(--text-primary)', fontWeight: 600 }}>
                                        No se encontraron transacciones
                                    </div>
                                    <div style={{ fontSize: '0.82rem', marginTop: '0.25rem' }}>
                                        Probá ajustando los filtros de búsqueda, exchange o capa de certificación.
                                    </div>
                                </td>
                            </tr>
                        ) : (
                            paginatedTxs.map((t, idx) => {
                                const isCert = t.is_certified === 1;
                                const fecha = t.fecha || t.Fecha || '-';
                                const exchange = t.exchange || t.Exchange || '-';
                                const tipo = t.tipo_operacion || t['Tipo de Operación'] || '-';
                                const moneda = t.moneda || t.Moneda || '-';
                                const montoArs = t.monto_ars ?? t['Monto ARS'] ?? 0;
                                const mCripto = Number(t['Monto Compra (Cripto)']) || Number(t['Monto Venta (Cripto)']) || Number(t.monto_compra_cripto) || Number(t.monto_venta_cripto) || Number(t.cantidad) || Number(t.Cantidad) || 0;
                                const txHash = String(t.tx_hash || t.hash || t.id || '');
                                const shortHash = txHash.length > 10 ? `${txHash.slice(0, 6)}...${txHash.slice(-4)}` : txHash;
                                const tipoLower = String(tipo).toLowerCase();
                                const isBuy = tipoLower.includes('compra') || tipoLower.includes('buy') || tipoLower.includes('ingreso') || tipoLower.includes('depósito') || tipoLower.includes('deposito');
                                const isCopied = copiedHash === `hash-${startIndex + idx}`;

                                return (
                                    <tr
                                        key={startIndex + idx}
                                        style={{
                                            backgroundColor: isCert ? 'rgba(16, 185, 129, 0.02)' : 'transparent'
                                        }}
                                    >
                                        <td style={{ whiteSpace: 'nowrap', fontWeight: 500, color: 'var(--text-primary)' }} className="font-mono">
                                            {fecha}
                                        </td>
                                        <td>
                                            <span className="badge badge-indigo" style={{ fontSize: '0.72rem' }}>
                                                {exchange}
                                            </span>
                                        </td>
                                        <td>
                                            <span
                                                className={isBuy ? 'badge badge-emerald badge-compra' : 'badge badge-rose badge-venta'}
                                                style={{ fontSize: '0.72rem' }}
                                            >
                                                {isBuy ? <ArrowDownLeft size={11} /> : <ArrowUpRight size={11} />}
                                                {tipo}
                                            </span>
                                        </td>
                                        <td>
                                            <span style={{ fontWeight: 700, color: '#F1F5F9' }}>
                                                {moneda}
                                            </span>
                                        </td>
                                        <td style={{ textAlign: 'right', fontWeight: 600, color: 'var(--text-secondary)' }} className="font-mono">
                                            {formatCryptoQty(mCripto)}
                                        </td>
                                        <td style={{ textAlign: 'right', fontWeight: 700, color: '#F8FAFC' }} className="font-mono">
                                            {formatCurrency(montoArs)}
                                        </td>
                                        <td>
                                            <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
                                                <span
                                                    className="font-mono"
                                                    style={{
                                                        fontSize: '0.75rem',
                                                        color: 'var(--text-muted)',
                                                        background: 'rgba(255, 255, 255, 0.04)',
                                                        padding: '0.15rem 0.4rem',
                                                        borderRadius: 'var(--radius-sm)',
                                                        border: '1px solid var(--border-subtle)'
                                                    }}
                                                    title={txHash}
                                                >
                                                    {shortHash}
                                                </span>
                                                <button
                                                    className="btn-copy"
                                                    onClick={() => copyToClipboard(txHash, `hash-${startIndex + idx}`)}
                                                    title="Copiar Hash / Identificador completo"
                                                >
                                                    {isCopied ? <Check size={12} color="#34D399" /> : <Copy size={12} />}
                                                </button>
                                            </div>
                                        </td>
                                        <td style={{ textAlign: 'center' }}>
                                            <div style={{ display: 'inline-flex', flexDirection: 'column', alignItems: 'center', gap: '0.25rem' }}>
                                                {isCert ? (
                                                    <span className="badge badge-emerald" style={{ fontSize: '0.72rem' }}>
                                                        <ShieldCheck size={12} /> Certificado C.P.N.
                                                    </span>
                                                ) : (
                                                    <span className="badge badge-amber" style={{ fontSize: '0.72rem' }}>
                                                        Provisorio (API/CSV)
                                                    </span>
                                                )}
                                                {(t.requires_cost_audit === 1 || t['requires_cost_audit'] === 1) && (
                                                    <span className="badge badge-rose" style={{ fontSize: '0.68rem', backgroundColor: 'rgba(239, 68, 68, 0.15)', color: '#F87171', border: '1px solid rgba(239, 68, 68, 0.3)' }} title="Requiere auditar costo de adquisición">
                                                        ⚠️ Auditar Costo
                                                    </span>
                                                )}
                                            </div>
                                        </td>
                                    </tr>
                                );
                            })
                        )}
                    </tbody>
                </table>
            </div>

            {/* Table Footer with Pagination Controls */}
            <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                flexWrap: 'wrap',
                gap: '1rem',
                marginTop: '1rem',
                padding: '0.75rem 1rem',
                background: 'rgba(15, 23, 42, 0.6)',
                borderRadius: '8px',
                border: '1px solid var(--border-subtle, rgba(255,255,255,0.08))',
                fontSize: '0.85rem',
                color: 'var(--text-secondary, #94a3b8)'
            }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem' }}>
                    <span>
                        Mostrando <strong>{filteredTxs.length > 0 ? startIndex + 1 : 0}</strong> - <strong>{endIndex}</strong> de <strong>{filteredTxs.length}</strong> operaciones
                        {filteredTxs.length !== allCount && ` (filtradas de ${allCount})`}
                    </span>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                        <span style={{ fontSize: '0.8rem' }}>Filas:</span>
                        <select
                            value={pageSize}
                            onChange={(e) => {
                                const val = e.target.value === 'all' ? 'all' : Number(e.target.value);
                                if (setPageSize) setPageSize(val);
                                if (setCurrentPage) setCurrentPage(1);
                            }}
                            style={{
                                background: '#0F172A',
                                color: '#F8FAFC',
                                border: '1px solid rgba(255,255,255,0.15)',
                                borderRadius: '4px',
                                padding: '0.2rem 0.5rem',
                                fontSize: '0.8rem',
                                cursor: 'pointer'
                            }}
                        >
                            <option value={50}>50</option>
                            <option value={100}>100</option>
                            <option value={250}>250</option>
                            <option value={500}>500</option>
                            <option value="all">Todas</option>
                        </select>
                    </div>
                </div>

                {!isAll && totalPages > 1 && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                        <button
                            className="btn-secondary"
                            style={{ padding: '0.35rem 0.6rem', display: 'flex', alignItems: 'center', cursor: safeCurrentPage <= 1 ? 'not-allowed' : 'pointer', opacity: safeCurrentPage <= 1 ? 0.5 : 1 }}
                            disabled={safeCurrentPage <= 1}
                            onClick={() => setCurrentPage && setCurrentPage(1)}
                            title="Primera página"
                        >
                            <ChevronsLeft size={14} />
                        </button>
                        <button
                            className="btn-secondary"
                            style={{ padding: '0.35rem 0.6rem', display: 'flex', alignItems: 'center', cursor: safeCurrentPage <= 1 ? 'not-allowed' : 'pointer', opacity: safeCurrentPage <= 1 ? 0.5 : 1 }}
                            disabled={safeCurrentPage <= 1}
                            onClick={() => setCurrentPage && setCurrentPage(prev => Math.max(prev - 1, 1))}
                            title="Página anterior"
                        >
                            <ChevronLeft size={14} />
                        </button>

                        <span style={{ margin: '0 0.5rem', fontWeight: 600, color: '#F8FAFC' }}>
                            Página {safeCurrentPage} de {totalPages}
                        </span>

                        <button
                            className="btn-secondary"
                            style={{ padding: '0.35rem 0.6rem', display: 'flex', alignItems: 'center', cursor: safeCurrentPage >= totalPages ? 'not-allowed' : 'pointer', opacity: safeCurrentPage >= totalPages ? 0.5 : 1 }}
                            disabled={safeCurrentPage >= totalPages}
                            onClick={() => setCurrentPage && setCurrentPage(prev => Math.min(prev + 1, totalPages))}
                            title="Página siguiente"
                        >
                            <ChevronRight size={14} />
                        </button>
                        <button
                            className="btn-secondary"
                            style={{ padding: '0.35rem 0.6rem', display: 'flex', alignItems: 'center', cursor: safeCurrentPage >= totalPages ? 'not-allowed' : 'pointer', opacity: safeCurrentPage >= totalPages ? 0.5 : 1 }}
                            disabled={safeCurrentPage >= totalPages}
                            onClick={() => setCurrentPage && setCurrentPage(totalPages)}
                            title="Última página"
                        >
                            <ChevronsRight size={14} />
                        </button>
                    </div>
                )}
            </div>
        </div>
    );
}

export default HistoryTransactionsTable;
