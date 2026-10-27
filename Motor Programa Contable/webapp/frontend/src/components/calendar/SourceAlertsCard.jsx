import React, { useState } from 'react';
import {
  AlertTriangle, Search, ShieldCheck, CheckCircle2,
  RefreshCw, AlertCircle, Eye, ChevronDown, ChevronUp, RotateCcw
} from 'lucide-react';
import axios from 'axios';
import config from '../../config';

const SourceAlertsCard = ({
  custodyDeficits = [],
  sourceAlerts = [],
  declaredSources = [],
  displayYear,
  loadingWarnings = false,
  apiBase,
  showToast,
  onRefreshWarnings,
  onOpenDeclareModal
}) => {
  const [showDeclaredSources, setShowDeclaredSources] = useState(false);
  const [revokingExchange, setRevokingExchange] = useState(null);
  const [declaringAll, setDeclaringAll] = useState(false);
  const [syncingExchange, setSyncingExchange] = useState(null);
  const [syncingAllApis, setSyncingAllApis] = useState(false);

  const hasSourceAlerts = sourceAlerts && sourceAlerts.length > 0;
  const hasDeclaredSources = declaredSources && declaredSources.length > 0;
  const staleSources = (sourceAlerts || []).filter((sa) => sa.type === 'stale_source');
  const staleApiSources = staleSources.filter((sa) => sa.is_api);
  const onlineApiSources = staleApiSources.filter((sa) => sa.api_status !== 'expired');

  const handleDeclareAllStale = async () => {
    if (staleSources.length === 0) return;
    const names = staleSources.map((s) => s.exchange);
    if (!window.confirm(`¿Confirmás declarar al día ${names.length} exchange(s) (${names.join(', ')}) sin operaciones posteriores?`)) {
      return;
    }
    setDeclaringAll(true);
    try {
      const baseUrl = (apiBase || config.API_URL || '').replace(/\/api\/?$/, '');
      const targetEndpoint = `${baseUrl}/api/audit/declarations`;
      await axios.post(targetEndpoint, {
        exchanges: names,
        status: 'NO_OPERATIONS',
        reason: 'Declarados sin operaciones posteriores'
      });
      if (showToast) showToast(`✅ ${names.length} fuentes declaradas al día con éxito.`, 'success');
      if (onRefreshWarnings) onRefreshWarnings();
    } catch (err) {
      console.error('Error al declarar todas las fuentes:', err);
      if (showToast) showToast('Error al registrar declaraciones en lote', 'error');
    } finally {
      setDeclaringAll(false);
    }
  };

  const handleRevokeDeclaration = async (exchange) => {
    if (!window.confirm(`¿Deseas reanudar la auditoría de extractos para ${exchange}? Volverá a comprobar si faltan movimientos.`)) {
      return;
    }
    setRevokingExchange(exchange);
    try {
      const baseUrl = (apiBase || config.API_URL || '').replace(/\/api\/?$/, '');
      const targetEndpoint = `${baseUrl}/api/audit/declarations/${encodeURIComponent(exchange)}`;
      await axios.delete(targetEndpoint);
      if (showToast) showToast(`Auditoría reanudada para ${exchange}.`, 'info');
      if (onRefreshWarnings) onRefreshWarnings();
    } catch (err) {
      console.error('Error al revocar declaración:', err);
      if (showToast) showToast('No se pudo reanudar la auditoría para ' + exchange, 'error');
    } finally {
      setRevokingExchange(null);
    }
  };

  const handleSyncSingleApi = async (apiId, exchangeName) => {
    const targetId = (apiId || exchangeName || '').toLowerCase().trim();
    setSyncingExchange(exchangeName);
    try {
      const baseUrl = (apiBase || config.API_URL || '').replace(/\/api\/?$/, '');
      const res = await axios.post(`${baseUrl}/api/sync/${encodeURIComponent(targetId)}`);
      const data = res.data;
      if (data.status === 'success') {
        const ins = data.total_inserted || 0;
        if (showToast) {
          showToast(
            ins > 0
              ? `✅ Sincronización de ${exchangeName}: ${ins} nuevas operaciones agregadas.`
              : `ℹ️ ${exchangeName} sincronizado: sin operaciones nuevas posteriores.`,
            'success'
          );
        }
        if (onRefreshWarnings) onRefreshWarnings();
      } else {
        const errMsg = (data.errors && data.errors.length > 0) ? data.errors.join('; ') : (data.error || 'Fallo de autenticación o conexión');
        if (showToast) showToast(`Error en API de ${exchangeName}: ${errMsg}`, 'error');
      }
    } catch (err) {
      console.error(`Error al sincronizar API de ${exchangeName}:`, err);
      if (showToast) showToast(`Error de conexión con la API de ${exchangeName}`, 'error');
    } finally {
      setSyncingExchange(null);
    }
  };

  const handleSyncAllApis = async () => {
    setSyncingAllApis(true);
    try {
      const baseUrl = (apiBase || config.API_URL || '').replace(/\/api\/?$/, '');
      const res = await axios.post(`${baseUrl}/api/sync`);
      const data = res.data;
      const ins = data.total_inserted || 0;
      if (showToast) {
        showToast(
          ins > 0
            ? `✅ Sincronización global completada: ${ins} nuevas operaciones incorporadas.`
            : 'ℹ️ Sincronización global completada: todas las APIs están al día.',
          'success'
        );
      }
      if (onRefreshWarnings) onRefreshWarnings();
    } catch (err) {
      console.error('Error en sincronización global de APIs:', err);
      if (showToast) showToast('Error al ejecutar sincronización de APIs', 'error');
    } finally {
      setSyncingAllApis(false);
    }
  };

  return (
    <>
      {/* Physical Custody Deficit Alerts */}
      {custodyDeficits && custodyDeficits.length > 0 && (
        <div style={{
          background: 'linear-gradient(135deg, rgba(239, 68, 68, 0.15), rgba(185, 28, 28, 0.25))',
          border: '1px solid rgba(239, 68, 68, 0.4)',
          borderRadius: 'var(--radius-md)',
          padding: '1rem 1.25rem',
          marginBottom: '1rem',
          display: 'flex',
          flexDirection: 'column',
          gap: '0.5rem'
        }}>
          <div style={{ fontSize: '0.88rem', fontWeight: 700, color: '#FCA5A5', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <AlertTriangle size={16} color="#EF4444" />
            Alerta Crítica: Déficit de Custodia Física por Exchange ({displayYear})
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', fontSize: '0.82rem', color: '#FEE2E2', lineHeight: 1.4 }}>
            {custodyDeficits.map((cd, idx) => (
              <div key={idx} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem', background: 'rgba(0,0,0,0.25)', padding: '0.5rem 0.75rem', borderRadius: '4px' }}>
                <span>{cd.message}</span>
                <span className="badge badge-amber font-mono font-bold" style={{ whiteSpace: 'nowrap' }}>
                  Déficit: {Number(cd.deficit).toLocaleString()} {cd.coin}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Stale Sources & Missing Deposit Alerts */}
      {(hasSourceAlerts || hasDeclaredSources) && (
        <div style={{
          background: hasSourceAlerts
            ? 'linear-gradient(135deg, rgba(245, 158, 11, 0.12), rgba(217, 119, 6, 0.2))'
            : 'linear-gradient(135deg, rgba(16, 185, 129, 0.08), rgba(5, 150, 105, 0.12))',
          border: hasSourceAlerts
            ? '1px solid rgba(245, 158, 11, 0.35)'
            : '1px solid rgba(16, 185, 129, 0.25)',
          borderRadius: 'var(--radius-md)',
          padding: '1rem 1.25rem',
          marginBottom: '1rem',
          display: 'flex',
          flexDirection: 'column',
          gap: '0.6rem'
        }}>
          <div style={{
            fontSize: '0.88rem',
            fontWeight: 700,
            color: hasSourceAlerts ? '#FDE68A' : '#A7F3D0',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '0.5rem'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              {hasSourceAlerts ? <Search size={16} color="#F59E0B" /> : <ShieldCheck size={16} color="#34D399" />}
              {hasSourceAlerts ? 'Desincronización de Fuentes y Extractos Faltantes' : 'Fuentes y Extractos al Día / Verificados'}
              {loadingWarnings && (
                <span style={{ fontSize: '0.72rem', color: '#94A3B8', fontWeight: 500, fontStyle: 'italic', marginLeft: '0.4rem' }}>
                  (Actualizando auditoría...)
                </span>
              )}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
              {hasSourceAlerts && onlineApiSources.length > 0 && (
                <button
                  type="button"
                  onClick={handleSyncAllApis}
                  disabled={syncingAllApis}
                  style={{
                    padding: '0.22rem 0.65rem',
                    borderRadius: '4px',
                    border: '1px solid rgba(59, 130, 246, 0.45)',
                    background: 'rgba(59, 130, 246, 0.2)',
                    color: '#93C5FD',
                    fontSize: '0.74rem',
                    fontWeight: 700,
                    cursor: syncingAllApis ? 'wait' : 'pointer',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '0.3rem',
                    transition: 'all 120ms ease'
                  }}
                  title="Sincronizar todas las conexiones API con un solo clic"
                >
                  <RefreshCw size={12} className={syncingAllApis ? "animate-spin" : ""} />
                  {syncingAllApis ? 'Sincronizando...' : `Sincronizar APIs (${onlineApiSources.length})`}
                </button>
              )}
              {hasSourceAlerts && staleSources.length > 1 && (
                <button
                  type="button"
                  onClick={handleDeclareAllStale}
                  disabled={declaringAll}
                  style={{
                    padding: '0.22rem 0.65rem',
                    borderRadius: '4px',
                    border: '1px solid rgba(16, 185, 129, 0.45)',
                    background: 'rgba(16, 185, 129, 0.2)',
                    color: '#34D399',
                    fontSize: '0.74rem',
                    fontWeight: 700,
                    cursor: declaringAll ? 'wait' : 'pointer',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '0.3rem',
                    transition: 'all 120ms ease'
                  }}
                  title="Declarar todas las fuentes desactualizadas sin movimientos en un solo clic"
                >
                  <CheckCircle2 size={12} /> {declaringAll ? 'Guardando...' : `Declarar todas al día (${staleSources.length})`}
                </button>
              )}
              {hasDeclaredSources && !hasSourceAlerts && (
                <span style={{ fontSize: '0.74rem', color: '#6EE7B7', fontWeight: 500 }}>
                  {declaredSources.length} fuente{declaredSources.length > 1 ? 's' : ''} declarada{declaredSources.length > 1 ? 's' : ''} sin actividad
                </span>
              )}
            </div>
          </div>

          {hasSourceAlerts && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.45rem', fontSize: '0.82rem', color: '#FEF3C7', lineHeight: 1.4 }}>
              {sourceAlerts.map((sa, idx) => (
                <div key={idx} style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  flexWrap: 'wrap',
                  gap: '0.5rem',
                  background: 'rgba(0,0,0,0.25)',
                  padding: '0.5rem 0.75rem',
                  borderRadius: '4px'
                }}>
                  <div style={{ flex: 1, minWidth: '240px', display: 'flex', alignItems: 'center', gap: '0.4rem', flexWrap: 'wrap' }}>
                    {sa.is_api && (
                      <span style={{
                        fontSize: '0.68rem',
                        fontWeight: 700,
                        padding: '0.12rem 0.4rem',
                        borderRadius: '3px',
                        background: sa.api_status === 'expired' ? 'rgba(239, 68, 68, 0.3)' : 'rgba(59, 130, 246, 0.25)',
                        color: sa.api_status === 'expired' ? '#FCA5A5' : '#93C5FD',
                        letterSpacing: '0.03em'
                      }}>
                        {sa.api_status === 'expired' ? 'API EXPIRADA' : 'CONEXIÓN API'}
                      </span>
                    )}
                    <span>{sa.message}</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', flexWrap: 'wrap' }}>
                    {/* Action 1: API Sync or Key Renewal */}
                    {sa.is_api && sa.api_status === 'expired' && (
                      <a
                        href="/apis"
                        style={{
                          padding: '0.22rem 0.65rem',
                          borderRadius: '4px',
                          border: '1px solid rgba(239, 68, 68, 0.5)',
                          background: 'rgba(239, 68, 68, 0.2)',
                          color: '#FCA5A5',
                          fontSize: '0.74rem',
                          fontWeight: 600,
                          textDecoration: 'none',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '0.3rem',
                          transition: 'all 120ms ease'
                        }}
                        title="Ir a renovar credenciales en la sección APIs"
                      >
                        <AlertCircle size={12} /> Renovar API Key
                      </a>
                    )}
                    {sa.is_api && sa.api_status !== 'expired' && (
                      <button
                        type="button"
                        disabled={syncingExchange === sa.exchange}
                        onClick={() => handleSyncSingleApi(sa.api_id, sa.exchange)}
                        style={{
                          padding: '0.22rem 0.65rem',
                          borderRadius: '4px',
                          border: '1px solid rgba(59, 130, 246, 0.45)',
                          background: 'rgba(59, 130, 246, 0.15)',
                          color: '#60A5FA',
                          fontSize: '0.74rem',
                          fontWeight: 600,
                          cursor: syncingExchange === sa.exchange ? 'wait' : 'pointer',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '0.3rem',
                          transition: 'all 120ms ease'
                        }}
                        title={`Sincronizar movimientos de ${sa.exchange} desde su API`}
                      >
                        <RefreshCw size={12} className={syncingExchange === sa.exchange ? "animate-spin" : ""} />
                        {syncingExchange === sa.exchange ? 'Sincronizando...' : 'Sincronizar API'}
                      </button>
                    )}

                    {/* Action 2: Declare up to date (no further operations) */}
                    {sa.type === 'stale_source' && (
                      <button
                        type="button"
                        onClick={() => onOpenDeclareModal(sa.exchange, sa.last_date)}
                        style={{
                          padding: '0.22rem 0.65rem',
                          borderRadius: '4px',
                          border: '1px solid rgba(16, 185, 129, 0.45)',
                          background: 'rgba(16, 185, 129, 0.15)',
                          color: '#34D399',
                          fontSize: '0.74rem',
                          fontWeight: 600,
                          cursor: 'pointer',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '0.3rem',
                          transition: 'all 120ms ease'
                        }}
                        title={`Declarar que no tuviste operaciones en ${sa.exchange} desde esa fecha`}
                      >
                        <CheckCircle2 size={12} /> Declarar al día
                      </button>
                    )}

                    <span className="badge font-mono" style={{
                      background: sa.severity === 'ALTA' ? 'rgba(239, 68, 68, 0.3)' : 'rgba(245, 158, 11, 0.3)',
                      color: '#FFF',
                      whiteSpace: 'nowrap'
                    }}>
                      {sa.type === 'stale_source' ? `Atraso: ${sa.days_behind}d` : 'Falta Historial'}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Acordeón Plegado de Fuentes Declaradas Sin Operaciones */}
          {hasDeclaredSources && (
            <div style={{
              marginTop: hasSourceAlerts ? '0.35rem' : '0',
              borderTop: hasSourceAlerts ? '1px solid rgba(245, 158, 11, 0.2)' : 'none',
              paddingTop: hasSourceAlerts ? '0.45rem' : '0'
            }}>
              <button
                type="button"
                onClick={() => setShowDeclaredSources(!showDeclaredSources)}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: hasSourceAlerts ? '#FDE68A' : '#A7F3D0',
                  fontSize: '0.78rem',
                  cursor: 'pointer',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.4rem',
                  padding: '0.2rem 0',
                  fontWeight: 600
                }}
              >
                <Eye size={13} />
                {showDeclaredSources ? 'Ocultar' : 'Ver'} {declaredSources.length} fuente{declaredSources.length > 1 ? 's' : ''} declarada{declaredSources.length > 1 ? 's' : ''} al día o sin actividad
                {showDeclaredSources ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
              </button>

              {showDeclaredSources && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', marginTop: '0.4rem' }}>
                  {declaredSources.map((ds, idx) => (
                    <div key={idx} style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      flexWrap: 'wrap',
                      gap: '0.5rem',
                      background: 'rgba(0,0,0,0.3)',
                      padding: '0.4rem 0.65rem',
                      borderRadius: '4px',
                      border: '1px solid rgba(255,255,255,0.06)'
                    }}>
                      <span style={{ fontSize: '0.78rem', color: '#E2E8F0' }}>
                        <strong style={{ color: '#34D399' }}>{ds.exchange}</strong>: {ds.reason}
                        {ds.last_date ? ` (última oper.: ${ds.last_date})` : ''}
                      </span>
                      <button
                        type="button"
                        disabled={revokingExchange === ds.exchange}
                        onClick={() => handleRevokeDeclaration(ds.exchange)}
                        style={{
                          padding: '0.2rem 0.55rem',
                          borderRadius: '4px',
                          border: '1px solid rgba(239, 68, 68, 0.4)',
                          background: 'rgba(239, 68, 68, 0.15)',
                          color: '#FCA5A5',
                          fontSize: '0.72rem',
                          fontWeight: 600,
                          cursor: revokingExchange === ds.exchange ? 'not-allowed' : 'pointer',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '0.25rem',
                          opacity: revokingExchange === ds.exchange ? 0.6 : 1
                        }}
                        title={`Reanudar auditoría continua para ${ds.exchange}`}
                      >
                        <RotateCcw size={11} /> {revokingExchange === ds.exchange ? 'Reanudando...' : 'Reanudar auditoría'}
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </>
  );
};

export default SourceAlertsCard;
