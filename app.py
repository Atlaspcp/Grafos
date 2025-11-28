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
        st.sidebar.warning(f"⚠️ La carpeta no existe: {ruta_carpeta}")
        return data_parcial

    archivos = [f for f in os.listdir(ruta_carpeta) if f.endswith('.json')]
    
    if not archivos:
        st.sidebar.warning(f"⚠️ Carpeta vacía o sin JSONs: {nombre_curso}")
        return data_parcial

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

def inyectar_boton_descarga(html_str):
    """
    Inyecta Javascript y CSS en el HTML generado por Pyvis 
    para crear un botón de descarga de imagen (PNG).
    """
    script_descarga = """
    <script>
    function descargarImagen() {
        var canvas = document.getElementsByTagName('canvas')[0];
        // Crear un fondo blanco temporalmente si es transparente
        var context = canvas.getContext('2d');
        var w = canvas.width;
        var h = canvas.height;
        var data;

        // Compuesto para asegurar fondo blanco en la imagen
        var compositeOperation = context.globalCompositeOperation;
        context.globalCompositeOperation = "destination-over";
        context.fillStyle = "#ffffff";
        context.fillRect(0,0,w,h);

        var link = document.createElement('a');
        link.download = 'sociograma_grafo.png';
        link.href = canvas.toDataURL("image/png");
        link.click();
        
        // Restaurar estado del canvas (opcional, visualmente imperceptible)
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
        padding: 10px 20px;
        border: none;
        border-radius: 5px;
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
    # Insertar justo antes del cierre del body
    return html_str.replace('</body>', f'{script_descarga}</body>')

# =========================
# Interfaz Principal
# =========================
st.title("🕸️ Grafo de Sociometría - Visualizador Web")

# --- Barra Lateral: Configuración de Carpetas ---
with st.sidebar:
    st.header("📂 Rutas de Carpetas")
    st.info("El programa buscará automáticamente en estas carpetas dentro de tu proyecto.")

    ruta_c1 = st.text_input("Carpeta Curso 1", value=os.path.join("respuestas", "curso1"))
    ruta_c2 = st.text_input("Carpeta Curso 2", value=os.path.join("respuestas", "curso2"))
    ruta_c3 = st.text_input("Carpeta Curso 3", value=os.path.join("respuestas", "curso3"))

    if st.button("🔄 Cargar Carpetas y Generar"):
        st.session_state['datos_grafo'] = {}
        
        d1 = cargar_desde_carpeta(ruta_c1, "Curso 1")
        d2 = cargar_desde_carpeta(ruta_c2, "Curso 2")
        d3 = cargar_desde_carpeta(ruta_c3, "Curso 3")
        
        st.session_state['datos_grafo'].update(d1)
        st.session_state['datos_grafo'].update(d2)
        st.session_state['datos_grafo'].update(d3)
        
        total = len(st.session_state['datos_grafo'])
        if total > 0:
            st.success(f"¡Éxito! {total} alumnos cargados.")
        else:
            st.error("No se encontraron alumnos. Revisa las rutas.")

    st.markdown("---")
    st.subheader("⚙️ Opciones")
    physics_enabled = st.checkbox("Activar Física (Movimiento)", value=True)

# --- Área de Visualización ---
if 'datos_grafo' not in st.session_state or not st.session_state['datos_grafo']:
    st.info("👈 Configura las carpetas a la izquierda y pulsa el botón para iniciar.")
    st.markdown("""
    ### Guía Rápida:
    1. Crea una carpeta llamada `respuestas` junto a este archivo.
    2. Dentro, crea `curso1`, `curso2` y `curso3`.
    3. Pega tus archivos JSON ahí.
    4. Pulsa **Cargar Carpetas y Generar**.
    """)

else:
    # Construcción del Grafo
    G = nx.DiGraph()
    datos = st.session_state['datos_grafo']
    
    for origen, info in datos.items():
        G.add_node(origen, group=info['curso'], title=f"Curso: {info['curso']}")
        for destino in info['conexiones']:
            if not G.has_node(destino):
                 G.add_node(destino, group=info['curso'], title="No entregó encuesta")
            G.add_edge(origen, destino)

    # Cálculos de popularidad
    in_degrees = dict(G.in_degree())
    
    # Configuración de Pyvis
    net = Network(height="650px", width="100%", bgcolor="#ffffff", font_color="black", directed=True)
    
    # 1. Agregar Nodos
    for node in G.nodes():
        curso = G.nodes[node].get('group', 'Curso 1')
        popularidad = in_degrees.get(node, 0)
        
        size = 15 + (popularidad * 4)
        color_fondo = COLORES_CURSO.get(curso, "#eeeeee")
        if popularidad >= 3:
            color_fondo = COLORES_POPULAR.get(curso, color_fondo)
            
        label = node
        if popularidad > 4: label += " 👑"
        
        title_html = f"<b>{node}</b><br>Curso: {curso}<br>Votos recibidos: {popularidad}"
        net.add_node(node, label=label, title=title_html, color=color_fondo, size=size)

    # 2. Agregar Aristas (Lógica Modificada para Mutuas)
    procesados = set() # Para evitar duplicar aristas mutuas

    for u, v in G.edges():
        # Si ya procesamos esta pareja (en orden inverso), saltamos
        if (u, v) in procesados or (v, u) in procesados:
            continue

        es_mutuo = G.has_edge(v, u)
        
        if es_mutuo:
            # CAMBIO 1: Mutua = Línea Roja, gruesa, SIN flechas
            # 'arrows': {'to': {'enabled': False}} quita la punta de la flecha
            net.add_edge(u, v, color="red", width=3, dashes=False, arrows={'to': {'enabled': False}})
            
            # Marcamos ambos sentidos como procesados para que el bucle no dibuje la vuelta
            procesados.add((u, v))
            procesados.add((v, u))
        else:
            # Normal = Línea Gris, punteada, con flecha estándar
            net.add_edge(u, v, color="#cccccc", width=1, dashes=True, arrows='to')
            procesados.add((u, v))

    if physics_enabled:
        net.barnes_hut(gravity=-2000, central_gravity=0.3, spring_length=120)
    else:
        net.toggle_physics(False)

    # Renderizado
    with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp:
        net.save_graph(tmp.name)
        with open(tmp.name, 'r', encoding='utf-8') as f:
            html_bytes = f.read()
            
        # CAMBIO 2: Inyectar botón de descarga en el HTML
        html_con_boton = inyectar_boton_descarga(html_bytes)
            
    st.components.v1.html(html_con_boton, height=670, scrolling=False)
    
    # Métricas
    c1, c2, c3 = st.columns(3)
    c1.metric("Alumnos", len(G.nodes()))
    c2.metric("Conexiones", len(G.edges()))
    c3.metric("Relaciones Mutuas", sum(1 for u, v in G.edges() if G.has_edge(v, u)) // 2)
