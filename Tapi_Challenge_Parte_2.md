# Tapi · Parte 2 · Monitor del ratio de DeltaPay

## Diseño

Revisaría el ratio **todos los días al inicio del día**, en la zona horaria registrada en los CSV, y reiniciaría los contadores el lunes. El numerador incluye las consultas realizadas y una verificación de saldo por pago. El denominador cuenta los pagos confirmados atribuidos a DeltaPay por convenio. Como en la Parte 1, el escenario principal excluye los errores y timeouts del numerador. Es un supuesto del ejercicio. El script también permite evaluar qué cambia si DeltaPay cuenta todos los intentos.

| Señal al iniciar el día | Acción |
|---|---|
| Ratio menor a 5 | Continúa el calendario base. Si ya hubo un ajuste, se vuelve al calendario base cuando el ratio baja de 4,5 o comienza una semana nueva. |
| Ratio de 5 o más | Se agrega hasta un día al intervalo de búsqueda programada de las cuentas cuya última respuesta fue «sin deuda». El punto de alerta deja margen antes de llegar a 6 y el umbral de vuelta evita cambios repetidos alrededor de 5. |
| Ratio de 6 o más, o consultas sin pagos confirmados | Se mantiene el ajuste y se registra un aviso para Operaciones. Con cero pagos, el ratio queda indefinido. Operaciones revisaría el volumen de pagos y decidiría si hace falta cambiar el calendario o consultar a DeltaPay. |

El ajuste automático se aplica solo a búsquedas programadas sin deuda conocida. Luz conserva **48 h durante todo el mes**, incluso en modo restringido. Las consultas de respaldo se habilitan desde el día anterior al vencimiento y se cuenta una revalidación justo antes de cada pago. Después del pago se reanuda la búsqueda. El modo restringido suma 24 horas al intervalo mínimo y deja pasar el próximo intento disponible una vez alcanzado ese intervalo. Cada decisión usa los eventos registrados hasta ese momento.

## Cómo correrlo

Desde la carpeta del proyecto, con Python 3 y los CSV en `data/`:

```bash
python3 02_monitor_ratio.py --salida resultados_monitor
python3 02_monitor_ratio.py --contar-fallos --salida resultados_con_fallos
```

La simulación ejecuta los controles diarios mientras procesa los eventos en orden cronológico. Para un piloto, el mismo control debería leer los contadores reales al inicio del día, aplicar el modo al programador de consultas y enviar los avisos a Operaciones. El script deja los avisos en el registro de controles.

### Qué deja registrado

- `controles_diarios.csv` guarda el ratio observado, los conteos acumulados, el modo anterior y el nuevo y si correspondía escalar.
- `consultas_diferidas.csv` indica qué intento se postergó, por qué y de cuánto fue el cambio de intervalo.
- `resumen_semanal.csv` compara el histórico, el calendario propuesto en la parte 1 y el mismo calendario con el monitor. Así se puede medir el aporte del ajuste.
- `impacto_deteccion.csv` registra las facturas cuya primera detección cambia respecto del calendario base y si se encontraron antes de vencer.

## Resultado sobre los tres meses

Procesé agosto a octubre de 2026, conservando el estado entre semanas. Para medir cumplimiento comparé las **12 semanas completas del 3 de agosto al 25 de octubre**.

| Convenio | Días 1–14 | Desde el día 15 |
|---|---:|---:|
| Luz | 48 h | 48 h |
| TV | 72 h | 48 h |
| Agua, Gas y Teléfono | 96 h | 48 h |

Los intervalos aplican mientras se busca una factura. El escenario conserva los pagos históricos y simula consultas individuales. Los lotes y el pago inmediato quedaron como opciones evaluadas aparte en la Parte 1.

| Criterio de conteo | Histórico | Calendario base | Calendario con monitor |
|---|---:|---:|---:|
| Todos los intentos | 25,76 · 0/12 | 4,47 · 7/12 | **4,38 · 9/12** |
| Sin errores ni timeouts | 22,66 · 0/12 | 4,23 · 9/12 | **4,15 · 9/12** |

Cada celda muestra el ratio acumulado y las semanas con ratio de hasta 6. En el escenario principal el monitor redujo de **5.678 a 5.577** las consultas frente al calendario base. Se mantuvieron nueve semanas dentro del límite. En 30 de los 84 controles diarios el modo quedó restringido y se registraron 21 avisos repartidos en cinco semanas. Al contar todos los intentos, las semanas del 7 y el 28 de septiembre pasan a cumplir con el monitor.

El histórico permite simular qué intentos se habrían ejecutado. Los pagos se conservan en sus fechas originales y las búsquedas solo pueden usar los horarios disponibles en el CSV. Frente al calendario base, cuatro facturas adicionales de TV dejaron de aparecer en las consultas conservadas. Entre las 221 facturas que tardaron más en detectarse, la demora mediana fue de unas 24 h. Ninguna de las que reaparecieron se detectó el día del vencimiento o después. En el piloto mediría cobertura y puntualidad real, además del ratio.
