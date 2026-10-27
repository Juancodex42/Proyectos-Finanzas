import { useState, useEffect } from 'react';
import { useFileContext } from '../context/FileContext';
import config from '../config';
import { AnimatePresence } from 'framer-motion';
import axios from 'axios';
import HomeGapsCard from '../components/home/HomeGapsCard';
import HomeWorkflowExplainer from '../components/home/HomeWorkflowExplainer';
import HomeDropzone from '../components/home/HomeDropzone';
import HomeImportResults from '../components/home/HomeImportResults';

function Home() {
    const [gaps, setGaps] = useState([]);
    const [gapsSummary, setGapsSummary] = useState(null);
    const [gapsModes, setGapsModes] = useState(null);
    const [selectedExchanges, setSelectedExchanges] = useState({});
    const [uploadProgress, setUploadProgress] = useState(0);

    const {
        fileList, addFiles, clearFiles, clearQueue,
        processing, setProcessing,
        results, setResults,
        error, setError
    } = useFileContext();

    const fetchGaps = async () => {
        try {
            const res = await axios.get(`${config.API_URL}/api/reports/gaps?mode=global`);
            const modes = res.data.modes || null;
            const hasGlobalData = modes?.global?.total_gaps !== undefined;
            const globalGaps = modes?.global?.gaps;
            setGaps(hasGlobalData ? (globalGaps || []) : (res.data.gaps || []));
            if (res.data.summary) setGapsSummary(res.data.summary);
            if (modes) setGapsModes(modes);
        } catch (err) {
            console.error("Error fetching gaps in Home page:", err);
        }
    };

    useEffect(() => {
        fetchGaps();
    }, []);

    const formatFileSize = (bytes) => {
        if (!bytes || bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    };

    const detectExchangeHint = (filename) => {
        const lower = (filename || '').toLowerCase();
        if (lower.includes('okx')) return 'OKX';
        if (lower.includes('binance') && lower.includes('p2p')) return 'Binance P2P';
        if (lower.includes('binance')) return 'Binance Spot';
        if (lower.includes('bitso')) return 'Bitso Alpha';
        if (lower.includes('fiwind')) return 'Fiwind';
        if (lower.includes('ripio') && lower.includes('trade')) return 'Ripio Trade';
        if (lower.includes('ripio')) return 'Ripio Classic';
        if (lower.includes('bitget')) return 'Bitget';
        if (lower.includes('bybit')) return 'Bybit';
        if (lower.includes('belo')) return 'Belo';
        if (lower.includes('buenbit')) return 'Buenbit';
        if (lower.includes('kraken')) return 'Kraken';
        if (lower.includes('lemon')) return 'Lemon Cash';
        if (lower.includes('consolidada') || lower.includes('manual')) return 'Planilla Consolidada';
        return 'Auto-detectar (Firma)';
    };

    const processFiles = async (overrideExchange = null) => {
        setProcessing(true);
        setError(null);
        setUploadProgress(0);
        const formData = new FormData();
        fileList.forEach(f => formData.append('files', f));
        if (overrideExchange && overrideExchange !== 'AUTO') {
            formData.append('override_exchange', overrideExchange);
        }

        try {
            const res = await axios.post(`${config.API_URL}/process`, formData, {
                onUploadProgress: (progressEvent) => {
                    const total = progressEvent.total || 1;
                    const percent = Math.round((progressEvent.loaded * 100) / total);
                    setUploadProgress(percent);
                }
            });
            setResults(res.data);
            if ((res.data?.status === 'success' && (res.data?.total_transactions || 0) > 0) || res.data?.results) {
                clearQueue();
            }
            fetchGaps();
        } catch (err) {
            if (err.response && err.response.data && err.response.data.error === 'missing_columns') {
                const ex = (err.response.data.exchange || 'el exchange').toUpperCase();
                const missingStr = Array.isArray(err.response.data.missing) ? err.response.data.missing.join(', ') : err.response.data.missing;
                const availStr = Array.isArray(err.response.data.available) ? err.response.data.available.slice(0, 10).join(', ') : err.response.data.available;
                setError({
                    type: 'config',
                    msg: `Faltan columnas requeridas para ${ex}`,
                    details: `No se encontraron los encabezados obligatorios: [${missingStr}]. Columnas detectadas: [${availStr}]. Puedes reconfigurarlas en Configuración.`
                });
            } else if (err.code === 'ERR_NETWORK' || !err.response) {
                setError({
                    type: 'network',
                    msg: 'No se pudo conectar con el servidor backend (puerto 5000). Asegúrate de que el motor contable esté iniciado.'
                });
            } else {
                const serverMsg = err.response?.data?.error || err.response?.data?.message;
                setError({
                    type: 'network',
                    msg: serverMsg || 'Error al procesar los archivos. Verifica que los formatos sean compatibles.'
                });
            }
        } finally {
            setProcessing(false);
        }
    };

    const downloadExcel = async () => {
        try {
            const filenames = results.files.map(f => f.filename);
            const res = await axios.post(`${config.API_URL}/download`, { filenames }, {
                responseType: 'blob'
            });
            const url = window.URL.createObjectURL(new Blob([res.data]));
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', 'Reporte_Ganancias_FIFO.xlsx');
            document.body.appendChild(link);
            link.click();
            link.remove();
            window.URL.revokeObjectURL(url);
        } catch (err) {
            console.error("Error downloading file", err);
            alert("Error al descargar el archivo");
        }
    };

    return (
        <div style={{ maxWidth: '1440px', margin: '0 auto', padding: '1.75rem 2rem', color: 'var(--text-primary)' }}>
            {/* INSTITUTIONAL PAGE HEADER */}
            <header style={{ marginBottom: '1.75rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.25rem' }}>
                    <h1 style={{ fontSize: '1.85rem', fontWeight: 800, letterSpacing: '-0.02em', color: '#F8FAFC', margin: 0 }}>
                        Motor de Procesamiento Contable
                    </h1>
                </div>
                <p style={{ color: 'var(--text-secondary)', margin: 0, fontSize: '0.9rem' }}>
                    Ingestión de reportes, cálculo de costo base FIFO y determinación de ganancias gravables.
                </p>
            </header>

            {/* CRITICAL GAP NOTIFICATION */}
            <HomeGapsCard
                gaps={gaps}
                gapsSummary={gapsSummary}
                gapsModes={gapsModes}
            />

            <AnimatePresence mode="wait">
                {!results ? (
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: '1.5rem' }}>
                        <HomeWorkflowExplainer />
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
                    </div>
                ) : (
                    <HomeImportResults
                        results={results}
                        setResults={setResults}
                        clearFiles={clearFiles}
                        downloadExcel={downloadExcel}
                        selectedExchanges={selectedExchanges}
                        setSelectedExchanges={setSelectedExchanges}
                    />
                )}
            </AnimatePresence>
        </div>
    );
}

export default Home;
