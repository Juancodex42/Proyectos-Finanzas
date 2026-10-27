import React, { useState } from 'react';
import { Flame, Sparkles, BellRing, Check } from 'lucide-react';

/**
 * HighRiskInvestmentsTeaser — Teaser interactivo con tooltip hover para futuras inversiones de alto riesgo (Dark Mode Ready).
 */
export function HighRiskInvestmentsTeaser() {
  const [avisado, setAvisado] = useState(false);

  return (
    <div className="relative group bg-gradient-to-r from-amber-500/10 via-orange-500/10 to-red-500/10 dark:from-amber-950/20 dark:via-orange-950/20 dark:to-red-950/20 border border-orange-200 dark:border-orange-500/30 rounded-3xl p-6 mb-12 flex flex-col sm:flex-row items-center justify-between gap-4 transition hover:border-valle-orange shadow-xs">
      <div className="flex items-center gap-4">
        <div className="w-12 h-12 rounded-2xl bg-valle-orange text-white flex items-center justify-center flex-shrink-0 shadow-sm">
          <Flame className="w-6 h-6 animate-pulse" />
        </div>
        <div>
          <div className="flex flex-wrap items-center gap-2.5">
            <h4 className="font-display font-extrabold text-base sm:text-lg text-slate-900 dark:text-white">
              Nuevas Inversiones en Mercado de Capitales
            </h4>
            <span className="px-2.5 py-0.5 rounded-full bg-valle-orange text-white text-xs font-bold uppercase tracking-wider">
              Próximamente
            </span>
          </div>
          <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-400 mt-1">
            Pasa el mouse para descubrir los nuevos instrumentos financieros supervisados por la CNV que estamos preparando.
          </p>
        </div>
      </div>

      {/* Botón de Interés */}
      <div className="relative flex-shrink-0">
        <button
          type="button"
          onClick={() => setAvisado(true)}
          className={`px-5 py-2.5 rounded-xl text-xs sm:text-sm font-bold transition flex items-center gap-2 shadow-xs ${
            avisado
              ? 'bg-emerald-600 text-white'
              : 'bg-white dark:bg-valle-darkElevated border border-slate-300 dark:border-valle-darkBorder hover:border-valle-orange text-slate-800 dark:text-slate-200'
          }`}
        >
          {avisado ? (
            <>
              <Check className="w-4 h-4" />
              <span>¡Te avisaremos primero!</span>
            </>
          ) : (
            <>
              <BellRing className="w-4 h-4 text-valle-orange" />
              <span>Quiero ser de los primeros</span>
            </>
          )}
        </button>

        {/* Hover Tooltip Dinámico */}
        <div className="absolute right-0 bottom-full mb-2 w-80 p-4 bg-slate-950 dark:bg-black text-white text-xs rounded-2xl shadow-2xl border border-slate-800 opacity-0 pointer-events-none group-hover:opacity-100 group-hover:pointer-events-auto transition-opacity duration-200 z-30">
          <div className="flex items-center gap-1.5 text-valle-orange font-bold mb-1.5 text-xs sm:text-sm">
            <Sparkles className="w-4 h-4" />
            <span>Próxima incorporación al Mercado de Capitales:</span>
          </div>
          <p className="text-slate-300 leading-relaxed text-xs">
            Pronto podrás operar directamente: <strong>Acciones locales (BYMA), Cedears (Apple, Tesla), Bonos soberanos y corporativos, Índices y Derivados financieros</strong>.
          </p>
          <div className="absolute top-full right-8 w-0 h-0 border-x-4 border-x-transparent border-t-4 border-t-slate-950" />
        </div>
      </div>
    </div>
  );
}

export default HighRiskInvestmentsTeaser;
