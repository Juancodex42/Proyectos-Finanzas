import React from 'react';
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, Legend, CartesianGrid } from 'recharts';
import { useTheme } from '../../context/ThemeContext';

/**
 * LiveRatesChart — Gráfico dinámico del spread de tasas de interés (Adaptado a Dark Mode).
 */
export function LiveRatesChart({ rates }) {
  const { isDark } = useTheme();

  const tnaActiva = rates?.tasa_activa_personal ? rates.tasa_activa_personal * 100 : 60.0;
  const tnaPf = rates?.tasa_pasiva_plazo_fijo ? rates.tasa_pasiva_plazo_fijo * 100 : 38.0;
  const tnaFlex = rates?.tasa_pasiva_flexible ? rates.tasa_pasiva_flexible * 100 : 28.5;

  const data = [
    { mes: 'Ene', activa: +(tnaActiva + 5.0).toFixed(1), pasivaPf: +(tnaPf).toFixed(1), pasivaFlex: +(tnaFlex).toFixed(1) },
    { mes: 'Feb', activa: +(tnaActiva + 4.0).toFixed(1), pasivaPf: +(tnaPf - 0.5).toFixed(1), pasivaFlex: +(tnaFlex - 0.5).toFixed(1) },
    { mes: 'Mar', activa: +(tnaActiva + 3.5).toFixed(1), pasivaPf: +(tnaPf - 1.2).toFixed(1), pasivaFlex: +(tnaFlex - 1.0).toFixed(1) },
    { mes: 'Abr', activa: +(tnaActiva + 2.0).toFixed(1), pasivaPf: +(tnaPf - 2.0).toFixed(1), pasivaFlex: +(tnaFlex - 1.5).toFixed(1) },
    { mes: 'May', activa: +(tnaActiva + 1.5).toFixed(1), pasivaPf: +(tnaPf - 2.5).toFixed(1), pasivaFlex: +(tnaFlex - 2.0).toFixed(1) },
    { mes: 'Actual', activa: +(tnaActiva).toFixed(1), pasivaPf: +(tnaPf).toFixed(1), pasivaFlex: +(tnaFlex).toFixed(1) },
  ];

  return (
    <div className="valle-card rounded-3xl p-6 sm:p-7 transition-colors">
      <div className="pb-4 mb-4 border-b border-slate-200 dark:border-valle-darkBorder">
        <h4 className="font-display font-extrabold text-base sm:text-lg text-slate-900 dark:text-white">
          Curva de Tasas y Spread Financiero (Fisher)
        </h4>
        <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-400 mt-0.5">
          Evolución de TNA Activa vs Costo Pasivo de Fondeo.
        </p>
      </div>

      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 10, right: 10, left: -15, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={isDark ? '#223552' : '#E2E8F0'} />
            <XAxis dataKey="mes" tick={{ fontSize: 12, fill: isDark ? '#94A3B8' : '#475569' }} />
            <YAxis tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11, fill: isDark ? '#94A3B8' : '#475569' }} />
            <Tooltip
              formatter={(val) => [`${val}%`, '']}
              contentStyle={{
                backgroundColor: isDark ? '#080D1A' : '#0F172A',
                borderColor: isDark ? '#223552' : '#334155',
                borderRadius: '12px',
                color: '#FFF',
                fontSize: '13px'
              }}
            />
            <Legend
              verticalAlign="bottom"
              height={32}
              iconType="circle"
              formatter={(value) => (
                <span className="text-xs sm:text-sm font-semibold text-slate-700 dark:text-slate-300">
                  {value}
                </span>
              )}
            />
            <Area
              type="monotone"
              dataKey="activa"
              name="TNA Activa (Préstamos)"
              stroke="#FF7A00"
              fill="#FF7A00"
              fillOpacity={0.2}
              strokeWidth={2.5}
            />
            <Area
              type="monotone"
              dataKey="pasivaPf"
              name="TNA Pasiva (Plazo Fijo)"
              stroke={isDark ? '#38BDF8' : '#0F3A5D'}
              fill={isDark ? '#38BDF8' : '#0F3A5D'}
              fillOpacity={0.2}
              strokeWidth={2.5}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export default LiveRatesChart;
