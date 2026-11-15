# NOSTOS — INFORME DE CALIDAD Y PRUEBAS (QA)

**Responsable:** Investigación, QA e Integración  
**Fecha:** 15 de noviembre de 2026  
**Repositorio:** nostos-health-monitor

---

## 1. Objetivo

Documentar las verificaciones realizadas sobre el proyecto Nostos, comprobar el funcionamiento de las pruebas automatizadas y registrar los hallazgos identificados durante la revisión.

## 2. Entorno de pruebas

- Sistema operativo: Windows.
- Lenguaje de programación: Python 3.15.2.
- Framework de pruebas: pytest 9.2.0.
- Framework de aplicación: Streamlit.
- Editor utilizado: Visual Studio Code.
- Control de versiones: Git y GitHub Desktop.

## 3. Ejecución de pruebas automatizadas

Se ejecutó el siguiente comando:

    py -m pytest tests/ -v

### Resultados

**14 pruebas aprobadas y 0 fallidas.**

| Módulo | Pruebas aprobadas |
|---|---:|
| Diagnóstico | 5 |
| Integración | 2 |
| Telemetría | 7 |
| **Total** | **14** |

**Tiempo de ejecución:** 0.46 segundos.

### Verificaciones realizadas

- Validación de lecturas normales y valores esperados.
- Detección de niveles críticos de oxígeno en sangre.
- Validación de datos duplicados.
- Comprobación de compatibilidad entre ambiente e historial.
- Validación de la generación de telemetría.
- Comprobación de reproducibilidad de simulaciones.
- Verificación del flujo entre telemetría, diagnóstico e historial.
- Comprobación de estabilidad de identificadores de eventos.

## 4. Verificación de la aplicación

Se ejecutó el siguiente comando:

    py -m streamlit run app.py

La aplicación inició correctamente y permitió acceder al panel general de Nostos.

Se comprobó visualmente:

- Visualización de AST-01, AST-02 y AST-03.
- Presentación de indicadores de salud.
- Visualización de tarjetas individuales.
- Funcionamiento general del panel.

## 5. Hallazgos identificados

### H1. Alertas críticas durante el escenario de reposo

Se observó que los tres astronautas presentan estado crítico durante el escenario de reposo.

El origen de las alertas está pendiente de revisión por parte de los responsables del módulo correspondiente.

### H2. Contraste visual de los indicadores

Se identificó una posible dificultad de lectura en los valores numéricos de las tarjetas debido al bajo contraste entre el texto y el fondo.

### H3. Visualización de tendencias

Se observó una acumulación de puntos al final de algunas gráficas.

Se requiere investigar si está relacionada con los intervalos de actualización de la telemetría o con posibles lecturas duplicadas.

### H4. Historial de eventos

Se mantiene pendiente la revisión del comportamiento del historial cronológico de eventos y la conservación de alertas anteriores.

## 6. Estado de las actividades de QA

- [x] Configuración del entorno Python.
- [x] Instalación de dependencias de desarrollo.
- [x] Ejecución de pruebas automatizadas.
- [x] Verificación de telemetría.
- [x] Verificación del módulo de diagnóstico mediante pruebas.
- [x] Comprobación del flujo de integración mediante pruebas.
- [x] Inicio de la aplicación Streamlit.
- [x] Registro de hallazgos funcionales y visuales.
- [ ] Revisión del historial cronológico de eventos.
- [ ] Seguimiento de las correcciones realizadas por los responsables.
- [ ] Ejecución de pruebas de regresión después de las modificaciones.

## 7. Conclusión

Las 14 pruebas automatizadas existentes finalizaron satisfactoriamente en el entorno local. Asimismo, se comprobó que la aplicación puede iniciarse correctamente mediante Streamlit.

Durante la revisión visual se identificaron aspectos que requieren seguimiento, especialmente el comportamiento de las alertas durante el reposo, el contraste de los indicadores y la visualización de las tendencias.

Este informe documenta el estado de las verificaciones realizadas el 15 de noviembre de 2026. Los hallazgos pendientes no se consideran corregidos hasta completar su comprobación.

---