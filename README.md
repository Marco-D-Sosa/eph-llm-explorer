# 📊 EPH AI Explorer: Asistente Analítico de Microdatos

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://eph-llm-explorer.streamlit.app/)

Prueba la aplicación en vivo aquí: **[EPH AI Explorer](https://eph-llm-explorer.streamlit.app/)**

## 🎯 Sobre el Proyecto

EPH AI Explorer es una interfaz interactiva de análisis y visualización de datos diseñada para democratizar el acceso a los microdatos de la Encuesta Permanente de Hogares (EPH - INDEC). 

A diferencia de los dashboards tradicionales —que limitan al usuario a filtros y gráficos predefinidos—, esta herramienta integra Inteligencia Artificial (Google Gemini) para traducir preguntas de negocio en lenguaje natural a código SQL estructurado. El resultado es una plataforma de análisis *ad-hoc* donde los tomadores de decisiones pueden explorar la base de datos, extraer insights y generar visualizaciones complejas de forma dinámica e instantánea.

Este proyecto destaca la evolución de la presentación de datos: pasar de reportes estáticos a experiencias analíticas conversacionales, manteniendo el rigor metodológico del tratamiento de datos estructurados.

## 💡 Propuesta de Valor Analítico

El enfoque central de este desarrollo es el **Análisis de Datos y la Comunicación Visual**:

*   **Consultas Dinámicas (Text-to-SQL):** Permite a usuarios sin conocimientos técnicos interrogar una base de datos compleja (millones de registros) escribiendo sus preguntas en español.
*   **Visualización Automática (Plotly):** Dependiendo de la estructura de la consulta generada, la aplicación interpreta los resultados y renderiza gráficos interactivos para facilitar la comprensión de las tendencias.
*   **Rigor Metodológico Integrado:** El modelo está condicionado por un diccionario semántico estricto para aplicar correctamente los ponderadores poblacionales (`PONDERA`, `PONDIH`) y las líneas de pobreza oficiales (`lp_moderada`, `lp_extrema`), asegurando que las inferencias estadísticas sean válidas.
*   **Arquitectura Desacoplada y Escalable:** De base, la aplicación está conectada a los microdatos de la EPH mediante el dataset procesado en mi proyecto previo **[SQL EPH ETL Pipeline](https://github.com/Marco-D-Sosa/SQL-eph-etl-pipeline)**. Gracias a su diseño modular, con un pequeño cambio en el código, el sistema puede modificarse fácilmente para realizar consultas sobre cualquier otra base de datos o conectarse a otros modelos de inteligencia artificial según la necesidad del negocio.

## 🛠️ Stack Tecnológico

*   **Lenguaje:** Python
*   **Interfaz de Usuario:** Streamlit
*   **Modelado y Manipulación de Datos:** Pandas, SQL (SQLite)
*   **Visualización:** Plotly Express
*   **Integración IA:** SDK Nativo de Google Generative AI (Modelos familia Gemini Flash)

## 🚀 Instalación y Uso Local

Si deseas correr este proyecto en tu propio entorno y explorar el código, sigue estos pasos:

1. **Clonar el repositorio:**
   ```bash
   git clone [https://github.com/Marco-D-Sosa/eph-llm-explorer.git](https://github.com/Marco-D-Sosa/eph-llm-explorer.git)
   cd eph-llm-explorer
   ```
2. **Instalar dependencias:**
   ```bash
   pip install -r requirements.txt
   ```
3. **Configurar la API Key:**

Crea una carpeta oculta llamada .streamlit en la raíz del proyecto.

Dentro de esa carpeta, crea un archivo secrets.toml.

Agrega tu clave de Google AI Studio con el siguiente formato:
```bash
GEMINI_API_KEY = "tu_clave_api_aqui"
```
4. **Ejecutar la aplicación:**

```bash
   streamlit run app.py
```
