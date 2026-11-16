"""Monitor del ratio de DeltaPay.

Qué mira: consultas computables y pagos confirmados atribuidos a DeltaPay.
El ratio incluye una revalidación por pago y excluye errores y timeouts por defecto.

Frecuencia: simula un control al comienzo de cada día con el acumulado
de la semana en curso, de lunes a domingo.

Umbrales: con ratio de 5 o más se aplica el ajuste preventivo. El 5 deja
una consulta por pago de margen antes del límite de 6. Si supera 6,
se escala a Operaciones. También se escala si hay consultas y cero pagos,
porque en ese caso el ratio queda indefinido.

Cupo de contingencia: del 1 al 7, si el ratio llega a 5 o hay consultas
sin pagos, Operaciones puede aprobar un cupo para las búsquedas programadas
pendientes hasta el domingo. El cupo se aplica solo con esa aprobación.
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


def intervalo_busqueda(dia, convenio):
    if dia.day <= 14 and convenio != "CONV-LUZ":
        return 72 if convenio == "CONV-TV" else 96
    return 48


def simular(eventos, excluir_fallos, ajustar=False, cupos=None):
    consultas, pagos = Counter(), Counter()
    controles, omitidas = [], []
    estado, detecciones = {}, {}
    dia_control = eventos[0][0].date()

    restringido = False
    agenda_diaria = {}
    seleccion = set()
    cupos_diarios = {}
    for aprobacion, presupuesto in (cupos or {}).items():
        dias_restantes = 7 - aprobacion.weekday()
        base, resto = divmod(presupuesto, dias_restantes)
        for indice in range(dias_restantes):
            cupos_diarios[aprobacion + timedelta(days=indice)] = base + (indice < resto)
    if cupos_diarios:
        for momento, tipo, identificador, fila in eventos:
            dia = momento.date()
            if tipo == 1 and dia in cupos_diarios and fila["origen"] == "programada":
                cuenta = (fila["convenio"], fila["account_id"])
                agenda_diaria.setdefault(dia, {}).setdefault(cuenta, (momento, identificador))

    def seleccionar_busquedas(dia):
        cupo = cupos_diarios[dia]
        if cupo == 0:
            return set()
        elegidas = set()
        for cuenta, (momento, identificador) in agenda_diaria.get(dia, {}).items():
            ultima, vence, respuesta = estado.get(cuenta, (None, None, None))
            convenio = cuenta[0]
            intervalo = intervalo_busqueda(dia, convenio)
            if restringido and respuesta == "sin_deuda" and convenio != "CONV-LUZ":
                intervalo += 24
            if vence is None and (ultima is None or momento - ultima >= timedelta(hours=intervalo)):
                elegidas.add(identificador)
                if len(elegidas) == cupo:
                    break
        return elegidas

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
            "revision_reforzada": dia.day <= 7,
            "revisar_cupo": dia.day <= 7 and (nivel in {"preventiva", "límite alcanzado", "escalar"}),
            "cupo_busquedas_dia": cupos_diarios.get(dia),
        })

        return aplicar

    for momento, tipo, identificador, fila in eventos:
        dia = momento.date()
        while dia_control <= dia:
            restringido = controlar(dia_control)
            if dia_control in cupos_diarios:
                seleccion = seleccionar_busquedas(dia_control)
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
        intervalo = intervalo_busqueda(dia, convenio) if vence is None else 48
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
        if motivo is None and dia in cupos_diarios and vence is None and identificador not in seleccion:
            motivo = "Cupo diario de búsquedas"
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
    parser.add_argument("--desde", type=date.fromisoformat, default=INICIO,
                        help="Primer lunes del período a evaluar.")
    parser.add_argument("--hasta", type=date.fromisoformat, default=FIN,
                        help="Último domingo del período a evaluar.")
    parser.add_argument("--aprobar-cupo", action="append", default=[], metavar="AAAA-MM-DD=CUPO",
                        help="Cupo aprobado al inicio de ese día, hasta el domingo.")
    conteo = parser.add_mutually_exclusive_group()
    conteo.add_argument("--excluir-fallos", dest="excluir_fallos", action="store_true",
                        help="Excluye errores y timeouts del ratio (valor por defecto).")
    conteo.add_argument("--contar-fallos", dest="excluir_fallos", action="store_false",
                        help="Incluye todos los intentos para comparar ambos criterios.")
    parser.set_defaults(excluir_fallos=True)
    args = parser.parse_args()
    desde, hasta = args.desde, args.hasta
    if desde.weekday() != 0 or hasta.weekday() != 6 or desde > hasta:
        parser.error("--desde y --hasta deben delimitar semanas completas, de lunes a domingo.")
    cupos = {}
    for opcion in args.aprobar_cupo:
        fecha, _, cupo = opcion.partition("=")
        try:
            aprobacion = date.fromisoformat(fecha)
            presupuesto = int(cupo)
        except ValueError:
            parser.error("--aprobar-cupo requiere AAAA-MM-DD=CUPO.")
        semana = lunes(aprobacion)
        if aprobacion.day > 7 or not desde <= semana <= hasta:
            parser.error("La aprobación debe caer del 1 al 7 en una semana del período.")
        if presupuesto < 0 or any(lunes(dia) == semana for dia in cupos):
            parser.error("Indicá un cupo no negativo y una sola aprobación por semana.")
        cupos[aprobacion] = presupuesto
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

    escenarios = [("historico", historico), ("propuesta", propuesta), ("monitor", monitor)]
    if cupos:
        con_cupo, _, detecciones_cupo, controles_cupo, omitidas_cupo = simular(
            eventos, args.excluir_fallos, ajustar=True, cupos=cupos
        )
        escenarios.append(("cupo", con_cupo))

    args.salida.mkdir(parents=True, exist_ok=True)
    semanas = [desde + timedelta(weeks=i) for i in range((hasta - desde).days // 7 + 1)]
    resumen = []
    for semana in semanas:
        p = por_semana[semana]
        fila = {"semana": semana, "pagos": p}
        for nombre, conteo in escenarios:
            q = conteo[semana]
            fila[f"consultas_{nombre}"] = q
            fila[f"ratio_{nombre}"] = round(q / p, 6) if p else None
            fila[f"cumple_{nombre}"] = q <= LIMITE * p if p else None
        resumen.append(fila)
    guardar(args.salida / "resumen_semanal.csv", resumen)
    guardar(args.salida / "controles_diarios.csv", controles)
    columnas_omitidas = ["fecha_hora", "semana", "consulta_id", "convenio", "cuenta",
                         "intervalo_base_h", "motivo", "horas_adicionales"]
    guardar(args.salida / "consultas_omitidas.csv", omitidas, columnas_omitidas)

    cambios = []
    for clave, original in detecciones_base.items():
        convenio, cuenta, vence = clave
        nueva = detecciones.get(clave)
        if not desde <= original.date() <= hasta or nueva == original:
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

    if cupos:
        aprobaciones = {lunes(dia): dia for dia in cupos}
        impacto = []
        for (convenio, cuenta, vence), original in detecciones.items():
            dia = original.date()
            semana = lunes(dia)
            aprobacion = aprobaciones.get(semana)
            if aprobacion is None or dia < aprobacion:
                continue
            nueva = detecciones_cupo.get((convenio, cuenta, vence))
            if nueva is None:
                estado_cupo = "sin detección posterior observable"
            elif lunes(nueva.date()) > semana:
                estado_cupo = "detectada en una semana posterior"
            else:
                estado_cupo = "detectada hasta el cierre de la semana"
            impacto.append({
                "semana": semana, "convenio": convenio, "cuenta": cuenta, "vencimiento": vence,
                "deteccion_monitor": original.isoformat(),
                "deteccion_cupo": nueva.isoformat() if nueva else None,
                "estado": estado_cupo,
            })
        guardar(args.salida / "impacto_deteccion_cupo.csv", impacto,
                ["semana", "convenio", "cuenta", "vencimiento", "deteccion_monitor", "deteccion_cupo", "estado"])
        guardar(args.salida / "controles_diarios_cupo.csv", controles_cupo)
        guardar(args.salida / "consultas_omitidas_cupo.csv", omitidas_cupo, columnas_omitidas)

        for fila in resumen:
            semana = fila["semana"]
            if semana in aprobaciones:
                print(f"Semana {semana}: {fila['consultas_cupo']} consultas, "
                      f"{fila['pagos']} pagos, ratio {fila['ratio_cupo']}")
        for semana, aprobacion in sorted(aprobaciones.items()):
            estados = Counter(r["estado"] for r in impacto if r["semana"] == semana)
            print(f"Detecciones del monitor desde la aprobación del {aprobacion} hasta el cierre:", dict(estados))

    total_pagos = sum(por_semana[s] for s in semanas)
    for nombre, _ in escenarios:
        q = sum(r[f"consultas_{nombre}"] for r in resumen)
        cumplen = sum(r[f"cumple_{nombre}"] is True for r in resumen)
        print(f"{nombre}: {q} consultas, {total_pagos} pagos, ratio {(q / total_pagos if total_pagos else float('nan')):.2f}, "
              f"{cumplen}/{len(semanas)} semanas cumplen")
    niveles = Counter(r["nivel"] for r in controles if desde <= r["fecha"] <= hasta)
    print("Controles diarios:", dict(niveles))
    print("Días con ajuste:", sum(r["ajuste_activo"] for r in controles
                                  if desde <= r["fecha"] <= hasta))
    print("Intentos postergados por el monitor:", sum(r["horas_adicionales"] > 0
          for r in omitidas if desde <= r["semana"] <= hasta))
    print("Detecciones demoradas:", sum((r["demora_h"] or 0) > 0 for r in cambios))
    print("Detecciones ausentes:", sum(r["deteccion_monitor"] is None for r in cambios))
    print("Detecciones cambiadas en o después del vencimiento:",
          sum(r["margen_dias"] <= 0 for r in cambios if r["margen_dias"] is not None))


if __name__ == "__main__":
    main()
