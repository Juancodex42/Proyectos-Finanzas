import React from 'react';
import { Wallet, TrendingUp, ArrowUpRight, ArrowDownLeft, Clock, ShieldCheck } from 'lucide-react';

/**
 * ClientBalanceCard — Tarjeta de saldo transaccional y rendimiento diario de cuenta (Alto contraste y Dark Mode).
 */
export function ClientBalanceCard({
  saldo = 3000000,
  rendimientoHoy = 2342.47,
  esCuentaSueldo = true,
  sueldoMensual = 3000000,
  onTransferClick,
  onDepositClick,
  onFixedTermClick,
}) {
  const formatearPesos = (val) =>
    new Intl.NumberFormat('es-AR', {
      style: 'currency',
      currency: 'ARS',
      minimumFractionDigits: 2,
    }).format(val || 0);

  return (
    <div className="p-7 sm:p-9 bg-gradient-to-br from-slate-900 via-valle-bluedark to-valle-blue dark:from-[#0B1526] dark:via-[#10203B] dark:to-[#172D52] text-white rounded-3xl shadow-xl border border-slate-800 dark:border-valle-darkBorder relative overflow-hidden mb-8">
      {/* Fondo vectorial sutil */}
      <div className="absolute right-0 top-0 opacity-10 pointer-events-none transform translate-x-12 -translate-y-8">
        <Wallet className="w-80 h-80 text-white" />
      </div>

      <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6 pb-6 border-b border-white/15">
        <div>
          <div className="flex flex-wrap items-center gap-2 mb-2">
            <span className="text-xs sm:text-sm font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
              <Wallet className="w-4 h-4 text-valle-orange" />
              <span>Caja de Ahorro Remunerada en Pesos</span>
            </span>

            {esCuentaSueldo && (
              <span className="px-3 py-0.5 rounded-full bg-emerald-500/25 text-emerald-300 border border-emerald-400/40 text-xs font-bold">
                Cuenta Sueldo Activa
              </span>
            )}
          </div>

          <div className="font-display font-extrabold text-3xl sm:text-5xl lg:text-6xl tracking-tight text-white tabular-nums">
            {formatearPesos(saldo)}
          </div>

          <div className="flex flex-wrap items-center gap-3 mt-3 text-xs sm:text-sm text-slate-300">
            <span className="inline-flex items-center gap-1.5 text-emerald-300 font-bold bg-emerald-500/20 px-3 py-1 rounded-xl border border-emerald-500/30">
              <TrendingUp className="w-4 h-4" />
              <span>+28.5% TNA Flexible</span>
            </span>
            <span>
              Ganancia devengada hoy: <strong className="text-white font-extrabold">+{formatearPesos(rendimientoHoy)}</strong>
            </span>
            {esCuentaSueldo && (
              <span className="text-slate-400">
                (Sueldo de {formatearPesos(sueldoMensual)} se acredita el día 1 de cada mes)
              </span>
            )}
          </div>
        </div>

        {/* Insignia de Protección Bancaria */}
        <div className="flex-shrink-0">
          <div className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-white/10 border border-white/15 text-slate-200 text-xs sm:text-sm font-semibold backdrop-blur-sm">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            <span>Fondos Protegidos por BCRA / SEDESA</span>
          </div>
        </div>
      </div>

      {/* Botones de Operatoria Transaccional Rápida */}
      <div className="relative z-10 grid grid-cols-2 sm:grid-cols-3 gap-4 pt-6">
        <button
          type="button"
          onClick={onTransferClick}
          className="p-3.5 bg-white/10 hover:bg-white/20 border border-white/15 rounded-xl font-bold text-xs sm:text-sm flex items-center justify-center gap-2 transition"
        >
          <ArrowUpRight className="w-4 h-4 text-valle-orange" />
          <span>Transferir Dinero</span>
        </button>

        <button
          type="button"
          onClick={onDepositClick}
          className="p-3.5 bg-white/10 hover:bg-white/20 border border-white/15 rounded-xl font-bold text-xs sm:text-sm flex items-center justify-center gap-2 transition"
        >
          <ArrowDownLeft className="w-4 h-4 text-emerald-400" />
          <span>Ingresar / CBU</span>
        </button>

        <button
          type="button"
          onClick={onFixedTermClick}
          className="col-span-2 sm:col-span-1 p-3.5 bg-white/10 hover:bg-white/20 border border-white/15 rounded-xl font-bold text-xs sm:text-sm flex items-center justify-center gap-2 transition"
        >
          <Clock className="w-4 h-4 text-sky-400" />
          <span>Plazo Fijo (38% TNA)</span>
        </button>
      </div>
    </div>
  );
}

export default ClientBalanceCard;
