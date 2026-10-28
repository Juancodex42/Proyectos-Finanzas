"""
Motor de Cierre Diario Bancario (Daily Tick: 1s = 1d).
Devenga rendimientos flexibles, cobra cuotas, gestiona mora, encajes BCRA y P&L.
Referencia de diseño: docs/diagrama_logica_negocio_banco.md
"""

from datetime import date
import sqlite3

from src.config import (
    CAPITAL_PATRIMONIO_INICIAL,
    ENCAJE_FLEXIBLE_PCT,
    ENCAJE_PLAZO_FIJO_PCT,
)
from src.database.repositories import (
    balance_repo,
    cuenta_repo,
    deposito_repo,
    movimiento_repo,
    persona_repo,
    prestamo_repo,
)
from src.domain.interest_rate import calcular_interes_flexible_diario
from src.domain.models import (
    BalancePatrimonio,
    EstadoPlazoFijo,
    EstadoPrestamo,
    MovimientoCuenta,
    ResultadoDailyTick,
    TipoMovimiento,
)
from src.domain.scoring import calcular_dias_mora_exactos, calcular_intereses_punitorios
from src.domain.treasury import (
    calcular_cashflow_seguro,
    calcular_encaje_requerido,
    calcular_margen_financiero_neto,
    capitalizar_utilidades_en_balance,
)


def ejecutar_cierre_diario(
    conn: sqlite3.Connection,
    fecha_simulada: date,
) -> ResultadoDailyTick:
    """
    Ejecuta en secuencia atómica todos los eventos contables y normativos del día:
    1. Rendimientos diarios de cuentas a la vista (28.5% TNA).
    2. Cobro de cuotas vencidas y devengamiento de intereses punitorios en mora.
    3. Liquidación de plazos fijos tradicionales al vencimiento.
    4. Acreditación de haberes mensuales en cuentas sueldo.
    5. Capitalización del margen financiero neto (P&L) y recálculo de encajes BCRA.
    """
    fecha_iso = fecha_simulada.isoformat()
    total_rendimientos_acreditados = 0.0
    intereses_cuotas_cobradas = 0.0
    punitorios_cobrados_dia = 0.0
    intereses_pf_liquidados = 0.0
    cuotas_cobradas = 0
    cuotas_en_mora = 0
    plazos_fijos_liquidados = 0
    sueldos_acreditados = 0

    # ------------------------------------------------------------------------
    # 1. Devengamiento y Acreditación de Rendimientos Diarios Flexibles
    # ------------------------------------------------------------------------
    cursor = conn.cursor()
    tipo_rend_val = (
        TipoMovimiento.RENDIMIENTO_FLEXIBLE_DIARIO.value
        if hasattr(TipoMovimiento.RENDIMIENTO_FLEXIBLE_DIARIO, "value")
        else str(TipoMovimiento.RENDIMIENTO_FLEXIBLE_DIARIO)
    )
    cuentas_activas = cuenta_repo.listar_todas_cuentas_activas(conn)
    for cuenta in cuentas_activas:
        if cuenta.saldo_actual > 0:
            # Control de Idempotencia Estricta: evitar doble acreditación en la misma fecha calendario
            cursor.execute(
                """
                SELECT 1 FROM movimientos_cuenta
                WHERE cuenta_id = ?
                  AND tipo_movimiento = ?
                  AND fecha_hora LIKE ?
                LIMIT 1
                """,
                (cuenta.id, tipo_rend_val, f"{fecha_iso}%"),
            )
            if cursor.fetchone():
                continue

            interes_dia = calcular_interes_flexible_diario(
                saldo=cuenta.saldo_actual,
                tna_flexible=cuenta.tna_rendimiento_diario,
            )
            if interes_dia >= 0.01:
                nuevo_saldo = round(cuenta.saldo_actual + interes_dia, 2)
                cuenta_repo.actualizar_saldo(conn, cuenta.id, nuevo_saldo)
                movimiento_repo.registrar_movimiento(
                    conn,
                    MovimientoCuenta(
                        cuenta_id=cuenta.id,
                        tipo_movimiento=TipoMovimiento.RENDIMIENTO_FLEXIBLE_DIARIO,
                        monto=interes_dia,
                        saldo_posterior=nuevo_saldo,
                        fecha_hora=f"{fecha_iso} 00:00:01",
                        descripcion=f"Rendimiento Flexible Diario ({cuenta.tna_rendimiento_diario * 100:.1f}% TNA)",
                    ),
                )
                total_rendimientos_acreditados += interes_dia

    # ------------------------------------------------------------------------
    # 2. Acreditación de Haberes Mensuales (si coincide el día del mes)
    # ------------------------------------------------------------------------
    tipo_sueldo_val = (
        TipoMovimiento.ACREDITACION_SUELDO.value
        if hasattr(TipoMovimiento.ACREDITACION_SUELDO, "value")
        else str(TipoMovimiento.ACREDITACION_SUELDO)
    )
    personas = persona_repo.listar_personas(conn, limite=1000)
    for p in personas:
        if p.monto_sueldo_acreditado > 0 and p.dia_cobro_sueldo == fecha_simulada.day:
            cuentas_p = cuenta_repo.obtener_cuentas_por_persona(conn, p.id)
            cuenta_sueldo = next((c for c in cuentas_p if c.es_cuenta_sueldo), None) or (cuentas_p[0] if cuentas_p else None)
            if cuenta_sueldo:
                # Control de Idempotencia: no duplicar sueldo si ya fue acreditado en la fecha
                cursor.execute(
                    """
                    SELECT 1 FROM movimientos_cuenta
                    WHERE cuenta_id = ?
                      AND tipo_movimiento = ?
                      AND fecha_hora LIKE ?
                    LIMIT 1
                    """,
                    (cuenta_sueldo.id, tipo_sueldo_val, f"{fecha_iso}%"),
                )
                if cursor.fetchone():
                    continue

                nuevo_saldo = round(cuenta_sueldo.saldo_actual + p.monto_sueldo_acreditado, 2)
                cuenta_repo.actualizar_saldo(conn, cuenta_sueldo.id, nuevo_saldo)
                movimiento_repo.registrar_movimiento(
                    conn,
                    MovimientoCuenta(
                        cuenta_id=cuenta_sueldo.id,
                        tipo_movimiento=TipoMovimiento.ACREDITACION_SUELDO,
                        monto=p.monto_sueldo_acreditado,
                        saldo_posterior=nuevo_saldo,
                        fecha_hora=f"{fecha_iso} 06:00:00",
                        descripcion=f"Acreditación de Sueldo Mensual — Haberes de {p.nombre_completo}",
                    ),
                )
                sueldos_acreditados += 1

    # ------------------------------------------------------------------------
    # 3. Cobro y Mora de Cuotas de Préstamos
    # ------------------------------------------------------------------------
    cuotas_pendientes = prestamo_repo.obtener_cuotas_pendientes_a_la_fecha(conn, fecha_iso)
    for cuota in cuotas_pendientes:
        prestamo = prestamo_repo.obtener_prestamo_por_id(conn, cuota.prestamo_id)
        if not prestamo:
            continue

        cuentas_titular = []
        if prestamo.persona_id:
            cuentas_titular = cuenta_repo.obtener_cuentas_por_persona(conn, prestamo.persona_id)
        elif prestamo.empresa_id:
            cuentas_titular = cuenta_repo.obtener_cuentas_por_empresa(conn, prestamo.empresa_id)

        cuenta_debito = cuentas_titular[0] if cuentas_titular else None

        if cuenta_debito and cuenta_debito.saldo_actual >= cuota.monto_cuota:
            nuevo_saldo = round(cuenta_debito.saldo_actual - cuota.monto_cuota, 2)
            cuenta_repo.actualizar_saldo(conn, cuenta_debito.id, nuevo_saldo)
            movimiento_repo.registrar_movimiento(
                conn,
                MovimientoCuenta(
                    cuenta_id=cuenta_debito.id,
                    tipo_movimiento=TipoMovimiento.COBRO_CUOTA_PRESTAMO,
                    monto=cuota.monto_cuota,
                    saldo_posterior=nuevo_saldo,
                    fecha_hora=f"{fecha_iso} 08:00:00",
                    descripcion=f"Cobro Cuota #{cuota.numero_cuota} de Préstamo #{prestamo.id}",
                ),
            )
            punitorios_cobrados_dia += cuota.intereses_punitorios
            intereses_cuotas_cobradas += round(cuota.monto_cuota * 0.35, 2)
            prestamo_repo.actualizar_cuota(
                conn=conn,
                cuota_id=cuota.id,
                fecha_pago=fecha_iso,
                dias_mora=0,
                intereses_punitorios=0.0,
            )
            cuotas_cobradas += 1

            cuotas_totales = prestamo_repo.obtener_cuotas_por_prestamo(conn, prestamo.id)
            if all(c.fecha_pago is not None for c in cuotas_totales):
                prestamo_repo.actualizar_estado_prestamo(conn, prestamo.id, EstadoPrestamo.CANCELADO)
            else:
                prestamo_repo.actualizar_estado_prestamo(conn, prestamo.id, EstadoPrestamo.AL_DIA)
        else:
            dias_atraso = calcular_dias_mora_exactos(
                fecha_vencimiento=cuota.fecha_vencimiento,
                fecha_pago=None,
                fecha_actual=fecha_iso,
            )
            punitorios = calcular_intereses_punitorios(
                monto_cuota=cuota.monto_cuota,
                dias_mora=dias_atraso,
            )
            prestamo_repo.actualizar_cuota(
                conn=conn,
                cuota_id=cuota.id,
                fecha_pago=None,
                dias_mora=dias_atraso,
                intereses_punitorios=punitorios,
            )
            prestamo_repo.actualizar_estado_prestamo(conn, prestamo.id, EstadoPrestamo.EN_MORA)
            cuotas_en_mora += 1

    # ------------------------------------------------------------------------
    # 4. Liquidación de Plazos Fijos Vencidos
    # ------------------------------------------------------------------------
    pfs_vencidos = deposito_repo.obtener_plazos_fijos_vencidos_a_la_fecha(conn, fecha_iso)
    for pf in pfs_vencidos:
        cuentas_dest = []
        if pf.persona_id:
            cuentas_dest = cuenta_repo.obtener_cuentas_por_persona(conn, pf.persona_id)
        elif pf.empresa_id:
            cuentas_dest = cuenta_repo.obtener_cuentas_por_empresa(conn, pf.empresa_id)

        if cuentas_dest:
            cta = cuentas_dest[0]
            monto_liquidacion = round(pf.monto_depositado + pf.intereses_a_generar, 2)
            nuevo_saldo = round(cta.saldo_actual + monto_liquidacion, 2)
            cuenta_repo.actualizar_saldo(conn, cta.id, nuevo_saldo)
            movimiento_repo.registrar_movimiento(
                conn,
                MovimientoCuenta(
                    cuenta_id=cta.id,
                    tipo_movimiento=TipoMovimiento.LIQUIDACION_PLAZO_FIJO,
                    monto=monto_liquidacion,
                    saldo_posterior=nuevo_saldo,
                    fecha_hora=f"{fecha_iso} 10:00:00",
                    descripcion=f"Liquidación de Plazo Fijo #{pf.id} (Capital ${pf.monto_depositado:,.2f} + Intereses ${pf.intereses_a_generar:,.2f})",
                ),
            )
            deposito_repo.actualizar_estado_plazo_fijo(conn, pf.id, EstadoPlazoFijo.LIQUIDADO)
            intereses_pf_liquidados += pf.intereses_a_generar
            plazos_fijos_liquidados += 1

    # ------------------------------------------------------------------------
    # 5. Capitalización del Margen Financiero (P&L) y Recálculo de Encajes BCRA
    # ------------------------------------------------------------------------
    total_flexibles = cuenta_repo.sumar_saldos_cuentas_flexibles(conn)
    total_pf = deposito_repo.sumar_total_depositos_plazo_fijo_activos(conn)
    total_prestado = prestamo_repo.obtener_total_prestado_activo(conn)

    _, _, encaje_requerido = calcular_encaje_requerido(
        total_flexibles=total_flexibles,
        total_plazos_fijos=total_pf,
        alicuota_flex=ENCAJE_FLEXIBLE_PCT,
        alicuota_pf=ENCAJE_PLAZO_FIJO_PCT,
    )

    ultimo_balance = balance_repo.obtener_ultimo_balance(conn)
    capital_propio = ultimo_balance.capital_propio_patrimonio if ultimo_balance else CAPITAL_PATRIMONIO_INICIAL

    devengamiento_cartera_y_tesoreria = round(
        (total_prestado * 0.60 / 365.0) + (capital_propio * 0.35 / 365.0) + intereses_cuotas_cobradas, 2
    )
    intereses_pasivos_dia = round(total_rendimientos_acreditados + intereses_pf_liquidados, 2)
    _, resultado_neto_dia = calcular_margen_financiero_neto(
        intereses_cobrados=devengamiento_cartera_y_tesoreria,
        intereses_pagados=intereses_pasivos_dia,
        punitorios_cobrados=punitorios_cobrados_dia,
    )

    balance_base = BalancePatrimonio(
        fecha_corte=fecha_iso,
        total_depositos_plazo_fijo=total_pf,
        total_depositos_flexibles=total_flexibles,
        encaje_obligatorio_bcra=encaje_requerido,
        capital_propio_patrimonio=capital_propio,
        total_prestado_activo=total_prestado,
        cashflow_seguro_prestable=0.0,
    )

    balance_snapshot = capitalizar_utilidades_en_balance(balance_base, resultado_neto_dia)
    balance_snapshot.cashflow_seguro_prestable = calcular_cashflow_seguro(
        balance=balance_snapshot,
        alicuota_flex=ENCAJE_FLEXIBLE_PCT,
        alicuota_pf=ENCAJE_PLAZO_FIJO_PCT,
    )
    snapshot_id = balance_repo.registrar_snapshot_balance(conn, balance_snapshot)

    return ResultadoDailyTick(
        fecha_simulada=fecha_iso,
        rendimientos_flexibles_acreditados=round(total_rendimientos_acreditados, 2),
        cuotas_cobradas=cuotas_cobradas,
        cuotas_en_mora=cuotas_en_mora,
        plazos_fijos_liquidados=plazos_fijos_liquidados,
        sueldos_acreditados=sueldos_acreditados,
        balance_snapshot_id=snapshot_id,
    )
