import React, { useState, useRef, useEffect } from 'react';
import { ChevronLeft, ChevronRight, Clock, ShieldCheck } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  months,
  getCertsForMonth,
  getMonthCertInfo,
  getMonthCoverageStatus,
  parseCleanDate,
  formatPeriodRange
} from './calendarUtils';
import MonthDiagnosisPopover from './MonthDiagnosisPopover';

const CalendarMonthGrid = ({
  mode = 'warnings', // 'warnings' | 'certifications'
  selectedYear,
  setSelectedYear,
  availableYears = [],
  allWarningsList = [],
  certificationsList = [],
  activeBrackets = [],
  monthlyCustody = {},
  onSelectGap,
  onOpenAddCertification,
  onOpenPonteAlDiaModal,
  onSwitchTab,
  loadingWarnings = false
}) => {
  const [hoveredMonth, setHoveredMonth] = useState(null);
  const [hoveredWarningMonth, setHoveredWarningMonth] = useState(null);
  const hoverTimeoutRef = useRef(null);
  const certHoverTimeoutRef = useRef(null);

  const handleMouseEnter = (idx) => {
    if (hoverTimeoutRef.current) clearTimeout(hoverTimeoutRef.current);
    hoverTimeoutRef.current = setTimeout(() => setHoveredWarningMonth(idx), 120);
  };

  const handleMouseLeave = () => {
    if (hoverTimeoutRef.current) clearTimeout(hoverTimeoutRef.current);
    hoverTimeoutRef.current = setTimeout(() => setHoveredWarningMonth(null), 100);
  };

  const handleCertMouseEnter = (idx) => {
    if (certHoverTimeoutRef.current) clearTimeout(certHoverTimeoutRef.current);
    certHoverTimeoutRef.current = setTimeout(() => setHoveredMonth(idx), 120);
  };

  const handleCertMouseLeave = () => {
    if (certHoverTimeoutRef.current) clearTimeout(certHoverTimeoutRef.current);
    certHoverTimeoutRef.current = setTimeout(() => setHoveredMonth(null), 100);
  };

  const [prevYear, setPrevYear] = useState(selectedYear);
  if (selectedYear !== prevYear) {
    setPrevYear(selectedYear);
    setHoveredWarningMonth(null);
    setHoveredMonth(null);
  }

  useEffect(() => {
    return () => {
      if (hoverTimeoutRef.current) clearTimeout(hoverTimeoutRef.current);
      if (certHoverTimeoutRef.current) clearTimeout(certHoverTimeoutRef.current);
    };
  }, []);

  const today = new Date();
  const currentYear = today.getFullYear();
  const currentMonth = today.getMonth();

  return (
    <div className="card-surface" style={{ padding: '1.25rem', marginBottom: '1.5rem', position: 'relative', zIndex: 30 }}>
      {/* Top Header & Year Navigation */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
          {mode === 'certifications' ? (
            <ShieldCheck size={18} color="var(--brand-indigo-light)" />
          ) : (
            <Clock size={18} color="var(--brand-indigo-light)" />
          )}
          <h3 style={{ fontSize: '1.05rem', fontWeight: 700, margin: 0 }}>
            {mode === 'certifications'
              ? `Línea de Tiempo de Cobertura Legal (${selectedYear})`
              : `Línea de Tiempo de Consistencia & Auditoría (${selectedYear})`}
          </h3>

          {/* Year Selector */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', background: '#0D131F', padding: '0.2rem 0.5rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)' }}>
            <button
              onClick={() => setSelectedYear((prev) => prev - 1)}
              style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer', display: 'flex', alignItems: 'center' }}
              title="Año anterior"
            >
              <ChevronLeft size={16} />
            </button>
            <select
              value={selectedYear}
              onChange={(e) => setSelectedYear(Number(e.target.value))}
              style={{ background: 'transparent', border: 'none', color: 'var(--brand-indigo-light)', fontWeight: 700, fontSize: '0.92rem', cursor: 'pointer' }}
              className="font-mono"
            >
              {availableYears.map((yr) => (
                <option key={yr} value={yr} style={{ background: '#0D131F', color: 'white' }}>
                  {yr}
                </option>
              ))}
            </select>
            <button
              onClick={() => setSelectedYear((prev) => prev + 1)}
              style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer', display: 'flex', alignItems: 'center' }}
              title="Año siguiente"
            >
              <ChevronRight size={16} />
            </button>
          </div>
        </div>

        {/* Legend */}
        <div style={{ display: 'flex', gap: '1rem', fontSize: '0.75rem', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
            <div style={{ width: '10px', height: '10px', borderRadius: '2px', background: '#10B981' }}></div>
            <span style={{ color: 'var(--text-secondary)' }}>Auditado C.P.N.</span>
          </div>
          {mode === 'warnings' ? (
            <>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                <div style={{ width: '10px', height: '10px', borderRadius: '2px', background: '#F59E0B' }}></div>
                <span style={{ color: 'var(--text-secondary)' }}>Advertencia / Hueco</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                <div style={{ width: '10px', height: '10px', borderRadius: '2px', border: '1px dashed #F59E0B', background: 'rgba(245, 158, 11, 0.2)' }}></div>
                <span style={{ color: 'var(--text-secondary)' }}>Al Día c/ Observación</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                <div style={{ width: '10px', height: '10px', borderRadius: '2px', background: '#4F46E5' }}></div>
                <span style={{ color: 'var(--text-secondary)' }}>Provisorio al Día</span>
              </div>
            </>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
              <div style={{ width: '10px', height: '10px', borderRadius: '2px', background: '#F59E0B' }}></div>
              <span style={{ color: 'var(--text-secondary)' }}>Pendiente de Certificación</span>
            </div>
          )}
        </div>
      </div>

      {/* Mode Certifications: Continuous Brackets / Bars across months */}
      {mode === 'certifications' && activeBrackets.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(12, 1fr)', gap: '0.45rem', marginBottom: '0.45rem' }}>
          {activeBrackets.map((b, bIdx) => {
            const spanCols = Math.max(1, b.endMonth - b.startMonth + 1);
            const shortTitle = b.cert.title ? b.cert.title.replace('Certificación Contable', 'Cert.').trim() : 'Certificado';
            return (
              <div
                key={b.cert.id ? `bracket-${b.cert.id}` : `bracket-idx-${bIdx}`}
                style={{
                  gridColumn: `${b.startMonth + 1} / span ${spanCols}`,
                  gridRow: `${(b.rowIndex || 0) + 1}`,
                  background: b.colorScheme.bg,
                  border: `1.5px solid ${b.colorScheme.border}`,
                  borderRadius: 'var(--radius-sm)',
                  padding: '0.3rem 0.5rem',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: '0.4rem',
                  fontSize: '0.74rem',
                  fontWeight: 600,
                  color: b.colorScheme.text,
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis'
                }}
                title={`Dictamen: ${b.cert.title} | Cobertura: ${formatPeriodRange(b.cert.start_date, b.cert.end_date)}`}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', minWidth: 0 }}>
                  <ShieldCheck size={13} style={{ flexShrink: 0 }} />
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {spanCols <= 1 ? shortTitle : b.cert.title}
                  </span>
                </div>
                {b.cert.cpa_name && spanCols > 1 && (
                  <span style={{ fontSize: '0.68rem', opacity: 0.9, flexShrink: 0, fontWeight: 500 }}>
                    {spanCols >= 4 ? b.cert.cpa_name : b.cert.cpa_name.replace(/^(?:C\.P\.N\.|CPN|Contador Público)\s+/i, '')}
                  </span>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* 12 Months Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(12, 1fr)', gap: '0.45rem', position: 'relative', zIndex: 25 }}>
        {months.map((monthName, mIdx) => {
          const isFuture = selectedYear > currentYear || (selectedYear === currentYear && mIdx > currentMonth);

          if (mode === 'warnings') {
            const monthKey = `${selectedYear}-${String(mIdx + 1).padStart(2, '0')}`;
            const diagnosis = monthlyCustody?.[monthKey];
            const hasObservations = Boolean(diagnosis?.has_observations);
            const certInfo = getMonthCertInfo(mIdx, selectedYear, certificationsList);

            const monthGaps = allWarningsList.filter((g) => {
              if (!g.date && !g.fecha) return false;
              const dateStr = String(g.date || g.fecha).split(' ')[0];
              const parts = dateStr.split('-');
              if (parts.length === 3) {
                const y = parseInt(parts[0], 10);
                const m = parseInt(parts[1], 10) - 1;
                if (y !== selectedYear || m !== mIdx) return false;
                if (certInfo.status === 'full') return false;
                if (certInfo.status === 'partial') {
                  const gapDate = parseCleanDate(dateStr);
                  if (gapDate) {
                    const isCoveredByCert = certInfo.certs.some((cert) => {
                      const cStart = parseCleanDate(cert.start_date);
                      const cEnd = parseCleanDate(cert.end_date, true);
                      return cStart && cEnd && gapDate >= cStart && gapDate <= cEnd;
                    });
                    if (isCoveredByCert) return false;
                  }
                }
                return true;
              }
              return false;
            });
            const hasGaps = monthGaps.length > 0;
            const isFullyCertified = certInfo.status === 'full';
            const isPartiallyCertified = certInfo.status === 'partial';

            let bg = 'rgba(79, 70, 229, 0.08)';
            let border = '1px solid rgba(79, 70, 229, 0.25)';
            let titleColor = '#818CF8';
            let labelText = 'Al Día';

            if (isFuture) {
              bg = 'rgba(15, 23, 42, 0.4)';
              border = '1px solid var(--border-subtle)';
              titleColor = 'var(--text-muted)';
              labelText = '-';
            } else if (isFullyCertified) {
              bg = 'rgba(16, 185, 129, 0.15)';
              border = '1px solid #10B981';
              titleColor = '#34D399';
              labelText = '✓ Auditado';
            } else if (hasGaps) {
              bg = 'rgba(245, 158, 11, 0.18)';
              border = '1px solid #F59E0B';
              titleColor = '#FBBF24';
              labelText = '⚠️ Hueco';
            } else if (isPartiallyCertified) {
              bg = 'rgba(16, 185, 129, 0.10)';
              border = '1.5px dashed #10B981';
              titleColor = '#34D399';
              labelText = '✓ Parcial';
            } else if (hasObservations) {
              bg = 'rgba(245, 158, 11, 0.08)';
              border = '1.5px dashed rgba(245, 158, 11, 0.65)';
              titleColor = '#FBBF24';
              labelText = 'Al Día ℹ️';
            } else if (loadingWarnings) {
              bg = 'rgba(79, 70, 229, 0.04)';
              border = '1px dashed rgba(79, 70, 229, 0.25)';
              titleColor = 'var(--text-muted)';
              labelText = 'Auditando...';
            }

            return (
              <div
                key={monthName}
                style={{
                  background: bg,
                  border: border,
                  borderRadius: 'var(--radius-sm)',
                  padding: '0.65rem 0.35rem',
                  textAlign: 'center',
                  cursor: !isFuture ? 'pointer' : 'default',
                  transition: 'all 150ms ease',
                  opacity: isFuture ? 0.45 : 1,
                  position: 'relative'
                }}
                onMouseEnter={() => handleMouseEnter(mIdx)}
                onMouseLeave={handleMouseLeave}
                onClick={() => {
                  if (hasGaps && monthGaps[0]) {
                    if (onSelectGap) onSelectGap(monthGaps[0]);
                  } else if (isFullyCertified || isPartiallyCertified) {
                    if (onSwitchTab) onSwitchTab('certifications');
                  } else if (!isFuture) {
                    if (onOpenPonteAlDiaModal) onOpenPonteAlDiaModal();
                  }
                }}
              >
                <div style={{ fontSize: '0.78rem', fontWeight: 700, color: titleColor }}>{monthName}</div>
                <div style={{ fontSize: '0.68rem', marginTop: '0.2rem', color: titleColor }}>
                  {labelText}
                </div>

                {/* Hover Popover */}
                <AnimatePresence>
                  {hoveredWarningMonth === mIdx && !isFuture && diagnosis && (
                    <MonthDiagnosisPopover
                      monthName={monthName}
                      selectedYear={selectedYear}
                      diagnosis={diagnosis}
                      hasGaps={hasGaps}
                      monthGapsCount={monthGaps.length}
                      isCertified={isFullyCertified}
                      certStatus={certInfo.status}
                      mIdx={mIdx}
                    />
                  )}
                </AnimatePresence>
              </div>
            );
          } else {
            // mode === 'certifications'
            const monthCerts = getCertsForMonth(mIdx, selectedYear, certificationsList);
            const status = getMonthCoverageStatus(mIdx, selectedYear, certificationsList);

            let bgColor = 'rgba(255, 255, 255, 0.03)';
            let borderStyle = '1px solid var(--border-subtle)';
            let textColor = 'var(--text-muted)';

            if (status === 'certified') {
              bgColor = 'rgba(16, 185, 129, 0.12)';
              borderStyle = '1px solid rgba(16, 185, 129, 0.35)';
              textColor = '#34D399';
            } else if (status === 'partial') {
              bgColor = 'rgba(16, 185, 129, 0.08)';
              borderStyle = '1.5px dashed rgba(16, 185, 129, 0.5)';
              textColor = '#34D399';
            } else if (status === 'pending') {
              bgColor = 'rgba(245, 158, 11, 0.12)';
              borderStyle = '1px solid rgba(245, 158, 11, 0.35)';
              textColor = '#FBBF24';
            }

            return (
              <div
                key={monthName}
                style={{
                  background: bgColor, border: borderStyle, borderRadius: 'var(--radius-sm)',
                  padding: '0.65rem 0.35rem', textAlign: 'center', transition: 'all 150ms ease',
                  cursor: 'pointer', position: 'relative'
                }}
                onMouseEnter={() => handleCertMouseEnter(mIdx)}
                onMouseLeave={handleCertMouseLeave}
                onClick={() => {
                  if ((status === 'pending' || status === 'partial') && onOpenAddCertification) {
                    const startD = `${selectedYear}-${String(mIdx + 1).padStart(2, '0')}-01`;
                    const endD = new Date(selectedYear, mIdx + 1, 0).toISOString().split('T')[0];
                    onOpenAddCertification({ title: `Certificación ${monthName} ${selectedYear}`, start_date: startD, end_date: endD });
                  }
                }}
              >
                <div style={{ fontSize: '0.8rem', fontWeight: 700, color: textColor }}>{monthName}</div>
                <div style={{ fontSize: '0.68rem', marginTop: '0.2rem', color: textColor }}>
                  {status === 'certified' ? '✓ Auditado' : status === 'partial' ? '⏳ Parcial' : status === 'pending' ? '⚠️ Sin cert.' : '-'}
                </div>

                {/* Hover Popover */}
                <AnimatePresence>
                  {hoveredMonth === mIdx && (
                    <motion.div
                      initial={{ opacity: 0, y: -6, scale: 0.96 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: -4, scale: 0.96 }}
                      style={{
                        position: 'absolute', bottom: 'calc(100% + 8px)',
                        left: mIdx > 8 ? 'auto' : mIdx < 3 ? '0' : '50%', right: mIdx > 8 ? '0' : 'auto',
                        transform: mIdx > 8 || mIdx < 3 ? 'none' : 'translateX(-50%)',
                        zIndex: 9999, width: '280px', background: '#0D131F',
                        border: '1px solid var(--brand-indigo-border)', boxShadow: 'var(--shadow-lg)',
                        borderRadius: 'var(--radius-md)', padding: '0.85rem', textAlign: 'left', pointerEvents: 'none'
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '0.35rem' }}>
                        <span style={{ fontWeight: 700, fontSize: '0.85rem', color: 'var(--brand-indigo-light)' }}>
                          📅 {monthName.toUpperCase()} {selectedYear}
                        </span>
                        <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>{monthCerts.length} Cert.</span>
                      </div>

                      {monthCerts.length === 0 ? (
                        <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                          {status === 'pending' ? '⚠️ Período sin certificar.' : 'Período futuro.'}
                        </div>
                      ) : (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                          {monthCerts.map((c, cIdx) => (
                            <div
                              key={c.id || cIdx}
                              style={{ background: 'var(--bg-elevated)', borderLeft: '3px solid var(--accent-emerald)', padding: '0.4rem 0.55rem', borderRadius: 'var(--radius-sm)' }}
                            >
                              <div style={{ fontWeight: 700, fontSize: '0.78rem', color: '#34D399' }}>{c.title}</div>
                              <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', marginTop: '0.15rem' }} className="font-mono">
                                {formatPeriodRange(c.start_date, c.end_date)}
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            );
          }
        })}
      </div>
    </div>
  );
};

export default CalendarMonthGrid;
