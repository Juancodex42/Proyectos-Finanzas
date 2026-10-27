import React, { useState, useEffect } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ThemeProvider } from './context/ThemeContext';
import { Navbar } from './components/common/Navbar';
import { Footer } from './components/common/Footer';
import { LoginModal } from './components/common/LoginModal';
import { RegisterModal } from './components/common/RegisterModal';
import { ExportModal } from './components/common/ExportModal';
import { HomePage } from './pages/HomePage';
import { ClientHomeBanking } from './pages/ClientHomeBanking';
import { EmployeeDashboard } from './pages/EmployeeDashboard';

function AppContent() {
  const { user, isAuthenticated, isGerente, isCliente } = useAuth();
  const [activeView, setActiveView] = useState('home'); // 'home' | 'homebanking' | 'dashboard'
  const [segmento, setSegmento] = useState('INDIVIDUOS'); // 'INDIVIDUOS' | 'EMPRESAS'

  // Modales globales
  const [isLoginOpen, setIsLoginOpen] = useState(false);
  const [isRegisterOpen, setIsRegisterOpen] = useState(false);
  const [registerTipo, setRegisterTipo] = useState('PERSONA');
  const [isExportOpen, setIsExportOpen] = useState(false);
  const [exportModulo, setExportModulo] = useState('PRESTAMOS');

  const handleOpenRegister = (tipo) => {
    const finalTipo = tipo || (segmento === 'EMPRESAS' ? 'EMPRESA' : 'PERSONA');
    setRegisterTipo(finalTipo);
    setIsRegisterOpen(true);
  };

  // Sincronización inicial y al autenticarse
  useEffect(() => {
    if (isAuthenticated) {
      if (isGerente && activeView === 'home') {
        setActiveView('dashboard');
      } else if (isCliente && activeView === 'home') {
        setActiveView('homebanking');
      }
    }
  }, [isAuthenticated, isGerente, isCliente]);

  const handleOpenExportModal = (modulo = 'PRESTAMOS') => {
    setExportModulo(modulo);
    setIsExportOpen(true);
  };

  const handleLoginSuccess = (targetView) => {
    if (targetView) {
      setActiveView(targetView);
    } else if (isGerente) {
      setActiveView('dashboard');
    } else {
      setActiveView('homebanking');
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-slate-100 dark:bg-valle-darkCanvas text-slate-900 dark:text-slate-100 transition-colors duration-200">
      {/* Barra de Navegación Dinámica con Identidad Catamarca Ciudad y Switch de Tema */}
      <Navbar
        activeView={activeView}
        setActiveView={setActiveView}
        segmento={segmento}
        setSegmento={setSegmento}
        onOpenLogin={() => setIsLoginOpen(true)}
        onOpenRegister={() => handleOpenRegister()}
      />

      {/* Contenido Principal según Vista Activa */}
      <main className="flex-1">
        {activeView === 'home' && (
          <HomePage
            segmento={segmento}
            onOpenRegister={handleOpenRegister}
            onOpenLogin={() => setIsLoginOpen(true)}
            onOpenExportModal={handleOpenExportModal}
          />
        )}

        {activeView === 'homebanking' && (
          <ClientHomeBanking
            onGoToDashboard={() => setActiveView('dashboard')}
          />
        )}

        {activeView === 'dashboard' && (
          <EmployeeDashboard />
        )}
      </main>

      {/* Pie de Página Institucional */}
      <Footer />

      {/* Modales Globales */}
      <LoginModal
        isOpen={isLoginOpen}
        onClose={() => setIsLoginOpen(false)}
        onRegisterClick={() => setIsRegisterOpen(true)}
        onSuccess={handleLoginSuccess}
      />

      <RegisterModal
        isOpen={isRegisterOpen}
        onClose={() => setIsRegisterOpen(false)}
        initialTipo={registerTipo}
        onSuccess={(targetView) => setActiveView(targetView || 'homebanking')}
      />

      <ExportModal
        isOpen={isExportOpen}
        onClose={() => setIsExportOpen(false)}
        defaultModulo={exportModulo}
      />
    </div>
  );
}

export function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <AppContent />
      </AuthProvider>
    </ThemeProvider>
  );
}

export default App;
