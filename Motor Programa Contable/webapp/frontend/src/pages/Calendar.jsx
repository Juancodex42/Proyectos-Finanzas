import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import config from '../config';
import CalendarHeader from '../components/calendar/CalendarHeader';
import CertificationsTab from '../components/calendar/CertificationsTab';
import WarningsTab from '../components/calendar/WarningsTab';
import CalendarModals from '../components/calendar/CalendarModals';
import CalendarToast from '../components/calendar/CalendarToast';
import { parseCleanDate, getYearCertificationBrackets } from '../components/calendar/calendarUtils';

const API_BASE = `${config.API_URL}/api`;

const Calendar = () => {
  const location = useLocation();
  const searchParams = new URLSearchParams(location.search);
  const initialTab = searchParams.get('tab') === 'warnings' ? 'warnings' : 'certifications';
  const paramYear = searchParams.get('year') ? parseInt(searchParams.get('year'), 10) : null;

  const [activeTab, setActiveTab] = useState(initialTab);
  const [loading, setLoading] = useState(true);
  const [loadingWarnings, setLoadingWarnings] = useState(false);
  const [selectedYear, setSelectedYear] = useState(paramYear || new Date().getFullYear());

  const [certData, setCertData] = useState({
    certifications: [],
    summary: { status: 'pending', total_count: 0, latest_end_date: null, uncertified_days: 0 }
  });

  const [gaps, setGaps] = useState([]);
  const [gapsSummary, setGapsSummary] = useState({ with_probable_match: 0, missing_data_source: 0, unknown_origin: 0 });
  const [modesData, setModesData] = useState(null);
  const [portfolioScope, setPortfolioScope] = useState('global');
  const [exchangeFreshness, setExchangeFreshness] = useState([]);
  const [custodyDeficits, setCustodyDeficits] = useState([]);
  const [sourceAlerts, setSourceAlerts] = useState([]);
  const [declaredSources, setDeclaredSources] = useState([]);
  const [monthlyCustody, setMonthlyCustody] = useState({});

  // Modals & Toast State
  const [showAddModal, setShowAddModal] = useState(false);
  const [addModalPrefill, setAddModalPrefill] = useState(null);
  const [showReplaceModal, setShowReplaceModal] = useState(false);
  const [showResolverModal, setShowResolverModal] = useState(false);
  const [selectedWarning, setSelectedWarning] = useState(null);
  const [showPonteAlDiaModal, setShowPonteAlDiaModal] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState({ show: false, id: null, title: '', deleting: false });
  const [toast, setToast] = useState({ show: false, message: '', type: 'info' });
  const toastTimerRef = useRef(null);
  const warningsAbortRef = useRef(null);
  const warningsRequestIdRef = useRef(0);
  const selectedYearRef = useRef(selectedYear);
  selectedYearRef.current = selectedYear;
  const portfolioScopeRef = useRef(portfolioScope);
  portfolioScopeRef.current = portfolioScope;

  const showToast = useCallback((message, type = 'info') => {
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    setToast({ show: true, message, type });
    toastTimerRef.current = setTimeout(() => {
      setToast({ show: false, message: '', type: 'info' });
      toastTimerRef.current = null;
    }, 4500);
  }, []);

  useEffect(() => {
    return () => {
      if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
      if (warningsAbortRef.current) warningsAbortRef.current.abort();
    };
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    if (params.get('tab') === 'warnings') {
      setActiveTab('warnings');
    } else if (params.get('tab') === 'certifications') {
      setActiveTab('certifications');
    }
    const y = params.get('year') ? parseInt(params.get('year'), 10) : null;
    if (y && !isNaN(y)) setSelectedYear(y);
  }, [location.search]);

  const fetchCertifications = async (isSilent = false) => {
    if (!isSilent) setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/certifications`);
      const data = await res.json();
      if (data.success || data.certifications) {
        setCertData({
          certifications: data.certifications || [],
          summary: data.summary || { status: 'pending', total_count: 0, latest_end_date: null, uncertified_days: 0 }
        });
      }
    } catch (err) {
      console.error('Error fetching certifications:', err);
    } finally {
      if (!isSilent) setLoading(false);
    }
  };

  const fetchWarningsAndGaps = useCallback(async (yearToFetch, scopeToFetch) => {
    const targetYear = yearToFetch !== undefined ? yearToFetch : selectedYearRef.current;
    const targetScope = scopeToFetch !== undefined ? scopeToFetch : portfolioScopeRef.current;
    const reqId = ++warningsRequestIdRef.current;
    if (warningsAbortRef.current) {
      warningsAbortRef.current.abort();
    }
    const controller = new AbortController();
    warningsAbortRef.current = controller;

    setLoadingWarnings(true);
    try {
      const url = targetYear ? `${API_BASE}/reports/gaps?year=${targetYear}&mode=${targetScope}` : `${API_BASE}/reports/gaps?mode=${targetScope}`;
      const res = await fetch(url, { signal: controller.signal });
      const data = await res.json();
      if (reqId !== warningsRequestIdRef.current) return;
      if (data.success || data.status === 'success' || data.gaps) {
        setGaps(data.gaps || []);
        setGapsSummary(data.summary || { with_probable_match: 0, missing_data_source: 0, unknown_origin: 0 });
        setModesData(data.modes || null);
        setExchangeFreshness(data.exchange_freshness || []);
        setCustodyDeficits(data.custody_deficits || []);
        setSourceAlerts(data.source_alerts || []);
        setDeclaredSources(data.declared_sources || []);
        setMonthlyCustody(data.monthly_custody || {});
      }
    } catch (err) {
      if (err.name === 'AbortError' || controller.signal.aborted) return;
      console.error('Error fetching warnings and gaps:', err);
    } finally {
      if (reqId === warningsRequestIdRef.current) {
        setLoadingWarnings(false);
      }
    }
  }, []);

  useEffect(() => {
    fetchCertifications();
  }, []);

  useEffect(() => {
    fetchWarningsAndGaps(selectedYear, portfolioScope);
  }, [selectedYear, portfolioScope, fetchWarningsAndGaps]);

  const handleDeleteConfirm = async () => {
    if (!deleteConfirm.id) return;
    setDeleteConfirm((prev) => ({ ...prev, deleting: true }));
    try {
      const res = await fetch(`${API_BASE}/certifications/${deleteConfirm.id}`, { method: 'DELETE' });
      const result = await res.json();
      if (res.ok && result.success) {
        showToast('Certificación eliminada con éxito.', 'success');
        setDeleteConfirm({ show: false, id: null, title: '', deleting: false });
        fetchCertifications();
        fetchWarningsAndGaps();
        window.dispatchEvent(new Event('certifications_updated'));
      } else {
        showToast(result.error || 'Error al eliminar certificación', 'error');
        setDeleteConfirm((prev) => ({ ...prev, deleting: false }));
      }
    } catch {
      showToast('Error de conexión', 'error');
      setDeleteConfirm((prev) => ({ ...prev, deleting: false }));
    }
  };

  const handleSyncCoverage = async () => {
    try {
      const res = await fetch(`${API_BASE}/certifications/sync_all_tables`, { method: 'POST' });
      const data = await res.json();
      if (!data?.success) await fetch(`${API_BASE}/certifications/sync`, { method: 'POST' });
      fetchCertifications();
      fetchWarningsAndGaps();
      const ins = data?.total_inserted || 0;
      showToast(ins > 0 ? `Sincronización completa: ${ins} transacciones certificadas actualizadas.` : 'Sincronización de cobertura legal realizada con éxito.', 'success');
    } catch {
      showToast('Error al sincronizar cobertura', 'error');
    }
  };

  const allWarningsList = useMemo(() => {
    if (modesData && modesData[portfolioScope]) {
      return (modesData[portfolioScope].gaps || []).map((g) => ({ ...g, isGap: true }));
    }
    return gaps.map((g) => ({ ...g, isGap: true }));
  }, [modesData, portfolioScope, gaps]);

  const activeSummary = useMemo(() => {
    if (modesData && modesData[portfolioScope]) {
      return modesData[portfolioScope].summary || { with_probable_match: 0, missing_data_source: 0, unknown_origin: 0 };
    }
    return gapsSummary;
  }, [modesData, portfolioScope, gapsSummary]);

  const certificationsList = useMemo(() => {
    return Array.isArray(certData?.certifications) ? certData.certifications : [];
  }, [certData]);

  const availableYears = useMemo(() => {
    const currentYr = new Date().getFullYear();
    const certYears = certificationsList.flatMap((c) => [
      parseCleanDate(c?.start_date)?.getFullYear(),
      parseCleanDate(c?.end_date, true)?.getFullYear()
    ]).filter((y) => y && !isNaN(y));
    const gapYears = allWarningsList.map((g) => {
      const d = g.date ? new Date(g.date) : null;
      return d && !isNaN(d.getTime()) ? d.getFullYear() : null;
    }).filter((y) => y && !isNaN(y));
    return Array.from(new Set([...Array.from({ length: 15 }, (_, i) => currentYr - 10 + i), ...certYears, ...gapYears])).sort((a, b) => a - b);
  }, [certificationsList, allWarningsList]);

  const activeBrackets = useMemo(() => {
    return getYearCertificationBrackets(selectedYear, certificationsList);
  }, [selectedYear, certificationsList]);

  const activeMonthlyCustody = useMemo(() => {
    if (modesData && modesData[portfolioScope]?.monthly_custody) {
      return modesData[portfolioScope].monthly_custody;
    }
    return monthlyCustody;
  }, [modesData, portfolioScope, monthlyCustody]);

  return (
    <div style={{ padding: '1.75rem 2rem', maxWidth: '1400px', margin: '0 auto', color: 'var(--text-primary)' }}>
      <CalendarHeader
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        certificationsCount={certificationsList.length}
        warningsCount={allWarningsList.length}
        loading={loading}
        loadingWarnings={loadingWarnings}
        onOpenPonteAlDiaModal={() => setShowPonteAlDiaModal(true)}
        onSyncCoverage={handleSyncCoverage}
        onRefresh={() => { fetchCertifications(); fetchWarningsAndGaps(); }}
        onOpenNewCertificationModal={() => { setAddModalPrefill(null); setShowAddModal(true); }}
        onOpenReplacePeriodModal={() => setShowReplaceModal(true)}
      />

      {activeTab === 'certifications' ? (
        <CertificationsTab
          certData={certData}
          certificationsList={certificationsList}
          selectedYear={selectedYear}
          setSelectedYear={setSelectedYear}
          availableYears={availableYears}
          activeBrackets={activeBrackets}
          monthlyCustody={activeMonthlyCustody}
          apiBase={API_BASE}
          onOpenAddCertification={(prefill) => { setAddModalPrefill(prefill || null); setShowAddModal(true); }}
          onOpenReplacePeriodModal={() => setShowReplaceModal(true)}
          onDeleteClick={(id, title) => setDeleteConfirm({ show: true, id, title, deleting: false })}
        />
      ) : (
        <WarningsTab
          portfolioScope={portfolioScope}
          setPortfolioScope={setPortfolioScope}
          modesData={modesData}
          allWarningsList={allWarningsList}
          activeSummary={activeSummary}
          exchangeFreshness={exchangeFreshness}
          custodyDeficits={custodyDeficits}
          sourceAlerts={sourceAlerts}
          declaredSources={declaredSources}
          apiBase={API_BASE}
          onRefreshWarnings={() => fetchWarningsAndGaps()}
          monthlyCustody={activeMonthlyCustody}
          selectedYear={selectedYear}
          setSelectedYear={setSelectedYear}
          availableYears={availableYears}
          certificationsList={certificationsList}
          onResolve={(item) => { setSelectedWarning(item); setShowResolverModal(true); }}
          onOpenPonteAlDiaModal={() => setShowPonteAlDiaModal(true)}
          onSwitchTab={(tab) => setActiveTab(tab)}
          showToast={showToast}
          loadingWarnings={loadingWarnings}
        />
      )}

      <CalendarModals
        apiBase={API_BASE}
        showAddModal={showAddModal}
        setShowAddModal={setShowAddModal}
        addModalPrefill={addModalPrefill}
        setAddModalPrefill={setAddModalPrefill}
        showReplaceModal={showReplaceModal}
        setShowReplaceModal={setShowReplaceModal}
        showResolverModal={showResolverModal}
        setShowResolverModal={setShowResolverModal}
        selectedWarning={selectedWarning}
        setSelectedWarning={setSelectedWarning}
        showPonteAlDiaModal={showPonteAlDiaModal}
        setShowPonteAlDiaModal={setShowPonteAlDiaModal}
        deleteConfirm={deleteConfirm}
        setDeleteConfirm={setDeleteConfirm}
        handleDeleteConfirm={handleDeleteConfirm}
        allWarningsList={allWarningsList}
        fetchCertifications={fetchCertifications}
        fetchWarningsAndGaps={fetchWarningsAndGaps}
        showToast={showToast}
        selectedYear={selectedYear}
      />

      <CalendarToast toast={toast} onClose={() => setToast({ show: false, message: '', type: 'info' })} />
    </div>
  );
};

export default Calendar;
