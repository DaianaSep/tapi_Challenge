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
| Ratio de 5 a menos de 6 | Registrar una alerta preventiva para que Operaciones revise el margen antes de llegar al límite. |
| Ratio igual a 6 | Registrar que se alcanzó el límite. |
| Ratio superior a 6 o consultas sin pagos | Escalar a Operaciones. Con cero pagos, el ratio queda indefinido. |

El calendario y la pausa por deuda conocida son los ajustes automáticos. Ante una alerta se registra el estado y cualquier cambio adicional de frecuencia queda a cargo de Operaciones.

## Cómo correrlo

Desde la raíz del repositorio de GitHub, con Python 3:

```bash
python3 02_monitor_ratio.py --datos . --salida resultados_monitor
python3 02_monitor_ratio.py --datos . --contar-fallos --salida resultados_con_fallos
```

Si los CSV están en `data/` junto al script, se puede omitir `--datos`. La simulación registra los avisos en CSV. Para un piloto habría que conectar el control diario al programador de consultas y al canal de avisos de Operaciones.

- `controles_diarios.csv` guarda consultas, pagos, ratio y nivel de alerta.
- `consultas_omitidas.csv` identifica cada intento omitido por el calendario o por deuda conocida.
- `resumen_semanal.csv` permite comparar el histórico con la propuesta.

## Resultado sobre los tres meses

Comparé las 12 semanas completas del 3 de agosto al 25 de octubre de 2026 sobre 1.343 pagos históricos en ambos escenarios.

| Criterio de conteo | Consultas históricas | Consultas con la propuesta | Ratio histórico → propuesto | Semanas dentro del límite |
|---|---:|---:|---:|---:|
| Sin errores ni timeouts | 30.439 | 5.678 | 22,66 → **4,23** | 0/12 → **9/12** |
| Todos los intentos | 34.602 | 6.002 | 25,76 → **4,47** | 0/12 → **7/12** |

Con el criterio principal, el monitor registró siete alertas preventivas y 23 controles que requerían escalamiento en los 84 días evaluados. Los avisos se basan en el acumulado disponible cada mañana y el cumplimiento de la tabla se mide al cierre semanal.

El ahorro estimado surge de aplicar el calendario y las pausas de la Parte 1. La simulación usa los horarios y respuestas disponibles en el histórico. Los resultados muestran el impacto en el ratio. La cobertura de facturas y la puntualidad de los pagos se medirían durante el piloto.
