# Tapi · Parte 2 · Monitor del ratio de DeltaPay

## Diseño

El proceso aplica automáticamente el calendario definido en la Parte 1 mientras busca una factura.

| Convenio | Días 1 a 14 | Desde el día 15 |
|---|---:|---:|
| Luz | 48 h | 48 h |
| TV | 72 h | 48 h |
| Agua, Gas y Teléfono | 96 h | 48 h |

Al detectar deuda, se pausan las consultas de rutina y se habilita el respaldo desde el día anterior al vencimiento. El modelo cuenta una revalidación antes de pagar y retoma la búsqueda tras el pago. Los pagos conservan sus fechas históricas.

El monitor calcula al inicio de cada día el ratio de la semana en curso, de lunes a domingo, en la zona horaria de los CSV. Divide las consultas computables, incluida la revalidación, por los pagos confirmados atribuidos a DeltaPay. Aplica el supuesto de la Parte 1 de excluir errores y timeouts. Si el proveedor cuenta esos intentos, se puede repetir la simulación con ese criterio.

| Señal al iniciar el día | Acción |
|---|---|
| Ratio menor a 5 | Continuar con el calendario de la Parte 1. |
| Ratio de 5 a menos de 6 | Activar el ajuste preventivo y registrar la alerta. El umbral deja una consulta por pago de margen frente al límite de 6. |
| Ratio igual a 6 | Mantener el ajuste y registrar que se alcanzó el límite. |
| Ratio superior a 6 o consultas sin pagos | Registrar el caso para Operaciones. Con ratio superior a 6 se mantiene el ajuste. Con cero pagos el ratio queda indefinido y se conserva el calendario base, sujeto al cupo que apruebe Operaciones. |
| Del 1 al 7 del mes, ratio de 5 o más o consultas sin pagos | Marcar el caso para revisión. Operaciones puede usar el margen semanal para decidir si aprueba un cupo para las búsquedas programadas pendientes desde ese día hasta el domingo. |

El ajuste suma 24 h al intervalo mínimo de búsqueda programada cuando la última respuesta fue sin deuda. Luz, las consultas de respaldo y la revalidación previa al pago conservan su tratamiento. Al siguiente control se vuelve al calendario base si el ratio baja de 5 o comienza una semana nueva. La simulación solo puede ejecutar el siguiente intento disponible en los CSV, así que 24 h describe el aumento del intervalo mínimo y la demora efectiva puede ser mayor.

## Cómo correrlo

En [Google Colab](https://colab.research.google.com/github/DaianaSep/tapi_Challenge/blob/main/03_ejecutar_monitor.ipynb), ejecutá la única celda para descargar los datos, reproducir la simulación con los tres cupos y generar los siete CSV en `tapi_monitor/resultados_cupo/`.

Desde la raíz del repositorio de GitHub, con Python 3:

```bash
python3 02_monitor_ratio.py --datos . --salida resultados_monitor
python3 02_monitor_ratio.py --datos . --contar-fallos --salida resultados_con_fallos
```

Si los CSV están en `data/` junto al script, se puede omitir `--datos`. La simulación registra los avisos en CSV. Para un piloto habría que conectar el control diario al programador de consultas y al canal de avisos de Operaciones.

- `controles_diarios.csv` guarda consultas, pagos, ratio, nivel de alerta y si se activó el ajuste. Tanto este archivo como `controles_diarios_cupo.csv` incluyen `margen_consultas`, calculado como 6 × pagos acumulados − consultas computables. Un valor negativo indica exceso. Con cero pagos, queda vacío. El margen orienta la decisión de Operaciones sobre el cupo.
- `consultas_omitidas.csv` identifica cada intento omitido por el calendario, deuda conocida o ajuste preventivo.
- `resumen_semanal.csv` compara el histórico, la propuesta y la propuesta con ajuste.
- `impacto_deteccion.csv` registra cambios en la primera detección frente a la propuesta.

## Seguimiento reforzado y cupo de contingencia

Del **1 al 7 de cada mes**, el monitor marca para revisión los días en que el ratio acumulado de la semana llega a 5 o hay consultas sin pagos. La medición sigue siendo de lunes a domingo. Operaciones revisa las consultas y pagos observados y decide si aprueba un cupo para las búsquedas programadas pendientes desde el día de aprobación hasta el domingo. El cupo incluye Luz y preserva el respaldo de deudas conocidas y la revalidación antes del pago.

Para un mes nuevo uso el histórico como referencia y los datos de la semana en curso para decidir. Por ejemplo, el 1 de noviembre de 2026 corresponde a la semana que cierra ese domingo. Una aprobación entre el 2 y el 7 rige hasta el domingo 8. Con cero pagos, el ratio queda indefinido y la señal de revisión es la acumulación de consultas.

| Semana desde | Aprobación simulada | Cupo restante | Ratio sin cupo | Ratio con cupo |
|---|---|---:|---:|---:|
| 3 de agosto | 4 de agosto | 5 | 39,75 | **6,00** |
| 31 de agosto | 3 de septiembre | 70 | 8,98 | **5,75** |
| 5 de octubre | 6 de octubre | 140 | 9,17 | **5,93** |

En la simulación, las tres semanas llegaron al límite o quedaron por debajo y el ratio del período bajó de **4,16 a 3,90** y el cumplimiento pasó de 9 a **11 de 12 semanas**. La semana del 7 de septiembre subió a **6,38**. Entre las facturas que el monitor detectaba desde cada aprobación hasta el domingo, 91 se detectaron en semanas posteriores y 7 quedaron sin detección observable. Los importes de los cupos son ejemplos retrospectivos. La simulación conserva las fechas de pago y excluye errores y timeouts.

```bash
python3 02_monitor_ratio.py --datos . --aprobar-cupo 2026-08-04=5 --aprobar-cupo 2026-09-03=70 --aprobar-cupo 2026-10-06=140
```

## Resultado sobre los tres meses

Comparé las 12 semanas completas del 3 de agosto al 25 de octubre de 2026 sobre 1.343 pagos históricos en ambos escenarios.

| Criterio | Histórico | Propuesta | Propuesta con ajuste |
|---|---:|---:|---:|
| Sin errores ni timeouts | 22,66 · 0/12 | 4,23 · 9/12 | 4,16 · 9/12 |
| Todos los intentos | 25,76 · 0/12 | 4,47 · 7/12 | 4,39 · 9/12 |

Cada celda muestra el ratio acumulado y las semanas con ratio de hasta 6. Sin fallos, el ajuste redujo de 5.678 a 5.588 las consultas computables. Se activó en 25 de 84 controles diarios y hubo 22 controles para escalar. Contando fallos, las semanas del 7 y el 28 de septiembre pasaron a cumplir.

Sin fallos, 188 facturas se detectaron más tarde y dos de TV dejaron de aparecer respecto de la propuesta. Entre las detecciones que cambiaron y siguieron observándose, ninguna cayó el día del vencimiento o después. Los pagos se mantienen fijos y los horarios disponibles son los del CSV. En el piloto se debe medir la cobertura y el pago a tiempo.
