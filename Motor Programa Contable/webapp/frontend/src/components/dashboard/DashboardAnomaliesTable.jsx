import React from 'react';
import { ShieldAlert, Loader2 } from 'lucide-react';
import { ORIGIN_OPTIONS } from './dashboardConstants';

const getAnomalyKey = (item, idx) => item?.id || `${item?.exchange || ''}_${item?.crypto || ''}_${item?.date || idx}`;

export function DashboardAnomaliesTable({
    anomalies = [],
    selectedOrigins = {},
    setSelectedOrigins,
    classifying = {},
    handleClassifyAnomaly
}) {
    if (!anomalies || anomalies.length === 0) return null;

    return (
        <div style={{
            marginBottom: '1.75rem',
            background: 'var(--bg-card)',
            border: '1px solid var(--accent-rose-border)',
            borderRadius: 'var(--radius-lg)',
            overflow: 'hidden',
            boxShadow: 'var(--shadow-md)'
        }}>
            <div style={{
                padding: '1rem 1.25rem',
                background: 'rgba(244, 63, 94, 0.08)',
                borderBottom: '1px solid var(--accent-rose-border)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                flexWrap: 'wrap',
                gap: '0.75rem'
            }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                    <ShieldAlert color="#FB7185" size={20} />
                    <div>
                        <h3 style={{ color: '#FB7185', margin: 0, fontSize: '1rem', fontWeight: 700 }}>
                            Conciliación de Fondos sin Origen Registrado ({anomalies.length})
                        </h3>
                        <p style={{ fontSize: '0.82rem', color: '#CBD5E1', margin: '0.15rem 0 0 0' }}>
                            Ventas registradas sin compra previa vinculada. Clasifica el origen para garantizar la trazabilidad legal:
                        </p>
                    </div>
                </div>
                <span className="badge badge-rose">
                    Acción Requerida
                </span>
            </div>

            <div style={{ overflowX: 'auto' }}>
                <table className="table-ledger">
                    <thead>
                        <tr>
                            <th>Fecha</th>
                            <th>Exchange</th>
                            <th>Activo</th>
                            <th>Faltante a Justificar</th>
                            <th>Procedencia Declarada</th>
                            <th style={{ textAlign: 'right' }}>Acción</th>
                        </tr>
                    </thead>
                    <tbody>
                        {anomalies.map((a, idx) => {
                            const key = getAnomalyKey(a, idx);
                            return (
                                <tr key={key}>
                                    <td style={{ color: 'var(--text-secondary)', fontWeight: 500 }}>{a.date}</td>
                                    <td style={{ fontWeight: 600, color: '#F8FAFC' }}>{a.exchange}</td>
                                    <td>
                                        <span className="badge badge-slate">{a.crypto}</span>
                                    </td>
                                    <td>
                                        <span style={{ color: '#FB7185', fontWeight: 700 }} className="tabular-nums">
                                            {a.missing} {a.crypto}
                                        </span>
                                    </td>
                                    <td>
                                        <select
                                            value={selectedOrigins[key] || ORIGIN_OPTIONS[0]}
                                            onChange={(e) => setSelectedOrigins(prev => ({ ...prev, [key]: e.target.value }))}
                                            className="input-field"
                                            style={{ padding: '0.35rem 0.65rem', fontSize: '0.82rem', width: 'auto', minWidth: '220px' }}
                                        >
                                            {ORIGIN_OPTIONS.map((opt, i) => (
                                                <option key={i} value={opt}>{opt}</option>
                                            ))}
                                        </select>
                                    </td>
                                    <td style={{ textAlign: 'right' }}>
                                        <button
                                            onClick={() => handleClassifyAnomaly(a, idx)}
                                            disabled={Boolean(classifying[key])}
                                            className="btn-primary"
                                            style={{ padding: '0.35rem 0.85rem', fontSize: '0.8rem' }}
                                        >
                                            {classifying[key] ? <Loader2 className="spin" size={14} /> : "Asignar Origen"}
                                        </button>
                                    </td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>
        </div>
    );
}

export default DashboardAnomaliesTable;
