import React, { useState, useEffect } from 'react';
import { Wand2, ChevronRight, CheckCircle2, UploadCloud, RefreshCw, X, ArrowRight } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import axios from 'axios';

const GuidedResolverModal = ({ isOpen, warning, onClose, apiBase, onResolved, showToast }) => {
  const [resolverStep, setResolverStep] = useState(1);
  const [resolverSubmitting, setResolverSubmitting] = useState(false);
  const [resolverError, setResolverError] = useState('');
  const [resolverSuccess, setResolverSuccess] = useState('');
  const [inModalUploading, setInModalUploading] = useState(false);
  const [inModalUploadMsg, setInModalUploadMsg] = useState(null);

  const [resolverData, setResolverData] = useState({
    exchange: '', crypto: '', date: '', missing: '', price: '',
    currency: 'USD', type: 'deposit', origin: 'unknown', notes: ''
  });

  useEffect(() => {
    if (warning) {
      setResolverStep(1);
      setResolverError('');
      setResolverSuccess('');
      setInModalUploadMsg(null);
      const parts = warning.date ? String(warning.date).trim().split(' ') : [''];
      const rawTime = parts.length > 1 ? parts[1] : '00:00:01';
      setResolverData({
        exchange: warning.exchange || '',
        crypto: warning.coin || '',
        date: parts[0] || '',
        rawTime,
        missing: warning.deficit ? String(Math.abs(warning.deficit)) : String(warning.sold_qty || ''),
        price: '', currency: 'USD', type: 'deposit', origin: 'unknown', notes: ''
      });
    }
  }, [warning]);

  const handleInModalUpload = async (files) => {
    if (!files || files.length === 0) return;
    setInModalUploading(true);
    setInModalUploadMsg(null);

    const formData = new FormData();
    for (let i = 0; i < files.length; i++) {
      formData.append('files[]', files[i]);
    }
    if (resolverData.exchange && resolverData.exchange !== 'Cartera Global') {
      formData.append('override_exchange', resolverData.exchange);
    }

    try {
      const uploadRes = await axios.post(`${apiBase}/upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });

      if (uploadRes.data && uploadRes.data.status === 'success') {
        const totalTx = uploadRes.data.total_transactions || 0;
        if (totalTx > 0) {
          setInModalUploadMsg({ type: 'success', text: `✓ Archivo cargado (${totalTx} operaciones nuevas). Conciliando ${resolverData.exchange}...` });
          if (showToast) showToast(`Archivo procesado con éxito (${totalTx} operaciones). Reconciliando...`, 'success');
          setTimeout(() => {
            if (onResolved) onResolved();
            onClose();
          }, 1500);
        } else {
          const warnMsg = uploadRes.data.message || 'El archivo fue leído pero no contenía transacciones nuevas (o ya estaban importadas / en período certificado).';
          setInModalUploadMsg({ type: 'warning', text: `⚠️ ${warnMsg}` });
          if (showToast) showToast(warnMsg, 'warning');
        }
      } else {
        const errMsg = uploadRes.data?.message || 'Error en la subida.';
        setInModalUploadMsg({ type: 'error', text: `⚠️ ${errMsg}` });
      }
    } catch (err) {
      console.error(err);
      const errMsg = err.response?.data?.error || err.response?.data?.message || err.message || 'Error de red';
      setInModalUploadMsg({ type: 'error', text: `⚠️ ${errMsg}` });
    } finally {
      setInModalUploading(false);
    }
  };

  const handleApiSync = async () => {
    if (!resolverData.exchange || resolverData.exchange === 'Cartera Global') {
      if (showToast) showToast('La sincronización API debe ejecutarse para un exchange específico, no para Cartera Global.', 'warning');
      return;
    }
    if (showToast) showToast(`Sincronizando API de ${resolverData.exchange}...`, 'info');
    try {
      const rawEx = resolverData.exchange.toLowerCase();
      const slug = rawEx.includes('binance') ? 'binance' : rawEx.includes('bitso') ? 'bitso' : rawEx.includes('ripio') ? 'ripio_trade' : rawEx.includes('bitget') ? 'bitget' : rawEx.includes('bybit') ? 'bybit' : rawEx.includes('okx') ? 'okx' : rawEx;
      const res = await axios.post(`${apiBase}/api_sync/${encodeURIComponent(slug)}`);
      if (res.data?.status === 'error') {
        throw new Error(res.data?.errors?.[0] || res.data?.error || 'Error de sincronización');
      }
      if (res.data?.skipped) {
        if (showToast) showToast(`ℹ️ Sincronización omitida: ${res.data?.reason || 'Sin credenciales o ya al día'}.`, 'info');
        return;
      }
      if (showToast) showToast(`✓ API de ${resolverData.exchange} sincronizada.`, 'success');
      if (onResolved) onResolved();
      onClose();
    } catch (err) {
      console.error(err);
      if (showToast) showToast(err.message || `Error al sincronizar API de ${resolverData.exchange}`, 'error');
    }
  };

  const handleResolverSubmit = async (e) => {
    e.preventDefault();
    if (resolverStep === 1) { setResolverStep(2); return; }
    if (resolverStep === 2) { setResolverStep(3); return; }

    setResolverSubmitting(true);
    setResolverError('');
    try {
      let dateToSend = (resolverData.date && resolverData.date.length === 10)
        ? `${resolverData.date} 00:00:01`
        : (resolverData.date || warning.date);
      if (dateToSend && dateToSend.length > 10 && resolverData.rawTime) {
        const parts = dateToSend.split(' ');
        if (parts.length === 2 && parts[1] === resolverData.rawTime) {
          dateToSend = `${parts[0]} 00:00:01`;
        }
      }

      const res = await axios.post(`${apiBase}/reconciliation/resolve_gap`, {
        exchange: resolverData.exchange,
        crypto: resolverData.crypto,
        date: dateToSend,
        amount: parseFloat(resolverData.missing) || 0,
        price: parseFloat(resolverData.price) || 0,
        currency: resolverData.currency || 'USD',
        type: resolverData.type,
        origin: resolverData.origin,
        notes: resolverData.notes
      });

      if (res.data && res.data.success) {
        setResolverSuccess('¡Ajuste aplicado exitosamente!');
        if (showToast) showToast('¡Hueco FIFO resuelto con éxito!', 'success');
        setTimeout(() => {
          if (onResolved) onResolved();
          onClose();
        }, 1000);
      } else {
        setResolverError(res.data?.error || 'No se pudo aplicar el ajuste.');
      }
    } catch (err) {
      console.error(err);
      setResolverError(err.response?.data?.error || err.message || 'Error al guardar el ajuste.');
    } finally {
      setResolverSubmitting(false);
    }
  };

  if (!isOpen || !warning) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
        style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(9, 13, 20, 0.85)', backdropFilter: 'blur(8px)', zIndex: 2500,
          display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '1.5rem'
        }}
      >
        <motion.div
          initial={{ scale: 0.94, y: 15 }} animate={{ scale: 1, y: 0 }} exit={{ scale: 0.94, y: 15 }}
          className="card-surface"
          style={{
            width: '100%', maxWidth: '560px', padding: '1.75rem',
            border: '1px solid var(--accent-amber-border)', boxShadow: 'var(--shadow-lg)'
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
            <h3 style={{ margin: 0, fontSize: '1.2rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#FBBF24' }}>
              <Wand2 size={20} /> Resolutor Guiado de Advertencias
            </h3>
            <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}>
              <X size={18} />
            </button>
          </div>

          {/* Steps Progress */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '1.25rem', background: '#0D131F', padding: '0.5rem 0.85rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', color: resolverStep === 1 ? 'var(--brand-indigo-light)' : '#34D399', fontWeight: 600, fontSize: '0.78rem' }}>
              <span style={{ width: '18px', height: '18px', borderRadius: '50%', background: resolverStep === 1 ? 'var(--brand-indigo)' : '#10B981', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.7rem' }}>1</span>
              Diagnóstico
            </div>
            <ChevronRight size={13} color="var(--text-muted)" />
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', color: resolverStep === 2 ? 'var(--brand-indigo-light)' : resolverStep === 3 ? '#34D399' : 'var(--text-muted)', fontWeight: 600, fontSize: '0.78rem' }}>
              <span style={{ width: '18px', height: '18px', borderRadius: '50%', background: resolverStep === 2 ? 'var(--brand-indigo)' : resolverStep === 3 ? '#10B981' : '#334155', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.7rem' }}>2</span>
              Datos
            </div>
            <ChevronRight size={13} color="var(--text-muted)" />
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', color: resolverStep === 3 ? '#34D399' : 'var(--text-muted)', fontWeight: 600, fontSize: '0.78rem' }}>
              <span style={{ width: '18px', height: '18px', borderRadius: '50%', background: resolverStep === 3 ? '#10B981' : '#334155', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.7rem' }}>3</span>
              Confirmar
            </div>
          </div>

          {resolverError && (
            <div style={{ background: 'var(--accent-rose-subtle)', border: '1px solid var(--accent-rose-border)', borderRadius: 'var(--radius-sm)', padding: '0.65rem', marginBottom: '1rem', color: 'var(--accent-rose-light)', fontSize: '0.82rem' }}>
              {resolverError}
            </div>
          )}

          {resolverSuccess && (
            <div style={{ background: 'var(--accent-emerald-subtle)', border: '1px solid var(--accent-emerald-border)', borderRadius: 'var(--radius-sm)', padding: '0.65rem', marginBottom: '1rem', color: 'var(--accent-emerald-light)', fontSize: '0.82rem', display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
              <CheckCircle2 size={16} /> {resolverSuccess}
            </div>
          )}

          <form onSubmit={handleResolverSubmit}>
            {resolverStep === 1 && (
              <div>
                <div style={{ background: 'var(--accent-amber-subtle)', border: '1px solid var(--accent-amber-border)', borderRadius: 'var(--radius-md)', padding: '0.85rem', marginBottom: '1.15rem' }}>
                  <h4 style={{ margin: '0 0 0.35rem 0', fontSize: '0.88rem', color: '#FEF08A' }}>Detalle de la Operación Afectada</h4>
                  <p style={{ margin: 0, fontSize: '0.82rem', color: '#CBD5E1', lineHeight: '1.4' }}>
                    <strong>Exchange:</strong> {resolverData.exchange}<br />
                    <strong>Fecha de la Venta:</strong> {resolverData.date}<br />
                    <strong>Cripto & Monto Faltante:</strong> {resolverData.missing} {resolverData.crypto}
                  </p>
                </div>

                <div style={{ display: 'grid', gap: '0.75rem', marginBottom: '1.25rem' }}>
                  {/* Vía 1: In-situ dropzone */}
                  <div style={{ background: '#0D131F', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)', padding: '0.85rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', marginBottom: '0.65rem' }}>
                      <UploadCloud size={18} color="var(--brand-indigo-light)" />
                      <strong style={{ fontSize: '0.85rem', color: '#F8FAFC' }}>
                        Vía 1: Cargar Excel / CSV de {resolverData.exchange}
                      </strong>
                    </div>
                    <div
                      className="upload-zone-refined"
                      style={{ padding: '0.85rem' }}
                      onClick={() => document.getElementById('resolverFileInputInSitu').click()}
                      onDragOver={(e) => e.preventDefault()}
                      onDrop={(e) => {
                        e.preventDefault();
                        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                          handleInModalUpload(e.dataTransfer.files);
                        }
                      }}
                    >
                      <input
                        id="resolverFileInputInSitu"
                        type="file"
                        multiple
                        style={{ display: 'none' }}
                        onChange={(e) => {
                          handleInModalUpload(e.target.files);
                          e.target.value = '';
                        }}
                      />
                      <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                        Arrastrá el archivo aquí o hacé clic para explorar
                      </div>
                    </div>
                    {inModalUploading && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginTop: '0.5rem', fontSize: '0.8rem', color: 'var(--brand-indigo-light)' }}>
                        <RefreshCw size={12} className="spin" /> Subiendo y procesando extracto...
                      </div>
                    )}
                    {inModalUploadMsg && (
                      <div style={{ marginTop: '0.5rem', fontSize: '0.8rem', color: inModalUploadMsg.type === 'success' ? '#34D399' : inModalUploadMsg.type === 'warning' ? '#FBBF24' : '#FB7185' }}>
                        {inModalUploadMsg.text}
                      </div>
                    )}
                  </div>

                  {/* Vía 2: API Sync */}
                  <div style={{ background: '#0D131F', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)', padding: '0.85rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <strong style={{ fontSize: '0.85rem', color: '#F8FAFC', display: 'block' }}>Vía 2: Sincronización Automática API</strong>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Consultar movimientos faltantes directamente a {resolverData.exchange}</span>
                    </div>
                    <button type="button" className="btn-secondary" style={{ fontSize: '0.78rem', padding: '0.35rem 0.75rem' }} onClick={handleApiSync}>
                      <RefreshCw size={13} /> Sincronizar
                    </button>
                  </div>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.65rem' }}>
                  <button type="button" onClick={onClose} className="btn-outline">Cancelar</button>
                  <button type="submit" className="btn-primary" style={{ background: 'linear-gradient(135deg, #10B981, #059669)', border: 'none', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                    Vía 3: Ingreso Manual de Saldo <ArrowRight size={14} />
                  </button>
                </div>
              </div>
            )}

            {resolverStep === 2 && (
              <div>
                <div style={{ display: 'grid', gap: '0.85rem', marginBottom: '1.25rem' }}>
                  <div>
                    <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.25rem' }}>Cripto y Cantidad de Ajuste</label>
                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                      <input type="text" value={resolverData.crypto} readOnly className="input-field font-mono" style={{ width: '90px', background: '#0D131F' }} />
                      <input type="number" step="any" value={resolverData.missing} onChange={(e) => setResolverData({ ...resolverData, missing: e.target.value })} className="input-field font-mono" required />
                    </div>
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                    <div>
                      <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.25rem' }}>Fecha del Saldo Inicial / Compra</label>
                      <input type="date" value={resolverData.date} onChange={(e) => setResolverData({ ...resolverData, date: e.target.value })} className="input-field font-mono" required />
                    </div>
                    <div>
                      <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.25rem' }}>Costo Unitario (Opcional)</label>
                      <div style={{ display: 'flex', gap: '0.35rem' }}>
                        <select value={resolverData.currency || 'USD'} onChange={(e) => setResolverData({ ...resolverData, currency: e.target.value })} className="input-field font-mono" style={{ width: '85px', padding: '0.35rem' }}>
                          <option value="USD">USD</option>
                          <option value="ARS">ARS</option>
                        </select>
                        <input type="number" step="any" placeholder="0.00" value={resolverData.price} onChange={(e) => setResolverData({ ...resolverData, price: e.target.value })} className="input-field font-mono" style={{ flex: 1 }} />
                      </div>
                      {(!resolverData.price || parseFloat(resolverData.price) === 0) && (
                        <div style={{ fontSize: '0.72rem', color: '#FBBF24', marginTop: '0.35rem', lineHeight: 1.3 }}>
                          ⚠️ Si se deja en 0, AFIP considerará el 100% de la venta posterior como ganancia gravada neta.
                        </div>
                      )}
                    </div>
                  </div>

                  <div>
                    <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.25rem' }}>
                      Origen del Saldo
                    </label>
                    <select
                      value={resolverData.origin}
                      onChange={(e) => setResolverData({ ...resolverData, origin: e.target.value })}
                      className="input-field"
                    >
                      <option value="cold_wallet">Billetera Fría / Personal (Ledger/Metamask)</option>
                      <option value="initial_balance">Saldo Previo al Sistema (Inventario Inicial)</option>
                      <option value="airdrop">Airdrop / Staking / Regalo</option>
                      <option value="p2p_untracked">Compra P2P en Efectivo No Registrada</option>
                      <option value="unknown">Otro / A determinar</option>
                    </select>
                  </div>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <button type="button" onClick={() => setResolverStep(1)} className="btn-outline">
                    ← Volver
                  </button>
                  <button type="submit" className="btn-primary">
                    Continuar a Confirmación →
                  </button>
                </div>
              </div>
            )}

            {resolverStep === 3 && (
              <div>
                <div style={{ background: '#0D131F', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)', padding: '1rem', marginBottom: '1.25rem' }}>
                  <h4 style={{ margin: '0 0 0.5rem 0', fontSize: '0.9rem', color: '#F8FAFC' }}>Resumen de la Inyección Contable</h4>
                  <ul style={{ margin: 0, paddingLeft: '1.25rem', fontSize: '0.82rem', color: '#CBD5E1', lineHeight: '1.5' }}>
                    <li>Se registrará una operación de <strong>Compra / Depósito Inicial</strong> en <strong>{resolverData.exchange}</strong>.</li>
                    <li>Cantidad: <strong>{resolverData.missing} {resolverData.crypto}</strong></li>
                    <li>Fecha: <strong>{resolverData.date}</strong></li>
                    <li>Costo unitario: <strong>{resolverData.price && parseFloat(resolverData.price) > 0 ? `${resolverData.price} ${resolverData.currency || 'USD'}` : '$0.00 (Costo cero - Advertencia Fiscal)'}</strong></li>
                    <li>Origen: <strong>{resolverData.origin}</strong></li>
                  </ul>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <button type="button" onClick={() => setResolverStep(2)} className="btn-outline" disabled={resolverSubmitting}>
                    ← Modificar Datos
                  </button>
                  <button
                    type="submit"
                    className="btn-primary"
                    disabled={resolverSubmitting}
                    style={{ background: 'linear-gradient(135deg, #10B981, #059669)' }}
                  >
                    {resolverSubmitting ? (
                      <>
                        <RefreshCw size={14} className="spin" /> Guardando ajuste...
                      </>
                    ) : (
                      '✓ Confirmar e Inyectar Ajuste'
                    )}
                  </button>
                </div>
              </div>
            )}
          </form>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
};

export default GuidedResolverModal;
