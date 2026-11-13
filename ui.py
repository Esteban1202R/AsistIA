"""
AsistIA · Piezas visuales de la interfaz
----------------------------------------
Aquí está todo lo que es "cómo se ve" (colores, botones, dibujos sobre el video),
separado de app.py, que es "qué hace". La IA no está aquí: está en motor.py.
"""
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# ------------------------------------------------------------------ paleta
# Identidad de la Universidad de Cundinamarca. Colores académicos: verde #00482B,
# amarillo #FBE122 y naranja #DAAA00. El verde es la marca (cabecera, pantalla de carga),
# el amarillo resalta sobre el verde y el dorado da los detalles sobre fondo blanco.
# Un verde algo más claro se usa en los botones para que se lean bien como acciones.
C = {
    "institucional": "#00482B",      # verde UdeC (cabecera, pantalla de carga)
    "institucional_osc": "#00351F",
    "amarillo": "#FBE122",           # realce sobre el verde: línea bajo la cabecera, subtítulos
    "dorado": "#DAAA00",             # realce sobre blanco: barrita de los títulos
    "sobre_inst": "#CFE3D6",         # texto secundario sobre el verde institucional
    "fondo": "#F3F5F2",
    "superficie": "#FFFFFF",
    "hover": "#F0F3EF",
    "borde": "#E1E6E0",
    "borde_fuerte": "#CBD3C9",
    "texto": "#14201A",
    "suave": "#5C6A61",
    "tenue": "#9AA69E",
    "acento": "#0B7A43",
    "acento_hover": "#075F33",
    "acento_suave": "#E8F3EC",
    "exito": "#15803D",
    "exito_suave": "#E6F4EA",
    "peligro": "#D32F2F",
    "peligro_hover": "#B71C1C",
    "peligro_suave": "#FDF0F0",
    "aviso": "#C77700",
    "aviso_suave": "#FFF6E5",
    "video": "#0C120E",
}
# colores sobre el video (RGB)
VERDE, ROJO, AMBAR, AMARILLO = (52, 199, 89), (239, 68, 68), (240, 140, 30), (251, 225, 34)

FUENTE = "Segoe UI"
FUENTE_SEMI = "Segoe UI Semibold"

ESCALA = 1.0  # se ajusta según la escala de pantalla de Windows (100 %, 125 %, 150 %...)


def configurar_escala(root):
    global ESCALA
    try:
        ESCALA = max(1.0, root.winfo_fpixels("1i") / 96.0)
    except tk.TclError:
        ESCALA = 1.0
    return ESCALA


def px(n):
    """Convierte píxeles de diseño a píxeles reales de la pantalla."""
    return int(round(n * ESCALA))


def hex_rgb(color):
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


# ------------------------------------------------------------------ estilos ttk
def aplicar_estilos(root):
    st = ttk.Style(root)
    st.theme_use("clam")
    sup = C["superficie"]
    st.configure(".", font=(FUENTE, 10), background=sup, foreground=C["texto"])

    st.configure("TEntry", fieldbackground=sup, bordercolor=C["borde_fuerte"],
                 lightcolor=C["borde_fuerte"], darkcolor=C["borde_fuerte"], padding=(8, 6),
                 insertcolor=C["texto"])
    st.map("TEntry", bordercolor=[("focus", C["acento"])], lightcolor=[("focus", C["acento"])],
           darkcolor=[("focus", C["acento"])])

    st.configure("TCheckbutton", background=sup, foreground=C["texto"], focuscolor=sup,
                 indicatorbackground=sup, indicatorforeground="white", indicatormargin=(0, 2, 8, 2),
                 upperbordercolor=C["borde_fuerte"], lowerbordercolor=C["borde_fuerte"])
    st.map("TCheckbutton",
           indicatorbackground=[("selected", C["acento"]), ("active", C["hover"])],
           background=[("active", sup)])

    st.configure("Treeview", background=sup, fieldbackground=sup, foreground=C["texto"],
                 bordercolor=C["borde"], lightcolor=sup, darkcolor=sup,
                 rowheight=px(30), font=(FUENTE, 10), borderwidth=0)
    st.map("Treeview", background=[("selected", C["acento_suave"])],
           foreground=[("selected", C["texto"])])
    st.configure("Treeview.Heading", background=sup, foreground=C["suave"], relief="flat",
                 font=(FUENTE, 9), bordercolor=C["borde"], lightcolor=sup, darkcolor=sup,
                 padding=(6, 4))
    st.map("Treeview.Heading", background=[("active", sup)])
    st.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])

    st.configure("Vertical.TScrollbar", background=C["borde"], troughcolor=sup, bordercolor=sup,
                 lightcolor=C["borde"], darkcolor=C["borde"], arrowcolor=C["suave"], gripcount=0)

    st.configure("Horizontal.TScale", background=C["acento"], troughcolor=C["borde"],
                 bordercolor=sup, lightcolor=C["acento"], darkcolor=C["acento"], sliderlength=px(18))
    return st


# ------------------------------------------------------------------ widgets
def rect_redondeado(canvas, x1, y1, x2, y2, r, **kw):
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    puntos = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
              x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return canvas.create_polygon(puntos, smooth=True, **kw)


class Boton(tk.Canvas):
    """Botón plano con esquinas redondeadas y efecto al pasar el mouse."""

    ESTILOS = {
        "primario": (C["acento"], C["acento_hover"], "#FFFFFF", None),
        "secundario": (C["superficie"], C["hover"], C["texto"], C["borde_fuerte"]),
        "peligro": (C["peligro"], C["peligro_hover"], "#FFFFFF", None),
        "peligro_suave": (C["superficie"], C["peligro_suave"], C["peligro"], "#F3C4C4"),
        "exito": (C["exito"], "#15803D", "#FFFFFF", None),
    }

    def __init__(self, padre, texto, comando=None, estilo="secundario", alto=38, ancho=None, tam=10):
        self.fuente = tkfont.Font(family=FUENTE_SEMI, size=tam)
        self.texto, self.comando, self.estilo = texto, comando, estilo
        self.habilitado, self.encima = True, False
        ancho = px(ancho) if ancho else self.fuente.measure(texto) + px(36)
        super().__init__(padre, width=ancho, height=px(alto), bg=padre.cget("bg"),
                         highlightthickness=0, bd=0, cursor="hand2")
        self.bind("<Configure>", self._dibujar)
        self.bind("<Enter>", lambda _: self._hover(True))
        self.bind("<Leave>", lambda _: self._hover(False))
        self.bind("<ButtonRelease-1>", self._clic)

    def configurar(self, texto=None, estilo=None, comando=None):
        if texto is not None:
            self.texto = texto
        if estilo is not None:
            self.estilo = estilo
        if comando is not None:
            self.comando = comando
        self._dibujar()

    def habilitar(self, si=True):
        self.habilitado = si
        self.configure(cursor="hand2" if si else "arrow")
        self._dibujar()

    def _hover(self, encima):
        self.encima = encima
        self._dibujar()

    def _clic(self, evento):
        dentro = 0 <= evento.x <= self.winfo_width() and 0 <= evento.y <= self.winfo_height()
        if self.habilitado and dentro and self.comando:
            self.comando()

    def _dibujar(self, _=None):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 4:
            w, h = int(self.cget("width")), int(self.cget("height"))
        fondo, hover, color_txt, borde = self.ESTILOS[self.estilo]
        relleno = hover if (self.encima and self.habilitado) else fondo
        if not self.habilitado:
            relleno, color_txt = (C["hover"], C["tenue"]) if borde else ("#D4D4D8", "#FFFFFF")
        rect_redondeado(self, 1, 1, w - 2, h - 2, px(9), fill=relleno, outline=borde or relleno)
        self.create_text(w / 2, h / 2, text=self.texto, fill=color_txt, font=self.fuente)


class Pestanas(tk.Frame):
    """Barra de pestañas minimalista: texto con una línea de color debajo de la activa."""

    def __init__(self, padre, al_cambiar):
        super().__init__(padre, bg=C["superficie"])
        self.al_cambiar = al_cambiar
        self.items, self.activa = {}, None
        self.linea_base = tk.Frame(self, bg=C["borde"], height=1)
        self.linea_base.pack(side="bottom", fill="x")

    def agregar(self, clave, texto):
        caja = tk.Frame(self, bg=C["superficie"], cursor="hand2")
        caja.pack(side="left", padx=(px(4), 0))
        lbl = tk.Label(caja, text=texto, font=(FUENTE_SEMI, 10), bg=C["superficie"], fg=C["suave"],
                       padx=px(10), pady=px(10), cursor="hand2")
        lbl.pack()
        linea = tk.Frame(caja, height=px(2), bg=C["superficie"])
        linea.pack(fill="x", padx=px(8))
        for w in (caja, lbl):
            w.bind("<Button-1>", lambda _e, c=clave: self.seleccionar(c))
            w.bind("<Enter>", lambda _e, c=clave: self._hover(c, True))
            w.bind("<Leave>", lambda _e, c=clave: self._hover(c, False))
        self.items[clave] = (lbl, linea)

    def _hover(self, clave, encima):
        if clave != self.activa:
            self.items[clave][0].configure(fg=C["texto"] if encima else C["suave"])

    def seleccionar(self, clave):
        self.activa = clave
        for c, (lbl, linea) in self.items.items():
            activa = c == clave
            lbl.configure(fg=C["acento"] if activa else C["suave"])
            linea.configure(bg=C["acento"] if activa else C["superficie"])
        self.al_cambiar(clave)


class Barra(tk.Canvas):
    """Barra de progreso delgada y redondeada."""

    def __init__(self, padre, alto=6, color=None):
        super().__init__(padre, height=px(alto), bg=padre.cget("bg"), highlightthickness=0, bd=0)
        self.valor, self.color = 0.0, color or C["acento"]
        self.bind("<Configure>", lambda _: self._dibujar())

    def poner(self, valor, color=None):
        self.valor = max(0.0, min(1.0, valor))
        if color:
            self.color = color
        self._dibujar()

    def _dibujar(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 4:
            return
        rect_redondeado(self, 0, 0, w, h, h / 2, fill=C["borde"], outline=C["borde"])
        if self.valor > 0:
            rect_redondeado(self, 0, 0, max(h, w * self.valor), h, h / 2, fill=self.color, outline=self.color)


class Puntos(tk.Canvas):
    """Fila de puntos (uno por muestra de registro) que se van llenando."""

    def __init__(self, padre, total):
        super().__init__(padre, height=px(14), bg=padre.cget("bg"), highlightthickness=0, bd=0)
        self.total, self.n = total, 0
        self.bind("<Configure>", lambda _: self._dibujar())

    def poner(self, n):
        self.n = n
        self._dibujar()

    def _dibujar(self):
        self.delete("all")
        r, sep = px(5), px(8)
        for i in range(self.total):
            x = r + 1 + i * (2 * r + sep)
            lleno = i < self.n
            self.create_oval(x - r, 2, x + r, 2 + 2 * r, fill=C["acento"] if lleno else C["borde"],
                             outline=C["acento"] if lleno else C["borde"])


def etiqueta(padre, texto="", tam=10, color="texto", semi=False, **kw):
    return tk.Label(padre, text=texto, font=(FUENTE_SEMI if semi else FUENTE, tam), fg=C[color],
                    bg=kw.pop("bg", padre.cget("bg")), justify="left", anchor="w", **kw)


def separador(padre, pady=10):
    tk.Frame(padre, bg=C["borde"], height=1).pack(fill="x", pady=px(pady))


# ------------------------------------------------------------------ dibujo sobre el video
_FUENTES = {}


def fuente_pil(tam, negrita=False):
    """Fuente con tildes y ñ para dibujar sobre el video (OpenCV no las soporta)."""
    tam = max(8, int(round(tam)))
    clave = (tam, negrita)
    if clave not in _FUENTES:
        nombres = (["seguisb.ttf", "segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"] if negrita
                   else ["segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"])
        for nombre in nombres:
            try:
                _FUENTES[clave] = ImageFont.truetype(nombre, tam)
                break
            except OSError:
                continue
        else:
            _FUENTES[clave] = ImageFont.load_default(size=tam)
    return _FUENTES[clave]


class Escena:
    """Lienzo transparente encima de un cuadro de video: recuadros, etiquetas y guías."""

    def __init__(self, imagen_rgb):
        self.base = imagen_rgb.convert("RGBA")
        self.capa = Image.new("RGBA", self.base.size, (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.capa)
        self.W, self.H = self.base.size
        self.k = self.W / 640  # tamaño relativo, para que todo escale con el video

    def imagen(self):
        return Image.alpha_composite(self.base, self.capa).convert("RGB")

    # -- piezas básicas
    def pastilla(self, x, y, texto, fondo, tam=13, color_txt=(255, 255, 255), ancla="abajo",
                 check=False, alfa=235):
        """Etiqueta redondeada. ancla: 'abajo' (x,y = esquina inferior izq.), 'arriba' o 'centro'."""
        f = fuente_pil(tam * self.k, True)
        l, t, r, b = self.d.textbbox((0, 0), texto, font=f)
        _, ta, _, tb = f.getbbox("ÁgyQ")
        alto_txt = tb - ta
        pad_x, pad_y = int(10 * self.k), int(5 * self.k)
        icono = int(alto_txt * 0.9) + int(6 * self.k) if check else 0
        w, h = (r - l) + 2 * pad_x + icono, alto_txt + 2 * pad_y
        if ancla == "abajo":
            x0, y0 = x, y - h
        elif ancla == "centro":
            x0, y0 = x - w // 2, y - h // 2
        else:
            x0, y0 = x, y
        x0 = int(max(4, min(x0, self.W - w - 4)))
        y0 = int(max(4, min(y0, self.H - h - 4)))
        self.d.rounded_rectangle([x0, y0, x0 + w, y0 + h], radius=h // 2, fill=(*fondo, alfa))
        if check:
            s = alto_txt * 0.9
            cx, cy = x0 + pad_x, y0 + pad_y + (alto_txt - s) / 2
            self.d.line([(cx, cy + s * 0.55), (cx + s * 0.38, cy + s * 0.9), (cx + s, cy + s * 0.15)],
                        fill=(*color_txt, 255), width=max(2, int(2.4 * self.k)), joint="curve")
        self.d.text((x0 + pad_x + icono - l, y0 + pad_y - ta), texto, font=f, fill=(*color_txt, 255))
        return x0, y0, w, h

    def esquinas(self, x, y, w, h, color, grosor=3):
        """Recuadro estilo visor: solo las esquinas marcadas y un borde muy suave."""
        g = max(2, int(grosor * self.k))
        largo = int(min(w, h) * 0.22)
        self.d.rounded_rectangle([x, y, x + w, y + h], radius=int(10 * self.k), outline=(*color, 90),
                                 width=max(1, int(self.k)))
        for cx, cy, dx, dy in ((x, y, 1, 1), (x + w, y, -1, 1), (x, y + h, 1, -1), (x + w, y + h, -1, -1)):
            self.d.line([(cx, cy + dy * largo), (cx, cy), (cx + dx * largo, cy)], fill=(*color, 255),
                        width=g, joint="curve")

    def barra(self, x, y, w, valor, color):
        h = max(4, int(6 * self.k))
        self.d.rounded_rectangle([x, y, x + w, y + h], radius=h // 2, fill=(0, 0, 0, 150))
        if valor > 0:
            self.d.rounded_rectangle([x, y, x + max(h, int(w * valor)), y + h], radius=h // 2,
                                     fill=(*color, 255))

    def puntos_clave(self, puntos):
        r = max(3, int(4 * self.k))
        for (x, y) in puntos:
            self.d.ellipse([x - r - 1, y - r - 1, x + r + 1, y + r + 1], fill=(*AMARILLO, 255))
            self.d.ellipse([x - r + 1, y - r + 1, x + r - 1, y + r - 1], fill=(255, 255, 255, 255))

    # -- escenas completas
    def rostro(self, r, escala, info):
        """Dibuja un rostro analizado. info: dict con presente, progreso, recien, ver_puntos."""
        x, y, w, h = [int(v * escala) for v in r["caja"]]
        conocido = r["persona"] is not None
        color = VERDE if conocido else ROJO
        self.esquinas(x, y, w, h, color)
        if info.get("ver_puntos"):
            self.puntos_clave([(px_ * escala, py_ * escala) for px_, py_ in r["puntos"]])
        if conocido:
            nombre = " ".join(r["persona"]["nombre"].split()[:2])
            self.pastilla(x, y - int(6 * self.k), f"{nombre}  ·  {r['similitud'] * 100:.0f} %", color)
        else:
            self.pastilla(x, y - int(6 * self.k), "Desconocido", color)
        abajo = y + h + int(8 * self.k)
        if info.get("recien"):
            self.pastilla(x, abajo, "Asistencia registrada", VERDE, ancla="arriba", check=True, tam=12)
        elif info.get("presente"):
            self.pastilla(x, abajo, f"Presente desde las {info['presente']}", (39, 39, 42), ancla="arriba",
                          check=True, tam=11, alfa=200)
        elif info.get("progreso") is not None:
            self.barra(x, abajo, w, info["progreso"], VERDE)

    def guia_registro(self, n, total, mensaje):
        """Oscurece todo menos un óvalo central y dibuja el avance alrededor."""
        W, H = self.W, self.H
        ow, oh = int(W * 0.40), int(H * 0.70)
        cx, cy = W // 2, H // 2 + int(14 * self.k)
        caja = [cx - ow // 2, cy - oh // 2, cx + ow // 2, cy + oh // 2]
        self.d.rectangle([0, 0, W, H], fill=(0, 0, 0, 120))
        self.d.ellipse(caja, fill=(0, 0, 0, 0))
        g = max(3, int(5 * self.k))
        exterior = [caja[0] - g, caja[1] - g, caja[2] + g, caja[3] + g]
        self.d.ellipse(exterior, outline=(255, 255, 255, 90), width=g)
        if n > 0:
            self.d.arc(exterior, start=-90, end=-90 + 360 * n / total, fill=(*AMARILLO, 255), width=g)
        self.pastilla(W // 2, int(26 * self.k), f"Registrando  ·  {n} de {total} muestras", (24, 24, 27),
                      ancla="centro", tam=13)
        self.pastilla(W // 2, H - int(24 * self.k), mensaje, (24, 24, 27), ancla="centro", tam=11, alfa=200)

    def insignia(self, texto, color, punto=True):
        """Indicador de estado en la esquina superior izquierda."""
        f = fuente_pil(11 * self.k, True)
        l, t, r, b = self.d.textbbox((0, 0), texto, font=f)
        _, ta, _, tb = f.getbbox("ÁgyQ")
        pad = int(9 * self.k)
        rp = int(4 * self.k) if punto else 0
        w, h = (r - l) + 2 * pad + (2 * rp + int(7 * self.k) if punto else 0), (tb - ta) + 2 * int(5 * self.k)
        x0, y0 = int(12 * self.k), int(12 * self.k)
        self.d.rounded_rectangle([x0, y0, x0 + w, y0 + h], radius=h // 2, fill=(15, 15, 18, 190))
        tx = x0 + pad
        if punto:
            cy = y0 + h // 2
            self.d.ellipse([tx, cy - rp, tx + 2 * rp, cy + rp], fill=(*color, 255))
            tx += 2 * rp + int(7 * self.k)
        self.d.text((tx - l, y0 + int(5 * self.k) - ta), texto, font=f, fill=(255, 255, 255, 255))


def pantalla_sin_camara(ancho, alto, titulo, lineas):
    """Imagen gris oscuro con un mensaje centrado (cuando no hay cámara)."""
    img = Image.new("RGB", (ancho, alto), hex_rgb(C["video"]))
    d = ImageDraw.Draw(img)
    k = ancho / 640
    cx, cy = ancho // 2, alto // 2 - int(40 * k)
    r = int(30 * k)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(80, 80, 90), width=max(2, int(2 * k)))
    d.line([(cx - r * 0.7, cy + r * 0.7), (cx + r * 0.7, cy - r * 0.7)], fill=(80, 80, 90), width=max(2, int(2 * k)))
    f1, f2 = fuente_pil(17 * k, True), fuente_pil(12 * k)
    y = cy + r + int(22 * k)
    d.text((cx, y), titulo, font=f1, fill=(235, 235, 240), anchor="mt")
    y += int(34 * k)
    for linea in lineas:
        d.text((cx, y), linea, font=f2, fill=(150, 150, 160), anchor="mt")
        y += int(22 * k)
    return img


def vector_a_imagen(v, ancho, alto, columnas=16):
    """Muestra los 128 números del embedding como una cuadrícula de colores:
    azul = valor positivo, naranja = negativo, blanco = cerca de cero."""
    v = np.asarray(v, np.float32).reshape(-1, columnas)
    m = float(np.max(np.abs(v))) or 1.0
    t = np.clip(v / m, -1, 1)[..., None]
    blanco = np.array([255, 255, 255], np.float32)
    pos = np.array(hex_rgb(C["acento"]), np.float32)
    neg = np.array([249, 115, 22], np.float32)
    rgb = np.where(t >= 0, blanco + (pos - blanco) * t, blanco + (neg - blanco) * (-t))
    img = Image.fromarray(rgb.astype(np.uint8), "RGB")
    return img.resize((ancho, alto), Image.NEAREST)


def icono_app(tam=64, claro=False):
    """Ícono de AsistIA: un visor (4 esquinas) con un punto amarillo en el centro, como el ojo de la
    cámara. Normal: blanco sobre verde UdeC. claro=True: verde sobre blanco (para fondos verdes)."""
    s = tam * 4  # se dibuja grande y se reduce, para bordes suaves
    fondo = (255, 255, 255, 255) if claro else (*hex_rgb(C["institucional"]), 255)
    trazo = (*hex_rgb(C["institucional"]), 255) if claro else (255, 255, 255, 255)
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, s - 1, s - 1], radius=int(s * 0.28), fill=fondo)
    m, L, g = s * 0.24, s * 0.17, int(s * 0.075)
    for cx, cy, dx, dy in ((m, m, 1, 1), (s - m, m, -1, 1), (m, s - m, 1, -1), (s - m, s - m, -1, -1)):
        d.line([(cx, cy + dy * L), (cx, cy), (cx + dx * L, cy)], fill=trazo, width=g, joint="curve")
    r = s * 0.10
    d.ellipse([s / 2 - r, s / 2 - r, s / 2 + r, s / 2 + r], fill=(*AMARILLO, 255))
    return img.resize((tam, tam), Image.LANCZOS)


def logo_institucional(alto):
    """Logo oficial de la universidad si se guardó en recursos/logo_udec.png (no se incluye
    con el programa: se descarga de la página oficial de la UdeC). Devuelve None si no está."""
    import os
    ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recursos", "logo_udec.png")
    if not os.path.exists(ruta):
        return None
    try:
        img = Image.open(ruta).convert("RGBA")
    except OSError:
        return None
    ancho = max(1, int(img.width * alto / img.height))
    return img.resize((ancho, alto), Image.LANCZOS)


class Casilla(tk.Frame):
    """Casilla de verificación propia: cuadrito redondeado con chulo, texto que se puede leer
    en varias líneas, y todo el renglón es clicable."""

    def __init__(self, padre, texto, variable, comando=None, tam=9, color="texto", wraplength=0):
        bg = padre.cget("bg")
        super().__init__(padre, bg=bg, cursor="hand2")
        self.var, self.comando = variable, comando
        self.lado = px(16)
        self.cv = tk.Canvas(self, width=self.lado + 2, height=self.lado + 2, bg=bg, highlightthickness=0,
                            cursor="hand2")
        self.cv.pack(side="left", anchor="n", pady=(px(2), 0))
        self.lbl = tk.Label(self, text=texto, font=(FUENTE, tam), fg=C[color], bg=bg, justify="left",
                            anchor="w", wraplength=wraplength, cursor="hand2")
        self.lbl.pack(side="left", padx=(px(8), 0), fill="x")
        for w in (self, self.cv, self.lbl):
            w.bind("<Button-1>", self._alternar)
        variable.trace_add("write", lambda *_: self._dibujar())
        self._dibujar()

    def _alternar(self, _=None):
        self.var.set(not self.var.get())
        if self.comando:
            self.comando()

    def _dibujar(self):
        c, s = self.cv, self.lado
        c.delete("all")
        marcado = bool(self.var.get())
        rect_redondeado(c, 1, 1, s, s, px(4), fill=C["acento"] if marcado else C["superficie"],
                        outline=C["acento"] if marcado else C["borde_fuerte"])
        if marcado:
            c.create_line(s * 0.27, s * 0.55, s * 0.45, s * 0.73, s * 0.78, s * 0.33, fill="white",
                          width=max(2, px(2)), capstyle="round", joinstyle="round")


class Deslizador(tk.Canvas):
    """Control deslizante minimalista: pista delgada, parte llena en color y perilla redonda.
    Se mueve con el mouse o con las flechas del teclado."""

    def __init__(self, padre, desde, hasta, variable, comando=None, marca=None):
        super().__init__(padre, height=px(24), bg=padre.cget("bg"), highlightthickness=0, cursor="hand2")
        self.desde, self.hasta, self.var, self.comando, self.marca = desde, hasta, variable, comando, marca
        self.bind("<Configure>", lambda _: self._dibujar())
        self.bind("<Button-1>", self._mover)
        self.bind("<B1-Motion>", self._mover)
        self.bind("<Left>", lambda _: self._paso(-1))
        self.bind("<Right>", lambda _: self._paso(1))
        variable.trace_add("write", lambda *_: self._dibujar())

    def _x(self, valor):
        r = px(9)
        return r + (self.winfo_width() - 2 * r) * (valor - self.desde) / (self.hasta - self.desde)

    def _mover(self, e):
        self.focus_set()
        r = px(9)
        w = max(1, self.winfo_width() - 2 * r)
        t = min(1, max(0, (e.x - r) / w))
        self._poner(self.desde + t * (self.hasta - self.desde))

    def _paso(self, d):
        self._poner(self.var.get() + d)

    def _poner(self, valor):
        self.var.set(round(min(self.hasta, max(self.desde, valor))))
        if self.comando:
            self.comando()

    def _dibujar(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 10:
            return
        cy, g, r = h / 2, px(4), px(9)
        rect_redondeado(self, r, cy - g / 2, w - r, cy + g / 2, g / 2, fill=C["borde"], outline=C["borde"])
        x = self._x(self.var.get())
        rect_redondeado(self, r, cy - g / 2, max(r + g, x), cy + g / 2, g / 2, fill=C["acento"],
                        outline=C["acento"])
        if self.marca is not None:
            xm = self._x(self.marca)
            self.create_line(xm, cy - px(7), xm, cy + px(7), fill=C["tenue"], width=1)
        self.create_oval(x - r, cy - r, x + r, cy + r, fill=C["superficie"], outline=C["acento"],
                         width=max(2, px(2)))



class PanelDesplazable(tk.Frame):
    """Contenedor que usa todo el alto disponible y, si el contenido no cabe (pantallas
    pequeñas o con escala alta), permite desplazarlo con la rueda del mouse."""

    def __init__(self, padre):
        bg = padre.cget("bg")
        super().__init__(padre, bg=bg)
        self.cv = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.barra = ttk.Scrollbar(self, orient="vertical", command=self.cv.yview)
        self.cv.configure(yscrollcommand=self.barra.set)
        self.cv.pack(side="left", fill="both", expand=True)
        self.interior = tk.Frame(self.cv, bg=bg)
        self._ventana = self.cv.create_window(0, 0, window=self.interior, anchor="nw")
        self.cv.bind("<Configure>", lambda _: self.ajustar())

    def ajustar(self):
        self.update_idletasks()
        w, h = self.cv.winfo_width(), self.cv.winfo_height()
        if w < 10:
            return
        necesario = self.interior.winfo_reqheight()
        sobra = necesario > h + 1
        if sobra and not self.barra.winfo_ismapped():
            self.barra.pack(side="right", fill="y", before=self.cv)
        elif not sobra and self.barra.winfo_ismapped():
            self.barra.pack_forget()
        alto = max(h, necesario)
        self.cv.itemconfigure(self._ventana, width=w, height=alto)
        self.cv.configure(scrollregion=(0, 0, w, alto))
        if not sobra:
            self.cv.yview_moveto(0)

    def rueda(self, evento):
        if self.barra.winfo_ismapped():
            self.cv.yview_scroll(int(-evento.delta / 120) * 3, "units")
