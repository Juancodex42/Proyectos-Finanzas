import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Download, RefreshCw, FileSpreadsheet, Layers, AlertTriangle, Info, Sparkles } from 'lucide-react';
import axios from 'axios';
import config from '../../config';
import ReportMappingModal from './ReportMappingModal';
import OperationalExportConfig from './OperationalExportConfig';

export function ReportExporter({
    exportFormat, setExportFormat, selectedExchanges, datesInverted,
    loadingPreview, previewCount, setPreviewCount, gaps, setGaps,
    exchangesWithErrors, staleExchanges, dateRange,
    openMappingModal, showMappingModal, setShowMappingModal,
    mappingPreviewData, setMappingPreviewData, activeTabIdx, setActiveTabIdx,
    formatDateDisplay, checkIsStale
}) {
    const navigate = useNavigate();
    const [downloading, setDownloading] = useState(false);
    const [uploadingFile, setUploadingFile] = useState(null);
    const [localGaps, setLocalGaps] = useState(null);
    const [operationalOptions, setOperationalOptions] = useState({
        existencia_inicial_usd: 0,
        existencia_inicial_ars: 0,
        garantia_total_usdt: 0,
        saldo_bancos_final_ars: 0,
        cotizacion_cierre_usdt: 0
    });

    useEffect(() => {
        setLocalGaps(null);
    }, [gaps]);

    const effectiveGaps = localGaps !== null ? localGaps : gaps;

    const handleModalFileUpload = async (exchangeId, fileOrFiles) => {
        setUploadingFile(exchangeId);
        const formData = new FormData();
        const filesArray = fileOrFiles instanceof FileList || Array.isArray(fileOrFiles)
            ? Array.from(fileOrFiles)
            : [fileOrFiles];

        filesArray.forEach(file => formData.append('files', file));
        if (exchangeId) formData.append('override_exchange', exchangeId);

        try {
            const processRes = await axios.post(`${config.API_URL}/process`, formData);
            const filesList = processRes.data?.files || processRes.data?.results || [];
            if (filesList.length > 0) {
                const totalCount = filesList.reduce((sum, r) => sum + (r.count || 0), 0);
                const hasErr = filesList.some(r => r.error);
                if (hasErr || totalCount === 0) {
                    const errDetail = filesList.find(r => r.error)?.error;
                    alert(errDetail || "No se detectaron transacciones válidas en la planilla cargada.");
                }
            }

            const res = await axios.post(`${config.API_URL}/api/reports/preview-mapping`, {
                exchanges: selectedExchanges, dateStart: dateRange.start, dateEnd: dateRange.end
            });
            setMappingPreviewData(res.data || []);

            const generateRes = await axios.post(`${config.API_URL}/api/reports/batch-generate`, {
                exchanges: selectedExchanges, dateStart: dateRange.start, dateEnd: dateRange.end
            });
            if (setPreviewCount) setPreviewCount(generateRes.data.count);

            const gapYear = dateRange?.start ? dateRange.start.slice(0, 4) : new Date().getFullYear();
            try {
                const gapsRes = await axios.get(`${config.API_URL}/api/reports/gaps?year=${gapYear}&mode=global`);
                const nextGaps = gapsRes?.data?.gaps || [];
                setLocalGaps(nextGaps);
                if (setGaps) setGaps(nextGaps);
            } catch (gapErr) {
                console.warn("Could not refresh gaps after upload:", gapErr);
            }
        } catch (err) {
            console.error("Error uploading file in modal", err);
            const errData = err.response?.data;
            if (errData && errData.error === 'missing_columns') {
                const ex = (errData.exchange || 'el archivo').toUpperCase();
                const missingStr = Array.isArray(errData.missing) ? errData.missing.join(', ') : (errData.missing || 'Encabezados requeridos');
                const availStr = Array.isArray(errData.available) ? errData.available.slice(0, 15).join(', ') : (errData.available || 'Ninguna');
                alert(`Error al procesar (${ex}): Faltan columnas en la planilla.\n\n• Columnas requeridas: ${missingStr}\n• Columnas detectadas: ${availStr}`);
            } else {
                const serverMsg = errData?.error || errData?.message;
                alert(serverMsg ? `Error al procesar: ${serverMsg}` : "Error al cargar y procesar el archivo.");
            }
        } finally {
            setUploadingFile(null);
        }
    };

    const handleBatchDownload = async () => {
        setDownloading(true);
        try {
            const response = await axios.post(`${config.API_URL}/api/reports/batch-download`, {
                exchanges: selectedExchanges,
                dateStart: dateRange.start,
                dateEnd: dateRange.end,
                format: exportFormat,
                options: exportFormat === 'operational' ? operationalOptions : undefined
            }, { responseType: 'blob' });

            const blob = new Blob([response.data]);
            const url = window.URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            const year = dateRange.start ? dateRange.start.substring(0, 4) : "Batch";
            const filename = exportFormat === 'separated'
                ? `Reportes_Separados_${year}.zip`
                : exportFormat === 'operational'
                    ? `Reporte_Operativo_Stock_Caja_${year}.xlsx`
                    : `Reporte_Consolidado_${year}.xlsx`;
            link.setAttribute('download', filename);
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            window.URL.revokeObjectURL(url);
        } catch (err) {
            console.error("Error downloading batch", err);
            let backendError = null;
            if (err.response?.data instanceof Blob) {
                try {
                    const errText = await err.response.data.text();
                    backendError = JSON.parse(errText).error;
                } catch (_) {
                    // Fallback to generic message if blob is not valid JSON
                }
            } else if (err.response?.data?.error) {
                backendError = err.response.data.error;
            }
            alert(backendError ? `Error al descargar el reporte: ${backendError}` : "Error al descargar el reporte consolidado.");
        } finally {
            setDownloading(false);
        }
    };

    const confirmAndDownload = async () => {
        setShowMappingModal(false);
        await handleBatchDownload();
    };

    const isDownloadDisabled = downloading || loadingPreview || !previewCount || previewCount === 0 || selectedExchanges.length === 0 || datesInverted;

    return (
        <div className="glass-card" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', borderRadius: '1rem', height: '100%', overflow: 'hidden', boxSizing: 'border-box' }}>
            <div style={{ flex: 1, overflowY: 'auto', paddingRight: '0.25rem' }}>
                <h3 style={{ fontSize: '1.25rem', fontWeight: '700', margin: '0 0 0.25rem 0', color: '#f8fafc' }}>
                    3. Exportar y Descargar
                </h3>
                <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', margin: '0 0 1rem 0' }}>
                    Elige el formato de salida para presentar al contador.
                </p>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginBottom: '1.5rem' }}>
                    <div
                        onClick={() => setExportFormat('consolidated')}
                        style={{
                            padding: '1.2rem', borderRadius: '0.75rem', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '1rem', transition: 'all 0.2s',
                            border: exportFormat === 'consolidated' ? '2px solid var(--accent-cyan)' : '1px solid var(--border-color)',
                            background: exportFormat === 'consolidated' ? 'rgba(6,182,212,0.05)' : 'rgba(30, 41, 59, 0.3)'
                        }}
                    >
                        <FileSpreadsheet size={28} color={exportFormat === 'consolidated' ? 'var(--accent-cyan)' : 'var(--text-secondary)'} />
                        <div>
                            <h4 style={{ margin: 0, fontSize: '0.98rem', fontWeight: '700', color: '#f8fafc' }}>Libro Consolidado</h4>
                            <p style={{ margin: '0.2rem 0 0 0', fontSize: '0.82rem', color: 'var(--text-secondary)', lineHeight: '1.3' }}>
                                Un único Excel con todas las operaciones unificadas cronológicamente.
                            </p>
                        </div>
                    </div>

                    <div
                        onClick={() => setExportFormat('separated')}
                        style={{
                            padding: '1.2rem', borderRadius: '0.75rem', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '1rem', transition: 'all 0.2s',
                            border: exportFormat === 'separated' ? '2px solid var(--accent-cyan)' : '1px solid var(--border-color)',
                            background: exportFormat === 'separated' ? 'rgba(6,182,212,0.05)' : 'rgba(30, 41, 59, 0.3)'
                        }}
                    >
                        <Layers size={28} color={exportFormat === 'separated' ? 'var(--accent-cyan)' : 'var(--text-secondary)'} />
                        <div>
                            <h4 style={{ margin: 0, fontSize: '0.98rem', fontWeight: '700', color: '#f8fafc' }}>Archivos Separados (ZIP)</h4>
                            <p style={{ margin: '0.2rem 0 0 0', fontSize: '0.82rem', color: 'var(--text-secondary)', lineHeight: '1.3' }}>
                                Genera planillas Excel individuales empaquetadas en un archivo comprimido ZIP.
                            </p>
                        </div>
                    </div>

                    <div
                        onClick={() => setExportFormat('operational')}
                        style={{
                            padding: '1.2rem', borderRadius: '0.75rem', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '1rem', transition: 'all 0.2s',
                            border: exportFormat === 'operational' ? '2px solid var(--accent-cyan)' : '1px solid var(--border-color)',
                            background: exportFormat === 'operational' ? 'rgba(6,182,212,0.05)' : 'rgba(30, 41, 59, 0.3)'
                        }}
                    >
                        <Sparkles size={28} color={exportFormat === 'operational' ? 'var(--accent-cyan)' : 'var(--text-secondary)'} />
                        <div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                <h4 style={{ margin: 0, fontSize: '0.98rem', fontWeight: '700', color: '#f8fafc' }}>Libro Operativo con Stock y Caja</h4>
                                <span className="badge badge-indigo" style={{ fontSize: '0.7rem' }}>Modelo Contador</span>
                            </div>
                            <p style={{ margin: '0.2rem 0 0 0', fontSize: '0.82rem', color: 'var(--text-secondary)', lineHeight: '1.3' }}>
                                Stock USD continuo, flujo bancario ARS, garantías merchant y Ecuación Patrimonial al centavo.
                            </p>
                        </div>
                    </div>
                </div>

                {exportFormat === 'operational' && (
                    <OperationalExportConfig
                        selectedExchanges={selectedExchanges}
                        dateRange={dateRange}
                        operationalOptions={operationalOptions}
                        setOperationalOptions={setOperationalOptions}
                    />
                )}

                {exchangesWithErrors.length > 0 && (
                    <div style={{ background: 'rgba(239, 68, 68, 0.12)', border: '1px solid #ef4444', borderRadius: '0.75rem', padding: '0.85rem 1rem', marginBottom: '1rem', display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                        <span style={{ fontSize: '0.85rem', color: '#fca5a5', fontWeight: '700', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                            <AlertTriangle size={15} color="#ef4444" /> Advertencia de API
                        </span>
                        <span style={{ fontSize: '0.78rem', color: '#cbd5e1', lineHeight: '1.4' }}>
                            Los siguientes exchanges seleccionados tienen problemas de conexión:
                            <ul style={{ margin: '0.2rem 0 0 0', paddingLeft: '1.1rem', maxHeight: '130px', overflowY: 'auto' }}>
                                {exchangesWithErrors.map(ex => (
                                    <li key={ex.name}><strong>{ex.name}:</strong> {ex.msg || 'Credenciales inválidas o error de red.'}</li>
                                ))}
                            </ul>
                        </span>
                    </div>
                )}

                {staleExchanges.length > 0 && (
                    <div style={{ background: 'rgba(245, 158, 11, 0.12)', border: '1px solid #f59e0b', borderRadius: '0.75rem', padding: '0.85rem 1rem', marginBottom: '1rem', display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                        <span style={{ fontSize: '0.85rem', color: '#fde68a', fontWeight: '700', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                            <Info size={15} color="#f59e0b" /> Datos Desactualizados
                        </span>
                        <span style={{ fontSize: '0.78rem', color: '#cbd5e1', lineHeight: '1.4' }}>
                            El periodo solicitado finaliza el {dateRange.end}, pero algunos exchanges no registran datos hasta esa fecha:
                            <ul style={{ margin: '0.2rem 0 0 0', paddingLeft: '1.1rem', maxHeight: '130px', overflowY: 'auto' }}>
                                {staleExchanges.map(ex => (
                                    <li key={ex.name}><strong>{ex.name}:</strong> última sincronización el {formatDateDisplay(ex.lastUpdate)}</li>
                                ))}
                            </ul>
                        </span>
                    </div>
                )}

                {effectiveGaps && effectiveGaps.length > 0 && (
                    <div style={{ background: 'rgba(245, 158, 11, 0.08)', border: '1px solid rgba(245, 158, 11, 0.3)', borderRadius: '0.75rem', padding: '0.85rem 1rem', marginBottom: '1rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flex: 1 }}>
                            <div style={{ background: 'rgba(245, 158, 11, 0.2)', padding: '0.45rem', borderRadius: '0.5rem', display: 'flex', alignItems: 'center' }}>
                                <AlertTriangle size={18} color="#fbbf24" />
                            </div>
                            <div>
                                <span style={{ fontSize: '0.86rem', color: '#fef08a', fontWeight: '700', display: 'block' }}>
                                    {effectiveGaps.length} Faltante(s) de Historial (Huecos FIFO / P2P)
                                </span>
                                <span style={{ fontSize: '0.78rem', color: '#cbd5e1', lineHeight: '1.3' }}>
                                    Se detectaron ventas sin compras previas registradas. Podes completar la información en el Calendario.
                                </span>
                            </div>
                        </div>
                        <button
                            className="btn-primary"
                            style={{ background: '#D97706', border: 'none', padding: '0.45rem 0.9rem', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#fff', fontWeight: '600', borderRadius: '0.5rem', cursor: 'pointer' }}
                            onClick={() => {
                                const targetYear = (effectiveGaps?.[0]?.date && String(effectiveGaps[0].date).slice(0, 4))
                                    || (dateRange?.start && String(dateRange.start).slice(0, 4))
                                    || '2025';
                                navigate(`/calendar?tab=warnings&year=${targetYear}`);
                            }}
                        >
                            <Sparkles size={14} /> Resolver en Calendario →
                        </button>
                    </div>
                )}

                <div style={{ background: 'rgba(15, 23, 42, 0.6)', border: '1px solid var(--border-color)', borderRadius: '0.75rem', padding: '1rem', display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem' }}>
                    <Info size={20} color={previewCount > 0 ? "var(--accent-cyan)" : "#ef4444"} style={{ flexShrink: 0 }} />
                    <div style={{ flex: 1 }}>
                        {selectedExchanges.length === 0 ? (
                            <span style={{ fontSize: '0.85rem', color: '#fca5a5' }}>Selecciona al menos un exchange para consultar operaciones.</span>
                        ) : datesInverted ? (
                            <span style={{ fontSize: '0.85rem', color: '#fca5a5' }}>Filtro de fechas incoherente.</span>
                        ) : loadingPreview ? (
                            <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                <RefreshCw size={12} className="spin" /> Calculando registros disponibles...
                            </span>
                        ) : previewCount !== null ? (
                            <span style={{ fontSize: '0.85rem', color: previewCount > 0 ? '#cbd5e1' : '#fca5a5', fontWeight: '500' }}>
                                {previewCount > 0 ? `Se detectaron ${previewCount} transacciones en la base de datos.` : "No se encontraron operaciones con los filtros actuales."}
                            </span>
                        ) : (
                            <span style={{ fontSize: '0.85rem', color: '#ef4444' }}>Error al consultar disponibilidad.</span>
                        )}
                    </div>
                </div>
            </div>

            <div style={{ paddingTop: '1rem', borderTop: '1px solid rgba(255,255,255,0.06)', flexShrink: 0 }}>
                <button
                    className="btn-primary"
                    onClick={openMappingModal}
                    disabled={isDownloadDisabled}
                    style={{
                        width: '100%', padding: '1rem', fontSize: '1rem', fontWeight: 'bold',
                        display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '0.5rem',
                        opacity: isDownloadDisabled ? 0.5 : 1,
                        cursor: isDownloadDisabled ? 'not-allowed' : 'pointer'
                    }}
                >
                    {downloading ? (
                        <><RefreshCw size={20} className="spin" /> GENERANDO REPORTE...</>
                    ) : selectedExchanges.length === 0 ? (
                        "SELECCIONA EXCHANGES"
                    ) : datesInverted ? (
                        "ERROR DE FECHAS"
                    ) : previewCount === 0 ? (
                        "SIN OPERACIONES"
                    ) : (
                        <><Download size={20} /> {exportFormat === 'separated' ? 'DESCARGAR ZIP' : 'DESCARGAR EXCEL MAESTRO'}</>
                    )}
                </button>
            </div>

            <ReportMappingModal
                show={showMappingModal} onClose={() => setShowMappingModal(false)}
                mappingPreviewData={mappingPreviewData} activeTabIdx={activeTabIdx} setActiveTabIdx={setActiveTabIdx}
                dateRange={dateRange} uploadingFile={uploadingFile} handleModalFileUpload={handleModalFileUpload}
                confirmAndDownload={confirmAndDownload} downloading={downloading}
                formatDateDisplay={formatDateDisplay} checkIsStale={checkIsStale}
            />
        </div>
    );
}

export default ReportExporter;
