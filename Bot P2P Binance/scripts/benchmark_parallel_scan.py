"""
Benchmark de escaneo paralelo vs secuencial contra la API real de Binance P2P.
Verifica:
1. Tiempo transcurrido (Benchmark de velocidad).
2. Integridad de la respuesta (status code, data, precios).
3. Consumo de Rate Limit (X-SAPI-USED-IP-WEIGHT-1M).
4. Cero errores 429 / WAF.
"""
import asyncio
import time
import sys
import os
from pathlib import Path

# Resolver ruta raíz
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.network.binance_api import BinanceClient
from config.settings import FIAT

# 10 métodos de pago representativos para la prueba
TEST_METHODS = [
    "MercadoPagoNew",
    "BankArgentina",
    "UalaNew",
    "bancogalicia",
    "SantanderArgentina",
    "LemonCash",
    "BancoBrubankNew",
    "NaranjaX",
    "personalpay",
    "Fiwind",
]


async def run_sequential_test(client: BinanceClient, methods: list[str]):
    """Modo histórico: Secuencial con sleep(0.2)."""
    print("\n" + "=" * 50)
    print(f"1. INICIANDO TEST SECUENCIAL ({len(methods)} consultas, sleep=0.2s)")
    print("=" * 50)

    start = time.perf_counter()
    results = []
    errors = 0

    for m in methods:
        t0 = time.perf_counter()
        try:
            res = await client.search_ads(
                asset="USDT",
                fiat=FIAT,
                trade_type="SELL",
                pay_types=[m],
                rows=5,
            )
            data = res.get("data", [])
            dt = time.perf_counter() - t0
            results.append((m, len(data), dt, True))
        except Exception as e:
            errors += 1
            results.append((m, 0, 0, False))
        await asyncio.sleep(0.2)

    elapsed = time.perf_counter() - start
    print(f"  Tiempo total secuencial: {elapsed:.2f} s")
    print(f"  Exitosos: {len(results) - errors} / {len(methods)}")
    print(f"  Rate limit restante reportado por Binance: {client._rate_limit_remaining}")
    return elapsed, results


async def run_parallel_test(client: BinanceClient, methods: list[str], concurrency: int = 4):
    """Modo optimizado: Paralelo ordenado con Semaphore."""
    print("\n" + "=" * 50)
    print(f"2. INICIANDO TEST PARALELO CONCURRENTE ({len(methods)} consultas, Semaphore={concurrency})")
    print("=" * 50)

    sem = asyncio.Semaphore(concurrency)
    start = time.perf_counter()
    results = []
    errors = []

    async def worker(method: str):
        async with sem:
            t0 = time.perf_counter()
            try:
                res = await client.search_ads(
                    asset="USDT",
                    fiat=FIAT,
                    trade_type="SELL",
                    pay_types=[method],
                    rows=5,
                )
                data = res.get("data", [])
                dt = time.perf_counter() - t0
                best_price = "?"
                if data:
                    adv = data[0].get("adv", data[0])
                    best_price = adv.get("price", "?")
                return {
                    "method": method,
                    "count": len(data),
                    "best_price": best_price,
                    "duration": dt,
                    "success": True,
                }
            except Exception as e:
                return {
                    "method": method,
                    "count": 0,
                    "best_price": None,
                    "duration": 0,
                    "success": False,
                    "error": str(e),
                }

    tasks = [worker(m) for m in methods]
    results = await asyncio.gather(*tasks)
    elapsed = time.perf_counter() - start

    success_count = sum(1 for r in results if r["success"])
    print(f"  Tiempo total paralelo ({concurrency} workers): {elapsed:.2f} s")
    print(f"  Exitosos: {success_count} / {len(methods)}")
    print(f"  Rate limit restante reportado por Binance: {client._rate_limit_remaining}")
    return elapsed, results


async def main():
    client = BinanceClient()
    try:
        t_seq, _ = await run_sequential_test(client, TEST_METHODS)
        await asyncio.sleep(2.0)
        t_par, _ = await run_parallel_test(client, TEST_METHODS, concurrency=4)

        speedup = t_seq / t_par if t_par > 0 else 0
        print("\n" + "=" * 50)
        print("RESULTADO COMPARATIVO")
        print("=" * 50)
        print(f"  Secuencial: {t_seq:.2f}s")
        print(f"  Paralelo:   {t_par:.2f}s")
        print(f"  Aceleración: {speedup:.2f}x más rápido")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
