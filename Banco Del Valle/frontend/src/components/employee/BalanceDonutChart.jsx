import React from 'react';
import { ResponsiveContainer, PieChart, Pie, Cell, Tooltip, Legend } from 'recharts';
import { useTheme } from '../../context/ThemeContext';

/**
 * BalanceDonutChart — Gráfico Donut de Composición de Activos y Encajes BCRA (Adaptado a Dark Mode).
 */
export function BalanceDonutChart({ kpis }) {
  const { isDark } = useTheme();
  const cartera = Number(kpis?.total_prestado_activo ?? 0);
  const encaje = Number(kpis?.encaje_obligatorio_bcra ?? 5400000);
  const liquidez = Number(kpis?.cashflow_seguro_prestable ?? 50000000);

  const data = [
    { name: 'Cartera Préstamos', value: cartera, color: '#FF7A00' },
    { name: 'Encaje BCRA (Reserva)', value: encaje, color: '#10B981' },
    { name: 'Liquidez Disponible', value: liquidez, color: isDark ? '#38BDF8' : '#0F3A5D' },
  ];

  const total = Math.max(1, cartera + encaje + liquidez);

  const formatearPesos = (val) =>
    new Intl.NumberFormat('es-AR', {
      style: 'currency',
      currency: 'ARS',
      maximumFractionDigits: 0,
    }).format(val || 0);

  const CustomTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      const item = payload[0];
      const pct = ((item.value / total) * 100).toFixed(1);
      return (
        <div className="bg-slate-900 text-white text-xs p-3 rounded-xl shadow-xl border border-slate-700">
          <p className="font-bold">{item.name}</p>
          <p className="font-mono text-valle-orange font-extrabold">{formatearPesos(item.value)}</p>
          <p className="text-[11px] text-slate-400 mt-0.5">{pct}% del activo bancario</p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="valle-card rounded-3xl p-6 sm:p-7 flex flex-col justify-between transition-colors">
      <div className="pb-4 border-b border-slate-200 dark:border-valle-darkBorder">
        <h4 className="font-display font-extrabold text-base sm:text-lg text-slate-900 dark:text-white">
          Distribución de Activos y Encajes
        </h4>
        <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-400 mt-0.5">
          Estructura de reservas líquidas vs colocaciones vivas.
        </p>
      </div>

      <div className="h-64 w-full my-3">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              innerRadius={60}
              outerRadius={85}
              paddingAngle={4}
              dataKey="value"
            >
              {data.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.color} />
              ))}
            </Pie>
            <Tooltip content={<CustomTooltip />} />
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
          </PieChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export default BalanceDonutChart;
