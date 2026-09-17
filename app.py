from __future__ import annotations

import hmac
import json
import os
from datetime import datetime
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

from engine import calcular_resultado
from services import (
    construir_transcripcion,
    evaluar_transcripcion,
    iniciar_paciente,
    responder_como_paciente,
)
from storage import guardar_resultado, listar_resultados, normalizar_segmento_archivo


BASE = Path(__file__).parent
load_dotenv(BASE / ".env")

VERSION_MVP = "0.3"
PATIENT_MODEL = os.getenv("OPENAI_MODEL_PATIENT", "gpt-5.6-luna")
EVALUATOR_MODEL = os.getenv("OPENAI_MODEL_EVALUATOR", "gpt-5.6-sol")

NOMBRES_AREA = {
    "encuadre_digital_y_seguridad": "Encuadre digital y seguridad",
    "anamnesis_clinica": "Anamnesis clínica",
    "comunicacion_remota": "Comunicación, escucha y empatía",
    "triaje_y_seguridad_clinica": "Triaje y seguridad clínica",
    "resolucion_clinica": "Resolución clínica",
}

NOMBRES_CRITERIO = {
    "E1_verificacion_identidad": "Verificación de identidad",
    "E2_ubicacion_fisica_actual": "Ubicación física actual",
    "E3_privacidad_y_contexto": "Privacidad y contexto",
    "E4_condiciones_tecnicas": "Condiciones técnicas",
    "A1_motivo_de_consulta": "Motivo de consulta",
    "A2_enfermedad_actual": "Enfermedad actual",
    "A3_antecedentes_relevantes": "Antecedentes relevantes",
    "A4_medicacion_y_alergias": "Medicación y alergias",
    "C1_claridad_comunicacional": "Claridad del lenguaje",
    "C2_escucha_activa": "Escucha activa",
    "C3_empatia_y_vinculo": "Empatía y vínculo",
    "T1_exploracion_signos_alarma": "Exploración de signos de alarma",
    "T2_reconocimiento_riesgo": "Reconocimiento del riesgo",
    "R1_decision_modalidad_asistencial": "Decisión sobre modalidad asistencial",
    "R2_justificacion_decision": "Justificación de la decisión",
}

MENSAJES_SEGURIDAD_ESTUDIANTE = {
    "EC-03": (
        "Seguridad clínica",
        "No quedó indicada con suficiente claridad la necesidad de una evaluación "
        "presencial urgente.",
    ),
    "EC-04": (
        "Conducta clínica",
        "Se mantuvo el manejo domiciliario o remoto como conducta principal cuando "
        "la situación requería evaluación presencial urgente.",
    ),
}

st.set_page_config(
    page_title="Simulador de Teleconsulta",
    page_icon="🩺",
    layout="centered",
)


def cargar_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def cargar_texto(path: Path):
    return path.read_text(encoding="utf-8")


def obtener_secreto(nombre: str) -> str:
    valor = os.getenv(nombre, "").strip()
    if valor:
        return valor

    try:
        valor_streamlit = st.secrets.get(nombre, "")
    except Exception:
        return ""

    return str(valor_streamlit).strip()


def obtener_client():
    api_key = obtener_secreto("OPENAI_API_KEY")
    if not api_key:
        return None
    return OpenAI(api_key=api_key)


def reset_simulacion():
    st.session_state.started = False
    st.session_state.finished = False
    st.session_state.messages = []
    st.session_state.evaluation_record = None
    st.session_state.teacher_authorized = False
    st.session_state.teacher_login_error = False
    st.session_state.reset_confirmation = False
    st.session_state.pop("teacher_history_selection", None)
    st.session_state.pop("teacher_password", None)


def solicitar_reset() -> None:
    st.session_state.reset_confirmation = True


def cancelar_reset() -> None:
    st.session_state.reset_confirmation = False


def procesar_login_docente(clave_correcta: str) -> None:
    clave_ingresada = str(st.session_state.get("teacher_password", ""))
    st.session_state.teacher_authorized = hmac.compare_digest(
        clave_ingresada.encode("utf-8"),
        clave_correcta.encode("utf-8"),
    )
    st.session_state.teacher_login_error = not st.session_state.teacher_authorized
    if st.session_state.teacher_authorized:
        st.session_state.reset_confirmation = False
    st.session_state.teacher_password = ""


def cerrar_vista_docente() -> None:
    st.session_state.teacher_authorized = False
    st.session_state.teacher_login_error = False
    st.session_state.pop("teacher_history_selection", None)
    st.session_state.pop("teacher_password", None)


def mostrar_control_reinicio() -> None:
    if not (st.session_state.started or st.session_state.finished):
        return

    st.divider()
    if not st.session_state.reset_confirmation:
        st.button(
            "Preparar nueva simulación",
            use_container_width=True,
            on_click=solicitar_reset,
        )
        return

    st.warning(
        "La conversación y el resultado visibles se cerrarán. "
        "Las evaluaciones ya guardadas permanecerán en el historial docente."
    )
    confirmar, cancelar = st.columns(2)
    confirmar.button(
        "Confirmar",
        type="primary",
        use_container_width=True,
        on_click=reset_simulacion,
    )
    cancelar.button(
        "Cancelar",
        use_container_width=True,
        on_click=cancelar_reset,
    )


def errores_detectados(evaluacion: dict) -> dict[str, dict]:
    return {
        error["codigo"]: error
        for error in evaluacion["errores_criticos"]
        if error["detectado"]
    }


def mostrar_desempeno_areas(resultado: dict, config: dict) -> None:
    st.subheader("Desempeño por área")
    for codigo, puntos in resultado["puntajes_por_area"].items():
        maximo = config["areas"][codigo]["maximo"]
        proporcion = puntos / maximo if maximo else 0
        st.write(f"**{NOMBRES_AREA.get(codigo, codigo)}:** {puntos} / {maximo}")
        st.progress(min(max(proporcion, 0.0), 1.0))


def mostrar_sintesis(evaluacion: dict) -> None:
    sintesis = evaluacion["sintesis"]
    st.subheader("Devolución pedagógica")

    st.markdown("**Puntos fuertes**")
    if sintesis["puntos_fuertes"]:
        for item in sintesis["puntos_fuertes"]:
            st.write(f"✓ {item}")
    else:
        st.write("No se identificaron fortalezas específicas en esta evaluación.")

    st.markdown("**Aspectos a mejorar**")
    if sintesis["aspectos_a_mejorar"]:
        for item in sintesis["aspectos_a_mejorar"]:
            st.write(f"• {item}")
    else:
        st.write("No se identificaron aspectos adicionales para mejorar.")

    st.markdown("**Recomendación**")
    st.write(sintesis["recomendacion_para_alumno"])


def mostrar_competencias_estudiante(
    evaluacion: dict,
    resultado: dict,
    config: dict,
) -> None:
    st.subheader("Evaluación por competencias")
    st.caption(
        "Puede desplegar cada competencia para revisar la evidencia observada "
        "durante la entrevista."
    )

    for codigo, datos in evaluacion["criterios"].items():
        puntos = resultado["puntajes_por_criterio"][codigo]
        regla = config["criterios"][codigo]
        maximo = max(float(valor) for valor in regla["niveles_puntos"].values())
        nombre = NOMBRES_CRITERIO.get(codigo, codigo)

        with st.expander(f"{nombre}: {puntos:g}/{maximo:g}"):
            st.write(datos["observacion"])
            if datos["evidencia"]:
                st.markdown("**Evidencia observable**")
                for evidencia in datos["evidencia"]:
                    st.write(f"• {evidencia}")


def mostrar_vista_estudiante(registro: dict, config: dict) -> None:
    resultado = registro["resultado_calculado"]
    evaluacion = registro["evaluacion_ia"]

    st.divider()
    st.header("Resultado de la simulación")

    c1, c2, c3 = st.columns(3)
    c1.metric("Puntaje", f"{resultado['puntaje_total']}/100")
    c2.metric("Nivel final", resultado["nivel_competencia_final"])
    c3.metric("Resultado", "APROBADO" if resultado["aprobado"] else "NO APROBADO")

    if resultado["aprobado"]:
        st.success("La simulación alcanzó los criterios requeridos.")
    else:
        st.error("La simulación no alcanzó todos los criterios requeridos.")

    if resultado["modificado_por_regla_seguridad"]:
        st.warning(
            "El nivel final fue limitado por un criterio de seguridad clínica. "
            f"Nivel por puntaje: {resultado['nivel_por_puntaje']} → "
            f"nivel final: {resultado['nivel_competencia_final']}."
        )

    detectados = errores_detectados(evaluacion)
    for codigo, (titulo, mensaje) in MENSAJES_SEGURIDAD_ESTUDIANTE.items():
        if codigo in detectados:
            st.warning(f"**{titulo}**\n\n{mensaje}")

    if resultado["motivos_no_aprobacion"]:
        st.subheader("Motivos generales del resultado")
        reglas = config["reglas_aprobacion"]
        if resultado["puntaje_total"] < reglas["puntaje_minimo"]:
            st.write(
                f"• El puntaje fue inferior al mínimo requerido "
                f"({reglas['puntaje_minimo']}/100)."
            )
        if resultado["criterios_obligatorios_incumplidos"]:
            st.write(
                "• Una o más competencias obligatorias de seguridad no alcanzaron "
                "el nivel mínimo."
            )
        if resultado["errores_criticos_mayores"]:
            st.write("• Se detectó una omisión clínica de seguridad de nivel mayor.")
        if len(resultado["errores_criticos_otros"]) > reglas[
            "maximo_errores_criticos_no_mayores_para_aprobar"
        ]:
            st.write("• Se superó el máximo admitido de omisiones de seguridad menores.")

    mostrar_desempeno_areas(resultado, config)
    mostrar_sintesis(evaluacion)
    mostrar_competencias_estudiante(evaluacion, resultado, config)


def mostrar_vista_docente(registro: dict, config: dict) -> None:
    resultado = registro["resultado_calculado"]
    evaluacion = registro["evaluacion_ia"]

    st.divider()
    st.header("Panel docente")
    st.caption("Vista de auditoría de la simulación")

    tab_resultado, tab_criterios, tab_transcripcion, tab_tecnico = st.tabs(
        ["Resultado", "Criterios", "Transcripción", "Datos técnicos"]
    )

    with tab_resultado:
        c1, c2, c3 = st.columns(3)
        c1.metric("Puntaje", f"{resultado['puntaje_total']}/100")
        c2.metric("Nivel final", resultado["nivel_competencia_final"])
        c3.metric(
            "Resultado",
            "APROBADO" if resultado["aprobado"] else "NO APROBADO",
        )

        st.write(
            "**Cumple puntaje mínimo:**",
            "Sí"
            if resultado["puntaje_total"]
            >= config["reglas_aprobacion"]["puntaje_minimo"]
            else "No",
        )
        st.write(
            "**Nivel modificado por seguridad:**",
            "Sí" if resultado["modificado_por_regla_seguridad"] else "No",
        )

        if resultado["motivos_no_aprobacion"]:
            st.subheader("Motivos de no aprobación")
            for motivo in resultado["motivos_no_aprobacion"]:
                st.write(f"• {motivo}")

        mostrar_desempeno_areas(resultado, config)
        mostrar_sintesis(evaluacion)

        st.subheader("Errores críticos")
        for error in evaluacion["errores_criticos"]:
            estado = "DETECTADO" if error["detectado"] else "No detectado"
            st.markdown(
                f"**{error['codigo']} — {error['severidad']} — {estado}**"
            )
            st.write(error["observacion"])
            st.caption(f"Evidencia: {error['evidencia']}")

    with tab_criterios:
        for codigo, datos in evaluacion["criterios"].items():
            puntos = resultado["puntajes_por_criterio"][codigo]
            regla = config["criterios"][codigo]
            maximo = max(float(valor) for valor in regla["niveles_puntos"].values())
            nombre = NOMBRES_CRITERIO.get(codigo, codigo)

            with st.expander(
                f"{codigo} — {nombre}: nivel {datos['nivel']} — "
                f"{puntos:g}/{maximo:g} puntos"
            ):
                st.write(datos["observacion"])
                if datos["evidencia"]:
                    st.markdown("**Evidencia identificada por el Evaluador IA**")
                    for evidencia in datos["evidencia"]:
                        st.write(f"• {evidencia}")

    with tab_transcripcion:
        st.subheader("Transcripción completa")
        st.text(registro["transcripcion"])

    with tab_tecnico:
        st.subheader("Salida estructurada del Evaluador IA")
        st.json(evaluacion)
        st.subheader("Resultado del motor determinístico")
        st.json(resultado)
        st.download_button(
            "Descargar registro completo en JSON",
            data=json.dumps(registro, ensure_ascii=False, indent=2),
            file_name=(
                f"{normalizar_segmento_archivo(registro['estudiante']['id'])}_"
                f"{normalizar_segmento_archivo(registro['sesion']['caso_id'])}_"
                "evaluacion.json"
            ),
            mime="application/json",
            use_container_width=True,
        )


def autenticar_docente() -> bool:
    if st.session_state.teacher_authorized:
        return True

    clave_correcta = obtener_secreto("DOCENTE_CLAVE")
    if not clave_correcta:
        return False

    with st.sidebar:
        st.divider()
        st.subheader("Acceso docente")
        st.text_input(
            "Clave docente",
            type="password",
            key="teacher_password",
        )
        st.button(
            "Ingresar como docente",
            use_container_width=True,
            on_click=procesar_login_docente,
            args=(clave_correcta,),
        )
        if st.session_state.teacher_login_error:
            st.error("Clave incorrecta.")

    return False


def mostrar_historial_docente(config: dict) -> None:
    guardados, errores = listar_resultados(BASE / "resultados")

    opciones: dict[str, dict] = {}
    etiquetas: dict[str, str] = {}

    if st.session_state.finished and st.session_state.evaluation_record:
        clave_actual = "__sesion_actual__"
        opciones[clave_actual] = st.session_state.evaluation_record
        actual = st.session_state.evaluation_record
        estudiante = actual["estudiante"]
        resultado = actual["resultado_calculado"]
        etiquetas[clave_actual] = (
            "Sesión actual — "
            f"{estudiante['nombre']} ({estudiante['id']}) — "
            f"{resultado['puntaje_total']}/100"
        )

    for item in guardados:
        clave = f"archivo:{item['nombre_archivo']}"
        opciones[clave] = item["registro"]
        etiquetas[clave] = item["etiqueta"]

    with st.sidebar:
        st.header("Panel docente")
        st.success("Vista docente activa")
        st.button(
            "Cerrar vista docente",
            use_container_width=True,
            on_click=cerrar_vista_docente,
        )

        st.divider()
        st.subheader("Historial de evaluaciones")

        if not opciones:
            st.info("Todavía no hay evaluaciones guardadas.")
            if errores:
                st.warning(
                    f"No se pudieron leer {len(errores)} archivo(s) de resultados."
                )
            return

        claves = list(opciones)
        seleccion_previa = st.session_state.get("teacher_history_selection")
        if seleccion_previa not in opciones:
            st.session_state.teacher_history_selection = claves[0]

        seleccion = st.selectbox(
            "Evaluación",
            options=claves,
            format_func=lambda clave: etiquetas[clave],
            key="teacher_history_selection",
        )
        st.caption(f"{len(guardados)} registro(s) guardado(s) en este equipo.")

        if errores:
            st.warning(
                f"Se omitieron {len(errores)} archivo(s) dañado(s) o incompleto(s)."
            )

    mostrar_vista_docente(opciones[seleccion], config)


for key, default in {
    "started": False,
    "finished": False,
    "messages": [],
    "evaluation_record": None,
    "teacher_authorized": False,
    "teacher_login_error": False,
    "reset_confirmation": False,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


caso = cargar_json(BASE / "cases" / "TC-001.json")
config = cargar_json(BASE / "config" / "puntajes.json")
prompt_paciente = cargar_texto(BASE / "prompts" / "paciente_global_v2.3.txt")
prompt_evaluador = cargar_texto(BASE / "prompts" / "evaluador_global_v2.3.txt")
client = obtener_client()


st.title("🩺 Simulador de Teleconsulta")
st.caption(f"MVP académico {VERSION_MVP} — entrenamiento formativo con paciente virtual")

if not st.session_state.teacher_authorized:
    with st.sidebar:
        st.header("Sesión")
        estudiante_nombre = st.text_input("Nombre del estudiante", key="student_name")
        estudiante_id = st.text_input("ID / matrícula", key="student_id")
        st.text_input("Caso", value=caso["caso_id"], disabled=True)

        st.divider()
        st.caption(f"Paciente IA: {PATIENT_MODEL}")
        st.caption(f"Evaluador IA: {EVALUATOR_MODEL}")

        if client is None:
            st.error("Falta configurar OPENAI_API_KEY.")

        mostrar_control_reinicio()
else:
    estudiante_nombre = str(st.session_state.get("student_name", ""))
    estudiante_id = str(st.session_state.get("student_id", ""))


acceso_docente = autenticar_docente()

if acceso_docente:
    mostrar_historial_docente(config)
else:
    st.info(
        "Simulación académica. Trabaje únicamente con pacientes ficticios. "
        "No introduzca datos de pacientes reales."
    )

    if not st.session_state.started:
        st.subheader(f"Caso {caso['caso_id']}")
        st.write(
            "**Consigna:** realice una teleconsulta completa como lo haría en una "
            "situación clínica. Explore los aspectos que considere necesarios y tome "
            "una decisión asistencial fundamentada. Cuando finalice, pulse "
            "**Finalizar y evaluar**."
        )

        puede_iniciar = bool(
            estudiante_nombre.strip() and estudiante_id.strip() and client
        )

        if st.button(
            "Iniciar teleconsulta",
            type="primary",
            disabled=not puede_iniciar,
            use_container_width=True,
        ):
            with st.spinner("Iniciando paciente simulado..."):
                try:
                    primera_respuesta = iniciar_paciente(
                        client, PATIENT_MODEL, prompt_paciente, caso
                    )
                    st.session_state.messages = [
                        {"role": "patient", "content": primera_respuesta}
                    ]
                    st.session_state.started = True
                    st.session_state.finished = False
                    st.session_state.evaluation_record = None
                    st.session_state.reset_confirmation = False
                    st.rerun()
                except Exception as exc:
                    st.error(f"No se pudo iniciar la simulación: {exc}")

    if st.session_state.started:
        for mensaje in st.session_state.messages:
            role = "user" if mensaje["role"] == "student" else "assistant"
            label = "Estudiante" if role == "user" else "Paciente"
            with st.chat_message(role):
                st.markdown(f"**{label}:** {mensaje['content']}")

        if not st.session_state.finished:
            entrada = st.chat_input("Escriba su intervención clínica...")

            if entrada:
                st.session_state.messages.append(
                    {"role": "student", "content": entrada.strip()}
                )

                with st.spinner("Paciente respondiendo..."):
                    try:
                        respuesta = responder_como_paciente(
                            client,
                            PATIENT_MODEL,
                            prompt_paciente,
                            caso,
                            st.session_state.messages,
                        )
                        st.session_state.messages.append(
                            {"role": "patient", "content": respuesta}
                        )
                        st.rerun()
                    except Exception as exc:
                        st.error(f"No se pudo obtener respuesta del paciente: {exc}")

            st.divider()

            if st.button(
                "Finalizar y evaluar",
                type="primary",
                use_container_width=True,
            ):
                if not any(
                    m["role"] == "student" for m in st.session_state.messages
                ):
                    st.warning(
                        "Debe realizar al menos una intervención antes de evaluar."
                    )
                else:
                    with st.spinner("Evaluando la entrevista completa..."):
                        try:
                            evaluacion_ia = evaluar_transcripcion(
                                client,
                                EVALUATOR_MODEL,
                                prompt_evaluador,
                                caso,
                                st.session_state.messages,
                            )

                            resultado = calcular_resultado(
                                evaluacion_ia,
                                config,
                                caso,
                            )

                            registro = {
                                "version_esquema": "2.0",
                                "version_mvp": VERSION_MVP,
                                "estudiante": {
                                    "id": estudiante_id.strip(),
                                    "nombre": estudiante_nombre.strip(),
                                },
                                "sesion": {
                                    "caso_id": caso["caso_id"],
                                    "fecha_hora": datetime.now()
                                    .astimezone()
                                    .isoformat(),
                                    "finalidad": caso["finalidad"],
                                    "modelos": {
                                        "paciente": PATIENT_MODEL,
                                        "evaluador": EVALUATOR_MODEL,
                                    },
                                },
                                "transcripcion": construir_transcripcion(
                                    st.session_state.messages
                                ),
                                "evaluacion_ia": evaluacion_ia,
                                "resultado_calculado": resultado,
                            }

                            guardar_resultado(registro, BASE / "resultados")
                            st.session_state.evaluation_record = registro
                            st.session_state.finished = True
                            st.rerun()
                        except Exception as exc:
                            st.error(f"No se pudo completar la evaluación: {exc}")

    if st.session_state.finished and st.session_state.evaluation_record:
        mostrar_vista_estudiante(st.session_state.evaluation_record, config)
        st.caption(
            "Para comenzar otra consulta, utilice "
            "**Preparar nueva simulación** en la barra lateral."
        )
