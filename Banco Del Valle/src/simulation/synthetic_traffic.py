"""
Generador de tráfico transaccional sintético (Synthetic Traffic Engine).
Inyecta depósitos, plazos fijos y préstamos estocásticos durante la simulación.
Referencia de diseño: docs/diagrama_logica_negocio_banco.md
"""

from datetime import date, timedelta
import random
import sqlite3
from typing import Any, Dict

from src.database.repositories import (
    balance_repo,
    cuenta_repo,
    deposito_repo,
    empresa_repo,
    movimiento_repo,
    persona_repo,
    prestamo_repo,
)
from src.domain.interest_rate import calcular_cuota_frances, calcular_interes_plazo_fijo, generar_cronograma_frances
from src.domain.models import (
    Cuota,
    EstadoPlazoFijo,
    EstadoPrestamo,
    HistorialVeraz,
    MovimientoCuenta,
    PlazoFijo,
    Prestamo,
    TipoMovimiento,
)
from src.domain.scoring import evaluar_scoring_persona
from src.domain.treasury import verificar_disponibilidad_desembolso


def inyectar_trafico_sintetico(
    conn: sqlite3.Connection,
    fecha_simulada: date,
    prob_deposito: float = 0.35,
    prob_credito: float = 0.20,
    prob_plazo_fijo: float = 0.15,
) -> Dict[str, Any]:
    """Inyecta operaciones probabilísticas para enriquecer la dinámica de la simulación."""
    resultado: Dict[str, Any] = {
        "depositos_generados": 0,
        "monto_total_depositado": 0.0,
        "creditos_otorgados": 0,
        "monto_total_prestado": 0.0,
        "plazos_fijos_creados": 0,
    }
    fecha_iso = fecha_simulada.isoformat()
    cuentas = cuenta_repo.listar_todas_cuentas_activas(conn)
    if not cuentas:
        return resultado

    # 1. Depósitos / Transferencias Entrantes Sintéticas
    if random.random() < prob_deposito:
        cuenta_sel = random.choice(cuentas)
        monto_deposito = round(random.uniform(50000.0, 800000.0), 2)
        nuevo_saldo = round(cuenta_sel.saldo_actual + monto_deposito, 2)
        cuenta_repo.actualizar_saldo(conn, cuenta_sel.id, nuevo_saldo)
        movimiento_repo.registrar_movimiento(
            conn,
            MovimientoCuenta(
                cuenta_id=cuenta_sel.id,
                tipo_movimiento=TipoMovimiento.TRANSFERENCIA_IN,
                monto=monto_deposito,
                saldo_posterior=nuevo_saldo,
                fecha_hora=f"{fecha_iso} 11:30:00",
                descripcion="Transferencia Inmediata Recibida — COELSA / Débito Interbanking",
            ),
        )
        resultado["depositos_generados"] += 1
        resultado["monto_total_depositado"] += monto_deposito

    # 2. Solicitudes y Desembolsos de Préstamos Sintéticos
    if random.random() < prob_credito:
        personas = persona_repo.listar_personas(conn, limite=100)
        if personas:
            p = random.choice(personas)
            monto_solicitado = round(random.choice([500000.0, 1000000.0, 1500000.0, 2000000.0]), 2)
            plazo_meses = random.choice([6, 12, 18, 24])
            tna_base = 0.60
            cuota_estimada = calcular_cuota_frances(monto_solicitado, tna_base, plazo_meses)
            veraz_mock = HistorialVeraz(persona_id=p.id, score_externo=720, peor_situacion_bcra=1)

            # Evaluar scoring y capacidad de pago
            scoring_res = evaluar_scoring_persona(
                persona=p,
                veraz=veraz_mock,
                cuota_propuesta=cuota_estimada,
                tna_base=tna_base,
            )

            if scoring_res.aprobado:
                # Verificar liquidez y encajes de tesorería
                ultimo_balance = balance_repo.obtener_ultimo_balance(conn)
                if ultimo_balance:
                    eval_liquidez = verificar_disponibilidad_desembolso(
                        monto_solicitado=monto_solicitado,
                        balance=ultimo_balance,
                    )
                else:
                    eval_liquidez = None

                if eval_liquidez and eval_liquidez.desembolso_autorizado:
                    plan = generar_cronograma_frances(
                        capital=monto_solicitado,
                        tna=scoring_res.tasa_anual_asignada,
                        cuotas=plazo_meses,
                    )
                    cuotas_obj = []
                    for c_det in plan.cronograma:
                        venc = (fecha_simulada + timedelta(days=30 * c_det.numero_cuota)).isoformat()
                        cuotas_obj.append(
                            Cuota(
                                numero_cuota=c_det.numero_cuota,
                                monto_cuota=c_det.monto_cuota,
                                fecha_vencimiento=venc,
                            )
                        )
                    prestamo_repo.crear_prestamo(
                        conn=conn,
                        prestamo=Prestamo(
                            persona_id=p.id,
                            tipo_credito="PERSONAL",
                            monto_capital=monto_solicitado,
                            tasa_nominal_anual=scoring_res.tasa_anual_asignada,
                            cantidad_cuotas=plazo_meses,
                            fecha_otorgamiento=fecha_iso,
                            estado=EstadoPrestamo.ACTIVO,
                        ),
                        cronograma=cuotas_obj,
                    )
                    # Acreditar desembolso en cuenta
                    cuentas_p = cuenta_repo.obtener_cuentas_por_persona(conn, p.id)
                    if cuentas_p:
                        cta = cuentas_p[0]
                        nuevo_saldo = round(cta.saldo_actual + monto_solicitado, 2)
                        cuenta_repo.actualizar_saldo(conn, cta.id, nuevo_saldo)
                        movimiento_repo.registrar_movimiento(
                            conn,
                            MovimientoCuenta(
                                cuenta_id=cta.id,
                                tipo_movimiento=TipoMovimiento.DEPOSITO,
                                monto=monto_solicitado,
                                saldo_posterior=nuevo_saldo,
                                fecha_hora=f"{fecha_iso} 14:00:00",
                                descripcion=f"Desembolso Préstamo Personal Sistema Francés ({plazo_meses} meses)",
                            ),
                        )
                    resultado["creditos_otorgados"] += 1
                    resultado["monto_total_prestado"] += monto_solicitado

    # 3. Constitución de Plazos Fijos Sintéticos
    if random.random() < prob_plazo_fijo:
        cuenta_sel = random.choice(cuentas)
        if cuenta_sel.saldo_actual >= 300000.0:
            monto_pf = round(min(500000.0, cuenta_sel.saldo_actual * 0.5), 2)
            tna_pf = 0.38
            intereses = calcular_interes_plazo_fijo(monto_pf, tna_pf, dias_plazo=30)
            fecha_venc = (fecha_simulada + timedelta(days=30)).isoformat()

            # Debitar de la cuenta transaccional
            nuevo_saldo = round(cuenta_sel.saldo_actual - monto_pf, 2)
            cuenta_repo.actualizar_saldo(conn, cuenta_sel.id, nuevo_saldo)
            movimiento_repo.registrar_movimiento(
                conn,
                MovimientoCuenta(
                    cuenta_id=cuenta_sel.id,
                    tipo_movimiento=TipoMovimiento.EXTRACCION,
                    monto=monto_pf,
                    saldo_posterior=nuevo_saldo,
                    fecha_hora=f"{fecha_iso} 15:30:00",
                    descripcion=f"Constitución de Plazo Fijo Tradicional a 30 días ({tna_pf * 100:.1f}% TNA)",
                ),
            )
            deposito_repo.crear_plazo_fijo(
                conn,
                PlazoFijo(
                    persona_id=cuenta_sel.persona_id,
                    empresa_id=cuenta_sel.empresa_id,
                    monto_depositado=monto_pf,
                    tasa_nominal_anual=tna_pf,
                    fecha_inicio=fecha_iso,
                    fecha_vencimiento=fecha_venc,
                    intereses_a_generar=intereses,
                    estado=EstadoPlazoFijo.ACTIVO,
                ),
            )
            resultado["plazos_fijos_creados"] += 1

    return resultado
