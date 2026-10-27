import React, { useState } from 'react';
import { X, ArrowUpRight, AlertTriangle, ShieldCheck } from 'lucide-react';

/**
 * TransferModal — Flujo de transferencia de fondos con contingencia realista COELSA.
 */
export function TransferModal({ isOpen, onClose, saldoDisponible = 3000000 }) {
  const [paso, setPaso] = useState(1); // 1: Datos, 2: Contingencia COELSA
  const [monto, setMonto] = useState('');
  const [destino, setDestino] = useState('');
  const [error, setError] = useState(null);

  if (!isOpen) return null;

  const handleTransferir = (e) => {
    e.preventDefault();
    const val = Number(monto);
    if (!val || val <= 0) {
      setError('Ingresá un monto válido');
      return;
    }
    if (val > saldoDisponible) {
      setError('El monto supera tu saldo disponible en cuenta');
      return;
    }
    if (!destino.trim()) {
      setError('Ingresá un CBU, CVU o Alias de destino');
      return;
    }

    // Pasa al mensaje de contingencia COELSA
    setError(null);
    setPaso(2);
  };

  const handleCerrar = () => {
    setPaso(1);
    setMonto('');
    setDestino('');
    setError(null);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/75 backdrop-blur-sm animate-fade-in">
      <div className="relative w-full max-w-md bg-white dark:bg-valle-darkSurface rounded-2xl shadow-2xl border border-slate-200 dark:border-valle-darkBorder overflow-hidden">
        {/* Header */}
        <div className="bg-valle-blue dark:bg-valle-darkElevated px-6 py-4 flex items-center justify-between text-white border-b border-valle-blue/20 dark:border-valle-darkBorder">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-valle-orange/20 flex items-center justify-center">
              <ArrowUpRight className="w-5 h-5 text-valle-orange" />
            </div>
            <h3 className="font-display font-bold text-base text-white">Transferir Dinero</h3>
          </div>
          <button
            onClick={handleCerrar}
            className="p-1.5 rounded-lg text-slate-300 hover:text-white hover:bg-white/10 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6">
          {paso === 1 ? (
            <form onSubmit={handleTransferir} className="space-y-4">
              <div>
                <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200 mb-1.5">
                  Monto a Transferir ($)
                </label>
                <input
                  type="number"
                  required
                  min="1"
                  max={saldoDisponible}
                  value={monto}
                  onChange={(e) => setMonto(e.target.value)}
                  placeholder="ej. 50000"
                  className="w-full text-base px-3.5 py-2.5 bg-white dark:bg-valle-darkElevated border border-slate-300 dark:border-valle-darkBorder rounded-xl outline-none focus:ring-2 focus:ring-valle-orange font-mono text-slate-900 dark:text-slate-100 placeholder:text-slate-400 dark:placeholder:text-slate-500"
                />
                <span className="text-xs text-slate-600 dark:text-slate-400 mt-1.5 block font-medium">
                  Saldo disponible: ${saldoDisponible.toLocaleString('es-AR')}
                </span>
              </div>

              <div>
                <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200 mb-1.5">
                  CBU, CVU (22 dígitos) o Alias Destino
                </label>
                <input
                  type="text"
                  required
                  value={destino}
                  onChange={(e) => setDestino(e.target.value)}
                  placeholder="ej. MARA.VALLE.PAGO"
                  className="w-full text-sm px-3.5 py-2.5 bg-white dark:bg-valle-darkElevated border border-slate-300 dark:border-valle-darkBorder rounded-xl outline-none focus:ring-2 focus:ring-valle-orange text-slate-900 dark:text-slate-100 placeholder:text-slate-400 dark:placeholder:text-slate-500"
                />
              </div>

              {error && (
                <div className="p-3 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800/60 text-red-700 dark:text-red-300 text-xs rounded-xl font-medium">
                  {error}
                </div>
              )}

              <button
                type="submit"
                className="w-full py-3 bg-valle-blue hover:bg-valle-bluelight text-white font-bold text-sm rounded-xl shadow-md transition"
              >
                Continuar con la Transferencia
              </button>
            </form>
          ) : (
            /* Modal Realista de Contingencia COELSA */
            <div className="text-center space-y-4 py-2">
              <div className="w-14 h-14 bg-amber-100 dark:bg-amber-950/50 text-amber-600 dark:text-amber-400 rounded-full flex items-center justify-center mx-auto border border-amber-200 dark:border-amber-800/50">
                <AlertTriangle className="w-7 h-7" />
              </div>

              <div>
                <h4 className="font-display font-bold text-lg text-slate-900 dark:text-slate-50">
                  Mantenimiento del Sistema Nacional de Pagos
                </h4>
                <p className="text-sm text-slate-600 dark:text-slate-300 mt-1.5 leading-relaxed">
                  La red interbancaria <strong>COELSA / BCRA</strong> se encuentra en ventana de mantenimiento preventivo.
                </p>
              </div>

              <div className="p-3.5 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800/60 rounded-xl text-xs sm:text-sm text-emerald-800 dark:text-emerald-200 flex items-center gap-2.5 text-left">
                <ShieldCheck className="w-5 h-5 text-emerald-600 dark:text-emerald-400 flex-shrink-0" />
                <span>
                  Tu saldo permanece <strong>intacto y 100% seguro</strong> en tu Caja de Ahorro.
                </span>
              </div>

              <button
                type="button"
                onClick={handleCerrar}
                className="w-full py-3 bg-valle-orange hover:bg-valle-orangedark text-white font-bold text-sm rounded-xl shadow-md transition"
              >
                Entendido, volver a mi cuenta
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default TransferModal;
