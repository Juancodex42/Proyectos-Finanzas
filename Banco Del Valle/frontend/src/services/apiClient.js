/**
 * Banco del Valle — Scoring Calculator & Lending Engine
 * Cliente HTTP centralizado para comunicación con el backend FastAPI.
 */

const BASE_URL = '';

// Limpieza preventiva inmediata de credenciales persistidas en localStorage legacy
try {
  if (typeof window !== 'undefined') {
    localStorage.removeItem('valle_auth_token');
    localStorage.removeItem('valle_auth_user');
  }
} catch {
  // Ignorar si el acceso a localStorage está restringido
}

/**
 * Obtiene el token JWT desde el almacenamiento de sesión efímero (sessionStorage).
 */
export function getAuthToken() {
  try {
    if (typeof window !== 'undefined') {
      // Garantizar que no queden residuos en localStorage
      if (localStorage.getItem('valle_auth_token')) {
        localStorage.removeItem('valle_auth_token');
        localStorage.removeItem('valle_auth_user');
      }
      return sessionStorage.getItem('valle_auth_token') || null;
    }
  } catch {}
  return null;
}

/**
 * Persiste el token JWT y el perfil de sesión solo durante la sesión activa (sessionStorage).
 */
export function setAuthToken(token, user) {
  try {
    if (typeof window !== 'undefined') {
      localStorage.removeItem('valle_auth_token');
      localStorage.removeItem('valle_auth_user');

      if (token) {
        sessionStorage.setItem('valle_auth_token', token);
      } else {
        sessionStorage.removeItem('valle_auth_token');
      }
      if (user) {
        sessionStorage.setItem('valle_auth_user', JSON.stringify(user));
      } else {
        sessionStorage.removeItem('valle_auth_user');
      }
    }
  } catch {}
}

/**
 * Recupera el usuario autenticado desde el almacenamiento de sesión (sessionStorage).
 */
export function getAuthUser() {
  try {
    if (typeof window !== 'undefined') {
      const raw = sessionStorage.getItem('valle_auth_user');
      return raw ? JSON.parse(raw) : null;
    }
  } catch {
    return null;
  }
  return null;
}

/**
 * Wrapper de fetch con manejo de headers y JSON.
 */
async function request(endpoint, options = {}) {
  const token = getAuthToken();
  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  };

  const response = await fetch(`${BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorDetail = `Error ${response.status}: ${response.statusText}`;
    try {
      const errorJson = await response.json();
      errorDetail = errorJson.detail || errorDetail;
    } catch {
      // Ignorar si no es JSON
    }
    throw new Error(errorDetail);
  }

  // Si es un archivo binario (blob)
  if (options.responseType === 'blob') {
    return response.blob();
  }

  return response.json();
}

export const apiClient = {
  // Autenticación
  login: async (identificador, password) => {
    return request('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ identificador, password }),
    });
  },

  // Scoring y Simuladores
  simularPrestamo: async (payload) => {
    return request('/api/scoring/simular-prestamo', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  consultarDni: async (dni) => {
    return request(`/api/scoring/consultar-dni/${encodeURIComponent(dni)}`);
  },

  buscarPorDni: async (dni) => {
    return request(`/api/scoring/consultar-dni/${encodeURIComponent(dni)}`);
  },

  consultarCuit: async (cuit) => {
    return request(`/api/scoring/consultar-cuit/${encodeURIComponent(cuit)}`);
  },

  buscarPorCuit: async (cuit) => {
    return request(`/api/scoring/consultar-cuit/${encodeURIComponent(cuit)}`);
  },

  // Onboarding y Registro
  registroPersona: async (payload) => {
    return request('/api/clientes/registro-persona', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  registroEmpresa: async (payload) => {
    return request('/api/clientes/registro-empresa', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  // Home Banking Clientes
  getHomeBanking: async (personaId) => {
    const token = getAuthToken();
    if (token) {
      return request('/api/client/resumen');
    }
    return request(`/api/clientes/homebanking/${personaId || 1}`);
  },

  transferir: async (payload) => {
    return request('/api/clientes/transferir', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  depositarPrueba: async (payload) => {
    return request('/api/clientes/depositar-prueba', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  constituirPlazoFijo: async (payload) => {
    return request('/api/clientes/constituir-plazo-fijo', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  cancelarPlazoFijo: async (plazoFijoId) => {
    return request(`/api/clientes/cancelar-plazo-fijo/${plazoFijoId}`, {
      method: 'POST',
    });
  },

  // Tablero Gerencial
  getKpis: async () => {
    return request('/api/dashboard/kpis');
  },

  getOperaciones: async () => {
    return request('/api/dashboard/operaciones');
  },

  getAlmGaps: async () => {
    return request('/api/dashboard/alm-gaps');
  },

  getLiveRates: async () => {
    return request('/api/dashboard/live-rates');
  },

  resetSimulacion: async () => {
    return request('/api/dashboard/simulacion/reset', { method: 'POST' });
  },

  getProyecciones: async (escenario = 'BASE', horizonte = '1_ANO') => {
    const params = new URLSearchParams({ escenario, horizonte });
    return request(`/api/dashboard/proyecciones?${params.toString()}`);
  },

  // Padrón Central de Clientes
  getUsuarios: async (params = {}) => {
    const query = new URLSearchParams();
    if (params.page) query.append('page', params.page);
    if (params.limit) query.append('limit', params.limit);
    if (params.tipo && params.tipo !== 'TODOS') query.append('tipo', params.tipo);
    if (params.estado && params.estado !== 'TODOS') query.append('estado', params.estado);
    if (params.busqueda) query.append('busqueda', params.busqueda);
    if (params.orden) query.append('orden', params.orden);
    return request(`/api/dashboard/usuarios?${query.toString()}`);
  },

  // Operaciones Normativas de Baja y Arrepentimiento (Ley 24.240 y BCRA)
  solicitarBaja: async (payload) => {
    return request('/api/clientes/solicitar-baja', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  solicitarArrepentimiento: async (payload) => {
    return request('/api/clientes/arrepentimiento', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  exportarUsuarios: async (formato = 'csv') => {
    const token = getAuthToken();
    const response = await fetch(`/api/dashboard/exportar?modulo=USUARIOS&formato=${formato}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!response.ok) {
      throw new Error(`Error descargando padrón: ${response.statusText}`);
    }
    return response.blob();
  },

  // Descarga y Exportación Universal
  exportarArchivo: async ({ modulo, formato, fechaInicio, fechaFin, estado }) => {
    const params = new URLSearchParams({
      modulo,
      formato,
      ...(fechaInicio ? { fecha_inicio: fechaInicio } : {}),
      ...(fechaFin ? { fecha_fin: fechaFin } : {}),
      ...(estado ? { estado } : {}),
    });

    const token = getAuthToken();
    const response = await fetch(`/api/dashboard/exportar?${params.toString()}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });

    if (!response.ok) {
      throw new Error(`Error en la exportación: ${response.statusText}`);
    }

    return response.blob();
  },
};

export default apiClient;
