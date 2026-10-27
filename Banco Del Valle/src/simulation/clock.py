"""
Controlador del Reloj de Simulación Temporal (Simulation Clock).
Administra el avance cronológico acelerado (1s = 1d), pausas y velocidades.
Referencia de diseño: docs/diagrama_logica_negocio_banco.md
"""

from datetime import date, timedelta
from typing import Any, Dict, Optional
import threading


class SimulationClock:
    """Reloj de tiempo virtual sincronizado para el motor de simulación."""

    _instance: Optional["SimulationClock"] = None
    _lock = threading.Lock()

    def __init__(self, fecha_inicial: Optional[date] = None):
        self._fecha_actual: date = fecha_inicial or date.today()
        self._en_pausa: bool = True
        self._segundos_por_dia: float = 1.0  # 1 segundo real = 1 día virtual
        self._contador_dias_simulados: int = 0
        self._mutex = threading.Lock()

    @classmethod
    def get_instance(cls, fecha_inicial: Optional[date] = None) -> "SimulationClock":
        """Retorna la instancia única (Singleton) del reloj de simulación."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(fecha_inicial)
            return cls._instance

    @property
    def fecha_actual(self) -> date:
        """Retorna la fecha virtual actual."""
        with self._mutex:
            return self._fecha_actual

    @property
    def en_pausa(self) -> bool:
        """Indica si el avance automático está pausado."""
        with self._mutex:
            return self._en_pausa

    @property
    def segundos_por_dia(self) -> float:
        """Velocidad de reproducción en segundos reales por cada día virtual."""
        with self._mutex:
            return self._segundos_por_dia

    @property
    def dias_transcurridos(self) -> int:
        """Cantidad total de días virtuales transcurridos desde el inicio."""
        with self._mutex:
            return self._contador_dias_simulados

    def avanzar_un_dia(self) -> date:
        """Avanza exactamente 24 horas virtuales el calendario del banco."""
        with self._mutex:
            self._fecha_actual += timedelta(days=1)
            self._contador_dias_simulados += 1
            return self._fecha_actual

    def avanzar_dias(self, dias: int) -> date:
        """Avanza N días en el calendario del banco."""
        if dias < 1:
            raise ValueError("La cantidad de días a avanzar debe ser positiva.")
        with self._mutex:
            self._fecha_actual += timedelta(days=dias)
            self._contador_dias_simulados += dias
            return self._fecha_actual

    def fijar_fecha(self, nueva_fecha: date) -> None:
        """Establece manualmente una fecha de calendario específica."""
        with self._mutex:
            self._fecha_actual = nueva_fecha

    def reiniciar(self, fecha_inicial: Optional[date] = None) -> date:
        """Restablece el reloj virtual a la fecha inicial, pausa y pone a cero los días transcurridos."""
        with self._mutex:
            self._fecha_actual = fecha_inicial or date(2026, 10, 26)
            self._en_pausa = True
            self._segundos_por_dia = 1.0
            self._contador_dias_simulados = 0
            return self._fecha_actual

    def pausar(self) -> None:
        """Detiene el avance automático del reloj."""
        with self._mutex:
            self._en_pausa = True

    def reanudar(self) -> None:
        """Reanuda el avance automático del reloj."""
        with self._mutex:
            self._en_pausa = False

    def fijar_velocidad(self, segundos_por_dia: float) -> None:
        """Modifica la velocidad del tick (mínimo 0.05s/d, máximo 10s/d)."""
        if segundos_por_dia <= 0.05:
            raise ValueError("La velocidad debe ser superior a 0.05 segundos por día.")
        with self._mutex:
            self._segundos_por_dia = round(segundos_por_dia, 2)

    def obtener_estado(self) -> Dict[str, Any]:
        """Retorna un resumen estructurado del estado del reloj con alias fullstack."""
        with self._mutex:
            fecha_iso = self._fecha_actual.isoformat()
            corriendo = not self._en_pausa
            vel_mult = round(1.0 / self._segundos_por_dia, 1) if self._segundos_por_dia > 0 else 1.0
            return {
                "fecha_simulada": fecha_iso,
                "fecha_virtual": fecha_iso,
                "en_pausa": self._en_pausa,
                "corriendo": corriendo,
                "segundos_por_dia": self._segundos_por_dia,
                "velocidad": int(vel_mult) if vel_mult.is_integer() else vel_mult,
                "dias_transcurridos": self._contador_dias_simulados,
            }
