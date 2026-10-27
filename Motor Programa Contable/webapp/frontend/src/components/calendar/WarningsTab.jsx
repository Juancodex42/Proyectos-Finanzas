import React, { useState } from 'react';
import {
  CheckCircle2, AlertTriangle, Compass, Link2, Search,
  HelpCircle, Wand2, ChevronDown, ChevronUp, Layers, RefreshCw,
  Info, X
} from 'lucide-react';
import CalendarMonthGrid from './CalendarMonthGrid';
import GapCard from './GapCard';
import WarningsSummaryCards from './WarningsSummaryCards';
import WarningsCompassView from './WarningsCompassView';
import WarningsExchangeView from './WarningsExchangeView';

const WarningsTab = ({
  portfolioScope,
  setPortfolioScope,
  modesData,
  allWarningsList = [],
  activeSummary = { with_probable_match: 0, missing_data_source: 0, unknown_origin: 0 },
  exchangeFreshness = [],
  custodyDeficits = [],
  sourceAlerts = [],
  declaredSources = [],
  apiBase,
  onRefreshWarnings,
  monthlyCustody = {},
  selectedYear,
  setSelectedYear,
  availableYears = [],
  certificationsList = [],
  onResolve,
  onOpenPonteAlDiaModal,
  onSwitchTab,
  showToast,
  loadingWarnings
}) => {
  const [viewGroupBy, setViewGroupBy] = useState('compass'); // 'compass' | 'exchange'
  const [selectedExchangeFilter, setSelectedExchangeFilter] = useState('ALL');
  const [expandedExchanges, setExpandedExchanges] = useState({});
  const [expandedCategories, setExpandedCategories] = useState({ probable_match: true, missing_data: true, unknown: true });
  const [exchangeLimits, setExchangeLimits] = useState({});
  const [categoryLimits, setCategoryLimits] = useState({});
  const [showApiNotice, setShowApiNotice] = useState(() => {
    try {
      return localStorage.getItem('crypto_tax_hide_api_limitations_notice') !== 'true';
    } catch {
      return true;
    }
  });

  const handleDismissNotice = () => {
    try {
      localStorage.setItem('crypto_tax_hide_api_limitations_notice', 'true');
    } catch {
      // ignore
    }
    setShowApiNotice(false);
  };

  const toggleExchangeExpand = (exName) => {
    setExpandedExchanges((prev) => ({
      ...prev,
      [exName]: prev[exName] !== undefined ? !prev[exName] : false
    }));
  };

  const toggleCategoryExpand = (catId) => {
    setExpandedCategories((prev) => ({
      ...prev,
      [catId]: prev[catId] !== undefined ? !prev[catId] : false
    }));
  };

  const loadMoreForExchange = (exName) => {
    setExchangeLimits((prev) => ({
      ...prev,
      [exName]: (prev[exName] || 10) + 15
    }));
  };

  const loadMoreForCategory = (catId) => {
    setCategoryLimits((prev) => ({
      ...prev,
      [catId]: (prev[catId] || 10) + 15
    }));
  };

  // Grouping by Exchange
  const groupedExchanges = allWarningsList.reduce((acc, item) => {
    const ex = item.exchange || 'Otros Exchanges';
    if (!acc[ex]) acc[ex] = [];
    acc[ex].push(item);
    return acc;
  }, {});
  const exchangeNames = Object.keys(groupedExchanges);
  const filteredNames = selectedExchangeFilter === 'ALL'
    ? exchangeNames
    : exchangeNames.filter((name) => name === selectedExchangeFilter);

  // Grouping by Diagnostic Category
  const diagnosticCategories = [
    {
      id: 'probable_match',
      title: 'Transferencias y Arbitrajes Cruzados Detectados',
      icon: Link2,
      color: '#10B981',
      bg: 'rgba(16, 185, 129, 0.15)',
      description: 'Se encontraron retiros en otros exchanges en fechas cercanas y con montos coincidentes. Muy probablemente compraste en otra plataforma y la transferiste para venderla acá.',
      items: allWarningsList.filter((item) => item.category === 'probable_match')
    },
    {
      id: 'missing_data',
      title: 'Falta Historial de Depósitos o Conversiones',
      icon: Search,
      color: '#F59E0B',
      bg: 'rgba(245, 158, 11, 0.15)',
      description: 'La venta ocurrió en un exchange donde no hay extracto de depósitos blockchain ni conversiones internas registrado. Descargá esos reportes desde tu cuenta.',
      items: allWarningsList.filter((item) => item.category === 'missing_data' || !item.category)
    },
    {
      id: 'unknown',
      title: 'Origen No Registrado / A Investigar',
      icon: HelpCircle,
      color: '#818CF8',
      bg: 'rgba(129, 140, 248, 0.15)',
      description: 'No se encontraron retiros coincidentes en ningún exchange registrado. Posible ingreso desde billetera personal (cold wallet / Metamask), airdrop o saldo previo no declarado.',
      items: allWarningsList.filter((item) => item.category === 'unknown')
    }
  ];

  return (
    <div>
      {/* Portfolio Scope Banner & KPI Cards */}
      <WarningsSummaryCards
        portfolioScope={portfolioScope}
        setPortfolioScope={setPortfolioScope}
        modesData={modesData}
        allWarningsList={allWarningsList}
        activeSummary={activeSummary}
        exchangeFreshness={exchangeFreshness}
        custodyDeficits={custodyDeficits}
        sourceAlerts={sourceAlerts}
        declaredSources={declaredSources}
        apiBase={apiBase}
        onRefreshWarnings={onRefreshWarnings}
        selectedYear={selectedYear}
        showToast={showToast}
        loadingWarnings={loadingWarnings}
      />

      {/* Month Timeline Grid */}
      <CalendarMonthGrid
        mode="warnings"
        selectedYear={selectedYear}
        setSelectedYear={setSelectedYear}
        availableYears={availableYears}
        allWarningsList={allWarningsList}
        certificationsList={certificationsList}
        monthlyCustody={monthlyCustody}
        onSelectGap={onResolve}
        onOpenPonteAlDiaModal={onOpenPonteAlDiaModal}
        onSwitchTab={onSwitchTab}
        loadingWarnings={loadingWarnings}
      />

      {/* API Limitations Informative Card */}
      {showApiNotice && (
        <div
          style={{
            marginBottom: '1.25rem',
            padding: '1.15rem 1.35rem',
            borderRadius: 'var(--radius-md)',
            background: 'linear-gradient(135deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.9) 100%)',
            border: '1px solid rgba(99, 102, 241, 0.35)',
            boxShadow: '0 4px 15px rgba(0, 0, 0, 0.25)',
            position: 'relative'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '1rem' }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.85rem' }}>
              <div
                style={{
                  width: '36px',
                  height: '36px',
                  borderRadius: '8px',
                  background: 'rgba(99, 102, 241, 0.15)',
                  border: '1px solid rgba(99, 102, 241, 0.3)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#818CF8',
                  flexShrink: 0,
                  marginTop: '0.1rem'
                }}
              >
                <Info size={20} />
              </div>
              <div>
                <h4 style={{ fontSize: '0.98rem', fontWeight: 700, color: '#F8FAFC', margin: '0 0 0.35rem' }}>
                  ¿Por qué la API no trajo todo automáticamente?
                </h4>
                <p style={{ fontSize: '0.84rem', color: '#CBD5E1', lineHeight: 1.55, margin: '0 0 0.45rem' }}>
                  Las conexiones automáticas por API registran compras y ventas del mercado tradicional (Spot), depósitos y retiros blockchain. Sin embargo, <strong>Bybit y OKX restringen las órdenes P2P vía API únicamente a comerciantes verificados</strong> (los usuarios comunes deben importar el CSV de órdenes P2P), y en apps móviles los canjes rápidos ("Convertir") requieren descargar el extracto de conversiones.
                </p>
                <div style={{
                  background: 'rgba(15, 23, 42, 0.6)',
                  border: '1px solid rgba(148, 163, 184, 0.15)',
                  borderRadius: '6px',
                  padding: '0.55rem 0.75rem',
                  marginBottom: '0.65rem'
                }}>
                  <p style={{ fontSize: '0.82rem', color: '#E2E8F0', lineHeight: 1.5, margin: 0 }}>
                    💡 <strong style={{ color: '#FBBF24' }}>¿Cómo se resuelve de forma automática?</strong> Aunque la API no los envíe, <strong>el exchange sí guarda todos los canjes de la App en sus reportes descargables</strong>. Descargá el historial en CSV o Excel desde la web del exchange y arrastralo acá: el sistema lo leerá y conciliará todo automáticamente sin que tengas que cargar nada a mano.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={handleDismissNotice}
                  style={{
                    background: 'none',
                    border: 'none',
                    padding: 0,
                    color: 'var(--brand-indigo-light)',
                    fontSize: '0.78rem',
                    fontWeight: 600,
                    cursor: 'pointer',
                    textDecoration: 'underline',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '0.25rem'
                  }}
                >
                  Entendido, no volver a mostrar
                </button>
              </div>
            </div>
            <button
              type="button"
              onClick={handleDismissNotice}
              title="Cerrar aviso"
              style={{
                background: 'rgba(255, 255, 255, 0.05)',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                borderRadius: '6px',
                color: 'var(--text-muted)',
                cursor: 'pointer',
                padding: '0.35rem',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0
              }}
            >
              <X size={15} />
            </button>
          </div>
        </div>
      )}

      {/* Grouped Warnings List */}
      <div className="card-surface" style={{ padding: '1.5rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '1rem' }}>
          <h3 style={{ fontSize: '1.1rem', fontWeight: 700, margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <AlertTriangle size={18} color="#F59E0B" />
            Inconsistencias y Huecos FIFO ({allWarningsList.length})
          </h3>

          <div style={{ display: 'flex', gap: '0.4rem', background: '#0D131F', padding: '0.25rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
            <button
              type="button"
              onClick={() => setViewGroupBy('compass')}
              style={{
                padding: '0.35rem 0.75rem',
                borderRadius: 'var(--radius-sm)',
                border: 'none',
                background: viewGroupBy === 'compass' ? 'var(--brand-indigo)' : 'transparent',
                color: viewGroupBy === 'compass' ? '#FFFFFF' : 'var(--text-secondary)',
                fontWeight: 600,
                fontSize: '0.78rem',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '0.35rem'
              }}
            >
              <Compass size={14} /> Brújula Inteligente
            </button>
            <button
              type="button"
              onClick={() => setViewGroupBy('exchange')}
              style={{
                padding: '0.35rem 0.75rem',
                borderRadius: 'var(--radius-sm)',
                border: 'none',
                background: viewGroupBy === 'exchange' ? 'var(--brand-indigo)' : 'transparent',
                color: viewGroupBy === 'exchange' ? '#FFFFFF' : 'var(--text-secondary)',
                fontWeight: 600,
                fontSize: '0.78rem',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '0.35rem'
              }}
            >
              <Layers size={14} /> Por Exchange
            </button>
          </div>
        </div>

        {loadingWarnings ? (
          <div style={{ textAlign: 'center', padding: '3.5rem 1rem', color: 'var(--text-secondary)' }}>
            <RefreshCw size={28} className="spin" color="var(--brand-indigo-light)" style={{ margin: '0 auto 0.75rem' }} />
            <h4 style={{ fontSize: '1.05rem', color: '#F8FAFC', margin: '0 0 0.25rem' }}>Auditando inconsistencias del ejercicio {selectedYear}...</h4>
            <p style={{ fontSize: '0.82rem', margin: 0, color: 'var(--text-muted)' }}>Procesando tenencia de cartera y pistas de arbitraje...</p>
          </div>
        ) : allWarningsList.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '3rem 1rem', color: 'var(--text-muted)' }}>
            <CheckCircle2 size={42} color="#34D399" style={{ margin: '0 auto 0.75rem', opacity: 0.9 }} />
            <h4 style={{ fontSize: '1.1rem', color: '#F8FAFC', margin: '0 0 0.25rem' }}>¡Historial 100% Consistente!</h4>
            <p style={{ fontSize: '0.85rem', margin: 0 }}>Todas tus transacciones cuentan con compras previas registradas y respaldo formal.</p>
          </div>
        ) : viewGroupBy === 'compass' ? (
          <WarningsCompassView
            diagnosticCategories={diagnosticCategories}
            expandedCategories={expandedCategories}
            toggleCategoryExpand={toggleCategoryExpand}
            categoryLimits={categoryLimits}
            loadMoreForCategory={loadMoreForCategory}
            onResolve={onResolve}
          />
        ) : (
          <WarningsExchangeView
            exchangeNames={exchangeNames}
            groupedExchanges={groupedExchanges}
            filteredNames={filteredNames}
            selectedExchangeFilter={selectedExchangeFilter}
            setSelectedExchangeFilter={setSelectedExchangeFilter}
            expandedExchanges={expandedExchanges}
            toggleExchangeExpand={toggleExchangeExpand}
            exchangeLimits={exchangeLimits}
            loadMoreForExchange={loadMoreForExchange}
            onResolve={onResolve}
          />
        )}
      </div>
    </div>
  );
};

export default WarningsTab;
