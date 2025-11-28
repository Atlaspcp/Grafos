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
# Constantes y Archivo de Persistencia
# =========================
FILE_GRUPOS = "grupos_guardados.json"

# =========================
# Funciones de Utilidad (Carga y Persistencia)
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

# --- Funciones para Guardar/Cargar Grupos ---
def leer_grupos_guardados():
    if not os.path.exists(FILE_GRUPOS): return {}
    try:
        with open(FILE_GRUPOS, 'r', encoding='utf-8') as f: return json.load(f)
    except: return {}

def guardar_nuevo_grupo(nombre_grupo, lista_alumnos):
    grupos = leer_grupos_guardados()
    grupos[nombre_grupo] = lista_alumnos
    with open(FILE_GRUPOS, 'w', encoding='utf-8') as f: json.dump(grupos, f, ensure_ascii=False, indent=4)

def eliminar_grupo(nombre_grupo):
    grupos = leer_grupos_guardados()
    if nombre_grupo in grupos:
        del grupos[nombre_grupo]
        with open(FILE_GRUPOS, 'w', encoding='utf-8') as f: json.dump(grupos, f, ensure_ascii=False, indent=4)

# --- Checkbox Modificado ---
def crear_grilla_checkbox(nombres, key_prefix, lista_preseleccion=None):
    seleccionados = []
    todos = st.checkbox("Seleccionar Todos", value=False, key=f"all_{key_prefix}")
    col1, col2 = st.columns(2)
    for i, n in enumerate(nombres):
        is_checked = todos or (lista_preseleccion is not None and n in lista_preseleccion)
        with (col1 if i%2==0 else col2):
            if st.checkbox(n, value=is_checked, key=f"{key_prefix}_{i}_{n}"):
                seleccionados.append(n)
    return seleccionados

# =========================
# INYECCIÓN DE JAVASCRIPT PARA IMAGEN HD
# =========================
def inyectar_botones_imagen_hd(html_str):
    script_botones = """
    <script>
    // 1. Función para Centrar (por si se pierde el grafo)
    function centrarGrafo() { if (typeof network !== 'undefined') network.fit({ animation: { duration: 1000 } }); }

    // 2. Función PRINCIPAL: Descargar Imagen HD de la vista actual
    async function descargarImagenHD() {
        var canvas = document.getElementsByTagName('canvas')[0];
        if (!canvas) return;

        // Guardar estado original
        var originalWidth = canvas.width;
        var originalHeight = canvas.height;
        // Guardamos el estilo CSS para que no se descuadre visualmente al usuario
        var originalStyleWidth = canvas.style.width;
        var originalStyleHeight = canvas.style.height;
        var ctx = canvas.getContext('2d');

        // --- FASE DE ALTA RESOLUCIÓN ---
        var scaleFactor = 4; // Multiplicador de calidad (4x es muy bueno)

        // Aumentamos el tamaño interno del canvas
        canvas.width = originalWidth * scaleFactor;
        canvas.height = originalHeight * scaleFactor;
        // Mantenemos el tamaño visual externo
        canvas.style.width = originalStyleWidth;
        canvas.style.height = originalStyleHeight;

        // Escalamos el contexto de dibujo
        ctx.scale(scaleFactor, scaleFactor);

        // Redibujamos el grafo en alta resolución (manteniendo el zoom actual)
        if (typeof network !== 'undefined') network.redraw();

        // Esperamos un momento para asegurar el redibujado
        await new Promise(r => setTimeout(r, 500));

        // --- FASE DE DESCARGA ---
        try {
            // Creamos la imagen PNG a partir del canvas gigante
            var imgData = canvas.toDataURL("image/png");
            
            // Creamos un enlace temporal para descargar
            var link = document.createElement('a');
            link.download = "sociograma_HD_vista_actual.png";
            link.href = imgData;
            link.click();

        } catch (error) { alert("Error generando imagen: " + error.message); }

        // --- FASE DE RESTAURACIÓN ---
        // Devolvemos el canvas a su estado normal
        canvas.width = originalWidth;
        canvas.height = originalHeight;
        canvas.style.width = originalStyleWidth;
        canvas.style.height = originalStyleHeight;
        ctx.setTransform(1, 0, 0, 1, 0, 0); // Resetear escala
        if (typeof network !== 'undefined') network.redraw();
    }
    </script>
    
    <style>
    .btn-container { position: absolute; top: 10px; right: 10px; z-index: 1000; display: flex; gap: 10px; }
    .btn-action { padding: 8px 16px; border: none; border-radius: 5px; cursor: pointer; font-family: sans-serif; font-weight: bold; font-size: 14px; box-shadow: 0 2px 4px rgba(0,0,0,0.2); color: white; }
    .btn-center { background-color: #555; } .btn-center:hover { background-color: #333; }
    /* Color violeta para el botón de imagen HD */
    .btn-img { background-color: #8E44AD; } .btn-img:hover { background-color: #732d91; }
    </style>
    
    <div class="btn-container">
        <button onclick="centrarGrafo()" class="btn-action btn-center">🔍 Centrar</button>
        <button onclick="descargarImagenHD()" class="btn-action btn-img">📸 Descargar Imagen HD (Vista Actual)</button>
    </div>
    """
    return html_str.replace('</body>', f'{script_botones}</body>')

# =========================
# Lógica Principal
# =========================
if 'datos_grafo' not in st.session_state:
    st.session_state['datos_grafo'] = {}
    for c in ["curso1", "curso2", "curso3"]:
        ruta = os.path.join("respuestas", c)
        st.session_state['datos_grafo'].update(cargar_desde_carpeta(ruta, c.replace("curso", "Curso ")))

st.title("🕸️ Grafo de Sociometría")
datos = st.session_state['datos_grafo']

with st.sidebar:
    # --- SECCIÓN DE GESTIÓN DE GRUPOS ---
    st.header("💾 Grupos Guardados")
    grupos_existentes = leer_grupos_guardados()
    nombres_grupos = ["-- Ninguno --"] + list(grupos_existentes.keys())
    
    grupo_seleccionado_nombre = st.selectbox("Cargar un grupo guardado:", nombres_grupos)
    lista_preseleccion = None
    if grupo_seleccionado_nombre != "-- Ninguno --":
        lista_preseleccion = set(grupos_existentes[grupo_seleccionado_nombre])
        if st.button("🗑️ Eliminar este grupo"):
            eliminar_grupo(grupo_seleccionado_nombre)
            st.rerun()

    st.markdown("---")
    
    # --- SECCIÓN DE FILTROS ---
    st.header("👥 Selección de Estudiantes")
    seleccionados_totales = []
    for c_nombre in ["Curso 1", "Curso 2", "Curso 3"]:
        nombres = sorted([n for n, d in datos.items() if d['curso'] == c_nombre])
        expandir = lista_preseleccion and any(n in lista_preseleccion for n in nombres) or c_nombre == "Curso 1"
        with st.expander(f"{c_nombre} ({len(nombres)})", expanded=expandir):
            if nombres: 
                sel = crear_grilla_checkbox(nombres, c_nombre.lower().replace(" ", ""), lista_preseleccion)
                seleccionados_totales.extend(sel)

    # --- SECCIÓN PARA GUARDAR LO ACTUAL ---
    if seleccionados_totales:
        st.markdown("---")
        st.subheader("💾 Guardar Selección Actual")
        nombre_nuevo_grupo = st.text_input("Nombre para el nuevo grupo:")
        if st.button("Guardar Grupo"):
            if nombre_nuevo_grupo:
                guardar_nuevo_grupo(nombre_nuevo_grupo, seleccionados_totales)
                st.success(f"Grupo '{nombre_nuevo_grupo}' guardado.")
                st.rerun()
            else: st.error("Escribe un nombre.")

    st.markdown("---")
    st.subheader("⚙️ Visualización")
    modo_fisica = st.selectbox("Estilo:", ["Equilibrado", "Espaciado (Recomendado)", "Compacto"], index=1)
    configuraciones_fisica = {
        "Equilibrado": {"grav": -2000, "spring": 200},
        "Espaciado (Recomendado)": {"grav": -4000, "spring": 350},
        "Compacto": {"grav": -1000, "spring": 100}
    }
    params = configuraciones_fisica[modo_fisica]
    max_ranking = st.slider("Afinidad Máxima:", 1, 10, 10)

# --- Renderizado ---
if not datos or not seleccionados_totales:
    st.info("👈 Selecciona alumnos o carga un grupo guardado.")
else:
    whitelist = set(seleccionados_totales)
    G = nx.DiGraph()
    mutuas = set()
    for n, info in datos.items():
        if n in whitelist:
            G.add_node(n, group=info['curso'], title=f"{info['curso']}")
            for dest, rank in info['conexiones'].items():
                if rank <= max_ranking and dest in whitelist:
                    if not G.has_node(dest): G.add_node(dest, group=datos.get(dest, {}).get('curso', 'Desconocido'))
                    es_mutua = False
                    if datos.get(dest, {}).get('conexiones', {}).get(n, 99) <= max_ranking:
                        es_mutua = True
                        mutuas.add(tuple(sorted((n, dest))))
                    G.add_edge(n, dest, weight=rank, mutua=es_mutua)

    if len(G.nodes()) == 0:
        st.warning("Sin conexiones visibles.")
    else:
        # Usamos fondo transparente (None) para que el PNG sea más versátil
        net = Network(height="750px", width="100%", bgcolor=None, font_color="black", directed=True)
        in_degrees = dict(G.in_degree())
        colores = {"Curso 1": "#FFFF00", "Curso 2": "#90EE90", "Curso 3": "#ADD8E6"}
        colores_pop = {"Curso 1": "#FFD700", "Curso 2": "#32CD32", "Curso 3": "#1E90FF"}
        
        for n in G.nodes():
            c = G.nodes[n].get('group', 'Desconocido')
            pop = in_degrees.get(n, 0)
            size = 25 + (pop * 5)
            color = colores_pop.get(c, "#ccc") if pop >= 3 else colores.get(c, "#eee")
            label = f"{n} 👑" if pop > 4 else n
            # Fuente grande y con borde para que se lea bien en el PNG
            net.add_node(n, label=label, title=f"{n}\nVotos: {pop}", color=color, size=size, font={'size': 24, 'face': 'arial', 'strokeWidth': 4, 'strokeColor': 'white', 'color': 'black'})

        dibujadas = set()
        for u, v, d in G.edges(data=True):
            if d['mutua']:
                par = tuple(sorted((u, v)))
                if par not in dibujadas:
                    net.add_edge(u, v, color="red", width=5, arrows={'to': {'enabled': False}})
                    dibujadas.add(par)
            else:
                color = "#666666" if d['weight'] == 1 else "#cccccc"
                net.add_edge(u, v, color=color, width=2 if d['weight']==1 else 1, dashes=True, arrows={'to': {'enabled': True, 'type': 'vee', 'scaleFactor': 1.5}})

        net.barnes_hut(gravity=params['grav'], central_gravity=0.1, spring_length=params['spring'], damping=0.09)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp:
            net.save_graph(tmp.name)
            with open(tmp.name, 'r', encoding='utf-8') as f:
                # Usamos la nueva función de inyección de imagen HD
                html = inyectar_botones_imagen_hd(f.read())
            
        st.components.v1.html(html, height=800)
        c1, c2, c3 = st.columns(3)
        c1.metric("Alumnos", len(G.nodes()))
        c2.metric("Conexiones", len(G.edges()))
        c3.metric("Relaciones Mutuas", len(mutuas))
