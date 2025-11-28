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

# CSS: Barra lateral y ocultar elementos al imprimir
st.markdown(
    """
    <style>
    [data-testid="stSidebar"] {
        min_width: 450px;
        max_width: 600px;
        width: 500px;
    }
    
    /* ESTILOS DE IMPRESIÓN (PDF) */
    @media print {
        /* Ocultar todo menos el grafo */
        [data-testid="stSidebar"], header, footer, .stApp > header, .btn-container {
            display: none !important;
        }
        .block-container {
            padding: 0 !important; margin: 0 !important; max-width: none !important;
        }
        #mynetwork, body, html {
            width: 100% !important; height: 100% !important; margin: 0 !important; overflow: visible !important;
        }
        canvas {
            width: 100% !important; height: auto !important; display: block;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

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
    if not os.path.exists(ruta_carpeta): return data_parcial
    archivos = [f for f in os.listdir(ruta_carpeta) if f.endswith('.json')]
    
    for archivo in archivos:
        try:
            with open(os.path.join(ruta_carpeta, archivo), 'r', encoding='utf-8') as f:
                contenido = json.load(f)
            nombre = contenido.get("Nombre")
            ranking = contenido.get("Seleccion_Jerarquica", {})
            if nombre:
                origen = normalizar_nombre(nombre)
                conexiones = {normalizar_nombre(k): int(v) if str(v).isdigit() else 99 for k, v in ranking.items()}
                data_parcial[origen] = {"curso": nombre_curso, "conexiones": conexiones, "raw_ranking": ranking}
        except: pass
    return data_parcial

def crear_grilla_checkbox(nombres, key_prefix, default_check=False):
    seleccionados = []
    todos = st.checkbox("Seleccionar Todos", value=default_check, key=f"all_{key_prefix}")
    col1, col2 = st.columns(2)
    for i, n in enumerate(nombres):
        with (col1 if i%2==0 else col2):
            if st.checkbox(n, value=todos, key=f"{key_prefix}_{i}_{n}"):
                seleccionados.append(n)
    return seleccionados

def inyectar_botones_control(html_str):
    """
    Inyecta dos botones: Uno para Centrar (Fit) y otro para Imprimir Alta Calidad (sin recentrar).
    """
    script_botones = """
    <script>
    // Función 1: Centrar el grafo
    function centrarGrafo() {
        if (typeof network !== 'undefined') {
            network.fit({ animation: { duration: 1000 } });
        }
    }

    // Función 2: Imprimir en Alta Calidad LO QUE SE VE (sin recentrar)
    function imprimirAltaCalidad() {
        var canvas = document.getElementsByTagName('canvas')[0];
        if (!canvas) return;

        var originalWidth = canvas.width;
        var originalHeight = canvas.height;
        var originalStyleWidth = canvas.style.width;
        var originalStyleHeight = canvas.style.height;
        var ctx = canvas.getContext('2d');
        var scaleFactor = 4; // Calidad x4

        // Aumentar resolución interna
        canvas.width = originalWidth * scaleFactor;
        canvas.height = originalHeight * scaleFactor;
        canvas.style.width = originalStyleWidth;
        canvas.style.height = originalStyleHeight;
        
        ctx.scale(scaleFactor, scaleFactor);

        if (typeof network !== 'undefined') {
            network.redraw(); // Redibujar en alta res
        }

        setTimeout(function() {
            window.print(); // Imprimir
            
            // Restaurar
            setTimeout(function() {
                canvas.width = originalWidth;
                canvas.height = originalHeight;
                canvas.style.width = originalStyleWidth;
                canvas.style.height = originalStyleHeight;
                ctx.setTransform(1, 0, 0, 1, 0, 0);
                if (typeof network !== 'undefined') network.redraw();
            }, 2000);
        }, 1000);
    }
    </script>
    
    <style>
    .btn-container {
        position: absolute; top: 10px; right: 10px; z-index: 1000; display: flex; gap: 10px;
    }
    .btn-action {
        padding: 8px 16px; border: none; border-radius: 5px; cursor: pointer;
        font-family: sans-serif; font-weight: bold; font-size: 14px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.2); color: white;
    }
    .btn-center { background-color: #555; }
    .btn-center:hover { background-color: #333; }
    .btn-print { background-color: #E74C3C; }
    .btn-print:hover { background-color: #C0392B; }
    </style>
    
    <div class="btn-container">
        <button onclick="centrarGrafo()" class="btn-action btn-center">🔍 Centrar</button>
        <button onclick="imprimirAltaCalidad()" class="btn-action btn-print">🖨️ PDF Alta Calidad (Vista Actual)</button>
    </div>
    """
    return html_str.replace('</body>', f'{script_botones}</body>')

# =========================
# Lógica Principal
# =========================
if 'datos_grafo' not in st.session_state:
    st.session_state['datos_grafo'] = {}
    # Cargar datos (ajusta las rutas según tu estructura)
    for c in ["curso1", "curso2", "curso3"]:
        ruta = os.path.join("respuestas", c)
        st.session_state['datos_grafo'].update(cargar_desde_carpeta(ruta, c.replace("curso", "Curso ")))

st.title("🕸️ Grafo de Sociometría")
datos = st.session_state['datos_grafo']

with st.sidebar:
    st.header("👥 Filtro de Alumnos")
    
    # Checkboxes por curso
    seleccionados = []
    for c_nombre in ["Curso 1", "Curso 2", "Curso 3"]:
        nombres = sorted([n for n, d in datos.items() if d['curso'] == c_nombre])
        with st.expander(f"{c_nombre} ({len(nombres)})", expanded=(c_nombre=="Curso 1")):
            if nombres: seleccionados.extend(crear_grilla_checkbox(nombres, c_nombre.lower().replace(" ", "")))

    st.markdown("---")
    st.subheader("⚙️ Configuración Visual")
    
    # SETS PREDETERMINADOS DE FÍSICA
    modo_fisica = st.selectbox(
        "Estilo del Grafo (Física):",
        ["Equilibrado", "Espaciado (Recomendado)", "Compacto"],
        index=1
    )
    
    # Diccionario de configuraciones físicas
    configuraciones_fisica = {
        "Equilibrado": {"grav": -2000, "spring": 200},
        "Espaciado (Recomendado)": {"grav": -4000, "spring": 350}, # Más repulsión, líneas más largas
        "Compacto": {"grav": -1000, "spring": 100}
    }
    params = configuraciones_fisica[modo_fisica]

    max_ranking = st.slider("Afinidad Máxima (1-10):", 1, 10, 10)
    st.caption("Nota: Usa el botón '🔍 Centrar' en el gráfico para restablecer la vista.")

# --- Renderizado ---
if not datos or not seleccionados:
    st.info("👈 Selecciona alumnos para visualizar.")
else:
    whitelist = set(seleccionados)
    G = nx.DiGraph()
    
    # Nodos y Aristas
    mutuas = set()
    for n, info in datos.items():
        if n in whitelist:
            G.add_node(n, group=info['curso'], title=f"{info['curso']}")
            for dest, rank in info['conexiones'].items():
                if rank <= max_ranking and dest in whitelist:
                    # Verificar nodo destino
                    if not G.has_node(dest):
                         G.add_node(dest, group=datos.get(dest, {}).get('curso', 'Desconocido'))
                    
                    # Verificar mutua
                    es_mutua = False
                    if datos.get(dest, {}).get('conexiones', {}).get(n, 99) <= max_ranking:
                        es_mutua = True
                        mutuas.add(tuple(sorted((n, dest))))
                    
                    G.add_edge(n, dest, weight=rank, mutua=es_mutua)

    if len(G.nodes()) == 0:
        st.warning("Sin conexiones visibles.")
    else:
        # Configurar Pyvis
        net = Network(height="750px", width="100%", bgcolor="white", font_color="black", directed=True)
        in_degrees = dict(G.in_degree())

        # Dibujar Nodos
        colores = {"Curso 1": "#FFFF00", "Curso 2": "#90EE90", "Curso 3": "#ADD8E6"}
        colores_pop = {"Curso 1": "#FFD700", "Curso 2": "#32CD32", "Curso 3": "#1E90FF"}
        
        for n in G.nodes():
            c = G.nodes[n].get('group', 'Desconocido')
            pop = in_degrees.get(n, 0)
            size = 25 + (pop * 5)
            color = colores_pop.get(c, "#ccc") if pop >= 3 else colores.get(c, "#eee")
            label = f"{n} 👑" if pop > 4 else n
            net.add_node(n, label=label, title=f"{n}\nVotos: {pop}", color=color, size=size, 
                         font={'size': 20, 'face': 'arial', 'strokeWidth': 3, 'strokeColor': 'white'})

        # Dibujar Aristas
        dibujadas = set()
        for u, v, d in G.edges(data=True):
            if d['mutua']:
                par = tuple(sorted((u, v)))
                if par not in dibujadas:
                    net.add_edge(u, v, color="red", width=4, arrows={'to': {'enabled': False}})
                    dibujadas.add(par)
            else:
                color = "#666666" if d['weight'] == 1 else "#cccccc"
                net.add_edge(u, v, color=color, width=2 if d['weight']==1 else 1, dashes=True, 
                             arrows={'to': {'enabled': True, 'type': 'vee'}})

        # Aplicar Física desde el Selectbox
        net.barnes_hut(
            gravity=params['grav'], 
            central_gravity=0.1, 
            spring_length=params['spring'], 
            damping=0.09
        )

        # Generar HTML
        with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp:
            net.save_graph(tmp.name)
            with open(tmp.name, 'r', encoding='utf-8') as f:
                html = inyectar_botones_control(f.read())
            
        st.components.v1.html(html, height=800)
        
        # Métricas
        c1, c2, c3 = st.columns(3)
        c1.metric("Alumnos", len(G.nodes()))
        c2.metric("Conexiones", len(G.edges()))
        c3.metric("Relaciones Mutuas", len(mutuas))
