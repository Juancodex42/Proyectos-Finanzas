import { useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { RefreshCw } from 'lucide-react';
import axios from 'axios';
import config from '../config';
import ExchangeSelector from '../components/reports/ExchangeSelector';
import DateRangeSelector from '../components/reports/DateRangeSelector';
import ReportExporter from '../components/reports/ReportExporter';
import { formatDateLocal, formatDateDisplay, checkIsStale, computeStaleExchanges } from '../components/reports/reportUtils';

function Reports() {
    const location = useLocation();
    const searchParams = new URLSearchParams(location.search);
    const paramStart = searchParams.get('start') || (searchParams.get('year') ? `${searchParams.get('year')}-01-01` : '');
    const paramEnd = searchParams.get('end') || (searchParams.get('year') ? `${searchParams.get('year')}-12-31` : '');

    const [selectedExchanges, setSelectedExchanges] = useState([]);
    const [dateRange, setDateRange] = useState({ start: paramStart, end: paramEnd });
    const [latestCertDate, setLatestCertDate] = useState(null);
    const [exportFormat, setExportFormat] = useState('consolidated');
    const [exchanges, setExchanges] = useState([]);
    const [previewCount, setPreviewCount] = useState(null);
    const [loadingPreview, setLoadingPreview] = useState(false);
    const [loadingExchanges, setLoadingExchanges] = useState(true);
    const [gaps, setGaps] = useState([]);

    // Modal States
    const [showMappingModal, setShowMappingModal] = useState(false);
    const [mappingPreviewData, setMappingPreviewData] = useState([]);
    const [activeTabIdx, setActiveTabIdx] = useState(0);

    const fetchExchanges = async () => {
        setLoadingExchanges(true);
        try {
            const exRes = await axios.get(`${config.API_URL}/api/exchanges`);
            const rawExchanges = (exRes.data || []).filter(ex => ex.id !== 'manual');
            const list = rawExchanges.map(ex => ({
                id: ex.id,
                name: ex.name,
                type: ex.type,
                status: 'loading',
                lastUpdate: '-',
                msg: ''
            }));
            setExchanges(list);
            setSelectedExchanges(list.map(ex => ex.name));

            const statusRes = await axios.get(`${config.API_URL}/api/status`);
            const statusData = statusRes.data || {};
            const statusList = Array.isArray(statusData.data) ? statusData.data : (Array.isArray(statusData) ? statusData : []);
            const statusMap = {};
            statusList.forEach(s => { if (s && s.id) statusMap[s.id] = s; });
            if (statusData.statuses) {
                Object.assign(statusMap, statusData.statuses);
            }
            Object.keys(statusData).forEach(k => {
                if (statusData[k] && typeof statusData[k] === 'object' && !Array.isArray(statusData[k])) {
                    statusMap[k] = statusData[k];
                }
            });

            setExchanges(prev => prev.map(ex => ({
                ...ex,
                status: statusMap[ex.id]?.status || statusData[ex.id]?.status || 'online',
                lastUpdate: statusMap[ex.id]?.lastUpdate || statusData[ex.id]?.lastUpdate || '-',
                msg: statusMap[ex.id]?.msg || statusData[ex.id]?.msg || ''
            })));
        } catch (err) {
            console.error("Error fetching exchanges/status", err);
        } finally {
            setLoadingExchanges(false);
        }
    };

    const fetchLatestCertDate = async () => {
        try {
            const res = await axios.get(`${config.API_URL}/api/certifications`);
            setLatestCertDate(res.data?.summary?.latest_end_date || null);
        } catch (err) {
            console.error("Error fetching latest certification date:", err);
            setLatestCertDate(null);
        }
    };

    useEffect(() => {
        fetchExchanges();
        fetchLatestCertDate();

        const onCertUpdated = () => fetchLatestCertDate();
        window.addEventListener('certifications_updated', onCertUpdated);
        return () => window.removeEventListener('certifications_updated', onCertUpdated);
    }, []);

    useEffect(() => {
        const params = new URLSearchParams(location.search);
        const s = params.get('start') || (params.get('year') ? `${params.get('year')}-01-01` : null);
        const e = params.get('end') || (params.get('year') ? `${params.get('year')}-12-31` : null);
        if (s || e) {
            setDateRange(prev => ({
                start: s !== null ? s : prev.start,
                end: e !== null ? e : prev.end
            }));
        }
    }, [location.search]);

    const startYMD = dateRange.start ? dateRange.start.slice(0, 10) : '';
    const endYMD = dateRange.end ? dateRange.end.slice(0, 10) : '';
    const datesInverted = Boolean(startYMD && endYMD && startYMD > endYMD);

    useEffect(() => {
        if (selectedExchanges.length === 0 || datesInverted) {
            setPreviewCount(0);
            setGaps([]);
            return;
        }

        const controller = new AbortController();

        const fetchPreview = async () => {
            setLoadingPreview(true);
            try {
                const res = await axios.post(`${config.API_URL}/api/reports/batch-generate`, {
                    exchanges: selectedExchanges,
                    dateStart: dateRange.start,
                    dateEnd: dateRange.end,
                    mode: 'global'
                }, { signal: controller.signal });
                setPreviewCount(res.data.count);
                setGaps(res.data.gaps || []);
            } catch (err) {
                if (err.name === 'AbortError' || err.name === 'CanceledError' || err.code === 'ERR_CANCELED') return;
                console.error("Error fetching preview", err);
                setPreviewCount(null);
                setGaps([]);
            } finally {
                if (!controller.signal.aborted) {
                    setLoadingPreview(false);
                }
            }
        };

        const delayDebounce = setTimeout(() => {
            fetchPreview();
        }, 300);

        return () => {
            clearTimeout(delayDebounce);
            controller.abort();
        };
    }, [selectedExchanges, dateRange, datesInverted]);

    const toggleSelection = (name) => {
        if (selectedExchanges.includes(name)) {
            setSelectedExchanges(selectedExchanges.filter(item => item !== name));
        } else {
            setSelectedExchanges([...selectedExchanges, name]);
        }
    };

    const selectAllExchanges = () => setSelectedExchanges(exchanges.map(ex => ex.name));
    const deselectAllExchanges = () => setSelectedExchanges([]);

    const handlePreset = (type) => {
        const today = new Date();
        let start = '';
        let end = '';

        if (type === 'last_cert') {
            if (latestCertDate) {
                const rawYMD = latestCertDate.slice(0, 10);
                const d = new Date(`${rawYMD}T00:00:00`);
                d.setDate(d.getDate() + 1);
                start = formatDateLocal(d);
                end = (dateRange.end && dateRange.end.slice(0, 10) >= start) ? dateRange.end.slice(0, 10) : formatDateLocal(today);
            }
        } else if (type === 'current_month') {
            start = formatDateLocal(new Date(today.getFullYear(), today.getMonth(), 1));
            end = formatDateLocal(new Date(today.getFullYear(), today.getMonth() + 1, 0));
        } else if (type === 'last_month') {
            start = formatDateLocal(new Date(today.getFullYear(), today.getMonth() - 1, 1));
            end = formatDateLocal(new Date(today.getFullYear(), today.getMonth(), 0));
        } else if (type === 'last_90') {
            const pastDate = new Date();
            pastDate.setDate(today.getDate() - 90);
            start = formatDateLocal(pastDate);
            end = formatDateLocal(today);
        } else if (type === 'all') {
            start = '';
            end = '';
        }

        setDateRange({ start, end });
    };

    const openMappingModal = async () => {
        if (selectedExchanges.length === 0) {
            alert("Selecciona al menos un exchange para descargar el reporte.");
            return;
        }
        if (datesInverted) {
            alert("La fecha de inicio debe ser anterior o igual a la fecha de fin.");
            return;
        }
        setLoadingPreview(true);
        try {
            const res = await axios.post(`${config.API_URL}/api/reports/preview-mapping`, {
                exchanges: selectedExchanges,
                dateStart: dateRange.start,
                dateEnd: dateRange.end
            });
            setMappingPreviewData(res.data || []);
            setActiveTabIdx(0);
            setShowMappingModal(true);
        } catch (err) {
            console.error("Error fetching preview mapping", err);
            alert("Error al cargar la previsualización del reporte.");
        } finally {
            setLoadingPreview(false);
        }
    };

    const staleExchanges = computeStaleExchanges(exchanges, selectedExchanges, dateRange.end);
    const exchangesWithErrors = exchanges.filter(ex => selectedExchanges.includes(ex.name) && ['expired', 'offline'].includes(ex.status));

    return (
        <div style={{ padding: '1.25rem 2rem', maxWidth: '1400px', margin: '1rem auto', display: 'flex', flexDirection: 'column', height: 'calc(100vh - 2rem)', boxSizing: 'border-box', overflow: 'hidden' }}>
            <header style={{ marginBottom: '1.25rem', borderBottom: '1px solid rgba(255,255,255,0.08)', paddingBottom: '0.75rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                    <h1 style={{ fontSize: '1.85rem', margin: 0, color: '#F8FAFC', fontWeight: '700', letterSpacing: '-0.02em' }}>
                        Reportes Continuos
                    </h1>
                    <p style={{ color: '#94A3B8', margin: '0.25rem 0 0 0', fontSize: '0.9rem' }}>
                        Genera y descarga reportes personalizados a partir del historial acumulado en la base de datos.
                    </p>
                </div>
                <button
                    onClick={fetchExchanges}
                    style={{ background: 'rgba(30, 41, 59, 0.6)', border: '1px solid var(--border-color)', color: 'var(--text-secondary)', padding: '0.5rem 1rem', borderRadius: '0.5rem', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem' }}
                >
                    <RefreshCw size={14} className={loadingExchanges ? "spin" : ""} /> Recargar Estados
                </button>
            </header>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '1.5rem', flex: 1, minHeight: 0, overflow: 'hidden' }}>
                <ExchangeSelector
                    exchanges={exchanges}
                    selectedExchanges={selectedExchanges}
                    toggleSelection={toggleSelection}
                    selectAllExchanges={selectAllExchanges}
                    deselectAllExchanges={deselectAllExchanges}
                    formatDateDisplay={formatDateDisplay}
                />

                <DateRangeSelector
                    dateRange={dateRange}
                    setDateRange={setDateRange}
                    datesInverted={datesInverted}
                    latestCertDate={latestCertDate}
                    handlePreset={handlePreset}
                    formatDateDisplay={formatDateDisplay}
                />

                <ReportExporter
                    exportFormat={exportFormat}
                    setExportFormat={setExportFormat}
                    selectedExchanges={selectedExchanges}
                    datesInverted={datesInverted}
                    loadingPreview={loadingPreview}
                    previewCount={previewCount}
                    setPreviewCount={setPreviewCount}
                    gaps={gaps}
                    setGaps={setGaps}
                    exchangesWithErrors={exchangesWithErrors}
                    staleExchanges={staleExchanges}
                    dateRange={dateRange}
                    openMappingModal={openMappingModal}
                    showMappingModal={showMappingModal}
                    setShowMappingModal={setShowMappingModal}
                    mappingPreviewData={mappingPreviewData}
                    setMappingPreviewData={setMappingPreviewData}
                    activeTabIdx={activeTabIdx}
                    setActiveTabIdx={setActiveTabIdx}
                    formatDateDisplay={formatDateDisplay}
                    checkIsStale={checkIsStale}
                />
            </div>
        </div>
    );
}

export default Reports;
