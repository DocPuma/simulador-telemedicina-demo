# Simulador de Teleconsulta — MVP 0.3

Primer prototipo funcional del simulador académico de telemedicina.

## Qué hace esta versión

1. El estudiante inicia el caso TC-001.
2. Una IA representa al paciente con el Prompt Maestro del Paciente Humanizado.
3. El paciente sólo revela información clínica cuando es explorada, salvo la información espontánea definida en el caso.
4. El paciente no comprende automáticamente jerga médica no explicada.
5. El estudiante conversa libremente con el paciente.
6. Al finalizar, una segunda IA evalúa la transcripción completa.
7. La IA evaluadora asigna niveles y evidencia.
8. El programa calcula determinísticamente el puntaje 0–100 y aplica errores críticos.
9. El estudiante recibe un debriefing formativo sin códigos internos de rúbrica.
10. El docente puede habilitar una vista protegida de auditoría completa.
11. Cada resultado se guarda en la carpeta `resultados` y puede volver a abrirse
    desde el historial docente aunque se cierre o reinicie la sesión del navegador.

## Importante

Este MVP es exclusivamente académico y formativo.
No introduzca datos de pacientes reales.
No reemplaza atención médica ni sistemas institucionales.

# Instalación en Windows

No hace falta saber programar. Abra PowerShell o Terminal de Windows dentro de esta carpeta.

## 1. Crear un entorno virtual

```powershell
py -m venv .venv
```

Si `py` no funciona, pruebe:

```powershell
python -m venv .venv
```

## 2. Instalar los componentes

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 3. Crear el archivo de configuración

Ejecute:

```powershell
Copy-Item .env.example .env
notepad .env
```

Se abrirá el Bloc de notas.

Reemplace:

```text
OPENAI_API_KEY=pegue_aqui_su_clave
```

por su clave de API de OpenAI.

Guarde el archivo y cierre el Bloc de notas.

NO comparta el archivo `.env`.

Además de la clave de OpenAI, cambie esta línea:

```text
DOCENTE_CLAVE=cambie_esta_clave
```

por una contraseña docente larga. Esta contraseña habilita la vista de
auditoría después de finalizar cada simulación. Es una protección provisoria
para el piloto y no sustituye una autenticación institucional.

## 4. Ejecutar la aplicación

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Streamlit abrirá la aplicación en el navegador.
Si no se abre automáticamente, la terminal mostrará la dirección local, normalmente `http://localhost:8501`.

# Uso

1. Escriba nombre del estudiante e ID/matrícula.
2. Pulse `Iniciar teleconsulta`.
3. Converse libremente con el paciente.
4. Cuando considere que terminó, pulse `Finalizar y evaluar`.
5. Revise puntaje, nivel, seguridad clínica, fortalezas y aspectos a mejorar.
6. Despliegue las competencias para revisar la evidencia observable.

## Vista docente

Después de finalizar una simulación, el acceso docente aparece en la barra
lateral cuando `DOCENTE_CLAVE` está configurada.

La vista docente está disponible desde la barra lateral aun cuando no haya una
simulación abierta. Después de ingresar la clave, permite seleccionar cualquier
evaluación guardada en este equipo y revisar:

- resultado y motivos técnicos de no aprobación;
- puntajes y evidencia de los 15 criterios;
- errores críticos con sus códigos internos;
- transcripción completa;
- JSON del Evaluador IA y del motor determinístico;
- descarga del registro completo.

El botón para comenzar una nueva simulación requiere confirmación. Reiniciar la
interfaz no elimina los archivos ya guardados en `resultados`.

El estudiante no ve los códigos internos `EC-*`, el JSON técnico ni la
transcripción descargable.

# Estructura

- `app.py`: interfaz principal.
- `services.py`: llamadas a Paciente IA y Evaluador IA.
- `models.py`: estructura tipada de la evaluación.
- `engine.py`: cálculo determinístico de puntajes y seguridad.
- `cases/TC-001.json`: caso clínico.
- `prompts/paciente_global_v2.3.txt`: reglas transversales del paciente humanizado.
- `prompts/evaluador_global_v2.3.txt`: reglas transversales del evaluador.
- `storage.py`: guardado seguro y recuperación del historial docente.
- `VALIDACION_0.3.md`: escenarios comprobados, hallazgos y pruebas de regresión.
- `config/puntajes.json`: pesos y reglas de aprobación.
- `gold_standard/`: casos patrón usados en la validación interna.
- `resultados/`: evaluaciones producidas localmente.
- `tests/`: pruebas del motor, la configuración y la estructura de salida.

# Modelos

Por defecto:
- Paciente: `gpt-5.6-luna`
- Evaluador: `gpt-5.6-sol`

Puede cambiarlos editando `.env`.

# Alcance del MVP

Todavía no incluye:
- autenticación institucional;
- múltiples cursos;
- base de datos institucional o sincronización entre equipos;
- audio/video;
- evaluación multimodal;
- integración con Moodle;
- estadísticas por cohorte;
- control de costos por alumno.

Esas funciones pertenecen a fases posteriores.

## Validación local

Con el entorno virtual activo, ejecute:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Las pruebas verifican los tres perfiles del gold standard, la suma de la
rúbrica, el rechazo de errores críticos duplicados, la estructura estricta de
la salida del Evaluador IA, el historial local y los contratos de comportamiento
incorporados al paciente simulado.

## Cambios principales de la versión 0.3

- historial docente recuperable desde los archivos locales;
- acceso al panel docente aun después de perder la sesión del navegador;
- confirmación obligatoria antes de cerrar una simulación visible;
- resistencia reforzada a intentos de sacar al paciente de su rol;
- las instrucciones ajenas al rol no desbloquean información clínica condicional;
- las acciones simuladas no pueden quedar indefinidamente en espera;
- se incorporaron valores simulados definidos para termómetro y tensiómetro;
- respuesta reproductiva coherente para TC-001;
- el evaluador distingue evidencia observable de un examen neurológico completo;
- guardado atómico de los archivos JSON de resultados;
- nuevas pruebas de recuperación, reinicio seguro y contratos del paciente.

## Cambios principales de la versión 0.2

- separación entre vista del estudiante y panel docente;
- acceso docente mediante secreto configurable;
- consigna estudiantil sin revelar la conducta esperada del caso;
- traducción pedagógica de errores críticos para el alumno;
- salida estructurada más estricta, sin campos no definidos;
- llamadas a la API con `store=False`;
- nombres de archivo normalizados y sello temporal con microsegundos;
- nuevas pruebas automatizadas y validación de la configuración.
