import React from 'react';
import { Layers, CheckCircle } from 'lucide-react';
import TaxReportTable from './TaxReportTable';

/**
 * ReportMappingModal Component
 * Modal for confirming report generation and validating column mappings.
 */
export function ReportMappingModal({
    show,
    onClose,
    mappingPreviewData,
    activeTabIdx,
    setActiveTabIdx,
    dateRange,
    uploadingFile,
    handleModalFileUpload,
    confirmAndDownload,
    downloading,
    formatDateDisplay,
    checkIsStale
}) {
    if (!show) return null;

    const current = mappingPreviewData[activeTabIdx];
    const isStale = current && (current.isStale || (dateRange.end && current.lastUpdate !== '-' && checkIsStale(current.lastUpdate, dateRange.end)));
    const isManualNoData = current && !current.isApi && current.transactionCount === 0;

    return (
        <div style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(15, 23, 42, 0.75)',
            backdropFilter: 'blur(8px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 9999,
            padding: '1.5rem'
        }}>
            <div className="glass-card" style={{
                width: '100%',
                maxWidth: '750px',
                maxHeight: '90vh',
                display: 'flex',
                flexDirection: 'column',
                background: 'rgba(30, 41, 59, 0.95)',
                border: '1px solid rgba(56, 189, 248, 0.25)',
                boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.3), 0 10px 10px -5px rgba(0, 0, 0, 0.2)',
                borderRadius: '1rem',
                overflow: 'hidden'
            }}>
                {/* Header */}
                <div style={{
                    padding: '1.25rem 1.5rem',
                    borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    gap: '1rem'
                }}>
                    <div>
                        <h3 style={{ margin: 0, fontSize: '1.2rem', fontWeight: '800', color: '#38bdf8' }}>
                            Confirmación de Reporte y Mapeo de Columnas
                        </h3>
                        <p style={{ margin: '0.2rem 0 0 0', fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                            Verifica cómo se relacionan las columnas antes de generar el Excel contable.
                        </p>
                    </div>

                    <div style={{
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'flex-end',
                        justifyContent: 'center',
                        background: 'rgba(15, 23, 42, 0.6)',
                        border: '1px solid rgba(56, 189, 248, 0.3)',
                        borderRadius: '0.5rem',
                        padding: '0.4rem 0.85rem',
                        fontSize: '0.8rem',
                        boxShadow: '0 2px 4px rgba(0,0,0,0.2)',
                        flexShrink: 0
                    }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                            <span style={{ color: 'var(--text-secondary)', fontWeight: '600' }}>Desde:</span>
                            <span style={{ color: '#38bdf8', fontWeight: 'bold' }}>
                                {dateRange.start ? formatDateDisplay(dateRange.start) : 'Inicio Histórico'}
                            </span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginTop: '0.15rem' }}>
                            <span style={{ color: 'var(--text-secondary)', fontWeight: '600' }}>Hasta:</span>
                            <span style={{ color: '#38bdf8', fontWeight: 'bold' }}>
                                {dateRange.end ? formatDateDisplay(dateRange.end) : 'Fecha Actual'}
                            </span>
                        </div>
                    </div>
                </div>

                {/* Tabs */}
                <div style={{
                    display: 'flex',
                    background: 'rgba(15, 23, 42, 0.4)',
                    borderBottom: '1px solid rgba(255, 255, 255, 0.05)',
                    padding: '0.5rem 1rem 0 1rem',
                    gap: '0.4rem',
                    overflowX: 'auto'
                }}>
                    {mappingPreviewData.map((item, idx) => {
                        const isActive = activeTabIdx === idx;
                        const itemStale = item.isStale || (dateRange.end && item.lastUpdate !== '-' && checkIsStale(item.lastUpdate, dateRange.end));
                        const statusColor = item.isReady
                            ? '#4ade80'
                            : itemStale
                                ? '#f59e0b'
                                : (!item.isApi && item.transactionCount === 0)
                                    ? '#f59e0b'
                                    : '#ef4444';
                        return (
                            <button
                                key={item.id}
                                onClick={() => setActiveTabIdx(idx)}
                                style={{
                                    padding: '0.6rem 1.1rem',
                                    background: isActive ? 'var(--card-bg)' : 'transparent',
                                    border: '1px solid ' + (isActive ? 'rgba(56, 189, 248, 0.2)' : 'transparent'),
                                    borderBottom: '1px solid ' + (isActive ? 'rgba(30, 41, 59, 0.95)' : 'transparent'),
                                    borderTopLeftRadius: '0.5rem',
                                    borderTopRightRadius: '0.5rem',
                                    color: isActive ? '#f8fafc' : 'var(--text-secondary)',
                                    fontWeight: '700',
                                    fontSize: '0.85rem',
                                    cursor: 'pointer',
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '0.5rem',
                                    whiteSpace: 'nowrap',
                                    marginBottom: '-1px',
                                    transition: 'all 0.2s'
                                }}
                            >
                                <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: statusColor }}></span>
                                {item.name}
                                {itemStale && <span style={{ fontSize: '0.7rem', background: 'rgba(245, 158, 11, 0.2)', color: '#f59e0b', padding: '0.1rem 0.4rem', borderRadius: '0.25rem', fontWeight: 'bold' }}>VIEJO</span>}
                            </button>
                        );
                    })}
                </div>

                {/* Tab Content */}
                <div style={{ padding: '1.5rem', flex: 1, overflowY: 'auto' }}>
                    {current && (
                        <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                                <div>
                                    <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                                        Origen de datos
                                    </span>
                                    <h4 style={{ margin: '0.15rem 0 0 0', fontSize: '1rem', color: '#f8fafc' }}>
                                        {current.isApi
                                            ? `🔌 Conexión API integrada (Estado: ${current.status?.toUpperCase()})`
                                            : `📁 Planilla de importación CSV / Manual (${current.transactionCount || 0} ops detectadas)`
                                        }
                                    </h4>
                                </div>
                                <div style={{ textAlign: 'right' }}>
                                    <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', fontWeight: '600', textTransform: 'uppercase' }}>
                                        Última sincronización
                                    </span>
                                    <p style={{ margin: '0.15rem 0 0 0', fontSize: '0.9rem', color: isStale ? '#f59e0b' : '#38bdf8', fontWeight: 'bold' }}>
                                        {formatDateDisplay(current.lastUpdate)} {isStale && '(Desactualizado)'}
                                    </p>
                                </div>
                            </div>

                            {isManualNoData ? (
                                <div
                                    style={{
                                        border: '2px dashed ' + (uploadingFile === current.id ? 'var(--accent-cyan)' : '#f59e0b'),
                                        borderRadius: '0.75rem',
                                        padding: '2.5rem 1.5rem',
                                        background: uploadingFile === current.id ? 'rgba(6, 182, 212, 0.04)' : 'rgba(245, 158, 11, 0.03)',
                                        textAlign: 'center',
                                        cursor: 'pointer',
                                        display: 'flex',
                                        flexDirection: 'column',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        flex: 1
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
                                    <Layers size={40} color="#f59e0b" style={{ marginBottom: '0.75rem', animation: uploadingFile === current.id ? 'spin 1.5s linear infinite' : 'none' }} />
                                    <h4 style={{ margin: '0 0 0.4rem 0', color: '#f8fafc', fontSize: '1rem', fontWeight: 'bold' }}>
                                        {uploadingFile === current.id ? "Procesando planilla..." : "Sin transacciones suficientes en este periodo"}
                                    </h4>
                                    <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', maxWidth: '440px', margin: 0, lineHeight: '1.4' }}>
                                        No hay registros de {current.name} para cubrir el periodo. Arrastra aquí la planilla contable correspondiente.
                                    </p>
                                </div>
                            ) : current.isApi ? (
                                <div style={{ background: 'rgba(15, 23, 42, 0.5)', border: '1px solid var(--border-color)', borderRadius: '0.75rem', padding: '2rem 1.5rem', textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', flex: 1 }}>
                                    <CheckCircle size={44} color="#4ade80" style={{ marginBottom: '0.75rem' }} />
                                    <h4 style={{ margin: '0 0 0.4rem 0', color: '#f8fafc', fontSize: '1.05rem', fontWeight: 'bold' }}>
                                        Integración API Lista y Sincronizada
                                    </h4>
                                    <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', maxWidth: '480px', margin: 0, lineHeight: '1.4' }}>
                                        Las columnas de esta plataforma se importan automáticamente a través de la API en tiempo real.
                                    </p>
                                </div>
                            ) : (
                                <TaxReportTable
                                    current={current}
                                    dateRange={dateRange}
                                    uploadingFile={uploadingFile}
                                    handleModalFileUpload={handleModalFileUpload}
                                    isStale={isStale}
                                    formatDateDisplay={formatDateDisplay}
                                />
                            )}
                        </div>
                    )}
                </div>

                {/* Footer */}
                <div style={{ padding: '1.25rem 1.5rem', borderTop: '1px solid rgba(255, 255, 255, 0.08)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'rgba(15, 23, 42, 0.2)' }}>
                    <button
                        onClick={onClose}
                        style={{
                            background: 'transparent',
                            border: '1px solid var(--border-color)',
                            color: 'var(--text-secondary)',
                            padding: '0.6rem 1.2rem',
                            borderRadius: '0.5rem',
                            fontSize: '0.85rem',
                            cursor: 'pointer',
                            fontWeight: '600'
                        }}
                    >
                        Cancelar
                    </button>

                    <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
                        <button
                            onClick={() => setActiveTabIdx(prev => Math.max(0, prev - 1))}
                            disabled={activeTabIdx === 0}
                            style={{
                                background: 'rgba(30, 41, 59, 0.6)',
                                border: '1px solid var(--border-color)',
                                color: activeTabIdx === 0 ? 'rgba(255,255,255,0.2)' : 'var(--text-primary)',
                                padding: '0.6rem 1rem',
                                borderRadius: '0.5rem',
                                fontSize: '0.85rem',
                                cursor: activeTabIdx === 0 ? 'not-allowed' : 'pointer',
                                fontWeight: '600'
                            }}
                        >
                            ◄ Anterior
                        </button>

                        {activeTabIdx < mappingPreviewData.length - 1 ? (
                            <button
                                onClick={() => setActiveTabIdx(prev => Math.min(mappingPreviewData.length - 1, prev + 1))}
                                style={{
                                    background: 'rgba(30, 41, 59, 0.6)',
                                    border: '1px solid var(--border-color)',
                                    color: 'var(--text-primary)',
                                    padding: '0.6rem 1rem',
                                    borderRadius: '0.5rem',
                                    fontSize: '0.85rem',
                                    cursor: 'pointer',
                                    fontWeight: '600'
                                }}
                            >
                                Siguiente ➔
                            </button>
                        ) : (
                            <button
                                onClick={confirmAndDownload}
                                disabled={downloading}
                                className="btn-primary"
                                style={{
                                    padding: '0.6rem 1.4rem',
                                    borderRadius: '0.5rem',
                                    fontSize: '0.85rem',
                                    cursor: downloading ? 'not-allowed' : 'pointer',
                                    fontWeight: '600',
                                    opacity: downloading ? 0.5 : 1
                                }}
                            >
                                Confirmar y Descargar
                            </button>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}

export default ReportMappingModal;
