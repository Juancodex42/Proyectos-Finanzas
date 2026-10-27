"""Test rápido de conexión con Binance API y Telegram (Sanity Check / Onboarding)."""
import asyncio
import sys
import os
from pathlib import Path

# Soporte de codificación UTF-8 en consola de Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Agregar el directorio raíz del proyecto al sys.path de manera segura y desacoplada
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import BINANCE_API_KEY, BINANCE_SECRET_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


async def test_spot():
    """Test 1: API pública de spot (sin auth)."""
    print("=" * 50)
    print("TEST 1: Spot prices (API publica)")
    print("=" * 50)
    from core.spot_client import SpotClient
    client = SpotClient()
    try:
        price = await client.get_price("BTCUSDT")
        print(f"  BTC/USDT: ${price:,.2f}")

        prices = await client.get_usdt_prices(["BTC", "ETH", "USDT", "SOL"])
        for asset, p in prices.items():
            print(f"  {asset}/USDT: ${p:,.2f}")
        print("  >> SPOT OK")
        return True
    except Exception as e:
        print(f"  >> ERROR: {e}")
        return False
    finally:
        await client.close()


async def test_binance_auth():
    """Test 2: API autenticada de Binance (SAPI)."""
    print("\n" + "=" * 50)
    print("TEST 2: Binance SAPI (autenticado)")
    print("=" * 50)
    print(f"  API Key: {BINANCE_API_KEY[:12]}...{BINANCE_API_KEY[-4:]}" if BINANCE_API_KEY else "  API Key: [NO CONFIGURADA]")
    print(f"  Secret:  {BINANCE_SECRET_KEY[:8]}...{BINANCE_SECRET_KEY[-4:]}" if BINANCE_SECRET_KEY else "  Secret:  [NO CONFIGURADA]")

    from core.network.binance_api import BinanceClient
    client = BinanceClient()
    try:
        # Test: buscar anuncios de USDT en ARS
        result = await client.search_ads(
            asset="USDT", fiat="ARS", trade_type="SELL", rows=3,
        )
        data = result.get("data", [])
        print(f"  Anuncios USDT/ARS SELL encontrados: {len(data)}")
        if data:
            for item in data[:3]:
                adv = item.get("adv", item)
                advertiser = item.get("advertiser", {})
                price = adv.get("price", "?")
                nick = advertiser.get("nickName", "?")
                print(f"    - {nick}: ${float(price):,.2f} ARS/USDT")
        print("  >> SAPI AUTH OK")
        return True
    except Exception as e:
        print(f"  >> ERROR: {e}")
        return False
    finally:
        await client.close()


async def test_my_ads():
    """Test 3: Listar mis anuncios."""
    print("\n" + "=" * 50)
    print("TEST 3: Mis anuncios en Binance P2P")
    print("=" * 50)

    from core.network.binance_api import BinanceClient
    client = BinanceClient()
    try:
        total_found = 0
        for tt in ["SELL", "BUY"]:
            result = await client.list_my_ads(trade_type=tt)
            data = result.get("data", [])
            print(f"  Anuncios tipo {tt}: {len(data)}")
            for item in data:
                total_found += 1
                adv_no = item.get("advNo", "?")
                asset = item.get("asset", "?")
                price = float(item.get("price", 0))
                status = item.get("advStatus", "?")
                methods = [m.get("identifier", m.get("tradeMethodShortName", "?"))
                           for m in item.get("tradeMethods", [])]
                status_txt = "ONLINE" if status == 1 else "OFFLINE" if status == 3 else str(status)
                print(f"    [{adv_no}] {asset} ({tt}): ${price:,.2f} [{status_txt}] metodos={methods}")
        if total_found == 0:
            print("  [ADVERTENCIA] No se encontraron anuncios en Binance P2P (0 anuncios).")
            print("  >> MIS ANUNCIOS OK (0 encontrados - verifica si necesitas crearlos)")
        else:
            print(f"  >> MIS ANUNCIOS OK ({total_found} encontrados)")
        return True
    except Exception as e:
        print(f"  >> ERROR: {e}")
        return False
    finally:
        await client.close()


async def test_payment_methods():
    """Test 4: Mis metodos de pago."""
    print("\n" + "=" * 50)
    print("TEST 4: Mis metodos de pago configurados")
    print("=" * 50)

    from core.network.binance_api import BinanceClient
    client = BinanceClient()
    try:
        result = await client.get_my_payment_methods()
        data = result.get("data", [])
        print(f"  Metodos de pago configurados: {len(data)}")
        for m in data:
            ident = m.get("tradeMethodIdentifier", m.get("identifier", "?"))
            mid = m.get("id", "?")
            status = m.get("payStatus", "?")
            print(f"    - ID {mid}: {ident} [{status}]")
        print("  >> PAYMENT METHODS OK")
        return True
    except Exception as e:
        print(f"  >> ERROR: {e}")
        return False
    finally:
        await client.close()


async def test_telegram():
    """Test 5: Enviar mensaje por Telegram."""
    print("\n" + "=" * 50)
    print("TEST 5: Telegram Bot")
    print("=" * 50)
    print(f"  Token: {TELEGRAM_BOT_TOKEN[:15]}..." if TELEGRAM_BOT_TOKEN else "  Token: [NO CONFIGURADO]")
    print(f"  Chat ID: {TELEGRAM_CHAT_ID}")

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("  >> TELEGRAM SKIPPED (credenciales vacías)")
        return False

    import aiohttp
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": "🤖 *Bot P2P Binance ARS*\n\n✅ Test de conexión exitoso!\nEl bot está listo para operar.",
            "parse_mode": "Markdown",
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                result = await resp.json()
                if result.get("ok"):
                    print("  Mensaje enviado correctamente a Telegram!")
                    print("  >> TELEGRAM OK")
                    return True
                else:
                    err = result.get("description", str(result))
                    print(f"  >> TELEGRAM ERROR: {err}")
                    if "chat not found" in err.lower():
                        print("  [AVISO] Debes abrir t.me/P2P_Binance_exchange_Bot en Telegram y tocar START")
                    return False
    except Exception as e:
        print(f"  >> ERROR: {e}")
        return False


async def main():
    print("\n" + "#" * 50)
    print("  TEST DE CONEXION - Bot P2P Binance ARS")
    print("#" * 50 + "\n")

    results = {}
    results["spot"] = await test_spot()
    results["auth"] = await test_binance_auth()
    results["my_ads"] = await test_my_ads()
    results["payment"] = await test_payment_methods()
    results["telegram"] = await test_telegram()

    print("\n" + "=" * 50)
    print("RESUMEN")
    print("=" * 50)
    for test, ok in results.items():
        icon = "[OK]" if ok else "[FAIL]"
        print(f"  {icon} {test}")

    all_ok = all(results.values())
    print(f"\n{'[+] TODOS LOS TESTS PASARON' if all_ok else '[-] ALGUNOS TESTS REQUIEREN ATENCION'}")
    return all_ok


if __name__ == "__main__":
    asyncio.run(main())
