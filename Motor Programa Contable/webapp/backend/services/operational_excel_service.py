"""
Generador del Libro Operativo con fórmulas vivas de inventario y caja.
Construye el libro Excel CPN sincronizado con el modelo matemático patrimonial.
Referencia de diseño: docs/modelo_matematico_fiscal.md
"""
import io
import datetime
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from typing import List, Dict, Any, Optional

from models.operational_models import (
    TIPO_COMPRA, TIPO_VENTA, TIPO_INYECCION, TIPO_RETIRO,
    TIPO_PRESTAMO_RECIBIDO, TIPO_DEVOLUCION_PRESTAMO, TIPO_DEVOLUCION_PRESTAMO_USDT,
    TIPO_BLOQUEO_BRONCE, TIPO_BLOQUEO_PLATA
)

def generate_operational_excel(
    transactions: List[Dict[str, Any]],
    options: Optional[Dict[str, Any]] = None
) -> io.BytesIO:
    """Generates the dual-sheet Operational Excel workbook with living formulas."""
    try:
        from services.bank_persistence_service import get_operational_settings
        saved_defaults = get_operational_settings()
    except Exception:
        saved_defaults = {}

    merged_opts = {**saved_defaults, **(options or {})}
    init_usd = float(merged_opts.get('existencia_inicial_usd', 0.0) or 0.0)
    init_ars = float(merged_opts.get('existencia_inicial_ars', 0.0) or 0.0)
    garantia_total_usdt = float(merged_opts.get('garantia_total_usdt', 0.0) or 0.0)
    cierre_rate = float(merged_opts.get('cotizacion_cierre_usdt', 0.0) or 0.0)
    saldo_bancos_final = float(merged_opts.get('saldo_bancos_final_ars', 0.0) or 0.0)

    wb = openpyxl.Workbook()
    # Sheet 1: Resumen Final
    ws_resumen = wb.active
    ws_resumen.title = "Resumen Final"
    ws_resumen.views.sheetView[0].showGridLines = True

    # Sheet 2: Historial Consolidado
    ws_historial = wb.create_sheet(title="Historial Consolidado")
    ws_historial.views.sheetView[0].showGridLines = True

    # ----------------------------------------------------
    # BUILD SHEET: Historial Consolidado
    # ----------------------------------------------------
    ws_historial.cell(row=1, column=1, value="HISTORIAL CONSOLIDADO + STOCK — todas las operaciones, orden cronológico").font = Font(bold=True, size=13, color="1E293B")
    ws_historial.cell(row=3, column=1, value="SUPUESTOS (editables):").font = Font(bold=True, size=10, color="64748B")
    
    ws_historial.cell(row=4, column=1, value="Existencia inicial USD:").font = Font(bold=True)
    c_init_usd = ws_historial.cell(row=4, column=2, value=init_usd)
    c_init_usd.number_format = '#,##0.00'
    c_init_usd.font = Font(bold=True, color="0D9488")
    
    ws_historial.cell(row=4, column=3, value="Existencia inicial ARS:").font = Font(bold=True)
    c_init_ars = ws_historial.cell(row=4, column=4, value=init_ars)
    c_init_ars.number_format = '$#,##0.00'
    c_init_ars.font = Font(bold=True, color="0D9488")

    ws_historial.cell(row=6, column=1, value="Nota: Los bloqueos de comerciante verificado son filas explícitas en el historial. Las columnas de Stock se calculan con fórmulas vivas.").font = Font(italic=True, size=9, color="64748B")
    
    headers = [
        'Exchange', 'Fecha', 'Tipo', 'Activo', 'Cantidad', 'Precio', 'Total ARS', 
        'Contraparte / Nota', 'Stock USD', 'Stock ARS', '', 'Cant. firmada (aux)', 
        'ARS firmado (aux)', 'Stock bruto USD (aux)', 'Bloqueo a la fecha (aux)'
    ]
    
    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=10)
    
    for c_idx, h_text in enumerate(headers, 1):
        if h_text:
            cell = ws_historial.cell(row=9, column=c_idx, value=h_text)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal='center', vertical='center')

    # Sort transactions chronologically
    sorted_txs = sorted(transactions, key=lambda x: str(x.get('fecha') or x.get('Fecha') or ''))
    start_row = 10
    
    thin_border = Border(
        left=Side(style='thin', color='E2E8F0'), right=Side(style='thin', color='E2E8F0'),
        top=Side(style='thin', color='E2E8F0'), bottom=Side(style='thin', color='E2E8F0')
    )

    for idx, tx in enumerate(sorted_txs):
        r = start_row + idx
        ex = str(tx.get('exchange') or tx.get('Exchange') or 'Binance P2P').upper()
        f_val = tx.get('fecha') or tx.get('Fecha')
        t_tipo_raw = str(tx.get('tipo_operacion') or tx.get('Tipo de Operación') or tx.get('tipo') or 'Compra').strip()
        t_low = t_tipo_raw.lower()
        is_garantia = (
            t_tipo_raw in (TIPO_BLOQUEO_BRONCE, TIPO_BLOQUEO_PLATA) or
            "bloqueo comerciante" in t_low or "garant" in t_low or "colateral" in t_low
        )

        # Normalize operational types to exact strings referenced in Excel formulas
        if is_garantia:
            if "plata" in t_low:
                t_tipo = TIPO_BLOQUEO_PLATA
            else:
                t_tipo = TIPO_BLOQUEO_BRONCE
        elif "inyecci" in t_low:
            t_tipo = TIPO_INYECCION
        elif "retiro" in t_low and any(k in t_low for k in ('personal', 'extern', 'propia', 'cuenta')):
            t_tipo = TIPO_RETIRO
        elif "prestamo" in t_low or "préstamo" in t_low:
            if "devoluci" in t_low or "pago" in t_low:
                if "usdt" in t_low or "cripto" in t_low:
                    t_tipo = TIPO_DEVOLUCION_PRESTAMO_USDT
                else:
                    t_tipo = TIPO_DEVOLUCION_PRESTAMO
            else:
                t_tipo = TIPO_PRESTAMO_RECIBIDO
        elif any(k in t_low for k in ('rendimiento', 'mercadofondo', 'lemon earn', 'interes', 'interés', 'fci')):
            t_tipo = "Rendimiento financiero"
        elif any(k in t_low for k in ('ley 25', '25413', 'impuesto deb', 'impuesto cre', 'mantenimiento de cuenta', 'cargo bancario')):
            t_tipo = "Gasto / Comisión operativa de arbitraje"
        elif "gasto personal" in t_low:
            t_tipo = "Gasto personal"
        elif any(k in t_low for k in ('pase interno', 'propio', 'transferencia interna')):
            t_tipo = "Pase interno / Propio"
        elif any(k in t_low for k in ('compra', 'buy')):
            t_tipo = TIPO_COMPRA
        elif any(k in t_low for k in ('venta', 'sell', 'consumo', 'pago')):
            t_tipo = TIPO_VENTA
        elif any(k in t_low for k in ('ingreso', 'deposito', 'depósito', 'deposit', 'recepcion')):
            t_tipo = "Ingreso Cripto"
        elif any(k in t_low for k in ('comisi', 'fee')):
            t_tipo = "Comisión"
        else:
            t_tipo = t_tipo_raw

        moneda = str(tx.get('moneda') or tx.get('Moneda') or tx.get('Activo') or 'USDT').upper()
        
        cant = float(tx.get('monto_compra_cripto') or tx.get('Monto Compra (Cripto)') or tx.get('monto_venta_cripto') or tx.get('Monto Venta (Cripto)') or tx.get('Cantidad') or 0.0)
        precio = float(tx.get('cotizacion_compra') or tx.get('Cotización Compra') or tx.get('cotizacion_venta') or tx.get('Cotización Venta') or tx.get('Precio') or 0.0)
        tot_ars = float(tx.get('monto_ars') or tx.get('Monto ARS') or tx.get('Total ARS') or 0.0)
        nota = str(tx.get('comentarios') or tx.get('Comentarios') or tx.get('Contraparte / Nota') or '')

        ws_historial.cell(row=r, column=1, value=ex).alignment = Alignment(horizontal='center')
        ws_historial.cell(row=r, column=2, value=str(f_val)[:19]).alignment = Alignment(horizontal='center')
        ws_historial.cell(row=r, column=3, value=t_tipo).alignment = Alignment(horizontal='center')
        ws_historial.cell(row=r, column=4, value=moneda).alignment = Alignment(horizontal='center')
        
        c_cant = ws_historial.cell(row=r, column=5, value=cant)
        c_cant.number_format = '#,##0.00'
        
        c_prec = ws_historial.cell(row=r, column=6, value=precio if precio > 0 else "")
        if precio > 0: c_prec.number_format = '$#,##0.00'
        
        c_ars = ws_historial.cell(row=r, column=7, value=tot_ars if tot_ars > 0 else "")
        if tot_ars > 0: c_ars.number_format = '$#,##0.00'
        
        ws_historial.cell(row=r, column=8, value=nota)

        # Living formulas:
        # Col L: Cant. firmada (aux) — excluye garantías para no duplicarlas con la fila 10 del Resumen Final
        if is_garantia:
            ws_historial.cell(row=r, column=12, value=0)
        else:
            ws_historial.cell(row=r, column=12, value=f'=IF(C{r}="Compra",E{r},IF(C{r}="Ingreso Cripto",E{r},IF(C{r}="Venta",-E{r},IF(C{r}="Devolución préstamo USDT",-E{r},IF(AND(C{r}="Préstamo recibido",D{r}<>"ARS"),E{r},0)))))')
        
        # Col M: ARS firmado (aux)
        ws_historial.cell(row=r, column=13, value=f'=IF(C{r}="Compra",IF(G{r}="",0,-G{r}),IF(C{r}="Venta",G{r},IF(AND(C{r}="Préstamo recibido",D{r}="ARS"),G{r},IF(AND(C{r}="Devolución préstamo",D{r}="ARS"),-G{r},IF(C{r}="Inyección transitoria de fondos personales",G{r},IF(C{r}="Retiro a cuenta personal",-G{r},IF(C{r}="Gasto / Comisión operativa de arbitraje",-G{r},IF(C{r}="Rendimiento financiero",G{r},0))))))))')
        
        # Col N: Stock bruto USD (aux)
        if r == start_row:
            ws_historial.cell(row=r, column=14, value=f'=$B$4+L{r}')
        else:
            ws_historial.cell(row=r, column=14, value=f'=N{r-1}+L{r}')
            
        # Col O: Bloqueo a la fecha (acumulado)
        if r == start_row:
            ws_historial.cell(row=r, column=15, value=f'=ABS(E{r})' if is_garantia else 0)
        else:
            ws_historial.cell(row=r, column=15, value=f'=O{r-1}+ABS(E{r})' if is_garantia else f'=O{r-1}')
        
        # Col I: Stock USD neto
        c_stock_usd = ws_historial.cell(row=r, column=9, value=f'=N{r}-O{r}')
        c_stock_usd.number_format = '#,##0.00'
        c_stock_usd.font = Font(bold=True)
        
        # Col J: Stock ARS
        if r == start_row:
            c_stock_ars = ws_historial.cell(row=r, column=10, value=f'=$D$4+M{r}')
        else:
            c_stock_ars = ws_historial.cell(row=r, column=10, value=f'=J{r-1}+M{r}')
        c_stock_ars.number_format = '$#,##0.00'
        c_stock_ars.font = Font(bold=True)

        for col_i in range(1, 16):
            if headers[col_i-1]:
                ws_historial.cell(row=r, column=col_i).border = thin_border

    last_row = max(start_row, start_row + len(sorted_txs) - 1)

    # ----------------------------------------------------
    # BUILD SHEET: Resumen Final (Patrimonial & Trading)
    # ----------------------------------------------------
    ws_resumen.cell(row=1, column=2, value="AUDITORÍA INTEGRAL Y CONCILIACIÓN OPERATIVA").font = Font(bold=True, size=14, color="0F172A")
    ws_resumen.cell(row=2, column=2, value="Reporte generado con Stock Continuo y Ecuación Patrimonial al Cierre").font = Font(size=10, color="64748B")
    
    ws_resumen.cell(row=4, column=2, value="1. DETERMINACIÓN POR MÉTODO PATRIMONIAL").font = Font(bold=True, size=11, color="1E293B")
    ws_resumen.cell(row=5, column=2, value="Ganancia Neta = Activos Finales Reales (A) − Capital Neto Invertido Financiado (B)").font = Font(italic=True, size=9, color="64748B")

    r_headers = ['Concepto Patrimonial', 'Monto (ARS)', 'Base / Unidad', 'Observación Auditoría']
    for c_i, h_t in enumerate(r_headers, 2):
        c = ws_resumen.cell(row=7, column=c_i, value=h_t)
        c.fill = PatternFill(start_color="334155", end_color="334155", fill_type="solid")
        c.font = Font(bold=True, color="FFFFFF")

    rows_patrimonio = [
        (8, "Saldo Real en Cuentas Fintech/Bancos al Cierre", saldo_bancos_final, "$#,##0.00", "ARS", "Extractos oficiales conciliados"),
        (9, "Stock Cripto Libre en Mano (Exchange)", f"='Historial Consolidado'!I{last_row}*{cierre_rate}", "$#,##0.00", f"USDT @ ${cierre_rate:,.2f}", "Disponible para operar"),
        (10, "Stock Cripto Bloqueado en Garantía (Merchant)", garantia_total_usdt * cierre_rate, "$#,##0.00", f"{garantia_total_usdt:,.0f} USDT @ ${cierre_rate:,.2f}", "Colateral Comerciante Verificado"),
        (11, "TOTAL ACTIVOS FINALES REALES AL CIERRE (A)", "=SUM(C8:C10)", "$#,##0.00", "ARS", "Total Patrimonio Activo"),
        (12, "Existencia Inicial asignada", init_ars, "$#,##0.00", "ARS", "Capital inicial base"),
        (13, "(+) Inyecciones Transitorias de Capital", f"=SUMIF('Historial Consolidado'!C10:C{last_row}, \"Inyección transitoria de fondos personales\", 'Historial Consolidado'!G10:G{last_row})", "$#,##0.00", "ARS", "Fondeos desde cuenta personal externa"),
        (14, "(−) Retiros Personales / Gastos de Vida", f"=-SUMIF('Historial Consolidado'!C10:C{last_row}, \"Retiro a cuenta personal\", 'Historial Consolidado'!G10:G{last_row})", "$#,##0.00", "ARS", "Retiros a cuenta personal y gastos comunes"),
        (15, "(+) Préstamos de Terceros recibidos", f"=SUMIF('Historial Consolidado'!C10:C{last_row}, \"Préstamo recibido\", 'Historial Consolidado'!G10:G{last_row})", "$#,##0.00", "ARS", "Financiamiento transitorio"),
        (16, "(−) Devolución Préstamos en pesos", f"=-SUMIF('Historial Consolidado'!C10:C{last_row}, \"Devolución préstamo\", 'Historial Consolidado'!G10:G{last_row})", "$#,##0.00", "ARS", "Obligaciones saldadas"),
        (17, "TOTAL CAPITAL NETO INVERTIDO FINANCIADO (B)", "=C12+C13+C14+C15+C16", "$#,##0.00", "ARS", "Capital Puesto en Juego"),
        (18, "(=) GANANCIA PATRIMONIAL DEL PERÍODO (A − B)", "=C11-C17", "$#,##0.00", "ARS", "Resultado Neto Real"),
        (20, "Gastos / Impuestos Bancarios del Arbitraje (Deducibles)", f"=SUMIF('Historial Consolidado'!C10:C{last_row}, \"Gasto / Comisión operativa de arbitraje\", 'Historial Consolidado'!G10:G{last_row})", "$#,##0.00", "ARS", "Ley 25.413, Mantenimiento y cargos de cuenta"),
        (21, "Rendimientos Financieros / FCI en Cuentas Operativas", f"=SUMIF('Historial Consolidado'!C10:C{last_row}, \"Rendimiento financiero\", 'Historial Consolidado'!G10:G{last_row})", "$#,##0.00", "ARS", "Intereses generados por saldos en tránsito"),
        (22, "Total Devolución Préstamo USDT (ARS)", f"=SUMIF('Historial Consolidado'!C10:C{last_row}, \"{TIPO_DEVOLUCION_PRESTAMO_USDT}\", 'Historial Consolidado'!G10:G{last_row})", "$#,##0.00", "ARS", "Obligaciones saldadas en cripto")
    ]

    for r_num, concepto, val, n_fmt, unit, obs in rows_patrimonio:
        ws_resumen.cell(row=r_num, column=2, value=concepto)
        c_val = ws_resumen.cell(row=r_num, column=3, value=val)
        c_val.number_format = n_fmt
        ws_resumen.cell(row=r_num, column=4, value=unit).alignment = Alignment(horizontal='center')
        ws_resumen.cell(row=r_num, column=5, value=obs)
        if r_num in [11, 17, 18]:
            for c_i in range(2, 6):
                cell_kpi = ws_resumen.cell(row=r_num, column=c_i)
                cell_kpi.font = Font(bold=True)
                if r_num == 18:
                    cell_kpi.fill = PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid")

    # Auto-adjust column widths
    for ws in [ws_resumen, ws_historial]:
        for col in ws.columns:
            max_len = 0
            col_letter = col[0].column_letter
            for cell in col:
                val_str = str(cell.value or '')
                if not val_str.startswith('='):
                    max_len = max(max_len, len(val_str))
            ws.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 48)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
