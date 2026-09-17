from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class ModeloEstricto(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Criterio02(ModeloEstricto):
    nivel: Literal[0, 1, 2]
    evidencia: list[str] = Field(default_factory=list, max_length=3)
    observacion: str


class Criterio03(ModeloEstricto):
    nivel: Literal[0, 1, 2, 3]
    evidencia: list[str] = Field(default_factory=list, max_length=3)
    observacion: str


class CriteriosEvaluacion(ModeloEstricto):
    E1_verificacion_identidad: Criterio02
    E2_ubicacion_fisica_actual: Criterio02
    E3_privacidad_y_contexto: Criterio02
    E4_condiciones_tecnicas: Criterio02

    A1_motivo_de_consulta: Criterio02
    A2_enfermedad_actual: Criterio02
    A3_antecedentes_relevantes: Criterio02
    A4_medicacion_y_alergias: Criterio02

    C1_claridad_comunicacional: Criterio03
    C2_escucha_activa: Criterio03
    C3_empatia_y_vinculo: Criterio03

    T1_exploracion_signos_alarma: Criterio02
    T2_reconocimiento_riesgo: Criterio02

    R1_decision_modalidad_asistencial: Criterio02
    R2_justificacion_decision: Criterio02


class ErrorCritico(ModeloEstricto):
    codigo: str = Field(pattern=r"^EC-[0-9]{2}$")
    detectado: bool
    severidad: Literal["menor", "mayor"]
    evidencia: str
    observacion: str


class SintesisPedagogica(ModeloEstricto):
    puntos_fuertes: list[str] = Field(default_factory=list, max_length=5)
    aspectos_a_mejorar: list[str] = Field(default_factory=list, max_length=5)
    recomendacion_para_alumno: str


class EvaluacionIA(ModeloEstricto):
    criterios: CriteriosEvaluacion
    errores_criticos: list[ErrorCritico]
    sintesis: SintesisPedagogica
