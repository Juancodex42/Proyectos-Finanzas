import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import config from '../config';
import { Link } from 'react-router-dom';
import { RefreshCw, Compass, ArrowRight } from 'lucide-react';
import DashboardFilters from '../components/dashboard/DashboardFilters';
import DashboardMetrics from '../components/dashboard/DashboardMetrics';
import DashboardCharts from '../components/dashboard/DashboardCharts';
import DashboardAnomaliesTable from '../components/dashboard/DashboardAnomaliesTable';
import CertExcelCrossAuditAlerts from '../components/dashboard/CertExcelCrossAuditAlerts';
import { ORIGIN_OPTIONS } from '../components/dashboard/dashboardConstants';

function Dashboard() {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [gaps, setGaps] = useState([]);
    const [gapsModes, setGapsModes] = useState(null);
    const [sourceAlerts, setSourceAlerts] = useState([]);
    const [startDate, setStartDate] = useState('');
    const [endDate, setEndDate] = useState('');
    const [statusFilter, setStatusFilter] = useState('all');
    const [selectedExchanges, setSelectedExchanges] = useState([]);
    const [equityInterval, setEquityInterval] = useState('daily');
    const [selectedOrigins, setSelectedOrigins] = useState({});
    const [classifying, setClassifying] = useState({});

    const fetchData = useCallback(async (signal) => {
        const isSignal = signal instanceof AbortSignal;
        setLoading(true);
        try {
            const params = {};
            if (startDate) params.start_date = startDate;
            if (endDate) params.end_date = endDate;
            if (statusFilter !== 'all') params.status = statusFilter;
            if (selectedExchanges.length > 0) params.exchanges = selectedExchanges.join(',');
            if (equityInterval) params.interval = equityInterval;

            const selectedYear = startDate ? parseInt(startDate.slice(0, 4), 10) : null;
            const gapsUrl = selectedYear 
                ? `${config.API_URL}/api/reports/gaps?year=${selectedYear}&mode=global` 
                : `${config.API_URL}/api/reports/gaps?mode=global`;
            const [dashRes, gapsRes] = await Promise.all([
                axios.get(`${config.API_URL}/api/dashboard`, { params, ...(isSignal && { signal }) }),
                axios.get(gapsUrl, isSignal ? { signal } : {})
            ]);

            setData(dashRes.data);
            const modes = gapsRes.data?.modes || null;
            const hasGlobal = modes?.global?.total_gaps !== undefined;
            setGaps(hasGlobal ? (modes?.global?.gaps || []) : (gapsRes.data?.gaps || []));
            setGapsModes(modes);
            setSourceAlerts(gapsRes.data?.source_alerts || []);
        } catch (error) {
            if (error.name === 'AbortError' || error.name === 'CanceledError' || error.code === 'ERR_CANCELED') return;
            console.error("Error fetching dashboard data:", error);
        } finally {
            if (!(isSignal && signal.aborted)) {
                setLoading(false);
            }
        }
    }, [startDate, endDate, statusFilter, selectedExchanges, equityInterval]);

    useEffect(() => {
        const controller = new AbortController();
        fetchData(controller.signal);
        return () => controller.abort();
    }, [fetchData]);

    const handleToggleExchange = (exch) => {
        setSelectedExchanges(prev =>
            prev.includes(exch) ? prev.filter(e => e !== exch) : [...prev, exch]
        );
    };

    const handleSelectAllExchanges = () => {
        if (selectedExchanges.length === availableExchanges.length) {
            setSelectedExchanges([]);
        } else {
            setSelectedExchanges([...availableExchanges]);
        }
    };

    const getAnomalyKey = (item, idx) => item?.id || `${item?.exchange || ''}_${item?.crypto || ''}_${item?.date || idx}`;

    const handleClassifyAnomaly = async (a, idx) => {
        const key = getAnomalyKey(a, idx);
        const origin = selectedOrigins[key] || ORIGIN_OPTIONS[0];
        setClassifying(prev => ({ ...prev, [key]: true }));
        try {
            const res = await axios.post(`${config.API_URL}/api/classify_origin`, {
                transaction_id: a.transaction_id,
                date: a.date,
                exchange: a.exchange,
                crypto: a.crypto,
                missing: a.missing,
                origin_type: origin
            });
            setSelectedOrigins(prev => {
                const next = { ...prev };
                delete next[key];
                return next;
            });
            alert(res.data.message || "Operación clasificada y registrada correctamente.");
            await fetchData();
        } catch (error) {
            console.error("Error classifying anomaly:", error);
            alert("Error al clasificar el origen de la operación.");
        } finally {
            setClassifying(prev => {
                const next = { ...prev };
                delete next[key];
                return next;
            });
        }
    };

    const handleResolveCrossAudit = async (txId, action, newVal) => {
        try {
            const res = await axios.post(`${config.API_BASE_URL}/reconciliation/cert-cross-audit/resolve`, {
                tx_id: txId,
                action: action,
                new_value: newVal
            });
            alert(res.data?.message || "Discrepancia resuelta correctamente.");
            await fetchData();
        } catch (err) {
            console.error("Error resolving cross audit discrepancy:", err);
            alert("Error al resolver la discrepancia.");
        }
    };

    const formatCurrency = (val) => {
        if (val === undefined || val === null) return "$ 0,00";
        return new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(val);
    };

    const availableExchanges = data?.available_exchanges || [];
    const kpis = data?.kpis;
    const anomalies = data?.anomalies || [];
    const certDiscrepancies = data?.cert_discrepancies || [];
    const equityCurve = data?.equity_curve || [];
    const dailyVol = data?.daily_volume || [];
    const exchangeDist = data?.exchange_distribution || [];
    const modalSpread = data?.modal_spread;

    return (
        <div style={{ maxWidth: '1440px', margin: '0 auto', padding: '1.75rem 2rem', color: 'var(--text-primary)' }}>
            {/* INSTITUTIONAL HEADER */}
            <header style={{ marginBottom: '1.75rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1.25rem' }}>
                <div>
                    <h1 style={{ margin: 0, fontSize: '1.85rem', fontWeight: 800, letterSpacing: '-0.02em', color: '#F8FAFC' }}>
                        Panel Analítico de Métricas
                    </h1>
                    <p style={{ color: 'var(--text-secondary)', margin: '0.25rem 0 0 0', fontSize: '0.9rem' }}>
                        Trazabilidad de fondos, curvas de rendimiento neto y conciliación contable multi-exchange.
                    </p>
                </div>
                <button
                    onClick={fetchData}
                    className="btn-primary"
                    style={{ padding: '0.625rem 1.25rem', fontSize: '0.875rem' }}
                >
                    <RefreshCw size={16} className={loading ? "spin" : ""} />
                    <span>Actualizar Métricas</span>
                </button>
            </header>

            {/* SOURCE ALERTS & ORPHAN WITHDRAWALS BANNER */}
            {sourceAlerts && sourceAlerts.length > 0 && (
                <div style={{
                    background: 'rgba(244, 63, 94, 0.08)',
                    border: '1px solid var(--accent-rose-border)',
                    borderRadius: 'var(--radius-lg)',
                    padding: '1rem 1.35rem',
                    marginBottom: '1.25rem',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '0.5rem'
                }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem' }}>
                        <span style={{ fontSize: '0.9rem', color: '#FDA4AF', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <Compass size={17} color="#FB7185" /> Alertas de Sincronización y Transferencias en Tránsito ({sourceAlerts.length})
                        </span>
                        <Link to={`/calendar?tab=warnings&year=${(sourceAlerts?.[0]?.date && String(sourceAlerts[0].date).slice(0, 4)) || (gaps?.[0]?.date && String(gaps[0].date).slice(0, 4)) || (startDate ? String(startDate).slice(0, 4) : 2025)}`} style={{ color: '#38BDF8', fontWeight: 600, fontSize: '0.82rem', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
                            Ver Detalle en Brújula <ArrowRight size={14} />
                        </Link>
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                        {sourceAlerts.slice(0, 3).map((al, idx) => (
                            <div key={idx} style={{ fontSize: '0.82rem', color: '#E2E8F0', background: 'rgba(13, 19, 31, 0.7)', padding: '0.5rem 0.75rem', borderRadius: 'var(--radius-md)', border: '1px solid rgba(244, 63, 94, 0.2)' }}>
                                {al.message}
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* CRITICAL GAP WARNING BANNER */}
            {((gapsModes?.global?.total_gaps !== undefined ? gapsModes.global.total_gaps > 0 : gaps.length > 0)) && (
                <div style={{
                    background: 'rgba(245, 158, 11, 0.08)',
                    border: '1px solid var(--accent-amber-border)',
                    borderRadius: 'var(--radius-lg)',
                    padding: '1.1rem 1.4rem',
                    marginBottom: '1.5rem',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '0.65rem',
                    boxShadow: 'var(--shadow-sm)'
                }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem' }}>
                        <span style={{ fontSize: '0.92rem', color: '#FDE68A', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <Compass size={18} color="#F59E0B" /> Brújula de Trazabilidad: {gapsModes?.global?.total_gaps !== undefined ? `${gapsModes.global.total_gaps} Inconsistencias Reales` : `Huecos de Historial (${gaps.length})`}
                        </span>
                        <Link to={`/calendar?tab=warnings&year=${(gaps?.[0]?.date && String(gaps[0].date).slice(0, 4)) || (startDate ? String(startDate).slice(0, 4) : 2025)}`} style={{ color: '#38BDF8', fontWeight: 600, fontSize: '0.85rem', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
                            Abrir Brújula de Resolución en Calendario <ArrowRight size={14} />
                        </Link>
                    </div>
                    <p style={{ fontSize: '0.85rem', color: '#CBD5E1', margin: 0, lineHeight: 1.5 }}>
                        {gapsModes?.global?.total_gaps !== undefined
                            ? `Criterio Patrimonial Real (AFIP/ARCA): Tenés ${gapsModes.global.total_gaps} ventas sin compra registrada en el sistema (pendientes de conciliar con extractos de Fiwind/OKX).`
                            : 'Se detectaron ventas de criptoactivos sin comprobante de compra previo. El sistema analizó pistas cruzadas para guiar tu búsqueda:'}
                    </p>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(290px, 1fr))', gap: '0.65rem', marginTop: '0.25rem' }}>
                        {gaps.slice(0, 3).map((gap, idx) => (
                            <div key={idx} style={{ background: 'rgba(13, 19, 31, 0.85)', padding: '0.65rem 0.85rem', borderRadius: 'var(--radius-md)', border: '1px solid rgba(245, 158, 11, 0.2)', fontSize: '0.82rem', display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                    <span style={{ color: '#FBBF24', fontWeight: 700 }}>{gap.exchange}</span>
                                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{gap.date ? gap.date.split(' ')[0] : ''}</span>
                                </div>
                                <div style={{ color: '#F8FAFC' }}>
                                    Venta de <span className="tabular-nums font-semibold">{gap.sold_qty} {gap.coin}</span> — Déficit: <span className="tabular-nums text-rose" style={{ color: '#FB7185' }}>{gap.deficit !== undefined ? (Number(gap.deficit) < 0.0001 && Number(gap.deficit) > 0 ? Number(gap.deficit).toFixed(8) : Number(gap.deficit).toFixed(4)) : ''} {gap.coin}</span>
                                </div>
                                {gap.clues && gap.clues[0] && (
                                    <div style={{ fontSize: '0.75rem', color: 'var(--brand-indigo-light)', marginTop: '0.15rem', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                                        <span>{gap.clues[0].icon || '💡'}</span>
                                        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{gap.clues[0].message}</span>
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                </div>
            )}

            <DashboardFilters
                kpis={kpis}
                statusFilter={statusFilter}
                setStatusFilter={setStatusFilter}
                startDate={startDate}
                setStartDate={setStartDate}
                endDate={endDate}
                setEndDate={setEndDate}
                availableExchanges={availableExchanges}
                selectedExchanges={selectedExchanges}
                handleToggleExchange={handleToggleExchange}
                handleSelectAllExchanges={handleSelectAllExchanges}
            />

            <DashboardAnomaliesTable
                anomalies={anomalies}
                selectedOrigins={selectedOrigins}
                setSelectedOrigins={setSelectedOrigins}
                classifying={classifying}
                handleClassifyAnomaly={handleClassifyAnomaly}
            />

            <CertExcelCrossAuditAlerts
                discrepancies={certDiscrepancies}
                onResolve={handleResolveCrossAudit}
            />

            <DashboardMetrics
                kpis={kpis}
                modalSpread={modalSpread}
                formatCurrency={formatCurrency}
            />

            <DashboardCharts
                equityCurve={equityCurve}
                dailyVol={dailyVol}
                exchangeDist={exchangeDist}
                equityInterval={equityInterval}
                setEquityInterval={setEquityInterval}
            />
        </div>
    );
}

export default Dashboard;
