"""
Motor de cálculo tributario argentino para criptoactivos (Ganancias e IIBB).
Fórmulas matemáticas puras sin efectos colaterales ni dependencias externas.
Referencia de diseño: docs/modelo_matematico_fiscal.md
"""

from typing import Dict, Any


def calculate_cedular_tax(
    ventas_totales_ars: float,
    costo_base_fifo_ars: float,
    gastos_deducibles_ars: float = 0.0,
    deduccion_especial_ars: float = 0.0,
    alicuota: float = 0.15
) -> Dict[str, Any]:
    """
    Calcula el Impuesto a las Ganancias (Régimen Cedular, Art. 95) para enajenación de monedas digitales.
    
    Retorna un desglose determinista con:
    - resultado_bruto
    - renta_neta
    - base_imponible
    - impuesto_determinado
    """
    v_tot = max(0.0, float(ventas_totales_ars))
    c_fifo = max(0.0, float(costo_base_fifo_ars))
    g_ded = max(0.0, float(gastos_deducibles_ars))
    d_esp = max(0.0, float(deduccion_especial_ars))

    resultado_bruto = v_tot - c_fifo
    renta_neta = resultado_bruto - g_ded
    base_imponible = max(0.0, renta_neta - d_esp)
    impuesto_determinado = base_imponible * float(alicuota)

    return {
        "ventas_totales_ars": round(v_tot, 2),
        "costo_base_fifo_ars": round(c_fifo, 2),
        "resultado_bruto_ars": round(resultado_bruto, 2),
        "gastos_deducibles_ars": round(g_ded, 2),
        "renta_neta_ars": round(renta_neta, 2),
        "deduccion_especial_ars": round(d_esp, 2),
        "base_imponible_ars": round(base_imponible, 2),
        "alicuota": alicuota,
        "impuesto_determinado_ars": round(impuesto_determinado, 2)
    }


def calculate_iibb_tax(
    ingresos_brutos_ars: float,
    alicuota: float = 0.03
) -> Dict[str, Any]:
    """
    Calcula el Impuesto sobre los Ingresos Brutos (IIBB) provincial sobre volumen facturado/operado.
    """
    ib_tot = max(0.0, float(ingresos_brutos_ars))
    impuesto = ib_tot * float(alicuota)

    return {
        "ingresos_brutos_ars": round(ib_tot, 2),
        "alicuota": alicuota,
        "impuesto_iibb_ars": round(impuesto, 2)
    }
