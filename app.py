import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import os
import requests
import google.generativeai as genai
from sqlalchemy import create_engine

# 1. Configuración de página y Secretos
st.set_page_config(page_title="EPH AI Explorer", layout="wide")

if "GEMINI_API_KEY" not in st.secrets:
    st.error("Falta configurar GEMINI_API_KEY en los secretos de Streamlit.")
    st.stop()
    
# Configuración nativa de Google GenAI
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# Usamos el cliente nativo con el modelo más ágil
modelo_nativo = genai.GenerativeModel("gemini-flash-latest")

# 2. Configuración de descarga y caché de la base de datos
URL_DB = "https://github.com/Marco-D-Sosa/eph-llm-explorer/releases/download/v1.0/eph.db"
PATH_DB = "eph.db"

@st.cache_resource(show_spinner="Descargando microdatos de la EPH (200MB)... Esto solo tomará unos segundos la primera vez.")
def inicializar_base_datos():
    if not os.path.exists(PATH_DB):
        try:
            respuesta = requests.get(URL_DB, stream=True, timeout=60)
            respuesta.raise_for_status() 
            with open(PATH_DB, "wb") as archivo:
                for chunk in respuesta.iter_content(chunk_size=16384):
                    if chunk:
                        archivo.write(chunk)
        except Exception as e:
            st.error(f"Error al descargar la base de datos: {e}")
            raise e
    return PATH_DB

db_path = inicializar_base_datos()

# 3. Diccionario de Datos (Capa Semántica)
diccionario_eph = """
DICCIONARIO DE DATOS EPH. La base SQLite contiene 3 tablas principales:
1. 'individuos': Tabla principal con los microdatos poblacionales. Columnas clave:
   - codusu, nro_hogar, componente: Identificadores únicos.
   - ano4, trimestre: Año y trimestre de la encuesta.
   - ch04: Sexo (1 = Hombre, 2 = Mujer).
   - ch06: Edad en años.
   - itf: Ingreso Total Familiar.
   - ipcf: Ingreso Per Cápita Familiar.
   - pondera, pondih: Ponderadores poblacionales (usar siempre pondera o pondih para calcular totales o promedios representativos).
   - estado: Condición de actividad (1 = Ocupado, 2 = Desocupado, 3 = Inactivo).
   - region: Código de región geográfico (1 = GBA, 2 = Pampeana, 3 = Cuyo, 4 = Noroeste, 5 = Patagonia, 6 = Noreste).
2. 'canastas': Contiene los umbrales monetarios de las líneas oficiales de pobreza. Columnas clave:
   - ano, trimestre, region: Para cruzar temporal y regionalmente con individuos.
   - lp_extrema: Línea de indigencia (CBA).
   - lp_moderada: Línea de pobreza (CBT).
3. 'cargados': Tabla de control interno de trimestres procesados.
"""

# 6. Interfaz de Usuario y Lógica Directa Nativa
st.title("📊 EPH AI Explorer")
st.markdown("Consulta y grafica los microdatos de la Encuesta Permanente de Hogares usando lenguaje natural.")

pregunta = st.text_input("¿Qué quieres analizar?", placeholder="Ej: ¿Cuál es el ingreso promedio por sexo entre los ocupados?")

if st.button("Ejecutar Análisis") and pregunta:
    with st.spinner("Generando consulta SQL..."):
        try:
            prompt_sql = f"""
            Eres un experto en SQL y econometría analizando la EPH. 
            El esquema de la base de datos es el siguiente:
            {diccionario_eph}

            Escribe ÚNICAMENTE una consulta SQL válida y limpia en SQLite que responda a la siguiente pregunta.
            No incluyas bloques de código markdown, explicaciones, ni texto adicional. Devuelve solo la sentencia SQL pura.

            Pregunta del usuario: {pregunta}
            """
            
            # Llamada nativa directa sin hilos ni timeouts complejos de LangChain
            respuesta_llm = modelo_nativo.generate_content(prompt_sql)
            
            query_generada = respuesta_llm.text.replace("```sql", "").replace("```", "").strip()
            
            with st.expander("Ver código SQL generado"):
                st.code(query_generada, language="sql")

            # Ejecución local directa con Pandas
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            df_resultado = pd.read_sql_query(query_generada, conn)
            conn.close()

            if not df_resultado.empty:
                st.write("### Datos Obtenidos")
                st.dataframe(df_resultado.head(10))

                # Visualización opcional con Plotly si hay columnas cruzadas
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
                        res_grafico = modelo_nativo.generate_content(prompt_grafico)
                        codigo_grafico_raw = res_grafico.text.replace("```python", "").replace("```", "").strip()
                        
                        local_vars = {"pd": pd, "px": px, "df_resultado": df_resultado}
                        try:
                            exec(codigo_grafico_raw, globals(), local_vars)
                            if "fig" in local_vars:
                                st.plotly_chart(local_vars["fig"], use_container_width=True)
                        except Exception as e_exec:
                            st.warning(f"No se pudo renderizar el gráfico. Error: {e_exec}")
            else:
                st.warning("La consulta no arrojó resultados en la base de datos.")

        except Exception as e:
            st.error(f"Error de ejecución: {e}")
