# Codex Quota Guard: instalación y uso

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
- «Inicia la supervisión con una reserva del 10 %, un margen de 2 puntos porcentuales y comprobaciones cada 30 segundos».
- «Detén la supervisión de cuota».

Una consulta puntual no inicia comprobaciones periódicas. Desde la raíz del paquete:

```sh
python3 scripts/quota_guard.py read --bucket codex --state-dir STATE --format text --locale es
python3 scripts/quota_guard.py start --bucket codex --reserve 10 --buffer 2 --interval 30 --state-dir STATE --format text --locale es
# En otra terminal, mientras start sigue en primer plano:
python3 scripts/quota_guard.py stop --state-dir STATE --format text --locale es
```

Sustituye `STATE` por la ruta absoluta de un directorio privado (0700), propiedad de tu usuario, fuera del repositorio y de la caché del complemento, bajo un directorio padre de confianza con permiso de escritura. No uses `chmod` para eludir restricciones de acceso. Usa exactamente el mismo directorio para detenerlo. `codex` es un ejemplo de grupo; selecciona explícitamente el que corresponda a tu trabajo.

`start` se ejecuta en primer plano: mantén su sesión supervisada. Tras solicitar la parada, verifica que el proceso haya terminado; la solicitud por sí sola no lo demuestra.

## Límites

La detección se activa al quedar un 12 % o menos: reserva del 10 % más 2 puntos de margen. No garantiza conservar un 10 %. Otros clientes pueden consumir cuota. Los datos vencidos o no válidos no son un saldo actual. No controla tareas arbitrarias en la nube. El campo `checkpoint_status` del complemento siempre permanece en `unconfirmed`; solo el orquestador responsable verifica de forma independiente el guardado y la finalización. Una interrupción gestionada requiere autorización explícita para el hilo y turno exactos y accesibles. Confirmar una interrupción no confirma la finalización de la tarea.

Más información: [README](../../README.md) · [Idiomas](../LANGUAGES.md).
