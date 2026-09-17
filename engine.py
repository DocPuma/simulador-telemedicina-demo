from __future__ import annotations

from collections import defaultdict
from typing import Any


ORDEN_NIVELES = ["Insuficiente", "En desarrollo", "Competente", "Sobresaliente"]


def nivel_por_puntaje(total: float, niveles: list[dict[str, Any]]) -> str:
    for tramo in niveles:
        desde = float(tramo["desde"])
        limite_exclusivo = tramo.get("hasta_menor_que")
        limite_inclusivo = tramo.get("hasta_inclusive")

        dentro_del_tramo = total >= desde
        if limite_exclusivo is not None:
            dentro_del_tramo = dentro_del_tramo and total < float(limite_exclusivo)
        if limite_inclusivo is not None:
            dentro_del_tramo = dentro_del_tramo and total <= float(limite_inclusivo)

        if dentro_del_tramo:
            return str(tramo["nivel"])

    raise ValueError(f"El puntaje {total} no pertenece a ningún nivel configurado.")


def validar_errores_criticos(evaluacion: dict[str, Any], caso: dict[str, Any]) -> None:
    esperados = {e["codigo"]: e["severidad"] for e in caso["errores_criticos"]}
    lista_codigos = [e["codigo"] for e in evaluacion["errores_criticos"]]

    if len(lista_codigos) != len(set(lista_codigos)):
        raise ValueError("La evaluación contiene códigos de error crítico duplicados.")

    recibidos = {
        e["codigo"]: e["severidad"] for e in evaluacion["errores_criticos"]
    }

    if set(esperados) != set(recibidos):
        faltan = sorted(set(esperados) - set(recibidos))
        sobran = sorted(set(recibidos) - set(esperados))
        raise ValueError(
            f"Códigos de errores críticos inconsistentes. Faltan={faltan}; sobran={sobran}"
        )

    for codigo, severidad in esperados.items():
        if recibidos[codigo] != severidad:
            raise ValueError(
                f"Severidad incorrecta para {codigo}: "
                f"esperada={severidad}, recibida={recibidos[codigo]}"
            )


def calcular_resultado(
    evaluacion: dict[str, Any],
    config: dict[str, Any],
    caso: dict[str, Any],
) -> dict[str, Any]:
    """
    Convierte niveles asignados por el Evaluador IA en un resultado determinístico.
    La IA no decide el puntaje ni la aprobación.
    """
    validar_errores_criticos(evaluacion, caso)

    criterios = evaluacion["criterios"]
    puntajes_area: dict[str, float] = defaultdict(float)
    detalle_puntos: dict[str, float] = {}

    for codigo, regla in config["criterios"].items():
        if codigo not in criterios:
            raise ValueError(f"Falta el criterio obligatorio: {codigo}")

        nivel = str(criterios[codigo]["nivel"])
        niveles_validos = regla["niveles_puntos"]

        if nivel not in niveles_validos:
            raise ValueError(f"Nivel inválido {nivel} para {codigo}")

        puntos = float(niveles_validos[nivel])
        detalle_puntos[codigo] = puntos
        puntajes_area[regla["area"]] += puntos

    total = round(sum(puntajes_area.values()), 2)
    bruto = nivel_por_puntaje(total, config["niveles_competencia"])

    errores_mayores = [
        e["codigo"]
        for e in evaluacion["errores_criticos"]
        if e["detectado"] and e["severidad"] == "mayor"
    ]
    errores_otros = [
        e["codigo"]
        for e in evaluacion["errores_criticos"]
        if e["detectado"] and e["severidad"] != "mayor"
    ]

    reglas = config["reglas_aprobacion"]
    obligatorios = reglas["criterios_obligatorios"]
    errores_mayores_bloquean = bool(
        reglas.get("error_critico_mayor_bloquea_aprobacion", True)
    )

    faltantes_obligatorios = [
        codigo
        for codigo, minimo in obligatorios.items()
        if criterios[codigo]["nivel"] < minimo
    ]

    aprobado = (
        total >= reglas["puntaje_minimo"]
        and not faltantes_obligatorios
        and not (errores_mayores and errores_mayores_bloquean)
        and len(errores_otros)
        <= reglas["maximo_errores_criticos_no_mayores_para_aprobar"]
    )

    final = bruto
    tope_mayor = reglas["tope_nivel_si_error_critico_mayor"]
    tope_otros = reglas["tope_nivel_si_dos_o_mas_errores_criticos_no_mayores"]
    if errores_mayores and ORDEN_NIVELES.index(final) > ORDEN_NIVELES.index(tope_mayor):
        final = tope_mayor
    elif (
        len(errores_otros) >= 2
        and ORDEN_NIVELES.index(final) > ORDEN_NIVELES.index(tope_otros)
    ):
        final = tope_otros

    motivos = []
    if total < reglas["puntaje_minimo"]:
        motivos.append("Puntaje total inferior al mínimo de aprobación.")
    if faltantes_obligatorios:
        motivos.append(
            "No cumple criterios obligatorios de seguridad: "
            + ", ".join(faltantes_obligatorios)
            + "."
        )
    if errores_mayores and errores_mayores_bloquean:
        motivos.append(
            "Presenta errores críticos mayores: "
            + ", ".join(errores_mayores)
            + "."
        )
    if len(errores_otros) > reglas["maximo_errores_criticos_no_mayores_para_aprobar"]:
        motivos.append("Presenta dos o más errores críticos no mayores.")

    return {
        "fuente_calculo": "motor_deterministico",
        "puntajes_por_area": {
            nombre: round(float(puntajes_area.get(nombre, 0)), 2)
            for nombre in config["areas"]
        },
        "puntajes_por_criterio": detalle_puntos,
        "puntaje_total": total,
        "nivel_por_puntaje": bruto,
        "nivel_competencia_final": final,
        "nivel_competencia": final,
        "modificado_por_regla_seguridad": final != bruto,
        "aprobado": aprobado,
        "errores_criticos_mayores": errores_mayores,
        "errores_criticos_otros": errores_otros,
        "criterios_obligatorios_incumplidos": faltantes_obligatorios,
        "motivos_no_aprobacion": motivos,
    }
