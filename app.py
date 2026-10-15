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
llm_sql = ChatGoogleGenerativeAI(model="gemini-3.5-flash", temperature=0)
llm_graficos = ChatGoogleGenerativeAI(model="gemini-3.5-flash", temperature=0.2)

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

pregunta = st.text_input("¿Qué quieres analizar?", placeholder="Ej: ¿Cuál es el ingreso promedio (ITF) por sexo (CH04) entre los ocupados?")

if st.button("Ejecutar Análisis") and pregunta:
    with st.spinner("Construyendo consulta SQL y analizando la base de datos..."):
        try:
            # Paso A: Generar SQL y extraer conclusión textual
            respuesta = agente_sql.invoke({"input": pregunta})
            
            st.write("### Conclusión")
            st.write(respuesta["output"])

            # Paso B: Extraer la query SQL
            query_generada = None
            for action, observation in respuesta.get("intermediate_steps", []):
                if action.tool == "sql_db_query":
                    query_generada = action.tool_input
                    break
            
            # Paso C: Visualización de datos
            if query_generada:
                with st.expander("Ver código SQL generado"):
                    st.code(query_generada, language="sql")
                    
                # Conexión independiente para que Pandas ejecute la query y recupere los datos
                conn = sqlite3.connect(f"file:{PATH_DB}?mode=ro", uri=True)
                df_resultado = pd.read_sql_query(query_generada, conn)
                conn.close()

                if not df_resultado.empty and len(df_resultado.columns) > 1:
                    st.write("### Datos Obtenidos")
                    st.dataframe(df_resultado.head(10))

                    # Generador de Plotly Express
                    prompt_grafico = f"""
                    Dada esta muestra de datos representados como un diccionario: {df_resultado.head().to_dict()}
                    Escribe SOLO código Python usando Plotly Express (importado como px) para crear el gráfico más adecuado para estos datos.
                    La figura resultante DEBE asignarse a una variable llamada 'fig'.
                    El DataFrame ya está en memoria como 'df_resultado'. NO crees datos ficticios ni uses 'fig.show()'.
                    No incluyas markdown, bloques de código, ni texto adicional. Devuelve únicamente el código Python crudo.
                    """
                    
                    st.write("### Gráfico")
                    with st.spinner("Renderizando visualización interactiva..."):
                        codigo_grafico_raw = llm_graficos.invoke(prompt_grafico).content
                        codigo_grafico = codigo_grafico_raw.replace("```python", "").replace("```", "").strip()
                        
                        local_vars = {"pd": pd, "px": px, "df_resultado": df_resultado}
                        try:
                            exec(codigo_grafico, globals(), local_vars)
                            if "fig" in local_vars:
                                st.plotly_chart(local_vars["fig"], use_container_width=True)
                        except Exception as e_exec:
                            st.warning(f"No se pudo renderizar la visualización de Plotly. Error: {e_exec}")
                            with st.expander("Ver el intento de código"):
                                st.code(codigo_grafico, language="python")
                else:
                    st.info("La consulta produjo un valor único (escalar) o no devolvió resultados para graficar.")

        except Exception as e:
            st.error(f"Error de ejecución: {e}")
