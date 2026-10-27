import os
import sys
import sqlite3

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'webapp', 'backend'))
COMPAT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'webapp', 'backend', 'compat'))
for _p in (COMPAT_DIR, BACKEND_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from services.fifo_service import recalculate_fifo_costs_db

conn = sqlite3.connect(os.path.join(BACKEND_DIR, 'transactions.db'))
c = conn.cursor()

print("=== PERIODO DE OPERACIONES DE USDC ===")
c.execute("SELECT MIN(fecha), MAX(fecha), COUNT(*) FROM transactions WHERE moneda = 'USDC'")
min_f, max_f, cnt = c.fetchone()
print(f"USDC operado desde: {min_f} hasta: {max_f} (Total {cnt} operaciones)")

print("\n=== GANANCIA DE LAS CERTIFICACIONES CPN EN ARS Y USD APROX ===")
# Approximate USD rate for each period
cert_rates = {
    1: 450.0,   # Nov 2022 - Jun 2023 (~$450 ARS/USD)
    2: 730.0,   # Jun 2023 - Sep 2023 (~$730 ARS/USD)
    3: 950.0,   # Sep 2023 - Ene 2024 (~$950 ARS/USD)
    4: 1050.0,  # Ene 2024 - May 2024 (~$1.050 ARS/USD)
    5: 1350.0,  # May 2024 - Sep 2024 (~$1.350 ARS/USD)
    6: 1200.0,  # Sep 2024 - Oct 2024 (~$1.200 ARS/USD)
    7: 1180.0,  # Nov 2024 - Abr 2025 (~$1.180 ARS/USD)
}

c.execute("""
    SELECT id, title, start_date, end_date, certified_pnl_ars, certified_sales_ars, certified_buys_ars
    FROM certifications
    ORDER BY start_date ASC
""")
tot_pnl_ars = 0
tot_pnl_usd = 0
for r in c.fetchall():
    cid = r[0]
    pnl_ars = r[4] or 0
    tot_pnl_ars += pnl_ars
    rate = cert_rates.get(cid, 1000.0)
    pnl_usd = pnl_ars / rate
    tot_pnl_usd += pnl_usd
    print(f"Cert {cid} ({r[2][:10]} a {r[3][:10]}): PnL ARS = ${pnl_ars:,.2f}  |  TC aprox: ${rate:.0f}  ->  PnL USD = ${pnl_usd:,.2f} USD")

print(f"\nTotal Ganancia Neta Certificada (2022 a 2025): ${tot_pnl_ars:,.2f} ARS  (~ ${tot_pnl_usd:,.2f} USD)")

print("\n=== TOTALES COMPRAS Y VENTAS POR AÑO (ARS Y USD ESTIMADO) ===")
year_rates = {
    '2021': 180.0,
    '2022': 310.0,
    '2023': 700.0,
    '2024': 1150.0,
    '2025': 1250.0,
    '2026': 1350.0
}

c.execute("""
    SELECT SUBSTR(fecha, 1, 4) as anio,
           ROUND(SUM(CASE WHEN tipo_operacion = 'Venta' THEN monto_ars ELSE 0 END), 2) as ventas_ars,
           ROUND(SUM(CASE WHEN tipo_operacion = 'Compra' THEN monto_ars ELSE 0 END), 2) as compras_ars
    FROM transactions
    WHERE tipo_operacion IN ('Compra', 'Venta')
    GROUP BY anio
    ORDER BY anio ASC
""")
tot_ganancia_usd_all = 0
for r in c.fetchall():
    anio, v_ars, c_ars = r
    diff_ars = v_ars - c_ars
    tc = year_rates.get(anio, 1000.0)
    diff_usd = diff_ars / tc
    tot_ganancia_usd_all += diff_usd
    print(f"Año {anio}: Ventas=${v_ars:,.2f} ARS | Compras=${c_ars:,.2f} ARS | Margen=${diff_ars:,.2f} ARS (~ ${diff_usd:,.2f} USD @ TC ${tc:.0f})")

print(f"\nMargen Bruto Total Acumulado Estimado: ~ ${tot_ganancia_usd_all:,.2f} USD")
