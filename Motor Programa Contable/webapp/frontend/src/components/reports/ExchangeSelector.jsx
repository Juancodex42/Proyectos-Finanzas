import React from 'react';
import { CheckSquare, Square, Clock, AlertTriangle } from 'lucide-react';

/**
 * ExchangeSelector Component
 * Column 1 of Reports page: allows selecting one, several, or all exchanges.
 */
export function ExchangeSelector({
    exchanges,
    selectedExchanges,
    toggleSelection,
    selectAllExchanges,
    deselectAllExchanges,
    formatDateDisplay
}) {
    return (
        <div className="glass-card" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', borderRadius: '1rem', height: '100%', overflow: 'hidden' }}>
            <h3 style={{ fontSize: '1.25rem', fontWeight: '700', margin: '0 0 0.25rem 0', color: '#f8fafc' }}>
                1. Seleccionar Exchanges
            </h3>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', margin: '0 0 1rem 0' }}>
                Elige las plataformas que quieres incluir en el reporte.
            </p>

            <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '1rem' }}>
                <button
                    onClick={selectAllExchanges}
                    style={{ flex: 1, padding: '0.5rem', background: 'rgba(56, 189, 248, 0.1)', border: '1px solid rgba(56, 189, 248, 0.2)', color: '#38bdf8', borderRadius: '0.375rem', fontSize: '0.85rem', fontWeight: '600', cursor: 'pointer' }}
                >
                    Seleccionar Todos
                </button>
                <button
                    onClick={deselectAllExchanges}
                    style={{ flex: 1, padding: '0.5rem', background: 'rgba(30, 41, 59, 0.6)', border: '1px solid var(--border-color)', color: 'var(--text-secondary)', borderRadius: '0.375rem', fontSize: '0.85rem', fontWeight: '600', cursor: 'pointer' }}
                >
                    Limpiar Selección
                </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', overflowY: 'auto', flex: 1, paddingRight: '0.25rem' }}>
                {exchanges.map(ex => {
                    const isSelected = selectedExchanges.includes(ex.name);
                    const hasError = ['expired', 'offline'].includes(ex.status);
                    return (
                        <div
                            key={ex.name}
                            style={{
                                padding: '1rem',
                                borderRadius: '0.75rem',
                                border: isSelected ? '2px solid var(--accent-cyan)' : '1px solid var(--border-color)',
                                background: isSelected ? 'rgba(6,182,212,0.05)' : 'rgba(30, 41, 59, 0.4)',
                                cursor: 'pointer',
                                display: 'flex',
                                justifyContent: 'space-between',
                                alignItems: 'center',
                                transition: 'all 0.2s',
                                opacity: hasError && !isSelected ? 0.7 : 1
                            }}
                            onClick={() => toggleSelection(ex.name)}
                        >
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                                {isSelected ? (
                                    <CheckSquare size={18} color="var(--accent-cyan)" />
                                ) : (
                                    <Square size={18} color="var(--text-secondary)" />
                                )}
                                <div>
                                    <h4 style={{ margin: 0, fontSize: '0.95rem', fontWeight: '700', color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                                        {ex.name} {hasError && <AlertTriangle size={14} color="#ef4444" title={ex.msg || "Error de conexión"} />}
                                    </h4>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--text-secondary)', fontSize: '0.75rem', marginTop: '0.2rem' }}>
                                        <Clock size={12} />
                                        <span>Act: {formatDateDisplay(ex.lastUpdate)}</span>
                                    </div>
                                </div>
                            </div>

                            <span style={{
                                fontSize: '0.7rem',
                                padding: '0.15rem 0.5rem',
                                borderRadius: '1rem',
                                background: ex.status === 'online' ? 'rgba(74, 222, 128, 0.15)' : (ex.status === 'unconfigured' || ex.status === 'loading') ? 'rgba(245, 158, 11, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                                color: ex.status === 'online' ? '#4ade80' : (ex.status === 'unconfigured' || ex.status === 'loading') ? '#f59e0b' : '#ef4444',
                                fontWeight: '600'
                            }}>
                                {ex.status === 'online' ? 'ONLINE' : ex.status === 'expired' ? 'VENCIDA' : ex.status === 'unconfigured' ? 'SIN KEYS' : ex.status === 'loading' ? '...' : 'OFFLINE'}
                            </span>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

export default ExchangeSelector;
