import React from 'react';
import { User, LogOut, ShieldAlert, Building2, Users, Sun, Moon, Check } from 'lucide-react';
import { BrandLogo } from './BrandLogo';
import { useAuth } from '../../context/AuthContext';
import { useTheme } from '../../context/ThemeContext';

/**
 * Navbar — Barra superior institucional con navegación dinámica por rol y selector de tema.
 */
export function Navbar({
  activeView,
  setActiveView,
  segmento,
  setSegmento,
  onOpenLogin,
  onOpenRegister,
}) {
  const { user, isAuthenticated, isGerente, isCliente, logout } = useAuth();
  const { theme, isDark, setTheme } = useTheme();

  return (
    <header className="sticky top-0 z-40 bg-white dark:bg-valle-darkSurface border-b border-slate-200 dark:border-valle-darkBorder shadow-xs transition-colors duration-200">
      <div className="max-w-[1600px] mx-auto px-3 sm:px-8 xl:px-12">
        <div className="flex items-center justify-between h-16 sm:h-20 gap-3 sm:gap-4">
          
          {/* Logo Corporativo e Isotipo B+V */}
          <div
            className="cursor-pointer flex items-center flex-shrink-0"
            onClick={() => {
              if (isGerente) {
                setActiveView('dashboard');
              } else if (isCliente) {
                setActiveView('homebanking');
              } else {
                setActiveView('home');
              }
            }}
          >
            <BrandLogo size="md" className="sm:hidden" variant={isDark ? 'light' : 'dark'} />
            <BrandLogo size="lg" className="hidden sm:flex" variant={isDark ? 'light' : 'dark'} />
          </div>

          {/* Navegación Central Dinámica según Estado de Autenticación y Rol */}
          <div className="hidden md:flex items-center gap-4 lg:gap-6">
            
            {/* CASO 1: NO AUTENTICADO — Selector de Segmentos y Portal Público */}
            {!isAuthenticated && (
              <>
                <div className="flex items-center bg-slate-100 dark:bg-valle-darkElevated p-1.5 rounded-2xl border border-slate-200 dark:border-valle-darkBorder shadow-inner">
                  <button
                    type="button"
                    onClick={() => setSegmento('INDIVIDUOS')}
                    className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs sm:text-sm font-bold transition-all duration-150 ${
                      segmento === 'INDIVIDUOS'
                        ? 'bg-valle-orange text-white shadow-md'
                        : 'text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white hover:bg-white dark:hover:bg-white/10'
                    }`}
                  >
                    <Users className="w-4 h-4" />
                    <span>Individuos & Familias</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setSegmento('EMPRESAS')}
                    className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs sm:text-sm font-bold transition-all duration-150 ${
                      segmento === 'EMPRESAS'
                        ? 'bg-valle-orange text-white shadow-md'
                        : 'text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white hover:bg-white dark:hover:bg-white/10'
                    }`}
                  >
                    <Building2 className="w-4 h-4" />
                    <span>Empresas & PyMEs</span>
                  </button>
                </div>

                <div className="h-6 w-px bg-slate-200 dark:bg-slate-700 hidden lg:block" />

                <button
                  type="button"
                  onClick={() => setActiveView('home')}
                  className={`px-3.5 py-2 rounded-xl text-xs sm:text-sm font-bold transition-all ${
                    activeView === 'home'
                      ? 'bg-slate-100 dark:bg-white/15 text-valle-blue dark:text-white shadow-xs'
                      : 'text-slate-600 dark:text-slate-300 hover:text-valle-blue dark:hover:text-white'
                  }`}
                >
                  Portal Público
                </button>
              </>
            )}

            {/* CASO 2: GERENTE AUTENTICADO — Solo Vista Gerencial ALM */}
            {isAuthenticated && isGerente && (
              <div className="flex items-center gap-2.5 px-4 py-2 rounded-2xl bg-valle-blue/10 dark:bg-valle-darkElevated border border-valle-blue/20 dark:border-valle-darkBorder text-valle-blue dark:text-sky-300 font-bold text-xs sm:text-sm">
                <ShieldAlert className="w-4 h-4 text-valle-orange" />
                <span>Terminal Ejecutiva de Tesorería & ALM</span>
                <span className="text-[10px] font-extrabold uppercase px-2 py-0.5 rounded-full bg-valle-orange text-white ml-1">
                  En Vivo
                </span>
              </div>
            )}

            {/* CASO 3: CLIENTE AUTENTICADO — Solo Home Banking */}
            {isAuthenticated && isCliente && (
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setActiveView('homebanking')}
                  className="flex items-center gap-2 px-4 py-2 rounded-xl text-xs sm:text-sm font-bold bg-valle-orange text-white shadow-md transition-all"
                >
                  <span>Mi Home Banking</span>
                </button>
              </div>
            )}

          </div>

          {/* Menú Derecho: Selector de Tema + Estado de Autenticación */}
          <div className="flex items-center gap-3.5 flex-shrink-0">
            
            {/* Selector Segmentado de Tema Inequívoco */}
            <div className="flex items-center bg-slate-100 dark:bg-valle-darkElevated p-1 rounded-xl border border-slate-200 dark:border-valle-darkBorder shadow-inner">
              <button
                type="button"
                onClick={() => setTheme('light')}
                className={`flex items-center gap-1 px-2.5 sm:px-3 py-1 rounded-lg text-xs font-bold transition-all ${
                  theme === 'light'
                    ? 'bg-white text-slate-900 shadow-xs'
                    : 'text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-white'
                }`}
                title="Activar Modo Claro"
              >
                <Sun className="w-3.5 h-3.5 text-amber-500" />
                <span className="hidden sm:inline">Claro</span>
                {theme === 'light' && <Check className="w-3 h-3 text-emerald-600" />}
              </button>
              <button
                type="button"
                onClick={() => setTheme('dark')}
                className={`flex items-center gap-1 px-2.5 sm:px-3 py-1 rounded-lg text-xs font-bold transition-all ${
                  theme === 'dark'
                    ? 'bg-valle-orange text-white shadow-xs'
                    : 'text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-white'
                }`}
                title="Activar Modo Oscuro"
              >
                <Moon className="w-3.5 h-3.5 text-white" />
                <span className="hidden sm:inline">Oscuro</span>
                {theme === 'dark' && <Check className="w-3 h-3 text-white" />}
              </button>
            </div>

            {/* Separador vertical sutil */}
            <div className="h-6 w-px bg-slate-200 dark:bg-slate-700 hidden sm:block" />

            {/* Autenticado vs No Autenticado */}
            {isAuthenticated ? (
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-2.5 px-3 py-1.5 rounded-xl bg-slate-50 dark:bg-valle-darkElevated border border-slate-200 dark:border-valle-darkBorder">
                  <div className="w-7 h-7 rounded-full bg-valle-orange text-white font-bold flex items-center justify-center text-xs shadow-xs">
                    {user?.nombre?.[0] || 'U'}
                  </div>
                  <div className="hidden sm:block text-left">
                    <span className="block text-slate-900 dark:text-white font-bold text-xs leading-none">
                      {user?.nombre || user?.identificador}
                    </span>
                    <span className="text-[10px] text-slate-500 dark:text-slate-400 leading-none mt-0.5 block">
                      {isGerente ? 'Gerencia de Tesorería' : user?.rol}
                    </span>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={() => {
                    logout();
                    setActiveView('home');
                  }}
                  title="Cerrar Sesión"
                  className="p-2 text-slate-500 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-950/30 rounded-xl transition"
                >
                  <LogOut className="w-4 h-4" />
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-2.5 sm:gap-3">
                <button
                  type="button"
                  onClick={onOpenRegister}
                  className="hidden sm:inline-flex px-4 py-2 border border-valle-blue dark:border-valle-orange/80 text-valle-blue dark:text-valle-orange hover:bg-slate-50 dark:hover:bg-valle-orange/10 text-xs sm:text-sm font-bold rounded-xl transition"
                >
                  Crear Cuenta
                </button>
                <button
                  type="button"
                  onClick={onOpenLogin}
                  className="px-4 py-2 bg-valle-orange hover:bg-valle-orangedark text-white text-xs sm:text-sm font-bold rounded-xl shadow-md transition flex items-center gap-2"
                >
                  <User className="w-4 h-4" />
                  <span>Ingresar</span>
                </button>
              </div>
            )}

          </div>

        </div>
      </div>

      {/* Selector de Segmento Exclusivo para Móviles (Familias vs Empresas) */}
      {!isAuthenticated && activeView === 'home' && (
        <div className="flex md:hidden items-center justify-center py-2 px-3 border-t border-slate-200/80 dark:border-valle-darkBorder bg-slate-50/90 dark:bg-valle-darkSurface/90">
          <div className="grid grid-cols-2 w-full max-w-sm bg-slate-200/70 dark:bg-valle-darkElevated p-1 rounded-xl">
            <button
              type="button"
              onClick={() => setSegmento('INDIVIDUOS')}
              className={`flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-xs font-bold transition-all ${
                segmento === 'INDIVIDUOS'
                  ? 'bg-valle-orange text-white shadow-xs'
                  : 'text-slate-600 dark:text-slate-300 hover:text-slate-900'
              }`}
            >
              <Users className="w-3.5 h-3.5" />
              <span>Familias</span>
            </button>
            <button
              type="button"
              onClick={() => setSegmento('EMPRESAS')}
              className={`flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-xs font-bold transition-all ${
                segmento === 'EMPRESAS'
                  ? 'bg-valle-orange text-white shadow-xs'
                  : 'text-slate-600 dark:text-slate-300 hover:text-slate-900'
              }`}
            >
              <Building2 className="w-3.5 h-3.5" />
              <span>Empresas</span>
            </button>
          </div>
        </div>
      )}
    </header>
  );
}

export default Navbar;
