"""
AsistIA · Control de asistencia por reconocimiento facial
Interfaz gráfica (Tkinter). Ejecutar:  python app.py
Opciones:  --camara 1   (otra cámara)   ·   --video archivo.mp4   (probar sin cámara)
           --sin-camara (solo fotos)

Organización del código:
  motor.py  -> la IA (detectar, alinear, describir, comparar) y los archivos de datos
  ui.py     -> cómo se ve (colores, botones, dibujos sobre el video)
  app.py    -> qué hace cada botón y el ciclo de la cámara (este archivo)
"""
import argparse
import datetime
import os
import subprocess
import sys
import time
import tkinter as tk
import traceback
from tkinter import filedialog, messagebox, ttk

import cv2
import numpy as np
from PIL import Image, ImageTk

import motor
import ui
from ui import C, FUENTE, FUENTE_SEMI, px

PROC_W, PROC_H = 640, 480        # tamaño en el que la IA analiza cada cuadro
CUADROS_CONFIRMAR = 5            # cuadros seguidos antes de marcar asistencia
SEGUNDOS_DESTACAR = 2.5          # tiempo que se muestra "Asistencia registrada"
LIMITE_REGISTRO_S = 25           # si no logra las muestras en este tiempo, cancela
IMAGENES = [("Imágenes", "*.jpg *.jpeg *.png *.bmp *.webp"), ("Todos los archivos", "*.*")]

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]

CONSENTIMIENTO = (
    "Yo, ______________________, identificado(a) con código ________, autorizo de manera libre, "
    "previa, expresa e informada que mi rostro sea procesado por el software AsistIA, con el único "
    "fin de registrar mi asistencia a la asignatura ______________________.\n\n"
    "Entiendo que:\n"
    "1. Los datos biométricos son datos sensibles (Ley 1581 de 2012) y no estoy obligado(a) a entregarlos.\n"
    "2. No se guardan fotos, solo una representación numérica de mi rostro, almacenada en el equipo del docente.\n"
    "3. Puedo pedir en cualquier momento que se eliminen mis datos.\n"
    "4. Si no acepto, mi asistencia se tomará por otro medio, sin ninguna consecuencia.\n\n"
    "Firma: ______________________    Fecha: ____________")

LIMITES = (
    "Privacidad\n"
    "• Todo se procesa en este computador: nada se envía a internet.\n"
    "• No se guardan fotos. De cada persona solo se guardan vectores de 128 números.\n"
    "• Se puede borrar a cualquier persona y sus datos desde la pestaña Personas.\n\n"
    "Límites que hay que conocer\n"
    "• Suplantación: no detecta si el rostro es real, una foto o un video en un celular. "
    "Úsalo donde el docente vea la cámara.\n"
    "• Sesgos: los modelos se entrenaron con bases de datos que no representan por igual a todas "
    "las poblaciones; la precisión puede variar con el tono de piel, la edad o la luz.\n"
    "• Condiciones: tapabocas, gafas oscuras, gorras, poca luz o gemelos reducen la precisión.\n"
    "• Uso indebido: no debe usarse para vigilar a personas que no aceptaron participar.\n\n"
    "Proyecto académico\n"
    "Introducción a la Inteligencia Artificial · Ingeniería de Sistemas y Computación\n"
    "Universidad de Cundinamarca, Fusagasugá\n"
    "Nikolay Alejandro León Duarte · Ian Esteban Ruiz Posso")


# ------------------------------------------------------------------ utilidades
def leer_imagen(ruta, lado_max=1280):
    """Lee imágenes aunque la ruta tenga tildes (Windows) y las reduce si son muy grandes."""
    try:
        img = cv2.imdecode(np.fromfile(ruta, np.uint8), cv2.IMREAD_COLOR)
    except (OSError, ValueError):
        return None
    if img is None:
        return None
    escala = lado_max / max(img.shape[:2])
    if escala < 1:
        img = cv2.resize(img, None, fx=escala, fy=escala, interpolation=cv2.INTER_AREA)
    return img


def cubrir(img, ancho, alto):
    """Recorta al centro y escala para llenar exactamente ancho x alto (sin bandas negras),
    así una cámara panorámica 16:9 también se ve bien en el visor 4:3."""
    h, w = img.shape[:2]
    objetivo = ancho / alto
    if w / h > objetivo:
        nuevo_w = int(h * objetivo)
        x0 = (w - nuevo_w) // 2
        img = img[:, x0:x0 + nuevo_w]
    elif w / h < objetivo:
        nuevo_h = int(w / objetivo)
        y0 = (h - nuevo_h) // 2
        img = img[y0:y0 + nuevo_h]
    if img.shape[1] != ancho:
        img = cv2.resize(img, (ancho, alto), interpolation=cv2.INTER_AREA)
    return img


def bgr_a_pil(img):
    return Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))


def nombre_corto(nombre, palabras=2):
    return " ".join(nombre.split()[:palabras])


def fecha_larga(d):
    return f"{DIAS[d.weekday()].capitalize()}, {d.day} de {MESES[d.month - 1]}"


def abrir_con_sistema(ruta):
    if os.name == "nt":
        os.startfile(ruta)
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", ruta])


# ------------------------------------------------------------------ aplicación
class App:
    def __init__(self, root, motor_facial, fuente):
        self.root, self.motor = root, motor_facial
        self.registro_dia = motor.RegistroAsistencia()
        self.confirmador = motor.Confirmador(CUADROS_CONFIRMAR)
        self.modo = "normal"                      # normal | registro
        self.asistencia_activa = False
        self.resultados, self.n_cuadro = [], 0
        self.muestras, self.t_muestra, self.t_inicio_registro = [], 0.0, 0.0
        self.msg_registro = ""
        self.caras_registro = np.zeros((0, 15), np.float32)
        self.recien = {}                          # id -> momento en que se marcó
        self.fallos_lectura = 0
        self.t_pipeline = 0.0
        self._vacia_clave, self._id_estado = None, None
        self.var_ver_ia = tk.BooleanVar(value=True)       # panel "La IA por dentro"
        self.var_ver_puntos = tk.BooleanVar(value=True)   # 5 puntos clave sobre el rostro
        self.panel_actual = "asistencia"

        ui.configurar_escala(root)
        self._calcular_tamanos()
        self._abrir_fuente(fuente)
        self._construir_ui()
        if not self.var_ver_ia.get():
            self.tira.pack_forget()
        self._refrescar_personas()
        self._actualizar_pipeline(forzar=True)

        if self.motor.personas:
            self.pestanas.seleccionar("asistencia")
            self.estado("Listo. Presiona «Iniciar asistencia» o la barra espaciadora para empezar.")
        else:
            self.pestanas.seleccionar("registrar")
            self.estado("¡Bienvenido! Empieza registrando a la primera persona.")
        if self.cap is None and fuente is not None:
            self.estado("No se encontró la cámara. Puedes registrar y probar con fotos.", "aviso")

        self._atajos()
        self.root.protocol("WM_DELETE_WINDOW", self.cerrar)
        self._centrar()
        self._reloj()
        self.ciclo()

    # ================================================================ interfaz
    def _calcular_tamanos(self):
        """El video se adapta a la pantalla para que la ventana quepa también en portátiles."""
        alto = self.root.winfo_screenheight()
        con_tira = alto - px(470)              # espacio para el video si se muestra la IA por dentro
        if con_tira >= px(330):
            self.VH = min(px(PROC_H), con_tira)
        else:                                  # pantalla baja: el video primero, la tira se puede activar
            self.var_ver_ia.set(False)
            self.VH = max(px(300), min(px(PROC_H), alto - px(295)))
        self.VW = int(self.VH * PROC_W / PROC_H)
        self.ANCHO_LATERAL = px(380)

    def _construir_ui(self):
        r = self.root
        r.title("AsistIA · Asistencia por reconocimiento facial")
        r.configure(bg=C["fondo"])
        r.resizable(False, False)
        ui.aplicar_estilos(r)
        try:
            self._icono = ImageTk.PhotoImage(ui.icono_app(64))
            r.iconphoto(True, self._icono)
        except tk.TclError:
            pass

        self._construir_cabecera()
        self._construir_barra_estado()

        cuerpo = tk.Frame(r, bg=C["fondo"])
        cuerpo.pack(fill="both", expand=True, padx=px(18), pady=px(16))
        izq = tk.Frame(cuerpo, bg=C["fondo"])
        izq.grid(row=0, column=0, sticky="n")
        der = tk.Frame(cuerpo, bg=C["superficie"], highlightthickness=1, highlightbackground=C["borde"],
                       width=self.ANCHO_LATERAL, height=10)
        der.grid(row=0, column=1, sticky="ns", padx=(px(16), 0))
        der.pack_propagate(False)
        cuerpo.rowconfigure(0, weight=1)

        # visor de la cámara
        marco = tk.Frame(izq, bg=C["video"], width=self.VW, height=self.VH)
        marco.pack()
        marco.pack_propagate(False)
        self.lbl_video = tk.Label(marco, bg=C["video"], bd=0)
        self.lbl_video.pack(fill="both", expand=True)

        self._construir_tira_ia(izq)

        # panel lateral con pestañas
        self.pestanas = ui.Pestanas(der, self._mostrar_panel)
        self.pestanas.pack(fill="x", padx=px(10), pady=(px(4), 0))
        self.contenedor = tk.Frame(der, bg=C["superficie"])
        self.contenedor.pack(fill="both", expand=True, pady=(px(6), px(6)))
        self.ancho_texto = self.ANCHO_LATERAL - px(62)
        self.paneles, self.marcos = {}, {}
        for clave, titulo in (("asistencia", "Asistencia"), ("registrar", "Registrar"),
                              ("personas", "Personas"), ("ayuda", "Cómo funciona")):
            self.pestanas.agregar(clave, titulo)
            marco = ui.PanelDesplazable(self.contenedor)
            interior = tk.Frame(marco.interior, bg=C["superficie"])
            interior.pack(fill="both", expand=True, padx=px(22), pady=px(12))
            self.marcos[clave], self.paneles[clave] = marco, interior
        self._panel_asistencia(self.paneles["asistencia"])
        self._panel_registrar(self.paneles["registrar"])
        self._panel_personas(self.paneles["personas"])
        self._panel_ayuda(self.paneles["ayuda"])
        r.bind_all("<MouseWheel>", self._rueda, add="+")

    def _construir_cabecera(self):
        """Banda verde institucional (UdeC) con la marca, la universidad, la fecha y la hora,
        y debajo una línea amarilla delgada (colores académicos de la UdeC) como detalle de realce."""
        verde = C["institucional"]
        cab = tk.Frame(self.root, bg=verde)
        cab.pack(fill="x")
        tk.Frame(self.root, bg=C["amarillo"], height=px(3)).pack(fill="x")
        dentro = tk.Frame(cab, bg=verde)
        dentro.pack(fill="x", padx=px(20), pady=px(11))

        # marca de la aplicación
        self._logo = ImageTk.PhotoImage(ui.icono_app(px(34), claro=True))
        tk.Label(dentro, image=self._logo, bg=verde).pack(side="left")
        marca = tk.Frame(dentro, bg=verde)
        marca.pack(side="left", padx=(px(11), px(16)))
        tk.Label(marca, text="AsistIA", font=(FUENTE_SEMI, 15), fg="white", bg=verde).pack(anchor="w")
        tk.Label(marca, text="Asistencia con reconocimiento facial", font=(FUENTE, 8), fg=C["sobre_inst"],
                 bg=verde).pack(anchor="w")
        tk.Frame(dentro, bg="#2E6B4B", width=1, height=px(34)).pack(side="left")

        # universidad: logo oficial si está en recursos/logo_udec.png
        logo = ui.logo_institucional(px(38))
        if logo is not None:
            self._logo_udec = ImageTk.PhotoImage(logo)
            tk.Label(dentro, image=self._logo_udec, bg=verde).pack(side="left", padx=(px(16), 0))
        uni = tk.Frame(dentro, bg=verde)
        uni.pack(side="left", padx=(px(12 if logo is not None else 16), 0))
        tk.Label(uni, text="Universidad de Cundinamarca", font=(FUENTE_SEMI, 10), fg="white",
                 bg=verde).pack(anchor="w")
        tk.Label(uni, text="Ingeniería de Sistemas y Computación  ·  Fusagasugá", font=(FUENTE, 8),
                 fg=C["amarillo"], bg=verde).pack(anchor="w")

        # derecha: hora, fecha y aviso de privacidad
        tiempo = tk.Frame(dentro, bg=verde)
        tiempo.pack(side="right")
        self.lbl_reloj = tk.Label(tiempo, text="", font=(FUENTE_SEMI, 15), fg="white", bg=verde)
        self.lbl_reloj.pack(anchor="e")
        self.lbl_fecha = tk.Label(tiempo, text="", font=(FUENTE, 8), fg=C["sobre_inst"], bg=verde)
        self.lbl_fecha.pack(anchor="e")
        tk.Label(dentro, text="●  IA local · sin internet", font=(FUENTE_SEMI, 8), fg=C["amarillo"],
                 bg=C["institucional_osc"], padx=px(10), pady=px(4)).pack(side="right", padx=(0, px(20)))

    def _construir_barra_estado(self):
        barra = tk.Frame(self.root, bg=C["superficie"])
        barra.pack(side="bottom", fill="x")
        tk.Frame(barra, bg=C["borde"], height=1).pack(fill="x")
        dentro = tk.Frame(barra, bg=C["superficie"])
        dentro.pack(fill="x", padx=px(20), pady=px(7))
        self.cv_estado = tk.Canvas(dentro, width=px(10), height=px(10), bg=C["superficie"],
                                   highlightthickness=0)
        self.cv_estado.pack(side="left", padx=(0, px(8)))
        self.lbl_estado = ui.etiqueta(dentro, "", 10)
        self.lbl_estado.pack(side="left")
        ui.etiqueta(dentro, "Espacio: asistencia  ·  P: puntos  ·  Esc: cancelar  ·  Ctrl+1…4: pestañas",
                    8, "tenue").pack(side="right")

    def _construir_tira_ia(self, padre):
        """Las 4 tarjetas que muestran, en vivo, lo que hace la IA con el rostro principal."""
        cab = tk.Frame(padre, bg=C["fondo"])
        cab.pack(fill="x", pady=(px(14), px(8)))
        tk.Frame(cab, bg=C["dorado"], width=px(4), height=px(16)).pack(side="left", padx=(0, px(8)))
        ui.etiqueta(cab, "La IA por dentro", 11, semi=True).pack(side="left")
        ui.etiqueta(cab, "  en vivo, cuadro a cuadro", 9, "suave").pack(side="left")
        ui.Casilla(cab, "Panel", self.var_ver_ia, self._alternar_ia, color="suave").pack(side="right")
        ui.Casilla(cab, "Puntos de la cara", self.var_ver_puntos, self._alternar_puntos,
                   color="suave").pack(side="right", padx=(0, px(16)))

        self.tira = tk.Frame(padre, bg=C["fondo"])
        self.tira.pack(fill="x")
        sep = px(8)
        aw = (self.VW - 3 * sep) // 4
        ah = px(150)
        self.ancho_tarjeta = aw
        pasos = [("Detectar", "YuNet halla la cara y 5 puntos clave."),
                 ("Alinear", "La endereza y recorta a 112 × 112 px."),
                 ("Describir", "SFace la resume en 128 números."),
                 ("Comparar", "Parecido frente a la exigencia (línea).")]
        self.circulos, contenidos = [], []
        for i, (titulo, pie) in enumerate(pasos):
            t = tk.Frame(self.tira, bg=C["superficie"], highlightthickness=1, highlightbackground=C["borde"],
                         width=aw, height=ah)
            t.grid(row=0, column=i, padx=(0 if i == 0 else sep, 0))
            t.pack_propagate(False)
            fila = tk.Frame(t, bg=C["superficie"])
            fila.pack(fill="x", padx=px(10), pady=(px(9), px(4)))
            cv = tk.Canvas(fila, width=px(18), height=px(18), bg=C["superficie"], highlightthickness=0)
            cv.pack(side="left")
            self.circulos.append(cv)
            ui.etiqueta(fila, titulo, 10, semi=True).pack(side="left", padx=(px(6), 0))
            ui.etiqueta(t, pie, 8, "suave", wraplength=aw - px(28)).pack(side="bottom", fill="x",
                                                                         padx=px(10), pady=(0, px(8)))
            c = tk.Frame(t, bg=C["superficie"])
            c.pack(fill="both", expand=True, padx=px(10))
            contenidos.append(c)

        # 1. detección
        fila = tk.Frame(contenidos[0], bg=C["superficie"])
        fila.pack(anchor="w", pady=(px(2), 0))
        self.p_det_num = ui.etiqueta(fila, "0", 20, semi=True)
        self.p_det_num.pack(side="left")
        self.p_det_uni = ui.etiqueta(fila, "rostros", 9, "suave")
        self.p_det_uni.pack(side="left", padx=(px(4), 0), pady=(px(8), 0))
        self.p_det_conf = ui.etiqueta(contenidos[0], "", 9, "suave")
        self.p_det_conf.pack(anchor="w")
        # 2. alineación
        self.lado_rostro = px(64)
        self.p_ali = tk.Label(contenidos[1], bg=C["superficie"], bd=0)
        self.p_ali.pack(anchor="w", pady=(px(2), 0))
        # 3. embedding
        self.vec_w, self.vec_h = aw - px(22), px(44)
        self.p_vec = tk.Label(contenidos[2], bg=C["superficie"], bd=0)
        self.p_vec.pack(anchor="w", pady=(px(4), 0))
        self.p_vec_txt = ui.etiqueta(contenidos[2], "", 8, "tenue")
        self.p_vec_txt.pack(anchor="w", pady=(px(3), 0))
        # 4. comparación
        self.p_cmp_nombre = ui.etiqueta(contenidos[3], "", 10, semi=True)
        self.p_cmp_nombre.pack(anchor="w", pady=(px(2), 0))
        self.cv_cmp = tk.Canvas(contenidos[3], width=aw - px(22), height=px(16), bg=C["superficie"],
                                highlightthickness=0)
        self.cv_cmp.pack(anchor="w", pady=(px(4), px(2)))
        self.p_cmp_txt = ui.etiqueta(contenidos[3], "", 8, "suave")
        self.p_cmp_txt.pack(anchor="w")

        gris = Image.new("RGB", (self.lado_rostro, self.lado_rostro), ui.hex_rgb(C["hover"]))
        self._vacio_rostro = ImageTk.PhotoImage(gris)
        self._vacio_vector = ImageTk.PhotoImage(Image.new("RGB", (self.vec_w, self.vec_h), ui.hex_rgb(C["hover"])))

    # ---------------------------------------------------------------- paneles
    def _titulo(self, padre, titulo, descripcion):
        fila = tk.Frame(padre, bg=C["superficie"])
        fila.pack(fill="x")
        tk.Frame(fila, bg=C["dorado"], width=px(4), height=px(20)).pack(side="left", padx=(0, px(10)))
        ui.etiqueta(fila, titulo, 14, semi=True).pack(side="left")
        ui.etiqueta(padre, descripcion, 9, "suave", wraplength=self.ancho_texto).pack(
            anchor="w", fill="x", pady=(px(3), px(10)))

    def _paso(self, padre, n, texto, arriba=12):
        fila = tk.Frame(padre, bg=C["superficie"])
        fila.pack(fill="x", pady=(px(arriba), px(6)))
        cv = tk.Canvas(fila, width=px(20), height=px(20), bg=C["superficie"], highlightthickness=0)
        cv.pack(side="left")
        cv.create_oval(1, 1, px(19), px(19), fill=C["acento_suave"], outline=C["acento_suave"])
        cv.create_text(px(10), px(10), text=str(n), fill=C["acento"], font=(FUENTE_SEMI, 8))
        ui.etiqueta(fila, texto, 10, semi=True).pack(side="left", padx=(px(8), 0))
        return fila

    def _enlace(self, padre, texto, comando, tam=9):
        lbl = tk.Label(padre, text=texto, font=(FUENTE, tam), fg=C["acento"], bg=padre.cget("bg"),
                       cursor="hand2")
        lbl.bind("<Button-1>", lambda _: comando())
        lbl.bind("<Enter>", lambda _: lbl.configure(font=(FUENTE, tam, "underline")))
        lbl.bind("<Leave>", lambda _: lbl.configure(font=(FUENTE, tam)))
        return lbl

    def _tabla(self, padre, columnas, alto):
        marco = tk.Frame(padre, bg=C["superficie"], highlightthickness=1, highlightbackground=C["borde"])
        tabla = ttk.Treeview(marco, columns=[c[0] for c in columnas], show="headings", height=alto)
        for clave, titulo, ancho, estira, alinear in columnas:
            tabla.heading(clave, text=titulo, anchor=alinear)
            tabla.column(clave, width=px(ancho), minwidth=px(ancho), stretch=estira, anchor=alinear)
        barra = ttk.Scrollbar(marco, orient="vertical", command=tabla.yview)

        def desplazar(primero, ultimo):  # la barra solo aparece si hay más filas de las que caben
            barra.set(primero, ultimo)
            if float(primero) <= 0 and float(ultimo) >= 1:
                barra.pack_forget()
            elif not barra.winfo_ismapped():
                barra.pack(side="right", fill="y", before=tabla)
        tabla.configure(yscrollcommand=desplazar)
        tabla.pack(side="left", fill="both", expand=True)
        return marco, tabla

    def _panel_asistencia(self, p):
        self._titulo(p, "Tomar asistencia",
                     "Cada estudiante mira la cámara uno o dos segundos. Queda anotado una sola vez "
                     "por día, con la hora, en un archivo que se abre en Excel.")
        fila = tk.Frame(p, bg=C["superficie"])
        fila.pack(fill="x")
        self.lbl_num_presentes = ui.etiqueta(fila, "0", 26, semi=True)
        self.lbl_num_presentes.pack(side="left")
        self.lbl_de_presentes = ui.etiqueta(fila, "", 10, "suave")
        self.lbl_de_presentes.pack(side="left", padx=(px(8), 0), pady=(px(14), 0))
        self.lbl_pct = ui.etiqueta(fila, "", 10, "exito", semi=True)
        self.lbl_pct.pack(side="right", pady=(px(14), 0))
        self.barra_presentes = ui.Barra(p, 6, C["exito"])
        self.barra_presentes.pack(fill="x", pady=(px(6), px(16)))

        self.btn_asistencia = ui.Boton(p, "Iniciar asistencia", self.alternar_asistencia, "primario",
                                       alto=46, tam=11)
        self.btn_asistencia.pack(fill="x")

        botones = tk.Frame(p, bg=C["superficie"])
        botones.pack(side="bottom", fill="x", pady=(px(12), 0))
        ui.Boton(botones, "Abrir lista en Excel", self.abrir_lista_hoy, ancho=10).pack(
            side="left", fill="x", expand=True, padx=(0, px(4)))
        ui.Boton(botones, "Ver carpeta", self.abrir_carpeta, ancho=10).pack(
            side="left", fill="x", expand=True, padx=(px(4), 0))

        cab = tk.Frame(p, bg=C["superficie"])
        cab.pack(fill="x", pady=(px(18), px(8)))
        ui.etiqueta(cab, "Lista de hoy", 10, semi=True).pack(side="left")
        self.lbl_aviso_excel = ui.etiqueta(cab, "", 8, "aviso")
        self.lbl_aviso_excel.pack(side="right")
        marco, self.tree_hoy = self._tabla(p, [("ok", "", 34, False, "center"),
                                               ("nombre", "Nombre", 150, True, "w"),
                                               ("hora", "Hora", 64, False, "center")], 4)
        self.tree_hoy.configure(selectmode="none")
        self.tree_hoy.tag_configure("presente", foreground=C["texto"])
        self.tree_hoy.tag_configure("pendiente", foreground=C["tenue"])
        marco.pack(fill="both", expand=True)

    def _panel_registrar(self, p):
        self._titulo(p, "Registrar persona", "Una sola vez por estudiante. No se guardan fotos.")
        self._paso(p, 1, "Datos", arriba=0)
        ui.etiqueta(p, "Nombre completo", 9, "suave").pack(anchor="w")
        self.ent_nombre = ttk.Entry(p, font=(FUENTE, 10))
        self.ent_nombre.pack(fill="x", pady=(px(2), px(8)))
        ui.etiqueta(p, "Código estudiantil (opcional)", 9, "suave").pack(anchor="w")
        self.ent_codigo = ttk.Entry(p, font=(FUENTE, 10))
        self.ent_codigo.pack(fill="x", pady=(px(2), 0))

        self._paso(p, 2, "Consentimiento")
        self.var_consent = tk.BooleanVar(value=False)
        ui.Casilla(p, "La persona leyó y aceptó el consentimiento informado para usar su rostro "
                      "(Ley 1581 de 2012).", self.var_consent,
                   wraplength=self.ancho_texto - px(28)).pack(anchor="w", fill="x")
        self._enlace(p, "Ver formato de consentimiento para imprimir", self.ver_consentimiento).pack(
            anchor="w", padx=(px(24), 0), pady=(px(2), 0))

        self._paso(p, 3, "Capturar el rostro")
        fila = tk.Frame(p, bg=C["superficie"])
        fila.pack(fill="x")
        self.btn_capturar = ui.Boton(fila, "Capturar con cámara", self.iniciar_registro, "primario", ancho=10)
        self.btn_capturar.pack(side="left", fill="x", expand=True, padx=(0, px(4)))
        self.btn_fotos = ui.Boton(fila, "Desde fotos…", self.registrar_desde_fotos)
        self.btn_fotos.pack(side="left")
        fila = tk.Frame(p, bg=C["superficie"])
        fila.pack(fill="x", pady=(px(10), 0))
        self.puntos = ui.Puntos(fila, motor.MUESTRAS_REGISTRO)
        self.puntos.configure(width=motor.MUESTRAS_REGISTRO * px(18))
        self.puntos.pack(side="left")
        self.lbl_prog_reg = ui.etiqueta(fila, f"{motor.MUESTRAS_REGISTRO} muestras en ~3 s", 8, "tenue")
        self.lbl_prog_reg.pack(side="left", padx=(px(6), 0))
        self.btn_cancelar = ui.Boton(p, "Cancelar captura  (Esc)", self.cancelar_registro, "peligro_suave",
                                     alto=34, tam=9)

        self.consejos = tk.Frame(p, bg=C["acento_suave"])
        self.consejos.pack(fill="x", pady=(px(12), 0))
        ui.etiqueta(self.consejos, "Consejo: luz de frente, sin gafas oscuras, gorra ni tapabocas. "
                                   "Durante la captura mueve un poco la cabeza.", 9, "acento",
                    wraplength=self.ancho_texto - px(24)).pack(anchor="w", padx=px(12), pady=px(8))

        self.ent_nombre.bind("<Return>", lambda _: self.ent_codigo.focus_set())
        self.ent_codigo.bind("<Return>", lambda _: self.iniciar_registro())

    def _panel_personas(self, p):
        cab = tk.Frame(p, bg=C["superficie"])
        cab.pack(fill="x")
        tk.Frame(cab, bg=C["dorado"], width=px(4), height=px(20)).pack(side="left", padx=(0, px(10)))
        ui.etiqueta(cab, "Personas registradas", 14, semi=True).pack(side="left")
        self.lbl_total = tk.Label(cab, text="0", font=(FUENTE_SEMI, 9), fg=C["acento"], bg=C["acento_suave"],
                                  padx=px(8), pady=px(1))
        self.lbl_total.pack(side="left", padx=(px(8), 0))
        ui.etiqueta(p, "Para borrar los datos biométricos de alguien (derecho a la supresión), "
                       "selecciónalo y elimínalo.", 9, "suave", wraplength=self.ancho_texto).pack(
            anchor="w", fill="x", pady=(px(3), px(12)))

        self.var_buscar = tk.StringVar()
        caja = tk.Frame(p, bg=C["superficie"])
        caja.pack(fill="x", pady=(0, px(10)))
        self.ent_buscar = ttk.Entry(caja, textvariable=self.var_buscar, font=(FUENTE, 10))
        self.ent_buscar.pack(fill="x")
        self.lbl_ph = tk.Label(caja, text="Buscar por nombre o código", font=(FUENTE, 10), fg=C["tenue"],
                               bg=C["superficie"], cursor="xterm")
        self.lbl_ph.place(x=px(9), rely=0.5, anchor="w")
        self.lbl_ph.bind("<Button-1>", lambda _: self.ent_buscar.focus_set())
        self.var_buscar.trace_add("write", lambda *_: self._refrescar_personas())

        abajo = tk.Frame(p, bg=C["superficie"])
        abajo.pack(side="bottom", fill="x", pady=(px(12), 0))
        ui.Boton(abajo, "Eliminar persona y sus datos", self.eliminar_persona, "peligro_suave").pack(fill="x")
        ui.etiqueta(abajo, "Se guardan en datos/personas.json, sin fotos. Las asistencias pasadas "
                           "se conservan.", 8, "tenue", wraplength=self.ancho_texto).pack(
            anchor="w", pady=(px(8), 0))

        marco, self.tree_personas = self._tabla(p, [("nombre", "Nombre", 140, True, "w"),
                                                    ("codigo", "Código", 84, False, "w"),
                                                    ("fecha", "Registro", 74, False, "center")], 5)
        self.tree_personas.configure(selectmode="browse")
        self.tree_personas.bind("<Delete>", lambda _: self.eliminar_persona())
        marco.pack(fill="both", expand=True)

    def _panel_ayuda(self, p):
        abajo = tk.Frame(p, bg=C["superficie"])
        abajo.pack(side="bottom", fill="x", pady=(px(12), 0))
        ui.Boton(abajo, "Probar con una foto…", self.reconocer_foto, ancho=10).pack(
            side="left", fill="x", expand=True, padx=(0, px(4)))
        ui.Boton(abajo, "Privacidad y límites", self.ver_limites, ancho=10).pack(
            side="left", fill="x", expand=True, padx=(px(4), 0))
        self._titulo(p, "Cómo funciona",
                     "Dos redes neuronales hacen 4 pasos con cada cuadro de la cámara, aquí mismo, "
                     "sin internet. Míralos en vivo en «La IA por dentro».")
        pasos = [("Detectar", "YuNet busca caras y marca ojos, nariz y boca."),
                 ("Alinear", "Endereza el rostro, como en una foto de documento."),
                 ("Describir", "SFace lo convierte en 128 números: la misma persona da números "
                               "parecidos aunque cambie la luz o el gesto."),
                 ("Comparar", "Si el parecido supera la exigencia en 5 cuadros seguidos, es esa "
                              "persona; si no, es «Desconocido».")]
        for i, (titulo, texto) in enumerate(pasos, 1):
            self._paso(p, i, titulo, arriba=0 if i == 1 else 6).pack_configure(
                pady=(px(0 if i == 1 else 6), px(2)))
            ui.etiqueta(p, texto, 9, "suave", wraplength=self.ancho_texto - px(28)).pack(
                anchor="w", padx=(px(28), 0))

        ui.separador(p, 12)
        fila = tk.Frame(p, bg=C["superficie"])
        fila.pack(fill="x")
        ui.etiqueta(fila, "Exigencia de reconocimiento", 10, semi=True).pack(side="left")
        self.lbl_umbral = ui.etiqueta(fila, "", 10, "acento", semi=True)
        self.lbl_umbral.pack(side="right")
        self._enlace(fila, "restablecer", self.restablecer_umbral, tam=8).pack(side="right", padx=(0, px(8)))
        self.var_umbral = tk.DoubleVar(value=round(self.motor.umbral * 100))
        ui.Deslizador(p, 25, 60, self.var_umbral, self.cambiar_umbral,
                      marca=motor.UMBRAL_COSENO * 100).pack(fill="x", pady=(px(6), px(2)))
        self.lbl_umbral_ayuda = ui.etiqueta(p, "", 9, "suave", wraplength=self.ancho_texto)
        self.lbl_umbral_ayuda.pack(anchor="w", fill="x", pady=(px(4), 0))

        self.cambiar_umbral()

    def _mostrar_panel(self, clave):
        for m in self.marcos.values():
            m.pack_forget()
        self.marcos[clave].pack(fill="both", expand=True)
        self.panel_actual = clave
        self.root.after(20, self.marcos[clave].ajustar)
        if clave == "registrar" and self.modo != "registro":
            self.root.after(50, self.ent_nombre.focus_set)

    def _rueda(self, evento):
        """La rueda del mouse desplaza el panel lateral si el puntero está encima."""
        w = evento.widget
        if not isinstance(w, tk.Widget) or isinstance(w, ttk.Treeview):
            return
        if str(w).startswith(str(self.contenedor)):
            self.marcos[self.panel_actual].rueda(evento)

    def _atajos(self):
        r = self.root

        def escribiendo():
            return isinstance(r.focus_get(), (tk.Entry, ttk.Entry))

        def espacio(_):
            if not escribiendo():
                self.alternar_asistencia()
                return "break"

        def puntos(_):
            if not escribiendo():
                self.var_ver_puntos.set(not self.var_ver_puntos.get())
                self._alternar_puntos()

        r.bind("<space>", espacio)
        r.bind("<KeyPress-p>", puntos)
        r.bind("<KeyPress-P>", puntos)
        r.bind("<Escape>", lambda _: self.cancelar_registro() if self.modo == "registro" else None)
        for i, clave in enumerate(("asistencia", "registrar", "personas", "ayuda"), 1):
            r.bind(f"<Control-Key-{i}>", lambda _, c=clave: self.pestanas.seleccionar(c))
        # clic fuera de un campo de texto le quita el foco (para que Espacio funcione)
        r.bind_all("<Button-1>", lambda e: r.focus_set()
                   if isinstance(e.widget, tk.Widget) and not isinstance(e.widget, (tk.Entry, ttk.Entry, ttk.Treeview, ui.Deslizador))
                   and str(e.widget).startswith(str(r)) and e.widget.winfo_toplevel() is r else None, add="+")
        self.var_buscar.trace_add("write", lambda *_: self._placeholder())
        self.ent_buscar.bind("<FocusIn>", lambda _: self._placeholder())
        self.ent_buscar.bind("<FocusOut>", lambda _: self._placeholder())

    def _placeholder(self):
        if self.var_buscar.get():
            self.lbl_ph.place_forget()
        else:
            self.lbl_ph.place(x=px(9), rely=0.5, anchor="w")

    def _centrar(self):
        r = self.root
        r.update_idletasks()
        w, h = r.winfo_reqwidth(), r.winfo_reqheight()
        x = max(0, (r.winfo_screenwidth() - w) // 2)
        y = max(0, (r.winfo_screenheight() - h) // 2 - px(20))
        r.geometry(f"+{x}+{y}")

    # ================================================================ estado y reloj
    def estado(self, texto, tipo="info"):
        colores = {"info": C["acento"], "exito": C["exito"], "aviso": C["aviso"], "error": C["peligro"]}
        fondos = {"exito": C["exito_suave"], "aviso": C["aviso_suave"], "error": C["peligro_suave"]}
        self.cv_estado.delete("all")
        self.cv_estado.create_oval(1, 1, px(9), px(9), fill=colores[tipo], outline=colores[tipo])
        self.lbl_estado.configure(text=texto, fg=C["peligro"] if tipo == "error" else C["texto"])
        # destello suave en la barra para que el mensaje importante se note
        if self._id_estado:
            self.root.after_cancel(self._id_estado)
            self._id_estado = None
        fondo = fondos.get(tipo, C["superficie"])
        self._pintar_estado(fondo)
        if tipo in fondos:
            self._id_estado = self.root.after(2500, lambda: self._pintar_estado(C["superficie"]))

    def _pintar_estado(self, fondo):
        for w in (self.lbl_estado.master, self.lbl_estado, self.cv_estado):
            w.configure(bg=fondo)

    def _reloj(self):
        ahora = datetime.datetime.now()
        self.lbl_reloj.configure(text=ahora.strftime("%H:%M"))
        self.lbl_fecha.configure(text=fecha_larga(ahora.date()))
        # si la app sigue abierta después de medianoche, empieza el archivo del nuevo día
        if ahora.date().isoformat() != self.registro_dia.fecha:
            self.registro_dia.guardar_pendientes()
            self.registro_dia = motor.RegistroAsistencia()
            self.confirmador = motor.Confirmador(CUADROS_CONFIRMAR)
            self._refrescar_hoy()
            self.estado("Nuevo día: se empezó un archivo de asistencia nuevo.", "info")
        # reintenta guardar si el archivo estaba bloqueado (abierto en Excel)
        if self.registro_dia.pendientes:
            if self.registro_dia.guardar_pendientes():
                self.estado("Asistencias pendientes guardadas en el archivo.", "exito")
        self.lbl_aviso_excel.configure(
            text=f"{len(self.registro_dia.pendientes)} sin guardar: cierra el archivo en Excel"
            if self.registro_dia.pendientes else "")
        self.root.after(1000, self._reloj)

    # ================================================================ cámara
    def _abrir_fuente(self, fuente):
        self.es_video = isinstance(fuente, str)
        self.cap = None
        if fuente is None:
            return
        if self.es_video:
            cap = cv2.VideoCapture(fuente)
        else:
            api = cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_ANY
            cap = cv2.VideoCapture(fuente, api)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, PROC_W)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, PROC_H)
        if cap.isOpened():
            self.cap = cap

    def _leer_cuadro(self):
        if self.cap is None:
            return None
        ok, frame = self.cap.read()
        if not ok and self.es_video:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = self.cap.read()
        if not ok or frame is None:
            self.fallos_lectura += 1
            return None
        self.fallos_lectura = 0
        frame = cubrir(frame, PROC_W, PROC_H)
        if not self.es_video:
            frame = cv2.flip(frame, 1)  # efecto espejo, más natural para quien se mira
        return frame

    def ciclo(self):
        inicio = time.time()
        try:
            frame = self._leer_cuadro()
            if frame is None:
                self._mostrar_vacia()
            else:
                self._vacia_clave = None
                self._foto = ImageTk.PhotoImage(self._renderizar(frame))
                self.lbl_video.configure(image=self._foto)
        except Exception as e:  # un error en un cuadro no debe congelar la aplicación
            traceback.print_exc()
            self.estado(f"Error al procesar la imagen: {e}", "error")
        espera = max(5, 30 - int((time.time() - inicio) * 1000))
        self.root.after(espera, self.ciclo)

    def _mostrar_vacia(self):
        if self.cap is None:
            clave = ("No hay cámara disponible",
                     ["Registra con «Desde fotos…» y prueba con «Probar con una foto…».",
                      "Si tienes otra cámara, abre el programa con:  python app.py --camara 1"])
        elif self.fallos_lectura > 15:
            clave = ("La cámara no responde",
                     ["Revisa que esté conectada y que otra aplicación",
                      "(Zoom, Teams, Meet…) no la esté usando."])
        else:
            return
        if clave != self._vacia_clave:
            self._vacia_clave = clave
            self._foto = ImageTk.PhotoImage(ui.pantalla_sin_camara(self.VW, self.VH, *clave))
            self.lbl_video.configure(image=self._foto)

    def _renderizar(self, frame):
        self.n_cuadro += 1
        if self.modo == "registro":
            self.caras_registro = self.motor.detectar(frame)
            self.paso_registro(frame, self.caras_registro)
        elif self.n_cuadro % 2 == 0:  # analiza un cuadro sí y otro no: más fluido
            self.resultados = self.motor.analizar(frame)
            if self.asistencia_activa:
                self._confirmar_asistencias()
            self._actualizar_pipeline()

        img = bgr_a_pil(frame)
        if (self.VW, self.VH) != (PROC_W, PROC_H):
            img = img.resize((self.VW, self.VH), Image.BILINEAR)
        esc = ui.Escena(img)
        k = self.VW / PROC_W

        if self.modo == "registro":
            esc.guia_registro(len(self.muestras), motor.MUESTRAS_REGISTRO, self.msg_registro)
            for c in self.caras_registro:
                x, y, w, h = [int(v * k) for v in c[:4]]
                esc.esquinas(x, y, w, h, ui.AMBAR)
            return esc.imagen()

        ahora = time.time()
        for r in self.resultados:
            info = {"ver_puntos": self.var_ver_puntos.get()}
            p = r["persona"]
            if p is not None and self.asistencia_activa:
                fila = self.registro_dia.fila_de(p)
                if ahora - self.recien.get(p["id"], 0) < SEGUNDOS_DESTACAR:
                    info["recien"] = True
                elif fila:
                    info["presente"] = fila["hora"][:5]
                else:
                    info["progreso"] = self.confirmador.progreso(p["id"])
            esc.rostro(r, k, info)

        if self.asistencia_activa:
            parpadeo = int(ahora * 2) % 2 == 0
            esc.insignia("Tomando asistencia", ui.ROJO if parpadeo else (120, 40, 40))
        else:
            esc.insignia("Video de prueba" if self.es_video else "En vivo", ui.VERDE)
        return esc.imagen()

    def _confirmar_asistencias(self):
        vistos = {r["persona"]["id"]: r for r in self.resultados
                  if r["persona"] is not None and not self.registro_dia.presente(r["persona"])}
        for pid in self.confirmador.actualizar(vistos):
            r = vistos[pid]
            if self.registro_dia.marcar(r["persona"], r["similitud"]):
                self.recien[pid] = time.time()
                self._refrescar_hoy()
                self._sonido()
                if self.registro_dia.pendientes:
                    self.estado(f"{r['persona']['nombre']} quedó presente, pero el archivo está abierto en "
                                "Excel: se guardará al cerrarlo.", "aviso")
                else:
                    self.estado(f"Asistencia registrada: {r['persona']['nombre']}  ·  "
                                f"{r['similitud'] * 100:.0f} % de parecido", "exito")

    @staticmethod
    def _sonido():
        if os.name == "nt":
            try:
                import winsound
                winsound.MessageBeep(winsound.MB_OK)
            except Exception:
                pass

    # ---------------------------------------------------------------- panel didáctico
    def _alternar_puntos(self):
        if self.var_ver_puntos.get():
            self.estado("Puntos de la cara visibles: los 5 puntos clave (ojos, nariz y comisuras de la "
                        "boca) que YuNet usa para alinear el rostro.")
        else:
            self.estado("Puntos de la cara ocultos. Presiona P o marca la casilla para volver a verlos.")

    def _alternar_ia(self):
        if self.var_ver_ia.get():
            self.tira.pack(fill="x")
            self._actualizar_pipeline(forzar=True)
        else:
            self.tira.pack_forget()

    def _circulo(self, i, activo):
        cv = self.circulos[i]
        cv.delete("all")
        fondo, texto = (C["acento"], "white") if activo else (C["hover"], C["tenue"])
        cv.create_oval(1, 1, px(17), px(17), fill=fondo, outline=fondo)
        cv.create_text(px(9), px(9), text=str(i + 1), fill=texto, font=(FUENTE_SEMI, 8))

    def _actualizar_pipeline(self, forzar=False):
        if not self.var_ver_ia.get():
            return
        ahora = time.time()
        if not forzar and ahora - self.t_pipeline < 0.15:
            return
        self.t_pipeline = ahora
        r = self.resultados[0] if self.resultados else None
        n = len(self.resultados)
        for i in range(4):
            self._circulo(i, r is not None)

        self.p_det_num.configure(text=str(n), fg=C["texto"] if n else C["tenue"])
        self.p_det_uni.configure(text="rostro" if n == 1 else "rostros")
        self.p_det_conf.configure(text=f"seguridad {r['confianza'] * 100:.0f} %" if r else "esperando una cara…")

        if r is None:
            self.p_ali.configure(image=self._vacio_rostro)
            self.p_vec.configure(image=self._vacio_vector)
            self.p_vec_txt.configure(text="")
            self.p_cmp_nombre.configure(text="—", fg=C["tenue"])
            self.p_cmp_txt.configure(text="")
            self._barra_comparar(None)
            return

        rostro = bgr_a_pil(r["alineado"]).resize((self.lado_rostro, self.lado_rostro), Image.BILINEAR)
        self._img_ali = ImageTk.PhotoImage(rostro)
        self.p_ali.configure(image=self._img_ali)
        self._img_vec = ImageTk.PhotoImage(ui.vector_a_imagen(r["vector"], self.vec_w, self.vec_h))
        self.p_vec.configure(image=self._img_vec)
        v = r["vector"]
        self.p_vec_txt.configure(text=f"[{v[0]:+.2f}, {v[1]:+.2f}, …]")

        if not self.motor.personas:
            self.p_cmp_nombre.configure(text="Nadie registrado", fg=C["tenue"])
            self.p_cmp_txt.configure(text="Registra a alguien primero")
            self._barra_comparar(None)
            return
        sim, umbral = r["similitud"], self.motor.umbral
        ok = r["persona"] is not None
        self.p_cmp_nombre.configure(text=nombre_corto(r["persona"]["nombre"]) if ok else "Desconocido",
                                    fg=C["exito"] if ok else C["peligro"])
        self.p_cmp_txt.configure(text=f"{max(0, sim) * 100:.0f} % {'≥' if ok else '<'} {umbral * 100:.0f} % exigido")
        self._barra_comparar(sim, ok)

    def _barra_comparar(self, sim, ok=False):
        """Barra de 0 a 100 % con una marca negra en el umbral de exigencia."""
        cv = self.cv_cmp
        cv.delete("all")
        w, h = int(cv.cget("width")), int(cv.cget("height"))
        y0, y1 = px(4), h - px(4)
        ui.rect_redondeado(cv, 0, y0, w, y1, (y1 - y0) / 2, fill=C["borde"], outline=C["borde"])
        if sim is not None and sim > 0:
            color = C["exito"] if ok else C["peligro"]
            ui.rect_redondeado(cv, 0, y0, max(y1 - y0, w * min(1, sim)), y1, (y1 - y0) / 2,
                               fill=color, outline=color)
        xu = w * self.motor.umbral
        cv.create_line(xu, 0, xu, h, fill=C["texto"], width=2)

    # ================================================================ registro
    def _validar_formulario(self):
        nombre = self.ent_nombre.get().strip()
        if len(nombre) < 3:
            self.pestanas.seleccionar("registrar")
            messagebox.showwarning("Falta el nombre", "Escribe el nombre completo de la persona.",
                                   parent=self.root)
            self.ent_nombre.focus_set()
            return False
        if not self.var_consent.get():
            self.pestanas.seleccionar("registrar")
            messagebox.showwarning("Falta el consentimiento",
                                   "Los datos del rostro son datos sensibles (Ley 1581 de 2012).\n"
                                   "Solo se puede registrar a alguien que haya dado su consentimiento.",
                                   parent=self.root)
            return False
        codigo = self.ent_codigo.get().strip()
        otro = self.motor.buscar_codigo(codigo)
        if otro and not messagebox.askyesno(
                "Código repetido", f"El código {codigo} ya pertenece a «{otro['nombre']}».\n"
                                   "¿Continuar de todas formas?", parent=self.root):
            return False
        return True

    def _bloquear_registro(self, si):
        self.btn_capturar.habilitar(not si)
        self.btn_fotos.habilitar(not si)
        if si:
            self.btn_cancelar.pack(fill="x", pady=(px(10), 0), before=self.consejos)
        else:
            self.btn_cancelar.pack_forget()
        self.root.after(20, self.marcos["registrar"].ajustar)

    def iniciar_registro(self):
        if self.modo == "registro":
            return
        if self.cap is None:
            messagebox.showinfo("Sin cámara", "No hay cámara disponible. Usa el botón «Desde fotos…».",
                                parent=self.root)
            return
        if not self._validar_formulario():
            return
        if self.asistencia_activa:
            self.alternar_asistencia()
        self.modo, self.muestras = "registro", []
        self.t_inicio_registro, self.t_muestra = time.time(), 0.0
        self.msg_registro = "Mira a la cámara y mueve un poco la cabeza"
        self.puntos.poner(0)
        self.lbl_prog_reg.configure(text="capturando…")
        self._bloquear_registro(True)
        self.root.focus_set()
        self.estado(f"Capturando el rostro de {self.ent_nombre.get().strip()}…  Mira a la cámara.")

    def paso_registro(self, frame, caras):
        if time.time() - self.t_inicio_registro > LIMITE_REGISTRO_S:
            self._terminar_registro()
            self.estado("No se lograron suficientes muestras. Revisa la luz, acércate e intenta de nuevo.", "aviso")
            return
        if time.time() - self.t_muestra < 0.25:   # una muestra cada 1/4 de segundo
            return
        vector, mensaje = self.motor.muestra_para_registro(frame, caras)
        if vector is None:
            self.msg_registro = mensaje
            return
        self.msg_registro = "¡Bien! Sigue moviendo un poco la cabeza"
        self.muestras.append(vector)
        self.t_muestra = time.time()
        self.puntos.poner(len(self.muestras))
        self.lbl_prog_reg.configure(text=f"{len(self.muestras)} de {motor.MUESTRAS_REGISTRO}")
        if len(self.muestras) >= motor.MUESTRAS_REGISTRO:
            muestras = self.muestras
            self._terminar_registro()
            # se guarda fuera del ciclo de video, para no congelar la imagen con el diálogo
            self.root.after(10, lambda: self._guardar_persona(muestras))

    def cancelar_registro(self):
        if self.modo == "registro":
            self._terminar_registro()
            self.estado("Captura cancelada.", "aviso")

    def _terminar_registro(self):
        self.modo = "normal"
        self.muestras = []
        self.resultados = []
        self._bloquear_registro(False)
        self.puntos.poner(0)
        self.lbl_prog_reg.configure(text=f"{motor.MUESTRAS_REGISTRO} muestras en ~3 s")

    def registrar_desde_fotos(self):
        if self.modo == "registro" or not self._validar_formulario():
            return
        rutas = filedialog.askopenfilenames(title="Fotos de la persona (una sola cara por foto)",
                                            filetypes=IMAGENES, parent=self.root)
        if not rutas:
            return
        self.root.configure(cursor="watch")
        self.root.update_idletasks()
        muestras, rechazadas, usadas = [], [], 0
        try:
            for ruta in rutas:
                img = leer_imagen(ruta)
                vector, mensaje = (None, "no se pudo abrir") if img is None else self.motor.muestra_para_registro(img)
                if vector is None:
                    rechazadas.append(f"•  {os.path.basename(ruta)}: {mensaje}")
                    continue
                usadas += 1
                muestras.append(vector)
                # también la versión en espejo, porque la cámara muestra la imagen invertida
                espejo, _ = self.motor.muestra_para_registro(cv2.flip(img, 1))
                if espejo is not None:
                    muestras.append(espejo)
        finally:
            self.root.configure(cursor="")
        if rechazadas:
            messagebox.showwarning("Algunas fotos no sirven",
                                   f"Se usaron {usadas} de {len(rutas)} fotos.\n\n" + "\n".join(rechazadas[:10]),
                                   parent=self.root)
        if muestras:
            self._guardar_persona(muestras)
        else:
            self.estado("Ninguna foto sirvió. Usa fotos de frente donde solo aparezca esa persona.", "aviso")

    def _guardar_persona(self, muestras):
        parecido, sim = self.motor.ya_registrado(muestras)
        if parecido and not messagebox.askyesno(
                "Posible duplicado",
                f"Este rostro se parece a «{parecido['nombre']}» ({sim * 100:.0f} % de parecido).\n\n"
                "¿Registrarlo de todas formas como una persona nueva?", parent=self.root):
            self.estado("Registro cancelado: la persona ya estaba registrada.", "aviso")
            return
        try:
            persona = self.motor.registrar(self.ent_nombre.get(), self.ent_codigo.get(), muestras,
                                           self.var_consent.get())
        except (ValueError, OSError) as e:
            messagebox.showerror("No se pudo registrar", str(e), parent=self.root)
            return
        self.ent_nombre.delete(0, "end")
        self.ent_codigo.delete(0, "end")
        self.var_consent.set(False)
        self._refrescar_personas()
        self._actualizar_pipeline(forzar=True)
        self.estado(f"{persona['nombre']} quedó registrada con {len(muestras)} muestras "
                    "(solo números, sin fotos). Ya puede tomar asistencia.", "exito")

    # ================================================================ asistencia
    def alternar_asistencia(self):
        if self.modo == "registro":
            return
        if not self.asistencia_activa:
            if self.cap is None:
                messagebox.showinfo("Sin cámara", "Para tomar asistencia se necesita una cámara.",
                                    parent=self.root)
                return
            if not self.motor.personas:
                messagebox.showinfo("Sin personas", "Primero registra al menos una persona.", parent=self.root)
                self.pestanas.seleccionar("registrar")
                return
        self.asistencia_activa = not self.asistencia_activa
        self.confirmador = motor.Confirmador(CUADROS_CONFIRMAR)
        self.recien.clear()
        if self.asistencia_activa:
            self.btn_asistencia.configurar("Detener asistencia", "peligro")
            self.pestanas.seleccionar("asistencia")
            self.estado("Tomando asistencia: cada persona debe mirar la cámara un momento.")
        else:
            self.btn_asistencia.configurar("Iniciar asistencia", "primario")
            self.estado(f"Asistencia detenida. Presentes hoy: {self._contar_presentes()}.")

    def _contar_presentes(self):
        return sum(1 for p in self.motor.personas if self.registro_dia.presente(p))

    def _refrescar_hoy(self):
        t = self.tree_hoy
        t.delete(*t.get_children())
        presentes, pendientes, usadas = [], [], set()
        for p in self.motor.personas:
            fila = self.registro_dia.fila_de(p)
            if fila:
                usadas.add(id(fila))
                presentes.append((fila["hora"], p["nombre"]))
            else:
                pendientes.append(p["nombre"])
        # asistencias de hoy de personas que luego fueron eliminadas
        presentes += [(f["hora"], f["nombre"]) for f in self.registro_dia.filas if id(f) not in usadas]
        for hora, nombre in sorted(presentes):
            t.insert("", "end", values=("✓", nombre, hora[:5]), tags=("presente",))
        for nombre in sorted(pendientes, key=str.lower):
            t.insert("", "end", values=("·", nombre, "—"), tags=("pendiente",))

        n, total = self._contar_presentes(), len(self.motor.personas)
        self.lbl_num_presentes.configure(text=str(n))
        self.lbl_de_presentes.configure(text=f"de {total} presentes" if total else "sin personas registradas")
        self.lbl_pct.configure(text=f"{n * 100 // total} %" if total else "")
        self.barra_presentes.poner(n / total if total else 0)

    def _refrescar_personas(self):
        filtro = self.var_buscar.get().strip().lower() if hasattr(self, "var_buscar") else ""
        t = self.tree_personas
        t.delete(*t.get_children())
        for p in sorted(self.motor.personas, key=lambda p: p["nombre"].lower()):
            if filtro and filtro not in p["nombre"].lower() and filtro not in p.get("codigo", "").lower():
                continue
            fecha = p.get("registrado", "")[:10]
            fecha = f"{fecha[8:10]}/{fecha[5:7]}/{fecha[2:4]}" if len(fecha) == 10 else ""
            t.insert("", "end", iid=p["id"], values=(p["nombre"], p.get("codigo") or "—", fecha))
        self.lbl_total.configure(text=str(len(self.motor.personas)))
        self._refrescar_hoy()

    def eliminar_persona(self):
        sel = self.tree_personas.selection()
        if not sel:
            messagebox.showinfo("Eliminar", "Selecciona una persona de la lista.", parent=self.root)
            return
        persona = next((p for p in self.motor.personas if p["id"] == sel[0]), None)
        if persona is None:
            return
        if messagebox.askyesno("Eliminar datos",
                               f"¿Borrar los datos biométricos de «{persona['nombre']}»?\n\n"
                               "Ya no será reconocida. Las asistencias pasadas se conservan.",
                               icon="warning", parent=self.root):
            try:
                self.motor.eliminar(persona["id"])
            except OSError as e:
                messagebox.showerror("No se pudo eliminar", str(e), parent=self.root)
                return
            self.resultados = []
            self._refrescar_personas()
            self._actualizar_pipeline(forzar=True)
            self.estado(f"Se eliminaron los datos de {persona['nombre']}.", "exito")

    # ================================================================ herramientas
    def reconocer_foto(self):
        ruta = filedialog.askopenfilename(title="Foto para reconocer", filetypes=IMAGENES, parent=self.root)
        if not ruta:
            return
        img = leer_imagen(ruta)
        if img is None:
            messagebox.showerror("Error", "No se pudo abrir la imagen.", parent=self.root)
            return
        resultados = self.motor.analizar(img)

        # ajusta la foto a la pantalla y dibuja encima con el mismo estilo del video
        max_w, max_h = min(px(900), self.root.winfo_screenwidth() - px(120)), \
            min(px(600), self.root.winfo_screenheight() - px(260))
        k = min(max_w / img.shape[1], max_h / img.shape[0], 2.0)
        vista = bgr_a_pil(img).resize((int(img.shape[1] * k), int(img.shape[0] * k)), Image.LANCZOS)
        esc = ui.Escena(vista)
        esc.k = max(0.6, min(vista.size) / 480)
        for r in resultados:
            esc.rostro(r, k, {"ver_puntos": self.var_ver_puntos.get()})

        conocidos = [r["persona"]["nombre"] for r in resultados if r["persona"]]
        n = len(resultados)
        if n == 0:
            resumen = "No se encontró ningún rostro en la foto."
        else:
            resumen = (f"{n} rostro{'s' if n != 1 else ''} detectado{'s' if n != 1 else ''}  ·  "
                       f"{len(conocidos)} reconocido{'s' if len(conocidos) != 1 else ''}")

        v = tk.Toplevel(self.root, bg=C["superficie"])
        v.title(f"Prueba con foto · {os.path.basename(ruta)}")
        v.resizable(False, False)
        v.transient(self.root)
        foto = ImageTk.PhotoImage(esc.imagen())
        lbl = tk.Label(v, image=foto, bg=C["video"], bd=0)
        lbl.image = foto
        lbl.pack(padx=px(18), pady=(px(18), px(12)))
        ui.etiqueta(v, resumen, 11, semi=True).pack(anchor="w", padx=px(18))
        if conocidos:
            ui.etiqueta(v, ", ".join(conocidos), 10, "exito", wraplength=vista.size[0]).pack(anchor="w", padx=px(18))
        fila = tk.Frame(v, bg=C["superficie"])
        fila.pack(fill="x", padx=px(18), pady=(px(10), px(18)))
        ui.etiqueta(fila, "Las fotos sirven para probar: solo la cámara en vivo marca asistencia.", 9,
                    "suave").pack(side="left")
        ui.Boton(fila, "Cerrar", v.destroy, alto=34).pack(side="right")
        v.bind("<Escape>", lambda _: v.destroy())
        v.focus_set()
        self.estado(resumen + (f": {', '.join(conocidos)}" if conocidos else ""))

    def _dialogo_texto(self, titulo, texto, copiar=False):
        v = tk.Toplevel(self.root, bg=C["superficie"])
        v.title(titulo)
        v.transient(self.root)
        v.resizable(False, False)
        ui.etiqueta(v, titulo, 13, semi=True).pack(anchor="w", padx=px(22), pady=(px(18), px(8)))
        caja = tk.Text(v, width=64, height=texto.count("\n") + len(texto) // 85 + 1, wrap="word", font=(FUENTE, 10),
                       bg=C["superficie"], fg=C["texto"], relief="flat", padx=0, pady=0,
                       highlightthickness=0, spacing2=px(2), spacing3=px(4))
        caja.insert("1.0", texto)
        caja.configure(state="disabled")
        caja.pack(padx=px(22))
        fila = tk.Frame(v, bg=C["superficie"])
        fila.pack(fill="x", padx=px(22), pady=(px(10), px(18)))
        ui.Boton(fila, "Cerrar", v.destroy, alto=34).pack(side="right")
        if copiar:
            def copiar_texto():
                self.root.clipboard_clear()
                self.root.clipboard_append(texto)
                boton.configurar("Copiado ✓")
            boton = ui.Boton(fila, "Copiar texto", copiar_texto, "primario", alto=34, ancho=120)
            boton.pack(side="right", padx=(0, px(8)))
        v.bind("<Escape>", lambda _: v.destroy())
        v.focus_set()

    def ver_consentimiento(self):
        self._dialogo_texto("Formato de consentimiento informado", CONSENTIMIENTO, copiar=True)

    def ver_limites(self):
        self._dialogo_texto("Privacidad y límites", LIMITES)

    def abrir_lista_hoy(self):
        if not os.path.exists(self.registro_dia.archivo):
            messagebox.showinfo("Lista de hoy", "Todavía no hay asistencias registradas hoy.", parent=self.root)
            return
        abrir_con_sistema(self.registro_dia.archivo)
        if self.asistencia_activa:
            self.estado("Mientras Excel tenga el archivo abierto, las nuevas asistencias esperan y se "
                        "guardan al cerrarlo.", "aviso")

    def abrir_carpeta(self):
        os.makedirs(motor.DIR_ASISTENCIA, exist_ok=True)
        abrir_con_sistema(motor.DIR_ASISTENCIA)

    def cambiar_umbral(self, *_):
        valor = round(self.var_umbral.get())
        self.motor.umbral = valor / 100
        recomendado = round(motor.UMBRAL_COSENO * 100)
        self.lbl_umbral.configure(text=f"{valor} %")
        if valor > recomendado + 4:
            ayuda = "Estricta: casi no confunde personas, pero puede no reconocer a alguien registrado."
        elif valor < recomendado - 4:
            ayuda = "Permisiva: reconoce con más facilidad, pero puede confundir a dos personas parecidas."
        else:
            ayuda = (f"Equilibrada (recomendado {recomendado} %, la rayita gris). Súbela si confunde "
                     "personas; bájala si no reconoce a alguien.")
        self.lbl_umbral_ayuda.configure(text=ayuda)
        if hasattr(self, "cv_cmp"):
            self._actualizar_pipeline(forzar=True)

    def restablecer_umbral(self):
        self.var_umbral.set(round(motor.UMBRAL_COSENO * 100))
        self.cambiar_umbral()

    def cerrar(self):
        while self.registro_dia.pendientes and not self.registro_dia.guardar_pendientes():
            if not messagebox.askretrycancel(
                    "Asistencias sin guardar",
                    f"Hay {len(self.registro_dia.pendientes)} asistencia(s) sin guardar porque el archivo "
                    "está abierto en Excel.\n\nCierra Excel y presiona «Reintentar».", parent=self.root):
                break
        if self.cap is not None:
            self.cap.release()
        self.root.destroy()


# ------------------------------------------------------------------ arranque
def pantalla_carga(root):
    """Ventanita mientras se cargan (o descargan) los modelos de IA."""
    verde = C["institucional"]
    v = tk.Toplevel(root, bg=verde)
    v.overrideredirect(True)
    marco = tk.Frame(v, bg=verde)
    marco.pack()
    v._logo = ImageTk.PhotoImage(ui.icono_app(px(56), claro=True))
    tk.Label(marco, image=v._logo, bg=verde).pack(pady=(px(36), px(14)), padx=px(110))
    tk.Label(marco, text="AsistIA", font=(FUENTE_SEMI, 20), fg="white", bg=verde).pack()
    tk.Label(marco, text="Asistencia con reconocimiento facial", font=(FUENTE, 9), fg=C["sobre_inst"],
             bg=verde).pack()
    tk.Frame(marco, bg=C["amarillo"], width=px(40), height=px(3)).pack(pady=px(16))
    tk.Label(marco, text="Universidad de Cundinamarca", font=(FUENTE_SEMI, 10), fg="white", bg=verde).pack()
    tk.Label(marco, text="Introducción a la Inteligencia Artificial", font=(FUENTE, 9), fg=C["amarillo"],
             bg=verde).pack()
    texto = tk.Label(marco, text="Cargando los modelos de IA…", font=(FUENTE, 9), fg=C["sobre_inst"],
                     bg=verde, justify="center")
    texto.pack(pady=(px(22), px(30)))
    tk.Frame(v, bg=C["amarillo"], height=px(4)).pack(fill="x", side="bottom")
    v.update_idletasks()
    w, h = v.winfo_reqwidth(), v.winfo_reqheight()
    v.geometry(f"+{(v.winfo_screenwidth() - w) // 2}+{(v.winfo_screenheight() - h) // 2}")
    v.update()

    def avisar(msg):
        texto.configure(text=msg.replace(" ...", "…") + "\n(solo la primera vez, unos 39 MB)")
        v.update()
    return v, avisar


def main():
    parser = argparse.ArgumentParser(description="AsistIA · asistencia por reconocimiento facial")
    parser.add_argument("--camara", type=int, default=0, help="índice de la cámara (0 por defecto)")
    parser.add_argument("--video", help="usar un archivo de video en vez de la cámara (para pruebas)")
    parser.add_argument("--sin-camara", action="store_true", help="abrir sin cámara (solo fotos)")
    args = parser.parse_args()

    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)  # texto nítido en pantallas con escala
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("AsistIA.App")  # ícono en la barra
        except Exception:
            pass

    raiz = tk.Tk()
    raiz.withdraw()
    ui.configurar_escala(raiz)
    splash, avisar = pantalla_carga(raiz)
    try:
        motor_facial = motor.MotorFacial(avisar=avisar)
    except Exception as e:
        splash.destroy()
        messagebox.showerror("AsistIA", "No se pudieron cargar los modelos de IA.\n"
                                        "La primera vez se necesita internet para descargarlos (39 MB).\n\n"
                             + str(e))
        raiz.destroy()
        return
    fuente = None if args.sin_camara else (args.video or args.camara)
    splash.destroy()
    App(raiz, motor_facial, fuente)
    raiz.deiconify()
    raiz.mainloop()


if __name__ == "__main__":
    main()
