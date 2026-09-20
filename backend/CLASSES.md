CLASES:
1.	DOMAIN

- User
Representa al operador que interactúa con el sistema desde una consola o estación sismológica.
•	Atributos: 
    o	user_id: Identificador único del usuario.
    o	estacion: Referencia o ID de la estación sismológica en la que opera el usuario.
    o	reportList: Historial de reportes creados y enviados por dicho usuario desde su estación.

- Event / AVL node
Entidad principal que representa un terremoto activo y funciona directamente como nodo en el árbol AVL y BST.
•	Atributos 
    o	event_id: Entero único (1 a 999999), inmutable y no reutilizable. Se compara numéricamente. Se conserva a lo largo de las correcciones de magnitud M o prioridad P.
    o	magnitude: Número decimal finito entre -2,0 y 10,0 (máximo 1 decimal).
    o	depth : Profundidad del hipocentro en km (0,0 a 700,0 km).
    o	Epicentro:
    o	x, y: Coordenadas cartesianas en km (0,0 a 1000,0 km) que determinan ubicación y pertenencia a zonas.
    o	occurred_at: Fecha y hora exacta de ocurrencia en UTC. 

NOtA:	Al reportar un evento, el usuario no ingresa la hora manualmente; el sistema asigna automáticamente la fecha/hora vigente del Reloj de Simulación Global.
    o	revision: Número entero positivo de revisión vigente (inicia en 1 y se incrementa en +1 por corrección).
    o	stations_list (Lista de estaciones): Conjunto de estaciones sismológicas que han emitido reportes aceptados para este evento.
    o	is_in_populated_zone: Booleano que registra si el epicentro está dentro o sobre el borde de una zona poblada. (True: poblado)
    o	priority : Calculada automáticamente (3=Alta, 2=Media, 1=Baja) según las reglas de M, H y zona poblada.
    o	key (K= P,M,I): Tupla obligatoria de ordenamiento lexicográfico. El recorrido inorden  produce claves ascendentes y el inverso descendentes. H y la ubicación solo influyen en K mediante el cálculo de P.
    o	AttentionStatus: Pendiente (PENDING) o Revisado (REVIEWED). Las altas o correcciones aceptadas lo devuelven a Pendiente. Cambiar a Revisado no modifica K ni reordena el árbol.
    o	Checklist: Pila interna que guarda el historial de revisiones del evento.
    o	Metadatos de Árbol: altura, factorDeBalance, hijoIzquierdo (left), hijoDerecho (right) y marcaAccesoCostoso.

- Station
Fuente emisora física e inmutable encargada de capturar y enviar reportes sísmicos.
    •	Atributos: 
    o	station_id: Identificador único de la estación.
    o	zonaCoordenadas: Coordenadas cartesianas (X, Y) de su ubicación en el plano geográfico.
    o	Reported_events: Historial de identificadores de eventos reportados por la estación.

- Report
Paquete de datos inmutable que ingresa a la Cola FIFO para ser procesado.
•	Atributos: 
    o	station: Estación emisora que genera el reporte.
    o	numRevision: Identificador/número de revisión del evento reportado. Reportes con IDs distintos representan terremotos distintos.
    o	Datos del objeto evento: Magnitud, profundidad, epicentro \((X, Y)\) y tiempo de ocurrencia.
    o	time_stamp: Representa la fecha y hora exacta del Reloj de Simulación Global en el instante preciso en que una estación sismológica genera el reporte y este ingresa a la Cola
    o	Corrección: El estado de atención (Pendiente/Revisado) NO pertenece al Reporte, es un atributo exclusivo de la entidad Evento.
    o	occurred_at (Fecha y Hora de Ocurrencia): Es el momento en que sucedió físicamente el terremoto en el territorio ficticio (por ejemplo: 10:00:00 UTC).
    o	time_stamp (Fecha y Hora de Recepción en Cola): Es el momento del reloj de simulación en que la estación emitió el paquete y la cola del sistema lo recibió (por ejemplo: 10:20:00 UTC)
- Scenario 
Modela el estado global del observatorio y coordina estructuras, reloj y modos de ejecución.
•	Atributos: 
    o	simulationClock: Reloj explícito en UTC con precisión de segundos. 
        1.	Corre y se asigna automáticamente al generar reportes.
        2.	El usuario puede detenerlo o moverlo hacia el futuro (por ejemplo, adelantar 3 días) para probar reglas dependientes de la antigüedad (como el archivo masivo tras T=72 horas) sin esperar tiempo real.
    o	L: Límite entero (inicialmente 3) para evaluar accesos costosos en nodos de alta prioridad.
    o	mode(enum): 
        -Modo Normal (mantiene el balance AVL en cada operación)
        -Modo Estrés (recibe ráfagas en la cola e inserta como BST sin balancear, postergando las rotaciones para la recuperación global).
    o	W (float = 48.0): Diferencia temporal máxima en horas para clasificar un evento como réplica.
    o	R (float = 40.0): Distancia geográfica máxima en km para clasificar réplicas.
    o	T (float = 72.0): Antigüedad mínima en horas respecto al reloj global para evaluar el archivo masivo de subárboles
    o	eliminated_IDs: Es un conjunto fuera del árbol AVL que registra únicamente los identificadores numéricos de los eventos eliminados individualmente para comprobar cada reporte entrante, rechazarlo al instante y bloquear permanentemente la reactivación de ese ID e impedir su reactivación por reportes futuros.
    o	archived_history: (Archivo masivo, diferente de ráfaga) Colección que almacena la información e identidad de los eventos cuyos subárboles fueron trasladados al histórico.  es una colección que almacena la información e identidad completa de los objetos  “Event”  cuyos subárboles fueron trasladados al histórico tras un archivo masivo, permitiendo que si ingresa un reporte posterior con una revisión mayor válida, el sistema localice el sismo de inmediato para reactivarlo reinsertándolo en el catálogo activo, además de incluir estos eventos como candidatos en las consultas de réplicas
            Aclaración sobre el archivo masivo: Para archivar una rama, TODOS los nodos de ese subárbol deben cumplir la condición de ser antiguos (antigüedad > T horas y prioridad baja); si un solo nodo hijo es reciente, ningún elemento de esa rama se puede archivar.
    o	queue: Cola FIFO que mantiene la secuencia de recepción de los reportes pendientes.
    o	Stack / Undo: Pila LIFO para el registro y reversión de acciones. 
            Restauración en la cola: Si la acción deshecha fue el procesamiento de un reporte, la operación devuelve el reporte al frente de la cola FIFO en su posición original, aun si había sido descartado o generado conflicto.
    o	zones: list[Zone]: Zonas pobladas y no pobladas del mapa (Colección de rectángulos geográficos fijos en el plano)
    o	stations: list[Station]: Estaciones sismológicas del escenario. Representa las fuentes físicamente instaladas que emiten los reportes hacia la cola del observatorio

- Zone (Geometría)
Modela las regiones geográficas fijas del mapa (0 a 1000 km).
•	Atributos:
    o	 Base: Base
    o	Height: Altura
    o	Coordinates: X, Y
    o	Is_Poblated: (booleano fijo por zona) 
    o	Stations_zone: lista Estaciones contenidas.

2. STRUCTURES

- avl_Node
•	Clase dummie encargada únicamente de envolver el evento y manejar la topología del árbol AVL.
•	Atributos:
    o	event: Instancia limpia de la entidad de dominio.
    o	Left: referencia al nodo hijo izquierdo.
    o	right: referencia al nodo hijo derecho.
    o	height: Altura entera del nodo dentro del árbol AVL.
    o	balance_factor: Factor de balance calculado.
        •	Justificación técnica: Mantiene la entidad Event desvinculada de los punteros del árbol. De este modo, pasar un evento entre el árbol AVL, el árbol BST, la cola, la pila o el histórico no requiere reescritura de referencias ni verificaciones individuales en el evento.
- avl_Tree 
Implementación propia del árbol binario auto-balanceado AVL que gestiona el catálogo activo ordenado por la clave K = (P, M, I).
•	Atributos:
    o	root: Referencia al nodo raíz del árbol (AvlNode).
    o	rotation_counter: Registro restorable de casos de desbalanceo atendidos (LL, RR, LR, RL) y giros simples/dobles ejecutados.
        •	Costo Operativo: Medido estrictamente por la cantidad de giros/rotaciones necesarias para rebalancear la estructura tras inserciones, correcciones o eliminaciones.
- bst_Node
Clase dummie para el árbol de búsqueda binaria no balanceado.
•	Atributos:
    o	event: Instancia de la misma entidad Event compartida con el sistema6.
    o	Left: Punteros a los nodos hijos.
    o	right: Punteros a los nodos hijos.
    •	Justificación técnica del audio: Permite insertar el mismo evento en el árbol BST sin alterar las referencias que ya posee en el árbol AVL.
- BstTree 
Implementación propia del árbol binario de búsqueda (BST) sin balanceo, utilizado para pruebas de desempeño y comparación estructural frente al AVL.
•	Atributos:
    o	root: Referencia al nodo raíz del árbol BST.
    o	comparacionesAcumuladas: Contador de nodos examinados en las búsquedas para evaluar el costo.
    •	Costo y Comparación: Compara contra el AVL mediante tres métricas estructurales: altura total, cantidad de hojas y cantidad de nodos visitados / comparaciones.
- Queue
Estructura lineal que almacena ráfagas de reportes emitidos por las estaciones sismológicas en estricto orden de llegada.
•	Atributos:
    o	reports: Colección lineal interna de objetos Report pendientes por procesar.
        •	Comportamiento en Modo Estrés: Durante ráfagas masivas, los reportes ingresan y se procesan en la cola insertándose directamente en el árbol como un BST sin balancear, postergando la recuperación del equilibrio AVL.
- Stack 
Estructura lineal utilizada exclusivamente para la pila de retroceso (Undo).
•	Atributos:
    o	actions: Historial de objetos de acción ejecutados en el sistema.
        •	Restauración de Cola y Métricas: Cada paso de procesamiento en la cola constituye una acción apilada. Al hacer Undo, devuelve el reporte a la parte frontal de la cola FIFO en su posición original y restaura los contadores de giros a sus valores previos.


2. Claridades sobre JSON y Métricas
•	JSON (Estructura de Persistencia): 
o	Historial: Estado de la pila de deshacer (Undo) y registro de operaciones.
o	Reportes en Cola: Mantiene el orden FIFO de recepción de los reportes aún no procesados.
o	Versiones Persistentes: Guardado estructurado con nombre del estado completo (árbol activo, histórico, retirados, reloj, parámetros (W, R, L, T), modo de ejecución y métricas acumuladas).
•	Métricas y Costos (Aclaraciones del Profesor): 
o	Concepto de Métricas: Corresponde al conteo explícito de eventos desencadenados (rotaciones LL, RR, LR, RL, giros simples y dobles).
o	Costo Operativo: "Costo" NO se refiere a tiempo de ejecución computacional (milisegundos de CPU), sino a la cantidad de giros/rotaciones realizadas (un desbalanceo doble RL/LR cuesta el doble que uno simple LL/RR).
o	Contadores Restaurables: Todos los contadores de giros se restauran a sus valores anteriores al desaplicar una acción con Undo o cargar una versión.

3. Requerimientos de Visualización
•	Vista Geográfica del Plano: Mapa cartesiano de 0 a 1000 km con delimitación de estaciones, zonas pobladas, zonas no pobladas y la ubicación de los epicentros sísmicos.
•	Vista Estructural de Árboles: Visualización interactiva del árbol AVL activo y comparación directa con la topología del árbol BST.
•	Vista de Cola y Métricas: Monitoreo en tiempo real del ingreso y procesamiento paso a paso de la cola FIFO y de los contadores de rotaciones del árbol.

Costo
•	Costo Operativo en el Árbol: Representa la cantidad de giros/rotaciones realizadas. Un desbalanceo doble (LR / RL) requiere dos giros elementales, por lo que tiene el doble de costo que un giro simple (LL / RR)
•	Costo en Consultas y Búsquedas: Equivale a la cantidad de nodos visitados / comparaciones de claves para localizar un elemento. El árbol que requiera visitar más nodos es el más costoso estructuralmente
def __init__(self, simulation_clock: Optional[datetime] = None): 
self.simulation_clock: datetime = ( simulation_clock or datetime.now(timezone.utc).replace(microsecond=0) )
