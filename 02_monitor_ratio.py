"""Reproduce el control diario del ratio semanal de DeltaPay sobre los CSV."""
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


def simular(eventos, excluir_fallos):
    consultas, pagos = Counter(), Counter()
    controles, omitidas = [], []
    estado, detecciones = {}, {}
    dia_control = eventos[0][0].date()

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
        controles.append({
            "fecha": dia, "semana": semana, "consultas": q, "pagos": p,
            "ratio": ratio, "nivel": nivel,
        })

    for momento, tipo, identificador, fila in eventos:
        dia = momento.date()
        while dia_control <= dia:
            controlar(dia_control)
            dia_control += timedelta(days=1)

        semana = lunes(dia)
        convenio = fila["convenio"]
        cuenta = (convenio, fila["account_id"])
        if tipo == 0:
            pagos[semana] += 1
            consultas[semana] += 1  # Una revalidación individual por pago.
            estado.pop(cuenta, None)
            continue

        ultima, vence = estado.get(cuenta, (None, None))
        intervalo = 48
        if dia.day <= 14 and vence is None and convenio != "CONV-LUZ":
            intervalo = 72 if convenio == "CONV-TV" else 96
        motivo = None
        if vence is not None and dia < vence - timedelta(days=1):
            motivo = "Deuda conocida"
        elif vence is None and ultima is not None and momento - ultima < timedelta(hours=intervalo):
            motivo = "Intervalo de búsqueda"
        if motivo:
            omitidas.append({
                "fecha_hora": momento.isoformat(), "semana": semana, "consulta_id": identificador,
                "convenio": convenio, "cuenta": cuenta[1], "intervalo_base_h": intervalo,
                "motivo": motivo,
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
        estado[cuenta] = (momento, vence)

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
    propuesta, por_semana, _, controles, omitidas = simular(eventos, args.excluir_fallos)

    args.salida.mkdir(parents=True, exist_ok=True)
    semanas = [INICIO + timedelta(weeks=i) for i in range((FIN - INICIO).days // 7 + 1)]
    resumen = []
    for semana in semanas:
        p = por_semana[semana]
        fila = {"semana": semana, "pagos": p}
        for nombre, conteo in [("historico", historico), ("propuesta", propuesta)]:
            q = conteo[semana]
            fila[f"consultas_{nombre}"] = q
            fila[f"ratio_{nombre}"] = round(q / p, 6) if p else None
            fila[f"cumple_{nombre}"] = q <= LIMITE * p if p else None
        resumen.append(fila)
    guardar(args.salida / "resumen_semanal.csv", resumen)
    guardar(args.salida / "controles_diarios.csv", controles)
    guardar(args.salida / "consultas_omitidas.csv", omitidas,
            ["fecha_hora", "semana", "consulta_id", "convenio", "cuenta",
             "intervalo_base_h", "motivo"])

    total_pagos = sum(por_semana[s] for s in semanas)
    for nombre in ("historico", "propuesta"):
        q = sum(r[f"consultas_{nombre}"] for r in resumen)
        cumplen = sum(r[f"cumple_{nombre}"] is True for r in resumen)
        print(f"{nombre}: {q} consultas, {total_pagos} pagos, ratio {q / total_pagos:.2f}, "
              f"{cumplen}/{len(semanas)} semanas cumplen")
    niveles = Counter(r["nivel"] for r in controles if INICIO <= r["fecha"] <= FIN)
    print("Controles diarios:", dict(niveles))


if __name__ == "__main__":
    main()
