import sqlite3
import sys
import os

sys.path.insert(0, os.path.abspath('webapp/backend'))
sys.path.insert(0, os.path.abspath('webapp/backend/compat'))

from models.transaction_models import compute_canonical_tx_hash

conn = sqlite3.connect('webapp/backend/transactions.db')
c = conn.cursor()

corrections = {
    28165: '2024-12-17 00:00:00',
    28164: '2024-12-24 00:00:00',
    28163: '2025-04-09 00:00:00',
    28162: '2025-02-09 00:00:00'
}

for tx_id, new_fecha in corrections.items():
    c.execute("SELECT id, fecha, exchange, tipo_operacion, moneda, monto_compra_cripto, monto_venta_cripto, monto_ars, comentarios FROM transactions WHERE id = ?", (tx_id,))
    row = c.fetchone()
    if not row:
        print(f"TX {tx_id} not found, skipping.")
        continue
    _, old_fecha, ex, op, coin, m_compra, m_venta, m_ars, com = row
    
    new_hash = compute_canonical_tx_hash(
        new_fecha, ex, op, coin,
        m_compra, m_venta, m_ars, com
    )
    
    # Check if a transaction with new_hash already exists
    c.execute("SELECT id FROM transactions WHERE tx_hash = ? AND id != ?", (new_hash, tx_id))
    existing = c.fetchone()
    if existing:
        print(f"  TX {tx_id} ({old_fecha}) is a duplicate of existing TX {existing[0]}. Deleting {tx_id}...")
        c.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))
    else:
        print(f"  Updating TX {tx_id}: {old_fecha} -> {new_fecha} (hash: {new_hash[:12]}...)")
        c.execute("UPDATE transactions SET fecha = ?, tx_hash = ? WHERE id = ?", (new_fecha, new_hash, tx_id))

conn.commit()

# Final audit: any transactions with fecha > 2030?
c.execute("SELECT COUNT(*) FROM transactions WHERE fecha > '2030'")
remaining_future = c.fetchone()[0]
print(f"\nAudit complete. Remaining transactions with fecha > 2030: {remaining_future}")

conn.close()
