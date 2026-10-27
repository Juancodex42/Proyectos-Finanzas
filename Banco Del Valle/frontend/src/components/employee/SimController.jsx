import React, { useState, useEffect, useRef } from 'react';
import { Play, Pause, FastForward, SkipForward, Users, Clock, RotateCcw } from 'lucide-react';
import { simSocket } from '../../services/simSocket';
import { apiClient } from '../../services/apiClient';

/**
 * SimController — Centro de Mando del Motor de Tiempo Acelerado (Time-Warp Engine) con diseño de alta visibilidad.
 */
export function SimController({ onTickUpdate }) {
  const [fechaVirtual, setFechaVirtual] = useState('2026-10-26');
  const [corriendo, setCorriendo] = useState(false);
  const [velocidad, setVelocidad] = useState(1);
  const [confirmandoReset, setConfirmandoReset] = useState(false);
  const resetTimerRef = useRef(null);

  useEffect(() => {
    simSocket.connect();

    const unsubscribe = simSocket.subscribe((msg) => {
      if (
        msg.tipo === 'CONEXION_ESTABLECIDA' ||
        msg.tipo === 'ESTADO_SIMULACION' ||
        msg.tipo === 'ESTADO_INICIAL' ||
        msg.tipo === 'ESTADO_RELOJ' ||
        msg.tipo === 'RESET'
      ) {
        const fv = msg.fecha_virtual || msg.fecha_simulada || msg.estado_reloj?.fecha_simulada;
        if (fv) setFechaVirtual(fv);
        if (msg.corriendo !== undefined) setCorriendo(msg.corriendo);
        else if (msg.en_pausa !== undefined) setCorriendo(!msg.en_pausa);
        if (msg.velocidad !== undefined) setVelocidad(msg.velocidad);

        if (msg.tipo === 'RESET') {
          setCorriendo(false);
          setConfirmandoReset(false);
          if (onTickUpdate) onTickUpdate(msg);
        }
      } else if (msg.tipo === 'TICK_DIARIO' || msg.tipo === 'TICK') {
        const fv = msg.fecha_virtual || msg.fecha_simulada;
        if (fv) setFechaVirtual(fv);
        if (onTickUpdate) onTickUpdate(msg);
      }
    });

    return () => {
      unsubscribe();
      if (resetTimerRef.current) clearTimeout(resetTimerRef.current);
    };
  }, []);

  const handleToggle = () => {
    if (corriendo) {
      simSocket.pausar();
      setCorriendo(false);
    } else {
      simSocket.iniciar();
      setCorriendo(true);
    }
  };

  const handleVelocidad = (vel) => {
    setVelocidad(vel);
    simSocket.setVelocidad(vel);
    if (!corriendo) {
      simSocket.iniciar();
      setCorriendo(true);
    }
  };

  const handleAvanzarDia = () => {
    simSocket.avanzarDia();
  };

  const handleInyectarTrafico = () => {
    simSocket.inyectarTrafico(5);
  };

  const handleReset = async () => {
    if (!confirmandoReset) {
      setConfirmandoReset(true);
      if (resetTimerRef.current) clearTimeout(resetTimerRef.current);
      resetTimerRef.current = setTimeout(() => {
        setConfirmandoReset(false);
      }, 4000);
      return;
    }

    if (resetTimerRef.current) clearTimeout(resetTimerRef.current);
    setConfirmandoReset(false);
    setCorriendo(false);
    setVelocidad(1);
    setFechaVirtual('2026-10-26');

    try {
      simSocket.reiniciar();
      await apiClient.resetSimulacion();
    } catch (err) {
      console.warn('[SimController] Error en reset HTTP:', err);
    } finally {
      if (onTickUpdate) {
        onTickUpdate({ tipo: 'RESET', fecha_virtual: '2026-10-26' });
      }
    }
  };

  return (
    <div className="bg-slate-900 dark:bg-valle-darkSurface text-white rounded-3xl p-5 sm:p-6 shadow-xl border border-slate-800 dark:border-valle-darkBorder flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8 transition-colors duration-200">
      {/* Indicador de Fecha Virtual y Estado */}
      <div className="flex items-center gap-4">
        <div className="w-12 h-12 rounded-2xl bg-valle-orange/20 border border-valle-orange/40 flex items-center justify-center text-valle-orange flex-shrink-0">
          <Clock className="w-6 h-6" />
        </div>

        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
              Reloj Virtual del Banco
            </span>
            <span
              className={`inline-flex items-center gap-1.5 text-xs font-extrabold px-2.5 py-0.5 rounded-full ${
                corriendo
                  ? 'bg-emerald-500/25 text-emerald-300 border border-emerald-400/40'
                  : 'bg-amber-500/25 text-amber-300 border border-amber-400/40'
              }`}
            >
              <span
                className={`w-2 h-2 rounded-full ${
                  corriendo ? 'bg-emerald-400 animate-ping' : 'bg-amber-400'
                }`}
              />
              <span>{corriendo ? `ACTIVO (${velocidad}d/s)` : 'PAUSADO'}</span>
            </span>
          </div>

          <div className="font-mono font-extrabold text-2xl sm:text-3xl text-white tracking-wider tabular-nums mt-0.5">
            {fechaVirtual}
          </div>
        </div>
      </div>

      {/* Botones de Control de Simulación */}
      <div className="flex flex-wrap items-center gap-2.5">
        <button
          type="button"
          onClick={handleToggle}
          className={`px-5 py-3 rounded-xl font-bold text-xs sm:text-sm flex items-center gap-2 shadow-md transition ${
            corriendo
              ? 'bg-amber-600 hover:bg-amber-700 text-white'
              : 'bg-valle-orange hover:bg-valle-orangedark text-white'
          }`}
        >
          {corriendo ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
          <span>{corriendo ? 'Pausar Reloj' : 'Acelerar Simulación (1s = 1d)'}</span>
        </button>

        <div className="flex items-center bg-valle-blue/80 dark:bg-valle-darkElevated p-1 rounded-xl border border-valle-bluelight/60 dark:border-valle-darkBorder gap-1 text-xs">
          <button
            type="button"
            onClick={() => handleVelocidad(1)}
            className={`px-3 py-2 rounded-lg font-bold transition ${
              velocidad === 1 && corriendo ? 'bg-white/20 text-white' : 'text-slate-300 hover:text-white'
            }`}
          >
            1x (1d/s)
          </button>
          <button
            type="button"
            onClick={() => handleVelocidad(5)}
            className={`px-3 py-2 rounded-lg font-bold transition flex items-center gap-1 ${
              velocidad === 5 && corriendo ? 'bg-white/20 text-white' : 'text-slate-300 hover:text-white'
            }`}
          >
            <FastForward className="w-3.5 h-3.5 text-valle-orange" />
            <span>5x</span>
          </button>
        </div>

        <button
          type="button"
          onClick={handleAvanzarDia}
          title="Avanzar 1 Día Bancario"
          className="p-3 bg-valle-blue/80 hover:bg-valle-bluelight text-slate-200 hover:text-white rounded-xl border border-valle-bluelight/60 transition shadow-xs"
        >
          <SkipForward className="w-4 h-4" />
        </button>

        <button
          type="button"
          onClick={handleInyectarTrafico}
          className="px-4 py-2.5 bg-emerald-600/30 hover:bg-emerald-600/40 text-emerald-300 border border-emerald-500/40 rounded-xl text-xs sm:text-sm font-semibold flex items-center gap-2 transition"
        >
          <Users className="w-4 h-4" />
          <span className="hidden sm:inline">+5 Solicitudes de Crédito</span>
        </button>

        <button
          type="button"
          onClick={handleReset}
          title="Restablecer simulación al Día 1 y reiniciar datos del banco"
          className={`px-3.5 py-2.5 rounded-xl text-xs sm:text-sm font-semibold flex items-center gap-1.5 transition border ${
            confirmandoReset
              ? 'bg-rose-600 hover:bg-rose-700 text-white border-rose-500 animate-pulse shadow-lg'
              : 'bg-slate-800/80 hover:bg-rose-950/60 text-slate-300 hover:text-rose-300 border-slate-700 hover:border-rose-500/50'
          }`}
        >
          <RotateCcw className={`w-4 h-4 ${confirmandoReset ? 'animate-spin' : ''}`} />
          <span>{confirmandoReset ? '¿Confirmar Reset?' : 'Reset'}</span>
        </button>
      </div>
    </div>
  );
}

export default SimController;
