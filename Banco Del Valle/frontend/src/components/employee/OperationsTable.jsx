import React, { useState } from 'react';
import { Download, AlertTriangle, CheckCircle2, User, Building2 } from 'lucide-react';

/**
 * OperationsTable — Tabla gerencial de cartera crediticia con tracking exacto de mora (Alto contraste y Dark Mode).
 */
export function OperationsTable({ operaciones = [], onExportClick }) {
  const [filtro, setFiltro] = useState('TODOS'); // 'TODOS' | 'AL_DIA' | 'EN_MORA'

  const filtradas = operaciones.filter((op) => {
    if (filtro === 'AL_DIA') return (op.dias_mora ?? 0) === 0;
    if (filtro === 'EN_MORA') return (op.dias_mora ?? 0) > 0;
    return true;
  });

  const formatearPesos = (val) =>
    new Intl.NumberFormat('es-AR', {
      style: 'currency',
      currency: 'ARS',
      maximumFractionDigits: 0,
    }).format(val || 0);

  return (
    <div className="valle-card rounded-3xl p-6 sm:p-8 transition-colors duration-200">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-5 mb-5 border-b border-slate-200 dark:border-valle-darkBorder gap-3">
        <div>
          <h3 className="font-display font-extrabold text-lg sm:text-xl text-slate-900 dark:text-white">
            Cartera de Préstamos y Control de Morosidad
          </h3>
          <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-400 mt-0.5">
            Seguimiento de cuotas, cobranzas y devengamiento diario de punitorios.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {/* Filtros */}
          <div className="flex gap-1 bg-slate-100 dark:bg-valle-darkElevated p-1 rounded-xl text-xs font-semibold border border-slate-200 dark:border-valle-darkBorder">
            {['TODOS', 'AL_DIA', 'EN_MORA'].map((f) => (
              <button
                key={f}
                type="button"
                onClick={() => setFiltro(f)}
                className={`px-3 py-1.5 rounded-lg transition ${
                  filtro === f
                    ? 'bg-white dark:bg-valle-blue text-valle-blue dark:text-white shadow-xs font-bold'
                    : 'text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white'
                }`}
              >
                {f.replace('_', ' ')}
              </button>
            ))}
          </div>

          <button
            type="button"
            onClick={onExportClick}
            className="px-4 py-2 bg-valle-orange hover:bg-valle-orangedark text-white text-xs sm:text-sm font-bold rounded-xl shadow-xs transition flex items-center gap-1.5"
          >
            <Download className="w-4 h-4" />
            <span>Exportar Cartera</span>
          </button>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="bg-slate-50 dark:bg-valle-darkElevated text-slate-700 dark:text-slate-300 uppercase tracking-wider text-xs font-extrabold border-b border-slate-200 dark:border-valle-darkBorder">
              <th className="py-3.5 px-4">Titular / Razón Social</th>
              <th className="py-3.5 px-4">Segmento</th>
              <th className="py-3.5 px-4 text-right">Capital Prestado</th>
              <th className="py-3.5 px-4 text-right">Cuota Fija</th>
              <th className="py-3.5 px-4 text-center">Cuotas</th>
              <th className="py-3.5 px-4 text-center">Días de Mora</th>
              <th className="py-3.5 px-4 text-center">Situación BCRA</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200 dark:divide-valle-darkBorder font-medium">
            {filtradas.length === 0 ? (
              <tr>
                <td colSpan={7} className="py-10 text-center text-sm text-slate-500 dark:text-slate-400">
                  No se encontraron operaciones registradas con este criterio.
                </td>
              </tr>
            ) : (
              filtradas.map((op, idx) => {
                const enMora = (op.dias_mora ?? 0) > 0;
                return (
                  <tr key={idx} className="hover:bg-slate-50/80 dark:hover:bg-valle-darkElevated/60 transition">
                    <td className="py-4 px-4 font-bold text-slate-900 dark:text-white">
                      {op.titular || 'Titular Registrado'}
                    </td>
                    <td className="py-4 px-4 text-slate-600 dark:text-slate-300">
                      <span className="inline-flex items-center gap-1.5">
                        {op.tipo_titular === 'EMPRESA' ? (
                          <Building2 className="w-4 h-4 text-valle-blue dark:text-sky-400" />
                        ) : (
                          <User className="w-4 h-4 text-valle-orange" />
                        )}
                        <span>{op.tipo_titular || 'INDIVIDUO'}</span>
                      </span>
                    </td>
                    <td className="py-4 px-4 text-right font-mono text-slate-900 dark:text-slate-100 tabular-nums font-bold">
                      {formatearPesos(op.monto_capital || 1500000)}
                    </td>
                    <td className="py-4 px-4 text-right font-mono font-extrabold text-valle-orange tabular-nums">
                      {formatearPesos(op.monto_cuota || 148200)}
                    </td>
                    <td className="py-4 px-4 text-center text-slate-700 dark:text-slate-300 font-mono text-xs sm:text-sm">
                      {op.cuota_actual || 3}/{op.cantidad_cuotas || 24}
                    </td>
                    <td className="py-4 px-4 text-center">
                      <span
                        className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full font-bold text-xs ${
                          enMora
                            ? 'bg-rose-100 text-rose-900 dark:bg-rose-950/60 dark:text-rose-300 border border-rose-300 dark:border-rose-800'
                            : 'bg-emerald-100 text-emerald-900 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800'
                        }`}
                      >
                        {enMora ? (
                          <>
                            <AlertTriangle className="w-3.5 h-3.5 text-rose-600 dark:text-rose-400" />
                            <span>{op.dias_mora} días</span>
                          </>
                        ) : (
                          <>
                            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
                            <span>Al Día (0d)</span>
                          </>
                        )}
                      </span>
                    </td>
                    <td className="py-4 px-4 text-center">
                      <span className="px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-valle-darkElevated font-mono text-slate-800 dark:text-slate-200 text-xs font-bold border border-slate-200 dark:border-valle-darkBorder">
                        Sit. {op.situacion_bcra || 1}
                      </span>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default OperationsTable;
