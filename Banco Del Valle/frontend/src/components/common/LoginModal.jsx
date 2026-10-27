import React, { useState } from 'react';
import { X, Lock, User, ShieldCheck, ArrowRight, AlertCircle, Loader2, Sparkles, Building2 } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { BrandLogo } from './BrandLogo';

/**
 * LoginModal — Modal de acceso institucional con Cuentas Guardadas de acceso rápido.
 */
export function LoginModal({ isOpen, onClose, onRegisterClick, onSuccess }) {
  const { login, loginDemoJuanJose, loginDemoGerente, loading } = useAuth();
  const [identificador, setIdentificador] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    try {
      const userObj = await login(identificador, password);
      onClose();
      if (onSuccess) {
        if (userObj?.rol === 'GERENTE' || userObj?.rol === 'EMPLEADO') {
          onSuccess('dashboard');
        } else {
          onSuccess('homebanking');
        }
      }
    } catch (err) {
      setError(err.message || 'Credenciales inválidas');
    }
  };

  const handleQuickLogin = async (tipo) => {
    setError(null);
    try {
      const userObj = tipo === 'GERENTE' ? await loginDemoGerente() : await loginDemoJuanJose();
      onClose();
      if (onSuccess) {
        if (userObj?.rol === 'GERENTE' || userObj?.rol === 'EMPLEADO') {
          onSuccess('dashboard');
        } else {
          onSuccess('homebanking');
        }
      }
    } catch (err) {
      setError(err.message || 'No se pudo iniciar la sesión demostrativa');
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 dark:bg-black/75 backdrop-blur-sm animate-fade-in">
      <div className="relative w-full max-w-md bg-white dark:bg-valle-darkSurface rounded-2xl shadow-2xl border border-slate-200 dark:border-valle-darkBorder overflow-hidden text-slate-800 dark:text-slate-100 transition-colors duration-200">
        
        {/* Header */}
        <div className="bg-valle-blue dark:bg-valle-darkElevated px-6 py-5 flex items-center justify-between text-white border-b border-valle-bluelight/40 dark:border-valle-darkBorder">
          <BrandLogo size="sm" variant="light" />
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-300 hover:text-white hover:bg-valle-bluelight transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Cuerpo */}
        <div className="p-6 space-y-5">
          <div>
            <h3 className="font-display font-bold text-lg sm:text-xl text-slate-900 dark:text-white">
              Iniciar Sesión
            </h3>
            <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-400 mt-0.5">
              Accede a tu Home Banking o ingresa al Tablero de Control Bancario.
            </p>
          </div>

          {/* Cuentas Guardadas (Acceso Rápido 1-Click) */}
          <div className="p-3.5 bg-slate-50 dark:bg-valle-darkElevated rounded-xl border border-slate-200 dark:border-valle-darkBorder space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-extrabold uppercase tracking-wider text-valle-orange flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5" />
                <span>Cuentas Guardadas (Acceso 1-Click)</span>
              </span>
              <span className="text-[10px] font-semibold text-slate-500 dark:text-slate-400">Modo Demo</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              <button
                type="button"
                disabled={loading}
                onClick={() => handleQuickLogin('JUAN_JOSE')}
                className="p-2.5 rounded-xl bg-white dark:bg-valle-darkSurface border border-slate-200 dark:border-valle-darkBorder hover:border-valle-orange dark:hover:border-valle-orange text-left transition flex items-center gap-2.5 shadow-2xs group"
              >
                <div className="w-8 h-8 rounded-lg bg-valle-orange/15 text-valle-orange flex items-center justify-center flex-shrink-0">
                  <User className="w-4 h-4" />
                </div>
                <div className="min-w-0">
                  <div className="text-xs font-bold text-slate-900 dark:text-white truncate group-hover:text-valle-orange transition">
                    Juan José
                  </div>
                  <div className="text-[10px] text-slate-500 dark:text-slate-400 truncate">
                    Cliente ($3.000.000)
                  </div>
                </div>
              </button>

              <button
                type="button"
                disabled={loading}
                onClick={() => handleQuickLogin('GERENTE')}
                className="p-2.5 rounded-xl bg-white dark:bg-valle-darkSurface border border-slate-200 dark:border-valle-darkBorder hover:border-valle-blue dark:hover:border-sky-400 text-left transition flex items-center gap-2.5 shadow-2xs group"
              >
                <div className="w-8 h-8 rounded-lg bg-valle-blue/15 dark:bg-sky-500/20 text-valle-blue dark:text-sky-400 flex items-center justify-center flex-shrink-0">
                  <Building2 className="w-4 h-4" />
                </div>
                <div className="min-w-0">
                  <div className="text-xs font-bold text-slate-900 dark:text-white truncate group-hover:text-valle-blue dark:group-hover:text-sky-400 transition">
                    Gerencia Tesorería
                  </div>
                  <div className="text-[10px] text-slate-500 dark:text-slate-400 truncate">
                    Tablero ALM & BCRA
                  </div>
                </div>
              </button>
            </div>
          </div>

          {/* Formulario de Acceso Seguro */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs sm:text-sm font-semibold text-slate-700 dark:text-slate-300 mb-1">
                DNI, CUIL o Email
              </label>
              <div className="relative">
                <input
                  type="text"
                  required
                  value={identificador}
                  onChange={(e) => setIdentificador(e.target.value)}
                  placeholder="ej. 35123456 o email"
                  className="w-full text-xs sm:text-sm pl-8 pr-3 py-2.5 bg-white dark:bg-valle-darkElevated border border-slate-300 dark:border-valle-darkBorder rounded-xl outline-none focus:ring-2 focus:ring-valle-orange text-slate-900 dark:text-white"
                />
                <User className="w-4 h-4 text-slate-400 absolute left-2.5 top-3" />
              </div>
            </div>

            <div>
              <label className="block text-xs sm:text-sm font-semibold text-slate-700 dark:text-slate-300 mb-1">
                Contraseña
              </label>
              <div className="relative">
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full text-xs sm:text-sm pl-8 pr-3 py-2.5 bg-white dark:bg-valle-darkElevated border border-slate-300 dark:border-valle-darkBorder rounded-xl outline-none focus:ring-2 focus:ring-valle-orange text-slate-900 dark:text-white"
                />
                <Lock className="w-4 h-4 text-slate-400 absolute left-2.5 top-3" />
              </div>
            </div>

            {error && (
              <div className="p-3 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-300 text-xs rounded-xl flex items-center gap-2">
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 bg-valle-blue hover:bg-valle-bluelight text-white font-bold text-xs sm:text-sm rounded-xl shadow-md transition flex items-center justify-center gap-2"
            >
              {loading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <>
                  <span>Ingresar a mi Cuenta</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>

          {/* Enlace para Crear Cuenta */}
          <div className="text-center pt-2 border-t border-slate-100 dark:border-valle-darkBorder">
            <span className="text-xs sm:text-sm text-slate-600 dark:text-slate-400">¿No tienes cuenta bancaria? </span>
            <button
              type="button"
              onClick={() => {
                onClose();
                if (onRegisterClick) onRegisterClick();
              }}
              className="text-xs sm:text-sm font-bold text-valle-orange hover:underline"
            >
              Crear cuenta en 3 pasos
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default LoginModal;
