/**
 * Banco del Valle — Scoring Calculator & Lending Engine
 * Cliente HTTP centralizado para comunicación con el backend FastAPI.
 */

const BASE_URL = '';

/**
 * Obtiene el token JWT persistido en el almacenamiento local.
 */
export function getAuthToken() {
  return localStorage.getItem('valle_auth_token') || null;
}

/**
 * Persiste el token JWT y el perfil de sesión.
 */
export function setAuthToken(token, user) {
  if (token) {
    localStorage.setItem('valle_auth_token', token);
  } else {
    localStorage.removeItem('valle_auth_token');
  }
  if (user) {
    localStorage.setItem('valle_auth_user', JSON.stringify(user));
  } else {
    localStorage.removeItem('valle_auth_user');
  }
}

/**
 * Recupera el usuario autenticado desde el almacenamiento local.
 */
export function getAuthUser() {
  const raw = localStorage.getItem('valle_auth_user');
  try {
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
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
