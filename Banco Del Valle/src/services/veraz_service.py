"""
Servicio de consulta y simulación estocástica de buró crediticio (Veraz / BCRA).
Emula la Central de Deudores del Sistema Financiero Argentino (Situaciones 1 a 6).
Referencia de diseño: docs/diagrama_logica_negocio_banco.md
"""

from datetime import date
import random
import sqlite3
from typing import Optional

from src.database.repositories import persona_repo
from src.domain.models import HistorialVeraz


def interpretar_situacion_bcra(situacion: int) -> str:
    """Retorna la denominación oficial normada por el BCRA para la situación crediticia."""
    descripciones = {
        1: "Situación 1: Normal (Sin atrasos relevantes o al día)",
        2: "Situación 2: Riesgo Bajo / Seguimiento Especial (Atrasos de 31 a 90 días)",
        3: "Situación 3: Riesgo Medio / Con Problemas (Atrasos de 91 a 180 días)",
        4: "Situación 4: Alto Riesgo de Insolvencia (Atrasos de 181 a 360 días)",
        5: "Situación 5: Irrecuperable (Mora superior a 360 días)",
        6: "Situación 6: Irrecuperable por Disposición Técnica",
    }
    return descripciones.get(situacion, f"Situación {situacion}: No clasificada")


def consultar_buro_externo(
    documento: str,
    persona_id: Optional[int] = None,
    empresa_id: Optional[int] = None,
    forzar_situacion: Optional[int] = None,
    simular_estocastico: bool = False,
) -> HistorialVeraz:
    """
    Simula la consulta externa a la Central de Deudores del BCRA / Buró Veraz.
    Si forzar_situacion está presente, fija dicha situación para pruebas deterministas.
    Si simular_estocastico es True, aplica probabilidades reales del sistema financiero.
    """
    doc_limpio = documento.strip().replace(".", "").replace("-", "")
    today_iso = date.today().isoformat()

    # Caso 1: Forzado explícito para testing y escenarios
    if forzar_situacion is not None:
        peor_sit = max(1, min(6, forzar_situacion))
        score_base = {1: 750, 2: 580, 3: 450, 4: 350, 5: 250, 6: 180}.get(peor_sit, 600)
        return HistorialVeraz(
            persona_id=persona_id,
            empresa_id=empresa_id,
            fecha_consulta=today_iso,
            score_externo=score_base,
            peor_situacion_bcra=peor_sit,
            monto_deuda_externa_total=250000.0 * peor_sit,
            cantidad_bancos_acreedores=peor_sit,
            cheques_rechazados_monto=50000.0 if peor_sit >= 3 else 0.0,
        )

    # Caso 2: Clientes conocidos por defecto (Juan José Cano y PyME Minería)
    if doc_limpio in ("35123456", "30712345678"):
        return HistorialVeraz(
            persona_id=persona_id,
            empresa_id=empresa_id,
            fecha_consulta=today_iso,
            score_externo=740,
            peor_situacion_bcra=1,
            monto_deuda_externa_total=0.0,
            cantidad_bancos_acreedores=1,
            cheques_rechazados_monto=0.0,
        )

    # Caso 3: Generación estocástica calibrada
    if simular_estocastico:
        r = random.random()
        if r < 0.80:
            peor_sit = 1
            score = random.randint(660, 850)
            deuda = round(random.uniform(0.0, 500000.0), 2)
            cheques = 0.0
        elif r < 0.90:
            peor_sit = 2
            score = random.randint(520, 649)
            deuda = round(random.uniform(500000.0, 1500000.0), 2)
            cheques = 0.0
        elif r < 0.96:
            peor_sit = 3
            score = random.randint(420, 519)
            deuda = round(random.uniform(1000000.0, 3000000.0), 2)
            cheques = round(random.uniform(50000.0, 200000.0), 2)
        elif r < 0.99:
            peor_sit = 4
            score = random.randint(320, 419)
            deuda = round(random.uniform(2000000.0, 6000000.0), 2)
            cheques = round(random.uniform(200000.0, 800000.0), 2)
        else:
            peor_sit = 5
            score = random.randint(200, 319)
            deuda = round(random.uniform(3000000.0, 10000000.0), 2)
            cheques = round(random.uniform(500000.0, 2000000.0), 2)

        return HistorialVeraz(
            persona_id=persona_id,
            empresa_id=empresa_id,
            fecha_consulta=today_iso,
            score_externo=score,
            peor_situacion_bcra=peor_sit,
            monto_deuda_externa_total=deuda,
            cantidad_bancos_acreedores=random.randint(1, 4),
            cheques_rechazados_monto=cheques,
        )

    # Caso 4: Cliente nuevo estándar sin antecedentes negativos
    return HistorialVeraz(
        persona_id=persona_id,
        empresa_id=empresa_id,
        fecha_consulta=today_iso,
        score_externo=680,
        peor_situacion_bcra=1,
        monto_deuda_externa_total=50000.0,
        cantidad_bancos_acreedores=1,
        cheques_rechazados_monto=0.0,
    )


def sincronizar_y_guardar_buro(
    conn: sqlite3.Connection,
    documento: str,
    persona_id: Optional[int] = None,
    empresa_id: Optional[int] = None,
    forzar_situacion: Optional[int] = None,
) -> HistorialVeraz:
    """Consulta el buró externo y persiste el snapshot en la base de datos relacional."""
    reporte = consultar_buro_externo(
        documento=documento,
        persona_id=persona_id,
        empresa_id=empresa_id,
        forzar_situacion=forzar_situacion,
    )
    persona_repo.guardar_historial_veraz(conn, reporte)
    return reporte
