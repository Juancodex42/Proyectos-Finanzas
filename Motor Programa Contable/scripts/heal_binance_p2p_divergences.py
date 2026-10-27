import sqlite3
import os
import sys

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'webapp', 'backend'))
COMPAT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'webapp', 'backend', 'compat'))
for _p in (COMPAT_DIR, BACKEND_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from models.transaction_models import compute_canonical_tx_hash


def heal_binance_p2p():
    db_path = os.path.join(BACKEND_DIR, 'transactions.db')
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # 1. Inspect affected rows
    query_select = """
        SELECT id, fecha, exchange, tipo_operacion, moneda,
               monto_compra_cripto, cotizacion_compra,
               monto_venta_cripto, cotizacion_venta, monto_ars,
               comentarios
        FROM transactions
        WHERE exchange = 'Binance P2P'
          AND (is_certified = 0 OR is_certified IS NULL)
          AND (
            (monto_compra_cripto > 1 AND cotizacion_compra > 100 AND ABS(monto_ars - cotizacion_compra) < 0.01)
            OR
            (monto_venta_cripto > 1 AND cotizacion_venta > 100 AND ABS(monto_ars - cotizacion_venta) < 0.01)
          )
    """
    c.execute(query_select)
    rows = c.fetchall()
    print(f"Total filas detectadas para curación: {len(rows)}")
    
    # 2. Heal each row
    healed_count = 0
    import re
    for r in rows:
        row_id, fecha, ex, tipo, moneda, mc, cc, mv, cv, m_ars, comentarios = r
        if mc and mc > 0 and cc and cc > 0:
            new_monto_ars = round(mc * cc, 2)
        elif mv and mv > 0 and cv and cv > 0:
            new_monto_ars = round(mv * cv, 2)
        else:
            continue

        # Extract unique_ref from comentarios if present
        unique_ref = ""
        if comentarios:
            m = re.search(r'(?:order\s*id|id|ref|trade|txid)[:\s#]+([a-zA-Z0-9_\-]+)', str(comentarios), re.IGNORECASE)
            unique_ref = m.group(1) if m else str(comentarios).strip()

        # Recompute canonical hash
        new_hash = compute_canonical_tx_hash(
            fecha,
            ex,
            tipo,
            moneda,
            monto_compra=mc or 0.0,
            monto_venta=mv or 0.0,
            monto_ars=new_monto_ars,
            unique_ref=unique_ref
        )
        
        c.execute("""
            UPDATE transactions
            SET monto_ars = ?, tx_hash = ?
            WHERE id = ?
              AND (is_certified = 0 OR is_certified IS NULL)
        """, (new_monto_ars, new_hash, row_id))
        healed_count += 1
        
    conn.commit()
    conn.close()
    print(f"Curación completada con éxito. Filas actualizadas: {healed_count}")

if __name__ == '__main__':
    heal_binance_p2p()
