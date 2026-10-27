import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { UploadCloud, FileSpreadsheet, ShieldCheck, Trash2, CheckCircle2, Loader2 } from 'lucide-react';

export function HomeDropzone({
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
    const navigate = useNavigate();
    const [isDragging, setIsDragging] = useState(false);
    const [selectedExchange, setSelectedExchange] = useState('AUTO');

    const handleFileChange = (e) => {
        if (e.target.files && e.target.files.length > 0) {
            addFiles(Array.from(e.target.files));
        }
        e.target.value = '';
    };

    return (
        <div className="card-surface" style={{ padding: '1.75rem', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
            <div>
                {/* MODE TABS */}
                <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.25rem', backgroundColor: 'var(--bg-panel)', padding: '0.25rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
                    <button
                        type="button"
                        style={{
                            flex: 1,
                            padding: '0.55rem 0.75rem',
                            borderRadius: 'var(--radius-sm)',
                            border: 'none',
                            backgroundColor: 'var(--bg-elevated)',
                            color: '#FFFFFF',
                            fontWeight: '600',
                            fontSize: 'var(--text-xs)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            gap: '0.4rem',
                            cursor: 'default',
                            borderLeft: '2px solid var(--brand-indigo)'
                        }}
                    >
                        <UploadCloud size={15} color="var(--brand-indigo-light)" /> Importar Operaciones
                    </button>
                    <button
                        type="button"
                        onClick={() => navigate('/reports')}
                        style={{
                            flex: 1,
                            padding: '0.55rem 0.75rem',
                            borderRadius: 'var(--radius-sm)',
                            border: 'none',
                            backgroundColor: 'transparent',
                            color: 'var(--text-secondary)',
                            fontWeight: '500',
                            fontSize: 'var(--text-xs)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            gap: '0.4rem',
                            cursor: 'pointer',
                            transition: 'color 150ms ease'
                        }}
                        onMouseEnter={(e) => e.currentTarget.style.color = '#FFFFFF'}
                        onMouseLeave={(e) => e.currentTarget.style.color = 'var(--text-secondary)'}
                    >
                        <FileSpreadsheet size={15} /> Generar Reporte Continuo
                    </button>
                </div>

                {/* DROPZONE */}
                <div
                    className="upload-zone-refined"
                    onClick={() => document.getElementById('fileInput')?.click()}
                    onDragOver={(e) => {
                        e.preventDefault();
                        setIsDragging(true);
                    }}
                    onDragLeave={() => setIsDragging(false)}
                    onDrop={(e) => {
                        e.preventDefault();
                        setIsDragging(false);
                        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                            addFiles(Array.from(e.dataTransfer.files));
                        }
                    }}
                    style={{
                        borderColor: isDragging ? 'var(--brand-indigo)' : undefined,
                        backgroundColor: isDragging ? 'var(--brand-indigo-subtle)' : undefined
                    }}
                >
                    <input type="file" id="fileInput" multiple hidden onChange={handleFileChange} accept=".csv, .xlsx, .xls" />
                    <div style={{
                        width: '48px',
                        height: '48px',
                        borderRadius: '50%',
                        backgroundColor: 'var(--bg-elevated)',
                        border: '1px solid var(--border-color)',
                        display: 'inline-flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        marginBottom: '0.85rem',
                        color: 'var(--brand-indigo-light)'
                    }}>
                        <UploadCloud size={24} />
                    </div>
                    <h3 style={{ fontSize: 'var(--text-base)', fontWeight: '600', color: 'var(--text-primary)', margin: '0 0 0.35rem 0' }}>
                        Arrastra tus archivos de reporte aquí
                    </h3>
                    <p style={{ color: 'var(--text-secondary)', fontSize: 'var(--text-xs)', margin: '0 0 0.85rem 0', maxWidth: '380px', marginInline: 'auto', lineHeight: '1.4' }}>
                        Soporta planillas <strong>.xlsx / .csv</strong> exportadas directamente de exchanges o plantillas personalizadas.
                    </p>
                    <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem', fontSize: 'var(--text-2xs)', color: 'var(--brand-indigo-light)', backgroundColor: 'var(--brand-indigo-subtle)', border: '1px solid var(--brand-indigo-border)', padding: '0.2rem 0.6rem', borderRadius: 'var(--radius-full)', fontWeight: '600' }}>
                        <ShieldCheck size={13} /> Detección de duplicados automática por Hash
                    </div>
                </div>
            </div>

            {/* QUEUE OF UPLOADED FILES */}
            {fileList.length > 0 && (
                <div style={{ marginTop: '1.25rem', borderTop: '1px solid var(--border-subtle)', paddingTop: '1rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.6rem' }}>
                        <span style={{ fontSize: 'var(--text-xs)', fontWeight: '600', color: 'var(--text-primary)' }}>
                            Cola de procesamiento ({fileList.length} archivo{fileList.length > 1 ? 's' : ''}):
                        </span>
                        <button
                            onClick={clearFiles}
                            style={{
                                background: 'transparent',
                                border: 'none',
                                color: 'var(--text-muted)',
                                fontSize: 'var(--text-2xs)',
                                cursor: 'pointer',
                                display: 'flex',
                                alignItems: 'center',
                                gap: '0.25rem',
                                padding: '0.2rem 0.4rem',
                                borderRadius: '0.25rem'
                            }}
                            onMouseEnter={(e) => e.currentTarget.style.color = 'var(--accent-rose-light)'}
                            onMouseLeave={(e) => e.currentTarget.style.color = 'var(--text-muted)'}
                        >
                            <Trash2 size={12} /> Limpiar cola
                        </button>
                    </div>

                    <div style={{ maxHeight: '130px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                        {fileList.map((f, i) => (
                            <div
                                key={i}
                                style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'space-between',
                                    padding: '0.45rem 0.75rem',
                                    backgroundColor: 'var(--bg-panel)',
                                    borderRadius: 'var(--radius-sm)',
                                    border: '1px solid var(--border-subtle)',
                                    fontSize: 'var(--text-xs)'
                                }}
                            >
                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', minWidth: 0 }}>
                                    <FileSpreadsheet size={15} color="var(--brand-indigo-light)" style={{ flexShrink: 0 }} />
                                    <span style={{ color: 'var(--text-primary)', fontWeight: '500', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: '240px' }}>
                                        {f.name}
                                    </span>
                                    <span style={{ color: 'var(--text-muted)', fontSize: 'var(--text-2xs)' }}>
                                        ({formatFileSize(f.size)})
                                    </span>
                                </div>
                                <span className="badge badge-indigo" style={{ fontSize: '10.5px' }}>
                                    {selectedExchange !== 'AUTO' ? selectedExchange : detectExchangeHint(f.name)}
                                </span>
                            </div>
                        ))}
                    </div>

                    {/* EXCHANGE DESTINATION SELECTOR */}
                    <div style={{ marginTop: '0.85rem', display: 'flex', alignItems: 'center', gap: '0.5rem', background: 'var(--bg-panel)', padding: '0.45rem 0.65rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
                        <span style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-secondary)', fontWeight: 600, whiteSpace: 'nowrap' }}>
                            Exchange destino:
                        </span>
                        <select
                            value={selectedExchange}
                            onChange={(e) => setSelectedExchange(e.target.value)}
                            className="input-field"
                            style={{ padding: '0.2rem 0.4rem', fontSize: 'var(--text-xs)', flex: 1, backgroundColor: 'var(--bg-card)', color: 'var(--text-primary)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)' }}
                        >
                            <option value="AUTO">🤖 Detección Automática por Firma de Columnas</option>
                            <option value="OKX">OKX (P2P y Spot)</option>
                            <option value="Binance P2P">Binance P2P (C2C)</option>
                            <option value="Binance Spot">Binance Spot</option>
                            <option value="Bitso Alpha">Bitso / Bitso Alpha</option>
                            <option value="Fiwind">Fiwind</option>
                            <option value="Ripio Trade">Ripio Trade</option>
                            <option value="Ripio Classic">Ripio Clásico</option>
                            <option value="Bitget">Bitget</option>
                            <option value="Lemon Cash">Lemon Cash</option>
                            <option value="Planilla Consolidada">Planilla Consolidada Multi-Exchange</option>
                        </select>
                    </div>

                    {/* PROGRESS BAR */}
                    {processing && (
                        <div style={{ marginTop: '1rem', marginBottom: '0.5rem' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 'var(--text-xs)', color: 'var(--brand-indigo-light)', marginBottom: '0.35rem', fontWeight: '600' }}>
                                <span>Importando y calculando lotes FIFO...</span>
                                <span className="mono">{uploadProgress}%</span>
                            </div>
                            <div style={{ width: '100%', height: '6px', backgroundColor: 'var(--bg-panel)', borderRadius: '3px', overflow: 'hidden', border: '1px solid var(--border-subtle)' }}>
                                <div
                                    style={{
                                        width: `${uploadProgress}%`,
                                        height: '100%',
                                        backgroundColor: 'var(--brand-indigo)',
                                        transition: 'width 150ms ease'
                                    }}
                                />
                            </div>
                        </div>
                    )}

                    {/* PROCESS SUBMIT BUTTON */}
                    <button
                        className="btn-primary"
                        style={{ width: '100%', marginTop: '0.85rem', padding: '0.75rem 1rem' }}
                        onClick={() => processFiles(selectedExchange)}
                        disabled={processing}
                    >
                        {processing ? (
                            <>
                                <Loader2 className="spin" size={18} /> Procesando e importando...
                            </>
                        ) : (
                            <>
                                <CheckCircle2 size={18} /> Procesar e Importar Operaciones
                            </>
                        )}
                    </button>
                </div>
            )}

            {/* ERROR MESSAGE BOX */}
            {error && (
                <div style={{
                    marginTop: '1rem',
                    padding: '0.85rem 1rem',
                    borderRadius: 'var(--radius-md)',
                    backgroundColor: 'var(--accent-rose-subtle)',
                    border: '1px solid var(--accent-rose-border)'
                }}>
                    <p style={{ color: 'var(--accent-rose-light)', margin: 0, fontWeight: '600', fontSize: 'var(--text-xs)' }}>
                        {error.msg}
                    </p>
                    {error.type === 'config' && (
                        <div style={{ marginTop: '0.5rem' }}>
                            <p style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-secondary)', margin: '0 0 0.5rem 0' }}>{error.details}</p>
                            <button
                                onClick={() => navigate('/settings')}
                                className="btn-secondary"
                                style={{ fontSize: 'var(--text-2xs)', padding: '0.35rem 0.75rem', borderColor: 'var(--accent-rose-border)', color: 'var(--accent-rose-light)' }}
                            >
                                Configurar Mapeo de Columnas
                            </button>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

export default HomeDropzone;
