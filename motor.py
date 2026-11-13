"""
AsistIA · Motor de reconocimiento facial
-----------------------------------------
Todo corre en el computador, sin APIs ni servicios en la nube.

Flujo de la IA:
  1. DETECCIÓN       -> YuNet (red neuronal convolucional) encuentra los rostros en la imagen
                        y 5 puntos clave (ojos, nariz, comisuras de la boca).
  2. ALINEACIÓN      -> con esos puntos se endereza y recorta el rostro a 112x112 píxeles.
  3. EMBEDDING       -> SFace (red neuronal) convierte el rostro en un vector de 128 números:
                        rostros de la misma persona quedan "cerca" en ese espacio.
  4. COMPARACIÓN     -> similitud coseno contra los vectores guardados; si supera el umbral
                        es esa persona, si no, es "Desconocido".

Privacidad por diseño: NO se guardan fotos, solo los vectores de 128 números de las personas
que dieron su consentimiento. Se pueden borrar en cualquier momento (Ley 1581 de 2012).
"""
import csv
import datetime
import json
import os
import socket
import unicodedata
import urllib.request
import uuid

import cv2
import numpy as np

try:  # silencia avisos internos de OpenCV que no son errores
    cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)
except Exception:
    pass

BASE = os.path.dirname(os.path.abspath(__file__))
DIR_MODELOS = os.path.join(BASE, "modelos")
DIR_DATOS = os.path.join(BASE, "datos")
DIR_ASISTENCIA = os.path.join(BASE, "asistencia")
ARCHIVO_DB = os.path.join(DIR_DATOS, "personas.json")

_URL = "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/"
MODELOS = {
    "detector": ("face_detection_yunet_2023mar.onnx",
                 _URL + "face_detection_yunet/face_detection_yunet_2023mar.onnx"),
    "reconocedor": ("face_recognition_sface_2021dec.onnx",
                    _URL + "face_recognition_sface/face_recognition_sface_2021dec.onnx"),
}

UMBRAL_COSENO = 0.363       # umbral recomendado para SFace (OpenCV Zoo)
CONFIANZA_DETECCION = 0.85  # qué tan seguro debe estar YuNet de que es un rostro
MUESTRAS_REGISTRO = 10      # vectores que se guardan por persona
TAMANO_MIN_ROSTRO = 60      # píxeles; rostros más pequeños se ignoran al registrar


def sin_tildes(texto):
    """OpenCV no dibuja tildes ni ñ: 'León' -> 'Leon'."""
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")


def asegurar_modelos(avisar=print):
    """Descarga los dos modelos ONNX la primera vez (unos 39 MB en total)."""
    os.makedirs(DIR_MODELOS, exist_ok=True)
    rutas = {}
    for clave, (nombre, url) in MODELOS.items():
        ruta = os.path.join(DIR_MODELOS, nombre)
        if not os.path.exists(ruta) or os.path.getsize(ruta) < 100_000:
            avisar(f"Descargando modelo {nombre} ...")
            temporal = ruta + ".parcial"
            socket.setdefaulttimeout(60)
            urllib.request.urlretrieve(url, temporal)
            os.replace(temporal, ruta)
        rutas[clave] = ruta
    return rutas


class MotorFacial:
    def __init__(self, umbral=UMBRAL_COSENO, avisar=print):
        rutas = asegurar_modelos(avisar)
        self.umbral = umbral
        self.detector = cv2.FaceDetectorYN.create(
            rutas["detector"], "", (320, 320), CONFIANZA_DETECCION, 0.3, 50)
        self.reconocedor = cv2.FaceRecognizerSF.create(rutas["reconocedor"], "")
        self.personas = []
        self._matriz = np.zeros((0, 128), np.float32)   # todos los vectores guardados
        self._dueno = []                                  # índice de persona de cada vector
        self.cargar()

    # ---------------- base de datos local ----------------
    def cargar(self):
        if os.path.exists(ARCHIVO_DB):
            with open(ARCHIVO_DB, encoding="utf-8") as f:
                self.personas = json.load(f)
        self._reindexar()

    def guardar(self):
        os.makedirs(DIR_DATOS, exist_ok=True)
        temporal = ARCHIVO_DB + ".tmp"
        with open(temporal, "w", encoding="utf-8") as f:
            json.dump(self.personas, f, ensure_ascii=False, indent=1)
        os.replace(temporal, ARCHIVO_DB)
        self._reindexar()

    def _reindexar(self):
        vectores, dueno = [], []
        for i, p in enumerate(self.personas):
            for v in p["vectores"]:
                vectores.append(v)
                dueno.append(i)
        self._matriz = np.asarray(vectores, np.float32).reshape(-1, 128)
        self._dueno = np.asarray(dueno, int)

    def registrar(self, nombre, codigo, vectores, consentimiento):
        nombre = (nombre or "").strip()
        if not consentimiento:
            raise ValueError("Sin consentimiento informado no se puede registrar a nadie.")
        if not nombre:
            raise ValueError("Escribe el nombre de la persona.")
        if len(vectores) < 1:
            raise ValueError("No hay muestras válidas del rostro.")
        persona = {
            "id": uuid.uuid4().hex[:8],
            "nombre": nombre,
            "codigo": (codigo or "").strip(),
            "registrado": datetime.datetime.now().isoformat(timespec="seconds"),
            "consentimiento": True,
            "vectores": [[round(float(x), 5) for x in v] for v in vectores],
        }
        self.personas.append(persona)
        self.guardar()
        return persona

    def buscar_codigo(self, codigo):
        """Devuelve la persona que ya tiene ese código (o None)."""
        codigo = (codigo or "").strip()
        if not codigo:
            return None
        return next((p for p in self.personas if p.get("codigo", "").strip() == codigo), None)

    def eliminar(self, persona_id):
        antes = len(self.personas)
        self.personas = [p for p in self.personas if p["id"] != persona_id]
        self.guardar()
        return len(self.personas) < antes

    # ---------------- IA ----------------
    def detectar(self, imagen):
        """Devuelve una matriz N x 15: caja (x, y, w, h), 5 puntos clave y confianza."""
        alto, ancho = imagen.shape[:2]
        self.detector.setInputSize((ancho, alto))
        _, caras = self.detector.detect(imagen)
        return caras if caras is not None else np.zeros((0, 15), np.float32)

    def vector(self, imagen, cara):
        """Alinea el rostro y lo convierte en un vector de 128 números de largo 1."""
        return self.vector_y_rostro(imagen, cara)[0]

    def vector_y_rostro(self, imagen, cara):
        """Igual que vector(), pero también devuelve el rostro alineado (112 x 112),
        que la interfaz muestra para explicar el paso de alineación."""
        alineado = self.reconocedor.alignCrop(imagen, cara)
        v = self.reconocedor.feature(alineado).flatten().astype(np.float32)
        return v / (np.linalg.norm(v) + 1e-9), alineado

    def identificar(self, v):
        """Compara un vector con todos los guardados. Devuelve (persona o None, similitud)."""
        if len(self._matriz) == 0:
            return None, 0.0
        similitudes = self._matriz @ v                 # coseno, porque todos tienen largo 1
        k = int(np.argmax(similitudes))
        mejor = float(similitudes[k])
        if mejor >= self.umbral:
            return self.personas[int(self._dueno[k])], mejor
        return None, mejor

    def ya_registrado(self, vectores):
        """Evita registrar dos veces a la misma persona."""
        if len(self._matriz) == 0 or not vectores:
            return None, 0.0
        promedio = np.mean(vectores, axis=0)
        return self.identificar(promedio / (np.linalg.norm(promedio) + 1e-9))

    def analizar(self, imagen):
        """Ejecuta los 4 pasos sobre cada rostro de la imagen.
        Cada resultado trae todo lo necesario para dibujarlo y para explicarlo."""
        resultados = []
        for cara in self.detectar(imagen):
            v, alineado = self.vector_y_rostro(imagen, cara)
            persona, similitud = self.identificar(v)
            x, y, w, h = [int(round(c)) for c in cara[:4]]
            puntos = [(float(cara[4 + 2 * i]), float(cara[5 + 2 * i])) for i in range(5)]
            resultados.append({"caja": (x, y, w, h), "persona": persona, "similitud": similitud,
                               "confianza": float(cara[14]), "puntos": puntos,
                               "vector": v, "alineado": alineado})
        # el rostro más grande primero: es el que se explica en el panel didáctico
        resultados.sort(key=lambda r: r["caja"][2] * r["caja"][3], reverse=True)
        return resultados

    def muestra_para_registro(self, imagen, caras=None):
        """Devuelve (vector, mensaje). Solo acepta imágenes con UN rostro claro y grande."""
        caras = self.detectar(imagen) if caras is None else caras
        if len(caras) == 0:
            return None, "No veo ningún rostro"
        if len(caras) > 1:
            return None, "Hay más de un rostro: debe aparecer solo la persona a registrar"
        cara = caras[0]
        if min(cara[2], cara[3]) < TAMANO_MIN_ROSTRO:
            return None, "Acércate más a la cámara"
        return self.vector(imagen, cara), "ok"


def dibujar(imagen, resultados, umbral=UMBRAL_COSENO):
    """Pinta recuadros: verde = persona reconocida, rojo = desconocido."""
    for r in resultados:
        x, y, w, h = r["caja"]
        conocido = r["persona"] is not None
        color = (80, 200, 60) if conocido else (60, 60, 230)
        nombre = sin_tildes(r["persona"]["nombre"]) if conocido else "Desconocido"
        etiqueta = f"{nombre}  {r['similitud'] * 100:.0f}%"
        cv2.rectangle(imagen, (x, y), (x + w, y + h), color, 2)
        (tw, th), _ = cv2.getTextSize(etiqueta, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)
        y_txt = max(y, th + 10)
        cv2.rectangle(imagen, (x, y_txt - th - 10), (x + tw + 10, y_txt), color, -1)
        cv2.putText(imagen, etiqueta, (x + 5, y_txt - 5), cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, (255, 255, 255), 1, cv2.LINE_AA)
    return imagen


class Confirmador:
    """Exige que una persona aparezca en varios cuadros seguidos antes de marcarla,
    para que un error de un solo cuadro no registre asistencia falsa."""

    def __init__(self, cuadros_necesarios=5):
        self.necesarios = cuadros_necesarios
        self.conteo = {}

    def actualizar(self, ids_vistos):
        """Suma un cuadro a quien se ve ahora y reinicia a quien dejó de verse.
        Devuelve los ids que acaban de completar los cuadros necesarios."""
        ids_vistos = set(ids_vistos)
        self.conteo = {i: self.conteo.get(i, 0) + 1 for i in ids_vistos}
        return [i for i, n in self.conteo.items() if n == self.necesarios]

    def progreso(self, persona_id):
        """Fracción (0 a 1) de cuadros seguidos acumulados por esa persona."""
        return min(1.0, self.conteo.get(persona_id, 0) / self.necesarios)


class RegistroAsistencia:
    """Un CSV por día en la carpeta asistencia/ (se abre directo en Excel)."""

    COLUMNAS = ["fecha", "hora", "nombre", "codigo", "similitud_%"]

    def __init__(self, fecha=None):
        self.fecha = fecha or datetime.date.today().isoformat()
        os.makedirs(DIR_ASISTENCIA, exist_ok=True)
        self.archivo = os.path.join(DIR_ASISTENCIA, f"asistencia_{self.fecha}.csv")
        self.filas = []
        self.pendientes = []   # filas que aún no se pudieron escribir en el archivo
        if os.path.exists(self.archivo):
            with open(self.archivo, encoding="utf-8-sig", newline="") as f:
                self.filas = list(csv.DictReader(f, delimiter=";"))

    def fila_de(self, persona):
        """Fila de asistencia de hoy de esa persona (o None). Si tiene código se busca
        por código, para que cambiar una tilde en el nombre no duplique la asistencia."""
        codigo = (persona.get("codigo") or "").strip()
        for f in self.filas:
            if codigo and (f.get("codigo") or "").strip() == codigo:
                return f
            if not codigo and f.get("nombre") == persona["nombre"]:
                return f
        return None

    def presente(self, persona):
        return self.fila_de(persona) is not None

    def marcar(self, persona, similitud):
        """Marca asistencia una sola vez por día. Devuelve True si es nueva."""
        if self.presente(persona):
            return False
        fila = {"fecha": self.fecha, "hora": datetime.datetime.now().strftime("%H:%M:%S"),
                "nombre": persona["nombre"], "codigo": persona.get("codigo", ""),
                "similitud_%": f"{similitud * 100:.0f}"}
        self.filas.append(fila)
        self.pendientes.append(fila)
        self.guardar_pendientes()
        return True

    def guardar_pendientes(self):
        """Escribe en el CSV las filas que faltan. Si Excel tiene el archivo abierto (Windows
        lo bloquea), no falla: las deja pendientes y se reintenta después. True = todo guardado."""
        if not self.pendientes:
            return True
        nuevo = not os.path.exists(self.archivo)
        try:
            with open(self.archivo, "a", encoding="utf-8-sig" if nuevo else "utf-8", newline="") as f:
                escritor = csv.DictWriter(f, fieldnames=self.COLUMNAS, delimiter=";")
                if nuevo:
                    escritor.writeheader()
                escritor.writerows(self.pendientes)
        except OSError:
            return False
        self.pendientes = []
        return True
