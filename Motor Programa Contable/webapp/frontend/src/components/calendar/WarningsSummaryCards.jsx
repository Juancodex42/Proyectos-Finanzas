import React, { useState } from 'react';
import {
  Globe, Layers, CheckCircle2, AlertTriangle, Compass, Link2,
  HelpCircle, Wand2, Search, RefreshCw
} from 'lucide-react';
import config from '../../config';
import DeclareNoOperationsModal from './DeclareNoOperationsModal';
import SourceAlertsCard from './SourceAlertsCard';

const WarningsSummaryCards = ({
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
  selectedYear,
  showToast,
  loadingWarnings
}) => {
  const [declareModal, setDeclareModal] = useState({ isOpen: false, exchange: '', lastDate: '' });

  const displayYear = selectedYear
    || custodyDeficits?.[0]?.year
    || allWarningsList?.[0]?.date?.slice(0, 4)
    || new Date().getFullYear();

  const handleOpenDeclareModal = (exchange, lastDate) => {
    setDeclareModal({ isOpen: true, exchange, lastDate });
  };

  return (
    <>
      <SourceAlertsCard
        custodyDeficits={custodyDeficits}
        sourceAlerts={sourceAlerts}
        declaredSources={declaredSources}
        displayYear={displayYear}
        loadingWarnings={loadingWarnings}
        apiBase={apiBase}
        showToast={showToast}
        onRefreshWarnings={onRefreshWarnings}
        onOpenDeclareModal={handleOpenDeclareModal}
      />

      {/* Portfolio Scope Banner & Switcher */}
      <div style={{
        background: 'linear-gradient(135deg, rgba(30, 41, 59, 0.7), rgba(15, 23, 42, 0.9))',
        border: '1px solid var(--border-color)',
        borderRadius: 'var(--radius-md)',
        padding: '1rem 1.25rem',
        marginBottom: '1.25rem',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: '1rem'
      }}>
        <div>
          <div style={{ fontSize: '0.88rem', fontWeight: 700, color: '#F8FAFC', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Globe size={16} color="var(--accent-cyan)" /> Criterio de Evaluación de Inconsistencias
          </div>
          <div style={{ fontSize: '0.8rem', marginTop: '0.35rem', maxWidth: '750px', lineHeight: 1.5 }}>
            {portfolioScope === 'global' ? (
              <span style={{ color: '#A7F3D0' }}>
                ⭐ <strong>Criterio Patrimonial Real (AFIP/ARCA):</strong> Trata todos tus exchanges como un patrimonio único consolidado por período fiscal. Muestra las <strong>{loadingWarnings ? '...' : (modesData?.global?.total_gaps ?? 0)} inconsistencias reales</strong> de ventas sin compra en ninguna de tus cuentas.
              </span>
            ) : (
              <span style={{ color: '#FDE68A' }}>
                ℹ️ <strong>Auditoría por Plataforma Aislada ({loadingWarnings ? '...' : (modesData?.exchange?.total_gaps ?? 0)}):</strong> Evalúa cada exchange por separado. Muestra ventas que no tuvieron orden de compra en esa misma plataforma (requieren comprobante de origen o mapeo de transferencia interna).
              </span>
            )}
          </div>
        </div>

        <div style={{ display: 'flex', gap: '0.4rem', background: '#090D16', padding: '0.25rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
          <button
            type="button"
            onClick={() => setPortfolioScope('global')}
            title="Criterio Patrimonial Real: Muestra las únicas ventas sin compra en toda tu cartera consolidada"
            style={{
              padding: '0.45rem 0.9rem',
              borderRadius: 'var(--radius-sm)',
              border: 'none',
              background: portfolioScope === 'global' ? 'linear-gradient(135deg, #10B981, #059669)' : 'transparent',
              color: portfolioScope === 'global' ? '#FFFFFF' : 'var(--text-secondary)',
              fontWeight: 700,
              fontSize: '0.78rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
              boxShadow: portfolioScope === 'global' ? '0 2px 8px rgba(16, 185, 129, 0.35)' : 'none'
            }}
          >
            <Globe size={14} /> Cartera Global Real {modesData?.global ? `(${modesData.global.total_gaps})` : ''}
          </button>
          <button
            type="button"
            onClick={() => setPortfolioScope('exchange')}
            title="Auditoría por Exchange: Evalúa plataformas de forma aislada. La mayoría son traspasos entre cuentas que a nivel global están cubiertos."
            style={{
              padding: '0.45rem 0.9rem',
              borderRadius: 'var(--radius-sm)',
              border: 'none',
              background: portfolioScope === 'exchange' ? 'linear-gradient(135deg, #F59E0B, #D97706)' : 'transparent',
              color: portfolioScope === 'exchange' ? '#FFFFFF' : 'var(--text-secondary)',
              fontWeight: 700,
              fontSize: '0.78rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
              boxShadow: portfolioScope === 'exchange' ? '0 2px 8px rgba(245, 158, 11, 0.35)' : 'none'
            }}
          >
            <Layers size={14} /> Por Exchange (Aislado) {modesData?.exchange ? `(${modesData.exchange.total_gaps})` : ''}
          </button>
        </div>
      </div>

      {/* KPI Summary Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
        <div className="card-surface" style={{ padding: '1.25rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.6rem' }}>
            <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Estado ({portfolioScope === 'global' ? 'Cartera Global' : 'Por Exchange'})
            </span>
            {loadingWarnings ? (
              <span className="badge badge-info" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
                <RefreshCw size={11} className="spin" /> Auditando {displayYear}...
              </span>
            ) : allWarningsList.length === 0 ? (
              <span className="badge badge-emerald">
                <CheckCircle2 size={12} /> Historial Consistente
              </span>
            ) : (
              <span className="badge badge-amber">
                <AlertTriangle size={12} /> {allWarningsList.length} Faltante(s)
              </span>
            )}
          </div>
          <div style={{ fontSize: '1.45rem', fontWeight: 700, color: loadingWarnings ? 'var(--text-secondary)' : allWarningsList.length === 0 ? '#34D399' : '#FBBF24' }} className="font-mono">
            {loadingWarnings ? 'Auditando...' : allWarningsList.length === 0 ? 'Sin Advertencias' : `${allWarningsList.length} Huecos FIFO`}
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
            {loadingWarnings
              ? 'Verificando comprobantes y trazabilidad patrimonial...'
              : allWarningsList.length === 0
                ? 'Todas las ventas tienen comprobantes de compra previos registrados.'
                : portfolioScope === 'global'
                  ? 'Ventas globales que superaron las compras totales de tu patrimonio.'
                  : 'Ventas sin lote de compra en el exchange donde se ejecutó.'}
          </div>
        </div>

        <div className="card-surface" style={{ padding: '1.25rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.6rem' }}>
            <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Brújula de Diagnóstico
            </span>
            <Compass size={18} color="var(--brand-indigo-light)" />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', marginTop: '0.15rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.82rem' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', color: '#34D399' }}>
                <Link2 size={13} /> Transferencias probables:
              </span>
              <span className="font-mono font-bold" style={{ color: '#34D399' }}>{activeSummary.with_probable_match || 0}</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.82rem' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', color: '#FBBF24' }}>
                <Search size={13} /> Falta extracto depósitos/swaps:
              </span>
              <span className="font-mono font-bold" style={{ color: '#FBBF24' }}>{activeSummary.missing_data_source || 0}</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.82rem' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', color: '#818CF8' }}>
                <HelpCircle size={13} /> Origen a investigar:
              </span>
              <span className="font-mono font-bold" style={{ color: '#818CF8' }}>{activeSummary.unknown_origin || 0}</span>
            </div>
          </div>
        </div>

        <div className="card-surface" style={{ padding: '1.25rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.6rem' }}>
            <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Resolución Guiada
            </span>
            <Wand2 size={18} color="var(--accent-cyan)" />
          </div>
          <div style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--brand-indigo-light)' }}>
            Asistente Automático
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
            {exchangeFreshness.some((e) => e.stale)
              ? `Hay ${exchangeFreshness.filter((e) => e.stale).length} exchange(s) con más de 30 días sin actualizar.`
              : 'Ingresá saldos iniciales o subí extractos para conciliar.'}
          </div>
        </div>
      </div>

      <DeclareNoOperationsModal
        isOpen={declareModal.isOpen}
        onClose={() => setDeclareModal({ isOpen: false, exchange: '', lastDate: '' })}
        exchange={declareModal.exchange}
        lastDate={declareModal.lastDate}
        apiBase={apiBase || config.API_URL}
        onSuccess={(exName) => {
          if (showToast) showToast(`✅ ${exName || declareModal.exchange} declarado al día con éxito.`, 'success');
          if (onRefreshWarnings) onRefreshWarnings();
        }}
      />
    </>
  );
};

export default WarningsSummaryCards;
