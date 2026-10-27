"""
Script para limpiar los filtros restrictivos de los anuncios de VENTA en Binance:
- Remueve takerAdditionalKycRequired = 0 (elimina el cartel [Verificación] / Verificación adicional).
- Remueve buyerRegDaysLimit = 0.
- Remueve userAllTradeCountMin = 0.
- Actualiza remarks y autoReplyMsg a aviso seguro sin palabras clave bloqueantes como "Bank Statement" (evita error 187059).
- Mantiene los anuncios en OFFLINE (advStatus=3). NO ENCIENDE LOS ANUNCIOS.
"""
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
from config.settings import DEFAULT_SELL_REMARKS, DEFAULT_SELL_AUTO_REPLY


async def main():
    client = BinanceClient()
    sell_adv_nos_env = os.getenv("BINANCE_SELL_ADV_NOS")
    if sell_adv_nos_env:
        sell_adv_nos = [x.strip() for x in sell_adv_nos_env.split(",") if x.strip()]
    else:
        sell_adv_nos = ["10000000000000000001", "10000000000000000002", "10000000000000000003"]
    
    clean_notice = "Buenas, solo transferencias del titular verificado en Binance. Rechazo pagos de terceros."
    
    for adv_no in sell_adv_nos:
        print(f"Limpiando anuncio de venta {adv_no}...")
        try:
            res = await client.update_ad(
                adv_no=adv_no,
                update_mode="selective",
                takerAdditionalKycRequired=0,
                buyerRegDaysLimit=0,
                userAllTradeCountMin=0,
                autoReplyMsg=clean_notice,
                remarks=clean_notice,
            )
            print(f"  Resultado {adv_no}: {res}")
        except Exception as e:
            print(f"  Error en {adv_no}: {e}")
        await asyncio.sleep(1.0)
    
    print("\n--- Verificando estado final de los 3 anuncios de venta en Binance ---")
    all_clean = True
    for adv_no in sell_adv_nos:
        detail = await client.get_ad_detail(adv_no)
        d = detail.get("data", {})
        status = d.get("advStatus")
        kyc = d.get("takerAdditionalKycRequired")
        reg_days = d.get("buyerRegDaysLimit")
        trades_min = d.get("userAllTradeCountMin")
        remarks = d.get("remarks")
        print(f"AdvNo: {adv_no}")
        print(f"  status: {status} (3=OFFLINE)")
        print(f"  takerAdditionalKycRequired: {kyc}")
        print(f"  buyerRegDaysLimit: {reg_days}")
        print(f"  userAllTradeCountMin: {trades_min}")
        print(f"  remarks: {remarks}")
        if kyc != 0 or status != 3:
            all_clean = False
            
    if all_clean:
        print("\n✅ ÉXITO TOTAL: Todos los anuncios de venta quedaron sin verificación adicional y en OFFLINE.")
    else:
        print("\n⚠️ ALERTA: Algún campo no quedó en el estado esperado.")

    await client.close()

if __name__ == "__main__":
    asyncio.run(main())
