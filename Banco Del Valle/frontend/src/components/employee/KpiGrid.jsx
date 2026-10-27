import React from 'react';
import { Landmark, ShieldCheck, TrendingUp, DollarSign, Wallet } from 'lucide-react';

/**
 * KpiGrid — Micro-tarjetas densas estilo Bento Grid para métricas patrimoniales de gerencia (Alto contraste y Dark Mode).
 */
export function KpiGrid({ kpis }) {
  const formatearPesos = (val) =>
    new Intl.NumberFormat('es-AR', {
      style: 'currency',
      currency: 'ARS',
      maximumFractionDigits: 0,
    }).format(val || 0);

  const encajeSuperavit = (kpis?.posicion_encaje_bcra ?? 0) >= 0;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-5 mb-8">
      {/* 1. Patrimonio Neto Total */}
      <div className="valle-card rounded-2xl p-5 flex flex-col justify-between transition-colors">
        <div>
          <div className="flex items-center justify-between text-slate-600 dark:text-slate-400 text-xs mb-2">
            <span className="font-bold uppercase tracking-wider text-xs">
              Patrimonio Neto (Equity)
            </span>
            <Landmark className="w-4 h-4 text-valle-blue dark:text-sky-400" />
          </div>
          <div className="font-display font-extrabold text-xl sm:text-2xl text-slate-900 dark:text-white tabular-nums">
            {formatearPesos(kpis?.patrimonio_neto ?? 50000000)}
          </div>
        </div>
        <div className="mt-4 flex items-center gap-1.5 text-xs font-bold text-emerald-700 dark:text-emerald-400">
          <TrendingUp className="w-3.5 h-3.5" />
          <span>+12.4% vs mes anterior</span>
        </div>
      </div>

      {/* 2. Cashflow Seguro Prestable */}
      <div className="valle-card rounded-2xl p-5 flex flex-col justify-between border-l-4 border-l-valle-orange transition-colors">
        <div>
          <div className="flex items-center justify-between text-slate-600 dark:text-slate-400 text-xs mb-2">
            <span className="font-bold uppercase tracking-wider text-xs">
              Cashflow Prestable
            </span>
            <DollarSign className="w-4 h-4 text-valle-orange" />
          </div>
          <div className="font-display font-extrabold text-xl sm:text-2xl text-valle-orange tabular-nums">
            {formatearPesos(kpis?.cashflow_seguro_prestable ?? 25000000)}
          </div>
        </div>
        <span className="mt-4 text-xs font-semibold text-slate-600 dark:text-slate-400 block">
          Capital líquido libre de encajes
        </span>
      </div>

      {/* 3. Base Total de Depósitos */}
      <div className="valle-card rounded-2xl p-5 flex flex-col justify-between transition-colors">
        <div>
          <div className="flex items-center justify-between text-slate-600 dark:text-slate-400 text-xs mb-2">
            <span className="font-bold uppercase tracking-wider text-xs">
              Base de Depósitos
            </span>
            <Wallet className="w-4 h-4 text-sky-500" />
          </div>
          <div className="font-display font-extrabold text-xl sm:text-2xl text-slate-900 dark:text-white tabular-nums">
            {formatearPesos(
              (kpis?.total_depositos_flexibles ?? 0) + (kpis?.total_depositos_plazo_fijo ?? 0)
            )}
          </div>
        </div>
        <div className="mt-4 text-xs text-slate-600 dark:text-slate-400 flex justify-between font-mono font-medium">
          <span>PF: {formatearPesos(kpis?.total_depositos_plazo_fijo ?? 0)}</span>
        </div>
      </div>

      {/* 4. Efectivo Mínimo BCRA */}
      <div className="valle-card rounded-2xl p-5 flex flex-col justify-between transition-colors">
        <div>
          <div className="flex items-center justify-between text-slate-600 dark:text-slate-400 text-xs mb-2">
            <span className="font-bold uppercase tracking-wider text-xs">
              Encajes BCRA
            </span>
            <ShieldCheck className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
          </div>
          <div className="font-display font-extrabold text-xl sm:text-2xl text-slate-900 dark:text-white tabular-nums">
            {formatearPesos(kpis?.encaje_obligatorio_bcra ?? 900000)}
          </div>
        </div>
        <div className="mt-4">
          <span
            className={`inline-flex items-center gap-1 text-xs font-bold px-2.5 py-0.5 rounded-full ${
              encajeSuperavit
                ? 'bg-emerald-100 text-emerald-900 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-700'
                : 'bg-rose-100 text-rose-900 dark:bg-rose-950/60 dark:text-rose-300 border border-rose-300 dark:border-rose-700'
            }`}
          >
            {encajeSuperavit ? '● Superávit Legal' : '▲ Déficit de Encaje'}
          </span>
        </div>
      </div>

      {/* 5. Cartera Activa Colocada */}
      <div className="valle-card rounded-2xl p-5 flex flex-col justify-between transition-colors">
        <div>
          <div className="flex items-center justify-between text-slate-600 dark:text-slate-400 text-xs mb-2">
            <span className="font-bold uppercase tracking-wider text-xs">
              Cartera Prestada
            </span>
            <TrendingUp className="w-4 h-4 text-valle-blue dark:text-sky-400" />
          </div>
          <div className="font-display font-extrabold text-xl sm:text-2xl text-slate-900 dark:text-white tabular-nums">
            {formatearPesos(kpis?.total_prestado_activo ?? 15000000)}
          </div>
        </div>
        <span className="mt-4 text-xs text-emerald-700 dark:text-emerald-400 font-bold block">
          Cobranzas al día: 96.2%
        </span>
      </div>
    </div>
  );
}

export default KpiGrid;
