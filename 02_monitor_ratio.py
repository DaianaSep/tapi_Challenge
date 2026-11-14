"""# Tapi · Parte 2 · Monitor del ratio de DeltaPay

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
| Ratio superior a 6 o consultas sin pagos | Registrar el caso para Operaciones. Con ratio superior a 6 se mantiene el ajuste. Con cero pagos el ratio queda indefinido y se conserva el calendario base. |

El ajuste suma 24 h al intervalo mínimo de búsqueda programada cuando la última respuesta fue sin deuda. Luz, las consultas de respaldo y la revalidación previa al pago conservan su tratamiento. Al siguiente control se vuelve al calendario base si el ratio baja de 5 o comienza una semana nueva. La simulación solo puede ejecutar el siguiente intento disponible en los CSV, así que 24 h describe el aumento del intervalo mínimo y la demora efectiva puede ser mayor.

## Cómo correrlo

Desde la raíz del repositorio de GitHub, con Python 3:

```bash
python3 02_monitor_ratio.py --datos . --salida resultados_monitor
python3 02_monitor_ratio.py --datos . --contar-fallos --salida resultados_con_fallos
```

Si los CSV están en `data/` junto al script, se puede omitir `--datos`. La simulación registra los avisos en CSV. Para un piloto habría que conectar el control diario al programador de consultas y al canal de avisos de Operaciones.

- `controles_diarios.csv` guarda consultas, pagos, ratio, nivel de alerta y si se activó el ajuste.
- `consultas_omitidas.csv` identifica cada intento omitido por el calendario, deuda conocida o ajuste preventivo.
- `resumen_semanal.csv` compara el histórico, la propuesta y la propuesta con ajuste.
- `impacto_deteccion.csv` registra cambios en la primera detección frente a la propuesta.

## Resultado sobre los tres meses

Comparé las 12 semanas completas del 3 de agosto al 25 de octubre de 2026 sobre 1.343 pagos históricos en ambos escenarios.

| Criterio | Histórico | Propuesta | Propuesta con ajuste |
|---|---:|---:|---:|
| Sin errores ni timeouts | 22,66 · 0/12 | 4,23 · 9/12 | 4,16 · 9/12 |
| Todos los intentos | 25,76 · 0/12 | 4,47 · 7/12 | 4,39 · 9/12 |

Cada celda muestra el ratio acumulado y las semanas con ratio de hasta 6. Sin fallos, el ajuste redujo de 5.678 a 5.588 las consultas computables. Se activó en 25 de 84 controles diarios y hubo 22 controles para escalar. Contando fallos, las semanas del 7 y el 28 de septiembre pasaron a cumplir.

Sin fallos, 188 facturas se detectaron más tarde y dos de TV dejaron de aparecer respecto de la propuesta. Entre las detecciones que cambiaron y siguieron observándose, ninguna cayó el día del vencimiento o después. Los pagos se mantienen fijos y los horarios disponibles son los del CSV. En el piloto se debe medir la cobertura y el pago a tiempo.
"""
import argparse
import csv
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

LIMITE = 6
ALERTA = 5
INICIO = date(2026, 8, 3)
FIN = date(2026, 10, 25)
FALLOS = {"error", "timeout"}


def leer(carpeta, nombre):
    with (carpeta / f"B_agenda_{nombre}.csv").open(newline="", encoding="utf-8-sig") as archivo:
        return list(csv.DictReader(archivo))


def lunes(dia):
    return dia - timedelta(days=dia.weekday())


def simular(eventos, excluir_fallos, ajustar=False):
    consultas, pagos = Counter(), Counter()
    controles, omitidas = [], []
    estado, detecciones = {}, {}
    dia_control = eventos[0][0].date()

    restringido = False

    def controlar(dia):
        semana = lunes(dia)
        q, p = consultas[semana], pagos[semana]
        ratio = q / p if p else None
        if not p:
            nivel = "escalar" if q else "sin actividad"
        elif ratio >= LIMITE:
            nivel = "escalar" if ratio > LIMITE else "límite alcanzado"
        else:
            nivel = "preventiva" if ratio >= ALERTA else "normal"
        aplicar = ajustar and ratio is not None and ratio >= ALERTA
        controles.append({
            "fecha": dia, "semana": semana, "consultas": q, "pagos": p,
            "ratio": ratio, "nivel": nivel, "ajuste_activo": aplicar,
        })

        return aplicar

    for momento, tipo, identificador, fila in eventos:
        dia = momento.date()
        while dia_control <= dia:
            restringido = controlar(dia_control)
            dia_control += timedelta(days=1)

        semana = lunes(dia)
        convenio = fila["convenio"]
        cuenta = (convenio, fila["account_id"])
        if tipo == 0:
            pagos[semana] += 1
            consultas[semana] += 1  # Una revalidación individual por pago.
            estado.pop(cuenta, None)
            continue

        ultima, vence, respuesta = estado.get(cuenta, (None, None, None))
        intervalo = 48
        if dia.day <= 14 and vence is None and convenio != "CONV-LUZ":
            intervalo = 72 if convenio == "CONV-TV" else 96
        motivo = None
        if vence is not None and dia < vence - timedelta(days=1):
            motivo = "Deuda conocida"
        elif vence is None and ultima is not None and momento - ultima < timedelta(hours=intervalo):
            motivo = "Intervalo de búsqueda"
        adicional = 0
        if (motivo is None and restringido and vence is None and respuesta == "sin_deuda"
                and convenio != "CONV-LUZ" and fila["origen"] == "programada"
                and momento - ultima < timedelta(hours=intervalo + 24)):
            motivo = "Ajuste por ratio"
            adicional = 24
        if motivo:
            omitidas.append({
                "fecha_hora": momento.isoformat(), "semana": semana, "consulta_id": identificador,
                "convenio": convenio, "cuenta": cuenta[1], "intervalo_base_h": intervalo,
                "motivo": motivo, "horas_adicionales": adicional,
            })
            continue

        resultado = fila["resultado"]
        if not excluir_fallos or resultado not in FALLOS:
            consultas[semana] += 1
        if resultado == "deuda_encontrada" and fila["fecha_vencimiento"]:
            vence = date.fromisoformat(fila["fecha_vencimiento"])
            detecciones.setdefault((*cuenta, vence), momento)
        elif resultado not in FALLOS:
            vence = None
        estado[cuenta] = (momento, vence, resultado)

    return consultas, pagos, detecciones, controles, omitidas


def guardar(ruta, filas, columnas=None):
    if columnas is None:
        columnas = list(filas[0])
    with ruta.open("w", encoding="utf-8", newline="") as archivo:
        salida = csv.DictWriter(archivo, fieldnames=columnas)
        salida.writeheader()
        salida.writerows(filas)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--datos", type=Path, default=Path(__file__).resolve().parent / "data")
    parser.add_argument("--salida", type=Path, default=Path("resultados_monitor"))
    conteo = parser.add_mutually_exclusive_group()
    conteo.add_argument("--excluir-fallos", dest="excluir_fallos", action="store_true",
                        help="Excluye errores y timeouts del ratio (valor por defecto).")
    conteo.add_argument("--contar-fallos", dest="excluir_fallos", action="store_false",
                        help="Incluye todos los intentos para comparar ambos criterios.")
    parser.set_defaults(excluir_fallos=True)
    args = parser.parse_args()
    consultas = [r for r in leer(args.datos, "consultas") if r["proveedor"] == "deltapay"]
    convenios = {r["convenio"] for r in consultas}
    pagos = [r for r in leer(args.datos, "pagos") if r["convenio"] in convenios]
    eventos = sorted(
        [(datetime.fromisoformat(r["timestamp"]), 1, r["consulta_id"], r) for r in consultas]
        + [(datetime.fromisoformat(r["fecha_pago"]), 0, r["pago_id"], r) for r in pagos]
    )
    historico = Counter(lunes(datetime.fromisoformat(r["timestamp"]).date()) for r in consultas
                        if not args.excluir_fallos or r["resultado"] not in FALLOS)
    propuesta, _, detecciones_base, _, _ = simular(eventos, args.excluir_fallos)
    monitor, por_semana, detecciones, controles, omitidas = simular(
        eventos, args.excluir_fallos, ajustar=True
    )

    args.salida.mkdir(parents=True, exist_ok=True)
    semanas = [INICIO + timedelta(weeks=i) for i in range((FIN - INICIO).days // 7 + 1)]
    resumen = []
    for semana in semanas:
        p = por_semana[semana]
        fila = {"semana": semana, "pagos": p}
        for nombre, conteo in [("historico", historico), ("propuesta", propuesta), ("monitor", monitor)]:
            q = conteo[semana]
            fila[f"consultas_{nombre}"] = q
            fila[f"ratio_{nombre}"] = round(q / p, 6) if p else None
            fila[f"cumple_{nombre}"] = q <= LIMITE * p if p else None
        resumen.append(fila)
    guardar(args.salida / "resumen_semanal.csv", resumen)
    guardar(args.salida / "controles_diarios.csv", controles)
    guardar(args.salida / "consultas_omitidas.csv", omitidas,
            ["fecha_hora", "semana", "consulta_id", "convenio", "cuenta",
             "intervalo_base_h", "motivo", "horas_adicionales"])

    cambios = []
    for clave, original in detecciones_base.items():
        convenio, cuenta, vence = clave
        nueva = detecciones.get(clave)
        if not INICIO <= original.date() <= FIN or nueva == original:
            continue
        cambios.append({
            "convenio": convenio, "cuenta": cuenta, "vencimiento": vence,
            "deteccion_base": original.isoformat(),
            "deteccion_monitor": nueva.isoformat() if nueva else None,
            "demora_h": round((nueva - original).total_seconds() / 3600, 2) if nueva else None,
            "margen_dias": (vence - nueva.date()).days if nueva else None,
        })
    guardar(args.salida / "impacto_deteccion.csv", cambios,
            ["convenio", "cuenta", "vencimiento", "deteccion_base",
             "deteccion_monitor", "demora_h", "margen_dias"])

    total_pagos = sum(por_semana[s] for s in semanas)
    for nombre in ("historico", "propuesta", "monitor"):
        q = sum(r[f"consultas_{nombre}"] for r in resumen)
        cumplen = sum(r[f"cumple_{nombre}"] is True for r in resumen)
        print(f"{nombre}: {q} consultas, {total_pagos} pagos, ratio {q / total_pagos:.2f}, "
              f"{cumplen}/{len(semanas)} semanas cumplen")
    niveles = Counter(r["nivel"] for r in controles if INICIO <= r["fecha"] <= FIN)
    print("Controles diarios:", dict(niveles))
    print("Días con ajuste:", sum(r["ajuste_activo"] for r in controles
                                  if INICIO <= r["fecha"] <= FIN))
    print("Intentos postergados por el monitor:", sum(r["horas_adicionales"] > 0
          for r in omitidas if INICIO <= r["semana"] <= FIN))
    print("Detecciones demoradas:", sum((r["demora_h"] or 0) > 0 for r in cambios))
    print("Detecciones ausentes:", sum(r["deteccion_monitor"] is None for r in cambios))
    print("Detecciones cambiadas en o después del vencimiento:",
          sum(r["margen_dias"] <= 0 for r in cambios if r["margen_dias"] is not None))


if __name__ == "__main__":
    main()
