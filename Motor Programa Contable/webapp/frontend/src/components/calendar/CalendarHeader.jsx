import React from 'react';
import {
  Calendar as CalendarIcon, ShieldCheck, AlertTriangle,
  Plus, RefreshCw, Sparkles, Database
} from 'lucide-react';

const CalendarHeader = ({
  activeTab,
  setActiveTab,
  certificationsCount = 0,
  warningsCount = 0,
  loading = false,
  loadingWarnings = false,
  onOpenPonteAlDiaModal,
  onSyncCoverage,
  onRefresh,
  onOpenNewCertificationModal,
  onOpenReplacePeriodModal
}) => {
  return (
    <div>
      {/* Top Header Bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem', marginBottom: '1.5rem' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
            <div style={{
              width: '36px',
              height: '36px',
              borderRadius: '8px',
              background: 'var(--brand-indigo-subtle)',
              border: '1px solid var(--brand-indigo-border)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--brand-indigo-light)'
            }}>
              <CalendarIcon size={20} />
            </div>
            <h1 style={{ fontSize: '1.75rem', fontWeight: 800, color: '#F8FAFC', margin: 0, letterSpacing: '-0.02em' }}>
              Calendario de Operaciones & Auditoría FIFO
            </h1>
          </div>
          <p style={{ color: 'var(--text-secondary)', margin: '0.35rem 0 0 0', fontSize: '0.88rem', paddingLeft: '2.85rem' }}>
            Línea temporal de períodos certificados, dictámenes C.P.N., consistencia FIFO y auditoría diaria.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.65rem', flexWrap: 'wrap' }}>
          <button
            onClick={onOpenPonteAlDiaModal}
            className="btn-primary"
            style={{
              background: 'linear-gradient(135deg, #F59E0B, #D97706)',
              border: 'none',
              display: 'flex',
              alignItems: 'center',
              gap: '0.45rem',
              fontWeight: 700,
              color: '#fff',
              boxShadow: '0 4px 14px rgba(245, 158, 11, 0.35)'
            }}
          >
            <Sparkles size={16} />
            Ponete al Día
            {warningsCount > 0 && (
              <span style={{ background: 'rgba(0,0,0,0.3)', padding: '0.15rem 0.5rem', borderRadius: '999px', fontSize: '0.72rem' }}>
                {warningsCount}
              </span>
            )}
          </button>

          <button
            onClick={onSyncCoverage}
            className="btn-secondary"
            style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}
            title="Vincular transacciones con calendario certificado"
          >
            <ShieldCheck size={16} color="#34D399" />
            Sincronizar Cobertura
          </button>

          <button
            onClick={onRefresh}
            className="btn-secondary"
            style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}
            title="Actualizar datos"
          >
            <RefreshCw size={16} className={(loading || loadingWarnings) ? 'spin' : ''} />
            Refrescar
          </button>

          {activeTab === 'certifications' && (
            <>
              {onOpenReplacePeriodModal && (
                <button
                  onClick={onOpenReplacePeriodModal}
                  className="btn-secondary"
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.45rem',
                    borderColor: 'rgba(59, 130, 246, 0.4)',
                    color: '#60A5FA'
                  }}
                  title="Reemplazar registros provisorios con transacciones oficiales de dictamen CPA"
                >
                  <Database size={16} />
                  Reemplazo Oficial CPA
                </button>
              )}
              <button
                onClick={onOpenNewCertificationModal}
                className="btn-primary"
                style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}
              >
                <Plus size={16} />
                Nueva Certificación
              </button>
            </>
          )}
        </div>
      </div>

      {/* Tabs Selector Bar */}
      <div style={{
        display: 'flex',
        gap: '0.5rem',
        marginBottom: '1.5rem',
        background: '#0D131F',
        padding: '0.3rem',
        borderRadius: 'var(--radius-md)',
        border: '1px solid var(--border-color)',
        width: 'fit-content'
      }}>
        <button
          onClick={() => setActiveTab('certifications')}
          style={{
            background: activeTab === 'certifications' ? 'var(--brand-indigo)' : 'transparent',
            border: 'none',
            color: activeTab === 'certifications' ? '#FFFFFF' : 'var(--text-secondary)',
            padding: '0.5rem 1.1rem',
            borderRadius: 'var(--radius-sm)',
            fontWeight: 600,
            fontSize: '0.85rem',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '0.45rem',
            transition: 'all 150ms ease'
          }}
        >
          <ShieldCheck size={16} />
          Dictámenes & Certificaciones Contables ({certificationsCount})
        </button>

        <button
          onClick={() => setActiveTab('warnings')}
          style={{
            background: activeTab === 'warnings' ? 'var(--brand-indigo)' : 'transparent',
            border: 'none',
            color: activeTab === 'warnings' ? '#FFFFFF' : 'var(--text-secondary)',
            padding: '0.5rem 1.1rem',
            borderRadius: 'var(--radius-sm)',
            fontWeight: 600,
            fontSize: '0.85rem',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '0.45rem',
            transition: 'all 150ms ease'
          }}
        >
          <AlertTriangle size={16} color={activeTab === 'warnings' ? '#FEF08A' : 'var(--accent-amber-light)'} />
          Operaciones & Inconsistencias
          {warningsCount > 0 && (
            <span style={{
              background: '#EF4444',
              color: '#fff',
              fontSize: '0.72rem',
              fontWeight: 700,
              padding: '0.1rem 0.45rem',
              borderRadius: '999px',
              marginLeft: '0.2rem'
            }}>
              {warningsCount}
            </span>
          )}
        </button>
      </div>
    </div>
  );
};

export default CalendarHeader;
