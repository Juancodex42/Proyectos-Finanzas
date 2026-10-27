import React from 'react';
import { Calendar, Clock, RefreshCw } from 'lucide-react';

/**
 * DateRangePicker — Selector visual de rango de fechas con atajos financieros.
 */
export function DateRangePicker({ fechaInicio, fechaFin, onChange }) {
  const getTodayISO = () => new Date().toISOString().split('T')[0];

  const handlePreset = (preset) => {
    const today = new Date();
    const todayISO = today.toISOString().split('T')[0];

    switch (preset) {
      case 'HOY':
        onChange({ fechaInicio: todayISO, fechaFin: todayISO });
        break;
      case 'MES_ACTUAL': {
        const firstDay = new Date(today.getFullYear(), today.getMonth(), 1)
          .toISOString()
          .split('T')[0];
        onChange({ fechaInicio: firstDay, fechaFin: todayISO });
        break;
      }
      case 'TRIMESTRE': {
        const past90 = new Date(today.getTime() - 90 * 24 * 60 * 60 * 1000)
          .toISOString()
          .split('T')[0];
        onChange({ fechaInicio: past90, fechaFin: todayISO });
        break;
      }
      case 'HISTORICO':
        onChange({ fechaInicio: '2026-01-01', fechaFin: todayISO });
        break;
      default:
        break;
    }
  };

  return (
    <div className="space-y-3">
      {/* Botones de Atajos Rápidos */}
      <div className="flex flex-wrap items-center gap-1.5 text-xs">
        <span className="text-slate-600 dark:text-slate-400 font-semibold mr-1 flex items-center gap-1">
          <Clock className="w-3.5 h-3.5" /> Atajos:
        </span>
        <button
          type="button"
          onClick={() => handlePreset('HOY')}
          className="px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-valle-darkBorder hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 font-medium transition"
        >
          Hoy
        </button>
        <button
          type="button"
          onClick={() => handlePreset('MES_ACTUAL')}
          className="px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-valle-darkBorder hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 font-medium transition"
        >
          Mes Actual
        </button>
        <button
          type="button"
          onClick={() => handlePreset('TRIMESTRE')}
          className="px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-valle-darkBorder hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 font-medium transition"
        >
          Último Trimestre
        </button>
        <button
          type="button"
          onClick={() => handlePreset('HISTORICO')}
          className="px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-valle-darkBorder hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 font-medium transition"
        >
          Histórico
        </button>
      </div>

      {/* Inputs Desde - Hasta */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
            Desde
          </label>
          <div className="relative">
            <input
              type="date"
              value={fechaInicio || ''}
              onChange={(e) => onChange({ fechaInicio: e.target.value, fechaFin })}
              className="w-full text-xs sm:text-sm px-3 py-2 border border-slate-300 dark:border-valle-darkBorder rounded-xl focus:ring-2 focus:ring-valle-orange focus:border-valle-orange outline-none bg-white dark:bg-valle-darkElevated text-slate-800 dark:text-slate-100"
            />
          </div>
        </div>

        <div>
          <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
            Hasta
          </label>
          <div className="relative">
            <input
              type="date"
              value={fechaFin || ''}
              onChange={(e) => onChange({ fechaInicio, fechaFin: e.target.value })}
              className="w-full text-xs sm:text-sm px-3 py-2 border border-slate-300 dark:border-valle-darkBorder rounded-xl focus:ring-2 focus:ring-valle-orange focus:border-valle-orange outline-none bg-white dark:bg-valle-darkElevated text-slate-800 dark:text-slate-100"
            />
          </div>
        </div>
      </div>
    </div>
  );
}

export default DateRangePicker;
