# Codex Quota Guard 0.5.0: instalación y uso

Requisitos: Python 3.10 o posterior, un sistema POSIX y la CLI oficial de Codex autenticada con una cuenta apta para consultar la cuota. Usa el procedimiento habitual de autorización e inicio de sesión. No eludas permisos ni autenticación, no cambies `CODEX_HOME` para evitar restricciones y no leas directamente credenciales ni archivos de sesión.

## Instalación

Ejecuta:

```sh
codex plugin marketplace add knight-bo/codex-quota-guard
```

Reinicia la aplicación de escritorio, elige **Codex Quota Guard Local**, instala el complemento y actívalo. La publicación en GitHub no supone aprobación en el directorio público de complementos. La instalación no inicia la supervisión y no configura un inicio automático.

## Consultar, iniciar y detener

Puedes pedir:
- «Consulta la cuota restante de Codex».
- «Supervisa la cuota de esta tarea cada 30 segundos. Avísame al llegar al 82 % restante y, al llegar al 81 %, pregúntame si quiero pausarla cuando quede un 80 %».
- «Detén la supervisión de cuota».

Una consulta puntual no inicia comprobaciones periódicas. Antes de iniciar una supervisión continua, el asistente anfitrión debe identificar la tarea concreta, poder ejecutar la CLI en una sesión de segundo plano supervisada, procesar sus eventos y mantener la conversación disponible para que puedas responder. Si no puede cumplir estas condiciones, debe explicar la limitación y ofrecer únicamente una consulta puntual, sin afirmar que la supervisión continua está activa.

Desde la raíz del paquete:

```sh
# Consulta manual en español:
python3 scripts/quota_guard.py read --bucket codex --state-dir STATE --format text --locale es
python3 scripts/quota_guard.py read --bucket codex --target 80 --task-key TASK --warn-margin 2 --confirm-margin 1 --state-dir STATE --format text --locale es
# El anfitrión debe supervisar esta sesión en segundo plano y procesar el JSON predeterminado:
python3 scripts/quota_guard.py start --bucket codex --target 80 --task-key TASK --warn-margin 2 --confirm-margin 1 --interval 30 --state-dir STATE
# Desde otra sesión, usando el mismo directorio de estado:
python3 scripts/quota_guard.py stop --state-dir STATE --format text --locale es
```

Sustituye `TASK` por la identidad estable y verificada de la tarea concreta que se va a supervisar; no inventes una identidad ni incluyas secretos. La vinculación almacenada y emitida usa un hash, no el identificador original, y no otorga permiso para controlar la tarea. Sustituye `STATE` por la ruta absoluta de un directorio privado (0700), propiedad de tu usuario, fuera del repositorio y de la caché del complemento, bajo un directorio padre de confianza con permiso de escritura. No uses `chmod` para eludir restricciones de acceso. Usa exactamente el mismo directorio para detenerlo. `codex` es un ejemplo de grupo; selecciona explícitamente el que corresponda a tu trabajo y usa directorios de estado separados para grupos distintos.

`start` sigue siendo un proceso en primer plano, no un servicio independiente: el anfitrión debe conservar y supervisar su sesión en segundo plano. Tras solicitar la parada, verifica que el proceso haya terminado; la solicitud por sí sola no lo demuestra. Detener la supervisión no detiene la tarea observada.

## Objetivo de cuota restante y confirmación

`--target` acepta cualquier porcentaje finito de cuota **restante** entre 0 y 100, incluidos ambos extremos y decimales como `37.5`. No representa el porcentaje consumido. Los márgenes predeterminados son 2 puntos porcentuales para el aviso y 1 para la confirmación. Con un objetivo de 80:
- Al quedar un 82 % o menos, se emite `warning`.
- Al quedar un 81 % o menos, se emite `confirmation_required`; el anfitrión debe preguntar, identificando la tarea: «¿Quieres que pause esta tarea cuando quede un 80 %?».
- Al quedar un 80 % o menos, se emite `target_reached` y se deniega la admisión de trabajo nuevo (`allow_new_work=false`). Esta decisión cooperativa de admisión no pausa realmente la tarea.

Los márgenes se expresan en puntos porcentuales, admiten valores finitos de 0 a 100 y el margen de aviso debe ser mayor o igual que el de confirmación. Cada línea de activación se limita al 100 %. Los márgenes no desplazan el umbral de admisión: sigue siendo exactamente el objetivo, con un búfer efectivo de 0.

Si la primera lectura válida ya está en el objetivo o por debajo, se debe preguntar de inmediato: «Ya queda un 80 % o menos. ¿Quieres pausar esta tarea ahora?». Con un objetivo de 100, la pregunta es inmediata incluso si queda un 100 %. Un objetivo de 0 no garantiza evitar el agotamiento de la cuota. Si varias etapas coinciden en una lectura, se deben agrupar en un solo mensaje, sin preguntas duplicadas.

Un evento no demuestra que se haya notificado al usuario, que este haya autorizado una acción ni que la tarea esté pausada. El anfitrión debe formular la pregunta y comprobar la respuesta real. El silencio no es consentimiento. Para actuar hacen falta autorización explícita para la tarea concreta y una vía de control compatible y verificada; sin ella, se debe explicar el impedimento y pedir al usuario que actúe manualmente. No se pueden pausar ni terminar tareas arbitrarias. Antes de afirmar que una tarea se ha pausado o detenido, hay que verificar su estado real.

El bloqueo de admisión se mantiene tras alcanzar el objetivo, aunque aumente o se restablezca la cuota o se reinicie la supervisión de la misma tarea y objetivo. No se reanuda trabajo automáticamente. Para cambiar la configuración, acuerda los nuevos valores, detén la supervisión y verifica su salida antes de volver a iniciarla. Usa `--new-cycle` solo si el usuario solicita expresamente un ciclo nuevo, después de detener el anterior; no autoriza una pausa ni una reanudación. Los eventos se registran como máximo una vez: si se pierde uno, consulta el estado y el historial real de la conversación; la ausencia de otro evento no prueba que ya se haya pedido ni obtenido autorización.

## Compatibilidad con el modo de reserva

El modo antiguo `--reserve 10 --buffer 2` se conserva únicamente como opción de compatibilidad. En ese modo, la detección se activa al quedar un 12 % o menos y no garantiza conservar un 10 %. No combines `--target` con `--reserve`, `--threshold` ni `--buffer`; la CLI rechaza esas combinaciones. Una reserva antigua del 10 % nunca sustituye el objetivo elegido, aunque sea inferior al 10 %.

## Límites

El sondeo puede detectar el cruce tarde o saltarse el porcentaje exacto; el retraso de los datos y el consumo de otros clientes impiden garantizar una parada exacta en el objetivo. Los datos ausentes, vencidos, sintéticos o no válidos no son un saldo actual ni prueban que se haya alcanzado o superado un umbral. El complemento no controla tareas arbitrarias en la nube. Su campo `checkpoint_status` siempre permanece en `unconfirmed`; solo el orquestador responsable verifica de forma independiente el guardado y la finalización. Una interrupción gestionada requiere autorización explícita para el hilo y turno exactos y accesibles. Confirmar una interrupción no confirma la finalización de la tarea, el guardado de un punto de control ni la posibilidad de reanudarla. Este mecanismo antiguo no permite eludir la confirmación del modo objetivo; `--target` rechaza `--allow-interrupt`.

Más información: [Contrato de confirmación del anfitrión (inglés)](../CONFIRMATION-WORKFLOW.md) · [README](../../README.md) · [Idiomas](../LANGUAGES.md).


## Anuncios públicos opcionales de Tibo

Di «Vigila cada hora los anuncios públicos de restablecimiento de Tibo», «Avísame solo de completed y banked en Asia/Shanghai», «Consulta los anuncios una vez» o «Detén los avisos públicos». Se usa el comando independiente `resetwatch`. Una pregunta implica un solo `read`; iniciar requiere una petición explícita de supervisión. El anfitrión debe supervisar el proceso en primer plano, consumir JSON y usar su adaptador local de notificaciones existente. Sin ese canal, debe explicar que solo hay salida de texto/JSON. Instalar no inicia la supervisión.

`planned` es un plan, no una finalización; `completed` es un informe de terceros sobre un anuncio de finalización; `banked` es un restablecimiento guardado sin confirmar su recepción ni canje manual; `manual_credit` anuncia crédito manual y exige revisar las condiciones originales. Los anuncios no prueban la cuota personal, no canjean crédito ni reanudan/pausan investigaciones automáticamente. Incluso «verificado directamente» es una afirmación del proveedor, no confirmación independiente ni API oficial.

Sustituye PUBLIC_STATE por un directorio padre absoluto y privado fuera del repositorio/caché. Se usan `PUBLIC_STATE/public-reset-watch`, bloqueo y token de parada independientes, sin cambiar el estado de cuota. La primera obtención correcta guarda una base silenciosa. Publicaciones históricas, duplicados, reinicios y estados antiguos desordenados no repiten avisos. La actualización planned→completed solo puede emitir el nuevo estado. Cambiar filtros no reproduce el historial. Detén, verifica la salida y reinicia para cambiar ajustes; no se detienen investigaciones ni el monitor de cuota.

`--events` elige planned,completed,banked,manual_credit (todos por defecto). `--interval`: 3600..86400 segundos, 3600 por defecto. La espera sobrevive a reinicios; el retroceso tras errores se limita a 24 horas. `--max-age` limita la antigüedad de pruebas de obtención/comprobación en caché (172800 segundos, al menos el intervalo y como máximo 604800); `--event-age`, la de nuevas publicaciones (604800, rango 3600..2592000). `--timeout` global: 1..30 segundos (10), con como máximo un tiempo límite de socket adicional. `--timezone` usa una zona IANA instalada, UTC por defecto; las fechas máquina siguen en UTC. `--locale` conserva las reglas de idioma alternativo; campos y valores JSON no se traducen.

El predeterminado `--provider modelyard` solo lee el RSS público fijo `/feed.xml`. Se retiraron HTML y el `--provider-url` arbitrario; cambiar fuente requiere revisar código. Las categorías RSS son relatos de terceros, no verificación oficial. `fetched_at` es evidencia local de descarga; lastBuildDate/última publicación no indica sincronización. Un feed antiguo válido puede crear la base, con cobertura desconocida. El ámbito se deduce del texto original aportado o queda desconocido; título/contexto solo son afirmaciones del proveedor. Los registros solo de ChatGPT no se envían como Codex/Work. Un cambio de categoría del mismo post usa `first_observed_status_at` y un aviso de cambio local del agregador, sin inventar fecha de edición. El callback usa una ruta local existente del anfitrión; entrega real no verificada. La red/descarga de Library está bloqueada aquí; se prueba el primer elemento real recortado recibido directamente. Robots no autoriza redistribuir; consulta las fuentes.

Fallo de red/HTTP, comprobación caducada, formato/fechas inválidos y fuentes falsas significan desconocido, nunca «restablecido» o «no restablecido»; no generan eventos. Una consulta correcta sin eventos nuevos no demuestra ausencia de restablecimiento. `status` es caché, no consulta nueva ni prueba de ejecución. El registro se guarda antes de emitir: un fallo puede perder la entrega y un evento no prueba la notificación. Suspensión, salida y demoras de red/fuente interrumpen la cobertura. Sin garantía de tiempo real ni inicio automático; no requiere cuenta nueva, API de pago, subida de datos personales ni nuevos permisos de notificación del sistema.

```sh
python3 scripts/quota_guard.py resetwatch --help --locale es
python3 scripts/quota_guard.py resetwatch read --state-dir PUBLIC_STATE --format text --locale es
python3 scripts/quota_guard.py resetwatch start --state-dir PUBLIC_STATE --events completed,banked --interval 3600 --timezone Asia/Shanghai
python3 scripts/quota_guard.py resetwatch stop --state-dir PUBLIC_STATE --format text --locale es
python3 scripts/quota_guard.py resetwatch status --state-dir PUBLIC_STATE --format text --locale es
```

La supervisión pública solo requiere Python/POSIX/red y datos IANA instalados; no exige la CLI oficial Codex ni una cuenta.

`--fixture FILE` solo sirve para `read`, sin red/cuenta y con estado sintético aislado; su fecha antigua puede aparecer correctamente como caducada.

[Contrato / JSON](../RESET-WATCH.md) · [Revisión de fuentes](../RESET-SOURCES.md)
