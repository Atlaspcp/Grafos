import streamlit as st
import json
import networkx as nx
from pyvis.network import Network
import tempfile
import os
import re

# =========================
# Configuración de Página
# =========================
st.set_page_config(page_title="Sociometría Interactiva", layout="wide")

# =========================
# Constantes y Estilos
# =========================
COLORES_CURSO = {
    "Curso 1": "#FFFF00",  # Amarillo
    "Curso 2": "#90EE90",  # Verde Claro
    "Curso 3": "#ADD8E6"   # Azul Claro
}

COLORES_POPULAR = {
    "Curso 1": "#FFD700",  # Dorado
    "Curso 2": "#32CD32",  # Verde Lima
    "Curso 3": "#1E90FF"   # Azul Rey
}

# =========================
# Funciones de Utilidad
# =========================
def normalizar_nombre(nombre):
    if not nombre: return "DESCONOCIDO"
    nombre = re.sub(r'\(.*?\)', '', nombre)
    nombre = re.sub(r'\s+', ' ', nombre.strip()).upper()
    return nombre

def cargar_desde_carpeta(ruta_carpeta, nombre_curso):
    data_parcial = {}
    if not os.path.exists(ruta_carpeta):
        return data_parcial

    archivos = [f for f in os.listdir(ruta_carpeta) if f.endswith('.json')]
    
    for archivo in archivos:
        ruta_completa = os.path.join(ruta_carpeta, archivo)
        try:
            with open(ruta_completa, 'r', encoding='utf-8') as f:
                contenido = json.load(f)
                
            nombre_completo = contenido.get("Nombre")
            ranking = contenido.get("Seleccion_Jerarquica", {}) 

            if nombre_completo:
                origen = normalizar_nombre(nombre_completo)
                conexiones_con_ranking = {}
                for k, v in ranking.items():
                    nombre_dest = normalizar_nombre(k)
                    try:
                        valor_rank = int(v) 
                    except:
                        valor_rank = 99 
                    conexiones_con_ranking[nombre_dest] = valor_rank

                data_parcial[origen] = {
                    "curso": nombre_curso,
                    "conexiones": conexiones_con_ranking, 
                    "raw_ranking": ranking
                }
        except Exception as e:
            st.sidebar.error(f"Error en {archivo}: {e}")
            
    return data_parcial

# =========================
# Interfaz Principal
# =========================
st.title("🕸️ Grafo de Sociometría - Visualizador Web")

# --- Barra Lateral: Carga ---
with st.sidebar:
    st.header("📂 1. Carga de Datos")
    
    ruta_c1 = st.text_input("Carpeta Curso 1", value=os.path.join("respuestas", "curso1"))
    ruta_c2 = st.text_input("Carpeta Curso 2", value=os.path.join("respuestas", "curso2"))
    ruta_c3 = st.text_input("Carpeta Curso 3", value=os.path.join("respuestas", "curso3"))

    if st.button("🔄 Cargar Carpetas"):
        st.session_state['datos_grafo'] = {}
        d1 = cargar_desde_carpeta(ruta_c1, "Curso 1")
        d2 = cargar_desde_carpeta(ruta_c2, "Curso 2")
        d3 = cargar_desde_carpeta(ruta_c3, "Curso 3")
        
        st.session_state['datos_grafo'].update(d1)
        st.session_state['datos_grafo'].update(d2)
        st.session_state['datos_grafo'].update(d3)
        
        total = len(st.session_state['datos_grafo'])
        if total > 0:
            st.success(f"Cargados {total} alumnos en memoria.")
        else:
            st.error("No se encontraron alumnos.")

    st.markdown("---")
    st.header("👥 2. Selección de Alumnos")
    
    # Lógica para extraer listas de alumnos cargados
    datos = st.session_state.get('datos_grafo', {})
    
    # Filtramos los nombres por curso basándonos en los datos cargados
    nombres_c1 = sorted([n for n, d in datos.items() if d['curso'] == "Curso 1"])
    nombres_c2 = sorted([n for n, d in datos.items() if d['curso'] == "Curso 2"])
    nombres_c3 = sorted([n for n, d in datos.items() if d['curso'] == "Curso 3"])

    seleccionados_finales = []

    # --- Selector Curso 1 ---
    with st.expander("Ver Integrantes Curso 1", expanded=True):
        activar_c1 = st.checkbox("Mostrar Curso 1", value=True)
        if activar_c1 and nombres_c1:
            sel_c1 = st.multiselect("Seleccionar alumnos C1:", nombres_c1, default=nombres_c1)
            seleccionados_finales.extend(sel_c1)
        elif activar_c1 and not nombres_c1:
            st.caption("(No hay datos cargados para Curso 1)")

    # --- Selector Curso 2 ---
    with st.expander("Ver Integrantes Curso 2", expanded=False):
        activar_c2 = st.checkbox("Mostrar Curso 2", value=False)
        if activar_c2 and nombres_c2:
            sel_c2 = st.multiselect("Seleccionar alumnos C2:", nombres_c2, default=nombres_c2)
            seleccionados_finales.extend(sel_c2)
        elif activar_c2 and not nombres_c2:
            st.caption("(No hay datos cargados para Curso 2)")

    # --- Selector Curso 3 ---
    with st.expander("Ver Integrantes Curso 3", expanded=False):
        activar_c3 = st.checkbox("Mostrar Curso 3", value=False)
        if activar_c3 and nombres_c3:
            sel_c3 = st.multiselect("Seleccionar alumnos C3:", nombres_c3, default=nombres_c3)
            seleccionados_finales.extend(sel_c3)
        elif activar_c3 and not nombres_c3:
            st.caption("(No hay datos cargados para Curso 3)")

    st.markdown("---")
    st.subheader("🎯 Opciones de Vista")
    max_ranking = st.slider("Afinidad (Ranking 1-10):", 1, 10, 10)
    
    st.markdown("---")
    physics_enabled = st.toggle("Activar Movimiento Automático", value=True)

# --- Área de Visualización ---
if not datos:
    st.info("👈 Carga los datos para comenzar.")
else:
    # Convertimos la lista de seleccionados a un SET para búsqueda rápida
    whitelist_nombres = set(seleccionados_finales)

    G = nx.DiGraph()
    
    # 1. Nodos: Solo agregamos los que estén en la whitelist
    for nombre, info in datos.items():
        if nombre in whitelist_nombres:
            G.add_node(nombre, group=info['curso'], title=f"Curso: {info['curso']}")

    # 2. Aristas: Solo si Origen Y Destino están en la whitelist (y cumplen ranking)
    mutuas_procesadas = set()

    for nombre, info in datos.items():
        # Si el alumno origen fue deseleccionado, saltamos
        if nombre not in whitelist_nombres: 
            continue
            
        for destino, ranking_val in info['conexiones'].items():
            if ranking_val > max_ranking: continue 

            # Verificamos que el DESTINO también esté seleccionado para verse
            if destino in whitelist_nombres:
                
                curso_destino = datos[destino]['curso']
                
                # Clave única para mutuas
                par_alumnos = tuple(sorted((nombre, destino)))
                if par_alumnos in mutuas_procesadas:
                    continue

                # Aseguramos nodo (aunque ya debería estar por el paso 1)
                if not G.has_node(destino):
                    G.add_node(destino, group=curso_destino, title=f"Curso: {curso_destino}")
                
                # Detección de reciprocidad
                es_mutua = False
                datos_destino = datos.get(destino, {})
                ranking_retorno = datos_destino.get('conexiones', {}).get(nombre)
                
                if ranking_retorno and ranking_retorno <= max_ranking:
                    es_mutua = True
                
                G.add_edge(nombre, destino, weight=ranking_val, mutua=es_mutua)
                
                if es_mutua:
                    mutuas_procesadas.add(par_alumnos)

    # Renderizado
    if len(G.nodes()) == 0:
        st.warning("No hay alumnos visibles. Revisa los selectores o carga los datos.")
    else:
        in_degrees = dict(G.in_degree())
        
        net = Network(height="750px", width="100%", bgcolor="#ffffff", font_color="black", directed=True)
        
        for node in G.nodes():
            curso = G.nodes[node].get('group', 'Desconocido')
            popularidad = in_degrees.get(node, 0)
            
            size = 15 + (popularidad * 4)
            color_fondo = COLORES_CURSO.get(curso, "#eeeeee")
            if popularidad >= 3:
                color_fondo = COLORES_POPULAR.get(curso, color_fondo)
                
            label = node
            if popularidad > 4: label += " 👑"
            
            title_html = f"<b>{node}</b><br>Curso: {curso}<br>Votos: {popularidad}"
            net.add_node(node, label=label, title=title_html, color=color_fondo, size=size)

        for u, v, data in G.edges(data=True):
            es_mutua = data.get('mutua', False)
            
            if es_mutua:
                net.add_edge(u, v, color="red", width=3, arrows="to;from")
            else:
                rank = data.get('weight', '?')
                color_linea = "#cccccc"
                if rank == 1: color_linea = "#666666"
                
                net.add_edge(u, v, color=color_linea, width=1, dashes=True, arrows="to")

        if physics_enabled:
            net.barnes_hut(gravity=-2000, central_gravity=0.3, spring_length=120)
        else:
            net.toggle_physics(False)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp:
            net.save_graph(tmp.name)
            with open(tmp.name, 'r', encoding='utf-8') as f:
                html_bytes = f.read()
                
        st.components.v1.html(html_bytes, height=770, scrolling=False)
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Alumnos en Pantalla", len(G.nodes()))
        c2.metric("Conexiones Visibles", len(G.edges()))
        c3.metric("Relaciones Mutuas", len(mutuas_procesadas))
