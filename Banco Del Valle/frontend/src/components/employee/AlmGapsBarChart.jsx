import React from 'react';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Legend, CartesianGrid } from 'recharts';
import { useTheme } from '../../context/ThemeContext';

/**
 * AlmGapsBarChart — Descalce de plazos ALM y brechas temporales de liquidez (Adaptado a Dark Mode).
 */
export function AlmGapsBarChart({ data: propData }) {
  const { isDark } = useTheme();

  const fallbackData = [
    { tramo: '30 Días', cobranzas: 0, vencimientos: 1800000 },
    { tramo: '60 Días', cobranzas: 0, vencimientos: 900000 },
    { tramo: '90 Días', cobranzas: 0, vencimientos: 360000 },
  ];

  const data = Array.isArray(propData) && propData.length > 0 ? propData : fallbackData;

  const formatearMonto = (val) => `$${(val / 1000000).toFixed(1)}M`;

  return (
    <div className="valle-card rounded-3xl p-6 sm:p-7 flex flex-col justify-between transition-colors">
      <div className="pb-4 border-b border-slate-200 dark:border-valle-darkBorder">
        <h4 className="font-display font-extrabold text-base sm:text-lg text-slate-900 dark:text-white">
          Brechas ALM: Vencimientos vs Cobranzas
        </h4>
        <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-400 mt-0.5">
          Monitoreo de descalce de plazos a 30, 60 y 90 días.
        </p>
      </div>

      <div className="h-64 w-full my-3">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 10, right: 10, left: -15, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={isDark ? '#223552' : '#E2E8F0'} />
            <XAxis dataKey="tramo" tick={{ fontSize: 12, fill: isDark ? '#94A3B8' : '#475569' }} />
            <YAxis tickFormatter={formatearMonto} tick={{ fontSize: 11, fill: isDark ? '#94A3B8' : '#475569' }} />
            <Tooltip
              formatter={(value) => [
                new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', maximumFractionDigits: 0 }).format(value),
              ]}
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
              height={36}
              iconType="circle"
              formatter={(value) => (
                <span className="text-xs sm:text-sm font-semibold text-slate-700 dark:text-slate-300">
                  {value}
                </span>
              )}
            />
            <Bar dataKey="cobranzas" name="Cobranzas Activas (Entradas)" fill="#10B981" radius={[6, 6, 0, 0]} />
            <Bar dataKey="vencimientos" name="Vencimientos Pasivos (Salidas)" fill="#EF4444" radius={[6, 6, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export default AlmGapsBarChart;
