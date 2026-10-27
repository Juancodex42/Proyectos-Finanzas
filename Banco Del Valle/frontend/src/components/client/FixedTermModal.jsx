import React, { useState } from 'react';
import { X, Clock, AlertTriangle, CheckCircle2, ArrowRight, Loader2, RefreshCw } from 'lucide-react';
import { apiClient } from '../../services/apiClient';

/**
 * FixedTermModal — Constitución y cancelación anticipada de plazos fijos sin intereses (BCRA).
 */
export function FixedTermModal({
  isOpen,
  onClose,
  personaId,
  saldoDisponible = 3000000,
  plazosFijos = [],
  onUpdateSuccess,
}) {
  const [monto, setMonto] = useState(1000000);
  const [dias, setDias] = useState(30);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  if (!isOpen) return null;

  const tna = 0.38; // 38%
  const gananciaEstimada = monto * (tna / 365) * dias;

  const handleConstituir = async (e) => {
    e.preventDefault();
    if (!personaId) return;
    if (monto > saldoDisponible) {
      setError('El monto supera tu saldo disponible en cuenta');
      return;
    }

    setLoading(true);
    setError(null);
    setSuccess(null);
    try {
      await apiClient.constituirPlazoFijo({
        persona_id: personaId,
        monto: Number(monto),
        plazo_dias: Number(dias),
      });
      setSuccess('¡Plazo fijo constituido con éxito!');
      if (onUpdateSuccess) onUpdateSuccess();
      setTimeout(() => setSuccess(null), 2500);
    } catch (err) {
      setError(err.message || 'Error al constituir plazo fijo');
    } finally {
      setLoading(false);
    }
  };

  const handleCancelarAnticipado = async (pfId) => {
    if (!window.confirm('¿Confirmás la cancelación anticipada? Conforme norma BCRA, recibirás el 100% de tu capital pero resignarás la totalidad de los intereses ($0 ganancia).')) {
      return;
    }

    setLoading(true);
    setError(null);
    try {
      await apiClient.cancelarPlazoFijo(pfId);
      setSuccess('Plazo fijo cancelado. Capital reintegrado a tu cuenta.');
      if (onUpdateSuccess) onUpdateSuccess();
      setTimeout(() => setSuccess(null), 2500);
    } catch (err) {
      setError(err.message || 'Error al cancelar plazo fijo');
    } finally {
      setLoading(false);
    }
  };

  const formatearPesos = (val) =>
    new Intl.NumberFormat('es-AR', {
      style: 'currency',
      currency: 'ARS',
      maximumFractionDigits: 0,
    }).format(val || 0);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/75 backdrop-blur-sm animate-fade-in">
      <div className="relative w-full max-w-xl bg-white dark:bg-valle-darkSurface rounded-2xl shadow-2xl border border-slate-200 dark:border-valle-darkBorder overflow-hidden max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="bg-valle-blue dark:bg-valle-darkElevated px-6 py-4 flex items-center justify-between text-white border-b border-valle-blue/20 dark:border-valle-darkBorder flex-shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-valle-orange/20 flex items-center justify-center">
              <Clock className="w-5 h-5 text-valle-orange" />
            </div>
            <h3 className="font-display font-bold text-base text-white">
              Gestión de Plazos Fijos Tradicionales
            </h3>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-300 hover:text-white hover:bg-white/10 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-6 overflow-y-auto">
          {/* Formulario de Constitución */}
          <form onSubmit={handleConstituir} className="space-y-4 bg-slate-50 dark:bg-valle-darkElevated p-5 rounded-2xl border border-slate-200 dark:border-valle-darkBorder">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300">
              Constituir Nuevo Certificado
            </h4>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs sm:text-sm font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
                  Monto a Invertir ($)
                </label>
                <input
                  type="number"
                  min="50000"
                  max={saldoDisponible}
                  value={monto}
                  onChange={(e) => setMonto(Number(e.target.value))}
                  className="w-full text-sm px-3.5 py-2.5 border border-slate-300 dark:border-valle-darkBorder rounded-xl outline-none focus:ring-2 focus:ring-valle-orange font-mono bg-white dark:bg-valle-darkSurface text-slate-900 dark:text-slate-100"
                />
              </div>

              <div>
                <label className="block text-xs sm:text-sm font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
                  Plazo en Días
                </label>
                <div className="flex gap-2">
                  {[30, 60, 90].map((d) => (
                    <button
                      key={d}
                      type="button"
                      onClick={() => setDias(d)}
                      className={`flex-1 py-2 text-xs sm:text-sm font-bold rounded-xl border transition ${
                        dias === d
                          ? 'bg-valle-blue dark:bg-valle-orange text-white border-valle-blue dark:border-valle-orange shadow-sm'
                          : 'bg-white dark:bg-valle-darkSurface border-slate-200 dark:border-valle-darkBorder text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800'
                      }`}
                    >
                      {d}d
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-1 text-xs sm:text-sm text-slate-600 dark:text-slate-300 pt-3 border-t border-slate-200 dark:border-valle-darkBorder">
              <span>TNA fija pactada: <strong className="text-slate-900 dark:text-white">38.0%</strong></span>
              <span>Interés estimado al vencimiento: <strong className="text-valle-orange font-mono text-sm sm:text-base">{formatearPesos(gananciaEstimada)}</strong></span>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 bg-valle-orange hover:bg-valle-orangedark text-white font-bold text-sm rounded-xl shadow-md transition flex items-center justify-center gap-2 disabled:opacity-50"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <span>Confirmar Constitución de Plazo Fijo</span>}
            </button>
          </form>

          {/* Mensajes */}
          {error && (
            <div className="p-3 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800/60 text-red-700 dark:text-red-300 text-xs sm:text-sm rounded-xl font-medium">
              {error}
            </div>
          )}
          {success && (
            <div className="p-3 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800/60 text-emerald-800 dark:text-emerald-200 text-xs sm:text-sm rounded-xl flex items-center gap-2 font-medium">
              <CheckCircle2 className="w-5 h-5 text-emerald-600 dark:text-emerald-400 flex-shrink-0" />
              <span>{success}</span>
            </div>
          )}

          {/* Listado de Plazos Fijos Vigentes */}
          <div>
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300 mb-3">
              Tus Certificados Activos ({plazosFijos.length})
            </h4>

            {plazosFijos.length === 0 ? (
              <p className="text-sm text-slate-500 dark:text-slate-400 py-4 text-center bg-slate-50 dark:bg-valle-darkElevated rounded-xl border border-dashed border-slate-200 dark:border-valle-darkBorder">
                No tienes plazos fijos activos en este momento.
              </p>
            ) : (
              <div className="space-y-3">
                {plazosFijos.map((pf) => (
                  <div
                    key={pf.id}
                    className="p-4 bg-white dark:bg-valle-darkElevated border border-slate-200 dark:border-valle-darkBorder rounded-xl flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-xs"
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-display font-bold text-slate-900 dark:text-slate-50 text-base">
                          {formatearPesos(pf.monto_depositado)}
                        </span>
                        <span className="text-xs px-2.5 py-0.5 rounded-full font-bold bg-blue-100 dark:bg-blue-950/60 text-blue-800 dark:text-blue-300 border border-blue-200 dark:border-blue-800/60">
                          {pf.estado}
                        </span>
                      </div>
                      <span className="text-xs text-slate-600 dark:text-slate-400 block mt-1">
                        Vence: {pf.fecha_vencimiento} | Interés a generar: <strong className="text-slate-700 dark:text-slate-200">{formatearPesos(pf.intereses_a_generar)}</strong>
                      </span>
                    </div>

                    {pf.estado === 'ACTIVO' && (
                      <button
                        type="button"
                        onClick={() => handleCancelarAnticipado(pf.id)}
                        disabled={loading}
                        className="px-3.5 py-2 bg-red-50 dark:bg-red-950/40 hover:bg-red-100 dark:hover:bg-red-900/50 text-red-700 dark:text-red-300 border border-red-200 dark:border-red-800/60 rounded-xl text-xs font-bold transition"
                      >
                        Cancelar sin Intereses
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default FixedTermModal;
