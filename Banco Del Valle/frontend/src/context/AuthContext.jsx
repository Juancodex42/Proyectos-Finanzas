import React, { createContext, useContext, useState, useEffect } from 'react';
import { apiClient, getAuthToken, getAuthUser, setAuthToken } from '../services/apiClient';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setTokenState] = useState(getAuthToken);
  const [user, setUserState] = useState(getAuthUser);
  const [loading, setLoading] = useState(false);

  const login = async (identificador, password) => {
    setLoading(true);
    try {
      const res = await apiClient.login(identificador, password);
      const token = res.access_token || res.token;
      const userObj = res.usuario || {
        id: res.usuario_id,
        persona_id: res.persona_id,
        empresa_id: res.empresa_id,
        identificador: res.identificador,
        email: res.email,
        nombre: res.nombre || res.identificador,
        rol: res.rol,
      };
      setAuthToken(token, userObj);
      setTokenState(token);
      setUserState(userObj);
      return userObj;
    } finally {
      setLoading(false);
    }
  };

  const loginDemoJuanJose = async () => {
    return login('35123456', 'Valle1234!');
  };

  const loginDemoGerente = async () => {
    return login('gerencia@bancodelvalle.com.ar', 'Gerencia2026!');
  };

  const logout = () => {
    setAuthToken(null, null);
    setTokenState(null);
    setUserState(null);
  };

  const value = {
    token,
    user,
    isAuthenticated: !!token && !!user,
    isGerente: user?.rol === 'GERENTE' || user?.rol === 'EMPLEADO',
    isCliente: user?.rol === 'CLIENTE',
    loading,
    login,
    loginDemoJuanJose,
    loginDemoGerente,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth debe ser utilizado dentro de un AuthProvider');
  }
  return context;
}

export default AuthContext;
