import { useState, useEffect, useMemo } from 'react';
import axios from 'axios';
import config from '../config';
import { useFileContext } from '../context/FileContext';
import HistoryToolbar, {
    formatFileSize, detectExchangeHint, formatCurrency, formatCryptoQty
} from '../components/history/HistoryToolbar';
import HistoryTransactionsTable from '../components/history/HistoryTransactionsTable';
import HistoryFilesView from '../components/history/HistoryFilesView';

function History() {
    const [viewMode, setViewMode] = useState('transactions');
    const [historySubMode, setHistorySubMode] = useState('exchanges');
    const [history, setHistory] = useState([]);
    const [fileHistory, setFileHistory] = useState([]);
    const [transactions, setTransactions] = useState([]);
    const [gaps, setGaps] = useState([]);
    const [loading, setLoading] = useState(true);
    const [statusFilter, setStatusFilter] = useState('all');
    const [typeFilter, setTypeFilter] = useState('ALL');
    const [selectedExchange, setSelectedExchange] = useState('ALL');
    const [txSearch, setTxSearch] = useState('');
    const [copiedHash, setCopiedHash] = useState(null);
    const [downloadingFile, setDownloadingFile] = useState(null);
    const [deletingBatch, setDeletingBatch] = useState(null);
    const [currentPage, setCurrentPage] = useState(1);
    const [pageSize, setPageSize] = useState(50);
    const [uploadProgress, setUploadProgress] = useState(0);

    const { fileList, addFiles, clearFiles, processing, setProcessing, error, setError } = useFileContext();

    useEffect(() => {
        setCurrentPage(1);
    }, [statusFilter, typeFilter, selectedExchange, txSearch]);

    const fetchAllData = async (signal) => {
        const isSignal = signal instanceof AbortSignal;
        const reqConfig = isSignal ? { signal } : {};
        setLoading(true);
        try {
            const [hRes, hfRes, tRes] = await Promise.all([
                axios.get(`${config.API_URL}/api/history`, reqConfig),
                axios.get(`${config.API_URL}/api/history?mode=files`, reqConfig),
                axios.get(`${config.API_URL}/api/transactions`, reqConfig)
            ]);
            setHistory(hRes.data || []);
            setFileHistory(hfRes.data || []);
            setTransactions(tRes.data || []);
            setLoading(false);

            // Fetch gaps in background without blocking transactions ledger view
            axios.get(`${config.API_URL}/api/reports/gaps?mode=global`, reqConfig)
                .then((gRes) => {
                    const gModes = gRes.data?.modes || null;
                    const hasGGlobal = gModes?.global?.total_gaps !== undefined;
                    setGaps(hasGGlobal ? (gModes?.global?.gaps || []) : (gRes.data?.gaps || []));
                })
                .catch((err) => {
                    if (err.name === 'AbortError' || err.name === 'CanceledError' || err.code === 'ERR_CANCELED') return;
                    console.error("Error fetching gaps in background", err);
                });
        } catch (err) {
            if (err.name === 'AbortError' || err.name === 'CanceledError' || err.code === 'ERR_CANCELED') return;
            console.error("Error fetching history or transactions", err);
        } finally {
            if (!(isSignal && signal.aborted)) setLoading(false);
        }
    };

    useEffect(() => {
        const controller = new AbortController();
        fetchAllData(controller.signal);
        return () => controller.abort();
    }, []);

    const deleteExchangeBatch = async (exchangeName) => {
        if (!window.confirm(`¿Estás seguro de que deseas eliminar TODAS las transacciones de ${exchangeName}? Esta acción no se puede deshacer.`)) return;
        setDeletingBatch(exchangeName);
        try {
            const res = await axios.delete(`${config.API_URL}/api/history/exchange/${encodeURIComponent(exchangeName)}`);
            if (res.data?.success) {
                alert(`Se eliminaron ${res.data.deleted_count} transacciones de ${exchangeName}.`);
                await fetchAllData();
            } else alert("Error al eliminar los registros.");
        } catch (err) {
            console.error("Error al eliminar intercambio", err);
            alert("Error de conexión al eliminar los registros.");
        } finally {
            setDeletingBatch(null);
        }
    };

    const deleteFileBatch = async (filename) => {
        if (!window.confirm(`¿Estás seguro de que deseas eliminar las transacciones importadas desde el archivo "${filename}"? Esta acción recalculará los lotes FIFO automáticamente.`)) return;
        setDeletingBatch(filename);
        try {
            const res = await axios.delete(`${config.API_URL}/api/history/file/${encodeURIComponent(filename)}`);
            if (res.data?.success) {
                alert(`Se eliminaron ${res.data.deleted_count} transacciones del archivo "${filename}".`);
                await fetchAllData();
            } else alert("Error al eliminar los registros del archivo.");
        } catch (err) {
            console.error("Error al eliminar archivo", err);
            alert("Error de conexión al eliminar los registros.");
        } finally {
            setDeletingBatch(null);
        }
    };

    const handleProcessFiles = async (overrideExchange = null) => {
        setProcessing(true);
        setError(null);
        setUploadProgress(0);
        const formData = new FormData();
        fileList.forEach(f => formData.append('files', f));
        if (overrideExchange && overrideExchange !== 'AUTO') formData.append('override_exchange', overrideExchange);

        try {
            const res = await axios.post(`${config.API_URL}/process`, formData, {
                onUploadProgress: (progressEvent) => {
                    const total = progressEvent.total || 1;
                    setUploadProgress(Math.round((progressEvent.loaded * 100) / total));
                }
            });
            const data = res.data || {};
            const processedFiles = data.files || data.results || [];
            const failedResults = processedFiles.filter(r => r.status === 'error' || r.error);
            if ((data.errors && data.errors.length > 0) || failedResults.length > 0) {
                const structuredMsgs = failedResults.map(r => {
                    const prefix = r.filename ? `[${r.filename}]: ` : '';
                    if (r.error === 'missing_columns' || r.missing_columns || r.missing) {
                        const cols = r.missing_columns || r.missing || [];
                        return `${prefix}Faltan columnas requeridas: ${Array.isArray(cols) ? cols.join(', ') : cols}`;
                    }
                    return `${prefix}${r.message || r.error}`;
                }).filter(Boolean);
                const msgList = [...(data.errors || []), ...structuredMsgs];
                setError({
                    type: failedResults.some(r => r.error === 'missing_columns' || r.missing_columns) ? 'config' : 'network',
                    msg: msgList.join(' | ') || 'Error al procesar los archivos.'
                });
            } else {
                clearFiles();
            }
            await fetchAllData();
        } catch (err) {
            const errData = err.response?.data;
            if (errData?.error === 'missing_columns' || errData?.missing_columns) {
                const cols = errData.missing_columns || errData.missing || [];
                setError({ type: 'config', msg: `Faltan columnas requeridas: ${Array.isArray(cols) ? cols.join(', ') : cols}` });
            } else if (err.code === 'ERR_NETWORK' || !err.response) {
                setError({ type: 'network', msg: 'No se pudo conectar con el servidor backend (puerto 5000). Asegúrate de que el motor contable esté iniciado.' });
            } else {
                const serverMsg = errData?.error || errData?.message;
                setError({ type: 'network', msg: serverMsg || 'Error al procesar los archivos.' });
            }
        } finally {
            setProcessing(false);
        }
    };

    const downloadOriginal = async (filename) => {
        setDownloadingFile(filename);
        try {
            const res = await axios.post(`${config.API_URL}/download`, { filenames: [filename] }, { responseType: 'blob' });
            const url = window.URL.createObjectURL(new Blob([res.data]));
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', `Reporte_${filename}.xlsx`);
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            window.URL.revokeObjectURL(url);
        } catch {
            alert("Error al descargar. Archivo no encontrado en DB.");
        } finally {
            setDownloadingFile(null);
        }
    };

    const copyToClipboard = (text, id) => {
        if (!text) return;
        navigator.clipboard.writeText(text);
        setCopiedHash(id);
        setTimeout(() => setCopiedHash(null), 2000);
    };

    const availableExchanges = useMemo(() => {
        const set = new Set();
        transactions.forEach(t => { const ex = t.exchange || t.Exchange; if (ex) set.add(ex); });
        return Array.from(set).sort();
    }, [transactions]);

    const allCount = transactions.length;
    const certifiedCount = transactions.filter(t => t.is_certified === 1).length;
    const uncertifiedCount = transactions.filter(t => t.is_certified !== 1).length;

    const filteredTxs = useMemo(() => {
        return transactions.filter(t => {
            if (statusFilter === 'certified' && t.is_certified !== 1) return false;
            if (statusFilter === 'uncertified' && t.is_certified === 1) return false;
            const tExchange = t.exchange || t.Exchange || '';
            if (selectedExchange !== 'ALL' && tExchange !== selectedExchange) return false;
            const tType = (t.tipo_operacion || t['Tipo de Operación'] || '').toLowerCase();
            if (typeFilter === 'Compra' && !tType.includes('compra') && !tType.includes('buy')) return false;
            if (typeFilter === 'Venta' && !tType.includes('venta') && !tType.includes('sell')) return false;
            if (txSearch.trim()) {
                const q = txSearch.toLowerCase().trim();
                const date = (t.fecha || t.Fecha || '').toLowerCase();
                const coin = (t.moneda || t.Moneda || '').toLowerCase();
                const hash = (t.tx_hash || t.id || t.order_id || t['ID Transacción'] || '').toString().toLowerCase();
                if (!date.includes(q) && !coin.includes(q) && !hash.includes(q) && !tExchange.toLowerCase().includes(q)) return false;
            }
            return true;
        });
    }, [transactions, statusFilter, selectedExchange, typeFilter, txSearch]);

    const filteredTotalARS = useMemo(() => {
        return filteredTxs.reduce((sum, t) => {
            const raw = t.monto_ars ?? t['Monto ARS'];
            const val = typeof raw === 'string' ? Number(raw.replace(',', '.')) : Number(raw);
            return sum + (val || 0);
        }, 0);
    }, [filteredTxs]);

    return (
        <div style={{ maxWidth: '1440px', margin: '0 auto', padding: '1.75rem 2rem', color: 'var(--text-primary)' }}>
            <HistoryToolbar
                loading={loading} onRefresh={fetchAllData} viewMode={viewMode} setViewMode={setViewMode}
                transactionsCount={transactions.length} historyCount={history.length} gaps={gaps}
                filteredCount={filteredTxs.length} allCount={allCount} filteredTotalARS={filteredTotalARS}
                certifiedCount={certifiedCount} uncertifiedCount={uncertifiedCount}
                txSearch={txSearch} setTxSearch={setTxSearch} statusFilter={statusFilter} setStatusFilter={setStatusFilter}
                selectedExchange={selectedExchange} setSelectedExchange={setSelectedExchange}
                availableExchanges={availableExchanges} typeFilter={typeFilter} setTypeFilter={setTypeFilter}
                formatCurrency={formatCurrency}
            />

            {viewMode === 'transactions' ? (
                <HistoryTransactionsTable
                    filteredTxs={filteredTxs} allCount={allCount} copiedHash={copiedHash}
                    copyToClipboard={copyToClipboard} formatCurrency={formatCurrency} formatCryptoQty={formatCryptoQty}
                    currentPage={currentPage} setCurrentPage={setCurrentPage} pageSize={pageSize} setPageSize={setPageSize}
                />
            ) : (
                <HistoryFilesView
                    history={history} fileHistory={fileHistory} historySubMode={historySubMode} setHistorySubMode={setHistorySubMode}
                    downloadOriginal={downloadOriginal} deleteExchangeBatch={deleteExchangeBatch} deleteFileBatch={deleteFileBatch}
                    downloadingFile={downloadingFile} deletingBatch={deletingBatch}
                    fileList={fileList} addFiles={addFiles} clearFiles={clearFiles} processing={processing}
                    uploadProgress={uploadProgress} processFiles={handleProcessFiles} error={error}
                    formatFileSize={formatFileSize} detectExchangeHint={detectExchangeHint}
                />
            )}
        </div>
    );
}

export default History;
