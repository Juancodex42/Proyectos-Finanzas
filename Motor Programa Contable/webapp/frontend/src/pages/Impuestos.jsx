import { useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { Settings as SettingsIcon, RefreshCw } from 'lucide-react';
import config from '../config';
import TaxKPICards from '../components/tax/TaxKPICards';
import TaxThresholdScale from '../components/tax/TaxThresholdScale';
import TaxMonthlyLedger from '../components/tax/TaxMonthlyLedger';
import TaxConfigDrawer, { DEFAULT_TAX_SETTINGS, resolveIibbBracket } from '../components/tax/TaxConfigDrawer';
import TaxEmptyState from '../components/tax/TaxEmptyState';

const API_BASE = `${config.API_URL}/api`;

const formatARS = (val) => new Intl.NumberFormat('es-AR', {
  style: 'currency', currency: 'ARS', maximumFractionDigits: 2
}).format(val || 0);

const Impuestos = () => {
  const location = useLocation();
  const searchParams = new URLSearchParams(location.search);
  const paramYear = searchParams.get('year') ? parseInt(searchParams.get('year'), 10) : null;

  const [selectedYear, setSelectedYear] = useState(paramYear || new Date().getFullYear());
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showConfigModal, setShowConfigModal] = useState(false);
  const [settingsForm, setSettingsForm] = useState(DEFAULT_TAX_SETTINGS);
  const [savingSettings, setSavingSettings] = useState(false);
  const [reportError, setReportError] = useState(null);
  const [scopeFilter, setScopeFilter] = useState('all');

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const y = params.get('year') ? parseInt(params.get('year'), 10) : null;
    if (y && !isNaN(y)) setSelectedYear(y);
  }, [location.search]);

  const fetchTaxReport = async (year, signal) => {
    const isSignal = signal instanceof AbortSignal;
    setLoading(true);
    setReport(null);
    setReportError(null);
    try {
      const res = await fetch(`${API_BASE}/taxes/report?year=${year}`, isSignal ? { signal } : {});
      if (!res.ok) throw new Error(`Error del servidor (${res.status})`);
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      setReport(data);
      if (
        (!data.is_fully_certified && !data.is_partially_certified && scopeFilter === 'certified') ||
        (data.is_fully_certified && scopeFilter === 'provisional')
      ) {
        setScopeFilter('all');
      }
      if (data.settings) setSettingsForm(data.settings);
    } catch (err) {
      if (err.name === 'AbortError') return;
      console.error('Error fetching tax report:', err);
      setReportError(err.message || 'Error al conectar con el servidor contable');
    } finally {
      if (!(isSignal && signal.aborted)) setLoading(false);
    }
  };

  useEffect(() => {
    const controller = new AbortController();
    fetchTaxReport(selectedYear, controller.signal);
    return () => controller.abort();
  }, [selectedYear]);

  const handleSaveSettings = async (e) => {
    e.preventDefault();
    setSavingSettings(true);
    try {
      const payload = {
        ...settingsForm,
        year: Number(settingsForm.year),
        ganancias_deduccion: Number(settingsForm.ganancias_deduccion),
        ganancias_alicuota: Number(settingsForm.ganancias_alicuota),
        iibb_tramo1_limite: Number(settingsForm.iibb_tramo1_limite),
        iibb_tramo1_alicuota: Number(settingsForm.iibb_tramo1_alicuota),
        iibb_tramo2_limite: Number(settingsForm.iibb_tramo2_limite),
        iibb_tramo2_alicuota: Number(settingsForm.iibb_tramo2_alicuota),
        iibb_tramo3_alicuota: Number(settingsForm.iibb_tramo3_alicuota),
        ganancias_estimadas_fallback_pct: Number(settingsForm.ganancias_estimadas_fallback_pct),
        usd_ars_exchange_rate: Number(settingsForm.usd_ars_exchange_rate),
        ...(settingsForm.use_ganancias_fallback !== undefined && {
          use_ganancias_fallback: Number(settingsForm.use_ganancias_fallback)
        })
      };
      const res = await fetch(`${API_BASE}/taxes/settings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        setShowConfigModal(false);
        fetchTaxReport(selectedYear);
      } else {
        const errData = await res.json().catch(() => ({}));
        const msg = errData.error || errData.message || `Error al guardar configuración (${res.status})`;
        setReportError(msg);
        alert(msg);
      }
    } catch (err) {
      console.error('Error saving tax settings:', err);
      const msg = err.message || 'Error de conexión al guardar la configuración fiscal';
      setReportError(msg);
      alert(msg);
    } finally {
      setSavingSettings(false);
    }
  };

  const isDiferencial = report?.settings?.iibb_base_calculo === 'diferencial';

  const currentMonths = (report?.monthly_data || []).map((m) => {
    const sells = scopeFilter === 'certified' ? (m.certified_sells_ars ?? m.sells_ars ?? 0)
      : scopeFilter === 'provisional' ? (m.provisional_sells_ars ?? m.sells_ars ?? 0) : (m.sells_ars ?? 0);
    const pnl = scopeFilter === 'certified' ? (m.certified_pnl_ars ?? m.pnl_ars ?? 0)
      : scopeFilter === 'provisional' ? (m.provisional_pnl_ars ?? m.pnl_ars ?? 0) : (m.pnl_ars ?? 0);
    const base_imponible_iibb = isDiferencial ? Math.max(0, pnl) : sells;
    const { tramo_iibb, alicuota_iibb } = resolveIibbBracket(sells, report);
    return { ...m, sells_volume: sells, base_imponible_iibb, tramo_iibb, alicuota_iibb };
  });

  const activeMetrics = (() => {
    if (!report) return {};
    if (scopeFilter === 'certified') {
      const scopeObj = report.certified || {};
      const sells = scopeObj.sells_ars || 0;
      const base_imponible_iibb = scopeObj.base_iibb ?? (isDiferencial ? Math.max(0, scopeObj.ganancia_neta || 0) : sells);
      const bracket = resolveIibbBracket(sells, report);
      return {
        ...scopeObj,
        sells_volume: sells,
        base_iibb: base_imponible_iibb,
        base_imponible_iibb,
        tramo_iibb: bracket.tramo_iibb,
        alicuota_iibb: bracket.alicuota_iibb
      };
    }
    if (scopeFilter === 'provisional') {
      const scopeObj = report.provisional || {};
      const sells = scopeObj.sells_ars || 0;
      const base_iibb = scopeObj.base_iibb ?? (isDiferencial ? Math.max(0, scopeObj.ganancia_neta || 0) : sells);
      const bracket = resolveIibbBracket(sells, report);
      return {
        ...scopeObj,
        sells_volume: sells,
        base_iibb,
        base_imponible_iibb: base_iibb,
        tramo_iibb: bracket.tramo_iibb,
        alicuota_iibb: bracket.alicuota_iibb
      };
    }
    const sells = report.total_sells_ars ?? report.total_ventas ?? 0;
    const base_iibb = report.base_iibb ?? (isDiferencial ? Math.max(0, report.ganancia_neta || 0) : sells);
    const bracket = resolveIibbBracket(sells, report);
    return {
      ...report,
      sells_volume: sells,
      base_iibb,
      base_imponible_iibb: base_iibb,
      tramo_iibb: report.tramo_iibb ? report.tramo_iibb : bracket.tramo_iibb,
      alicuota_iibb: report.alicuota_iibb ? report.alicuota_iibb : bracket.alicuota_iibb
    };
  })();

  const scopedReport = report ? {
    ...report,
    monthly_data: currentMonths,
    sells_volume: activeMetrics.sells_volume,
    tramo_iibb: activeMetrics.tramo_iibb,
    alicuota_iibb: activeMetrics.alicuota_iibb
  } : null;

  return (
    <div style={{ padding: '1.75rem 2rem', color: 'var(--text-primary)', maxWidth: '1440px', margin: '0 auto' }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1.25rem' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.25rem' }}>
            <div style={{ width: '10px', height: '10px', borderRadius: '50%', backgroundColor: '#4F46E5', boxShadow: '0 0 10px rgba(79, 70, 229, 0.7)' }} />
            <h1 style={{ fontSize: '1.85rem', fontWeight: 800, letterSpacing: '-0.02em', color: '#F8FAFC', margin: 0 }}>
              Liquidación Impositiva & DDJJ
            </h1>
          </div>
          <p style={{ color: 'var(--text-secondary)', margin: 0, fontSize: '0.9rem' }}>
            Determinación de Ganancias Cedulares (15%) e Ingresos Brutos (IIBB) con respaldo de Auditoría C.P.N.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', background: 'var(--bg-panel)', padding: '0.35rem 0.65rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)', gap: '0.5rem' }}>
            <span style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', fontWeight: 600 }}>Ejercicio Fiscal:</span>
            <select value={selectedYear} onChange={(e) => setSelectedYear(Number(e.target.value))} style={{ background: 'transparent', border: 'none', color: '#F8FAFC', fontWeight: 700, fontSize: '0.9rem', cursor: 'pointer', outline: 'none' }}>
              {[2022, 2023, 2024, 2025, 2026].map(y => <option key={y} value={y} style={{ background: '#182238', color: '#F8FAFC' }}>{y}</option>)}
            </select>
          </div>
          <button onClick={() => setShowConfigModal(true)} className="btn-secondary" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.85rem', padding: '0.5rem 0.9rem' }}>
            <SettingsIcon size={15} /><span>Configurar Alícuotas</span>
          </button>
        </div>
      </header>

      {reportError && (
        <div style={{ padding: '1rem 1.25rem', marginBottom: '1.5rem', borderRadius: '8px', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.3)', color: '#f87171', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div><strong>Error al cargar el reporte fiscal:</strong> {reportError}</div>
          <button onClick={() => fetchTaxReport(selectedYear)} className="btn-secondary" style={{ fontSize: '0.85rem', padding: '0.35rem 0.75rem' }}>Reintentar</button>
        </div>
      )}

      {!loading && report && report.tx_count > 0 && (
        <div style={{ marginBottom: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div style={{
            background: report.is_fully_certified ? 'rgba(16, 185, 129, 0.08)' : report.is_partially_certified ? 'rgba(245, 158, 11, 0.08)' : 'rgba(99, 102, 241, 0.08)',
            border: `1px solid ${report.is_fully_certified ? 'rgba(16, 185, 129, 0.25)' : report.is_partially_certified ? 'rgba(245, 158, 11, 0.25)' : 'rgba(99, 102, 241, 0.25)'}`,
            borderRadius: 'var(--radius-md)', padding: '1rem 1.25rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem'
          }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.2rem' }}>
                <span className={`badge ${report.is_fully_certified ? 'badge-emerald' : report.is_partially_certified ? 'badge-amber' : 'badge-indigo'}`}>
                  {report.is_fully_certified ? '✓ 100% Auditado C.P.N.' : report.is_partially_certified ? '⚖ Período Mixto (Auditado + Provisorio)' : 'ℹ Ejercicio Provisorio'}
                </span>
                <span style={{ fontSize: '0.9rem', fontWeight: 700, color: '#F8FAFC' }}>
                  {report.is_fully_certified
                    ? `Ejercicio ${selectedYear} respaldado íntegramente por ${report.certifications_included?.length || 0} Certificaciones Contables`
                    : report.is_partially_certified
                      ? `Ejercicio ${selectedYear} con ${report.certified_tx_count} transacciones auditadas y ${report.provisional_tx_count} provisorias`
                      : `Ejercicio ${selectedYear} sin certificaciones contables emitidas aún`}
                </span>
              </div>
              <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                {report.certifications_included?.length > 0 ? (
                  <>Certificaciones vinculadas: {report.certifications_included.map((c, idx) => <span key={c.id || idx} style={{ color: '#818CF8', fontWeight: 600, marginRight: '0.5rem' }}>[{c.title} - {c.cpa_name || 'C.P.N.'}]</span>)}</>
                ) : 'Las estimaciones provisorias están sujetas a reajuste una vez cargadas las certificaciones contables en el Calendario.'}
              </p>
            </div>

            <div style={{ display: 'flex', background: 'var(--bg-panel)', padding: '0.25rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)', gap: '0.25rem' }}>
              <button type="button" onClick={() => setScopeFilter('all')} style={{ background: scopeFilter === 'all' ? 'var(--brand-indigo)' : 'transparent', color: scopeFilter === 'all' ? '#FFFFFF' : 'var(--text-secondary)', border: 'none', borderRadius: 'var(--radius-sm)', padding: '0.35rem 0.75rem', fontSize: '0.78rem', fontWeight: 600, cursor: 'pointer' }}>
                Consolidado ({report.tx_count})
              </button>
              <button type="button" onClick={() => setScopeFilter('certified')} disabled={!report.certified_tx_count} style={{ background: scopeFilter === 'certified' ? '#059669' : 'transparent', color: scopeFilter === 'certified' ? '#FFFFFF' : report.certified_tx_count ? 'var(--text-secondary)' : 'var(--text-muted)', border: 'none', borderRadius: 'var(--radius-sm)', padding: '0.35rem 0.75rem', fontSize: '0.78rem', fontWeight: 600, cursor: report.certified_tx_count ? 'pointer' : 'not-allowed' }}>
                Auditado CPN ({report.certified_tx_count || 0})
              </button>
              <button type="button" onClick={() => setScopeFilter('provisional')} disabled={!report.provisional_tx_count} style={{ background: scopeFilter === 'provisional' ? '#D97706' : 'transparent', color: scopeFilter === 'provisional' ? '#FFFFFF' : report.provisional_tx_count ? 'var(--text-secondary)' : 'var(--text-muted)', border: 'none', borderRadius: 'var(--radius-sm)', padding: '0.35rem 0.75rem', fontSize: '0.78rem', fontWeight: 600, cursor: report.provisional_tx_count ? 'pointer' : 'not-allowed' }}>
                Provisorio ({report.provisional_tx_count || 0})
              </button>
            </div>
          </div>
        </div>
      )}

      {loading ? (
        <div style={{ padding: '4rem 0', textAlign: 'center', color: 'var(--text-secondary)' }}>
          <RefreshCw className="spin" size={24} style={{ margin: '0 auto 0.75rem auto' }} />
          <p style={{ margin: 0, fontSize: '0.9rem' }}>Calculando base imponible y retenciones fiscales...</p>
        </div>
      ) : scopedReport ? (
        scopedReport.tx_count > 0 ? (
          <>
            <TaxKPICards report={scopedReport} scopeFilter={scopeFilter} formatARS={formatARS} tramoIibb={activeMetrics.tramo_iibb} alicuotaIibb={activeMetrics.alicuota_iibb} activeMetrics={activeMetrics} />
            <TaxThresholdScale report={scopedReport} scopeFilter={scopeFilter} selectedYear={selectedYear} formatARS={formatARS} baseIibb={activeMetrics.base_iibb} tramoIibb={activeMetrics.tramo_iibb} alicuotaIibb={activeMetrics.alicuota_iibb} activeMetrics={activeMetrics} />
            <TaxMonthlyLedger report={scopedReport} scopeFilter={scopeFilter} selectedYear={selectedYear} formatARS={formatARS} activeMetrics={activeMetrics} />
          </>
        ) : <TaxEmptyState selectedYear={selectedYear} />
      ) : null}

      <TaxConfigDrawer
        show={showConfigModal} onClose={() => setShowConfigModal(false)}
        settingsForm={settingsForm} setSettingsForm={setSettingsForm}
        handleSaveSettings={handleSaveSettings} savingSettings={savingSettings}
      />
    </div>
  );
};

export default Impuestos;
