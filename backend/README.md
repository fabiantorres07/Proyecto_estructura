# SismoLab AVL — Backend

Backend (sin base de datos) del proyecto SismoLab AVL: un observatorio sísmico simulado cuyo catálogo activo se organiza en un árbol AVL. Este README explica la estructura del proyecto, cómo configurar y correr el backend, y los conceptos de backend/Python/FastAPI que el equipo necesita para seguirle el hilo, ya que casi nadie tenía experiencia previa en backend.

**Este archivo se debe actualizar en cada sesión de trabajo**, agregando lo que se implementó y las decisiones de diseño nuevas.

## 1. Requisitos previos

- Python 3.11 o superior.
- Git (ya configurado si clonaste este repositorio).

## 2. Configuración inicial del entorno (solo la primera vez)

Ejecuta estos comandos parado dentro de la carpeta `backend/` en la consola (no en la raíz del repositorio).

```
cd backend (en caso de estar sobre el reposiotio en general y no en backend)
```

**Crear el entorno virtual** (una sola vez, la primera vez que configures el proyecto en tu computador):

```
python -m venv venv
```

Un entorno virtual (`venv`) es una copia aislada de Python solo para este proyecto, con sus propias librerías instaladas, sin mezclarse con lo que tengas instalado globalmente en tu computador. Cada persona del equipo debe crear el suyo — la carpeta `venv/` nunca se sube a Git (está excluida en `.gitignore`).

**Activarlo:**

- Windows (PowerShell):
  ```
  .\venv\Scripts\Activate.ps1
  ```
  Si PowerShell bloquea el script con un error de "execution policy", ejecuta esto una sola vez y vuelve a intentar:
  ```
  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
  ```
- macOS / Linux:
  ```
  source venv/bin/activate
  ```

Sabes que quedó activo cuando tu terminal empieza a mostrar `(venv)`.

**Instalar las dependencias:**

```
pip install -r requirements.txt
```

`requirements.txt` es la lista exacta de librerías (y sus versiones) que necesita el proyecto — principalmente FastAPI y Uvicorn. Este comando las instala todas de una vez dentro de tu entorno virtual.

## 3. Cómo correr el proyecto en cada sesión (rutina diaria)

Esto es lo único que necesitas repetir cada vez que vuelvas a trabajar (no hace falta crear el entorno virtual de nuevo, ni reinstalar las dependencias, salvo la excepción del final):

1. Abre una terminal en VS Code (`Ctrl + ñ` o desde el menú Terminal → New Terminal).
2. Si la terminal se abre en la raíz del repositorio y no dentro de `backend/`, muévete ahí:
   ```
   cd backend
   ```
3. Activa el entorno virtual:
   ```
   .\venv\Scripts\Activate.ps1
   ```
   (en macOS/Linux: `source venv/bin/activate`). Verifica que aparezca `(venv)` al inicio de la terminal.
4. Corre el servidor:
   ```
   uvicorn main:app --reload
   ```
5. Abre en el navegador:
   - `http://127.0.0.1:8000` — la API misma.
   - `http://127.0.0.1:8000/docs` — documentación interactiva (Swagger UI), donde puedes ver y probar cada endpoint sin necesitar el frontend.
6. Para detener el servidor, `Ctrl + C` en la terminal.

**Única excepción:** si en algún momento se agrega una librería nueva al proyecto (y por tanto cambia `requirements.txt`), después de activar el entorno virtual corre una vez más `pip install -r requirements.txt` para instalar lo nuevo. Para el día a día normal, solo necesitas los pasos 1 a 6.

## 4. Estructura del proyecto

```
backend/
├── venv/                    (no se sube a Git)
├── requirements.txt         (versiones exactas de las dependencias)
├── .gitignore
├── main.py                  (punto de entrada de FastAPI)
└── app/
    ├── domain/              (lógica de negocio, sin saber nada de HTTP/FastAPI)
    │   ├── event.py         (clase Event, enum AttentionStatus)
    │   ├── report.py        (clase Report)
    │   ├── station.py       (clase Station)
    │   ├── zone.py          (clase Zone)
    │   └── scenario.py      (clase Scenario, estado global — pendiente)
    ├── structures/          (estructuras de datos genéricas, reutilizables)
    │   ├── avl_node.py / avl_tree.py   (AVLNode, AVLTree — pendiente)
    │   ├── bst_node.py / bst_tree.py   (BSTNode, BSTTree — pendiente)
    │   ├── stack.py         (Stack — pendiente, usada para deshacer)
    │   └── queue.py         (Queue — pendiente, usada para reportes pendientes)
    ├── schemas/             (modelos pydantic: forma de entrada/salida de la API — pendiente)
    └── api/                 (endpoints/routers de FastAPI — pendiente)
```

Dividimos el backend en capas para separar responsabilidades: `domain/` tiene las reglas del problema sísmico en Python puro; `structures/` tiene las estructuras de datos genéricas (AVL, BST, pila, cola); `schemas/` y `api/` son la capa que habla HTTP con el frontend, y se llenan al final, una vez existan las clases de negocio. Nodo y Árbol están en archivos separados (en vez de compartir uno) para evitar que dos personas del equipo choquen editando el mismo archivo en Git.

Fuera de `backend/`, en la raíz del repositorio, hay también una carpeta `manual/` con documentos que **no se suben a Git** (excluida en el `.gitignore` de la raíz, distinto del de `backend/`).

## 5. Conceptos de backend usados en este proyecto (resumen rápido)

Para quienes del equipo son nuevos en backend/Python/FastAPI:

- **Backend vs frontend**: el frontend (GUI) es lo que el usuario ve y clickea; el backend es donde vive la lógica de negocio (el AVL, el BST, el cálculo de prioridad, deshacer, etc.) y donde se guardan los datos mientras el programa corre. El enunciado exige esta separación explícitamente.
- **Cliente-servidor / HTTP**: el frontend le manda peticiones al backend por HTTP. Los verbos comunes calzan con nuestras operaciones: `GET` (consultar un evento), `POST` (crear uno), `PUT`/`PATCH` (corregir uno / marcarlo revisado — `PUT` para un reemplazo completo, `PATCH` para un cambio parcial como solo el estado de atención), `DELETE` (eliminar uno).
- **FastAPI**: el framework de Python usado para construir la API. Escribes funciones normales de Python, las decoras para decir a qué URL/verbo responden, y FastAPI se encarga de la validación y genera automáticamente la página `/docs`.
- **Uvicorn**: el servidor que realmente ejecuta FastAPI y escucha las conexiones HTTP.
- **Sin base de datos**: todo el estado vive en memoria (en nuestras propias estructuras: el AVL, la cola, la pila, etc.) mientras el programa corre. La persistencia entre ejecuciones se hace exportando/importando archivos JSON, no una base de datos.
- **pydantic / schemas**: FastAPI usa pydantic para validar automáticamente los datos que llegan (por ejemplo, "la magnitud debe ser un número entre -2.0 y 10.0"), basándose en las anotaciones de tipo.
- **`@property` / `@x.setter`**: la forma en que Python expone valores calculados (como `Event.priority`, calculado a partir de otros campos) o asignación controlada de atributos, sin necesidad de métodos `getX()`/`setX()` como en Java — en Python se sigue escribiendo `evento.priority` o `evento.magnitude = valor` como si fueran atributos normales.
- **`set`, `__eq__` y `__hash__`**: un `set` es una colección sin duplicados que usa una tabla hash por dentro (por eso "¿está esto adentro?" es O(1) promedio, en vez de recorrer todo como en una lista). Para que un objeto propio (como `Station`) funcione bien en un `set`, hay que decirle a Python cómo compararlos (`__eq__`) y cómo calcular su "posición" en la tabla hash (`__hash__`) — si no se sobrescriben, Python usa identidad de memoria por defecto, y dos objetos que representan "lo mismo" en la vida real (mismo `station_id`, por ejemplo) no se reconocerían como duplicados.

 Si algo no se entiende, pregúntenle a quien haya llevado esa sesión, o repasen la conversación — la idea es que todo el equipo entienda el backend, no solo quien lo escribió.

## 6. Estado actual

**Hecho:**

- Separación backend/frontend en la raíz del repositorio (`backend/` y `front/`).
- Entorno virtual de Python, FastAPI + Uvicorn instalados, `requirements.txt` generado.
- Servidor mínimo de FastAPI (`main.py`) con un endpoint de prueba.
- Estructura de carpetas del proyecto bajo `app/` creada.
- Clase de dominio `Event` implementada por completo: atributos base (`event_id`, `magnitude`, `depth`, `x`, `y`, `occurred_at`, `revision`, `stations`, `is_in_populated_zone`, `attention_status`), el enum `AttentionStatus` (`PENDING`/`REVIEWED`), dos propiedades derivadas (`priority` y `key`, la clave de orden del AVL `K = (priority, magnitude, event_id)`), y los dos métodos de transición de estado:
  - `mark_as_reviewed()`: marca el evento como revisado; idempotente, no cambia la clave.
  - `apply_correction(magnitude=None, depth=None, x=None, y=None, is_in_populated_zone=None)`: aplica una corrección parcial o total. Valida coherencia interna antes de tocar nada (si cambia el epicentro, exige que también venga la zona recalculada), se ejecuta en dos fases (validar todo en variables locales, y solo después aplicar) para que una corrección inválida no deje el evento a medias, siempre incrementa `revision` y vuelve el evento a `PENDING`, y devuelve `(old_key, new_key)` para que quien la use decida si hay que reubicar el nodo en el AVL.
- Clase `Station` implementada: `station_id`, `x`, `y`, con `__eq__`/`__hash__` propios basados en `station_id` (para que el conjunto de estaciones de un evento no tenga duplicados aunque se reconstruyan instancias distintas desde JSON).
- Clase `Report` implementada: portador de datos puro (sin lógica de negocio) con `event_id`, `revision_num`, `station` (objeto `Station` ya resuelto, no un id crudo), y los datos del evento que trae el reporte (`magnitude`, `depth`, `x`, `y`, `occurred_at`).
- Clase `Zone` implementada: rectángulo alineado a los ejes, definido por `x_min`, `x_max`, `y_min`, `y_max` (no por 4 puntos/esquinas — ver decisiones abajo), más `is_populated`, y el método `contains(x, y)` que revisa si un punto cae dentro de la zona (incluyendo el borde).

**Pendiente / próximos pasos:**

- Clase `Scenario` — el orquestador central: procesa la cola de reportes (decide entre alta nueva / revisión mayor / confirmación / conflicto / reporte antiguo), calcula `is_in_populated_zone` recorriendo todas las zonas, y coordina con el AVL y el índice por id.
- `AVLNode`/`AVLTree`, `BSTNode`/`BSTTree`, `Stack`, `Queue`.
- Schemas y endpoints de la API.
- Estrategia de validación de rangos: **por ahora delegada solo a los schemas de pydantic** (no dentro de `Event`). Riesgo aceptado: la carga de escenario por topología (sección 12 del enunciado) reconstruye eventos sin pasar por la API/schemas, así que esto hay que revisarlo cuando se implemente esa carga.

## 7. Decisiones de diseño abiertas para confirmar con el equipo/profesor

- **No existe una clase `Usuario`**: el enunciado no exige login ni datos de múltiples usuarios, así que no se está modelando. Avisar si esta suposición resulta incorrecta.
- **Índice por id = diccionario, no lista ordenada**: se decidió indexar los eventos por id con un `dict` (hash map) en vez de una lista ordenada + búsqueda binaria, porque no hay ningún requisito de recorrer eventos ordenados por id — un diccionario da inserción/búsqueda/eliminación O(1) promedio sin pagar el costo de mantener el orden bajo cambios.
- **No hay una pila/historial de revisiones dentro de `Event`**: se consideró agregar una (una especie de bitácora de correcciones aceptadas por evento) y se descartó — lo que aportaría ya está cubierto por el contador `revision` de `Event` más la pila de deshacer global de `Scenario` (la única pila que exige el enunciado).
- **`Station` no guarda qué eventos ha reportado**: se descartó ese atributo porque el enunciado dice explícitamente que las estaciones son inmutables durante la ejecución, y un atributo así se iría modificando con cada reporte aceptado. Tampoco hay ninguna consulta obligatoria que lo necesite.
- **`Station.x`/`Station.y`** (ubicación de la estación): no está siendo usada todavía por ninguna regla obligatoria del enunciado (no confundir con el epicentro del evento, que es lo que sí determina la zona poblada). Queda como decisión abierta a justificar o retirar más adelante.
- **La comparación de "igualdad de datos" entre un reporte entrante y el evento vigente** (necesaria para distinguir una confirmación de un conflicto, sección "Procesamiento de reportes recibidos" del enunciado) va a vivir en `Scenario`, no como método de `Report` ni de `Event` — evita que esas dos clases tengan que conocerse mutuamente. Al implementarla, ojo con comparar decimales usando `==` directo: puede fallar por precisión de punto flotante, así que probablemente haga falta redondear antes de comparar.
- **`Zone` se representa con los 4 límites del rectángulo (`x_min`/`x_max`/`y_min`/`y_max`)**, no con 4 puntos/esquinas — al ser un rectángulo alineado a los ejes, las esquinas se derivan matemáticamente de esos 4 números; guardarlas por separado sería redundante y permitiría representar un rectángulo inconsistente.
- **La regla de "borde compartido entre dos zonas"** (un epicentro en el borde de dos zonas se clasifica como poblado si alguna de las dos lo es) va a vivir en `Scenario`, que es quien tiene la lista completa de zonas — una `Zone` individual solo puede responder si el punto está dentro de sí misma.

---

*Mantén este archivo actualizado: después de cada sesión de trabajo, agrega lo que se implementó y cualquier decisión de diseño nueva en la sección correspondiente.*
