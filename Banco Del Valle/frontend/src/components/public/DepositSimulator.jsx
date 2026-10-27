import React, { useState } from 'react';
import { TrendingUp, Clock, Zap, ArrowRight, ShieldCheck } from 'lucide-react';

/**
 * DepositSimulator — Comparador de inversiones: Plazo Fijo vs Cuenta Flexible Money Market (Alto contraste y Dark Mode).
 */
export function DepositSimulator({ onOpenRegister }) {
  const [capital, setCapital] = useState(1000000);
  const [dias, setDias] = useState(30);

  const tnaPf = 0.38; // 38.0% TNA
  const tnaFlex = 0.285; // 28.5% TNA

  const gananciaPf = capital * (tnaPf / 365) * dias;
  const gananciaFlex = capital * (tnaFlex / 365) * dias;
  const gananciaDiariaFlex = capital * (tnaFlex / 365);

  const formatearPesos = (val) =>
    new Intl.NumberFormat('es-AR', {
      style: 'currency',
      currency: 'ARS',
      maximumFractionDigits: 0,
    }).format(val || 0);

  return (
    <div id="simulador-inversiones" className="valle-card p-6 sm:p-10 mb-12 rounded-3xl transition-colors duration-200">
      <div className="pb-6 mb-8 border-b border-slate-200 dark:border-valle-darkBorder">
        <div className="inline-flex items-center gap-2 text-xs sm:text-sm font-bold uppercase tracking-wider text-emerald-700 dark:text-emerald-400 mb-1.5">
          <TrendingUp className="w-4 h-4" />
          <span>Ahorro & Rentabilidad Inteligente</span>
        </div>
        <h2 className="font-display font-extrabold text-2xl sm:text-3xl text-slate-900 dark:text-white">
          Simulador de Inversiones y Liquidez
        </h2>
        <p className="text-sm sm:text-base text-slate-600 dark:text-slate-300 mt-1">
          Elegí entre maximizar tu tasa a plazo o mantener disponibilidad inmediata con rendimiento diario.
        </p>
      </div>

      {/* Controles */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-8 mb-10">
        <div>
          <div className="flex justify-between items-center text-sm font-bold text-slate-800 dark:text-slate-200 mb-2">
            <span>Capital a Invertir</span>
            <span className="text-valle-blue dark:text-sky-400 text-lg sm:text-xl font-extrabold tabular-nums">{formatearPesos(capital)}</span>
          </div>
          <input
            type="range"
            min="100000"
            max="15000000"
            step="50000"
            value={capital}
            onChange={(e) => setCapital(Number(e.target.value))}
            className="slider-valle"
          />
        </div>

        <div>
          <div className="flex justify-between items-center text-sm font-bold text-slate-800 dark:text-slate-200 mb-2">
            <span>Plazo de Permanencia</span>
            <span className="text-valle-orange text-lg sm:text-xl font-extrabold tabular-nums">{dias} días</span>
          </div>
          <div className="grid grid-cols-4 gap-2">
            {[30, 60, 90, 180].map((d) => (
              <button
                key={d}
                type="button"
                onClick={() => setDias(d)}
                className={`py-2 text-xs sm:text-sm font-bold rounded-xl border transition ${
                  dias === d
                    ? 'bg-valle-orange text-white border-valle-orange shadow-md'
                    : 'border-slate-300 dark:border-valle-darkBorder text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-valle-darkElevated'
                }`}
              >
                {d}d
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Comparativa Bento Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        {/* Opción 1: Cuenta Flexible Money Market */}
        <div className="p-7 sm:p-8 rounded-3xl border-2 border-emerald-500/50 bg-emerald-50/40 dark:bg-emerald-950/20 flex flex-col justify-between relative overflow-hidden transition-colors">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="inline-flex items-center gap-1.5 text-xs font-bold px-3 py-1 rounded-full bg-emerald-100 text-emerald-900 dark:bg-emerald-900/60 dark:text-emerald-200 border border-emerald-300 dark:border-emerald-700">
                <Zap className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                <span>Liquidez Inmediata 24/7</span>
              </span>
              <span className="font-display font-extrabold text-emerald-700 dark:text-emerald-400 text-lg tabular-nums">
                28.5% TNA
              </span>
            </div>

            <h3 className="font-display font-extrabold text-xl sm:text-2xl text-slate-900 dark:text-white">
              Caja de Ahorro Remunerada
            </h3>
            <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed font-normal">
              Tu saldo nunca duerme. Genera intereses automáticos acreditados al cierre de cada día hábil.
            </p>

            <div className="pt-5 border-t border-emerald-200 dark:border-emerald-800/40 space-y-3 text-sm">
              <div className="flex justify-between items-center">
                <span className="text-slate-600 dark:text-slate-400">Rendimiento devengado por día:</span>
                <span className="font-extrabold text-emerald-700 dark:text-emerald-400 tabular-nums text-base">{formatearPesos(gananciaDiariaFlex)} / día</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-slate-600 dark:text-slate-400">Ganancia acumulada en {dias} días:</span>
                <span className="font-extrabold text-slate-900 dark:text-white tabular-nums text-lg">{formatearPesos(gananciaFlex)}</span>
              </div>
            </div>
          </div>

          <button
            type="button"
            onClick={onOpenRegister}
            className="w-full mt-8 py-3.5 bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-sm sm:text-base rounded-xl shadow-md transition flex items-center justify-center gap-2 group"
          >
            <span>Abrir Cuenta Remunerada</span>
            <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
          </button>
        </div>

        {/* Opción 2: Plazo Fijo Tradicional */}
        <div className="valle-card p-7 sm:p-8 rounded-3xl flex flex-col justify-between transition-colors">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="inline-flex items-center gap-1.5 text-xs font-bold px-3 py-1 rounded-full bg-slate-100 dark:bg-valle-darkElevated text-slate-800 dark:text-slate-200 border border-slate-300 dark:border-valle-darkBorder">
                <Clock className="w-4 h-4 text-slate-600 dark:text-slate-400" />
                <span>Renta a Término Fijo</span>
              </span>
              <span className="font-display font-extrabold text-valle-blue dark:text-sky-400 text-lg tabular-nums">
                38.0% TNA
              </span>
            </div>

            <h3 className="font-display font-extrabold text-xl sm:text-2xl text-slate-900 dark:text-white">
              Plazo Fijo Tradicional
            </h3>
            <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed font-normal">
              Mayor rendimiento pactado. Incluye opción de cancelación anticipada sin intereses según norma BCRA.
            </p>

            <div className="pt-5 border-t border-slate-200 dark:border-valle-darkBorder space-y-3 text-sm">
              <div className="flex justify-between items-center">
                <span className="text-slate-600 dark:text-slate-400">Garantía y Supervisión:</span>
                <span className="font-semibold text-slate-800 dark:text-slate-200">SEDESA hasta $25M (100% regulado BCRA)</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-slate-600 dark:text-slate-400">Ganancia fija al vencimiento:</span>
                <span className="font-extrabold text-valle-orange tabular-nums text-lg">{formatearPesos(gananciaPf)}</span>
              </div>
            </div>
          </div>

          <button
            type="button"
            onClick={onOpenRegister}
            className="w-full mt-8 py-3.5 bg-valle-blue hover:bg-valle-bluelight text-white font-bold text-sm sm:text-base rounded-xl shadow-md transition flex items-center justify-center gap-2 group"
          >
            <span>Constituir Plazo Fijo</span>
            <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
          </button>
        </div>
      </div>
    </div>
  );
}

export default DepositSimulator;
