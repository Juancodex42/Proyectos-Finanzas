import React from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Link2,
  Lightbulb,
  ShieldAlert,
  ArrowRight
} from 'lucide-react';
import { motion } from 'framer-motion';

const MonthDiagnosisPopover = ({
  monthName,
  selectedYear,
  diagnosis,
  hasGaps = false,
  monthGapsCount = 0,
  isCertified = false,
  certStatus = 'none',
  mIdx = 0
}) => {
  if (!diagnosis) return null;

  const {
    exchanges = [],
    total_deficit = 0,
    has_observations = false,
    stale_sources = [],
    probable_matches = [],
    recommendations = []
  } = diagnosis;

  const effectiveCertStatus = certStatus !== 'none' ? certStatus : (isCertified ? 'full' : 'none');

  // Header status resolution
  let statusBadge = (
    <span style={{ fontSize: '0.7rem', padding: '0.15rem 0.5rem', borderRadius: '4px', background: 'rgba(79, 70, 229, 0.2)', color: '#818CF8', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
      <CheckCircle2 size={11} /> Provisorio al Día
    </span>
  );

  if (effectiveCertStatus === 'full') {
    statusBadge = (
      <span style={{ fontSize: '0.7rem', padding: '0.15rem 0.5rem', borderRadius: '4px', background: 'rgba(16, 185, 129, 0.2)', color: '#34D399', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
        <CheckCircle2 size={11} /> Auditado C.P.N.
      </span>
    );
  } else if (hasGaps) {
    statusBadge = (
      <span style={{ fontSize: '0.7rem', padding: '0.15rem 0.5rem', borderRadius: '4px', background: 'rgba(245, 158, 11, 0.25)', color: '#FBBF24', fontWeight: 700, display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
        <AlertTriangle size={11} /> {monthGapsCount} Hueco(s) FIFO{effectiveCertStatus === 'partial' ? ' (Cert. Parcial)' : ''}
      </span>
    );
  } else if (effectiveCertStatus === 'partial') {
    statusBadge = (
      <span style={{ fontSize: '0.7rem', padding: '0.15rem 0.5rem', borderRadius: '4px', background: 'rgba(16, 185, 129, 0.15)', color: '#34D399', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
        <CheckCircle2 size={11} /> Auditado Parcial
      </span>
    );
  } else if (has_observations) {
    statusBadge = (
      <span style={{ fontSize: '0.7rem', padding: '0.15rem 0.5rem', borderRadius: '4px', background: 'rgba(245, 158, 11, 0.18)', color: '#FBBF24', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
        <Clock size={11} /> Al Día ℹ️ Observaciones
      </span>
    );
  }

  // Exchanges without deposits but with sales
  const salesWithoutDeposits = exchanges.filter(
    (e) => e.sells > 0 && !e.has_deposits
  );

  return (
    <motion.div
      initial={{ opacity: 0, y: -6, scale: 0.96 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: -4, scale: 0.96 }}
      transition={{ duration: 0.15 }}
      style={{
        position: 'absolute',
        bottom: 'calc(100% + 8px)',
        left: mIdx > 8 ? 'auto' : mIdx < 3 ? '0' : '50%',
        right: mIdx > 8 ? '0' : 'auto',
        transform: mIdx > 8 || mIdx < 3 ? 'none' : 'translateX(-50%)',
        zIndex: 9999,
        width: '360px',
        maxWidth: '90vw',
        background: '#0D131F',
        border: '1px solid rgba(99, 102, 241, 0.4)',
        boxShadow: '0 12px 30px rgba(0, 0, 0, 0.75)',
        borderRadius: 'var(--radius-md, 8px)',
        padding: '0.85rem',
        textAlign: 'left',
        pointerEvents: 'none',
        color: '#E2E8F0',
        fontSize: '0.78rem',
        lineHeight: 1.4
      }}
    >
      {/* 1. Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid rgba(255, 255, 255, 0.08)', paddingBottom: '0.45rem', marginBottom: '0.6rem' }}>
        <div style={{ fontWeight: 700, fontSize: '0.88rem', color: '#F8FAFC', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <span>📅 {monthName.toUpperCase()} {selectedYear}</span>
        </div>
        <div>{statusBadge}</div>
      </div>

      {/* 2. Monthly Physical Balance */}
      <div style={{ marginBottom: '0.65rem' }}>
        <div style={{ fontSize: '0.72rem', color: '#94A3B8', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '0.35rem' }}>
          Balance de Custodia del Mes
        </div>

        {exchanges.length === 0 ? (
          <div style={{ color: '#64748B', fontSize: '0.75rem', fontStyle: 'italic', padding: '0.2rem 0' }}>
            Sin movimientos registrados en este período.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
            {exchanges.map((ex, idx) => {
              const isDeficit = ex.net < -1e-4;
              return (
                <div
                  key={`${ex.exchange}-${ex.coin}-${idx}`}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    background: isDeficit ? 'rgba(239, 68, 68, 0.08)' : 'rgba(255, 255, 255, 0.02)',
                    border: isDeficit ? '1px solid rgba(239, 68, 68, 0.25)' : '1px solid rgba(255, 255, 255, 0.04)',
                    borderRadius: '4px',
                    padding: '0.25rem 0.45rem',
                    fontSize: '0.72rem'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                    <span style={{ fontWeight: 700, color: '#F1F5F9' }}>{ex.exchange}</span>
                    <span style={{ color: '#94A3B8', fontSize: '0.68rem' }}>({ex.coin})</span>
                  </div>

                  <div style={{ display: 'flex', gap: '0.5rem', fontFamily: 'monospace', fontSize: '0.7rem' }}>
                    <span style={{ color: '#10B981' }} title="Compras registradas">+{ex.buys.toLocaleString()}</span>
                    <span style={{ color: '#F43F5E' }} title="Ventas registradas">-{ex.sells.toLocaleString()}</span>
                    <span
                      style={{
                        fontWeight: 700,
                        color: isDeficit ? '#F87171' : '#34D399'
                      }}
                      title="Balance neto del mes"
                    >
                      {ex.net > 0 ? `+${ex.net.toLocaleString()}` : ex.net.toLocaleString()}
                    </span>
                  </div>
                </div>
              );
            })}

            {total_deficit > 0 && (
              <div style={{ padding: '0.35rem 0.45rem', background: 'rgba(245, 158, 11, 0.1)', borderRadius: '4px', border: '1px solid rgba(245, 158, 11, 0.3)', marginTop: '0.15rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontWeight: 600, color: '#FBBF24', fontSize: '0.72rem' }}>
                    Déficit Físico Estimado:
                  </span>
                  <span style={{ fontWeight: 700, color: '#FBBF24', fontFamily: 'monospace', fontSize: '0.75rem' }}>
                    ~{total_deficit.toLocaleString()} USD (est.)
                  </span>
                </div>
                {diagnosis.deficits_by_coin && Object.keys(diagnosis.deficits_by_coin).length > 0 && (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', marginTop: '0.25rem', paddingTop: '0.25rem', borderTop: '1px dashed rgba(245, 158, 11, 0.2)' }}>
                    {Object.entries(diagnosis.deficits_by_coin).map(([c, amt]) => (
                      <span key={c} style={{ fontSize: '0.68rem', color: '#FCD34D', fontFamily: 'monospace' }}>
                        {c}: <strong>{amt.toLocaleString()}</strong>
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* 3. Discard and Integrity Alerts */}
      {(salesWithoutDeposits.length > 0 || stale_sources.length > 0) && (
        <div style={{ marginBottom: '0.65rem', borderTop: '1px solid rgba(255, 255, 255, 0.06)', paddingTop: '0.45rem' }}>
          <div style={{ fontSize: '0.72rem', color: '#F59E0B', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '0.3rem', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
            <ShieldAlert size={12} /> Descarte e Integridad de Fuentes
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
            {salesWithoutDeposits.map((swd, i) => (
              <div key={`swd-${i}`} style={{ color: '#FCD34D', fontSize: '0.7rem', display: 'flex', alignItems: 'flex-start', gap: '0.3rem' }}>
                <span>⚠️</span>
                <span>
                  <strong>{swd.exchange}</strong> registra ventas sin depósitos cripto previos de {swd.coin}.
                </span>
              </div>
            ))}

            {stale_sources.map((stale, i) => {
              const exName = typeof stale === 'object' ? (stale?.exchange || 'Desconocido') : String(stale);
              const lastDate = typeof stale === 'object' ? (stale?.last_date || 'previa') : 'previa';
              return (
                <div key={`stale-${i}`} style={{ color: '#FCD34D', fontSize: '0.7rem', display: 'flex', alignItems: 'flex-start', gap: '0.3rem' }}>
                  <span>📅</span>
                  <span>
                    Extracto de <strong>{exName}</strong> desactualizado (última operación el {lastDate}).
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 4. Probable Matches */}
      {probable_matches.length > 0 && (
        <div style={{ marginBottom: '0.65rem', borderTop: '1px solid rgba(255, 255, 255, 0.06)', paddingTop: '0.45rem' }}>
          <div style={{ fontSize: '0.72rem', color: '#10B981', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '0.3rem', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
            <Link2 size={12} /> Coincidencias Probables de Origen
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
            {probable_matches.slice(0, 2).map((m, idx) => {
              const displayAmt = typeof m.source_amount === 'number'
                ? m.source_amount.toLocaleString()
                : (m.source_amount || m.target_amount);
              return (
                <div
                  key={`pm-${idx}`}
                  style={{
                    background: 'rgba(16, 185, 129, 0.08)',
                    border: '1px solid rgba(16, 185, 129, 0.25)',
                    borderRadius: '4px',
                    padding: '0.3rem 0.45rem',
                    fontSize: '0.7rem'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', color: '#6EE7B7' }}>
                    <span>{m.source_exchange}</span>
                    <ArrowRight size={10} />
                    <span>{m.target_exchange}</span>
                    <span style={{ marginLeft: 'auto', fontWeight: 700, fontFamily: 'monospace' }}>
                      {displayAmt} {m.coin}
                    </span>
                  </div>
                  {m.source_date && (
                    <div style={{ fontSize: '0.65rem', color: '#94A3B8', marginTop: '0.1rem' }}>
                      Retiro el {m.source_date}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 5. Guided Recommendations */}
      {recommendations.length > 0 && (
        <div style={{ borderTop: '1px solid rgba(255, 255, 255, 0.06)', paddingTop: '0.45rem' }}>
          <div style={{ fontSize: '0.72rem', color: '#818CF8', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '0.3rem', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
            <Lightbulb size={12} /> Acción Recomendada
          </div>

          <ul style={{ margin: 0, paddingLeft: '1.1rem', fontSize: '0.7rem', color: '#CBD5E1' }}>
            {recommendations.map((rec, rIdx) => (
              <li key={`rec-${rIdx}`} style={{ marginBottom: '0.15rem' }}>
                {rec}
              </li>
            ))}
          </ul>
        </div>
      )}
    </motion.div>
  );
};

export default MonthDiagnosisPopover;
