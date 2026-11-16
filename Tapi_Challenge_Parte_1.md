# Tapi · Challenge de Product Operations

## Parte 1 · Diagnóstico y propuesta para el equipo

### Análisis de la situación

En las 12 semanas completas del 3 de agosto al 25 de octubre de 2026, DeltaPay superó el límite de **6 consultas por pago** todas las semanas. El ratio acumulado fue de **25,76** (34.602 consultas y 1.343 pagos). TV y Agua concentraron el **75,9 %** de las consultas. Espaciar solo esos dos convenios redujo el volumen, pero ninguna semana cumplió el límite. También encontré reconsultas de facturas con el mismo importe y casos en los que el importe cambió antes del pago.

### Qué propongo cambiar

- **Durante la búsqueda de deuda**, usar 48 h para Luz, 72 h para TV y 96 h para Agua, Gas y Teléfono del día 1 al 14. Desde el día 15, usar 48 h para todos. Las semanas con pocos pagos motivaron probar un intervalo mayor al inicio del mes.
- **Al detectar la factura**, guardar el importe y el vencimiento, pausar las consultas de rutina y hacer una consulta de respaldo si sigue pendiente cerca del vencimiento. Confirmar el saldo antes de pagar y reanudar la búsqueda de la próxima factura tras confirmar el pago.

### Impacto estimado

| Escenario | Consultas por pago del período | Semanas con ratio ≤ 6 |
|---|---:|---:|
| Histórico, todos los intentos | 25,76 | 0 de 12 |
| Propuesta, todos los intentos | 4,47 | 7 de 12 |
| Propuesta, sin errores ni *timeouts* | 4,23 | 9 de 12 |
| Monitor con ajuste preventivo, sin errores ni *timeouts* | 4,16 | 9 de 12 |
| Monitor con ajuste preventivo y cupos aprobados, sin errores ni *timeouts* | **3,90** | **11 de 12** |

La propuesta reduce de **34.602 a 6.002** las consultas computadas al contar todos los intentos, incluida una revalidación por pago. Con el supuesto de excluir fallos, las tres semanas que superaron 6 tuvieron entre **8 y 42 pagos**, frente a **76–172** en las que cumplieron.

Con el **cupo de contingencia**, el ratio bajó de **4,16 a 3,90** frente al mismo monitor sin cupo y dos semanas más quedaron dentro del límite. La simulación usa cupos elegidos retrospectivamente y mantiene las fechas de pago históricas. El [detalle de la contingencia](#seguimiento-reforzado-y-cupo-de-contingencia) muestra el resultado por semana y el efecto sobre las detecciones.

### Riesgo que aceptaría y opciones a considerar

Aceptaría probar intervalos mayores en un piloto acotado y medir el tiempo entre detección y vencimiento y los pagos a tiempo, especialmente en Luz y TV. Supuse que la factura impaga sigue visible hasta el pago o el vencimiento. El histórico permite estimar el margen, pero no qué respondería DeltaPay en un horario nuevo. Con la propuesta, **724 facturas de Luz y 10 de TV** dejaron de aparecer en las consultas conservadas por la simulación.

Si DeltaPay acepta lotes y cuenta por llamada, **hasta cinco cuentas por lote** llevarían el ratio a **2,01** y el cumplimiento a **11 de 12 semanas**. Pagar de inmediato las facturas autorizadas al detectarlas llevaría el ratio a **4,10**, con **9 de 12 semanas**. Estimé ambas opciones por separado, excluyendo errores y *timeouts*.

### Seguimiento reforzado y cupo de contingencia

Del **1 al 7 de cada mes**, el monitor marca para revisión los días en que el ratio acumulado de la semana llega a 5 o hay consultas sin pagos. La medición sigue siendo de lunes a domingo. Operaciones revisa las consultas y pagos observados y decide si aprueba un cupo para las búsquedas programadas pendientes desde el día de aprobación hasta el domingo. El cupo incluye Luz y preserva el respaldo de deudas conocidas y la revalidación antes del pago.

Para un mes nuevo uso el histórico como referencia y los datos de la semana en curso para decidir. Por ejemplo, el 1 de noviembre de 2026 corresponde a la semana que cierra ese domingo. Una aprobación entre el 2 y el 7 rige hasta el domingo 8. Con cero pagos, el ratio queda indefinido y la señal de revisión es la acumulación de consultas.

| Semana desde | Aprobación simulada | Cupo restante | Ratio sin cupo | Ratio con cupo |
|---|---|---:|---:|---:|
| 3 de agosto | 4 de agosto | 5 | 39,75 | **6,00** |
| 31 de agosto | 3 de septiembre | 70 | 8,98 | **5,75** |
| 5 de octubre | 6 de octubre | 140 | 9,17 | **5,93** |

En la simulación, las tres semanas llegaron al límite o quedaron por debajo y el período pasó de 9 a **11 de 12 semanas** dentro del límite. La semana del 7 de septiembre subió a **6,38**. Entre las facturas que el monitor detectaba desde cada aprobación hasta el domingo, 91 se detectaron en semanas posteriores y 7 quedaron sin detección observable. Los importes de los cupos son ejemplos retrospectivos. La simulación conserva las fechas de pago y excluye errores y timeouts.

## Email to DeltaPay

Hi Mariana,

Thanks for flagging this. Before December 1, we’ll run a pilot to reduce the number of bill lookups. We’ll check for new bills less often, depending on the service and the time of the month. Once we find a bill, we’ll pause routine checks for that account and confirm the current amount due right before paying it.

During the pilot, we’ll track how many lookups we make per payment each week and check that bills are still paid on time. We’ll share an initial update before the new limit takes effect.

We’re also exploring batch lookups so we can check multiple accounts in a single request. Could you confirm whether DeltaPay supports batch lookups and whether you count one lookup per batch or one per account?

## Consultas y recorrido del análisis

Primero validé los datos y definí cómo medir el ratio. Después busqué qué explicaba el volumen y usé esos hallazgos para probar cambios en las consultas. Los bloques SQL usan las tablas de DuckDB del notebook. Las semanas se agrupan de lunes a domingo en la fecha local del archivo. Como el CSV de pagos carece de un campo de proveedor, atribuí los pagos por convenio a partir del cruce con las consultas. [Abrir el notebook en Colab](https://colab.research.google.com/github/DaianaSep/tapi_Challenge/blob/23b5b7b179b5effb1f8e410e580fe892b40427a5/01_exploracion_datos.ipynb).

### Dimensionar los archivos

Conté los registros de entrada y después comprobé en el notebook que los identificadores de cuentas, consultas y pagos estaban informados y eran únicos.

```sql
SELECT 'cuentas' AS tabla, COUNT(*) AS filas FROM cuentas
UNION ALL
SELECT 'consultas' AS tabla, COUNT(*) AS filas FROM consultas
UNION ALL
SELECT 'pagos' AS tabla, COUNT(*) AS filas FROM pagos
```

### Validar los identificadores

Comparé el total de filas, los identificadores informados y los identificadores distintos. Los tres conteos coincidieron en cada archivo. Así comprobé que podía contar cuentas, consultas y pagos por ID.

```sql
SELECT
    COUNT(*) AS filas,
    COUNT(account_id) AS filas_con_id,
    COUNT(DISTINCT account_id) AS cuentas_distintas
FROM cuentas
```

```sql
SELECT
    COUNT(*) AS filas,
    COUNT(consulta_id) AS filas_con_id,
    COUNT(DISTINCT consulta_id) AS consultas_distintas
FROM consultas
```

```sql
SELECT
    COUNT(*) AS filas,
    COUNT(pago_id) AS filas_con_id,
    COUNT(DISTINCT pago_id) AS pagos_distintos
FROM pagos
```

### Identificar los convenios de DeltaPay

Crucé convenio y proveedor para justificar qué pagos entran en el denominador.

```sql
SELECT
    convenio,
    proveedor,
    COUNT(*) AS cantidad_consultas
FROM consultas
GROUP BY convenio, proveedor
ORDER BY convenio, proveedor
```

### Entender qué cuenta como intento

Separé programadas y reintentos según el resultado. El desglose permite distinguir errores y timeouts de las respuestas sobre deuda.

```sql
SELECT origen, resultado, COUNT(*) AS intentos
FROM consultas
GROUP BY origen, resultado
ORDER BY origen, intentos DESC
```

### Delimitar el período

Revisé el rango de cada archivo y usé las 12 semanas completas para comparar ratios.

```sql
SELECT 'cuentas' AS tabla, MIN(fecha_alta) AS desde, MAX(fecha_alta) AS hasta
FROM cuentas
UNION ALL
SELECT 'consultas', MIN(SUBSTR("timestamp", 1, 10)), MAX(SUBSTR("timestamp", 1, 10))
FROM consultas
UNION ALL
SELECT 'pagos', MIN(SUBSTR(fecha_pago, 1, 10)), MAX(SUBSTR(fecha_pago, 1, 10))
FROM pagos
```

### Validar monto y vencimiento

Medí campos vacíos por resultado para comprobar si podía seguir una misma factura y comparar importes.

```sql
SELECT
    resultado,
    COUNT(*) AS intentos,
    COUNT(*) FILTER (WHERE NULLIF(TRIM(monto), '') IS NULL) AS sin_monto,
    COUNT(*) FILTER (WHERE NULLIF(TRIM(fecha_vencimiento), '') IS NULL) AS sin_vencimiento
FROM consultas
GROUP BY resultado
ORDER BY resultado
```

### Medir el ratio por semana

Crucé los dos conteos semanales. La semana del 3 de agosto, por ejemplo, tuvo 3.046 consultas y solo 8 pagos.

```sql
WITH q AS (
    SELECT CAST(date_trunc('week', CAST(left(timestamp, 10) AS DATE)) AS DATE) AS semana,
           count(*) AS consultas
    FROM consultas WHERE proveedor = 'deltapay'
    GROUP BY 1
), p AS (
    SELECT CAST(date_trunc('week', CAST(left(fecha_pago, 10) AS DATE)) AS DATE) AS semana,
           count(*) AS pagos
    FROM pagos
    WHERE convenio IN (SELECT DISTINCT convenio FROM consultas WHERE proveedor = 'deltapay')
    GROUP BY 1
)
SELECT semana, consultas, coalesce(pagos, 0) AS pagos,
       round(consultas * 1.0 / nullif(pagos, 0), 2) AS ratio
FROM q LEFT JOIN p USING (semana)
WHERE semana BETWEEN DATE '2026-08-03' AND DATE '2026-10-19'
ORDER BY semana
```

### Localizar dónde se concentra el volumen

Calculé la participación de cada convenio para elegir por dónde empezar las pruebas.

```sql
SELECT convenio, count(*) AS consultas,
       round(100.0 * count(*) / sum(count(*)) OVER (), 2) AS porcentaje
FROM consultas
WHERE proveedor = 'deltapay'
  AND left(timestamp, 10) BETWEEN '2026-08-03' AND '2026-10-25'
GROUP BY convenio ORDER BY consultas DESC
```

### Identificar consultas repetidas y cambios de importe

Vinculé detecciones previas al pago por cuenta, convenio y vencimiento. Con coincidencia de importe, 630 de 1.322 pagos tuvieron reconsultas, con mediana de 12. Sin exigir esa coincidencia, identifiqué 93 pagos con cambios de importe en las respuestas previas.

```sql
WITH filtros AS (
    SELECT unnest([false, true]) AS exigir_monto_pago
), vinculos AS (
    SELECT exigir_monto_pago, p.pago_id, q.monto,
           row_number() OVER (PARTITION BY exigir_monto_pago, p.pago_id ORDER BY q.timestamp, q.consulta_id) AS orden,
           first_value(q.monto) OVER (PARTITION BY exigir_monto_pago, p.pago_id ORDER BY q.timestamp, q.consulta_id) AS monto_inicial
    FROM pagos p JOIN consultas q
      ON p.account_id = q.account_id AND p.convenio = q.convenio
     AND p.fecha_vencimiento = q.fecha_vencimiento
     AND q.timestamp < p.fecha_pago
    CROSS JOIN filtros
    WHERE (NOT exigir_monto_pago OR TRY_CAST(q.monto AS DECIMAL(18,2)) = TRY_CAST(p.monto AS DECIMAL(18,2)))
      AND q.proveedor = 'deltapay' AND q.resultado = 'deuda_encontrada'
), por_pago AS (
    SELECT exigir_monto_pago, pago_id, count(*) FILTER (WHERE orden > 1) AS reconsultas,
           count(*) FILTER (WHERE orden > 1 AND monto = monto_inicial) AS mismo_monto,
           count(*) FILTER (WHERE orden > 1 AND monto <> monto_inicial) AS cambio_monto
    FROM vinculos GROUP BY exigir_monto_pago, pago_id
)
SELECT exigir_monto_pago, count(*) AS pagos_vinculados,
       count(*) FILTER (WHERE reconsultas > 0) AS pagos_con_reconsulta,
       median(mismo_monto) FILTER (WHERE mismo_monto > 0) AS mediana_reconsultas_mismo_monto,
       count(*) FILTER (WHERE cambio_monto > 0) AS pagos_con_cambio_monto
FROM por_pago GROUP BY exigir_monto_pago ORDER BY exigir_monto_pago
```

### Preparar los eventos de la primera simulación

Extraje las consultas a DeltaPay en orden cronológico y los pagos de los convenios que atiende. Usé esas dos tablas como entrada para probar los intervalos de 12 h y 24 h en TV y Agua.

```sql
SELECT account_id, convenio, "timestamp", origen, resultado, monto, fecha_vencimiento
    FROM consultas
    WHERE proveedor = 'deltapay'
    ORDER BY "timestamp", consulta_id
```

```sql
SELECT account_id, convenio, fecha_pago
    FROM pagos
    WHERE convenio IN (
        SELECT DISTINCT convenio FROM consultas WHERE proveedor = 'deltapay'
    )
```

### Cómo pasé de los resultados a la propuesta

1. **Probé 12 h y 24 h en TV y Agua** porque concentraban el volumen. El ratio acumulado bajó a 18,73 y 15,40, respectivamente, con las 12 semanas todavía por encima de 6. [Primera prueba](https://colab.research.google.com/github/DaianaSep/tapi_Challenge/blob/23b5b7b179b5effb1f8e410e580fe892b40427a5/01_exploracion_datos.ipynb#scrollTo=primera-prueba-tv-agua).
2. **Simulé pausas con deuda conocida y distintos intervalos.** Con 48 h para todos y excluyendo fallos obtuve 4,72 y 7 de 12 semanas. Revisé el margen histórico antes del vencimiento. En Luz, las 724 facturas ausentes con esa regla tenían al menos 7 días desde la primera detección histórica hasta vencer. [Simulación y márgenes](https://colab.research.google.com/github/DaianaSep/tapi_Challenge/blob/23b5b7b179b5effb1f8e410e580fe892b40427a5/01_exploracion_datos.ipynb#scrollTo=regla-estado).
3. **Ajusté la frecuencia al comienzo del mes.** Con 96 h hasta el día 14 salvo Luz, pasé a 9 de 12 semanas sin contar fallos. Reducir TV de 96 h a 72 h mantuvo esas nueve semanas y recuperó cuatro detecciones en las consultas conservadas. [Ajuste por convenio](https://colab.research.google.com/github/DaianaSep/tapi_Challenge/blob/23b5b7b179b5effb1f8e410e580fe892b40427a5/01_exploracion_datos.ipynb#scrollTo=decision-final).
4. **Revisé qué quedaba pendiente.** Las semanas que superaron 6 sin contar fallos empezaron el 3 de agosto, el 31 de agosto y el 5 de octubre. Todas tocaron el inicio del mes. Con tres meses de datos, tomaría ese patrón como hipótesis para el piloto. [Brechas semanales](https://colab.research.google.com/github/DaianaSep/tapi_Challenge/blob/23b5b7b179b5effb1f8e410e580fe892b40427a5/01_exploracion_datos.ipynb#scrollTo=semanas-fuera-limite).
5. **Evalué opciones adicionales.** En los lotes agrupé búsquedas por día y convenio y mantuve las revalidaciones, los reintentos y las consultas de respaldo individuales. En el pago inmediato adelanté los pagos históricos vinculados a una detección simulada, trasladé sus revalidaciones y desconté reconsultas de la misma factura. [Lotes](https://colab.research.google.com/github/DaianaSep/tapi_Challenge/blob/23b5b7b179b5effb1f8e410e580fe892b40427a5/01_exploracion_datos.ipynb#scrollTo=simulacion-lotes) · [Pago inmediato](https://colab.research.google.com/github/DaianaSep/tapi_Challenge/blob/23b5b7b179b5effb1f8e410e580fe892b40427a5/01_exploracion_datos.ipynb#scrollTo=pago-inmediato).


## Código de las simulaciones del Colab

Los bloques siguen el orden del notebook y comparten sus tablas y variables. Las dos consultas que preparan los eventos se incluyen también en la primera celda de simulación para conservarla completa.

### Primera simulación de TV y Agua

Probé espaciar solo las consultas programadas de TV y Agua. El ahorro redujo el ratio acumulado, pero ninguna semana quedó dentro del límite.

```python
import pandas as pd

consultas_delta = consultar("""
    SELECT account_id, convenio, "timestamp", origen, resultado, monto, fecha_vencimiento
    FROM consultas
    WHERE proveedor = 'deltapay'
    ORDER BY "timestamp", consulta_id
""")
pagos_delta = consultar("""
    SELECT account_id, convenio, fecha_pago
    FROM pagos
    WHERE convenio IN (
        SELECT DISTINCT convenio FROM consultas WHERE proveedor = 'deltapay'
    )
""")

# Los CSV usan un único desplazamiento horario (-06:00).
from datetime import date, datetime

consultas_delta["timestamp"] = consultas_delta["timestamp"].map(datetime.fromisoformat)
consultas_delta["fecha_vencimiento"] = consultas_delta["fecha_vencimiento"].map(
    lambda valor: date.fromisoformat(valor) if valor is not None else None
)
pagos_delta["fecha_pago"] = pagos_delta["fecha_pago"].map(datetime.fromisoformat)
eventos = list(consultas_delta.itertuples(index=False))
pagos_observados = list(pagos_delta.itertuples(index=False))

from collections import Counter, defaultdict
from datetime import timedelta
from statistics import median

def medir_frecuencia(horas, horas_agua=None, horas_agua_despues=None):
    intervalos = {
        "CONV-TV": timedelta(hours=horas),
        "CONV-AGUA": timedelta(hours=horas if horas_agua is None else horas_agua),
    }
    objetivos = {"CONV-TV", "CONV-AGUA"}
    ultima_programada = {}
    primera_observada = {}
    primera_con_regla = {}
    resumen = defaultdict(Counter)

    def lunes(momento):
        dia = momento.date()
        return dia - timedelta(days=dia.weekday())

    for consulta in eventos:
        momento = consulta.timestamp
        cuenta = (consulta.account_id, consulta.convenio)
        semana = lunes(momento)
        resumen[semana]["consultas"] += 1
        omitir = False
        if consulta.convenio in objetivos and consulta.origen == "programada":
            anterior = ultima_programada.get(cuenta)
            minimo = intervalos[consulta.convenio]
            if consulta.convenio == "CONV-AGUA" and horas_agua_despues is not None and momento.day > 10:
                minimo = timedelta(hours=horas_agua_despues)
            omitir = anterior is not None and momento - anterior < minimo
            if not omitir:
                ultima_programada[cuenta] = momento

        if omitir:
            resumen[semana]["omitidas"] += 1

        if consulta.resultado == "deuda_encontrada" and consulta.fecha_vencimiento is not None:
            clave = (*cuenta, consulta.fecha_vencimiento)
            primera_observada.setdefault(clave, momento)
            if not omitir:
                primera_con_regla.setdefault(clave, momento)

    for pago in pagos_observados:
        resumen[lunes(pago.fecha_pago)]["pagos"] += 1

    semanas_completas = [
        v for semana, v in sorted(resumen.items())
        if date(2026, 8, 3) <= semana <= date(2026, 10, 19)
    ]
    demoras = []
    riesgos = Counter()
    for clave, original in primera_observada.items():
        if clave[1] not in objetivos or not date(2026, 8, 3) <= original.date() <= date(2026, 10, 25):
            continue
        siguiente = primera_con_regla.get(clave)
        if siguiente is None:
            riesgos["sin_deteccion"] += 1
        elif siguiente > original:
            demoras.append((siguiente - original).total_seconds() / 3600)
            if siguiente.date() >= clave[-1] and original.date() < clave[-1]:
                riesgos["pierde_margen_previo"] += 1

    return {
        "horas_tv": horas,
        "horas_agua": horas if horas_agua is None else horas_agua,
        "horas_agua_despues": horas_agua_despues,
        "consultas_omitidas": sum(v["omitidas"] for v in semanas_completas),
        "semanas_en_limite": sum(
            v["pagos"] > 0 and v["consultas"] - v["omitidas"] <= 6 * v["pagos"]
            for v in semanas_completas
        ),
        "mejor_ratio": min((v["consultas"] - v["omitidas"]) / v["pagos"] for v in semanas_completas if v["pagos"]),
        "detecciones_demoradas": len(demoras),
        "mediana_demora_horas": median(demoras) if demoras else None,
        "sin_deteccion_observada": riesgos["sin_deteccion"],
        "pasa_al_dia_de_vencimiento_o_despues": riesgos["pierde_margen_previo"],
    }


filas_primera_prueba = []
for horas in (12, 24):
    resultado = medir_frecuencia(horas)
    evitadas = resultado["consultas_omitidas"]
    filas_primera_prueba.append((horas, evitadas, round((34602 - evitadas) / 1343, 2),
                                round(resultado["mejor_ratio"], 2), resultado["semanas_en_limite"]))
pd.DataFrame(filas_primera_prueba, columns=["Intervalo mínimo (h)", "Consultas evitadas",
    "Ratio del período", "Mejor ratio semanal", "Semanas ≤ 6"])
```

### Regla de búsqueda según el estado de la deuda

Modelé cuándo consultar, pausar las búsquedas, revisar cerca del vencimiento y revalidar antes del pago.

```python
import csv
from collections import Counter
from datetime import datetime, timedelta, date
from pathlib import Path

def simular_estado(consultas, pagos, intervalo, ventanas=None, reintento_dias=(), intervalo_inicio_mes=None, busquedas_programadas=None):
    eventos = [(datetime.fromisoformat(r['timestamp']), 1, r['consulta_id'], r) for r in consultas]
    eventos += [(datetime.fromisoformat(r['fecha_pago']), 0, r['pago_id'], r) for r in pagos]
    estado, primera, retenida = {}, {}, {}
    guardadas=[]
    pendientes=set()
    semanal = {}
    for t, tipo, _, r in sorted(eventos):
        dia = t.date()
        lunes = dia - timedelta(days=dia.weekday())
        m = semanal.setdefault(lunes, Counter())
        k = r['account_id'], r['convenio']
        if tipo == 0:
            m['pagos'] += 1
            m['revalidaciones'] += 1
            estado.pop(k, None)
            pendientes.discard(k)
            continue
        m['observadas'] += 1
        deuda = r['resultado'] == 'deuda_encontrada' and r['fecha_vencimiento']
        if deuda:
            clave = (*k, date.fromisoformat(r['fecha_vencimiento']))
            primera.setdefault(clave, t)
        ultima, vence = estado.get(k, (None, None))
        horas = intervalo
        if intervalo_inicio_mes is not None and dia.day <= 14 and vence is None:
            horas = intervalo_inicio_mes
        ventana = (ventanas or {}).get(k)
        if dia.month == 10 and not vence and ventana and not ventana[0] <= dia.day <= ventana[1]:
            horas = 96
        es_reintento = k in pendientes and ultima is not None and t-ultima < timedelta(hours=horas)
        if not es_reintento and ultima is not None and (t-ultima < timedelta(hours=horas) or (vence and dia < vence-timedelta(days=1))):
            # El respaldo prevalece cuando falta un día para el vencimiento conocido.
            if not vence or dia < vence-timedelta(days=1):
                continue
        m['ejecutadas'] += 1
        guardadas.append(r)
        if busquedas_programadas is not None and vence is None and r['origen'] == 'programada':
            busquedas_programadas.add(r['consulta_id'])
        pendientes.discard(k)
        if not es_reintento and r['resultado'] in ('timeout','error') and vence is None and dia.day in reintento_dias:
            pendientes.add(k)
        if deuda:
            retenida.setdefault(clave, t)
        nuevo_vence = clave[-1] if deuda else vence if r['resultado'] in ('timeout','error') else None
        estado[k] = (ultima if es_reintento else t, nuevo_vence)
    return semanal, primera, retenida, guardadas
```

### Comparar frecuencias y detecciones

Medí tanto el cumplimiento semanal como las facturas que dejaron de aparecer en las consultas conservadas.

```python
def leer(nombre):
    with (Path("data") / nombres[nombre]).open() as archivo:
        return list(csv.DictReader(archivo))

consultas_delta = [r for r in leer("consultas") if r["proveedor"] == "deltapay"]
convenios = sorted({r["convenio"] for r in consultas_delta})
pagos_delta = [r for r in leer("pagos") if r["convenio"] in convenios]

def evaluar(intervalo, luz_historica=True, tv=None, ventanas=None, reintento_dias=()):
    consultas_semana, pagos_semana = Counter(), Counter()
    primeras, detecciones = {}, {}
    for convenio in convenios:
        cc = [r for r in consultas_delta if r["convenio"] == convenio]
        pp = [r for r in pagos_delta if r["convenio"] == convenio]
        horas = tv if convenio == "CONV-TV" and tv is not None else intervalo
        dias = reintento_dias if convenio == "CONV-TV" else ()
        semanas, original, retenida, _ = simular_estado(cc, pp, horas, ventanas, dias)
        sin_cambios = luz_historica and convenio == "CONV-LUZ"
        primeras.update(original)
        detecciones.update(original if sin_cambios else retenida)
        for semana, datos in semanas.items():
            consultas_semana[semana] += datos["observadas"] if sin_cambios else datos["ejecutadas"] + datos["revalidaciones"]
            pagos_semana[semana] += datos["pagos"]
    return consultas_semana, pagos_semana, primeras, detecciones

def resumir(resultado, desde, hasta, desde_facturas, hasta_facturas):
    consultas, pagos, primeras, detecciones = resultado
    semanas = [s for s in sorted(pagos) if desde <= s <= hasta]
    q, p = sum(consultas[s] for s in semanas), sum(pagos[s] for s in semanas)
    ausentes = Counter(k[1] for k,t in primeras.items()
                       if desde_facturas <= t.date() <= hasta_facturas and k not in detecciones)
    return q, round(q/p, 2), sum(0 < pagos[s] and consultas[s] <= 6*pagos[s] for s in semanas), dict(ausentes)

base = evaluar(48)
periodo = (date(2026,8,3), date(2026,10,19), date(2026,8,3), date(2026,10,25))
escenarios = {
    "24 h para todos": evaluar(24, luz_historica=False),
    "72 h para todos": evaluar(72, luz_historica=False),
    "48 h para todos": evaluar(48, luz_historica=False),
    "48 h salvo Luz": base,
    "72 h salvo Luz": evaluar(72),
    "96 h salvo Luz": evaluar(96),
    "TV 24 h": evaluar(48, tv=24),
    "TV 24 h y reintento cualquier día": evaluar(48, tv=24, reintento_dias=range(1,32)),
    "TV 24 h y reintento en ventanas": evaluar(48, tv=24, reintento_dias={5,6,7,20,21,22,23,24}),
}
import pandas as pd
pd.DataFrame({nombre: resumir(r, *periodo) for nombre,r in escenarios.items()},
             index=["Consultas", "Ratio", "Semanas ≤ 6", "Facturas ausentes por convenio"]).T
```

### Medir el margen hasta el vencimiento

Comparé la primera detección histórica y la simulada por convenio. Las facturas ausentes quedaron fuera del cálculo de margen.

```python
from statistics import median

escenarios_margen = {
    "Histórico": base[2],
    "48 h salvo Luz": base[3],
    "48 h para todos": escenarios["48 h para todos"][3],
}
filas_margen = []
for convenio in convenios:
    facturas = {
        clave: primera for clave, primera in base[2].items()
        if clave[1] == convenio and periodo[2] <= primera.date() <= periodo[3]
    }
    for nombre, detecciones in escenarios_margen.items():
        margen = [(clave[2] - detecciones[clave].date()).days
                  for clave in facturas if clave in detecciones]
        filas_margen.append({
            "Convenio": convenio, "Escenario": nombre, "Facturas históricas": len(facturas),
            "Mediana de días de margen": median(margen) if margen else None,
            "Con ≥ 2 días": sum(d >= 2 for d in margen),
            "Con 1 día": margen.count(1),
            "El día del vencimiento": margen.count(0),
            "Después del vencimiento": sum(d < 0 for d in margen),
            "Sin detección": len(facturas) - len(margen),
        })

margenes_por_convenio = pd.DataFrame(filas_margen)
display(margenes_por_convenio)

# Margen histórico de Luz en las facturas ausentes al aplicar 48 h a todos.
luz_ausentes = [
    (clave[2] - primera.date()).days
    for clave, primera in base[2].items()
    if clave[1] == "CONV-LUZ" and periodo[2] <= primera.date() <= periodo[3]
    and clave not in escenarios_margen["48 h para todos"]
]
print(f"Luz: {len(luz_ausentes)} ausentes con 48 h para todos; "
      f"{sum(d >= 2 for d in luz_ausentes)} tenían al menos 2 días de margen histórico; "
      f"mediana histórica: {median(luz_ausentes)} días.")
```

### Probar otro horario para la segunda búsqueda de Luz

Estimé cuánto tiempo quedaría para pagar si la segunda consulta se hiciera 48 h después del primer intento.

```python
from collections import defaultdict

# Segunda consulta: primer intento histórico + 48 h, si el primero devolvió sin_deuda.
programadas_luz = defaultdict(list)
for fila in consultas_delta:
    if fila["convenio"] == "CONV-LUZ" and fila["origen"] == "programada":
        programadas_luz[fila["account_id"]].append(
            (datetime.fromisoformat(fila["timestamp"]), fila["resultado"])
        )
pagos_luz = defaultdict(list)
for fila in pagos_delta:
    if fila["convenio"] == "CONV-LUZ" and fila["fecha_vencimiento"]:
        clave = (fila["account_id"], "CONV-LUZ", date.fromisoformat(fila["fecha_vencimiento"]))
        pagos_luz[clave].append(datetime.fromisoformat(fila["fecha_pago"]))

margenes_luz = []
pagos_previos = 0
objetivo_luz = 0
for clave, primera in base[2].items():
    cuenta, convenio, vencimiento = clave
    if convenio != "CONV-LUZ" or not periodo[2] <= primera.date() <= periodo[3]:
        continue
    if clave in escenarios_margen["48 h para todos"]:
        continue
    objetivo_luz += 1
    anteriores = [evento for evento in programadas_luz[cuenta] if evento[0] < primera]
    if not anteriores:
        continue
    intento, respuesta = max(anteriores)
    if respuesta != "sin_deuda" or primera.date() - intento.date() != timedelta(days=1):
        continue
    nueva_consulta = intento + timedelta(hours=48)
    margenes_luz.append((vencimiento - nueva_consulta.date()).days)
    pagos_previos += any(primera <= pago < nueva_consulta for pago in pagos_luz[clave])

print(f"Facturas analizadas: {len(margenes_luz)} de {objetivo_luz}")
print(f"Margen mínimo y mediano: {min(margenes_luz)} y {median(margenes_luz):g} días calendario")
print(f"Pagos históricos entre la detección y el horario propuesto: {pagos_previos}")
```

### Medir 48 h para todos con y sin fallos

Usé la misma regla en los cinco convenios y calculé el efecto de descontar errores y timeouts del numerador.

```python
def evaluar_busqueda_mensual(intervalos_inicio_mes):
    consultas, fallos, pagos = Counter(), Counter(), Counter()
    ausentes = Counter()
    for convenio in convenios:
        intentos = [r for r in consultas_delta if r["convenio"] == convenio]
        pagos_convenio = [r for r in pagos_delta if r["convenio"] == convenio]
        semanas, primeras, retenidas, ejecutadas = simular_estado(
            intentos, pagos_convenio, 48,
            intervalo_inicio_mes=intervalos_inicio_mes.get(convenio),
        )
        for semana, conteos in semanas.items():
            consultas[semana] += conteos["ejecutadas"] + conteos["revalidaciones"]
            pagos[semana] += conteos["pagos"]
        for intento in ejecutadas:
            if intento["resultado"] in ("timeout", "error"):
                dia = date.fromisoformat(intento["timestamp"][:10])
                fallos[dia - timedelta(days=dia.weekday())] += 1
        ausentes[convenio] = sum(
            clave not in retenidas for clave, primera in primeras.items()
            if periodo[2] <= primera.date() <= periodo[3]
        )
    filas = []
    for semana in sorted(pagos):
        if periodo[0] <= semana <= periodo[1]:
            filas.append((semana, pagos[semana], consultas[semana],
                          fallos[semana], consultas[semana] - fallos[semana]))
    tabla = pd.DataFrame(filas, columns=["Semana", "Pagos", "Consultas con fallos",
                                        "Fallos", "Consultas computadas"])
    tabla["Ratio"] = tabla["Consultas computadas"] / tabla["Pagos"]
    return tabla, ausentes

def resumir_busqueda(nombre, tabla, ausentes):
    pagos = tabla["Pagos"].sum()
    return {
        "Escenario": nombre,
        "Consultas con fallos": tabla["Consultas con fallos"].sum(),
        "Consultas computadas": tabla["Consultas computadas"].sum(),
        "Ratio contando fallos": tabla["Consultas con fallos"].sum() / pagos,
        "Ratio excluyendo fallos": tabla["Consultas computadas"].sum() / pagos,
        "Semanas ≤ 6 sin fallos": (tabla["Consultas computadas"] <= 6 * tabla["Pagos"]).sum(),
        "Facturas ausentes en TV": ausentes["CONV-TV"],
        "Facturas ausentes en Luz": ausentes["CONV-LUZ"],
    }

semanas_48h, ausentes_48h = evaluar_busqueda_mensual({})
resumen_48h = resumir_busqueda("48 h para todos", semanas_48h, ausentes_48h)
display(pd.DataFrame([resumen_48h]).round(2))
```

### Comparar frecuencias de inicio de mes

Probé 96 h salvo Luz y después 72 h para TV. Busqué mantener nueve semanas dentro del límite con más detecciones.

```python
intervalos_96h = {convenio: 96 for convenio in convenios if convenio != "CONV-LUZ"}
intervalos_tv_72h = {**intervalos_96h, "CONV-TV": 72}
semanas_96h, ausentes_96h = evaluar_busqueda_mensual(intervalos_96h)
semanas_propuesta, ausentes_propuesta = evaluar_busqueda_mensual(intervalos_tv_72h)
display(pd.DataFrame([
    resumen_48h,
    resumir_busqueda("96 h del 1 al 14 salvo Luz", semanas_96h, ausentes_96h),
    resumir_busqueda("96 h del 1 al 14 con TV a 72 h", semanas_propuesta, ausentes_propuesta),
]).round(2))
```

### Medir la brecha de las semanas que no cumplieron

Comparé consultas y pagos para saber cuánto faltaba recortar en cada semana.

```python
brechas = semanas_propuesta.copy()
brechas["Brecha sobre el límite"] = brechas["Consultas computadas"] - 6 * brechas["Pagos"]
fuera_limite = brechas["Brecha sobre el límite"] > 0
display(brechas.loc[fuera_limite, ["Semana", "Pagos", "Consultas computadas",
                                  "Ratio", "Brecha sobre el límite"]].round(2))
display(brechas.groupby(fuera_limite.rename("Supera 6"))[
    ["Pagos", "Consultas computadas"]
].agg(["min", "median", "max"]))
```

### Revisar el calendario de pagos

Comparé los primeros siete días de cada mes para evaluar si el bajo volumen se repetía.

```python
# Comparo ventanas idénticas del calendario, aparte de las semanas lunes a domingo.
pagos_por_mes = Counter()
pagos_del_1_al_7 = Counter()
for pago in pagos_delta:
    dia = date.fromisoformat(pago["fecha_pago"][:10])
    mes = dia.strftime("%Y-%m")
    pagos_por_mes[mes] += 1
    if dia.day <= 7:
        pagos_del_1_al_7[mes] += 1
display(pd.DataFrame([
    {"Mes": mes, "Pagos del 1 al 7": pagos_del_1_al_7[mes], "Pagos del mes": total,
     "% del 1 al 7": round(100 * pagos_del_1_al_7[mes] / total, 1)}
    for mes, total in sorted(pagos_por_mes.items())
]))
```

### Evaluar consultas por lotes

Estimé el ahorro de solicitudes si DeltaPay contabiliza cada lote como una consulta.

```python
# Agrupo por convenio y día, con una sola consulta por cuenta en cada lote.
from math import ceil

grupos_lotes = defaultdict(Counter)
individuales = Counter()
for convenio in convenios:
    ids_lote = set()
    _, _, _, intentos = simular_estado(
        [r for r in consultas_delta if r["convenio"] == convenio],
        [r for r in pagos_delta if r["convenio"] == convenio], 48,
        intervalo_inicio_mes=intervalos_tv_72h.get(convenio),
        busquedas_programadas=ids_lote,
    )
    for intento in intentos:
        dia = date.fromisoformat(intento["timestamp"][:10])
        semana = dia - timedelta(days=dia.weekday())
        if intento["resultado"] in ("timeout", "error"):
            continue
        if intento["consulta_id"] in ids_lote:
            grupos_lotes[semana, dia, convenio][intento["account_id"]] += 1
        else:
            individuales[semana] += 1

filas_lotes, detalle_lotes = [], []
for capacidad in (1, 2, 5, 10, 20, 50):
    llamadas = individuales.copy()
    for (semana, dia, convenio), cuentas in grupos_lotes.items():
        # Cada ronda agrupa como máximo un intento por cuenta.
        llamadas[semana] += sum(
            ceil(sum(n >= ronda for n in cuentas.values()) / capacidad)
            for ronda in range(1, max(cuentas.values()) + 1)
        )
    total_consultas = total_pagos = cumplen = 0
    for semana, pagos in semanas_propuesta[["Semana", "Pagos"]].itertuples(index=False, name=None):
        computadas = llamadas[semana] + pagos  # Una revalidación individual por pago.
        total_consultas += computadas
        total_pagos += pagos
        cumple = computadas <= 6 * pagos
        cumplen += cumple
        if not cumple:
            detalle_lotes.append((capacidad, semana, pagos, computadas, round(computadas / pagos, 2)))
    filas_lotes.append((capacidad, total_consultas, round(total_consultas / total_pagos, 2), cumplen))

tabla_lotes = pd.DataFrame(filas_lotes, columns=["Cuentas por lote", "Consultas computadas", "Ratio", "Semanas ≤ 6"])
pendientes_lotes = pd.DataFrame(detalle_lotes, columns=["Cuentas por lote", "Semana", "Pagos", "Consultas computadas", "Ratio"])
display(tabla_lotes)
display(pendientes_lotes[pendientes_lotes["Cuentas por lote"].isin([5, 20, 50])])
```

### Simular el pago al detectar la deuda

Adelanté pagos históricos vinculados a una detección y comparé el efecto semanal para las dos reglas de frecuencia.

```python
def semana_de(momento):
    dia = momento.date()
    return dia - timedelta(days=dia.weekday())

def simular_pago_inmediato(intervalos, semanas_base):
    movimientos, reconsultas = Counter(), Counter()
    for convenio in convenios:
        pagos = [p for p in pagos_delta if p["convenio"] == convenio]
        _, _, detecciones, intentos = simular_estado(
            [r for r in consultas_delta if r["convenio"] == convenio], pagos, 48,
            intervalo_inicio_mes=intervalos.get(convenio))
        adelantados = {}
        for pago in sorted(pagos, key=lambda p: datetime.fromisoformat(p["fecha_pago"])):
            if not pago["fecha_vencimiento"]:
                continue
            clave = (pago["account_id"], convenio, date.fromisoformat(pago["fecha_vencimiento"]))
            original = datetime.fromisoformat(pago["fecha_pago"])
            primera = detecciones.get(clave)
            if primera is not None and primera < original and clave not in adelantados:
                adelantados[clave] = original
                movimientos[semana_de(original)] -= 1
                movimientos[semana_de(primera)] += 1
        for intento in intentos:
            if intento["resultado"] != "deuda_encontrada" or not intento["fecha_vencimiento"]:
                continue
            clave = (intento["account_id"], convenio, date.fromisoformat(intento["fecha_vencimiento"]))
            momento = datetime.fromisoformat(intento["timestamp"])
            if clave in adelantados and detecciones[clave] < momento < adelantados[clave]:
                reconsultas[semana_de(momento)] += 1

    tabla = semanas_base[["Semana", "Pagos", "Consultas computadas"]].copy()
    cambio = tabla["Semana"].map(lambda semana: movimientos[semana])
    evitadas = tabla["Semana"].map(lambda semana: reconsultas[semana])
    tabla["Pagos inmediatos"] = tabla["Pagos"] + cambio
    tabla["Consultas con pago inmediato"] = tabla["Consultas computadas"] + cambio - evitadas
    tabla["Ratio original"] = tabla["Consultas computadas"] / tabla["Pagos"].where(tabla["Pagos"] > 0)
    tabla["Ratio con pago inmediato"] = tabla["Consultas con pago inmediato"] / tabla["Pagos inmediatos"].where(tabla["Pagos inmediatos"] > 0)
    return tabla

resumen_inmediato, detalle_inmediato = [], []
for nombre, intervalos, semanas in [
    ("48 h fijas", {}, semanas_48h),
    ("Frecuencias por quincena", intervalos_tv_72h, semanas_propuesta),
]:
    tabla = simular_pago_inmediato(intervalos, semanas)
    detalle_inmediato.append(tabla.assign(Escenario=nombre))
    for momento, consultas, pagos, ratio in [
        ("Fecha de pago histórica", "Consultas computadas", "Pagos", "Ratio original"),
        ("Pago al detectar", "Consultas con pago inmediato", "Pagos inmediatos", "Ratio con pago inmediato"),
    ]:
        resumen_inmediato.append((nombre, momento, tabla[consultas].sum(), tabla[pagos].sum(),
                                tabla[consultas].sum() / tabla[pagos].sum(), tabla[ratio].le(6).sum()))
tabla_inmediato = pd.DataFrame(resumen_inmediato, columns=[
    "Frecuencia", "Momento del pago", "Consultas", "Pagos", "Ratio", "Semanas ≤ 6"])
display(tabla_inmediato.round(2))
display(pd.concat(detalle_inmediato, ignore_index=True).round(2))
```
