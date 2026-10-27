import React, { useState, useEffect } from 'react';
import { SimController } from '../components/employee/SimController';
import { KpiGrid } from '../components/employee/KpiGrid';
import { BalanceDonutChart } from '../components/employee/BalanceDonutChart';
import { AlmGapsBarChart } from '../components/employee/AlmGapsBarChart';
import { ProfitProjectionsChart } from '../components/employee/ProfitProjectionsChart';
import { LiveRatesChart } from '../components/employee/LiveRatesChart';
import { OperationsTable } from '../components/employee/OperationsTable';
import { ExportModal } from '../components/common/ExportModal';
import { apiClient } from '../services/apiClient';
import { simSocket } from '../services/simSocket';
import { ShieldCheck, Download, RotateCcw, Loader2 } from 'lucide-react';

/**
 * EmployeeDashboard — Terminal Ejecutiva y Cuantitativa de Control Bancario.
 */
export function EmployeeDashboard() {
  const [kpis, setKpis] = useState(null);
  const [operaciones, setOperaciones] = useState([]);
  const [almGaps, setAlmGaps] = useState([]);
  const [liveRates, setLiveRates] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isResetting, setIsResetting] = useState(false);
  const [resetKey, setResetKey] = useState(0);
  const [isExportOpen, setIsExportOpen] = useState(false);
  const [exportModulo, setExportModulo] = useState('BALANCE');

  const recargarMetricas = async () => {
    try {
      const [resKpis, resOps, resGaps, resRates] = await Promise.all([
        apiClient.getKpis().catch(() => null),
        apiClient.getOperaciones().catch(() => []),
        apiClient.getAlmGaps().catch(() => []),
        apiClient.getLiveRates().catch(() => null),
      ]);
      if (resKpis) setKpis(resKpis);
      if (Array.isArray(resOps)) setOperaciones(resOps);
      if (Array.isArray(resGaps)) setAlmGaps(resGaps);
      if (resRates) setLiveRates(resRates);
    } catch (e) {
      console.error('[EmployeeDashboard] Error al recargar métricas:', e);
    } finally {
      setLoading(false);
    }
  };

  const handleGlobalReset = async () => {
    setIsResetting(true);
    try {
      simSocket.reiniciar();
      await apiClient.resetSimulacion();
      setResetKey((prev) => prev + 1);
      await recargarMetricas();
    } catch (err) {
      console.error('[EmployeeDashboard] Error al restablecer simulación:', err);
    } finally {
      setIsResetting(false);
    }
  };

  useEffect(() => {
    recargarMetricas();

    // Actualización reactiva por cada tick o reset del reloj de simulación
    const unsubscribe = simSocket.subscribe((msg) => {
      if (msg.tipo === 'RESET') {
        setResetKey((prev) => prev + 1);
        recargarMetricas();
      } else if (
        msg.tipo === 'TICK' ||
        msg.tipo === 'TICK_DIARIO' ||
        msg.tipo === 'BALANCE_ACTUALIZADO'
      ) {
        recargarMetricas();
      }
    });

    return () => unsubscribe();
  }, []);

  const handleOpenExport = (modulo = 'BALANCE') => {
    setExportModulo(modulo);
    setIsExportOpen(true);
  };

  return (
    <div className="max-w-[1600px] mx-auto px-4 sm:px-8 xl:px-12 py-8 animate-fade-in">
      {/* Encabezado del Tablero */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 mb-6 border-b border-slate-200 dark:border-valle-darkBorder gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-valle-orange animate-pulse" />
            <span className="text-xs sm:text-sm font-bold uppercase tracking-wider text-valle-blue dark:text-sky-400">
              Terminal Ejecutiva de Tesorería & ALM
            </span>
          </div>
          <h2 className="font-display font-extrabold text-2xl sm:text-3xl text-slate-900 dark:text-white mt-1">
            Tablero de Control Bancario
          </h2>
          <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-400">
            Monitoreo en tiempo real de solvencia, encajes BCRA, carteras y paso del tiempo acelerado.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <button
            type="button"
            onClick={handleGlobalReset}
            disabled={isResetting}
            title="Restablecer simulación, base de datos y todas las gráficas a valores iniciales"
            className="px-3.5 py-2 bg-slate-100 hover:bg-rose-50 dark:bg-valle-darkElevated dark:hover:bg-rose-950/40 text-slate-700 hover:text-rose-600 dark:text-slate-200 dark:hover:text-rose-400 font-bold text-xs rounded-xl border border-slate-300 dark:border-valle-darkBorder hover:border-rose-400 transition flex items-center gap-1.5 shadow-xs"
          >
            <RotateCcw className={`w-4 h-4 text-rose-500 ${isResetting ? 'animate-spin' : ''}`} />
            <span>{isResetting ? 'Restableciendo...' : 'Restablecer Valores Iniciales'}</span>
          </button>

          <button
            type="button"
            onClick={() => handleOpenExport('BALANCE')}
            className="px-3.5 py-2 bg-valle-blue hover:bg-valle-bluelight text-white font-bold text-xs rounded-xl shadow-xs transition flex items-center gap-1.5"
          >
            <Download className="w-4 h-4 text-valle-orange" />
            <span>Exportar Balance Oficial</span>
          </button>
        </div>
      </div>

      {/* Centro de Mando del Time-Warp Engine */}
      <SimController onTickUpdate={(msg) => {
        if (msg?.tipo === 'RESET') {
          setResetKey((prev) => prev + 1);
        }
        recargarMetricas();
      }} />

      {/* Tarjetas Bento Grid de Métricas Principales */}
      <KpiGrid key={`kpis-${resetKey}`} kpis={kpis} />

      {/* Segmentación Analítica: Fila 1 (Donut de Balance + Barras ALM) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <BalanceDonutChart key={`donut-${resetKey}`} kpis={kpis} />
        <AlmGapsBarChart key={`gaps-${resetKey}`} data={almGaps} />
      </div>

      {/* Segmentación Analítica: Fila 2 (Proyecciones Multi-Escenario + Spread Fisher) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <ProfitProjectionsChart key={`projections-${resetKey}`} kpis={kpis} />
        <LiveRatesChart key={`rates-${resetKey}`} rates={liveRates} />
      </div>

      {/* Tabla de Operaciones de Cartera Crediticia */}
      <OperationsTable
        key={`ops-${resetKey}`}
        operaciones={operaciones}
        onExportClick={() => handleOpenExport('PRESTAMOS')}
      />

      {/* Modal Universal de Exportación */}
      <ExportModal
        isOpen={isExportOpen}
        onClose={() => setIsExportOpen(false)}
        defaultModulo={exportModulo}
      />
    </div>
  );
}

export default EmployeeDashboard;
