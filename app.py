import streamlit as st
import json
import networkx as nx
from pyvis.network import Network
import tempfile
import os
import re

# =========================
# Configuración de Página y Estilos CSS
# =========================
st.set_page_config(page_title="Sociometría Interactiva", layout="wide")

# Inyectamos CSS para ensanchar la barra lateral
st.markdown(
    """
    <style>
    [data-testid="stSidebar"] {
        min_width: 450px;
        max_width: 600px;
        width: 500px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================
# Constantes
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
        except Exception:
            pass
            
    return data_parcial

def crear_grilla_checkbox(nombres, key_prefix, default_check=False):
    """
    Crea una lista de checkboxes en 2 columnas.
    default_check controla si empiezan marcados o no.
    """
    seleccionados = []
    
    # Checkbox maestro
    todos = st.checkbox("Seleccionar Todos", value=default_check, key=f"all_{key_prefix}")
    
    # Creamos 2 columnas para distribución horizontal
    col1, col2 = st.columns(2)
    
    for i, nombre in enumerate(nombres):
        columna_actual = col1 if i % 2 == 0 else col2
        with columna_actual:
            if st.checkbox(nombre, value=todos, key=f"{key_prefix}_{i}_{nombre}"):
                seleccionados.append(nombre)
                
    return seleccionados

def inyectar_boton_descarga(html_str):
    """
    Inyecta Javascript para capturar el Canvas y descargar como PNG.
    """
    script_descarga = """
    <script>
    function descargarImagen() {
        var canvas = document.getElementsByTagName('canvas')[0];
        var context = canvas.getContext('2d');
        var w = canvas.width;
        var h = canvas.height;
        
        // Guardar estado actual
        var compositeOperation = context.globalCompositeOperation;
        
        // Dibujar fondo blanco detrás del grafo (para que no salga transparente)
        context.globalCompositeOperation = "destination-over";
        context.fillStyle = "#ffffff";
        context.fillRect(0,0,w,h);

        var link = document.createElement('a');
        link.download = 'sociograma.png';
        link.href = canvas.toDataURL("image/png");
        link.click();
        
        // Restaurar estado
        context.globalCompositeOperation = compositeOperation;
    }
    </script>
    <style>
    .btn-download {
        position: absolute;
        top: 10px;
        right: 10px;
        z-index: 1000;
        background-color: #4CAF50;
        color: white;
        padding: 8px 15px;
        border: none;
        border-radius: 4px;
        cursor: pointer;
        font-family: sans-serif;
        font-weight: bold;
        box-shadow: 0px 2px 5px rgba(0,0,0,0.2);
    }
    .btn-download:hover {
        background-color: #45a049;
    }
    </style>
    <button onclick="descargarImagen()" class="btn-download">📸 Descargar Imagen</button>
    """
    return html_str.replace('</body>', f'{script_descarga}</body>')

# =========================
# Lógica de Carga Automática
# =========================
if 'datos_grafo' not in st.session_state:
    st.session_state['datos_grafo'] = {}
    
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

# --- Barra Lateral ---
with st.sidebar:
    st.header("👥 Filtro de Alumnos")
    st.caption("Marca las casillas para incluir alumnos en el grafo.")
    
    nombres_c1 = sorted([n for n, d in datos.items() if d['curso'] == "Curso 1"])
    nombres_c2 = sorted([n for n, d in datos.items() if d['curso'] == "Curso 2"])
    nombres_c3 = sorted([n for n, d in datos.items() if d['curso'] == "Curso 3"])

    seleccionados_finales = []

    # --- Curso 1 ---
    with st.expander(f"Curso 1 ({len(nombres_c1)})", expanded=True):
        if nombres_c1:
            sel_c1 = crear_grilla_checkbox(nombres_c1, "c1", default_check=False)
            seleccionados_finales.extend(sel_c1)
        else:
            st.caption("Sin datos")

    # --- Curso 2 ---
    with st.expander(f"Curso 2 ({len(nombres_c2)})", expanded=False):
        if nombres_c2:
            sel_c2 = crear_grilla_checkbox(nombres_c2, "c2", default_check=False)
            seleccionados_finales.extend(sel_c2)
        else:
            st.caption("Sin datos")

    # --- Curso 3 ---
    with st.expander(f"Curso 3 ({len(nombres_c3)})", expanded=False):
        if nombres_c3:
            sel_c3 = crear_grilla_checkbox(nombres_c3, "c3", default_check=False)
            seleccionados_finales.extend(sel_c3)
        else:
            st.caption("Sin datos")

    st.markdown("---")
    st.subheader("🎯 Opciones")
    max_ranking = st.slider("Afinidad Máxima (1-10):", 1, 10, 10)
    physics_enabled = st.toggle("Física (Movimiento)", value=True)

# --- Visualización ---
if not datos:
    st.error("⚠️ No se encontraron datos. Verifica las carpetas 'respuestas/cursoX'.")
elif not seleccionados_finales:
    st.info("👈 **Grafo vacío.** Por favor selecciona alumnos en la barra lateral izquierda para comenzar el análisis.")
else:
    whitelist_nombres = set(seleccionados_finales)
    G = nx.DiGraph()
    
    # Nodos
    for nombre, info in datos.items():
        if nombre in whitelist_nombres:
            G.add_node(nombre, group=info['curso'], title=f"Curso: {info['curso']}")

    # Aristas (Construcción Lógica)
    mutuas_para_metricas = set() # Solo para el contador de abajo

    for nombre, info in datos.items():
        if nombre not in whitelist_nombres: continue
            
        for destino, ranking_val in info['conexiones'].items():
            if ranking_val > max_ranking: continue 

            if destino in whitelist_nombres:
                curso_destino = datos[destino]['curso'] if destino in datos else "Desconocido"
                
                if not G.has_node(destino):
                    G.add_node(destino, group=curso_destino, title=f"Curso: {curso_destino}")
                
                es_mutua = False
                datos_destino = datos.get(destino, {})
                ranking_retorno = datos_destino.get('conexiones', {}).get(nombre)
                
                if ranking_retorno and ranking_retorno <= max_ranking:
                    es_mutua = True
                    mutuas_para_metricas.add(tuple(sorted((nombre, destino))))
                
                G.add_edge(nombre, destino, weight=ranking_val, mutua=es_mutua)

    # Renderizado
    if len(G.nodes()) == 0:
        st.warning("Alumnos seleccionados sin conexiones visibles.")
    else:
        in_degrees = dict(G.in_degree())
        net = Network(height="750px", width="100%", bgcolor="#ffffff", font_color="black", directed=True)
        
        # Agregar Nodos a Pyvis
        for node in G.nodes():
            curso = G.nodes[node].get('group', 'Desconocido')
            popularidad = in_degrees.get(node, 0)
            size = 15 + (popularidad * 4)
            color_fondo = COLORES_CURSO.get(curso, "#eeeeee")
            if popularidad >= 3:
                color_fondo = COLORES_POPULAR.get(curso, color_fondo)
            
            label = node
            if popularidad > 4: label += " 👑"
            title = f"<b>{node}</b><br>{curso}<br>Votos: {popularidad}"
            
            net.add_node(node, label=label, title=title, color=color_fondo, size=size)

        # ---------------------------------------------------------------------
        # CAMBIO 1: Agregar Aristas controlando visualización de Mutuas
        # ---------------------------------------------------------------------
        dibujados_mutuos = set()

        for u, v, data in G.edges(data=True):
            es_mutua = data.get('mutua', False)

            if es_mutua:
                # Ordenamos la tupla para verificar si ya dibujamos este par (A-B o B-A)
                par = tuple(sorted((u, v)))
                
                if par in dibujados_mutuos:
                    continue # Si ya la dibujamos, saltamos para no duplicar

                # Dibujamos UNA sola línea ROJA sin flechas ('enabled': False)
                net.add_edge(u, v, color="red", width=3, arrows={'to': {'enabled': False}})
                dibujados_mutuos.add(par)
            
            else:
                # Dibujo normal estándar con flecha
                rank = data.get('weight', '?')
                color = "#666666" if rank == 1 else "#cccccc"
                net.add_edge(u, v, color=color, width=1, dashes=True, arrows='to')

        # Física
        if physics_enabled:
            net.barnes_hut(gravity=-2000, central_gravity=0.3, spring_length=120)
        else:
            net.toggle_physics(False)

        # ---------------------------------------------------------------------
        # CAMBIO 2: Guardar HTML e inyectar el botón
        # ---------------------------------------------------------------------
        with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp:
            net.save_graph(tmp.name)
            with open(tmp.name, 'r', encoding='utf-8') as f:
                html_bytes = f.read()
                
            # Llamamos a la función inyectora
            html_final = inyectar_boton_descarga(html_bytes)
            
        st.components.v1.html(html_final, height=770)
        
        # Métricas
        c1, c2, c3 = st.columns(3)
        c1.metric("Alumnos Visibles", len(G.nodes()))
        c2.metric("Conexiones Totales", len(G.edges()))
        c3.metric("Parejas Mutuas", len(mutuas_para_metricas))
