# Nostos

## Descripción del proyecto

NOSTOS es una aplicación web concebida para vigilar de manera integral la salud física y psicológica de los tripulantes durante misiones espaciales de larga duración, ya sea a bordo de estaciones orbitales o en las futuras bases de exploración en Marte.

A través de un panel de control centralizado, el sistema permite visualizar, evaluar y registrar los principales indicadores biomédicos y de bienestar de una tripulación simulada de tres astronautas. De este modo, facilita tanto el seguimiento individual como la observación del estado general del equipo, la detección temprana de posibles anomalías y la emisión de alertas visuales acompañadas de recomendaciones preventivas.

La aplicación contempla cuatro áreas principales de monitoreo: sistema cardiovascular, salud ósea, composición muscular y bienestar psicológico. Para ello, utiliza datos biomédicos simulados que permiten representar distintos escenarios operativos, como períodos de reposo, actividad física y situaciones de emergencia controlada

### Plantemiento de la problematica 

Las misiones espaciales de larga duración exponen a los astronautas a condiciones como la microgravedad, la radiación, el confinamiento y el aislamiento, que pueden provocar alteraciones progresivas en su salud cardiovascular, ósea, muscular y psicológica.

Este desafío aumenta en futuras misiones a Marte, donde la distancia respecto a la Tierra, los retrasos en las comunicaciones y las dificultades de evacuación médica hacen necesario que los astronautas tengan mayor autonomía para supervisar su propio estado de salud.

Entre las principales dificultades se encuentran la fragmentación de la información médica, la dependencia del apoyo terrestre y la necesidad de identificar oportunamente anomalías en los indicadores de salud.

Ante esta situación, surge NOSTOS, una propuesta de monitoreo integral que busca centralizar la información física y psicológica de la tripulación, facilitar la identificación de posibles anomalías y generar alertas y recomendaciones preventivas mediante una interfaz visual e intuitiva.

## Funcionalidades principales

NOSTOS contará con los siguientes módulos funcionales, diseñados para facilitar la supervisión, evaluación y seguimiento de las condiciones de salud de la tripulación durante las misiones espaciales.

 1. Panel general de tripulación

Proporciona una vista centralizada del estado de salud de los tres astronautas (AST-01, AST-02 y AST-03). Permite visualizar simultáneamente sus indicadores principales, identificar posibles anomalías y reconocer rápidamente qué integrantes requieren atención.

2. Selector de astronautas

Permite seleccionar individualmente a cada integrante de la tripulación para consultar su información biomédica, estado de salud, indicadores específicos y registros históricos. Cada astronauta dispone de un perfil independiente, con sus propias lecturas y eventos registrados.

 3. Selector de ambiente operativo

Permite alternar entre los dos entornos contemplados por el sistema:

- **Estación espacial:** representa las condiciones de operación de una misión en microgravedad.
- **Base en Marte:** representa las condiciones de una misión prolongada en la superficie marciana.

La selección del ambiente permite adaptar los escenarios y criterios de simulación al contexto operativo correspondiente.

4. Selector de escenarios de simulación

Permite configurar las condiciones bajo las cuales se generan los datos biomédicos de la tripulación:

- **Reposo:** representa el comportamiento de los indicadores durante períodos de baja actividad física.
- **Actividad física/EVA:** simula las variaciones fisiológicas asociadas al ejercicio, al trabajo físico y a las actividades extravehiculares.
- **Emergencia simulada:** introduce anomalías controladas en determinados indicadores para comprobar la capacidad del sistema de detectar alteraciones y generar alertas.

Los escenarios estarán diseñados para producir resultados reproducibles y facilitar las pruebas funcionales del sistema.

 5. Selector de frecuencia de actualización

Permite configurar el intervalo de actualización de los datos simulados mediante cuatro opciones: 5, 15, 30 y 60 segundos. La frecuencia predeterminada será de 30 segundos, equivalente a dos actualizaciones por minuto.

El sistema deberá conservar el historial de lecturas durante las actualizaciones y evitar cambios bruscos en variables que presentan una evolución fisiológica más lenta, como la composición corporal y el sueño acumulado.

 6. Panel de monitoreo cardiovascular

Presenta los principales indicadores relacionados con el funcionamiento del sistema cardiovascular de cada astronauta:

- Frecuencia cardíaca (BPM).
- Saturación periférica de oxígeno (SpO₂).
- Temperatura corporal (°C).
- Presión arterial sistólica y diastólica (mmHg).

Permite observar los valores registrados, identificar desviaciones respecto a los criterios de referencia y visualizar su evolución mediante indicadores y gráficas.

 7. Panel de seguimiento óseo y muscular

Integra indicadores relacionados con la actividad física y la composición corporal para facilitar el seguimiento de las condiciones musculoesqueléticas de la tripulación.

Incluye:

- Nivel de actividad física.
- Minutos de ejercicio durante las últimas 24 horas.
- Tiempo dedicado al entrenamiento de resistencia.
- Masa muscular estimada (kg).
- Porcentaje de grasa corporal.
- Índice estimado de riesgo de deterioro óseo.

Los indicadores de salud ósea serán estimaciones simuladas basadas en variables de actividad y ejercicio, ya que el sistema no dispone de mediciones directas de densidad mineral ósea. Las variaciones de composición corporal deberán mantener una evolución gradual y coherente.

 8. Panel de bienestar psicológico

Permite realizar un seguimiento de indicadores relacionados con el bienestar psicológico de cada astronauta mediante registros de autopercepción y descanso.

Incluye:

- Nivel de estrés percibido, en una escala de 0 a 10.
- Estado de ánimo, en una escala de 0 a 10.
- Horas de sueño durante las últimas 24 horas.

La información permitirá observar tendencias y variaciones en el bienestar individual durante la misión, sin utilizarse para establecer diagnósticos de trastornos psicológicos.

 9. Centro de alertas y recomendaciones

Centraliza las anomalías identificadas por el motor de diagnóstico y presenta información sobre los parámetros que requieren atención.

Cada alerta deberá incluir:

- Identificación del astronauta afectado.
- Parámetro que presenta la anomalía.
- Valor detectado y unidad de medida.
- Criterio o rango de referencia utilizado.
- Nivel de gravedad asignado.
- Descripción de la situación identificada.
- Acción preventiva o recomendación correspondiente.

Las alertas se clasificarán mediante un sistema visual de tres niveles:

- **Verde — Normal:** parámetros dentro de los criterios establecidos.
- **Amarillo — Precaución:** valores que requieren seguimiento o atención.
- **Rojo — Crítico:** anomalías que requieren atención prioritaria.

10. Historial de eventos de salud

Permite consultar los eventos registrados durante la simulación, incluyendo lecturas relevantes, anomalías detectadas y alertas generadas.

El historial estará organizado por astronauta y fecha, facilitando la revisión de acontecimientos anteriores, la identificación de patrones y el seguimiento de la evolución de los indicadores durante la misión.

11. Gráficas y visualización de tendencias

Proporciona representaciones gráficas interactivas de los indicadores biomédicos para facilitar el análisis de su comportamiento a lo largo del tiempo.

Las gráficas permitirán:

- Consultar la evolución histórica de los parámetros.
- Identificar variaciones y tendencias individuales.
- Comparar diferentes períodos de observación.
- Reconocer visualmente posibles desviaciones.
- Mantener los registros históricos durante las actualizaciones de la simulación.

Estas visualizaciones complementarán los paneles de monitoreo y facilitarán la interpretación de la información presentada por el sistema.

