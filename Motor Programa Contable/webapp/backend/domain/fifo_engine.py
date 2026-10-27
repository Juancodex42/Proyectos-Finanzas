"""
Motor puro de costeo FIFO y balance de inventario para criptoactivos.
Ejecuta la cola determinista sin efectos colaterales ni dependencias de base de datos.
Referencia de diseño: docs/especificacion_fifo_prioridades.md
"""

from collections import deque
from datetime import datetime
from typing import List, Tuple, Dict, Any
from .models import Transaction, Lot, CostAssignment, InventoryGap, CRYPTO_DUST_EPSILON
from .operations import get_operation_priority


def compute_fifo_lots(transactions: List[Transaction]) -> Tuple[List[CostAssignment], List[InventoryGap]]:
    """
    Función de dominio pura que calcula el costo base FIFO y detecta brechas de inventario.
    
    Parámetros:
        transactions: Lista de objetos Transaction inmutables.
        
    Retorna:
        Tuple[List[CostAssignment], List[InventoryGap]]: Asignaciones de costo unitario y brechas.
    """
    if not transactions:
        return [], []

    # Ordenamiento determinista: Fecha ASC -> Prioridad intra-segundo ASC -> Hash Canónico ASC
    sorted_txs = sorted(
        transactions,
        key=lambda tx: (
            tx.fecha,
            get_operation_priority(tx.tipo_operacion, tx.monto_compra_cripto, tx.monto_venta_cripto),
            tx.tx_hash
        )
    )

    cost_assignments: List[CostAssignment] = []
    gaps: List[InventoryGap] = []

    # Agrupar por moneda canónica
    by_coin: Dict[str, List[Transaction]] = {}
    for tx in sorted_txs:
        c = tx.moneda.upper().strip()
        if c in ("ARS", "USD", "EUR", ""):
            continue
        by_coin.setdefault(c, []).append(tx)

    for coin, coin_txs in by_coin.items():
        buy_queue: deque[Lot] = deque()
        transfer_out_pool: deque[Dict[str, Any]] = deque()
        running_balance = 0.0

        for tx in coin_txs:
            op_prio = get_operation_priority(tx.tipo_operacion, tx.monto_compra_cripto, tx.monto_venta_cripto)
            mc = tx.monto_compra_cripto
            mv = tx.monto_venta_cripto
            price_ars = tx.cotizacion_compra

            # 1. Compras e Ingresos directos (Prioridad 1)
            if op_prio == 1 and mc > 0:
                buy_queue.append(Lot(
                    lot_id=tx.tx_hash,
                    fecha=tx.fecha,
                    moneda=coin,
                    quantity=mc,
                    price_ars=price_ars,
                    exchange=tx.exchange,
                    is_certified=bool(tx.is_certified)
                ))
                running_balance += mc

            # 2. Retiros inter-exchange (Prioridad 2)
            elif op_prio == 2 and mv > 0:
                transfer_out_pool.append({
                    "tx_hash": tx.tx_hash,
                    "fecha": tx.fecha,
                    "qty": mv,
                    "exchange_root": tx.exchange_root,
                    "matched": False
                })

            # 3. Depósitos inter-exchange (Prioridad 3)
            elif op_prio == 3 and mc > 0:
                # Intentar emparejar con transfer_out_pool
                matched = False
                for tout in list(transfer_out_pool):
                    if not tout["matched"] and tout["exchange_root"] != tx.exchange_root:
                        diff = abs(tout["qty"] - mc)
                        is_match = (diff <= 5.0) or (diff / max(tout["qty"], 0.01) <= 0.05) or (diff <= CRYPTO_DUST_EPSILON)
                        if is_match:
                            tout["matched"] = True
                            matched = True
                            transfer_out_pool.remove(tout)
                            break
                if not matched:
                    # Depósito externo sin retiro previo: entra al inventario a costo base $0
                    buy_queue.append(Lot(
                        lot_id=tx.tx_hash,
                        fecha=tx.fecha,
                        moneda=coin,
                        quantity=mc,
                        price_ars=price_ars if price_ars > 0 else 0.0,
                        exchange=tx.exchange,
                        is_certified=bool(tx.is_certified)
                    ))
                    running_balance += mc

            # 4. Comisiones / Fees de red (Prioridad 4)
            elif op_prio == 4 and mv > 0:
                rem_fee = mv
                fee_cost_ars = 0.0
                while rem_fee > 0 and buy_queue:
                    lot = buy_queue[0]
                    consume_qty = min(rem_fee, lot.quantity)
                    fee_cost_ars += consume_qty * lot.price_ars
                    lot.quantity -= consume_qty
                    rem_fee -= consume_qty
                    running_balance -= consume_qty
                    if lot.is_dust():
                        buy_queue.popleft()

                unit_cost = fee_cost_ars / mv if mv > 0 else 0.0
                cost_assignments.append(CostAssignment(
                    tx_hash=tx.tx_hash,
                    moneda=coin,
                    fecha_venta=tx.fecha,
                    cantidad_vendida=mv,
                    costo_unitario_ars=round(unit_cost, 8),
                    costo_total_ars=round(fee_cost_ars, 2),
                    monto_descubierto=round(rem_fee, 8) if rem_fee > 1e-6 else 0.0,
                    requires_cost_audit=1 if rem_fee > 1e-6 else 0
                ))

            # 5. Ventas gravadas y Egresos (Prioridad 5)
            elif op_prio == 5 and mv > 0:
                rem_sale = mv
                total_cost_ars = 0.0
                qty_valued = 0.0

                while rem_sale > 0 and buy_queue:
                    lot = buy_queue[0]
                    consume_qty = min(rem_sale, lot.quantity)
                    if lot.price_ars > 0:
                        total_cost_ars += consume_qty * lot.price_ars
                        qty_valued += consume_qty

                    lot.quantity -= consume_qty
                    rem_sale -= consume_qty
                    running_balance -= consume_qty
                    if lot.is_dust():
                        buy_queue.popleft()

                unit_cost = (total_cost_ars / qty_valued) if qty_valued > 0 else 0.0
                uncovered = max(0.0, rem_sale)

                if uncovered > CRYPTO_DUST_EPSILON:
                    gaps.append(InventoryGap(
                        exchange="Cartera Global",
                        origin_exchange=tx.exchange,
                        coin=coin,
                        date=tx.fecha,
                        deficit=round(uncovered, 8),
                        running_deficit=round(abs(min(0.0, running_balance)), 8),
                        sold_qty=mv,
                        available_qty=max(0.0, mv - uncovered)
                    ))

                cost_assignments.append(CostAssignment(
                    tx_hash=tx.tx_hash,
                    moneda=coin,
                    fecha_venta=tx.fecha,
                    cantidad_vendida=mv,
                    costo_unitario_ars=round(unit_cost, 8),
                    costo_total_ars=round(total_cost_ars, 2),
                    monto_descubierto=round(uncovered, 8),
                    requires_cost_audit=1 if uncovered > 1e-6 else 0
                ))

    return cost_assignments, gaps
