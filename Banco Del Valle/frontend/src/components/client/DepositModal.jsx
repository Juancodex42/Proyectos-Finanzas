import React, { useState } from 'react';
import { X, Copy, Check, ArrowDownLeft, QrCode, ShieldCheck, CheckCircle2 } from 'lucide-react';
import { apiClient } from '../../services/apiClient';

/**
 * DepositModal — Información de cuenta (CBU / Alias) y Código QR Interoperable Transferencias 3.0.
 */
export function DepositModal({
  isOpen,
  onClose,
  cuentaId,
  cbu = '0000003100012345678901',
  alias = 'JUAN.BANCO.VALLE',
  onDepositSuccess,
}) {
  const [copiadoCbu, setCopiadoCbu] = useState(false);
  const [copiadoAlias, setCopiadoAlias] = useState(false);
  const [copiadoQr, setCopiadoQr] = useState(false);
  const [loading, setLoading] = useState(false);
  const [mensaje, setMensaje] = useState(null);

  if (!isOpen) return null;

  const handleCopiar = (texto, tipo) => {
    navigator.clipboard.writeText(texto);
    if (tipo === 'CBU') {
      setCopiadoCbu(true);
      setTimeout(() => setCopiadoCbu(false), 2000);
    } else if (tipo === 'ALIAS') {
      setCopiadoAlias(true);
      setTimeout(() => setCopiadoAlias(false), 2000);
    } else {
      setCopiadoQr(true);
      setTimeout(() => setCopiadoQr(false), 2000);
    }
  };

  const handleRecepcionInmediata = async () => {
    if (!cuentaId) return;
    setLoading(true);
    setMensaje(null);
    try {
      await apiClient.depositarPrueba({
        cuenta_id: cuentaId,
        monto: 500000,
        descripcion: 'Transferencia Inmediata Recibida — COELSA / Transferencias 3.0',
      });
      setMensaje('¡Transferencia inmediata acreditada en tu cuenta!');
      if (onDepositSuccess) onDepositSuccess();
      setTimeout(() => {
        setMensaje(null);
        onClose();
      }, 1500);
    } catch (err) {
      setMensaje(`Error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/75 backdrop-blur-sm animate-fade-in">
      <div className="relative w-full max-w-md bg-white dark:bg-valle-darkSurface rounded-3xl shadow-2xl border border-slate-200 dark:border-valle-darkBorder overflow-hidden">
        {/* Header */}
        <div className="bg-valle-blue dark:bg-valle-darkElevated px-6 py-4 flex items-center justify-between text-white border-b border-valle-blue/20 dark:border-valle-darkBorder">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-emerald-500/20 flex items-center justify-center">
              <ArrowDownLeft className="w-5 h-5 text-emerald-400" />
            </div>
            <h3 className="font-display font-bold text-base text-white">Ingresar Dinero / Datos de Cuenta</h3>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-300 hover:text-white hover:bg-white/10 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-5">
          {/* Código QR Interoperable Transferencias 3.0 */}
          <div className="p-4 bg-slate-50 dark:bg-valle-darkElevated rounded-2xl border border-slate-200 dark:border-valle-darkBorder text-center">
            <div className="w-32 h-32 bg-white p-2.5 rounded-2xl mx-auto shadow-xs border border-slate-200 flex items-center justify-center mb-2">
              <svg className="w-full h-full text-slate-900" viewBox="0 0 24 24" fill="currentColor">
                <path d="M2 2h8v8H2V2zm2 2v4h4V4H4zm10-2h8v8h-8V2zm2 2v4h4V4h-4zM2 14h8v8H2v-8zm2 2v4h4v-4H4zm14 0h4v4h-4v-4zm-4 4h4v4h-4v-4zm0-4h4v4h-4v-4zm4-4h4v4h-4v-4zm-4 0h4v4h-4v-4zM6 6h2v2H6V6zm10 0h2v2h-2V6zM6 16h2v2H6v-2z"/>
              </svg>
            </div>
            <span className="text-xs font-bold text-slate-800 dark:text-slate-200 block">
              QR Interoperable — Transferencias 3.0 / MODO
            </span>
            <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
              Escaneá desde cualquier billetera virtual o app bancaria para transferir al instante.
            </p>
          </div>

          {/* Ficha de Coordenadas */}
          <div className="space-y-3">
            <div className="p-3.5 bg-slate-50 dark:bg-valle-darkElevated border border-slate-200 dark:border-valle-darkBorder rounded-xl flex items-center justify-between">
              <div>
                <span className="text-xs uppercase font-bold text-slate-500 dark:text-slate-400 block tracking-wider">CBU (22 dígitos)</span>
                <span className="font-mono text-sm font-bold text-slate-900 dark:text-slate-100">{cbu}</span>
              </div>
              <button
                type="button"
                onClick={() => handleCopiar(cbu, 'CBU')}
                className="p-2 text-slate-600 dark:text-slate-400 hover:text-valle-orange dark:hover:text-valle-orange rounded-lg hover:bg-slate-200 dark:hover:bg-slate-800 transition"
                title="Copiar CBU"
              >
                {copiadoCbu ? <Check className="w-4 h-4 text-emerald-600 dark:text-emerald-400" /> : <Copy className="w-4 h-4" />}
              </button>
            </div>

            <div className="p-3.5 bg-slate-50 dark:bg-valle-darkElevated border border-slate-200 dark:border-valle-darkBorder rounded-xl flex items-center justify-between">
              <div>
                <span className="text-xs uppercase font-bold text-slate-500 dark:text-slate-400 block tracking-wider">Alias Bancario Único</span>
                <span className="font-mono text-sm font-bold text-valle-blue dark:text-valle-orange">{alias}</span>
              </div>
              <button
                type="button"
                onClick={() => handleCopiar(alias, 'ALIAS')}
                className="p-2 text-slate-600 dark:text-slate-400 hover:text-valle-orange dark:hover:text-valle-orange rounded-lg hover:bg-slate-200 dark:hover:bg-slate-800 transition"
                title="Copiar Alias"
              >
                {copiadoAlias ? <Check className="w-4 h-4 text-emerald-600 dark:text-emerald-400" /> : <Copy className="w-4 h-4" />}
              </button>
            </div>
          </div>

          {/* Información y Acreditación Inmediata */}
          <div className="pt-3 border-t border-slate-200 dark:border-valle-darkBorder space-y-3">
            <div className="flex items-center gap-2 text-xs text-slate-600 dark:text-slate-400">
              <ShieldCheck className="w-4 h-4 text-emerald-600 dark:text-emerald-400 flex-shrink-0" />
              <span>Acreditación inmediata 24/7 sin costo ni comisiones de ingreso.</span>
            </div>

            <button
              type="button"
              onClick={handleRecepcionInmediata}
              disabled={loading}
              className="w-full py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs sm:text-sm rounded-xl transition flex items-center justify-center gap-2 disabled:opacity-50 shadow-xs"
            >
              <CheckCircle2 className="w-4 h-4" />
              <span>Simular Recepción de Transferencia Inmediata</span>
            </button>

            {mensaje && (
              <div className="p-3 text-center text-xs font-semibold rounded-xl bg-emerald-50 dark:bg-emerald-950/40 text-emerald-800 dark:text-emerald-200 border border-emerald-200 dark:border-emerald-800/60">
                {mensaje}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default DepositModal;
