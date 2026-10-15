import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import os
import requests
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import create_sql_agent
from langchain_google_genai import ChatGoogleGenerativeAI

# 1. Configuración de página y Secretos
st.set_page_config(page_title="EPH AI Explorer", layout="wide")

if "GEMINI_API_KEY" not in st.secrets:
    st.error("Falta configurar GEMINI_API_KEY en los secretos de Streamlit.")
    st.stop()
    
os.environ["GOOGLE_API_KEY"] = st.secrets["GEMINI_API_KEY"]

# 2. Configuración de descarga y caché de la base de datos
URL_DB = "https://github.com/Marco-D-Sosa/eph-llm-explorer/releases/download/v1.0/eph.db"
PATH_DB = "eph.db"

@st.cache_resource(show_spinner="Descargando microdatos de la EPH (200MB)... Esto solo tomará unos segundos la primera vez.")
def inicializar_base_datos():
    if not os.path.exists(PATH_DB):
        respuesta = requests.get(URL_DB, stream=True)
        respuesta.raise_for_status() 
        
        with open(PATH_DB, "wb") as archivo:
            for chunk in respuesta.iter_content(chunk_size=8192):
                archivo.write(chunk)
                
    # Retorna la conexión en modo seguro de solo lectura
    return SQLDatabase.from_uri(f"sqlite:///file:{PATH_DB}?mode=ro&uri=true")

try:
    db = inicializar_base_datos()
except Exception as e:
    st.error(f"Error al descargar o conectar la base de datos: {e}")
    st.stop()

# 3. Diccionario de Datos (Capa Semántica)
diccionario_eph = """
DICCIONARIO DE DATOS EPH. La base SQLite contiene 3 tablas:
1. 'individuos': Tabla principal con los microdatos poblacionales. Columnas clave:
   - CODUSU / NRO_HOGAR: Identificadores únicos.
   - CH04: Sexo (1 = Hombre, 2 = Mujer).
   - CH06: Edad en años.
   - ITF: Ingreso Total Familiar.
   - ESTADO: Condición de actividad (1 = Ocupado, 2 = Desocupado, 3 = Inactivo).
   - PONDERA: Ponderador poblacional (usar siempre para calcular totales o promedios representativos).
2. 'canastas': Contiene los umbrales monetarios de las líneas de pobreza (CBA y CBT).
3. 'cargados': Tabla de control interno de los trimestres procesados.
"""

# 4. Instanciación de Modelos
llm_sql = ChatGoogleGenerativeAI(model="gemini-flash-latest", temperature=0)
llm_graficos = ChatGoogleGenerativeAI(model="gemini-flash-latest", temperature=0.2)

# 5. Configuración del Agente SQL
agente_sql = create_sql_agent(
    llm=llm_sql,
    db=db,
    agent_type="zero-shot-react-description",
    verbose=True,
    agent_executor_kwargs={
        "return_intermediate_steps": True, 
        "handle_parsing_errors": True # Agregado para mayor estabilidad
    },
    prefix=f"Eres un experto en econometría analizando la EPH. Escribe código SQL basado estrictamente en este diccionario: {diccionario_eph}"
)

# 6. Interfaz de Usuario
st.title("📊 EPH AI Explorer")
st.markdown("Consulta y grafica los microdatos de la Encuesta Permanente de Hogares usando lenguaje natural.")

pregunta = st.text_input("¿Qué quieres analizar?", placeholder="Ej: ¿Cuál es el ingreso promedio por sexo entre los ocupados?")

if st.button("Ejecutar Análisis") and pregunta:
    with st.spinner("Generando consulta SQL y procesando datos..."):
        try:
            # Paso 1: Una sola llamada directa al LLM para obtener estrictamente el SQL
            prompt_sql = f"""
            Eres un experto en SQL y econometría analizando la EPH. 
            El esquema de la base de datos es el siguiente:
            {diccionario_eph}

            Escribe ÚNICAMENTE una consulta SQL válida y limpia en SQLite que responda a la siguiente pregunta.
            No incluyas bloques de código markdown (como ```sql), explicaciones, ni texto adicional. Devuelve solo la sentencia SQL pura.

            Pregunta del usuario: {pregunta}
            """
            
            query_generada = llm_sql.invoke(prompt_sql).content.replace("```sql", "").replace("```", "").strip()
            
            with st.expander("Ver código SQL generado"):
                st.code(query_generada, language="sql")

            # Paso 2: Ejecución local directa con Pandas (Sin intermediarios lentos)
            conn = sqlite3.connect(f"file:{PATH_DB}?mode=ro", uri=True)
            df_resultado = pd.read_sql_query(query_generada, conn)
            conn.close()

            if not df_resultado.empty:
                # Paso 3: Generar conclusión textual basada en los resultados obtenidos
                prompt_conclusion = f"""
                A partir de la pregunta del usuario: "{pregunta}"
                Y los siguientes resultados obtenidos de la base de datos (mostrados como dataframe en formato dict): {df_resultado.head(15).to_dict()}
                Redacta una conclusión analítica clara y directa en español.
                """
                conclusion = llm_sql.invoke(prompt_conclusion).content
                
                st.write("### Conclusión")
                st.write(conclusion)

                st.write("### Datos Obtenidos")
                st.dataframe(df_resultado.head(10))

                # Paso 4: Visualización con Plotly
                if len(df_resultado.columns) > 1:
                    prompt_grafico = f"""
                    Dada esta muestra de datos: {df_resultado.head().to_dict()}
                    Escribe SOLO código Python usando Plotly Express (importado como px) para crear el gráfico adecuado.
                    La figura DEBE asignarse a una variable llamada 'fig'.
                    El DataFrame está en memoria como 'df_resultado'. NO uses 'fig.show()'.
                    Devuelve únicamente el código Python crudo sin markdown ni explicaciones.
                    """
                    
                    st.write("### Gráfico")
                    with st.spinner("Renderizando visualización..."):
                        codigo_grafico_raw = llm_graficos.invoke(prompt_grafico).content
                        codigo_grafico = codigo_grafico_raw.replace("```python", "").replace("```", "").strip()
                        
                        local_vars = {"pd": pd, "px": px, "df_resultado": df_resultado}
                        try:
                            exec(codigo_grafico, globals(), local_vars)
                            if "fig" in local_vars:
                                st.plotly_chart(local_vars["fig"], use_container_width=True)
                        except Exception as e_exec:
                            st.warning(f"No se pudo renderizar el gráfico. Error: {e_exec}")
            else:
                st.warning("La consulta no arrojó resultados en la base de datos.")

        except Exception as e:
            st.error(f"Error de ejecución: {e}")
