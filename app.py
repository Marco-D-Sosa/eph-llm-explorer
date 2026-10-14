import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import create_sql_agent
from langchain_google_genai import ChatGoogleGenerativeAI
import os

# 1. Configuración de página y Secretos
st.set_page_config(page_title="EPH Query Engine", layout="wide")

# En local, esto requiere un archivo .streamlit/secrets.toml con: GEMINI_API_KEY="tu_clave"
# En Streamlit Cloud, se configura en la interfaz web de la plataforma.
if "GEMINI_API_KEY" not in st.secrets:
    st.error("Falta configurar GEMINI_API_KEY en los secretos de Streamlit.")
    st.stop()
    
os.environ["GOOGLE_API_KEY"] = st.secrets["GEMINI_API_KEY"]

# 2. Conexión segura a SQLite (Modo Solo Lectura)
# Cambia 'eph_limpia.db' por el nombre exacto del archivo que generó tu pipeline
db_path = "eph_limpia.db"
try:
    # uri=True y ?mode=ro evitan inyecciones que modifiquen la base de datos
    db = SQLDatabase.from_uri(f"sqlite:///file:{db_path}?mode=ro&uri=true")
except Exception as e:
    st.error(f"Error al conectar con la base de datos: {e}")
    st.stop()

# 3. Diccionario de Datos (Capa Semántica)
diccionario_eph = """
DICCIONARIO DE DATOS EPH (usa esto para mapear las preguntas de usuario a SQL):
- NRO_HOGAR / CODUSU: Identificadores únicos.
- CH04: Sexo (1 = Hombre, 2 = Mujer).
- CH06: Edad en años.
- ITF: Ingreso Total Familiar.
- ESTADO: Condición de actividad (1 = Ocupado, 2 = Desocupado, 3 = Inactivo).
- PONDERA: Ponderador poblacional (usar para calcular totales a nivel poblacional).
"""

# 4. Instanciación de Modelos
# Temperature 0 para SQL (precisión lógica) y 0.2 para código Python (leve flexibilidad)
llm_sql = ChatGoogleGenerativeAI(model="gemini-1.5-pro", temperature=0)
llm_graficos = ChatGoogleGenerativeAI(model="gemini-1.5-pro", temperature=0.2)

# 5. Configuración del Agente SQL
agente_sql = create_sql_agent(
    llm=llm_sql,
    db=db,
    agent_type="tool-calling",
    verbose=True,
    agent_executor_kwargs={"return_intermediate_steps": True},
    prefix=f"Eres un experto en econometría analizando la EPH. Escribe código SQL basado estrictamente en este diccionario: {diccionario_eph}"
)

# 6. Interfaz de Usuario
st.title("📊 Asistente de Datos EPH")
st.markdown("Genera consultas SQL y visualizaciones dinámicas sobre los microdatos ingresando texto plano.")

pregunta = st.text_input("¿Qué quieres saber de la base de datos?", placeholder="Ej: Promedio de ingreso (ITF) por sexo (CH04) en ocupados")

if st.button("Ejecutar Análisis") and pregunta:
    with st.spinner("Analizando la base de datos y diseñando la consulta..."):
        try:
            # Paso A: Traducir a SQL y ejecutar el análisis
            respuesta = agente_sql.invoke({"input": pregunta})
            
            st.write("### Conclusión")
            st.write(respuesta["output"])

            # Paso B: Extraer la query SQL exacta de los pasos intermedios de LangChain
            query_generada = None
            for action, observation in respuesta.get("intermediate_steps", []):
                if action.tool == "sql_db_query":
                    query_generada = action.tool_input
                    break
            
            # Paso C: Generación de gráfico en base a los resultados del SQL
            if query_generada:
                with st.expander("Ver código SQL ejecutado"):
                    st.code(query_generada, language="sql")
                    
                # Ejecutamos la query en Pandas para pasársela al LLM graficador
                conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
                df_resultado = pd.read_sql_query(query_generada, conn)
                conn.close()

                # Solo graficamos si hay más de una columna y datos útiles
                if not df_resultado.empty and len(df_resultado.columns) > 1:
                    st.write("### Datos Obtenidos")
                    st.dataframe(df_resultado.head(10))

                    prompt_grafico = f"""
                    Dada esta muestra de datos representados como un diccionario: {df_resultado.head().to_dict()}
                    Escribe SOLO código Python usando Plotly Express (importado como px) para crear el mejor gráfico que represente esta relación.
                    La figura resultante DEBE asignarse a una variable llamada 'fig'.
                    El DataFrame ya está cargado en memoria como 'df_resultado'. NO uses 'pd.read_csv', ni crees datos ficticios, ni uses 'show()'.
                    No incluyas markdown, ni bloques de código (```python), ni explicaciones. Devuelve únicamente el código Python crudo.
                    """
                    
                    st.write("### Visualización")
                    with st.spinner("Escribiendo código Plotly..."):
                        codigo_grafico_raw = llm_graficos.invoke(prompt_grafico).content
                        
                        # Limpieza por si el modelo incluye formato markdown
                        codigo_grafico = codigo_grafico_raw.replace("```python", "").replace("```", "").strip()
                        
                        # Entorno local seguro para el comando exec()
                        local_vars = {"pd": pd, "px": px, "df_resultado": df_resultado}
                        try:
                            exec(codigo_grafico, globals(), local_vars)
                            if "fig" in local_vars:
                                st.plotly_chart(local_vars["fig"], use_container_width=True)
                        except Exception as e_exec:
                            st.warning(f"No se pudo generar la visualización. Error en el código: {e_exec}")
                            with st.expander("Ver intento de código Python"):
                                st.code(codigo_grafico, language="python")
                else:
                    st.info("La consulta devolvió un valor escalar único. No se requiere visualización gráfica.")

        except Exception as e:
            st.error(f"Error general de ejecución: {e}")