import React from 'react';
import { ArrowDownLeft, ArrowUpRight, TrendingUp, Download, Sparkles } from 'lucide-react';

/**
 * TransactionsTable — Tabla de movimientos de cuenta y devengamientos en vivo (Alto contraste y Dark Mode).
 */
export function TransactionsTable({ movimientos = [], onExportClick }) {
  const getBadgeIcon = (tipo) => {
    switch (tipo) {
      case 'DEPOSITO':
      case 'ACREDITACION_SUELDO':
        return <ArrowDownLeft className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />;
      case 'RENDIMIENTO_FLEXIBLE_DIARIO':
        return <TrendingUp className="w-3.5 h-3.5 text-valle-orange" />;
      case 'TRANSFERENCIA_OUT':
      case 'COBRO_CUOTA_PRESTAMO':
        return <ArrowUpRight className="w-3.5 h-3.5 text-rose-500" />;
      default:
        return <Sparkles className="w-3.5 h-3.5 text-slate-500" />;
    }
  };

  const formatearPesos = (val) =>
    new Intl.NumberFormat('es-AR', {
      style: 'currency',
      currency: 'ARS',
      minimumFractionDigits: 2,
    }).format(val || 0);

  return (
    <div className="valle-card rounded-3xl p-6 sm:p-8 transition-colors duration-200">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-5 mb-5 border-b border-slate-200 dark:border-valle-darkBorder gap-3">
        <div>
          <h3 className="font-display font-extrabold text-lg sm:text-xl text-slate-900 dark:text-white">
            Últimos Movimientos en Cuenta
          </h3>
          <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-400 mt-0.5">
            Historial de operaciones, acreditación de sueldo y devengamiento diario.
          </p>
        </div>

        <button
          type="button"
          onClick={onExportClick}
          className="px-4 py-2 bg-slate-100 dark:bg-valle-darkElevated hover:bg-slate-200 dark:hover:bg-valle-darkBorder text-slate-800 dark:text-slate-200 text-xs sm:text-sm font-bold rounded-xl transition flex items-center gap-2 border border-slate-300 dark:border-valle-darkBorder shadow-xs"
        >
          <Download className="w-4 h-4 text-valle-orange" />
          <span>Exportar Extracto</span>
        </button>
      </div>

      {movimientos.length === 0 ? (
        <div className="text-center py-10 text-sm text-slate-500 dark:text-slate-400">
          No hay movimientos registrados recientemente en esta cuenta.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="bg-slate-50 dark:bg-valle-darkElevated text-slate-700 dark:text-slate-300 uppercase tracking-wider text-xs font-extrabold border-b border-slate-200 dark:border-valle-darkBorder">
                <th className="py-3.5 px-4">Fecha y Hora</th>
                <th className="py-3.5 px-4">Tipo de Operación</th>
                <th className="py-3.5 px-4">Descripción</th>
                <th className="py-3.5 px-4 text-right">Monto</th>
                <th className="py-3.5 px-4 text-right">Saldo Posterior</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 dark:divide-valle-darkBorder font-medium">
              {movimientos.map((m) => {
                const esIngreso =
                  m.tipo_movimiento === 'DEPOSITO' ||
                  m.tipo_movimiento === 'ACREDITACION_SUELDO' ||
                  m.tipo_movimiento === 'RENDIMIENTO_FLEXIBLE_DIARIO' ||
                  m.tipo_movimiento === 'LIQUIDACION_PLAZO_FIJO';

                return (
                  <tr key={m.id} className="hover:bg-slate-50/80 dark:hover:bg-valle-darkElevated/60 transition">
                    <td className="py-4 px-4 text-slate-600 dark:text-slate-400 whitespace-nowrap font-mono text-xs sm:text-sm">
                      {m.fecha_hora?.slice(0, 16) || 'Reciente'}
                    </td>
                    <td className="py-4 px-4 whitespace-nowrap">
                      <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-valle-darkElevated text-slate-800 dark:text-slate-200 text-xs font-semibold border border-slate-200 dark:border-valle-darkBorder">
                        {getBadgeIcon(m.tipo_movimiento)}
                        <span>{m.tipo_movimiento.replace(/_/g, ' ')}</span>
                      </div>
                    </td>
                    <td className="py-4 px-4 text-slate-900 dark:text-slate-100 max-w-xs truncate">
                      {m.descripcion}
                    </td>
                    <td
                      className={`py-4 px-4 text-right font-extrabold whitespace-nowrap tabular-nums text-base ${
                        esIngreso ? 'text-emerald-700 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'
                      }`}
                    >
                      {esIngreso ? '+' : '-'} {formatearPesos(m.monto)}
                    </td>
                    <td className="py-4 px-4 text-right text-slate-900 dark:text-white font-extrabold tabular-nums whitespace-nowrap text-base">
                      {formatearPesos(m.saldo_posterior)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default TransactionsTable;
