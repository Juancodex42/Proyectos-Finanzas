import React, { useState } from 'react';
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, Legend, CartesianGrid } from 'recharts';
import { useTheme } from '../../context/ThemeContext';

/**
 * ProfitProjectionsChart — Curvas multi-escenario de ganancias y patrimonio (Adaptado a Dark Mode).
 */
export function ProfitProjectionsChart() {
  const { isDark } = useTheme();
  const [horizonte, setHorizonte] = useState('1_ANO'); // '1_ANO' | '3_ANOS' | '5_ANOS'

  // Datos simulados de proyecciones
  const data1Ano = [
    { periodo: 'Mes 1', optimista: 51200000, base: 50800000, pesimista: 50200000 },
    { periodo: 'Mes 3', optimista: 54500000, base: 52400000, pesimista: 50900000 },
    { periodo: 'Mes 6', optimista: 61000000, base: 56100000, pesimista: 51800000 },
    { periodo: 'Mes 9', optimista: 68500000, base: 60200000, pesimista: 52600000 },
    { periodo: 'Mes 12', optimista: 78000000, base: 65000000, pesimista: 53500000 },
  ];

  const data3Anos = [
    { periodo: 'Año 1', optimista: 78000000, base: 65000000, pesimista: 53500000 },
    { periodo: 'Año 2', optimista: 125000000, base: 89000000, pesimista: 59000000 },
    { periodo: 'Año 3', optimista: 195000000, base: 122000000, pesimista: 64000000 },
  ];

  const data5Anos = [
    { periodo: 'Año 1', optimista: 78000000, base: 65000000, pesimista: 53500000 },
    { periodo: 'Año 2', optimista: 125000000, base: 89000000, pesimista: 59000000 },
    { periodo: 'Año 3', optimista: 195000000, base: 122000000, pesimista: 64000000 },
    { periodo: 'Año 4', optimista: 290000000, base: 165000000, pesimista: 70000000 },
    { periodo: 'Año 5', optimista: 410000000, base: 215000000, pesimista: 76000000 },
  ];

  const data = horizonte === '1_ANO' ? data1Ano : horizonte === '3_ANOS' ? data3Anos : data5Anos;

  const formatearMonto = (val) => `$${(val / 1000000).toFixed(0)}M`;

  return (
    <div className="valle-card rounded-3xl p-6 sm:p-7 transition-colors">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 mb-4 border-b border-slate-200 dark:border-valle-darkBorder gap-3">
        <div>
          <h4 className="font-display font-extrabold text-base sm:text-lg text-slate-900 dark:text-white">
            Proyecciones Multi-Escenario de Patrimonio (P&L)
          </h4>
          <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-400 mt-0.5">
            Simulación macroeconómica: Inflación REM vs Shock vs Desaceleración.
          </p>
        </div>

        {/* Selector de Horizonte */}
        <div className="flex gap-1 bg-slate-100 dark:bg-valle-darkElevated p-1 rounded-xl text-xs font-semibold border border-slate-200 dark:border-valle-darkBorder">
          {[
            { id: '1_ANO', label: '1 Año' },
            { id: '3_ANOS', label: '3 Años' },
            { id: '5_ANOS', label: '5 Años' },
          ].map((h) => (
            <button
              key={h.id}
              type="button"
              onClick={() => setHorizonte(h.id)}
              className={`px-3 py-1.5 rounded-lg transition ${
                horizonte === h.id
                  ? 'bg-white dark:bg-valle-blue text-valle-blue dark:text-white shadow-xs font-bold'
                  : 'text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white'
              }`}
            >
              {h.label}
            </button>
          ))}
        </div>
      </div>

      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={isDark ? '#223552' : '#E2E8F0'} />
            <XAxis dataKey="periodo" tick={{ fontSize: 12, fill: isDark ? '#94A3B8' : '#475569' }} />
            <YAxis tickFormatter={formatearMonto} tick={{ fontSize: 11, fill: isDark ? '#94A3B8' : '#475569' }} />
            <Tooltip
              formatter={(val) => [
                new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', maximumFractionDigits: 0 }).format(val),
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
              height={32}
              iconType="circle"
              formatter={(value) => (
                <span className="text-xs sm:text-sm font-semibold text-slate-700 dark:text-slate-300">
                  {value}
                </span>
              )}
            />
            <Line
              type="monotone"
              dataKey="optimista"
              name="Escenario Optimista (Bull +3% PBI)"
              stroke="#10B981"
              strokeWidth={3}
              dot={{ r: 4 }}
            />
            <Line
              type="monotone"
              dataKey="base"
              name="Escenario Base (Consenso REM)"
              stroke={isDark ? '#38BDF8' : '#0F3A5D'}
              strokeWidth={3}
              dot={{ r: 4 }}
            />
            <Line
              type="monotone"
              dataKey="pesimista"
              name="Escenario Pesimista (Stress -3.5% PBI)"
              stroke="#EF4444"
              strokeWidth={2.5}
              strokeDasharray="5 5"
              dot={{ r: 3 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export default ProfitProjectionsChart;
