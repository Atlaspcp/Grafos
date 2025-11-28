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
    if not os.path.exists(FILE_GRUPOS):
        return {}
    try:
        with open(FILE_GRUPOS, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def guardar_nuevo_grupo(nombre_grupo, lista_alumnos):
    grupos = leer_grupos_guardados()
    grupos[nombre_grupo] = lista_alumnos
    with open(FILE_GRUPOS, 'w', encoding='utf-8') as f:
        json.dump(grupos, f, ensure_ascii=False, indent=4)

def eliminar_grupo(nombre_grupo):
    grupos = leer_grupos_guardados()
    if nombre_grupo in grupos:
        del grupos[nombre_grupo]
        with open(FILE_GRUPOS, 'w', encoding='utf-8') as f:
            json.dump(grupos, f, ensure_ascii=False, indent=4)

# --- Checkbox Modificado para aceptar pre-selección ---
def crear_grilla_checkbox(nombres, key_prefix, lista_preseleccion=None):
    """
    lista_preseleccion: Lista de nombres que deben aparecer marcados.
                        Si es None, se usa el comportamiento manual estándar.
    """
    seleccionados = []
    
    # Determinar estado inicial del "Seleccionar Todos"
    # Si hay una lista cargada y cubre casi todos, o si el usuario lo marca manual
    estado_todos = False 
    
    # Checkbox maestro
    todos = st.checkbox("Seleccionar Todos", value=estado_todos, key=f"all_{key_prefix}")
    
    col1, col2 = st.columns(2)
    for i, n in enumerate(nombres):
        # Lógica de marcado:
        # 1. Si "Todos" está marcado -> True
        # 2. Si hay una lista guardada y el nombre está en ella -> True
        # 3. Si no, False
        is_checked = False
        if todos:
            is_checked = True
        elif lista_preseleccion is not None:
            if n in lista_preseleccion:
                is_checked = True
        
        with (col1 if i%2==0 else col2):
            # Usamos 'value' para forzar el estado visual
            if st.checkbox(n, value=is_checked, key=f"{key_prefix}_{i}_{n}"):
                seleccionados.append(n)
                
    return seleccionados

def inyectar_botones_con_jspdf(html_str):
    head_injection = """<script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>"""
    script_botones = """
    <script>
    function centrarGrafo() { if (typeof network !== 'undefined') network.fit({ animation: { duration: 1000 } }); }
    async function descargarPDFDirecto() {
        const { jsPDF } = window.jspdf;
        var canvas = document.getElementsByTagName('canvas')[0];
        if (!canvas) return;
        var originalWidth = canvas.width; var originalHeight = canvas.height;
        var originalStyleWidth = canvas.style.width; var originalStyleHeight = canvas.style.height;
        var ctx = canvas.getContext('2d');
        var scaleFactor = 3; 
        canvas.width = originalWidth * scaleFactor; canvas.height = originalHeight * scaleFactor;
        canvas.style.width = originalStyleWidth; canvas.style.height = originalStyleHeight;
        ctx.scale(scaleFactor, scaleFactor);
        if (typeof network !== 'undefined') network.redraw();
        await new Promise(r => setTimeout(r, 1000));
        try {
            var imgData = canvas.toDataURL("image/jpeg", 1.0);
            var pdfWidth = canvas.width * 0.264583 / scaleFactor;
            var pdfHeight = canvas.height * 0.264583 / scaleFactor;
            var orientation = (pdfWidth > pdfHeight) ? 'l' : 'p';
            const pdf = new jsPDF({ orientation: orientation, unit: 'mm', format: [pdfWidth + 20, pdfHeight + 20] });
            pdf.text("Sociograma", 10, 10);
            pdf.addImage(imgData, 'JPEG', 10, 15, pdfWidth, pdfHeight);
            pdf.save("sociograma_alta_calidad.pdf");
        } catch (error) { alert("Error: " + error.message); }
        canvas.width = originalWidth; canvas.height = originalHeight;
        canvas.style.width = originalStyleWidth; canvas.style.height = originalStyleHeight;
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        if (typeof network !== 'undefined') network.redraw();
    }
    </script>
    <style>
    .btn-container { position: absolute; top: 10px; right: 10px; z-index: 1000; display: flex; gap: 10px; }
    .btn-action { padding: 8px 16px; border: none; border-radius: 5px; cursor: pointer; font-family: sans-serif; font-weight: bold; font-size: 14px; box-shadow: 0 2px 4px rgba(0,0,0,0.2); color: white; }
    .btn-center { background-color: #555; } .btn-center:hover { background-color: #333; }
    .btn-print { background-color: #27AE60; } .btn-print:hover { background-color: #219150; }
    </style>
    <div class="btn-container">
        <button onclick="centrarGrafo()" class="btn-action btn-center">🔍 Centrar</button>
        <button onclick="descargarPDFDirecto()" class="btn-action btn-print">📥 Descargar PDF (Alta Calidad)</button>
    </div>
    """
    html_with_head = html_str.replace('<head>', '<head>' + head_injection)
    return html_with_head.replace('</body>', f'{script_botones}</body>')

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
    
    # Selector para cargar
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
        # Expandimos si hay alguien de ese curso en la preselección cargada
        expandir = False
        if lista_preseleccion:
            if any(n in lista_preseleccion for n in nombres):
                expandir = True
        elif c_nombre == "Curso 1":
            expandir = True

        with st.expander(f"{c_nombre} ({len(nombres)})", expanded=expandir):
            if nombres: 
                # Pasamos la lista cargada (si existe) para que marque las casillas
                sel = crear_grilla_checkbox(nombres, c_nombre.lower().replace(" ", ""), lista_preseleccion)
                seleccionados_totales.extend(sel)

    # --- SECCIÓN PARA GUARDAR LO ACTUAL ---
    if seleccionados_totales:
        st.markdown("---")
        st.subheader("💾 Guardar Selección Actual")
        nombre_nuevo_grupo = st.text_input("Nombre para el nuevo grupo (ej: 'Caso Juan')")
        if st.button("Guardar Grupo"):
            if nombre_nuevo_grupo:
                guardar_nuevo_grupo(nombre_nuevo_grupo, seleccionados_totales)
                st.success(f"Grupo '{nombre_nuevo_grupo}' guardado.")
                st.rerun() # Recargar para que aparezca arriba
            else:
                st.error("Escribe un nombre para el grupo.")

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
        net = Network(height="750px", width="100%", bgcolor="white", font_color="black", directed=True)
        in_degrees = dict(G.in_degree())
        colores = {"Curso 1": "#FFFF00", "Curso 2": "#90EE90", "Curso 3": "#ADD8E6"}
        colores_pop = {"Curso 1": "#FFD700", "Curso 2": "#32CD32", "Curso 3": "#1E90FF"}
        
        for n in G.nodes():
            c = G.nodes[n].get('group', 'Desconocido')
            pop = in_degrees.get(n, 0)
            size = 25 + (pop * 5)
            color = colores_pop.get(c, "#ccc") if pop >= 3 else colores.get(c, "#eee")
            label = f"{n} 👑" if pop > 4 else n
            net.add_node(n, label=label, title=f"{n}\nVotos: {pop}", color=color, size=size, font={'size': 20, 'face': 'arial', 'strokeWidth': 3, 'strokeColor': 'white'})

        dibujadas = set()
        for u, v, d in G.edges(data=True):
            if d['mutua']:
                par = tuple(sorted((u, v)))
                if par not in dibujadas:
                    net.add_edge(u, v, color="red", width=4, arrows={'to': {'enabled': False}})
                    dibujadas.add(par)
            else:
                color = "#666666" if d['weight'] == 1 else "#cccccc"
                net.add_edge(u, v, color=color, width=2 if d['weight']==1 else 1, dashes=True, arrows={'to': {'enabled': True, 'type': 'vee'}})

        net.barnes_hut(gravity=params['grav'], central_gravity=0.1, spring_length=params['spring'], damping=0.09)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp:
            net.save_graph(tmp.name)
            with open(tmp.name, 'r', encoding='utf-8') as f:
                html = inyectar_botones_con_jspdf(f.read())
            
        st.components.v1.html(html, height=800)
        c1, c2, c3 = st.columns(3)
        c1.metric("Alumnos", len(G.nodes()))
        c2.metric("Conexiones", len(G.edges()))
        c3.metric("Relaciones Mutuas", len(mutuas))
