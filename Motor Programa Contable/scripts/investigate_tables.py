import sqlite3

conn = sqlite3.connect('webapp/backend/transactions.db')
c = conn.cursor()

c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in c.fetchall()]
print("Tablas en transactions.db:", tables)

for t in tables:
    c.execute(f"SELECT COUNT(*) FROM {t}")
    cnt = c.fetchone()[0]
    print(f"  * {t}: {cnt} registros")

print("\n--- Desglose de transacciones por fuente ---")
c.execute("SELECT source, count(*) FROM transactions GROUP BY source")
for r in c.fetchall():
    print(f"  Fuente {r[0]}: {r[1]} filas")

print("\n--- Desglose por certification_id ---")
c.execute("SELECT certification_id, count(*) FROM transactions WHERE source='CERTIFICATION' GROUP BY certification_id")
for r in c.fetchall():
    print(f"  Certificación #{r[0]}: {r[1]} transacciones")

print("\n--- Desglose por Exchange ---")
c.execute("SELECT exchange, count(*) FROM transactions GROUP BY exchange ORDER BY count(*) DESC")
for r in c.fetchall():
    print(f"  {r[0]}: {r[1]} transacciones")

conn.close()
