# Documentación Maestra del Proyecto: Nexus Quant Terminal

> Este documento es un espejo sincronizado de [`project.md`](../project.md) en la raíz del proyecto. Consulte también [`docs/ARQUITECTURA.md`](ARQUITECTURA.md) para el detalle de componentes, flujos de datos y decisiones de diseño.

## 1. Propósito del Sistema

**Nexus Quant Terminal** es una plataforma cuantitativa de simulación por eventos (Binary & Triple-Barrier), optimización evolutiva híbrida (Python + Rust) y ejecución algorítmica dual (*Paper* y *Live* en Binance Futures USDT-M).

> **Nota sobre Propiedad Intelectual (Alpha Protection):**
> Las estrategias incluidas en este repositorio corresponden a implementaciones base y académicas (modelos de Markov, cruces institucionales, reversión a la media y estructuras de volumen) diseñadas para demostrar la capacidad de procesamiento, simulación por eventos y optimización genética del motor **Nexus Quant Terminal**. Las estrategias propietarias de generación de *Alpha* en producción han sido excluidas por razones de confidencialidad financiera.

## 2. Ejecución Rápida (Zero-API Demo Mode)

Ejecute `NEXUS_QUANT_TERMINAL.bat` en la raíz del repositorio para acceder al panel interactivo:
- **[1]** Iniciar servidor web en segundo plano (`http://127.0.0.1:5001`) sin requerir claves de API.
- **[2]** Ejecutar demostración cuantitativa en consola (Backtest Multi-Estrategia + Simulación Barbell).
- **[3]** Ejecutar la suite completa de pruebas automatizadas (`pytest`).
- **[4]** Detener el servidor en el puerto `5001`.
- **[5]** Salir.
