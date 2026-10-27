import React from 'react';
import { Sliders, Calendar, ShieldCheck } from 'lucide-react';

export const DEFAULT_MAPPING_FIELDS = [
    { key: 'fecha', label: 'Fecha y Hora de Operación' },
    { key: 'tipo_operacion', label: 'Tipo de Operación (BUY / SELL / SWAP)' },
    { key: 'moneda', label: 'Moneda / Criptoactivo (BTC, USDT, etc.)' },
    { key: 'monto_compra_cripto', label: 'Cantidad Comprada (Crypto In)' },
    { key: 'monto_venta_cripto', label: 'Cantidad Vendida (Crypto Out)' },
    { key: 'cotizacion_compra', label: 'Cotización de Compra (ARS/USD)' },
    { key: 'cotizacion_venta', label: 'Cotización de Venta (ARS/USD)' },
    { key: 'monto_ars', label: 'Monto Total Equivalente en ARS' },
    { key: 'comentarios', label: 'Notas / Identificador de Orden' }
];

export function SettingsIntegritySection({
    selectedEx,
    defaultFields = DEFAULT_MAPPING_FIELDS,
    handleUpdateDateFormat,
    handleUpdateMappingField
}) {
    if (!selectedEx) return null;

    return (
        <>
            {/* Mapping Info & Integrity Banner */}
            <div style={{
                background: 'rgba(79, 70, 229, 0.08)',
                border: '1px solid rgba(79, 70, 229, 0.2)',
                padding: '0.85rem 1rem',
                borderRadius: '8px',
                marginBottom: '1.5rem',
                display: 'flex',
                gap: '0.75rem',
                alignItems: 'center',
                justifyContent: 'space-between',
                flexWrap: 'wrap'
            }}>
                <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
                    <Sliders color="#818CF8" size={18} style={{ flexShrink: 0 }} />
                    <p style={{ fontSize: '13px', color: '#94A3B8', margin: 0 }}>
                        <strong>Mapeo de Columnas e Integridad:</strong> Vincula cada variable del motor contable con el encabezado de columna literal de los extractos descargados de {selectedEx.name}.
                    </p>
                </div>
                <span className="badge badge-emerald" style={{ fontSize: '11px', display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
                    <ShieldCheck size={13} /> Deduplicación SHA-256 Activa
                </span>
            </div>

            {/* Date Format Card */}
            <div style={{
                marginBottom: '1.75rem',
                background: '#090D14',
                border: '1px solid rgba(255,255,255,0.06)',
                borderRadius: '8px',
                padding: '1rem 1.25rem'
            }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '1rem', alignItems: 'center' }}>
                    <div>
                        <div style={{ color: '#F8FAFC', fontWeight: 600, fontSize: '13px', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                            <Calendar size={14} color="#818CF8" /> Formato de Fecha (STRFTIME)
                        </div>
                        <p style={{ fontSize: '11px', color: '#64748B', margin: '0.2rem 0 0 0' }}>
                            Ej: %d/%m/%Y %H:%M:%S (Día/Mes/Año)
                        </p>
                    </div>
                    <input
                        key={`df-${selectedEx.id}`}
                        type="text"
                        className="input-field"
                        defaultValue={selectedEx.dateFormat || '%d/%m/%Y %H:%M:%S'}
                        onBlur={(e) => handleUpdateDateFormat(e.target.value)}
                        style={{ width: '100%', boxSizing: 'border-box' }}
                    />
                </div>
            </div>

            {/* Field Mappings Table */}
            <div style={{ overflowX: 'auto' }}>
                <table className="table-ledger" style={{ width: '100%' }}>
                    <thead>
                        <tr>
                            <th style={{ width: '50%' }}>Variable Interna del Sub-Ledger</th>
                            <th style={{ width: '50%' }}>Nombre de Columna en CSV / Excel</th>
                        </tr>
                    </thead>
                    <tbody>
                        {defaultFields.map(f => (
                            <tr key={f.key}>
                                <td style={{ verticalAlign: 'middle' }}>
                                    <div style={{ color: '#F8FAFC', fontWeight: 600, fontSize: '13px' }}>{f.label}</div>
                                    <div style={{ color: '#64748B', fontSize: '11px', fontFamily: 'monospace' }}>{f.key}</div>
                                </td>
                                <td style={{ verticalAlign: 'middle' }}>
                                    <input
                                        key={`${selectedEx.id}-${f.key}`}
                                        type="text"
                                        className="input-field"
                                        defaultValue={selectedEx.mapping ? (selectedEx.mapping[f.key] || '') : ''}
                                        onBlur={(e) => handleUpdateMappingField(f.key, e.target.value)}
                                        placeholder={`Columna en extracto de ${selectedEx.name}`}
                                        style={{ width: '100%', boxSizing: 'border-box', fontSize: '12px' }}
                                    />
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </>
    );
}

export default SettingsIntegritySection;
