import { useState, lazy, Suspense } from 'react';
import { Routes, Route } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import Home from './pages/Home';
import ErrorBoundary from './components/ErrorBoundary';
import { FileProvider } from './context/FileContext';
import './index.css';

// Code-splitting via lazy loading for heavy pages
const Dashboard = lazy(() => import('./pages/Dashboard'));
const Calendar = lazy(() => import('./pages/Calendar'));
const History = lazy(() => import('./pages/History'));
const APIs = lazy(() => import('./pages/APIs'));
const Reports = lazy(() => import('./pages/Reports'));
const Settings = lazy(() => import('./pages/Settings'));
const Impuestos = lazy(() => import('./pages/Impuestos'));

function PageFallback() {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      height: '60vh',
      color: 'var(--text-muted, #94a3b8)',
      fontSize: '0.9rem'
    }}>
      <div style={{ textAlign: 'center' }}>
        <div style={{
          width: '24px',
          height: '24px',
          border: '2px solid rgba(255,255,255,0.15)',
          borderTopColor: '#3B82F6',
          borderRadius: '50%',
          margin: '0 auto 0.75rem',
          animation: 'spin 0.8s linear infinite'
        }} />
        <span>Cargando...</span>
      </div>
    </div>
  );
}

function App() {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <FileProvider>
      <div className="app-container" style={{ minHeight: '100vh', background: 'var(--bg-color)' }}>
        <Sidebar isOpen={sidebarOpen} setIsOpen={setSidebarOpen} />
        <main 
          className="main-content"
          style={{ 
            marginLeft: sidebarOpen ? '260px' : '0px', 
            transition: 'margin-left 0.3s ease-in-out',
            minHeight: '100vh',
            boxSizing: 'border-box'
          }}
        >
          <ErrorBoundary>
            <Suspense fallback={<PageFallback />}>
              <Routes>
                <Route path="/" element={<Home />} />
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/calendar" element={<Calendar />} />
                <Route path="/impuestos" element={<Impuestos />} />
                <Route path="/history" element={<History />} />
                <Route path="/apis" element={<APIs />} />
                <Route path="/reports" element={<Reports />} />
                <Route path="/settings" element={<Settings />} />
              </Routes>
            </Suspense>
          </ErrorBoundary>
        </main>
      </div>
    </FileProvider>
  );
}


export default App;
