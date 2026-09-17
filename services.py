from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from openai import OpenAI

from models import EvaluacionIA


def construir_instrucciones_paciente(
    prompt_global: str,
    caso: dict[str, Any],
) -> str:
    return (
        prompt_global
        + "\n\nCASO CLÍNICO ESPECÍFICO\n"
        + json.dumps(caso, ensure_ascii=False, indent=2)
        + "\n\nRepresenta exclusivamente a este paciente."
    )


def mensajes_para_api(historial: list[dict[str, str]]) -> list[dict[str, str]]:
    salida = []
    for mensaje in historial:
        if mensaje["role"] == "student":
            salida.append({"role": "user", "content": mensaje["content"]})
        elif mensaje["role"] == "patient":
            salida.append({"role": "assistant", "content": mensaje["content"]})
    return salida


def iniciar_paciente(
    client: OpenAI,
    model: str,
    prompt_global: str,
    caso: dict[str, Any],
) -> str:
    instrucciones = construir_instrucciones_paciente(prompt_global, caso)
    response = client.responses.create(
        model=model,
        reasoning={"effort": "low"},
        instructions=instrucciones,
        input=(
            "INICIO DE LA SIMULACIÓN. "
            "Inicia ahora como el paciente del caso. "
            "Usa sólo la información que el caso permite aportar espontáneamente. "
            "No saludes de forma artificialmente cordial si el estado clínico o "
            "emocional no lo justifica."
        ),
        store=False,
    )
    salida = response.output_text.strip()
    if not salida:
        raise ValueError("El Paciente IA no devolvió una respuesta.")
    return salida


def responder_como_paciente(
    client: OpenAI,
    model: str,
    prompt_global: str,
    caso: dict[str, Any],
    historial: list[dict[str, str]],
) -> str:
    instrucciones = construir_instrucciones_paciente(prompt_global, caso)
    response = client.responses.create(
        model=model,
        reasoning={"effort": "low"},
        instructions=instrucciones,
        input=mensajes_para_api(historial),
        store=False,
    )
    salida = response.output_text.strip()
    if not salida:
        raise ValueError("El Paciente IA no devolvió una respuesta.")
    return salida


def construir_transcripcion(historial: list[dict[str, str]]) -> str:
    lineas = []
    for mensaje in historial:
        etiqueta = "ESTUDIANTE" if mensaje["role"] == "student" else "PACIENTE"
        lineas.append(f"{etiqueta}: {mensaje['content']}")
    return "\n\n".join(lineas)


def evaluar_transcripcion(
    client: OpenAI,
    model: str,
    prompt_evaluador: str,
    caso: dict[str, Any],
    historial: list[dict[str, str]],
) -> dict[str, Any]:
    transcripcion = construir_transcripcion(historial)

    input_evaluacion = (
        "CASO CLÍNICO:\n"
        + json.dumps(caso, ensure_ascii=False, indent=2)
        + "\n\nTRANSCRIPCIÓN COMPLETA:\n"
        + transcripcion
        + "\n\nEvalúa los 15 criterios y TODOS los errores críticos definidos en el caso."
    )

    response = client.responses.parse(
        model=model,
        reasoning={"effort": "medium"},
        instructions=prompt_evaluador,
        input=input_evaluacion,
        text_format=EvaluacionIA,
        store=False,
    )

    parsed = response.output_parsed
    if parsed is None:
        raise ValueError("El Evaluador IA no devolvió una estructura válida.")

    return parsed.model_dump()
