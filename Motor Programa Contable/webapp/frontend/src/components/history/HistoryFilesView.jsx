import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { FileText, Download, Trash2, RefreshCw, UploadCloud, Layers, Globe, FileSpreadsheet, ChevronDown, ChevronUp, Landmark, CheckCircle2, AlertCircle } from 'lucide-react';
import HomeDropzone from '../home/HomeDropzone';

export function HistoryFilesView({
    history = [],
    fileHistory = [],
    historySubMode = 'exchanges',
    setHistorySubMode,
    downloadOriginal,
    deleteExchangeBatch,
    deleteFileBatch,
    downloadingFile,
    deletingBatch,
    fileList = [],
    addFiles,
    clearFiles,
    processing,
    uploadProgress,
    processFiles,
    error,
    formatFileSize,
    detectExchangeHint
}) {
    const [showUploadZone, setShowUploadZone] = useState(false);

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            {/* TOP BAR: UPLOAD ACCORDION TOGGLE & SUB-MODE SELECTOR */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem', backgroundColor: 'var(--bg-card)', padding: '0.85rem 1.25rem', borderRadius: 'var(--radius-lg)', border: '1px solid var(--border-color)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <button
                        type="button"
                        onClick={() => setShowUploadZone(prev => !prev)}
                        className="btn-primary"
                        style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', fontSize: '0.82rem', padding: '0.45rem 0.9rem' }}
                    >
                        <UploadCloud size={15} />
                        <span>{showUploadZone ? 'Ocultar Subida de Archivos' : 'Subir Nuevos Archivos Aquí'}</span>
                        {showUploadZone ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                    </button>
                    {fileList.length > 0 && !showUploadZone && (
                        <span className="badge badge-indigo" style={{ fontSize: '0.75rem' }}>
                            {fileList.length} archivo(s) listo(s) para procesar
                        </span>
                    )}
                </div>

                {/* SUBMODE SWITCHER: EXCHANGES VS DISCRETE FILES VS BANKS */}
                <div style={{
                    display: 'inline-flex',
                    background: '#0D131F',
                    padding: '0.2rem',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--border-color)'
                }}>
                    <button
                        type="button"
                        onClick={() => setHistorySubMode('exchanges')}
                        style={{
                            padding: '0.35rem 0.8rem',
                            borderRadius: 'var(--radius-sm)',
                            border: 'none',
                            background: historySubMode === 'exchanges' ? 'var(--brand-indigo)' : 'transparent',
                            color: historySubMode === 'exchanges' ? '#FFFFFF' : 'var(--text-secondary)',
                            fontWeight: 600,
                            fontSize: '0.78rem',
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '0.35rem',
                            transition: 'all 150ms ease'
                        }}
                    >
                        <Layers size={13} /> Por Exchange
                    </button>
                    <button
                        type="button"
                        onClick={() => setHistorySubMode('files')}
                        style={{
                            padding: '0.35rem 0.8rem',
                            borderRadius: 'var(--radius-sm)',
                            border: 'none',
                            background: historySubMode === 'files' ? 'var(--brand-indigo)' : 'transparent',
                            color: historySubMode === 'files' ? '#FFFFFF' : 'var(--text-secondary)',
                            fontWeight: 600,
                            fontSize: '0.78rem',
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '0.35rem',
                            transition: 'all 150ms ease'
                        }}
                    >
                        <FileSpreadsheet size={13} /> Archivos Subidos ({fileHistory.length})
                    </button>
                    <button
                        type="button"
                        onClick={() => setHistorySubMode('banks')}
                        style={{
                            padding: '0.35rem 0.8rem',
                            borderRadius: 'var(--radius-sm)',
                            border: 'none',
                            background: historySubMode === 'banks' ? 'var(--brand-indigo)' : 'transparent',
                            color: historySubMode === 'banks' ? '#FFFFFF' : 'var(--text-secondary)',
                            fontWeight: 600,
                            fontSize: '0.78rem',
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '0.35rem',
                            transition: 'all 150ms ease'
                        }}
                    >
                        <Landmark size={13} /> Bancos & Fintechs
                    </button>
                </div>
            </div>

            {/* COLLAPSIBLE DROPZONE EMBEDDED IN HISTORY */}
            <AnimatePresence>
                {showUploadZone && (
                    <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        exit={{ opacity: 0, height: 0 }}
                        transition={{ duration: 0.2 }}
                    >
                        <HomeDropzone
                            fileList={fileList}
                            addFiles={addFiles}
                            clearFiles={clearFiles}
                            processing={processing}
                            uploadProgress={uploadProgress}
                            processFiles={processFiles}
                            error={error}
                            formatFileSize={formatFileSize}
                            detectExchangeHint={detectExchangeHint}
                        />
                    </motion.div>
                )}
            </AnimatePresence>

            {/* VIEW 1: EXCHANGES VIEW WITH API VS FILE RANGES */}
            {historySubMode === 'exchanges' && (
                history.length === 0 ? (
                    <div className="card-surface" style={{ padding: '3.5rem 1.5rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                        <FileText size={42} style={{ margin: '0 auto 1rem', opacity: 0.6, color: 'var(--brand-indigo-light)' }} />
                        <h3 style={{ fontSize: '1.15rem', color: 'var(--text-primary)', margin: '0 0 0.5rem' }}>No hay registros consolidados</h3>
                        <p style={{ fontSize: '0.88rem', margin: '0 0 1.25rem' }}>Usa el botón de arriba para importar planillas o sincroniza tus claves API.</p>
                    </div>
                ) : (
                    <div className="sticky-table-container">
                        <table className="table-ledger">
                            <thead>
                                <tr>
                                    <th>Exchange</th>
                                    <th style={{ textAlign: 'center' }}>Total Transacciones</th>
                                    <th style={{ textAlign: 'center' }}>Rango Vía API</th>
                                    <th style={{ textAlign: 'center' }}>Rango Vía Archivos</th>
                                    <th style={{ textAlign: 'right' }}>Rango Global Cubierto</th>
                                    <th style={{ textAlign: 'center', width: '220px' }}>Acciones</th>
                                </tr>
                            </thead>
                            <tbody>
                                {history.map((item, idx) => (
                                    <motion.tr
                                        key={idx}
                                        initial={{ opacity: 0, y: 6 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        transition={{ delay: idx * 0.03 }}
                                    >
                                        <td>
                                            <span className="badge badge-indigo" style={{ fontSize: '0.82rem', fontWeight: 700 }}>
                                                {item.exchange}
                                            </span>
                                        </td>
                                        <td style={{ textAlign: 'center', fontWeight: 700 }} className="font-mono">
                                            {item.count}
                                        </td>
                                        <td style={{ textAlign: 'center', fontSize: '0.78rem' }}>
                                            {item.api_count > 0 ? (
                                                <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem', color: '#34D399', background: 'rgba(52, 211, 153, 0.1)', padding: '0.15rem 0.5rem', borderRadius: '4px' }}>
                                                    <Globe size={11} />
                                                    <span className="font-mono">{item.api_range}</span>
                                                    <span style={{ fontSize: '0.7rem', opacity: 0.8 }}>({item.api_count})</span>
                                                </div>
                                            ) : (
                                                <span style={{ color: 'var(--text-muted)' }}>-</span>
                                            )}
                                        </td>
                                        <td style={{ textAlign: 'center', fontSize: '0.78rem' }}>
                                            {item.file_count > 0 ? (
                                                <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem', color: '#818CF8', background: 'rgba(129, 140, 248, 0.1)', padding: '0.15rem 0.5rem', borderRadius: '4px' }}>
                                                    <FileSpreadsheet size={11} />
                                                    <span className="font-mono">{item.file_range}</span>
                                                    <span style={{ fontSize: '0.7rem', opacity: 0.8 }}>({item.file_count})</span>
                                                </div>
                                            ) : (
                                                <span style={{ color: 'var(--text-muted)' }}>-</span>
                                            )}
                                        </td>
                                        <td style={{ textAlign: 'right', fontSize: '0.82rem', color: 'var(--text-secondary)' }} className="font-mono">
                                            {item.date_range}
                                        </td>
                                        <td style={{ textAlign: 'center' }}>
                                            <div style={{ display: 'inline-flex', gap: '0.5rem' }}>
                                                <button
                                                    className="btn-secondary"
                                                    style={{ padding: '0.35rem 0.75rem', fontSize: '0.75rem' }}
                                                    onClick={() => downloadOriginal(item.filename)}
                                                    disabled={downloadingFile === item.filename}
                                                >
                                                    {downloadingFile === item.filename ? <RefreshCw size={12} className="spin" /> : <Download size={12} />}
                                                    Descargar
                                                </button>
                                                <button
                                                    style={{
                                                        padding: '0.35rem 0.75rem',
                                                        fontSize: '0.75rem',
                                                        background: 'var(--accent-rose-subtle)',
                                                        color: 'var(--accent-rose-light)',
                                                        border: '1px solid var(--accent-rose-border)',
                                                        borderRadius: 'var(--radius-md)',
                                                        fontWeight: 600,
                                                        cursor: 'pointer',
                                                        display: 'inline-flex',
                                                        alignItems: 'center',
                                                        gap: '0.3rem'
                                                    }}
                                                    onClick={() => deleteExchangeBatch(item.exchange)}
                                                    disabled={deletingBatch === item.exchange}
                                                >
                                                    {deletingBatch === item.exchange ? <RefreshCw size={12} className="spin" /> : <Trash2 size={12} />}
                                                    Eliminar
                                                </button>
                                            </div>
                                        </td>
                                    </motion.tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )
            )}

            {/* VIEW 2: DISCRETE UPLOADED FILES WITH FILE-LEVEL ROLLBACK */}
            {historySubMode === 'files' && (
                fileHistory.length === 0 ? (
                    <div className="card-surface" style={{ padding: '3.5rem 1.5rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                        <FileSpreadsheet size={42} style={{ margin: '0 auto 1rem', opacity: 0.6, color: 'var(--brand-indigo-light)' }} />
                        <h3 style={{ fontSize: '1.15rem', color: 'var(--text-primary)', margin: '0 0 0.5rem' }}>No hay planillas individuales registradas con nombre</h3>
                        <p style={{ fontSize: '0.88rem', margin: '0 0 1.25rem' }}>Los nuevos archivos que importes quedarán catalogados aquí con trazabilidad completa.</p>
                    </div>
                ) : (
                    <div className="sticky-table-container">
                        <table className="table-ledger">
                            <thead>
                                <tr>
                                    <th>Archivo Subido</th>
                                    <th>Exchange</th>
                                    <th style={{ textAlign: 'center' }}>Registros</th>
                                    <th style={{ textAlign: 'right' }}>Rango Cubierto</th>
                                    <th style={{ textAlign: 'center', width: '160px' }}>Acción</th>
                                </tr>
                            </thead>
                            <tbody>
                                {fileHistory.map((item, idx) => (
                                    <motion.tr
                                        key={idx}
                                        initial={{ opacity: 0, y: 6 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        transition={{ delay: idx * 0.03 }}
                                    >
                                        <td style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                                            <FileSpreadsheet size={16} color="var(--brand-indigo-light)" style={{ flexShrink: 0 }} />
                                            <span style={{ wordBreak: 'break-all' }}>{item.filename}</span>
                                        </td>
                                        <td>
                                            <span className="badge badge-indigo" style={{ fontSize: '0.72rem' }}>
                                                {item.exchange}
                                            </span>
                                        </td>
                                        <td style={{ textAlign: 'center', fontWeight: 700 }} className="font-mono">
                                            {item.count}
                                        </td>
                                        <td style={{ textAlign: 'right', fontSize: '0.82rem', color: 'var(--text-secondary)' }} className="font-mono">
                                            {item.date_range}
                                        </td>
                                        <td style={{ textAlign: 'center' }}>
                                            <button
                                                style={{
                                                    padding: '0.35rem 0.75rem',
                                                    fontSize: '0.75rem',
                                                    background: 'var(--accent-rose-subtle)',
                                                    color: 'var(--accent-rose-light)',
                                                    border: '1px solid var(--accent-rose-border)',
                                                    borderRadius: 'var(--radius-md)',
                                                    fontWeight: 600,
                                                    cursor: 'pointer',
                                                    display: 'inline-flex',
                                                    alignItems: 'center',
                                                    gap: '0.3rem'
                                                }}
                                                onClick={() => deleteFileBatch(item.filename)}
                                                disabled={deletingBatch === item.filename}
                                            >
                                                {deletingBatch === item.filename ? <RefreshCw size={12} className="spin" /> : <Trash2 size={12} />}
                                                Revertir Archivo
                                            </button>
                                        </td>
                                    </motion.tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )
            )}

            {/* VIEW 3: BANCOS & FINTECHS CONCILIATION */}
            {historySubMode === 'banks' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                    <div style={{
                        backgroundColor: 'var(--bg-card)',
                        padding: '1.5rem',
                        borderRadius: 'var(--radius-lg)',
                        border: '1px solid var(--border-color)',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '1rem'
                    }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                                <div style={{
                                    width: '36px',
                                    height: '36px',
                                    borderRadius: 'var(--radius-md)',
                                    background: 'rgba(6, 182, 212, 0.1)',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    border: '1px solid rgba(6, 182, 212, 0.3)'
                                }}>
                                    <Landmark size={18} color="var(--accent-cyan)" />
                                </div>
                                <div>
                                    <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 700, color: '#F8FAFC' }}>
                                        Bandeja de Conciliación Bancaria y Cuentas Fiat
                                    </h3>
                                    <p style={{ margin: '0.2rem 0 0 0', fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                                        Cruce de extractos (Mercado Pago, Lemon Cash, Galicia) contra órdenes P2P para el Libro Operativo.
                                    </p>
                                </div>
                            </div>
                            <span className="badge badge-emerald" style={{ fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                                <CheckCircle2 size={13} /> Algoritmo 4 Capas Activo
                            </span>
                        </div>

                        {/* Cards de Cuentas */}
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '1rem', marginTop: '0.5rem' }}>
                            <div style={{ background: '#0D131F', padding: '1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                                    <span style={{ fontWeight: 700, color: '#F8FAFC', fontSize: '0.9rem' }}>Mercado Pago</span>
                                    <span className="badge badge-indigo" style={{ fontSize: '0.7rem' }}>CVU Principal</span>
                                </div>
                                <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', margin: 0 }}>
                                    Cobros/pagos P2P, fondeos y compras cotidianas. Macheo determinístico por monto exacto y horario.
                                </p>
                            </div>
                            <div style={{ background: '#0D131F', padding: '1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                                    <span style={{ fontWeight: 700, color: '#F8FAFC', fontSize: '0.9rem' }}>Lemon Cash</span>
                                    <span className="badge badge-cyan" style={{ fontSize: '0.7rem' }}>Puente / Fondeo</span>
                                </div>
                                <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', margin: 0 }}>
                                    Cuenta puente de acreditación rápida. Los giros hacia MP (mismo CUIT) se neutralizan a efecto neto $0.
                                </p>
                            </div>
                            <div style={{ background: '#0D131F', padding: '1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                                    <span style={{ fontWeight: 700, color: '#F8FAFC', fontSize: '0.9rem' }}>Bancos Tradicionales</span>
                                    <span className="badge badge-amber" style={{ fontSize: '0.7rem' }}>Galicia / Santander</span>
                                </div>
                                <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', margin: 0 }}>
                                    Préstamos recibidos de terceros e inyecciones externas de capital personal.
                                </p>
                            </div>
                        </div>

                        {/* Banner explicativo de cómo subir */}
                        <div style={{
                            padding: '0.85rem 1rem',
                            borderRadius: 'var(--radius-md)',
                            background: 'rgba(79, 70, 229, 0.08)',
                            border: '1px solid rgba(79, 70, 229, 0.25)',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '0.75rem'
                        }}>
                            <AlertCircle size={18} color="var(--brand-indigo-light)" style={{ flexShrink: 0 }} />
                            <p style={{ margin: 0, fontSize: '0.82rem', color: 'var(--text-primary)', lineHeight: '1.4' }}>
                                Para incorporar tus movimientos bancarios, hacé clic arriba en <strong>"Subir Nuevos Archivos Aquí"</strong> y arrastrá el extracto en CSV o Excel de tu banco. El sistema clasificará automáticamente el 95% de las filas.
                            </p>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

export default HistoryFilesView;
