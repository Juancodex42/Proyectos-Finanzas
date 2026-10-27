import React from 'react';
import { Layers, CheckCircle, BarChart3 } from 'lucide-react';

/**
 * ReportCharts Component
 * Visual metrics and distribution summary for the selected report filters.
 */
export function ReportCharts({ exchanges = [], selectedExchanges = [] }) {
    const selectedList = exchanges.filter(ex => selectedExchanges.includes(ex.name));

    return (
        <div style={{
            background: 'rgba(15, 23, 42, 0.4)',
            border: '1px solid var(--border-color)',
            borderRadius: '0.75rem',
            padding: '1rem',
            marginBottom: '1rem'
        }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#38bdf8', fontSize: '0.85rem', fontWeight: '700' }}>
                    <BarChart3 size={16} />
                    <span>Resumen de Plataformas Incluidas</span>
                </div>
                <span className="badge badge-slate" style={{ fontSize: '0.75rem' }}>
                    {selectedList.length} seleccionadas
                </span>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '0.5rem' }}>
                {selectedList.map(ex => (
                    <div
                        key={ex.name}
                        style={{
                            background: 'rgba(30, 41, 59, 0.5)',
                            border: '1px solid rgba(255, 255, 255, 0.05)',
                            borderRadius: '0.5rem',
                            padding: '0.5rem 0.75rem',
                            display: 'flex',
                            flexDirection: 'column',
                            gap: '0.2rem'
                        }}
                    >
                        <span style={{ fontSize: '0.8rem', fontWeight: '600', color: '#f8fafc', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                            {ex.name}
                        </span>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.7rem', color: ex.status === 'online' ? '#4ade80' : '#f59e0b' }}>
                            <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: ex.status === 'online' ? '#4ade80' : '#f59e0b' }}></span>
                            <span>{ex.status === 'online' ? 'Sincronizado' : 'Pendiente'}</span>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}

export default ReportCharts;
