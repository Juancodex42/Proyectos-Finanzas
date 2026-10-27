"""
Parseador numérico tolerante a formatos locales y anglosajones para inputs de Telegram.
Referencia de diseño: docs/ARQUITECTURA.md
"""
import math
from typing import Optional


def parse_numeric_input(text: str) -> Optional[float]:
    """
    Parsea entradas numéricas de usuarios en Telegram tolerando formatos locales y anglosajones.
    Ejemplos:
      "500.000" -> 500000.0
      "500,000" -> 500000.0
      "1.500.000,50" -> 1500000.5
      "1,500,000.50" -> 1500000.5
      "10,5" -> 10.5
      "10.5" -> 10.5
      "$ 500.000" -> 500000.0
    """
    cleaned = text.strip().replace("$", "").replace("ARS", "").replace("USDT", "").replace(" ", "")
    if not cleaned:
        return None

    try:
        # Caso 1: Tiene punto y coma (ej: 1.500.000,50 o 1,500,000.50)
        if "." in cleaned and "," in cleaned:
            if cleaned.rfind(",") > cleaned.rfind("."):
                # Formato argentino/europeo: 1.500.000,50
                cleaned = cleaned.replace(".", "").replace(",", ".")
            else:
                # Formato anglosajón: 1,500,000.50
                cleaned = cleaned.replace(",", "")
        # Caso 2: Múltiples puntos (ej: 1.500.000) -> separadores de miles
        elif cleaned.count(".") > 1:
            cleaned = cleaned.replace(".", "")
        # Caso 3: Múltiples comas (ej: 1,500,000) -> separadores de miles
        elif cleaned.count(",") > 1:
            cleaned = cleaned.replace(",", "")
        # Caso 4: Un solo punto (ej: "500.000" vs "10.50")
        elif "." in cleaned:
            parts = cleaned.split(".")
            if len(parts[1]) == 3 and len(parts[0]) >= 1 and parts[0] != "0":
                cleaned = cleaned.replace(".", "")
        # Caso 5: Una sola coma (ej: "500,000" vs "10,5")
        elif "," in cleaned:
            parts = cleaned.split(",")
            if len(parts[1]) == 3 and len(parts[0]) >= 1 and parts[0] != "0":
                cleaned = cleaned.replace(",", "")
            else:
                cleaned = cleaned.replace(",", ".")

        val = float(cleaned)
        if not math.isfinite(val):
            return None
        return val
    except ValueError:
        return None
