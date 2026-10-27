import React, { useState } from 'react';
import { Scale, Check, Calendar, AlertCircle, Loader2 } from 'lucide-react';

export function CertExcelCrossAuditAlerts({ discrepancies = [], onResolve }) {
    const [resolvingId, setResolvingId] = useState(null);
    const [filterType, setFilterType] = useState('ACTIONABLE'); // 'ACTIONABLE' (date/amount) or 'ALL'

    if (!discrepancies || discrepancies.length === 0) return null;

    // Separate actionable (date or amount discrepancies) from purely informational missing rows
    const actionableItems = discrepancies.filter(
        d => d.type === 'FECHA_DISCREPANTE' || d.type === 'MONTO_DISCREPANTE'
    );
    const displayedItems = filterType === 'ACTIONABLE' && actionableItems.length > 0
        ? actionableItems
        : discrepancies;

    if (displayedItems.length === 0 && discrepancies.length === 0) return null;

    const handleAction = async (item, action, newVal) => {
        if (!onResolve) return;
        setResolvingId(item.id);
        try {
            await onResolve(item.tx_id || item.excel_tx_id, action, newVal);
        } finally {
            setResolvingId(null);
        }
    };

    return (
        <div style={{
            marginBottom: '1.75rem',
            background: 'var(--bg-card)',
            border: '1px solid rgba(168, 85, 247, 0.35)',
            borderRadius: 'var(--radius-lg)',
            overflow: 'hidden',
            boxShadow: 'var(--shadow-md)'
        }}>
            {/* Header */}
            <div style={{
                padding: '1rem 1.25rem',
                background: 'rgba(168, 85, 247, 0.08)',
                borderBottom: '1px solid rgba(168, 85, 247, 0.25)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                flexWrap: 'wrap',
                gap: '0.75rem'
            }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                    <Scale color="#C084FC" size={20} />
                    <div>
                        <h3 style={{ color: '#D8B4FE', margin: 0, fontSize: '1rem', fontWeight: 700 }}>
                            Auditoría Cruzada: Certificaciones C.P.N. vs. Extractos Excel ({discrepancies.length})
                        </h3>
                        <p style={{ fontSize: '0.82rem', color: '#CBD5E1', margin: '0.15rem 0 0 0' }}>
                            Validación de fechas e importes escaneados por OCR contra los archivos digitales originales del exchange:
                        </p>
                    </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    {actionableItems.length > 0 && actionableItems.length !== discrepancies.length && (
                        <div style={{ display: 'flex', gap: '0.25rem', background: 'rgba(15, 23, 42, 0.6)', padding: '0.2rem', borderRadius: 'var(--radius-md)' }}>
                            <button
                                onClick={() => setFilterType('ACTIONABLE')}
                                style={{
                                    border: 'none',
                                    background: filterType === 'ACTIONABLE' ? 'rgba(168, 85, 247, 0.3)' : 'transparent',
                                    color: filterType === 'ACTIONABLE' ? '#F8FAFC' : '#94A3B8',
                                    fontSize: '0.75rem',
                                    padding: '0.25rem 0.5rem',
                                    borderRadius: '4px',
                                    cursor: 'pointer',
                                    fontWeight: 600
                                }}
                            >
                                Discrepancias OCR ({actionableItems.length})
                            </button>
                            <button
                                onClick={() => setFilterType('ALL')}
                                style={{
                                    border: 'none',
                                    background: filterType === 'ALL' ? 'rgba(168, 85, 247, 0.3)' : 'transparent',
                                    color: filterType === 'ALL' ? '#F8FAFC' : '#94A3B8',
                                    fontSize: '0.75rem',
                                    padding: '0.25rem 0.5rem',
                                    borderRadius: '4px',
                                    cursor: 'pointer',
                                    fontWeight: 600
                                }}
                            >
                                Todas ({discrepancies.length})
                            </button>
                        </div>
                    )}
                    <span style={{
                        padding: '0.25rem 0.65rem',
                        borderRadius: '9999px',
                        fontSize: '0.75rem',
                        fontWeight: 700,
                        background: 'rgba(168, 85, 247, 0.2)',
                        color: '#E9D5FF',
                        border: '1px solid rgba(168, 85, 247, 0.4)'
                    }}>
                        Validación Cruzada
                    </span>
                </div>
            </div>

            {/* Table */}
            <div style={{ overflowX: 'auto', maxHeight: '420px', overflowY: 'auto' }}>
                <table className="table-ledger" style={{ width: '100%', borderCollapse: 'collapse' }}>
                    <thead>
                        <tr>
                            <th style={{ padding: '0.75rem 1rem', textAlign: 'left' }}>Tipo</th>
                            <th style={{ padding: '0.75rem 1rem', textAlign: 'left' }}>Exchange / Período</th>
                            <th style={{ padding: '0.75rem 1rem', textAlign: 'left' }}>Activo / Monto</th>
                            <th style={{ padding: '0.75rem 1rem', textAlign: 'left' }}>En Certificación (Papel OCR)</th>
                            <th style={{ padding: '0.75rem 1rem', textAlign: 'left' }}>En Extracto Digital (Excel)</th>
                            <th style={{ padding: '0.75rem 1rem', textAlign: 'right' }}>Acción de Resolución</th>
                        </tr>
                    </thead>
                    <tbody>
                        {displayedItems.slice(0, 50).map((d) => {
                            const isResolving = resolvingId === d.id;
                            const isDateDisc = d.type === 'FECHA_DISCREPANTE';
                            const isAmtDisc = d.type === 'MONTO_DISCREPANTE';

                            return (
                                <tr key={d.id} style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.05)' }}>
                                    <td style={{ padding: '0.75rem 1rem' }}>
                                        {isDateDisc ? (
                                            <span style={{
                                                display: 'inline-flex',
                                                alignItems: 'center',
                                                gap: '0.3rem',
                                                padding: '0.2rem 0.5rem',
                                                borderRadius: '4px',
                                                fontSize: '0.75rem',
                                                fontWeight: 700,
                                                background: 'rgba(234, 179, 8, 0.15)',
                                                color: '#FDE047',
                                                border: '1px solid rgba(234, 179, 8, 0.3)'
                                            }}>
                                                <Calendar size={12} /> Fecha OCR
                                            </span>
                                        ) : isAmtDisc ? (
                                            <span style={{
                                                display: 'inline-flex',
                                                alignItems: 'center',
                                                gap: '0.3rem',
                                                padding: '0.2rem 0.5rem',
                                                borderRadius: '4px',
                                                fontSize: '0.75rem',
                                                fontWeight: 700,
                                                background: 'rgba(244, 63, 94, 0.15)',
                                                color: '#FDA4AF',
                                                border: '1px solid rgba(244, 63, 94, 0.3)'
                                            }}>
                                                <AlertCircle size={12} /> Monto OCR
                                            </span>
                                        ) : (
                                            <span style={{
                                                padding: '0.2rem 0.5rem',
                                                borderRadius: '4px',
                                                fontSize: '0.75rem',
                                                fontWeight: 600,
                                                background: 'rgba(148, 163, 184, 0.15)',
                                                color: '#CBD5E1'
                                            }}>
                                                {d.type.replace(/_/g, ' ')}
                                            </span>
                                        )}
                                    </td>
                                    <td style={{ padding: '0.75rem 1rem' }}>
                                        <div style={{ fontWeight: 600, color: '#F8FAFC' }}>{d.exchange}</div>
                                        <div style={{ fontSize: '0.75rem', color: '#94A3B8' }}>{d.cert_title || ''}</div>
                                    </td>
                                    <td style={{ padding: '0.75rem 1rem' }}>
                                        <span style={{ fontWeight: 700, color: '#E2E8F0' }}>
                                            {d.amount ? `${d.amount} ` : ''}{d.coin}
                                        </span>
                                    </td>
                                    <td style={{ padding: '0.75rem 1rem' }}>
                                        <span style={{ color: isDateDisc || isAmtDisc ? '#FCA5A5' : '#CBD5E1', fontWeight: 600 }}>
                                            {d.cert_value}
                                        </span>
                                    </td>
                                    <td style={{ padding: '0.75rem 1rem' }}>
                                        <span style={{ color: isDateDisc || isAmtDisc ? '#86EFAC' : '#CBD5E1', fontWeight: 600 }}>
                                            {d.excel_value}
                                        </span>
                                    </td>
                                    <td style={{ padding: '0.75rem 1rem', textAlign: 'right' }}>
                                        {isDateDisc ? (
                                            <button
                                                onClick={() => handleAction(d, 'align_with_excel_date', d.excel_value)}
                                                disabled={isResolving}
                                                style={{
                                                    background: 'rgba(168, 85, 247, 0.25)',
                                                    border: '1px solid rgba(168, 85, 247, 0.5)',
                                                    color: '#F3E8FF',
                                                    padding: '0.35rem 0.75rem',
                                                    borderRadius: 'var(--radius-md)',
                                                    fontSize: '0.78rem',
                                                    fontWeight: 600,
                                                    cursor: 'pointer',
                                                    display: 'inline-flex',
                                                    alignItems: 'center',
                                                    gap: '0.35rem'
                                                }}
                                            >
                                                {isResolving ? <Loader2 size={13} className="animate-spin" /> : <Check size={13} />}
                                                Alinear con Excel
                                            </button>
                                        ) : isAmtDisc ? (
                                            <button
                                                onClick={() => handleAction(d, 'align_with_excel_amount', d.excel_value.split(' ')[0])}
                                                disabled={isResolving}
                                                style={{
                                                    background: 'rgba(168, 85, 247, 0.25)',
                                                    border: '1px solid rgba(168, 85, 247, 0.5)',
                                                    color: '#F3E8FF',
                                                    padding: '0.35rem 0.75rem',
                                                    borderRadius: 'var(--radius-md)',
                                                    fontSize: '0.78rem',
                                                    fontWeight: 600,
                                                    cursor: 'pointer',
                                                    display: 'inline-flex',
                                                    alignItems: 'center',
                                                    gap: '0.35rem'
                                                }}
                                            >
                                                {isResolving ? <Loader2 size={13} className="animate-spin" /> : <Check size={13} />}
                                                Alinear Importe
                                            </button>
                                        ) : (
                                            <button
                                                onClick={() => handleAction(d, 'dismiss')}
                                                disabled={isResolving}
                                                style={{
                                                    background: 'transparent',
                                                    border: '1px solid rgba(148, 163, 184, 0.3)',
                                                    color: '#94A3B8',
                                                    padding: '0.3rem 0.65rem',
                                                    borderRadius: 'var(--radius-md)',
                                                    fontSize: '0.75rem',
                                                    cursor: 'pointer'
                                                }}
                                            >
                                                Mantener Dictamen
                                            </button>
                                        )}
                                    </td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>
            {displayedItems.length > 50 && (
                <div style={{ padding: '0.5rem 1.25rem', fontSize: '0.75rem', color: '#94A3B8', background: 'rgba(15, 23, 42, 0.4)', textAlign: 'center' }}>
                    Mostrando las primeras 50 de {displayedItems.length} operaciones. Utiliza los filtros para acotar.
                </div>
            )}
        </div>
    );
}

export default CertExcelCrossAuditAlerts;
