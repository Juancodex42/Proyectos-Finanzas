import os
import sys
import sqlite3
import pandas as pd

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'webapp', 'backend'))
COMPAT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'webapp', 'backend', 'compat'))
for _p in (COMPAT_DIR, BACKEND_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

conn = sqlite3.connect(os.path.join(BACKEND_DIR, 'transactions.db'))

query = """
    SELECT fecha, exchange, tipo_operacion, moneda, monto_compra_cripto, monto_venta_cripto, monto_ars,
           CASE WHEN monto_compra_cripto > 0 THEN monto_ars / monto_compra_cripto 
                WHEN monto_venta_cripto > 0 THEN monto_ars / monto_venta_cripto ELSE 0 END as precio_unitario
    FROM transactions
    WHERE tipo_operacion IN ('Compra', 'Venta')
    ORDER BY fecha ASC
"""
df = pd.read_sql_query(query, conn)

print("=== SPREADS REALES POR AÑO Y MONEDA ===")
for yr in ['2024', '2025', '2026']:
    df_yr = df[df['fecha'].str.startswith(yr)]
    for m in ['USDT', 'USDC']:
        sub = df_yr[df_yr['moneda'] == m]
        b = sub[sub['tipo_operacion'] == 'Compra']
        s = sub[sub['tipo_operacion'] == 'Venta']
        if not b.empty and not s.empty:
            vol_b = b['monto_compra_cripto'].sum()
            vol_s = s['monto_venta_cripto'].sum()
            avg_p_b = b['monto_ars'].sum() / vol_b if vol_b > 0 else 0
            avg_p_s = s['monto_ars'].sum() / vol_s if vol_s > 0 else 0
            spread = ((avg_p_s - avg_p_b) / avg_p_b) * 100 if avg_p_b > 0 else 0
            matched_vol = min(vol_b, vol_s)
            real_pnl_ars = matched_vol * (avg_p_s - avg_p_b)
            real_pnl_usd = real_pnl_ars / avg_p_b if avg_p_b > 0 else 0
            print(f"Año {yr} - {m}:")
            print(f"  Volumen operado match: {matched_vol:,.2f} {m}")
            print(f"  Precio compra promedio: ${avg_p_b:,.2f} | Precio venta promedio: ${avg_p_s:,.2f}")
            print(f"  Spread real: {spread:.2f}%")
            print(f"  Ganancia REAL estimada en pesos: ${real_pnl_ars:,.2f} ARS")
            print(f"  Ganancia REAL estimada en dólares: ${real_pnl_usd:,.2f} USD")
            print("-" * 50)
