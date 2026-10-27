import React from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { FileSpreadsheet, RefreshCw, Download, AlertTriangle, ArrowRight, Filter } from 'lucide-react';

export function HomeImportResults({
    results,
    setResults,
    clearFiles,
    downloadExcel,
    selectedExchanges,
    setSelectedExchanges
}) {
    const navigate = useNavigate();

    if (!results) return null;

    return (
        <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            style={{ flex: 1, display: 'flex', flexDirection: 'column' }}
        >
            {/* RESULTS TOOLBAR */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', paddingBottom: '0.85rem', borderBottom: '1px solid var(--border-subtle)' }}>
                <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                        <h2 style={{ fontSize: '1.35rem', margin: 0, color: 'var(--text-primary)', fontWeight: '700' }}>
                            Resultado de la Importación
                        </h2>
                        <span className="badge badge-emerald">
                            {results.total_transactions} operaciones procesadas
                        </span>
                    </div>
                    <p style={{ color: 'var(--text-secondary)', fontSize: 'var(--text-xs)', margin: '0.2rem 0 0 0' }}>
                        Transacciones normalizadas e incorporadas a la base contable para cálculo FIFO.
                    </p>
                </div>

                <div style={{ display: 'flex', gap: '0.75rem' }}>
                    <button
                        className="btn-secondary"
                        style={{ fontSize: 'var(--text-xs)', padding: '0.55rem 1rem' }}
                        onClick={() => { setResults(null); clearFiles(); }}
                    >
                        <RefreshCw size={14} /> Cargar Nuevos Archivos
                    </button>
                    <button
                        className="btn-primary"
                        style={{ fontSize: 'var(--text-xs)', padding: '0.55rem 1.15rem' }}
                        onClick={downloadExcel}
                    >
                        <Download size={15} /> Descargar Certificación Excel
                    </button>
                </div>
            </div>

            {/* WARNINGS IN RESULTS */}
            {results.warnings && results.warnings.length > 0 && (
                <div style={{
                    backgroundColor: 'var(--accent-amber-subtle)',
                    border: '1px solid var(--accent-amber-border)',
                    borderRadius: 'var(--radius-md)',
                    padding: '0.85rem 1.25rem',
                    marginBottom: '1.25rem',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: '1rem',
                    flexWrap: 'wrap'
                }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                        <AlertTriangle size={18} color="var(--accent-amber-light)" style={{ flexShrink: 0 }} />
                        <div>
                            <span style={{ fontSize: 'var(--text-sm)', color: 'var(--accent-amber-light)', fontWeight: '700', display: 'block' }}>
                                Se detectaron {results.warnings.length} hueco(s) FIFO en el balance acumulado
                            </span>
                            <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
                                Algunas ventas no tienen lote de adquisición previo coincidente. Puedes conciliar en el módulo Calendario.
                            </span>
                        </div>
                    </div>
                    <button
                        className="btn-secondary"
                        style={{
                            borderColor: 'var(--accent-amber-border)',
                            color: 'var(--accent-amber-light)',
                            backgroundColor: 'rgba(245, 158, 11, 0.12)',
                            fontSize: 'var(--text-xs)',
                            padding: '0.45rem 0.85rem'
                        }}
                        onClick={() => {
                            const targetYear = (results?.warnings?.[0]?.date && String(results.warnings[0].date).slice(0, 4))
                                || (results?.files?.[0]?.processed_sample?.[0]?.Date && String(results.files[0].processed_sample[0].Date).slice(0, 4))
                                || '';
                            navigate(targetYear ? `/calendar?tab=warnings&year=${targetYear}` : '/calendar?tab=warnings');
                        }}
                    >
                        Resolver en Calendario <ArrowRight size={14} />
                    </button>
                </div>
            )}

            {/* PROCESSED FILES CARDS */}
            <div style={{ display: 'grid', gap: '1.25rem', flex: 1 }}>
                {results.files && results.files.map((file, idx) => {
                    const getTxExchange = tx => {
                        const ex = (tx.Exchange || tx.exchange || '').toString().trim();
                        if (!ex || ex.toLowerCase() === 'nan' || ex.toLowerCase() === 'none' || ex.toLowerCase() === 'null') {
                            return 'Otros';
                        }
                        return ex;
                    };
                    const uniqueExchanges = file.processed_sample
                        ? Array.from(new Set(file.processed_sample.map(getTxExchange)))
                        : [];
                    const currentFilter = selectedExchanges[idx] || 'ALL';
                    const displaySample = file.processed_sample
                        ? (currentFilter === 'ALL'
                            ? file.processed_sample
                            : file.processed_sample.filter(tx => getTxExchange(tx) === currentFilter))
                        : [];

                    return (
                        <div key={idx} className="card-surface" style={{ padding: '1.25rem' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                    <FileSpreadsheet size={18} color="var(--brand-indigo-light)" />
                                    <h3 style={{ fontSize: 'var(--text-sm)', margin: 0, color: 'var(--text-primary)', fontWeight: '700' }}>
                                        {file.filename}
                                    </h3>
                                </div>
                                <div style={{ display: 'flex', gap: '0.45rem' }}>
                                    <span className="badge badge-indigo">{file.count} Ops Detectadas</span>
                                    {file.inserted > 0 && <span className="badge badge-emerald">+{file.inserted} Nuevas</span>}
                                    {file.skipped > 0 && <span className="badge badge-amber">{file.skipped} Duplicadas</span>}
                                </div>
                            </div>

                            {/* DUAL COMPARISON GRID */}
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                                {/* ORIGINAL RAW PREVIEW */}
                                <div style={{ backgroundColor: 'var(--bg-panel)', padding: '0.85rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)', overflow: 'hidden' }}>
                                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.6rem' }}>
                                        <h5 style={{ color: 'var(--text-secondary)', fontSize: 'var(--text-xs)', margin: 0, textTransform: 'uppercase', letterSpacing: '0.04em', fontWeight: '600' }}>
                                            Estructura Original (Extracto)
                                        </h5>
                                        <span style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>
                                            Muestra {file.raw_sample ? file.raw_sample.length : 0} filas
                                        </span>
                                    </div>
                                    <div style={{ overflowX: 'auto', maxHeight: '280px' }}>
                                        {file.raw_sample && file.raw_sample.length > 0 ? (
                                            <table className="table-ledger" style={{ whiteSpace: 'nowrap', fontSize: 'var(--text-xs)' }}>
                                                <thead>
                                                    <tr>
                                                        {Object.keys(file.raw_sample[0]).map((key) => (
                                                            <th key={key} style={{ padding: '0.45rem 0.65rem' }}>{key}</th>
                                                        ))}
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    {file.raw_sample.map((row, rIdx) => (
                                                        <tr key={rIdx}>
                                                            {Object.values(row).map((val, cIdx) => (
                                                                <td key={cIdx} style={{ padding: '0.4rem 0.65rem', color: 'var(--text-secondary)' }}>
                                                                    {String(val).substring(0, 32)}{String(val).length > 32 ? '...' : ''}
                                                                </td>
                                                            ))}
                                                        </tr>
                                                    ))}
                                                </tbody>
                                            </table>
                                        ) : (
                                            <p style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', margin: 0, padding: '1rem' }}>
                                                Sin datos en la muestra original
                                            </p>
                                        )}
                                    </div>
                                </div>

                                {/* PROCESSED SUB-LEDGER VIEW */}
                                <div style={{ backgroundColor: 'var(--bg-panel)', padding: '0.85rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)', overflow: 'hidden' }}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.6rem', flexWrap: 'wrap', gap: '0.4rem' }}>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                                            <h5 style={{ color: 'var(--brand-indigo-light)', fontSize: 'var(--text-xs)', margin: 0, textTransform: 'uppercase', letterSpacing: '0.04em', fontWeight: '700' }}>
                                                Normalizado (Base Contable)
                                            </h5>
                                        </div>

                                        {uniqueExchanges.length > 0 && (
                                            <div style={{ display: 'flex', gap: '0.3rem', alignItems: 'center', flexWrap: 'wrap' }}>
                                                <Filter size={12} color="var(--text-muted)" />
                                                <button
                                                    onClick={() => setSelectedExchanges(prev => ({ ...prev, [idx]: 'ALL' }))}
                                                    style={{
                                                        padding: '0.15rem 0.5rem',
                                                        fontSize: 'var(--text-2xs)',
                                                        borderRadius: 'var(--radius-sm)',
                                                        border: '1px solid',
                                                        borderColor: currentFilter === 'ALL' ? 'var(--brand-indigo)' : 'var(--border-subtle)',
                                                        cursor: 'pointer',
                                                        backgroundColor: currentFilter === 'ALL' ? 'var(--brand-indigo-subtle)' : 'transparent',
                                                        color: currentFilter === 'ALL' ? 'var(--brand-indigo-light)' : 'var(--text-secondary)',
                                                        fontWeight: '600'
                                                    }}
                                                >
                                                    Todos ({file.count || file.processed_sample?.length})
                                                </button>
                                                {uniqueExchanges.map(ex => {
                                                    const count = file.exchange_counts ? file.exchange_counts[ex] : file.processed_sample.filter(tx => getTxExchange(tx) === ex).length;
                                                    const isActive = currentFilter === ex;
                                                    return (
                                                        <button
                                                            key={ex}
                                                            onClick={() => setSelectedExchanges(prev => ({ ...prev, [idx]: ex }))}
                                                            style={{
                                                                padding: '0.15rem 0.5rem',
                                                                fontSize: 'var(--text-2xs)',
                                                                borderRadius: 'var(--radius-sm)',
                                                                border: '1px solid',
                                                                borderColor: isActive ? 'var(--brand-indigo)' : 'var(--border-subtle)',
                                                                cursor: 'pointer',
                                                                backgroundColor: isActive ? 'var(--brand-indigo-subtle)' : 'transparent',
                                                                color: isActive ? 'var(--brand-indigo-light)' : 'var(--text-secondary)',
                                                                fontWeight: '600'
                                                            }}
                                                        >
                                                            {ex} ({count})
                                                        </button>
                                                    );
                                                })}
                                            </div>
                                        )}
                                    </div>

                                    <div style={{ overflowX: 'auto', maxHeight: '280px' }}>
                                        {displaySample && displaySample.length > 0 ? (
                                            <table className="table-ledger" style={{ whiteSpace: 'nowrap', fontSize: 'var(--text-xs)' }}>
                                                <thead>
                                                    <tr>
                                                        {Object.keys(displaySample[0]).map((key) => (
                                                            <th key={key} style={{ padding: '0.45rem 0.65rem' }}>{key}</th>
                                                        ))}
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    {displaySample.map((tx, i) => (
                                                        <tr key={i}>
                                                            {Object.values(tx).map((val, cIdx) => (
                                                                <td key={cIdx} style={{ padding: '0.4rem 0.65rem', fontWeight: typeof val === 'number' ? '600' : 'normal' }}>
                                                                    {val}
                                                                </td>
                                                            ))}
                                                        </tr>
                                                    ))}
                                                </tbody>
                                            </table>
                                        ) : (
                                            <p style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', margin: 0, padding: '1rem' }}>
                                                No se detectaron operaciones fiscales en la muestra.
                                            </p>
                                        )}
                                    </div>
                                </div>
                            </div>
                        </div>
                    );
                })}
            </div>
        </motion.div>
    );
}

export default HomeImportResults;
