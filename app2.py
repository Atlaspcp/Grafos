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
    # Verificación silenciosa: si no existe la carpeta, retorna vacío sin error visual
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
        except Exception:
            # Ignoramos errores de lectura individuales para no ensuciar la UI
            pass
            
    return data_parcial

# =========================
# Lógica de Carga Automática (State)
# =========================
if 'datos_grafo' not in st.session_state:
    st.session_state['datos_grafo'] = {}
    
    # Rutas por defecto (Hardcoded según tu estructura)
    path_c1 = os.path.join("respuestas", "curso1")
    path_c2 = os.path.join("respuestas", "curso2")
    path_c3 = os.path.join("respuestas", "curso3")
    
    d1 = cargar_desde_carpeta(path_c1, "Curso 1")
    d2 = cargar_desde_carpeta(path_c2, "Curso 2")
    d3 = cargar_desde_carpeta(path_c3, "Curso 3")
    
    st.session_state['datos_grafo'].update(d1)
    st.session_state['datos_grafo'].update(d2)
    st.session_state['datos_grafo'].update(d3)

# =========================
# Interfaz Principal
# =========================
st.title("🕸️ Grafo de Sociometría")

datos = st.session_state.get('datos_grafo', {})

# --- Barra Lateral: Selección de Alumnos ---
with st.sidebar:
    st.header("👥 Filtro de Alumnos")
    st.write("Selecciona los estudiantes que deseas visualizar.")
    
    # Listas maestras de nombres disponibles en los datos cargados
    nombres_c1 = sorted([n for n, d in datos.items() if d['curso'] == "Curso 1"])
    nombres_c2 = sorted([n for n, d in datos.items() if d['curso'] == "Curso 2"])
    nombres_c3 = sorted([n for n, d in datos.items() if d['curso'] == "Curso 3"])

    seleccionados_finales = []

    # --- Selector Curso 1 ---
    with st.expander(f"Curso 1 ({len(nombres_c1)} alumnos)", expanded=True):
        if nombres_c1:
            # Checkbox para "Seleccionar todos" rápido
            todos_c1 = st.checkbox("Marcar todos Curso 1", value=True)
            
            # El multiselect muestra las selecciones horizontalmente (como etiquetas)
            sel_c1 = st.multiselect(
                "Integrantes:", 
                nombres_c1, 
                default=nombres_c1 if todos_c1 else [],
                key="ms_c1"
            )
            seleccionados_finales.extend(sel_c1)
        else:
            st.caption("No se encontraron datos para Curso 1")

    # --- Selector Curso 2 ---
    with st.expander(f"Curso 2 ({len(nombres_c2)} alumnos)", expanded=False):
        if nombres_c2:
            todos_c2 = st.checkbox("Marcar todos Curso 2", value=False)
            sel_c2 = st.multiselect(
                "Integrantes:", 
                nombres_c2, 
                default=nombres_c2 if todos_c2 else [],
                key="ms_c2"
            )
            seleccionados_finales.extend(sel_c2)
        else:
            st.caption("No se encontraron datos para Curso 2")

    # --- Selector Curso 3 ---
    with st.expander(f"Curso 3 ({len(nombres_c3)} alumnos)", expanded=False):
        if nombres_c3:
            todos_c3 = st.checkbox("Marcar todos Curso 3", value=False)
            sel_c3 = st.multiselect(
                "Integrantes:", 
                nombres_c3, 
                default=nombres_c3 if todos_c3 else [],
                key="ms_c3"
            )
            seleccionados_finales.extend(sel_c3)
        else:
            st.caption("No se encontraron datos para Curso 3")

    st.markdown("---")
    st.subheader("🎯 Opciones de Grafo")
    max_ranking = st.slider("Afinidad Máxima (1-10):", 1, 10, 10, help="Muestra conexiones hasta este nivel de preferencia.")
    physics_enabled = st.toggle("Movimiento (Física)", value=True)

# --- Área de Visualización ---
if not datos:
    st.error("⚠️ No se encontraron archivos JSON en las carpetas 'respuestas/cursoX'. Por favor verifica la estructura de directorios.")
elif not seleccionados_finales:
    st.info("👈 Selecciona al menos un alumno en la barra lateral para generar el grafo.")
else:
    # Convertimos la lista de seleccionados a un SET para búsqueda rápida
    whitelist_nombres = set(seleccionados_finales)

    G = nx.DiGraph()
    
    # 1. Nodos: Solo agregamos los que estén en la whitelist
    for nombre, info in datos.items():
        if nombre in whitelist_nombres:
            G.add_node(nombre, group=info['curso'], title=f"Curso: {info['curso']}")

    # 2. Aristas: Lógica de conexión y reciprocidad
    mutuas_procesadas = set()

    for nombre, info in datos.items():
        # Si el alumno origen no está seleccionado, saltamos
        if nombre not in whitelist_nombres: 
            continue
            
        for destino, ranking_val in info['conexiones'].items():
            if ranking_val > max_ranking: continue 

            # Verificamos que el DESTINO también esté seleccionado para verse
            if destino in whitelist_nombres:
                
                # Recuperamos curso destino (seguro porque ya filtramos por whitelist)
                curso_destino = datos[destino]['curso'] if destino in datos else "Desconocido"
                
                # Aseguramos nodo destino si no existiera (caso raro data incompleta)
                if not G.has_node(destino):
                    G.add_node(destino, group=curso_destino, title=f"Curso: {curso_destino}")
                
                # Detección de reciprocidad (mutua)
                es_mutua = False
                datos_destino = datos.get(destino, {})
                ranking_retorno = datos_destino.get('conexiones', {}).get(nombre)
                
                if ranking_retorno and ranking_retorno <= max_ranking:
                    es_mutua = True
                
                # Añadir arista
                G.add_edge(nombre, destino, weight=ranking_val, mutua=es_mutua)
                
                if es_mutua:
                    par_alumnos = tuple(sorted((nombre, destino)))
                    mutuas_procesadas.add(par_alumnos)

    # Renderizado PyVis
    if len(G.nodes()) == 0:
        st.warning("Los alumnos seleccionados no tienen conexiones entre sí bajo los criterios actuales.")
    else:
        in_degrees = dict(G.in_degree())
        
        net = Network(height="750px", width="100%", bgcolor="#ffffff", font_color="black", directed=True)
        
        # Estilizar Nodos
        for node in G.nodes():
            curso = G.nodes[node].get('group', 'Desconocido')
            popularidad = in_degrees.get(node, 0)
            
            size = 15 + (popularidad * 4)
            color_fondo = COLORES_CURSO.get(curso, "#eeeeee")
            if popularidad >= 3:
                color_fondo = COLORES_POPULAR.get(curso, color_fondo)
                
            label = node
            if popularidad > 4: label += " 👑"
            
            title_html = f"<b>{node}</b><br>Curso: {curso}<br>Votos recibidos: {popularidad}"
            net.add_node(node, label=label, title=title_html, color=color_fondo, size=size)

        # Estilizar Aristas
        for u, v, data in G.edges(data=True):
            es_mutua = data.get('mutua', False)
            
            if es_mutua:
                net.add_edge(u, v, color="red", width=3, arrows="to;from")
            else:
                rank = data.get('weight', '?')
                color_linea = "#cccccc"
                # Destacar primera opción
                if rank == 1: color_linea = "#666666"
                
                net.add_edge(u, v, color=color_linea, width=1, dashes=True, arrows="to")

        if physics_enabled:
            net.barnes_hut(gravity=-2000, central_gravity=0.3, spring_length=120)
        else:
            net.toggle_physics(False)

        # Guardar y mostrar HTML
        with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp:
            net.save_graph(tmp.name)
            with open(tmp.name, 'r', encoding='utf-8') as f:
                html_bytes = f.read()
                
        st.components.v1.html(html_bytes, height=770, scrolling=False)
        
        # Métricas inferiores
        c1, c2, c3 = st.columns(3)
        c1.metric("Alumnos Visibles", len(G.nodes()))
        c2.metric("Conexiones Totales", len(G.edges()))
        c3.metric("Relaciones Mutuas (❤️)", len(mutuas_procesadas))
