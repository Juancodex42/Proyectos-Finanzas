import React, { useState, useEffect } from 'react';
import { ClientBalanceCard } from '../components/client/ClientBalanceCard';
import { TransferModal } from '../components/client/TransferModal';
import { DepositModal } from '../components/client/DepositModal';
import { FixedTermModal } from '../components/client/FixedTermModal';
import { TransactionsTable } from '../components/client/TransactionsTable';
import { ExportModal } from '../components/common/ExportModal';
import { apiClient } from '../services/apiClient';
import { simSocket } from '../services/simSocket';
import { useAuth } from '../context/AuthContext';
import { Loader2, AlertCircle } from 'lucide-react';

/**
 * ClientHomeBanking — Panel transaccional de Home Banking (Juan José Gonzalez).
 */
export function ClientHomeBanking({ onGoToDashboard }) {
  const { user } = useAuth();
  const personaId = user?.persona_id || 1;

  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  // Modales
  const [isTransferOpen, setIsTransferOpen] = useState(false);
  const [isDepositOpen, setIsDepositOpen] = useState(false);
  const [isFixedTermOpen, setIsFixedTermOpen] = useState(false);
  const [isExportOpen, setIsExportOpen] = useState(false);

  const cargarDatos = async () => {
    try {
      const res = await apiClient.getHomeBanking(personaId);
      setData(res);
      setError(null);
    } catch (err) {
      console.error('[HomeBanking] Error cargando datos:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    cargarDatos();

    // Suscripción al WebSocket para actualizar saldo en cada tick
    const unsubscribe = simSocket.subscribe((msg) => {
      if (msg.tipo === 'TICK' || msg.tipo === 'TICK_DIARIO' || msg.tipo === 'BALANCE_ACTUALIZADO') {
        cargarDatos();
      }
    });

    return () => unsubscribe();
  }, [personaId]);

  if (loading) {
    return (
      <div className="min-h-[60vh] flex flex-col items-center justify-center gap-3">
        <Loader2 className="w-8 h-8 animate-spin text-valle-orange" />
        <span className="text-xs text-slate-500 font-medium">
          Cargando tu Home Banking...
        </span>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="max-w-xl mx-auto my-12 p-6 bg-red-50 border border-red-200 rounded-2xl text-center space-y-3">
        <AlertCircle className="w-8 h-8 text-red-600 mx-auto" />
        <h3 className="font-bold text-red-800 text-sm">Error cargando cuenta</h3>
        <p className="text-xs text-red-600">{error}</p>
        <button
          onClick={cargarDatos}
          className="px-4 py-2 bg-red-600 text-white rounded-lg text-xs font-bold"
        >
          Reintentar
        </button>
      </div>
    );
  }

  const saldo = data?.cuenta?.saldo_actual ?? 3000000;
  const tna = data?.cuenta?.tna_rendimiento_diario ?? 0.285;
  const rendimientoHoy = saldo * (tna / 365);

  return (
    <div className="max-w-[1600px] mx-auto px-4 sm:px-8 xl:px-12 py-8 animate-fade-in space-y-8">
      {/* Saludo Personalizado */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 mb-2 border-b border-slate-200 dark:border-valle-darkBorder gap-2">
        <div>
          <h2 className="font-display font-extrabold text-2xl sm:text-3xl text-slate-900 dark:text-white">
            Hola, {data?.persona?.nombre_completo || user?.nombre || 'Titular'} 👋
          </h2>
          <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-400 mt-0.5">
            DNI/CUIL: {data?.persona?.dni || user?.identificador || 'Verificado'} | San Fernando del Valle de Catamarca
          </p>
        </div>

        <div className="text-left sm:text-right text-xs sm:text-sm">
          <span className="text-slate-600 dark:text-slate-400 font-medium">Estado de Cuenta:</span>{' '}
          <strong className="text-emerald-700 dark:text-emerald-400 font-extrabold">ACTIVA (Al Día)</strong>
        </div>
      </div>

      {/* Tarjeta Principal de Saldo */}
      <ClientBalanceCard
        saldo={saldo}
        rendimientoHoy={rendimientoHoy}
        esCuentaSueldo={data?.cuenta?.es_cuenta_sueldo ?? true}
        sueldoMensual={data?.persona?.monto_sueldo_acreditado ?? 3000000}
        onTransferClick={() => setIsTransferOpen(true)}
        onDepositClick={() => setIsDepositOpen(true)}
        onFixedTermClick={() => setIsFixedTermOpen(true)}
      />

      {/* Tabla de Movimientos */}
      <TransactionsTable
        movimientos={data?.movimientos || []}
        onExportClick={() => setIsExportOpen(true)}
      />

      {/* Modales */}
      <TransferModal
        isOpen={isTransferOpen}
        onClose={() => setIsTransferOpen(false)}
        saldoDisponible={saldo}
      />

      <DepositModal
        isOpen={isDepositOpen}
        onClose={() => setIsDepositOpen(false)}
        cuentaId={data?.cuenta?.id}
        cbu={data?.cuenta?.cbu}
        alias={data?.cuenta?.alias}
        onDepositSuccess={cargarDatos}
      />

      <FixedTermModal
        isOpen={isFixedTermOpen}
        onClose={() => setIsFixedTermOpen(false)}
        personaId={personaId}
        saldoDisponible={saldo}
        plazosFijos={data?.plazos_fijos || []}
        onUpdateSuccess={cargarDatos}
      />

      <ExportModal
        isOpen={isExportOpen}
        onClose={() => setIsExportOpen(false)}
        defaultModulo="FLEXIBLES"
      />
    </div>
  );
}

export default ClientHomeBanking;
