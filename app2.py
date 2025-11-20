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
    """Limpieza de nombres."""
    if not nombre: return "DESCONOCIDO"
    nombre = re.sub(r'\(.*?\)', '', nombre)
    nombre = re.sub(r'\s+', ' ', nombre.strip()).upper()
    return nombre

def cargar_desde_carpeta(ruta_carpeta, nombre_curso):
    """Lee todos los JSON de una ruta local específica."""
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
                destinos = [normalizar_nombre(k) for k in ranking.keys()]
                
                data_parcial[origen] = {
                    "curso": nombre_curso,
                    "conexiones": destinos,
                    "raw_ranking": ranking
                }
        except Exception as e:
            st.sidebar.error(f"Error en {archivo}: {e}")
            
    return data_parcial

# =========================
# Interfaz Principal
# =========================
st.title("🕸️ Grafo de Sociometría - Visualizador Web")

# --- Barra Lateral: Carga y Filtros ---
with st.sidebar:
    st.header("📂 1. Carga de Datos")
    
    # Rutas por defecto
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
    st.header("👀 2. Filtros de Visualización")
    st.info("Selecciona qué cursos quieres ver en el grafo:")
    
    # Checkboxes para filtrar
    ver_c1 = st.checkbox("Ver Curso 1", value=True)
    ver_c2 = st.checkbox("Ver Curso 2", value=False)
    ver_c3 = st.checkbox("Ver Curso 3", value=False)
    
    # Creamos una lista con los cursos que el usuario marcó como True
    cursos_activos = []
    if ver_c1: cursos_activos.append("Curso 1")
    if ver_c2: cursos_activos.append("Curso 2")
    if ver_c3: cursos_activos.append("Curso 3")

    st.markdown("---")
    physics_enabled = st.checkbox("Activar Física (Movimiento)", value=True)

# --- Área de Visualización ---
if 'datos_grafo' not in st.session_state or not st.session_state['datos_grafo']:
    st.info("👈 Primero carga los datos usando el botón en la barra lateral.")
else:
    # Construcción del Grafo con FILTRO
    G = nx.DiGraph()
    datos = st.session_state['datos_grafo']
    
    # 1. Agregar NODOS (Solo de los cursos activos)
    nodos_visibles = set() # Usaremos esto para verificar conexiones válidas después
    
    for nombre, info in datos.items():
        if info['curso'] in cursos_activos:
            G.add_node(nombre, group=info['curso'], title=f"Curso: {info['curso']}")
            nodos_visibles.add(nombre)

    # 2. Agregar ARISTAS (Solo si origen Y destino son visibles)
    # Esto asegura que si ocultas el Curso 2, las flechas hacia el Curso 2 desaparecen
    for nombre, info in datos.items():
        # Si el alumno origen no debe verse, saltamos
        if nombre not in nodos_visibles:
            continue
            
        for destino in info['conexiones']:
            # LÓGICA DE FILTRO DE CONEXIONES:
            # Opción A (Estricta): Solo mostramos la conexión si el destino TAMBIÉN está cargado y es de un curso activo.
            
            if destino in datos:
                curso_destino = datos[destino]['curso']
                if curso_destino in cursos_activos:
                    # Ambos (origen y destino) son visibles -> Dibujar línea
                    if not G.has_node(destino):
                        G.add_node(destino, group=curso_destino, title=f"Curso: {curso_destino}")
                    G.add_edge(nombre, destino)
            
            else:
                # Opción para "Fantasmas" (Alumnos que fueron votados pero no cargamos su JSON)
                # Por defecto, los ocultamos para mantener la vista limpia según tu petición.
                # Si quisieras verlos, descomenta las lineas de abajo:
                pass 
                # G.add_node(destino, group="Desconocido", title="No entregó encuesta", color="#dddddd")
                # G.add_edge(nombre, destino)

    # Si no hay nodos seleccionados, mostrar aviso
    if len(G.nodes()) == 0:
        st.warning("No hay alumnos para mostrar con la selección actual. Activa más cursos o carga los datos.")
    else:
        # Cálculos de popularidad (Solo sobre el grafo visible)
        in_degrees = dict(G.in_degree())
        
        # Configuración de Pyvis
        net = Network(height="650px", width="100%", bgcolor="#ffffff", font_color="black", directed=True)
        
        for node in G.nodes():
            # Obtener datos del nodo en el grafo filtrado
            curso = G.nodes[node].get('group', 'Desconocido')
            popularidad = in_degrees.get(node, 0)
            
            # Estilos
            size = 15 + (popularidad * 4)
            color_fondo = COLORES_CURSO.get(curso, "#eeeeee")
            if popularidad >= 3:
                color_fondo = COLORES_POPULAR.get(curso, color_fondo)
                
            label = node
            if popularidad > 4: label += " 👑"
            
            title_html = f"<b>{node}</b><br>Curso: {curso}<br>Votos recibidos (en vista actual): {popularidad}"

            net.add_node(node, label=label, title=title_html, color=color_fondo, size=size)

        for u, v in G.edges():
            es_mutuo = G.has_edge(v, u)
            color_linea = "red" if es_mutuo else "#cccccc"
            width = 3 if es_mutuo else 1
            dashes = False if es_mutuo else True
            
            net.add_edge(u, v, color=color_linea, width=width, dashes=dashes)

        if physics_enabled:
            net.barnes_hut(gravity=-2000, central_gravity=0.3, spring_length=120)
        else:
            net.toggle_physics(False)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp:
            net.save_graph(tmp.name)
            with open(tmp.name, 'r', encoding='utf-8') as f:
                html_bytes = f.read()
                
        st.components.v1.html(html_bytes, height=670, scrolling=False)
        
        # Métricas dinámicas
        c1, c2, c3 = st.columns(3)
        c1.metric("Alumnos Visibles", len(G.nodes()))
        c2.metric("Conexiones Visibles", len(G.edges()))
        c3.metric("Mutuas (En vista)", sum(1 for u, v in G.edges() if G.has_edge(v, u)) // 2)
