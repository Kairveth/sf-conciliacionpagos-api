# 02. Requisitos: épicas, historias y criterios de aceptación

Versión 0.2 · 2 de noviembre de 2026 · Parte de: `01-as-is-to-be.md`

Etiquetas:

- **[C]** Confirmado: dato medido en la org o dado por el caso.
- **[D]** Decisión de diseño propuesta en este documento, pendiente de revisión. Las de la sección 9 del documento 01 ya están validadas y van como [C].
- **[S]** Supuesto: valor numérico razonable. Se ajusta con datos reales.
- **[F]** Falta: dato sin respuesta. Indica qué historia depende de él.

Prioridad: **MVP** (entra en la demo) o **F2** (fase 2, fuera de esta entrega).

---

## Resumen de épicas

| Épica | Qué resuelve | Historias | Prioridad |
|---|---|---|---|
| E1 | Entrada de cobros de la pasarela | 5 | MVP |
| E2 | Entrada del extracto bancario | 3 | MVP |
| E3 | Entrada de facturas del ERP | 2 | MVP |
| E4 | Motor de conciliación y cuadre | 9 | MVP |
| E5 | Incidencias y panel del analista | 4 | MVP |
| E6 | Permisos, RGPD y auditoría | 5 | MVP (H6.4 ejecución en F2) |
| E7 | Integración de vuelta con el ERP | 2 | F2 |

Total: 30 historias. 27 MVP completas, 1 con parte en F2 (H6.4), 2 F2 (E7).


---

## E1. Entrada de cobros de la pasarela

**Objetivo:** cada cobro de la pasarela llega una vez a Salesforce, con firma verificada y sin datos de tarjeta.
**Trazabilidad:** RF-01, RF-02, CA-5.

### H1.1 Recibir aviso de cobro desde el relé · MVP

Como relé de webhooks (H1.5), quiero enviar cada aviso ya verificado a un endpoint REST de Salesforce, para que se registre en tiempo real.

Criterios de aceptación:

- Llamada con token OAuth (client credentials) del usuario de integración del proyecto: responde 200 y crea un registro en staging con estado `Recibido`.
- Llamada sin token válido: 401 y no crea nada.
- Usuario sin permiso de creación en staging: 403 y no crea nada.
- Payload mal formado: 400 y registra el error sin datos personales.
- Entrada en staging con el id de la pasarela como clave externa.

Escalabilidad: el webhook solo escribe en staging, sin lógica de negocio. Volumen: 20.000 al día son unos 0,23 por segundo de media. Pico de fin de mes: unas 3 veces la media [S]. Si el pico supera el límite de llamadas REST de la org, pasar a cola de staging con Platform Event (F2).

### H1.2 Deduplicar avisos repetidos · MVP

Como analista, quiero que un mismo aviso recibido dos veces no cree dos cobros, para no contar dinero dos veces.

Criterios de aceptación:

- Mismo id de pasarela: no se crea un segundo Cobro. El segundo aviso queda con estado `Duplicado`.
- La respuesta HTTP al duplicado es 200, no 409, para que la pasarela deje de reintentar.
- Prueba: enviar el mismo payload dos veces y comprobar un único Cobro (CA-5).

### H1.3 Recibir liquidación diaria con comisiones · MVP

Como analista, quiero recibir la liquidación de la pasarela, para conciliar el único abono que llega al banco por todos los cobros del día.

Criterios de aceptación:

- Cada fichero de liquidación crea un registro Liquidación con referencia, fecha y neto total.
- Cada línea enlaza su Cobro con la Liquidación por id de pasarela.
- La comisión queda en un campo propio del Cobro. Suma de (bruto − comisión) de sus cobros = neto de la Liquidación. Si no cuadra, incidencia `Liquidación descuadrada`.
- Si una línea no tiene Cobro previo, se crea en estado `Pendiente de cobro` y se espera al aviso.

### H1.4 Registrar devoluciones y contracargos · MVP

Como analista, quiero que una devolución reabra la factura, para que la deuda vuelva a estar visible.

Criterios de aceptación:

- Un evento de devolución crea un Cobro con importe negativo y tipo `Devolución`, vinculado al Cobro original.
- La factura afectada pasa de conciliada a `Abierta` si su saldo vuelve a ser positivo.
- Un contracargo se trata igual, con tipo `Contracargo`.

### H1.5 Relé de webhooks en Cloudflare Worker · MVP

Como responsable de seguridad, quiero que ningún endpoint de Salesforce quede abierto a internet sin autenticar.

Criterios de aceptación:

- El Worker verifica la firma HMAC del aviso con el secreto de la pasarela. Firma inválida: 401 a la pasarela y no llama a Salesforce.
- Firma válida: obtiene token OAuth (client credentials) y reenvía el aviso a H1.1.
- Salesforce no responde o devuelve 5xx: el relé devuelve 5xx a la pasarela para que reintente. El relé no guarda avisos.
- Secretos (firma de la pasarela y credenciales OAuth) en variables secretas del Worker, nunca en el repositorio.
- Logs del Worker sin payload ni datos personales: solo id de aviso y resultado.

Alternativa descartada: endpoint público en un Site de Salesforce con usuario invitado. Expone la org y obliga a dar permisos al invitado.

---

## E2. Entrada del extracto bancario

**Objetivo:** cada movimiento del banco queda registrado una vez, y el fichero se valida antes de procesarse.
**Trazabilidad:** RF-03, CA-4.

### H2.1 Cargar extracto y registrar abonos · MVP

Como sistema, quiero leer el extracto diario convertido a CSV y crear un MovimientoBanco por cada abono.

Criterios de aceptación:

- Solo se registran abonos (importe positivo). Los cargos se ignoran y se cuentan aparte.
- Cada movimiento lleva fecha valor, importe, concepto y referencia del ordenante.
- Abono de la pasarela: se casa con su Liquidación por referencia e importe neto. Transferencia B2B: genera un Cobro de tipo `Transferencia` (1:1).
- Conversión camt.053 → CSV fuera de Salesforce, por script documentado [D]. Formato de origen pendiente [F-4].

### H2.2 Validar control del fichero antes de procesar · MVP

Como sistema, quiero comprobar que el fichero cuadra con su control antes de crear nada, para no procesar un extracto cortado.

Criterios de aceptación:

- El fichero incluye total de líneas y suma de importes. Si no cuadra, el fichero se rechaza entero y no se crea ningún movimiento.
- Rechazo registrado como error de ejecución con motivo, sin datos personales.

### H2.3 Idempotencia de carga · MVP

Como sistema, quiero que cargar dos veces el mismo extracto no duplique movimientos.

Criterios de aceptación:

- Clave externa del movimiento = hash de fecha valor + importe + referencia bancaria.
- Segunda carga del mismo fichero: 0 movimientos nuevos, resumen con `N omitidos por duplicado`.

---

## E3. Entrada de facturas del ERP

**Objetivo:** las facturas llegan cada noche, con clave externa, y una recarga no duplica nada.
**Trazabilidad:** RF-04, CA-4.

### H3.1 Carga nocturna de facturas con clave externa · MVP

Como sistema, quiero hacer upsert de las facturas del ERP por número de factura, para que cada factura exista una sola vez.

Criterios de aceptación:

- Clave externa: número de factura del ERP.
- Upsert por lote con `sf data upsert bulk` en la demo. En producción, Bulk API 2.0 desde el ERP [D].
- Fila con importe no numérico o cliente vacío: se rechaza esa fila, las demás se cargan, y el error queda registrado por fila.
- Recarga del mismo fichero: 0 facturas nuevas, sin cambios de importe.

### H3.2 Cambio de importe en factura ya conciliada · MVP

Como responsable, quiero que un cambio de importe en el ERP no altere silenciosamente una factura ya conciliada.

Criterios de aceptación:

- Si la factura no tiene aplicaciones de cobro: se actualiza el importe.
- Si tiene aplicaciones: no se actualiza, se abre una incidencia de tipo `Importe cambiado` con ambos valores.

---

## E4. Motor de conciliación y cuadre

**Objetivo:** three-way match entre factura, cobro y abono, con reglas en orden, y cada ejecución cerrada con un cuadre exacto.
**Trazabilidad:** RF-05, RF-06, RF-10, RF-11, CA-1, CA-2, CA-4.

Orden de reglas [D]:

1. Referencia exacta de factura en el concepto del pago.
2. Importe y cliente dentro de la ventana de fechas.
3. Tolerancia: diferencia máxima aceptada, 0,05 € [S, en Custom Metadata].

### H4.1 Lanzar conciliación programada y manual · MVP

Como analista, quiero que la conciliación corra cada día y poder lanzarla a mano, para no depender de un horario.

Criterios de aceptación:

- Programación diaria tras la carga del extracto (hora propuesta: 07:00 [S]).
- Botón o acción manual en el panel, con el mismo proceso.
- Dos ejecuciones simultáneas: la segunda no arranca y deja aviso.

### H4.2 Regla 1: referencia exacta · MVP

Como sistema, quiero casar un pago con su factura cuando el concepto trae el número de factura.

Criterios de aceptación:

- Importe del pago = importe pendiente de la factura, dentro de tolerancia → se crea AplicacionCobro y la factura pasa a conciliada si también está abonada.
- Importe distinto fuera de tolerancia → incidencia `Importe distinto`, sin aplicar.

### H4.3 Regla 2: importe y cliente en ventana de fechas · MVP

Como sistema, quiero casar por importe y cliente cuando no hay referencia.

Criterios de aceptación:

- Coincidencia única de factura pendiente, mismo cliente, importe dentro de tolerancia, fecha dentro de la ventana → se aplica.
- Dos o más candidatas: no se aplica, se abre incidencia `Ambigüedad` con las candidatas.
- Ventana de fechas en Custom Metadata, 5 días por defecto [S].

### H4.4 Tolerancia configurable · MVP

Como responsable financiero, quiero cambiar la tolerancia sin desplegar código.

Criterios de aceptación:

- Tolerancia y ventana leídas de Custom Metadata en cada ejecución.
- Cambio de valor: aplica en la siguiente ejecución, sin deploy.

### H4.5 Transferencia que cubre varias facturas · MVP

Como sistema, quiero repartir un pago entre las facturas que nombra su concepto.

Criterios de aceptación:

- Concepto con varios números de factura y suma igual al pago (dentro de tolerancia) → una AplicacionCobro por factura.
- Suma distinta al pago → incidencia `Reparto incompleto`, con el resto sin asignar.
- Concepto sin números de factura → no se reparte, se abre incidencia `Sin referencia`.

### H4.6 Factura pagada en varios cobros · MVP

Como sistema, quiero que una factura se marque conciliada solo cuando la suma de sus cobros la cubre.

Criterios de aceptación:

- Dos pagos parciales que suman el importe, ambos abonados → factura conciliada.
- Suma insuficiente → factura en `Parcialmente conciliada`, sin incidencia, hasta el siguiente pago.
- Suma superior al importe → incidencia `Sobrepago`.

### H4.7 Estado pendiente de abono · MVP

Como analista, quiero distinguir un pago cobrado de un pago abonado en el banco.

Criterios de aceptación:

- Cobro con tarjeta: pasa a `Abonado` cuando su Liquidación tiene un MovimientoBanco casado. Hasta entonces, `Pendiente de abono`.
- Cobro por transferencia: nace `Abonado`, porque sale del propio movimiento.
- Al abonarse un cobro, se reevalúa su factura.
- Pendiente de abono más de 3 días hábiles → incidencia `Abono no recibido` [S].

### H4.8 Resumen de ejecución con cuadre · MVP

Como responsable, quiero ver si cada ejecución cuadra al céntimo.

Criterios de aceptación:

- Registro de ejecución con: leídos, conciliados, incidencias, duplicados, importes totales de cada grupo.
- Cuadre: leídos = conciliados + incidencias + duplicados. Si no cuadra, la ejecución queda en estado `Error de cuadre`.
- Prueba en bulk con 200 registros (CA-4).

### H4.9 Histórico de ejecuciones · MVP

Como responsable, quiero conservar el resumen de cada ejecución sin agotar el almacenamiento.

Criterios de aceptación:

- Un registro de ejecución por día en objeto estándar: unos 365 al año, 0,7 MB.
- Batch de purga: borra el staging procesado y el detalle de ejecuciones con más de 30 días [S]. El resumen se conserva.
- Big Object descartado en el MVP (ADR en documento 05).

---

## E5. Incidencias y panel del analista

**Objetivo:** cada diferencia tiene un motivo, un dueño y una acción registrada.
**Trazabilidad:** RF-07, RF-08, RF-09, CA-3.

### H5.1 Abrir incidencia con tipo y motivo · MVP

Como sistema, quiero abrir una incidencia por cada diferencia con un tipo cerrado.

Criterios de aceptación:

- Tipos: `Sin referencia`, `Importe distinto`, `Ambigüedad`, `Reparto incompleto`, `Sobrepago`, `Abono no recibido`, `Importe cambiado`, `Movimiento sin factura`, `Liquidación descuadrada`, `Divisa no soportada`, `Otro`.
- Cada incidencia enlaza con el cobro o movimiento de origen.
- No se crea incidencia duplicada para el mismo origen en la siguiente ejecución.

### H5.2 Panel de resumen y lista · MVP

Como analista, quiero ver de un vistazo qué queda por resolver.

Criterios de aceptación:

- Panel con contadores: incidencias abiertas, por tipo, y más de 48 h (CA-3).
- Lista filtrada por estado y tipo, ordenada por antigüedad.
- Dato de la última ejecución y su cuadre visible en cabecera.

Implementación [D]: Lightning Record Page con componentes estándar y un LWC de resumen, sin rediseñar la interfaz de Salesforce.

### H5.3 Resolver incidencia con acción registrada · MVP

Como analista, quiero resolver una incidencia con una de tres acciones, dejando constancia.

Criterios de aceptación:

- Acciones: `Aplicar` (a una factura concreta), `Ajustar` (importe con motivo obligatorio), `Escalar` (asigna a responsable).
- `Ajustar` crea un registro de ajuste con motivo. No modifica el cobro, el movimiento ni la factura de origen.
- Ajustar sin motivo: no guarda y muestra el campo como obligatorio.
- Al resolver, la incidencia pasa a `Resuelta` y se reevalúa la factura afectada.

### H5.4 Escalado y cierre por responsable · MVP

Como responsable, quiero recibir las incidencias escaladas y cerrarlas.

Criterios de aceptación:

- Solo el rol responsable puede pasar a `Cerrada` una incidencia escalada.
- Cierre sin resolución previa: no permitido.

---

## E6. Permisos, RGPD y auditoría

**Objetivo:** cada rol ve solo lo suyo, y los datos personales caducan.
**Trazabilidad:** RF-12, CA-6, sección 6 del documento 01.

### H6.1 Permission Set por rol · MVP

Como administrador, quiero asignar permisos por rol con Permission Sets, no con Profiles.

Criterios de aceptación:

- Cuatro roles: analista, responsable, auditor, usuario de integración [C].
- Licencia Salesforce Platform para los cuatro usuarios (4 de 6 libres). El usuario de integración es exclusivo de este proyecto [C].
- El usuario de integración lleva el permiso `API Only User`: no puede entrar por la interfaz [D].
- La licencia Salesforce Integration la usa `Integración Web` (candidaturas). No se comparte [C].
- Usuario sin Permission Set: no ve objetos ni incidencias (CA-6).
- Auditor: lectura de todo, sin acciones de resolución.
- Integración: solo crear y actualizar en staging y facturas, sin acceso al panel.

### H6.2 Clases con `with sharing` y `WITH USER_MODE` · MVP

Como desarrollador, quiero que el código respete permisos del usuario en cualquier consulta que devuelve datos al usuario.

Criterios de aceptación:

- Clases de servicio: `with sharing` por defecto.
- Consultas que devuelven datos a la interfaz: `WITH USER_MODE`.
- Revisión en autorrevisión (sección 8 del CLAUDE.md del repo).

### H6.3 Datos de pago sin tarjeta · MVP

Como responsable de RGPD, quiero que Salesforce nunca guarde datos de tarjeta.

Criterios de aceptación:

- Se guardan: token de la pasarela, marca y cuatro últimos dígitos.
- IBAN del ordenante: enmascarado, con hash para detectar pagos repetidos.
- Prueba: un payload con número de tarjeta completo no deja ese número en ningún campo.

### H6.4 Anonimizar pagador tras el plazo · MVP (diseño) / F2 (ejecución programada)

Como responsable de RGPD, quiero que los datos personales del pagador caduquen.

Criterios de aceptación:

- Plazo de anonimización: 24 meses para nombre e IBAN [S]. Importes y referencias se conservan por obligación contable.
- Batch que pone `Anonimizado` en nombre y borra el IBAN en claro. Marca en el registro.
- Plazo definitivo: pendiente de validación con asesoría [F].

### H6.5 Auditoría de acciones · MVP

Como auditor, quiero saber quién hizo qué sobre cada incidencia.

Criterios de aceptación:

- Cada cambio de estado o acción queda con usuario, fecha y valor anterior/nuevo. Campos de auditoría o seguimiento de historial en objeto [D].
- Logs de integración: sin tokens ni datos personales (CLAUDE.md, sección 6).

---

## E7. Integración de vuelta con el ERP (F2)

**Objetivo:** el ERP recibe el estado de conciliación sin esperar al cierre.
**Trazabilidad:** fuera del MVP.

### H7.1 Devolver estado de conciliación al ERP · F2

Como ERP, quiero recibir el estado de cada factura al conciliarse.

Criterios de aceptación:

- Salida mediante Named Credential, sin endpoints hardcodeados.
- Callout desde Queueable con `Database.AllowsCallouts`, nunca desde trigger.
- Simulación del ERP con un Cloudflare Worker en la demo [D].
- Reintento con Finalizer y registro de fallo sin datos personales.

### H7.2 Asientos contables · F2

Fuera del MVP. Salesforce deja el resultado conciliado; el ERP genera los asientos [D].

---

## Trazabilidad: requisito → historias

| RF | Historias |
|---|---|
| RF-01 | H1.1, H1.5 |
| RF-02 | H1.3 |
| RF-03 | H2.1, H2.2, H2.3 |
| RF-04 | H3.1, H3.2 |
| RF-05 | H4.2, H4.3, H4.4, H4.5 |
| RF-06 | H4.2, H4.5, H4.6 |
| RF-07 | H5.1 |
| RF-08 | H5.2 |
| RF-09 | H5.3, H5.4 |
| RF-10 | H4.1 |
| RF-11 | H4.8, H4.9 |
| RF-12 | H6.4 |

Pendientes de RF sin historia propia: ninguno. Los RF de la sección 5 del documento 01 quedan cubiertos.

---

## Criterios de aceptación del negocio → historias

| CA | Historias que lo prueban |
|---|---|
| CA-1 (90 % sin intervención) | H4.2, H4.3, H4.5, H4.6 |
| CA-2 (cierre en 30 min) | H4.1, H4.8 |
| CA-3 (incidencias < 48 h) | H5.2 |
| CA-4 (cuadre exacto) | H2.2, H3.1, H4.8 |
| CA-5 (sin duplicados) | H1.2, H2.3 |
| CA-6 (permisos) | H6.1 |

---

## Preguntas que cambian el diseño

Cada una tiene propuesta por defecto. Solo bloquea si la respuesta es distinta:

| Dato | Historias afectadas | Propuesta por defecto |
|---|---|---|
| F-3 volumen y pico reales | H1.1, H4.1 | Pico x3, lotes de 200 |
| F-4 formato del extracto | H2.1 | camt.053 convertido por script |
| F-6 datos del pagador en pasarela | H1.1, H6.4 | Solo id de cliente y nombre enmascarado |
| Plazo RGPD | H6.4 | 24 meses para datos personales |

## Fuera de alcance de este documento

- Diseño de objetos, campos y relaciones: documento 03 (modelo de datos).
- Diagramas técnicos: documento 04.
- Decisiones de arquitectura con alternativas descartadas: documento 05 (ADR).
- Plan de pruebas y de despliegue: documento 06.

## Siguiente documento

`03-modelo-datos.md`: objetos, campos, relaciones N:M con AplicacionCobro, Liquidación, ajustes, Custom Metadata y claves externas, a partir de las historias de esta versión.
