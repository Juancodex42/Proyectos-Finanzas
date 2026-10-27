import React, { useState, useEffect } from 'react';
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, Legend, CartesianGrid } from 'recharts';
import { useTheme } from '../../context/ThemeContext';
import { apiClient } from '../../services/apiClient';
import { simSocket } from '../../services/simSocket';

/**
 * ProfitProjectionsChart — Curvas multi-escenario de ganancias y patrimonio (Adaptado a Dark Mode y tiempo real).
 */
export function ProfitProjectionsChart({ kpis }) {
  const { isDark } = useTheme();
  const [horizonte, setHorizonte] = useState('1_ANO'); // '1_ANO' | '3_ANOS' | '5_ANOS'
  const [chartData, setChartData] = useState([]);

  const capitalBase = Number(kpis?.patrimonio_neto || kpis?.capital_propio_patrimonio || 50000000);

  useEffect(() => {
    let cancelado = false;

    const cargarProyecciones = async () => {
      try {
        const res = await apiClient.getProyecciones('BASE', horizonte);
        if (cancelado) return;

        if (res && res.escenarios) {
          const { base, optimista, pesimista } = res.escenarios;
          const cBase = base?.curva_mensual || [];
          const cOpt = optimista?.curva_mensual || [];
          const cPes = pesimista?.curva_mensual || [];

          if (horizonte === '1_ANO') {
            const indices = [
              { label: 'Mes 1', idx: 1 },
              { label: 'Mes 3', idx: 3 },
              { label: 'Mes 6', idx: 6 },
              { label: 'Mes 9', idx: 9 },
              { label: 'Mes 12', idx: 12 },
            ];
            setChartData(
              indices.map(({ label, idx }) => ({
                periodo: label,
                optimista: Math.round(cOpt[idx] ?? capitalBase * (1 + 0.56 * (idx / 12))),
                base: Math.round(cBase[idx] ?? capitalBase * (1 + 0.30 * (idx / 12))),
                pesimista: Math.round(cPes[idx] ?? capitalBase * (1 + 0.07 * (idx / 12))),
              }))
            );
          } else if (horizonte === '3_ANOS') {
            const indices = [
              { label: 'Año 1', idx: 12 },
              { label: 'Año 2', idx: 24 },
              { label: 'Año 3', idx: 36 },
            ];
            setChartData(
              indices.map(({ label, idx }) => ({
                periodo: label,
                optimista: Math.round(cOpt[idx] ?? capitalBase * Math.pow(1.56, idx / 12)),
                base: Math.round(cBase[idx] ?? capitalBase * Math.pow(1.30, idx / 12)),
                pesimista: Math.round(cPes[idx] ?? capitalBase * Math.pow(1.07, idx / 12)),
              }))
            );
          } else {
            const indices = [
              { label: 'Año 1', idx: 12 },
              { label: 'Año 2', idx: 24 },
              { label: 'Año 3', idx: 36 },
              { label: 'Año 4', idx: 48 },
              { label: 'Año 5', idx: 60 },
            ];
            setChartData(
              indices.map(({ label, idx }) => ({
                periodo: label,
                optimista: Math.round(cOpt[idx] ?? capitalBase * Math.pow(1.56, idx / 12)),
                base: Math.round(cBase[idx] ?? capitalBase * Math.pow(1.30, idx / 12)),
                pesimista: Math.round(cPes[idx] ?? capitalBase * Math.pow(1.07, idx / 12)),
              }))
            );
          }
          return;
        }
      } catch (e) {
        console.warn('[ProfitProjectionsChart] Error cargando proyecciones del backend:', e);
      }

      // Fallback dinámico si no hay respuesta del backend
      if (horizonte === '1_ANO') {
        setChartData([
          { periodo: 'Mes 1', optimista: Math.round(capitalBase * 1.04), base: Math.round(capitalBase * 1.02), pesimista: Math.round(capitalBase * 1.005) },
          { periodo: 'Mes 3', optimista: Math.round(capitalBase * 1.12), base: Math.round(capitalBase * 1.06), pesimista: Math.round(capitalBase * 1.015) },
          { periodo: 'Mes 6', optimista: Math.round(capitalBase * 1.25), base: Math.round(capitalBase * 1.14), pesimista: Math.round(capitalBase * 1.03) },
          { periodo: 'Mes 9', optimista: Math.round(capitalBase * 1.40), base: Math.round(capitalBase * 1.22), pesimista: Math.round(capitalBase * 1.05) },
          { periodo: 'Mes 12', optimista: Math.round(capitalBase * 1.56), base: Math.round(capitalBase * 1.30), pesimista: Math.round(capitalBase * 1.07) },
        ]);
      } else if (horizonte === '3_ANOS') {
        setChartData([
          { periodo: 'Año 1', optimista: Math.round(capitalBase * 1.56), base: Math.round(capitalBase * 1.30), pesimista: Math.round(capitalBase * 1.07) },
          { periodo: 'Año 2', optimista: Math.round(capitalBase * 2.40), base: Math.round(capitalBase * 1.69), pesimista: Math.round(capitalBase * 1.15) },
          { periodo: 'Año 3', optimista: Math.round(capitalBase * 3.80), base: Math.round(capitalBase * 2.20), pesimista: Math.round(capitalBase * 1.23) },
        ]);
      } else {
        setChartData([
          { periodo: 'Año 1', optimista: Math.round(capitalBase * 1.56), base: Math.round(capitalBase * 1.30), pesimista: Math.round(capitalBase * 1.07) },
          { periodo: 'Año 2', optimista: Math.round(capitalBase * 2.40), base: Math.round(capitalBase * 1.69), pesimista: Math.round(capitalBase * 1.15) },
          { periodo: 'Año 3', optimista: Math.round(capitalBase * 3.80), base: Math.round(capitalBase * 2.20), pesimista: Math.round(capitalBase * 1.23) },
          { periodo: 'Año 4', optimista: Math.round(capitalBase * 5.90), base: Math.round(capitalBase * 2.85), pesimista: Math.round(capitalBase * 1.31) },
          { periodo: 'Año 5', optimista: Math.round(capitalBase * 8.50), base: Math.round(capitalBase * 3.70), pesimista: Math.round(capitalBase * 1.40) },
        ]);
      }
    };

    cargarProyecciones();

    const unsubscribe = simSocket.subscribe((msg) => {
      if (msg.tipo === 'RESET') {
        setHorizonte('1_ANO');
        cargarProyecciones();
      }
    });

    return () => {
      cancelado = true;
      unsubscribe();
    };
  }, [horizonte, capitalBase]);

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
          <LineChart data={chartData} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
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
