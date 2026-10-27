import React from 'react';
import { CheckCircle, Layers } from 'lucide-react';

/**
 * TaxReportTable Component
 * Renders the table of mapped accounting fields vs detected columns,
 * plus file update dropzone banner if file needs refreshing.
 */
export function TaxReportTable({
    current,
    uploadingFile,
    handleModalFileUpload,
    isStale
}) {
    if (!current) return null;

    return (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {/* Compact Dropzone to allow updating CSV even if existing data exists */}
            <div
                style={{
                    border: '2px dashed ' + (uploadingFile === current.id ? 'var(--accent-cyan)' : isStale ? '#f59e0b' : 'rgba(56, 189, 248, 0.3)'),
                    borderRadius: '0.5rem',
                    padding: '0.85rem 1rem',
                    background: uploadingFile === current.id ? 'rgba(6, 182, 212, 0.08)' : isStale ? 'rgba(245, 158, 11, 0.05)' : 'rgba(30, 41, 59, 0.4)',
                    textAlign: 'center',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '0.75rem',
                    transition: 'all 0.2s'
                }}
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                    e.preventDefault();
                    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                        handleModalFileUpload(current.id, e.dataTransfer.files);
                    }
                }}
                onClick={() => document.getElementById(`modal-file-input-${current.id}`)?.click()}
            >
                <input
                    type="file"
                    id={`modal-file-input-${current.id}`}
                    multiple
                    hidden
                    onChange={(e) => {
                        if (e.target.files && e.target.files.length > 0) {
                            handleModalFileUpload(current.id, e.target.files);
                        }
                    }}
                />
                <Layers
                    size={20}
                    color={isStale ? '#f59e0b' : '#38bdf8'}
                    style={{ animation: uploadingFile === current.id ? 'spin 1.5s linear infinite' : 'none' }}
                />
                <span style={{ fontSize: '0.85rem', color: '#f8fafc', fontWeight: '600' }}>
                    {uploadingFile === current.id
                        ? "Procesando nueva planilla..."
                        : isStale
                            ? `📥 Arrastra aquí o haz clic para cargar un CSV actualizado para ${current.name}`
                            : `📥 ¿Deseas actualizar los datos? Arrastra un nuevo CSV para ${current.name}`
                    }
                </span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', background: 'rgba(6, 182, 212, 0.08)', border: '1px solid rgba(6, 182, 212, 0.2)', padding: '0.75rem 1rem', borderRadius: '0.5rem' }}>
                <CheckCircle size={16} color="#4ade80" />
                <span style={{ fontSize: '0.78rem', color: '#cbd5e1', fontWeight: '500' }}>
                    Columnas validadas. Se detectaron {current.transactionCount || 0} registros en la base de datos para este periodo.
                </span>
            </div>

            <div style={{ overflowX: 'auto', background: 'rgba(0,0,0,0.2)', borderRadius: '0.5rem', border: '1px solid var(--border-color)' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
                    <thead>
                        <tr style={{ background: 'rgba(0, 0, 0, 0.3)', borderBottom: '1px solid var(--border-color)' }}>
                            <th style={{ padding: '0.65rem 1rem', textAlign: 'left', color: 'var(--text-secondary)', fontWeight: '600' }}>PLANTILLA CONTABLE (IDEAL)</th>
                            <th style={{ padding: '0.65rem 1rem', textAlign: 'left', color: 'var(--text-secondary)', fontWeight: '600' }}>COLUMNA DETECTADA</th>
                        </tr>
                    </thead>
                    <tbody>
                        {current.mapping && Object.entries(current.mapping).map(([field, colName]) => {
                            const cleanField = field.charAt(0).toUpperCase() + field.slice(1).replace('_', ' ');
                            return (
                                <tr key={field} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                                    <td style={{ padding: '0.65rem 1rem', color: '#f1f5f9', fontWeight: '600' }}>{cleanField}</td>
                                    <td style={{ padding: '0.65rem 1rem', color: '#cbd5e1' }}>
                                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
                                            <span style={{ display: 'inline-block', width: '6px', height: '6px', borderRadius: '50%', background: '#4ade80' }}></span>
                                            {colName || "N/A"}
                                        </span>
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

export default TaxReportTable;
