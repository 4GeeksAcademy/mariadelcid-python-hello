vale,# Python Hello

El boilerplate más básico para comenzar un proyecto en Python en 4Geeks. Inicia tu primer proyecto en Python desde cero.

## ¿Qué hacer a continuación?

Abre el archivo `main.py` y comienza a escribir tu código.

Ejecuta tu código escribiendo el siguiente comando en tu terminal:

```bash
$ python main.py
```

Puedes crear e incluir tantos archivos de Python (también conocidos como módulos) como desees utilizando las declaraciones de importación.

## Requisitos

Asegúrate de tener Python instalado en tu computadora. Te recomendamos encarecidamente [instalar Python a través de Pyenv](https://4geeks.com/es/how-to/que-es-pyenv-y-como-instalar-pyenv) para evitar conflictos de versiones en el futuro.

### Contribuidores

Esta plantilla fue creada como parte de los [Recursos de Python de 4Geeks](https://4geeks.com/es/technology/python) para el aprendizaje en [4Geeks.com](https://4geeks.com) por [Alejandro Sanchez](https://twitter.com/alesanchezr) y [muchos otros contribuyentes](https://github.com/4GeeksAcademy/python-hello/graphs/contributors).

## Sistema de inventario con agente

### Instalación

Instala las dependencias del proyecto:

```bash
python -m pip install -e .
```

Crea un archivo `.env` en la raíz (no se sube al repositorio) y configura tu clave de Groq:

```env
GROQ_API_KEY=tu_clave
GROQ_MODEL=llama-3.3-70b-versatile
```

### Ejecución

En una terminal inicia la API:

```bash
uvicorn api.app:app --reload
```

En otra terminal inicia el agente:

```bash
python agent.py
```

La API debe iniciarse antes que el agente. Escribe preguntas como `¿Cómo está el stock?`, `Añade 5 cajas de leche` o `Acabamos de vender 2 unidades de arroz`. Escribe `salir` para terminar.

La API guarda el inventario en `products.csv`. Las alertas usan un umbral predeterminado de 5 unidades y distinguen entre `low_stock` (cantidad positiva menor o igual que el umbral) y `out_of_stock` (cantidad cero). La conversación se añade a `conversation_log.csv` sin sobrescribir sesiones anteriores.
