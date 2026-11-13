# AsistIA: control de asistencia por reconocimiento facial

Introducción a la Inteligencia Artificial · Ingeniería de Sistemas y Computación · Universidad de Cundinamarca, Fusagasugá
Nikolay Alejandro León Duarte · Ian Esteban Ruiz Posso

## ¿De qué se trata?

Llamar lista o pasar una hoja de firmas consume minutos de cada clase, y en la hoja cualquiera puede firmar por otro. **AsistIA** toma la asistencia con la cámara del computador. Cada estudiante se registra una sola vez, con su consentimiento. Desde ahí, cuando la cámara lo reconoce, queda anotado con la hora en un archivo del día que se abre en Excel.

Toda la inteligencia artificial corre en el computador. No usa APIs, internet ni servicios en la nube (solo descarga los modelos la primera vez, si no vienen incluidos). Además, **no guarda fotos**: de cada persona solo guarda un vector de 128 números.

## ¿Cómo funciona por dentro?

| Paso | Qué hace | Tecnología |
|---|---|---|
| 1. Detección | Encuentra los rostros en la imagen y 5 puntos clave: ojos, nariz y comisuras de la boca | YuNet, red neuronal convolucional (Wu et al., 2023) |
| 2. Alineación | Con esos puntos endereza y recorta el rostro a 112 × 112 píxeles | OpenCV (`alignCrop`) |
| 3. Embedding | Convierte el rostro en un vector de 128 números; los rostros de la misma persona quedan cerca entre sí | SFace, red neuronal profunda (Zhong et al., 2021) |
| 4. Comparación | Mide la similitud coseno con los vectores guardados. Si supera el umbral (36,3 %), es esa persona; si no, es "Desconocido" | NumPy, vecino más cercano |

Para que un error de un solo cuadro no marque una asistencia falsa, la persona debe ser reconocida en **5 cuadros seguidos**. Además, solo se marca **una vez por día**.

### ¿Por qué esto es inteligencia artificial?

- **Aprendizaje profundo.** Las dos redes neuronales aprendieron a partir de millones de rostros a detectar caras y a describirlas con números. Nadie programó a mano reglas como "los ojos están encima de la nariz".
- **Aprendizaje de representaciones.** SFace no memoriza fotos: aprende un espacio matemático donde la distancia entre vectores significa "qué tan parecidas son dos caras".
- **Reconocimiento con pocos ejemplos.** Para reconocer a alguien nuevo bastan 10 muestras, sin volver a entrenar la red. Se clasifica por similitud con el vecino más cercano y un umbral de decisión.

## Ética y protección de datos

En Colombia, los datos biométricos (como el rostro) son **datos sensibles** según el artículo 5 de la Ley 1581 de 2012. Su tratamiento requiere **autorización explícita** del titular (art. 6). Por eso el software:

- **Exige consentimiento:** no deja registrar a nadie sin marcar la casilla de consentimiento informado.
- **No guarda fotos:** solo los vectores de 128 números, en `datos/personas.json`.
- **Funciona local:** nada sale del computador.
- **Permite borrar:** "Eliminar seleccionada y sus datos" borra los datos biométricos de la persona (derecho a la supresión).
- **No marca asistencia con fotos:** "Reconocer en una foto" sirve para probar, pero solo la cámara en vivo marca asistencia.
- **Evita duplicados:** avisa si alguien intenta registrarse dos veces.

### Limitaciones conocidas

- **Suplantación:** no tiene detección de "rostro vivo", así que una foto o un video mostrado en un celular podría engañarlo. Por eso está pensado para un salón donde el docente ve la cámara, no para control de acceso.
- **Sesgos:** los modelos se entrenaron con bases de datos públicas que no representan por igual a todas las poblaciones. La precisión puede variar según el tono de piel, la edad o la iluminación.
- **Condiciones:** el tapabocas, las gafas oscuras, las gorras, la poca luz y los gemelos reducen la precisión.
- **Uso indebido:** no debe usarse para vigilar a personas que no aceptaron participar.

## Instalación en Windows

1. Instala **Python 3.10 o superior** desde python.org y marca la casilla **"Add Python to PATH"**.
2. Haz doble clic en **`instalar.bat`**. Instala OpenCV, NumPy y Pillow.
3. Haz doble clic en **`ejecutar.bat`**.

Si prefieres la terminal, escribe cada comando en su propia línea:

```
python -m pip install -r requirements.txt
python app.py
```

Los modelos no vienen en el repositorio por su tamaño: el programa los descarga solo la primera vez que se abre (39 MB, se necesita internet) y los guarda en `modelos/`.

Otras opciones:

- `python app.py --camara 1` usa otra cámara.
- `python app.py --sin-camara` abre el programa solo para trabajar con fotos.
- `python app.py --video clase.mp4` hace la demostración con un video.

## Cómo se usa

La ventana tiene tres zonas: la **cámara** a la izquierda, **«La IA por dentro»** debajo de ella y un **panel con pestañas** a la derecha.

1. **Registrar** (pestaña *Registrar*). Escribe el nombre (y el código, si quieres), marca el consentimiento y elige:
    - **Capturar con cámara:** aparece un óvalo guía y se toman 10 muestras en unos 3 segundos. Mueve un poco la cabeza. `Esc` cancela.
    - **Desde fotos…:** elige una o varias fotos donde aparezca solo esa persona.
    - El enlace *Ver formato de consentimiento* muestra el texto para imprimir y permite copiarlo.
2. **Tomar asistencia** (pestaña *Asistencia*). Presiona **Iniciar asistencia** (o la barra espaciadora) y que cada estudiante mire la cámara un momento. Sobre el video:
    - recuadro **verde** con nombre y porcentaje = reconocido; **rojo** = desconocido;
    - la barrita bajo el rostro se llena en 5 cuadros seguidos y entonces aparece **«Asistencia registrada»** (con un sonido);
    - la *Lista de hoy* muestra quién llegó (✓ y hora) y quién falta.
3. **Revisar.** *Abrir lista en Excel* abre el archivo `asistencia_AAAA-MM-DD.csv` del día. Si Excel tiene el archivo abierto, las nuevas asistencias no se pierden: esperan y se guardan cuando se cierra.
4. **Personas.** Busca por nombre o código y elimina a alguien junto con sus datos biométricos (también con la tecla `Supr`).
5. **Cómo funciona.** Explica los 4 pasos y permite ajustar la **exigencia**: súbela si confunde personas, bájala si no reconoce a alguien registrado. *Probar con una foto…* reconoce rostros en una imagen sin marcar asistencia.

### La IA por dentro (modo didáctico)

Cuatro tarjetas muestran, en vivo, lo que hace la IA con la cara más cercana:

| Tarjeta | Qué se ve |
|---|---|
| 1. Detectar | Cuántos rostros encontró YuNet y qué tan segura está. Sobre el video aparecen los 5 puntos clave. |
| 2. Alinear | El rostro enderezado y recortado, tal como lo recibe la segunda red. |
| 3. Describir | Los 128 números del embedding como cuadrícula de colores (verde = positivo, naranja = negativo). |
| 4. Comparar | El parecido con la persona más cercana frente a la línea de exigencia. |

El panel se oculta con la casilla *Panel*; en pantallas bajas empieza oculto para que el video se vea grande. Los **5 puntos de la cara** que se dibujan sobre el rostro se ocultan o muestran con la casilla *Puntos de la cara* o la tecla `P`.

### Identidad visual

La interfaz usa la identidad de la **Universidad de Cundinamarca**: sus colores académicos (verde `#00482B`, amarillo `#FBE122` y naranja `#DAAA00`), con la cabecera en verde institucional, una línea amarilla y el nombre de la universidad y del programa. Los colores están en un solo lugar (`ui.py`, diccionario `C`). Si se guarda el logo oficial en `recursos/logo_udec.png` (versión para fondo oscuro), aparece en la cabecera.

### Atajos

`Espacio` iniciar/detener asistencia · `P` mostrar/ocultar los puntos de la cara · `Esc` cancelar captura · `Ctrl+1…4` cambiar de pestaña · `Enter` en el campo de código empieza la captura.

## Archivos

```
AsistIA/
├── app.py              qué hace cada botón y el ciclo de la cámara (Tkinter)
├── ui.py               cómo se ve: colores, botones, dibujos sobre el video
├── recursos/           opcional: logo_udec.png (logo oficial para la cabecera)
├── motor.py            la IA: detección, embeddings, comparación, base de datos y asistencia
├── requirements.txt    librerías necesarias
├── instalar.bat        instala las librerías (Windows)
├── ejecutar.bat        abre el programa (Windows)
├── modelos/            redes neuronales preentrenadas (.onnx, se descargan solas)
├── datos/              se crea solo: personas.json (nombres y vectores, sin fotos)
└── asistencia/         se crea solo: un CSV por día
```

## Formato de consentimiento (para imprimir)

> Yo, ______________________, identificado(a) con código ________, autorizo de manera libre, previa, expresa e informada que mi rostro sea procesado por el software AsistIA, con el único fin de registrar mi asistencia a la asignatura ______________________. Entiendo que: (1) los datos biométricos son datos sensibles (Ley 1581 de 2012) y no estoy obligado(a) a entregarlos; (2) no se guardan fotos, solo una representación numérica de mi rostro, almacenada en el equipo del docente; (3) puedo pedir en cualquier momento que se eliminen mis datos, y (4) si no acepto, mi asistencia se tomará por otro medio, sin ninguna consecuencia.
>
> Firma: ______________________  Fecha: ____________

## Referencias

- Ley 1581 de 2012, por la cual se dictan disposiciones generales para la protección de datos personales. Congreso de la República de Colombia.
- Wu, W., Peng, H. y Yu, S. (2023). YuNet: A tiny millisecond-level face detector. *Machine Intelligence Research, 20*(5), 656–665. https://doi.org/10.1007/s11633-023-1423-y. Modelo con licencia MIT.
- Zhong, Y., Deng, W., Hu, J., Zhao, D., Li, X. y Wen, D. (2021). SFace: Sigmoid-constrained hypersphere loss for robust face recognition. *IEEE Transactions on Image Processing, 30*, 2587–2598. https://doi.org/10.1109/TIP.2020.3048632. Modelo con licencia Apache 2.0.
- OpenCV. (s. f.). *DNN-based face detection and recognition*. https://docs.opencv.org/4.x/d0/dd4/tutorial_dnn_face.html
