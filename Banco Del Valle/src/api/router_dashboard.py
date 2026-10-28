"""
Router del Tablero Gerencial, KPIs de Solvencia, Encajes BCRA y Exportaciones.
Expone métricas ejecutivas ALM, proyecciones P&L, cartera activa y reportes.
Referencia de diseño: docs/margen_financiero_y_proyecciones_escenarios.md
"""

from datetime import date, timedelta
import math
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Header, HTTPException, Query, Response, status

from src.config import (
    CAPITAL_PATRIMONIO_INICIAL,
    COLCHON_LIQUIDEZ_SEGURIDAD,
    ENCAJE_FLEXIBLE_PCT,
    ENCAJE_PLAZO_FIJO_PCT,
    TNA_FLEXIBLE_BASE,
    TNA_PLAZO_FIJO_BASE,
    TNA_PRESTAMO_PERSONAL_BASE,
)
from src.database.connection import get_db_connection, reset_database
from src.database.repositories import (
    balance_repo,
    cuenta_repo,
    deposito_repo,
    movimiento_repo,
    prestamo_repo,
    usuario_repo,
)
from src.domain.interest_rate import calcular_cuota_frances
from src.domain.models import BalancePatrimonio
from src.domain.treasury import (
    calcular_cashflow_seguro,
    calcular_encaje_requerido,
    proyectar_patrimonio_escenario,
)
from src.simulation.clock import SimulationClock
from src.services.export_service import (
    exportar_a_csv,
    exportar_a_excel,
    exportar_a_pdf,
)
from src.services.security_service import decodificar_token

router = APIRouter(tags=["Tablero Gerencial y Tesorería"])


def verificar_acceso_gerencial(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    """Exige credenciales con rol 'GERENTE' o 'EMPLEADO' para acceder al tablero."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token no suministrado.")
    token = authorization.split(" ")[1]
    payload = decodificar_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido o expirado.")
    rol = payload.get("rol", "")
    if rol not in ("GERENTE", "EMPLEADO"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado: rol gerencial requerido.")
    return payload


@router.get("/api/dashboard/kpis")
def obtener_kpis_gerenciales():
    """Retorna las métricas clave de solvencia, liquidez prestable y encajes BCRA en tiempo real."""
    conn = get_db_connection()
    try:
        ultimo_b = balance_repo.obtener_ultimo_balance(conn)
        total_flex = cuenta_repo.sumar_saldos_cuentas_flexibles(conn)
        total_pf = deposito_repo.sumar_total_depositos_plazo_fijo_activos(conn)
        total_prestado = prestamo_repo.obtener_total_prestado_activo(conn)

        _, _, encaje_exigido = calcular_encaje_requerido(
            total_flexibles=total_flex,
            total_plazos_fijos=total_pf,
            alicuota_flex=ENCAJE_FLEXIBLE_PCT,
            alicuota_pf=ENCAJE_PLAZO_FIJO_PCT,
        )

        capital = ultimo_b.capital_propio_patrimonio if ultimo_b else CAPITAL_PATRIMONIO_INICIAL
        
        balance_vivo = BalancePatrimonio(
            fecha_corte=ultimo_b.fecha_corte if ultimo_b else date.today().isoformat(),
            total_depositos_plazo_fijo=total_pf,
            total_depositos_flexibles=total_flex,
            encaje_obligatorio_bcra=encaje_exigido,
            capital_propio_patrimonio=capital,
            total_prestado_activo=total_prestado,
            cashflow_seguro_prestable=0.0,
        )
        cashflow = calcular_cashflow_seguro(
            balance=balance_vivo,
            alicuota_flex=ENCAJE_FLEXIBLE_PCT,
            alicuota_pf=ENCAJE_PLAZO_FIJO_PCT,
        )

        prestamos_activos = prestamo_repo.obtener_prestamos_activos(conn)
        en_mora = sum(1 for p in prestamos_activos if p.estado.value == "EN_MORA")
        tasa_mora = (en_mora / len(prestamos_activos) * 100.0) if prestamos_activos else 0.0

        return {
            "fecha_corte": ultimo_b.fecha_corte if ultimo_b else date.today().isoformat(),
            "capital_propio_patrimonio": capital,
            "patrimonio_neto": capital,
            "total_depositos_flexibles": total_flex,
            "total_depositos_plazo_fijo": total_pf,
            "encaje_obligatorio_bcra": encaje_exigido,
            "posicion_encaje_bcra": cashflow,
            "cashflow_seguro_prestable": cashflow,
            "total_prestado_activo": total_prestado,
            "cantidad_prestamos_activos": len(prestamos_activos),
            "cantidad_prestamos_en_mora": en_mora,
            "tasa_mora_porcentaje": round(tasa_mora, 2),
            "colchon_seguridad": COLCHON_LIQUIDEZ_SEGURIDAD,
        }
    finally:
        conn.close()


@router.get("/api/dashboard/alm-gaps")
def obtener_brechas_alm():
    """
    Retorna la estructura de descalce de plazos y brechas temporales (ALM).
    Compara cobranzas proyectadas de cuotas vs vencimientos de depósitos a 30, 60 y 90 días.
    """
    conn = get_db_connection()
    try:
        reloj = SimulationClock.get_instance()
        f_base = reloj.fecha_actual
        cursor = conn.cursor()

        tramos = [
            ("30 Días", f_base, f_base + timedelta(days=30), 0.10),
            ("60 Días", f_base + timedelta(days=31), f_base + timedelta(days=60), 0.05),
            ("90 Días", f_base + timedelta(days=61), f_base + timedelta(days=90), 0.02),
        ]

        # Saldo flexible para ponderación de volatilidad
        total_flex = cuenta_repo.sumar_saldos_cuentas_flexibles(conn)

        resultado = []
        for nombre, d_inicio, d_fin, pct_flex_volatilidad in tramos:
            s_ini = d_inicio.isoformat()
            s_fin = d_fin.isoformat()

            # Cobranzas de préstamos activos en el tramo
            cursor.execute(
                """
                SELECT COALESCE(SUM(c.monto_cuota), 0.0)
                FROM cuotas c
                JOIN prestamos p ON c.prestamo_id = p.id
                WHERE c.fecha_pago IS NULL 
                  AND p.estado IN ('ACTIVO', 'AL_DIA', 'EN_MORA')
                  AND c.fecha_vencimiento BETWEEN ? AND ?
                """,
                (s_ini, s_fin),
            )
            cobranzas_cuotas = float(cursor.fetchone()[0] or 0.0)

            # Vencimientos de plazos fijos en el tramo
            cursor.execute(
                """
                SELECT COALESCE(SUM(monto_depositado + intereses_a_generar), 0.0)
                FROM plazos_fijos
                WHERE estado = 'ACTIVO' AND fecha_vencimiento BETWEEN ? AND ?
                """,
                (s_ini, s_fin),
            )
            vencimientos_pf = float(cursor.fetchone()[0] or 0.0)

            # Volatilidad estimada de depósitos vista como pasivo exigible
            vencimiento_total = vencimientos_pf + (total_flex * pct_flex_volatilidad)

            resultado.append({
                "tramo": nombre,
                "cobranzas": round(cobranzas_cuotas, 2),
                "vencimientos": round(vencimiento_total, 2),
            })

        return resultado
    finally:
        conn.close()


@router.post("/api/dashboard/simulacion/reset")
@router.post("/api/simulacion/reset")
async def reset_simulacion_http():
    """Restablece el reloj virtual de simulación y la base de datos a su estado inicial limpio."""
    reloj = SimulationClock.get_instance()
    reloj.reiniciar(date(2026, 10, 26))
    conn = get_db_connection()
    try:
        reset_database(conn)
        ultimo_b = balance_repo.obtener_ultimo_balance(conn)
        est = reloj.obtener_estado()
        evento_reset = {
            "tipo": "RESET",
            "subtipo": "SIMULACION_REINICIADA",
            "fecha_simulada": est["fecha_virtual"],
            "fecha_virtual": est["fecha_virtual"],
            "estado_reloj": est,
            "balance": {
                "capital_propio": ultimo_b.capital_propio_patrimonio if ultimo_b else 50000000.0,
                "patrimonio_neto": ultimo_b.capital_propio_patrimonio if ultimo_b else 50000000.0,
                "cashflow_seguro": ultimo_b.cashflow_seguro_prestable if ultimo_b else 57600000.0,
                "encaje_bcra": ultimo_b.encaje_obligatorio_bcra if ultimo_b else 5400000.0,
                "depositos_flexibles": ultimo_b.total_depositos_flexibles if ultimo_b else 18000000.0,
                "total_prestado": ultimo_b.total_prestado_activo if ultimo_b else 0.0,
            },
            **est,
        }
    finally:
        conn.close()

    try:
        from src.api.websocket_sim import manager
        await manager.broadcast(evento_reset)
    except Exception as exc:
        pass

    return {
        "exito": True,
        "mensaje": "Simulación y base de datos restablecidas al estado inicial.",
        "fecha_simulada": "2026-10-26",
        "capital_propio": ultimo_b.capital_propio_patrimonio if ultimo_b else 50000000.0,
        "balance": evento_reset["balance"],
    }



@router.get("/api/dashboard/live-rates")
def obtener_curva_tasas():
    """Retorna la estructura de tasas activas y pasivas vigentes y el spread financiero."""
    spread = TNA_PRESTAMO_PERSONAL_BASE - TNA_FLEXIBLE_BASE
    return {
        "tasa_activa_personal": TNA_PRESTAMO_PERSONAL_BASE,
        "tasa_activa_porcentaje": f"{TNA_PRESTAMO_PERSONAL_BASE * 100:.1f}%",
        "tasa_pasiva_flexible": TNA_FLEXIBLE_BASE,
        "tasa_pasiva_flexible_porcentaje": f"{TNA_FLEXIBLE_BASE * 100:.1f}%",
        "tasa_pasiva_plazo_fijo": TNA_PLAZO_FIJO_BASE,
        "tasa_pasiva_plazo_fijo_porcentaje": f"{TNA_PLAZO_FIJO_BASE * 100:.1f}%",
        "spread_bruto": round(spread, 4),
        "spread_porcentaje": f"{spread * 100:.1f}%",
    }


@router.get("/api/dashboard/profit-projections")
@router.get("/api/dashboard/proyecciones")
def obtener_proyecciones_ganancias(horizonte: str = "1_ANO"):
    """Calcula la proyección patrimonial bajo escenarios Optimista, Base y Pesimista."""
    meses = 36 if horizonte == "3_ANOS" else (60 if horizonte == "5_ANOS" else 12)
    conn = get_db_connection()
    try:
        ultimo_b = balance_repo.obtener_ultimo_balance(conn)
        capital_inicial = ultimo_b.capital_propio_patrimonio if ultimo_b else CAPITAL_PATRIMONIO_INICIAL

        curva_base = proyectar_patrimonio_escenario(
            patrimonio_inicial=capital_inicial,
            tasa_crecimiento_anual=0.30,
            meses=meses,
        )
        curva_opt = proyectar_patrimonio_escenario(
            patrimonio_inicial=capital_inicial,
            tasa_crecimiento_anual=0.56,
            meses=meses,
        )
        curva_pes = proyectar_patrimonio_escenario(
            patrimonio_inicial=capital_inicial,
            tasa_crecimiento_anual=0.07,
            meses=meses,
        )

        proj_base_final = curva_base[-1]
        proj_opt_final = curva_opt[-1]
        proj_pes_final = curva_pes[-1]

        return {
            "capital_base": capital_inicial,
            "meses_proyectados": meses,
            "escenarios": {
                "base": {
                    "tasa_interes_activa": "60%",
                    "mora_esperada": "3.5%",
                    "patrimonio_proyectado_12m": proj_base_final,
                    "ganancia_estimada": round(proj_base_final - capital_inicial, 2),
                    "curva_mensual": curva_base,
                },
                "optimista": {
                    "tasa_interes_activa": "65%",
                    "mora_esperada": "1.5%",
                    "patrimonio_proyectado_12m": proj_opt_final,
                    "ganancia_estimada": round(proj_opt_final - capital_inicial, 2),
                    "curva_mensual": curva_opt,
                },
                "pesimista": {
                    "tasa_interes_activa": "52%",
                    "mora_esperada": "8.0%",
                    "patrimonio_proyectado_12m": proj_pes_final,
                    "ganancia_estimada": round(proj_pes_final - capital_inicial, 2),
                    "curva_mensual": curva_pes,
                },
            },
        }
    finally:
        conn.close()


@router.get("/api/dashboard/operaciones")
def listar_operaciones_activas(limite: int = 50):
    """Retorna la lista de préstamos activos con seguimiento de atrasos, cuota y situación BCRA."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT p.id, p.persona_id, p.empresa_id, p.monto_capital,
                   p.tasa_nominal_anual, p.cantidad_cuotas,
                   p.fecha_otorgamiento, p.estado, p.tipo_credito,
                   COALESCE(per.nombre_completo, emp.razon_social) AS titular,
                   COALESCE(per.dni, emp.cuit) AS documento,
                   COALESCE(MAX(c.dias_mora), 0) AS max_dias_mora,
                   COALESCE(MAX(c.monto_cuota), 0.0) AS cuota_registrada,
                   SUM(CASE WHEN c.fecha_pago IS NOT NULL THEN 1 ELSE 0 END) AS cuotas_pagas,
                   COALESCE(SUM(c.intereses_punitorios), 0.0) AS total_punitorios
            FROM prestamos p
            LEFT JOIN personas per ON p.persona_id = per.id
            LEFT JOIN empresas emp ON p.empresa_id = emp.id
            LEFT JOIN cuotas c ON p.id = c.prestamo_id
            GROUP BY p.id
            ORDER BY p.id DESC
            LIMIT ?
            """,
            (limite,),
        )
        filas = cursor.fetchall()
        resultado = []
        for r in filas:
            d = dict(r)
            dias_mora = int(d.get("max_dias_mora") or 0)
            monto_cap = float(d.get("monto_capital") or 0.0)
            tna = float(d.get("tasa_nominal_anual") or 0.60)
            cant_cuotas = int(d.get("cantidad_cuotas") or 12)
            cuota_reg = float(d.get("cuota_registrada") or 0.0)
            monto_cuota = cuota_reg if cuota_reg > 0 else calcular_cuota_frances(monto_cap, tna, cant_cuotas)
            situacion_bcra = (
                1 if dias_mora <= 30 else (2 if dias_mora <= 90 else (3 if dias_mora <= 180 else (4 if dias_mora <= 360 else 5)))
            )
            d["dias_mora"] = dias_mora
            d["monto_cuota"] = monto_cuota
            d["tipo_titular"] = "EMPRESA" if d.get("empresa_id") else "INDIVIDUO"
            d["situacion_bcra"] = situacion_bcra
            d["cuota_actual"] = min(cant_cuotas, int(d.get("cuotas_pagas") or 0) + 1)
            resultado.append(d)
        return resultado
    finally:
        conn.close()


def _construir_respuesta_archivo(
    datos_dict: List[Dict[str, Any]],
    formato_limpio: str,
    nombre_base: str,
    nombre_hoja: str,
    titulo_pdf: str,
    subtitulo_pdf: str,
    cols_pdf: List[str],
    filas_pdf: List[List[Any]],
    kpis_pdf: Optional[Dict[str, Any]] = None,
) -> Response:
    """Empaqueta los datos en el formato binario o texto requerido con cabeceras HTTP."""
    if formato_limpio == "csv":
        contenido = exportar_a_csv(datos_dict)
        mime = "text/csv"
        fn = f"{nombre_base}.csv"
    elif formato_limpio in ("excel", "xlsx"):
        contenido = exportar_a_excel(
            datos=datos_dict,
            nombre_hoja=nombre_hoja,
            titulo_reporte=titulo_pdf,
            subtitulo=subtitulo_pdf,
            kpis=kpis_pdf,
        )
        mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        fn = f"{nombre_base}.xlsx"
    else:
        contenido = exportar_a_pdf(
            titulo=titulo_pdf,
            subtitulo=subtitulo_pdf,
            columnas=cols_pdf,
            filas=filas_pdf,
            kpis=kpis_pdf,
        )
        mime = "application/pdf"
        fn = f"{nombre_base}.pdf"

    return Response(
        content=contenido,
        media_type=mime,
        headers={"Content-Disposition": f"attachment; filename={fn}"},
    )


@router.get("/api/dashboard/usuarios")
def listar_usuarios_dashboard(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    tipo: Optional[str] = Query(None, description="INDIVIDUO o EMPRESA"),
    estado: Optional[str] = Query(None, description="ACTIVO, BAJA_SOLICITADA, etc."),
    busqueda: Optional[str] = Query(None, description="Búsqueda por DNI, CUIT, Nombre, Alias, Email"),
    orden: str = Query("recientes", description="recientes, antiguos, mayor_saldo, menor_saldo"),
):
    """Retorna la lista paginada y filtrada del Padrón Central de Clientes (Individuos y Empresas)."""
    offset = (page - 1) * limit
    conn = get_db_connection()
    try:
        usuarios = usuario_repo.obtener_lista_usuarios_banco(
            conn,
            tipo_cliente=tipo,
            estado=estado,
            busqueda=busqueda,
            orden=orden,
            limite=limit,
            offset=offset,
        )
        total = usuario_repo.contar_usuarios_banco(
            conn,
            tipo_cliente=tipo,
            estado=estado,
            busqueda=busqueda,
        )
        total_paginas = max(1, math.ceil(total / limit)) if limit > 0 else 1
        return {
            "usuarios": usuarios,
            "total": total,
            "pagina": page,
            "total_paginas": total_paginas,
            "limite": limit,
        }
    finally:
        conn.close()


@router.get("/api/dashboard/exportar")
@router.get("/api/dashboard/export/{formato_path}")
def exportar_reporte(
    formato_path: Optional[str] = None,
    tipo: Optional[str] = Query(None, description="balance, prestamos, plazos_fijos o flexibles"),
    modulo: Optional[str] = Query(None, description="Alias frontend para tipo de reporte"),
    formato: str = Query("pdf", description="pdf, excel o csv"),
    fecha_desde: Optional[str] = None,
    fecha_hasta: Optional[str] = None,
    fecha_inicio: Optional[str] = None,
    fecha_fin: Optional[str] = None,
    estado: Optional[str] = None,
):
    """Genera y descarga en streaming reportes oficiales en formato PDF, Excel o CSV."""
    f_desde = fecha_desde or fecha_inicio or "2020-01-01"
    f_hasta = fecha_hasta or fecha_fin or "2030-12-31"
    formato_limpio = (formato_path or formato or "pdf").lower().strip()
    modulo_objetivo = (modulo or tipo or "balance").upper().strip()

    conn = get_db_connection()
    try:
        if modulo_objetivo in ("BALANCE", "TESORERIA"):
            balances = balance_repo.obtener_historico_balances(conn, fecha_desde=f_desde, fecha_hasta=f_hasta)
            datos_dict = [
                {
                    "fecha_corte": b.fecha_corte,
                    "capital_propio": b.capital_propio_patrimonio,
                    "depositos_flexibles": b.total_depositos_flexibles,
                    "plazos_fijos": b.total_depositos_plazo_fijo,
                    "encaje_bcra": b.encaje_obligatorio_bcra,
                    "total_prestado": b.total_prestado_activo,
                    "cashflow_seguro": b.cashflow_seguro_prestable,
                }
                for b in balances
            ]
            cols = ["FECHA", "CAPITAL", "DEP. FLEX", "PLAZO FIJO", "ENCAJE", "CASHFLOW"]
            filas = [
                [
                    d["fecha_corte"],
                    f"${d['capital_propio']:,.0f}",
                    f"${d['depositos_flexibles']:,.0f}",
                    f"${d['plazos_fijos']:,.0f}",
                    f"${d['encaje_bcra']:,.0f}",
                    f"${d['cashflow_seguro']:,.0f}",
                ]
                for d in datos_dict
            ]
            ultimo = datos_dict[-1] if datos_dict else {}
            kpis = {
                "Capital": f"${ultimo.get('capital_propio', 0):,.0f}",
                "Encajes": f"${ultimo.get('encaje_bcra', 0):,.0f}",
                "Cashflow": f"${ultimo.get('cashflow_seguro', 0):,.0f}",
            }
            return _construir_respuesta_archivo(
                datos_dict=datos_dict,
                formato_limpio=formato_limpio,
                nombre_base=f"balance_patrimonial_{f_hasta}",
                nombre_hoja="Balance Diario",
                titulo_pdf="Evolución de Balance y Encajes BCRA",
                subtitulo_pdf=f"Período: {f_desde} al {f_hasta} — Banco del Valle",
                cols_pdf=cols,
                filas_pdf=filas,
                kpis_pdf=kpis,
            )

        if modulo_objetivo in ("PRESTAMOS", "CREDITOS"):
            prestamos = prestamo_repo.obtener_prestamos_con_detalle_rango(conn, f_desde, f_hasta)
            cols = ["TITULAR", "DOC", "CAPITAL", "TNA", "PLAZO", "ESTADO"]
            filas = [
                [
                    str(p.get("titular", ""))[:18],
                    str(p.get("documento_fiscal", "")),
                    f"${float(p.get('monto_capital', 0)):,.2f}",
                    f"{float(p.get('tasa_nominal_anual', 0)) * 100:.1f}%",
                    f"{p.get('cantidad_cuotas', 0)} m",
                    str(p.get("estado", "")),
                ]
                for p in prestamos
            ]
            return _construir_respuesta_archivo(
                datos_dict=prestamos,
                formato_limpio=formato_limpio,
                nombre_base=f"cartera_creditos_{f_hasta}",
                nombre_hoja="Cartera Creditos",
                titulo_pdf="Reporte Oficial de Cartera de Préstamos",
                subtitulo_pdf=f"Operaciones registradas del {f_desde} al {f_hasta}",
                cols_pdf=cols,
                filas_pdf=filas,
            )

        if modulo_objetivo in ("PLAZOS_FIJOS", "DEPOSITOS"):
            pfs = deposito_repo.listar_plazos_fijos_rango(conn, f_desde, f_hasta)
            cols = ["TITULAR", "DOC", "CAPITAL", "TNA", "VENCIMIENTO", "ESTADO"]
            filas = [
                [
                    str(pf.get("titular", ""))[:18],
                    str(pf.get("documento_fiscal", "")),
                    f"${float(pf.get('monto_depositado', 0)):,.2f}",
                    f"{float(pf.get('tasa_nominal_anual', 0)) * 100:.1f}%",
                    str(pf.get("fecha_vencimiento", "")),
                    str(pf.get("estado", "")),
                ]
                for pf in pfs
            ]
            return _construir_respuesta_archivo(
                datos_dict=pfs,
                formato_limpio=formato_limpio,
                nombre_base=f"plazos_fijos_{f_hasta}",
                nombre_hoja="Plazos Fijos",
                titulo_pdf="Reporte de Imposiciones a Plazo Fijo",
                subtitulo_pdf=f"Certificados del {f_desde} al {f_hasta} — Encaje 12% BCRA",
                cols_pdf=cols,
                filas_pdf=filas,
            )

        if modulo_objetivo in ("FLEXIBLES", "MOVIMIENTOS", "CUENTAS"):
            movs = movimiento_repo.listar_todos_movimientos_rango(conn, f_desde, f_hasta)
            cols = ["FECHA", "ALIAS", "OPERACIÓN", "MONTO", "SALDO POST."]
            filas = [
                [
                    str(m.get("fecha_hora", ""))[:16],
                    str(m.get("alias", ""))[:16],
                    str(m.get("tipo_movimiento", ""))[:18],
                    f"${float(m.get('monto', 0)):,.2f}",
                    f"${float(m.get('saldo_posterior', 0)):,.2f}",
                ]
                for m in movs
            ]
            return _construir_respuesta_archivo(
                datos_dict=movs,
                formato_limpio=formato_limpio,
                nombre_base=f"cuentas_flexibles_{f_hasta}",
                nombre_hoja="Cuentas Flexibles",
                titulo_pdf="Movimientos y Rendimientos de Cuentas Flexibles",
                subtitulo_pdf=f"Período: {f_desde} al {f_hasta} — Remuneración 28.5% TNA",
                cols_pdf=cols,
                filas_pdf=filas,
            )

        if modulo_objetivo in ("USUARIOS", "CLIENTES", "PADRON"):
            usuarios = usuario_repo.obtener_lista_usuarios_banco(
                conn,
                tipo_cliente=None if not estado or estado.upper() not in ("INDIVIDUO", "EMPRESA") else estado,
                estado=None if estado in ("INDIVIDUO", "EMPRESA") else estado,
                orden="recientes",
                limite=5000,
                offset=0,
            )
            cols = ["TITULAR", "DOC FISCAL", "SEGMENTO", "SUBTIPO / ACTIVIDAD", "ESTADO", "SALDO", "PRESTAMOS"]
            filas = [
                [
                    str(u.get("nombre_titular", ""))[:25],
                    str(u.get("identificador_fiscal", "")),
                    str(u.get("tipo_cliente", "")),
                    str(u.get("subtipo_actividad", ""))[:25],
                    str(u.get("estado_cliente", "")),
                    f"${float(u.get('saldo_cuenta', 0)):,.2f}",
                    f"{u.get('prestamos_activos', 0)} Activo(s) (${float(u.get('monto_prestamos', 0)):,.0f})" if u.get('prestamos_activos', 0) > 0 else "Sin préstamos",
                ]
                for u in usuarios
            ]
            return _construir_respuesta_archivo(
                datos_dict=usuarios,
                formato_limpio=formato_limpio,
                nombre_base=f"padron_clientes_{f_hasta}",
                nombre_hoja="Padrón Clientes",
                titulo_pdf="Padrón Oficial de Clientes & Cuentas — Banco del Valle",
                subtitulo_pdf=f"Generado al {f_hasta} — Titulares Individuos y Empresas",
                cols_pdf=cols,
                filas_pdf=filas,
            )

        raise HTTPException(status_code=400, detail=f"Tipo de reporte '{modulo_objetivo}' no soportado.")
    finally:
        conn.close()
