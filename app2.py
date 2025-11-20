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
    """Lee JSONs y guarda DESTINO + RANKING (puesto)."""
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
            ranking = contenido.get("Seleccion_Jerarquica", {}) # Ej: {"Juan": 1, "Pedro": 2}

            if nombre_completo:
                origen = normalizar_nombre(nombre_completo)
                
                # AHORA: Guardamos un diccionario {NombreDestino: NumeroRanking}
                conexiones_con_ranking = {}
                for k, v in ranking.items():
                    nombre_dest = normalizar_nombre(k)
                    try:
                        valor_rank = int(v) # Aseguramos que sea número
                    except:
                        valor_rank = 99 # Si no tiene número, lo mandamos al final
                    conexiones_con_ranking[nombre_dest] = valor_rank

                data_parcial[origen] = {
                    "curso": nombre_curso,
                    "conexiones": conexiones_con_ranking, # Guardamos el dict con valores
                    "raw_ranking": ranking
                }
        except Exception as e:
            st.sidebar.error(f"Error en {archivo}: {e}")
            
    return data_parcial

# =========================
# Interfaz Principal
# =========================
st.title("🕸️ Grafo de Sociometría - Visualizador Web")

# --- Barra Lateral ---
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
    st.header("👀 2. Filtros de Visualización")
    
    # Checkboxes de Cursos
    col_chk1, col_chk2, col_chk3 = st.columns(3)
    ver_c1 = col_chk1.checkbox("C1", value=True)
    ver_c2 = col_chk2.checkbox("C2", value=False)
    ver_c3 = col_chk3.checkbox("C3", value=False)
    
    cursos_activos = []
    if ver_c1: cursos_activos.append("Curso 1")
    if ver_c2: cursos_activos.append("Curso 2")
    if ver_c3: cursos_activos.append("Curso 3")

    # --- NUEVO: Slider de Afinidad ---
    st.subheader("🎯 Nivel de Afinidad")
    max_ranking = st.slider(
        "Mostrar hasta la preferencia nº:", 
        min_value=1, 
        max_value=10, 
        value=10,
        help="Si seleccionas 1, solo verás a los mejores amigos (primera opción). Si seleccionas 10, verás todas las conexiones."
    )
    
    st.markdown("---")
    physics_enabled = st.checkbox("Activar Física (Movimiento)", value=True)

# --- Área de Visualización ---
if 'datos_grafo' not in st.session_state or not st.session_state['datos_grafo']:
    st.info("👈 Primero carga los datos usando el botón en la barra lateral.")
else:
    # Construcción del Grafo con DOBLE FILTRO (Curso + Ranking)
    G = nx.DiGraph()
    datos = st.session_state['datos_grafo']
    
    # 1. Agregar NODOS (Solo de los cursos activos)
    nodos_visibles = set()
    
    for nombre, info in datos.items():
        if info['curso'] in cursos_activos:
            G.add_node(nombre, group=info['curso'], title=f"Curso: {info['curso']}")
            nodos_visibles.add(nombre)

    # 2. Agregar ARISTAS (Filtro Curso + Filtro Slider)
    for nombre, info in datos.items():
        if nombre not in nodos_visibles:
            continue
            
        # info['conexiones'] ahora es un dict {Nombre: Ranking}
        for destino, ranking_val in info['conexiones'].items():
            
            # --- FILTRO DE AFINIDAD ---
            # Si el ranking de esta conexión es mayor que el slider, la ignoramos
            if ranking_val > max_ranking:
                continue 

            # --- FILTRO DE CURSO DESTINO ---
            if destino in datos:
                curso_destino = datos[destino]['curso']
                if curso_destino in cursos_activos:
                    if not G.has_node(destino):
                        G.add_node(destino, group=curso_destino, title=f"Curso: {curso_destino}")
                    
                    # Agregamos la arista
                    # Tip visual: Grosor según ranking (opcional, aquí es fijo o por reciprocidad)
                    G.add_edge(nombre, destino, weight=ranking_val)

    # Mensaje si está vacío
    if len(G.nodes()) == 0:
        st.warning("No hay datos visibles. Prueba activando más cursos o aumentando el nivel de afinidad.")
    else:
        # Cálculos (Solo sobre lo visible)
        in_degrees = dict(G.in_degree())
        
        # Configuración Pyvis
        net = Network(height="650px", width="100%", bgcolor="#ffffff", font_color="black", directed=True)
        
        for node in G.nodes():
            curso = G.nodes[node].get('group', 'Desconocido')
            popularidad = in_degrees.get(node, 0)
            
            size = 15 + (popularidad * 4)
            color_fondo = COLORES_CURSO.get(curso, "#eeeeee")
            if popularidad >= 3:
                color_fondo = COLORES_POPULAR.get(curso, color_fondo)
                
            label = node
            if popularidad > 4: label += " 👑"
            
            title_html = f"<b>{node}</b><br>Curso: {curso}<br>Votos visibles: {popularidad}"
            net.add_node(node, label=label, title=title_html, color=color_fondo, size=size)

        for u, v in G.edges():
            # Datos de la arista (recuperamos el ranking si quisiéramos ponerlo en el tooltip)
            rank = G[u][v].get('weight', '?')
            
            es_mutuo = G.has_edge(v, u)
            color_linea = "red" if es_mutuo else "#cccccc"
            
            # Ajuste visual: Si es 1ra opción, la línea es un poco más oscura aunque no sea mutua
            if not es_mutuo and rank == 1:
                color_linea = "#666666" # Gris oscuro para 1ra opción

            width = 3 if es_mutuo else 1
            dashes = False if es_mutuo else True
            
            title_edge = f"Ranking: {rank}º opción"
            net.add_edge(u, v, color=color_linea, width=width, dashes=dashes, title=title_edge)

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
        c1.metric("Alumnos", len(G.nodes()))
        c2.metric(f"Conexiones (Top {max_ranking})", len(G.edges()))
        c3.metric("Mutuas Visibles", sum(1 for u, v in G.edges() if G.has_edge(v, u)) // 2)
