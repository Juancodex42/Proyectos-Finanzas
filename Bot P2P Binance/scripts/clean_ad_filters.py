"""
Script para actualizar y limpiar los filtros restrictivos en Binance del anuncio de compra G1.
Remueve takerAdditionalKycRequired (elimina [Verification]), 90 días, 100 trades,
y actualiza autoReplyMsg y remarks a: 'Buenas, no transfiero a terceros'.
"""
import sys
import os
import asyncio
import json

sys.path.insert(0, os.path.abspath("."))
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
from core.network.binance_api import BinanceClient
from config.settings import DEFAULT_BUY_AUTO_REPLY, DEFAULT_BUY_REMARKS


async def main():
    client = BinanceClient()
    adv_no = os.getenv("BINANCE_TARGET_ADV_NO", "10000000000000000001")
    print(f"Consultando estado actual de {adv_no}...")
    detail_before = await client.get_ad_detail(adv_no)
    data_b = detail_before.get("data", {})
    print("Estado actual:")
    print(f"  - Price: {data_b.get('price')}")
    print(f"  - buyerRegDaysLimit: {data_b.get('buyerRegDaysLimit')}")
    print(f"  - userAllTradeCountMin: {data_b.get('userAllTradeCountMin')}")
    print(f"  - takerAdditionalKycRequired: {data_b.get('takerAdditionalKycRequired')}")
    print(f"  - autoReplyMsg: {data_b.get('autoReplyMsg')}")
    print(f"  - remarks: {data_b.get('remarks')}")

    print("\nEnviando actualización a Binance...")
    update_res = await client.update_ad(
        adv_no=adv_no,
        update_mode="selective",
        buyerRegDaysLimit=0,
        userAllTradeCountMin=0,
        takerAdditionalKycRequired=0,
        autoReplyMsg=DEFAULT_BUY_AUTO_REPLY,
        remarks=DEFAULT_BUY_REMARKS,
    )
    print("Respuesta de update_ad:", update_res)

    await asyncio.sleep(1.0)
    print("\nConsultando estado posterior en Binance...")
    detail_after = await client.get_ad_detail(adv_no)
    data_a = detail_after.get("data", {})
    print("Estado posterior:")
    print(f"  - Price: {data_a.get('price')}")
    print(f"  - buyerRegDaysLimit: {data_a.get('buyerRegDaysLimit')}")
    print(f"  - userAllTradeCountMin: {data_a.get('userAllTradeCountMin')}")
    print(f"  - takerAdditionalKycRequired: {data_a.get('takerAdditionalKycRequired')}")
    print(f"  - autoReplyMsg: {data_a.get('autoReplyMsg')}")
    print(f"  - remarks: {data_a.get('remarks')}")

    if (
        data_a.get("buyerRegDaysLimit") == 0
        and data_a.get("userAllTradeCountMin") == 0
        and data_a.get("takerAdditionalKycRequired") == 0
        and data_a.get("autoReplyMsg") == DEFAULT_BUY_AUTO_REPLY
    ):
        print("\n✅ ÉXITO: El anuncio fue limpiado y actualizado correctamente en Binance.")
    else:
        print("\n⚠️ AVISO: Revisar campos no actualizados.")

    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
