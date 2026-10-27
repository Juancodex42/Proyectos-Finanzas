import sys
import os
import asyncio

sys.path.insert(0, os.path.abspath("."))
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from core.network.binance_api import BinanceClient

async def apply_90_100():
    client = BinanceClient()
    sell_adv_nos_env = os.getenv("BINANCE_SELL_ADV_NOS")
    if sell_adv_nos_env:
        sell_adv_nos = [x.strip() for x in sell_adv_nos_env.split(",") if x.strip()]
    else:
        sell_adv_nos = ["10000000000000000001", "10000000000000000002", "10000000000000000003"]
    for adv_no in sell_adv_nos:
        res = await client.update_ad(
            adv_no=adv_no,
            update_mode="selective",
            takerAdditionalKycRequired=0,
            buyerRegDaysLimit=90,
            userAllTradeCountMin=100,
        )
        print(f"{adv_no} update:", res)
        await asyncio.sleep(1.0)

    print("\n--- Verificación final de los 3 anuncios de venta en Binance ---")
    for adv_no in sell_adv_nos:
        detail = await client.get_ad_detail(adv_no)
        d = detail.get("data", {})
        status = d.get("advStatus")
        kyc = d.get("takerAdditionalKycRequired")
        reg_days = d.get("buyerRegDaysLimit")
        trades_min = d.get("userAllTradeCountMin")
        print(f"AdvNo: {adv_no} | status={status} (3=OFFLINE) | takerAdditionalKycRequired={kyc} | buyerRegDaysLimit={reg_days} | userAllTradeCountMin={trades_min}")
    await client.close()

if __name__ == "__main__":
    asyncio.run(apply_90_100())
