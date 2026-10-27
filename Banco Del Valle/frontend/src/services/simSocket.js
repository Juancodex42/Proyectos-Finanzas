/**
 * Banco del Valle — Scoring Calculator & Lending Engine
 * Cliente WebSocket para la simulación reactiva en vivo (/ws/simulacion).
 */

class SimulationSocket {
  constructor() {
    this.ws = null;
    this.listeners = new Set();
    this.reconnectTimer = null;
    this.url = (window.location.protocol === 'https:' ? 'wss://' : 'ws://') + 
               window.location.host + '/ws/simulacion';
  }

  connect() {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    try {
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        console.log('[SimSocket] Conexión establecida con /ws/simulacion');
        if (this.reconnectTimer) {
          clearTimeout(this.reconnectTimer);
          this.reconnectTimer = null;
        }
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          this.notifyListeners(data);
        } catch (e) {
          console.error('[SimSocket] Error parseando mensaje WS:', e);
        }
      };

      this.ws.onclose = () => {
        console.warn('[SimSocket] Desconectado. Reintentando en 3s...');
        this.scheduleReconnect();
      };

      this.ws.onerror = (err) => {
        console.error('[SimSocket] Error en socket:', err);
        this.ws?.close();
      };
    } catch (e) {
      console.error('[SimSocket] Fallo al iniciar WebSocket:', e);
      this.scheduleReconnect();
    }
  }

  scheduleReconnect() {
    if (!this.reconnectTimer) {
      this.reconnectTimer = setTimeout(() => {
        this.reconnectTimer = null;
        this.connect();
      }, 3000);
    }
  }

  subscribe(listener) {
    this.listeners.add(listener);
    if (!this.ws || (this.ws.readyState !== WebSocket.OPEN && this.ws.readyState !== WebSocket.CONNECTING)) {
      this.connect();
    }
    return () => this.listeners.delete(listener);
  }

  notifyListeners(data) {
    this.listeners.forEach((fn) => {
      try {
        fn(data);
      } catch (err) {
        console.error('[SimSocket] Error en listener callback:', err);
      }
    });
  }

  sendCommand(comando, payload = {}) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ comando, ...payload }));
    } else {
      console.warn('[SimSocket] Socket no disponible para enviar:', comando);
    }
  }

  iniciar() {
    this.sendCommand('INICIAR');
  }

  pausar() {
    this.sendCommand('PAUSAR');
  }

  avanzarDia() {
    this.sendCommand('AVANZAR_DIA');
  }

  setVelocidad(velocidad) {
    this.sendCommand('SET_VELOCIDAD', { velocidad });
  }

  inyectarTrafico(cantidad = 5) {
    this.sendCommand('INYECTAR_TRAFICO', { cantidad });
  }

  reiniciar() {
    this.sendCommand('REINICIAR');
  }
}

export const simSocket = new SimulationSocket();
export default simSocket;
