# Tapi · Product Operations

## Entregables

- [Parte 1 · Diagnóstico y propuesta](Tapi_Challenge_Parte_1.md)
- [Notebook de análisis](01_exploracion_datos.ipynb) · [Abrir en Colab](https://colab.research.google.com/github/DaianaSep/tapi_Challenge/blob/main/01_exploracion_datos.ipynb)
- [Parte 2 · Diseño y resultados del monitor](Tapi_Challenge_Parte_2.md) · [Script](02_monitor_ratio.py)
- [Enunciado](Challenge_Product_Operations_2.pdf) y archivos CSV en la raíz del repositorio.

## Ejecutar la simulación

Desde la raíz del repositorio, con Python 3:

```bash
python3 02_monitor_ratio.py --datos . --salida resultados_monitor
python3 02_monitor_ratio.py --datos . --contar-fallos --salida resultados_con_fallos
```

El script genera los controles diarios, las consultas omitidas y el resumen semanal.

## Contingencia de inicio de mes

El monitor refuerza la revisión del 1 al 7. Operaciones decide si aprueba un cupo desde ese día hasta el domingo. Para reproducir las tres aprobaciones simuladas:

```bash
python3 02_monitor_ratio.py --datos . --aprobar-cupo 2026-08-04=5 --aprobar-cupo 2026-09-03=70 --aprobar-cupo 2026-10-06=140 --salida resultados_cupo
```
