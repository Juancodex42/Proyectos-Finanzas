"""
Canal WebSocket Reactivo para la Simulación Temporal en Vivo (/ws/simulacion).
Transmite ticks diarios (1s = 1d), saldos, encajes BCRA y recibe comandos de control.
Referencia de diseño: docs/diagrama_logica_negocio_banco.md
"""

import asyncio
from datetime import date
import json
from typing import Any, Dict, Optional, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.database.connection import transaction
from src.database.repositories import balance_repo
from src.simulation.clock import SimulationClock
from src.simulation.daily_tick import ejecutar_cierre_diario
from src.simulation.synthetic_traffic import inyectar_trafico_sintetico

router = APIRouter(tags=["WebSocket Simulación"])


class ConnectionManager:
    """Administrador de clientes WebSocket conectados concurrentemente."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            self.active_connections.add(websocket)

    async def disconnect(self, websocket: WebSocket):
        async with self._lock:
            self.active_connections.discard(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        """Transmite un mensaje JSON a todas las pantallas conectadas."""
        encoded = json.dumps(message)
        async with self._lock:
            desconectados = set()
            for connection in self.active_connections:
                try:
                    await connection.send_text(encoded)
                except Exception:
                    desconectados.add(connection)
            for dead in desconectados:
                self.active_connections.discard(dead)


manager = ConnectionManager()
_sim_task: Optional[asyncio.Task] = None


def _construir_evento_tick(reloj: SimulationClock, nueva_fecha: date, tick_res: Any, trafico: Dict[str, Any], balance: Any) -> Dict[str, Any]:
    """Construye el payload unificado de un tick diario con todos los alias fullstack."""
    estado = reloj.obtener_estado()
    fecha_iso = nueva_fecha.isoformat()
    return {
        "tipo": "TICK",
        "subtipo": "TICK_DIARIO",
        "fecha_simulada": fecha_iso,
        "fecha_virtual": fecha_iso,
        "en_pausa": estado["en_pausa"],
        "corriendo": estado["corriendo"],
        "velocidad": estado["velocidad"],
        "segundos_por_dia": estado["segundos_por_dia"],
        "dias_transcurridos": reloj.dias_transcurridos,
        "rendimientos_acreditados": tick_res.rendimientos_flexibles_acreditados,
        "cuotas_cobradas": tick_res.cuotas_cobradas,
        "cuotas_en_mora": tick_res.cuotas_en_mora,
        "plazos_fijos_liquidados": tick_res.plazos_fijos_liquidados,
        "trafico_sintetico": trafico,
        "balance": {
            "capital_propio": balance.capital_propio_patrimonio if balance else 50000000.0,
            "patrimonio_neto": balance.capital_propio_patrimonio if balance else 50000000.0,
            "cashflow_seguro": balance.cashflow_seguro_prestable if balance else 57600000.0,
            "encaje_bcra": balance.encaje_obligatorio_bcra if balance else 5400000.0,
            "depositos_flexibles": balance.total_depositos_flexibles if balance else 18000000.0,
            "total_prestado": balance.total_prestado_activo if balance else 0.0,
        },
    }


async def _bucle_simulacion_fondo():
    """Tarea asíncrona de fondo que impulsa el avance del tiempo cuando no está en pausa."""
    reloj = SimulationClock.get_instance()
    while True:
        try:
            if not reloj.en_pausa:
                velocidad = reloj.segundos_por_dia
                await asyncio.sleep(velocidad)

                nueva_fecha = reloj.avanzar_un_dia()
                with transaction() as conn:
                    tick_res = ejecutar_cierre_diario(conn, nueva_fecha)
                    trafico = inyectar_trafico_sintetico(conn, nueva_fecha)
                    balance = balance_repo.obtener_ultimo_balance(conn)

                evento = _construir_evento_tick(reloj, nueva_fecha, tick_res, trafico, balance)
                await manager.broadcast(evento)
            else:
                await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            break
        except Exception:
            await asyncio.sleep(1.0)


def iniciar_tarea_simulacion():
    """Inicia el background loop de simulación si aún no está corriendo."""
    global _sim_task
    if _sim_task is None or _sim_task.done():
        _sim_task = asyncio.create_task(_bucle_simulacion_fondo())


def detener_tarea_simulacion():
    """Cancela la tarea asíncrona de fondo al apagar el servidor."""
    global _sim_task
    if _sim_task and not _sim_task.done():
        _sim_task.cancel()


@router.websocket("/ws/simulacion")
async def websocket_simulacion_endpoint(websocket: WebSocket):
    """Canal WebSocket bidireccional para recibir ticks y enviar comandos de control."""
    await manager.connect(websocket)
    iniciar_tarea_simulacion()
    reloj = SimulationClock.get_instance()

    estado_inicial = reloj.obtener_estado()
    await websocket.send_text(
        json.dumps(
            {
                "tipo": "ESTADO_INICIAL",
                "estado_reloj": estado_inicial,
                **estado_inicial,
            }
        )
    )

    try:
        while True:
            datos_texto = await websocket.receive_text()
            try:
                comando = json.loads(datos_texto)
                accion = (comando.get("action") or comando.get("comando") or "").strip().lower()

                if accion in ("play", "iniciar", "start"):
                    reloj.reanudar()
                    est = reloj.obtener_estado()
                    await manager.broadcast({"tipo": "ESTADO_RELOJ", "estado": est, **est})

                elif accion in ("pause", "pausar", "stop"):
                    reloj.pausar()
                    est = reloj.obtener_estado()
                    await manager.broadcast({"tipo": "ESTADO_RELOJ", "estado": est, **est})

                elif accion in ("speed", "set_velocidad"):
                    if "velocidad" in comando and comando["velocidad"]:
                        vel_mult = float(comando["velocidad"])
                        nuevo_seg = (1.0 / vel_mult) if vel_mult >= 1.0 else vel_mult
                    else:
                        nuevo_seg = float(comando.get("value", 1.0))
                    reloj.fijar_velocidad(max(0.1, nuevo_seg))
                    est = reloj.obtener_estado()
                    await manager.broadcast({"tipo": "ESTADO_RELOJ", "estado": est, **est})

                elif accion in ("advance_day", "avanzar_dia"):
                    nueva_fecha = reloj.avanzar_un_dia()
                    with transaction() as conn:
                        tick_res = ejecutar_cierre_diario(conn, nueva_fecha)
                        trafico = inyectar_trafico_sintetico(conn, nueva_fecha)
                        balance = balance_repo.obtener_ultimo_balance(conn)

                    evento = _construir_evento_tick(reloj, nueva_fecha, tick_res, trafico, balance)
                    await manager.broadcast(evento)

                elif accion in ("inyectar_trafico", "inject_traffic"):
                    cantidad = max(1, min(15, int(comando.get("cantidad", 5))))
                    fecha_act = reloj.fecha_actual
                    with transaction() as conn:
                        trafico_acum = {
                            "depositos_generados": 0,
                            "monto_total_depositado": 0.0,
                            "creditos_otorgados": 0,
                            "monto_total_prestado": 0.0,
                            "plazos_fijos_creados": 0,
                        }
                        for _ in range(cantidad):
                            t_parcial = inyectar_trafico_sintetico(
                                conn, fecha_act, prob_deposito=0.6, prob_credito=0.8, prob_plazo_fijo=0.3
                            )
                            for k in trafico_acum:
                                trafico_acum[k] += t_parcial.get(k, 0)
                        tick_res = ejecutar_cierre_diario(conn, fecha_act)
                        balance = balance_repo.obtener_ultimo_balance(conn)

                    evento = _construir_evento_tick(reloj, fecha_act, tick_res, trafico_acum, balance)
                    await manager.broadcast(evento)

            except json.JSONDecodeError:
                pass

    except WebSocketDisconnect:
        await manager.disconnect(websocket)
