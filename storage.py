from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


def normalizar_segmento_archivo(valor: str) -> str:
    limpio = re.sub(r"[^A-Za-z0-9_-]+", "_", str(valor).strip())
    limpio = limpio.strip("_-")[:80]
    return limpio or "estudiante"


def validar_registro_basico(registro: Any) -> dict[str, Any]:
    if not isinstance(registro, dict):
        raise ValueError("El registro no es un objeto JSON.")

    requeridos = {
        "estudiante",
        "sesion",
        "transcripcion",
        "evaluacion_ia",
        "resultado_calculado",
    }
    faltantes = requeridos.difference(registro)
    if faltantes:
        raise ValueError(
            "El registro está incompleto: " + ", ".join(sorted(faltantes))
        )

    if not isinstance(registro["estudiante"], dict):
        raise ValueError("La sección estudiante no es válida.")
    if not isinstance(registro["sesion"], dict):
        raise ValueError("La sección sesión no es válida.")
    if not isinstance(registro["evaluacion_ia"], dict):
        raise ValueError("La evaluación estructurada no es válida.")
    if not isinstance(registro["resultado_calculado"], dict):
        raise ValueError("El resultado calculado no es válido.")

    return registro


def guardar_resultado(
    registro: dict[str, Any],
    carpeta: Path,
    ahora: datetime | None = None,
) -> Path:
    validar_registro_basico(registro)
    carpeta.mkdir(parents=True, exist_ok=True)

    instante = ahora or datetime.now()
    sello = instante.strftime("%Y%m%d_%H%M%S_%f")
    student_id = normalizar_segmento_archivo(registro["estudiante"].get("id", ""))
    caso_id = normalizar_segmento_archivo(registro["sesion"].get("caso_id", ""))
    destino = carpeta / f"{sello}_{student_id}_{caso_id}.json"
    temporal = destino.with_suffix(".json.tmp")

    temporal.write_text(
        json.dumps(registro, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporal.replace(destino)
    return destino


def cargar_resultado(path: Path, carpeta: Path) -> dict[str, Any]:
    carpeta_resuelta = carpeta.resolve()
    path_resuelto = path.resolve()

    if carpeta_resuelta not in path_resuelto.parents:
        raise ValueError("El archivo solicitado está fuera de la carpeta de resultados.")
    if path_resuelto.suffix.lower() != ".json":
        raise ValueError("El archivo seleccionado no es un registro JSON.")

    registro = json.loads(path_resuelto.read_text(encoding="utf-8"))
    return validar_registro_basico(registro)


def etiqueta_resultado(registro: dict[str, Any], path: Path) -> str:
    estudiante = registro.get("estudiante", {})
    sesion = registro.get("sesion", {})
    resultado = registro.get("resultado_calculado", {})

    fecha = str(sesion.get("fecha_hora", "")).replace("T", " ")[:19]
    nombre = str(estudiante.get("nombre", "Sin nombre")).strip() or "Sin nombre"
    student_id = str(estudiante.get("id", "Sin ID")).strip() or "Sin ID"
    caso = str(sesion.get("caso_id", "Sin caso")).strip() or "Sin caso"
    puntaje = resultado.get("puntaje_total", "?")

    if not fecha:
        fecha = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")

    return f"{fecha} — {nombre} ({student_id}) — {caso} — {puntaje}/100"


def listar_resultados(
    carpeta: Path,
    limite: int = 200,
) -> tuple[list[dict[str, Any]], list[str]]:
    if not carpeta.exists():
        return [], []

    archivos = sorted(
        carpeta.glob("*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )[:limite]

    validos: list[dict[str, Any]] = []
    errores: list[str] = []

    for path in archivos:
        try:
            registro = cargar_resultado(path, carpeta)
            validos.append(
                {
                    "nombre_archivo": path.name,
                    "path": path,
                    "etiqueta": etiqueta_resultado(registro, path),
                    "registro": registro,
                }
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errores.append(f"{path.name}: {exc}")

    return validos, errores
