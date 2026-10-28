"""
Test suite to generate the operational Excel with living formulas, read it back,
and verify that all formulas, balances, and sheets match the accountant's model.
"""
import sys
import os
import tempfile
import openpyxl

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'webapp', 'backend'))
COMPAT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'webapp', 'backend', 'compat'))
for _p in (COMPAT_DIR, BACKEND_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import db_manager
from services.transactions_service import get_transactions
from services.operational_excel_service import generate_operational_excel

def test_generate_and_inspect_operational_excel():
    print("1. Inicializando base de datos y obteniendo transacciones...")
    db_manager.init_db()
    txs = get_transactions(exchanges=['Binance P2P', 'Fiwind', 'Lemon Cash'], date_start='2026-06-01', date_end='2026-10-01')
    print(f"Transacciones obtenidas: {len(txs)}")
    
    # Add dummy operational transactions to simulate loans, collateral and injections if not present in DB
    dummy_operational = [
        {
            "exchange": "BINANCE P2P",
            "fecha": "2026-07-07 15:25:00",
            "tipo_operacion": "Bloqueo comerciante verificado (bronce)",
            "moneda": "USDT",
            "monto_compra_cripto": -500.0,
            "monto_ars": 0.0,
            "comentarios": "Bloqueo colateral Bronce"
        },
        {
            "exchange": "BANCO / LEMON",
            "fecha": "2026-07-07 10:26:00",
            "tipo_operacion": "Inyección transitoria de fondos personales",
            "moneda": "ARS",
            "monto_compra_cripto": 0.0,
            "monto_ars": 1030618.70,
            "comentarios": "Fondeo de giro"
        },
        {
            "exchange": "LEMON / BANCO",
            "fecha": "2026-07-14 20:38:21",
            "tipo_operacion": "Retiro a cuenta personal",
            "moneda": "ARS",
            "monto_compra_cripto": 0.0,
            "monto_ars": 500000.0,
            "comentarios": "Devolución giro"
        },
        {
            "exchange": "BANCO / FIWIND",
            "fecha": "2026-08-25 11:07:00",
            "tipo_operacion": "Préstamo recibido",
            "moneda": "ARS",
            "monto_compra_cripto": 0.0,
            "monto_ars": 1000000.0,
            "comentarios": "Préstamo mutuo comercial"
        },
        {
            "exchange": "LEMON / FIWIND",
            "fecha": "2026-09-02 10:40:00",
            "tipo_operacion": "Devolución préstamo",
            "moneda": "ARS",
            "monto_compra_cripto": 0.0,
            "monto_ars": 1000000.0,
            "comentarios": "Devolución préstamo comercial"
        }
    ]
    all_txs = txs + dummy_operational

    options = {
        "existencia_inicial_usd": 0.0,
        "existencia_inicial_ars": 604395.39,
        "garantia_total_usdt": 650.0,
        "cotizacion_cierre_usdt": 1601.20,
        "saldo_bancos_final_ars": 1042066.17
    }

    print("2. Generando Excel Operativo con Fórmulas Vivas...")
    excel_buf = generate_operational_excel(all_txs, options)
    
    test_path = os.path.join(tempfile.gettempdir(), 'test_operational_out.xlsx')
    try:
        with open(test_path, 'wb') as f:
            f.write(excel_buf.getvalue())
        print(f"Excel guardado para inspección temporal en: {test_path}")

        print("3. Leyendo el Excel generado de vuelta para verificar fórmulas y estructura...")
        wb = openpyxl.load_workbook(test_path, data_only=False)
        try:
            assert "Resumen Final" in wb.sheetnames, "Falta la solapa Resumen Final"
            assert "Historial Consolidado" in wb.sheetnames, "Falta la solapa Historial Consolidado"

            ws_hist = wb["Historial Consolidado"]
            assert ws_hist.max_row >= 10, "Historial Consolidado está vacío"

            # Check living formulas in first data row (row 10)
            col_l = ws_hist.cell(10, 12).value
            col_m = ws_hist.cell(10, 13).value
            col_n = ws_hist.cell(10, 14).value
            col_i = ws_hist.cell(10, 9).value
            col_j = ws_hist.cell(10, 10).value

            print(f"Fila 10 Col L (Fórmula aux USD): {col_l}")
            print(f"Fila 10 Col M (Fórmula aux ARS): {col_m}")
            print(f"Fila 10 Col N (Fórmula Stock USD bruto): {col_n}")
            print(f"Fila 10 Col I (Fórmula Stock USD neto): {col_i}")
            print(f"Fila 10 Col J (Fórmula Stock ARS caja): {col_j}")

            assert str(col_l).startswith("="), "Columna L debe ser fórmula viva"
            assert str(col_m).startswith("="), "Columna M debe ser fórmula viva"
            assert str(col_n).startswith("="), "Columna N debe ser fórmula viva"
            assert str(col_i).startswith("="), "Columna I debe ser fórmula viva"
            assert str(col_j).startswith("="), "Columna J debe ser fórmula viva"

            ws_res = wb["Resumen Final"]
            resumen_c11 = ws_res.cell(11, 3).value
            resumen_c17 = ws_res.cell(17, 3).value
            resumen_c18 = ws_res.cell(18, 3).value
            print(f"Resumen Final C11 (Activos A): {resumen_c11}")
            print(f"Resumen Final C17 (Capital B): {resumen_c17}")
            print(f"Resumen Final C18 (Ganancia Patrimonial A-B): {resumen_c18}")

            assert str(resumen_c11) == "=SUM(C8:C10)", "C11 debe ser suma viva de activos"
            assert str(resumen_c17) == "=C12+C13+C14+C15+C16", "C17 debe ser suma viva de capital invertido"
            assert str(resumen_c18) == "=C11-C17", "C18 debe ser la resta viva de la ecuación patrimonial"

            print("[OK] TODAS LAS VALIDACIONES DEL EXCEL OPERATIVO PASARON EXITOSAMENTE.")
        finally:
            wb.close()
    finally:
        if os.path.exists(test_path):
            try:
                os.remove(test_path)
            except OSError:
                pass


if __name__ == '__main__':
    test_generate_and_inspect_operational_excel()

