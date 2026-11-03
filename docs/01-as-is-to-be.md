# 01. AS-IS y TO-BE: conciliación de pagos

Versión 0.2 · 2 de noviembre de 2026 · Estado: decisiones de la sección 9 validadas

Caso ficticio. La empresa, sus datos y sus cifras son supuestos de un ejercicio de portfolio, no de un cliente real. Cada dato se marca con su origen:

- **[C] Confirmado:** dato medido en una org o decisión validada por el autor del caso (sección 9, 2 de noviembre de 2026).
- **[S] Supuesto:** valor razonable que el diseño necesita. Se valida antes de construir.
- **[F] Falta:** dato que nadie ha dado todavía. Se indica cómo afecta.

---

## 1. Contexto del caso

Distribuidor con dos canales:

- **B2C:** tienda online. El cliente paga con tarjeta a través de una pasarela. [S]
- **B2B:** clientes de empresa. Pagan por transferencia, a menudo varias facturas de una vez. [S]

Tres sistemas participan en el proceso:

| Sistema | Qué aporta | Fuente de verdad de… |
|---|---|---|
| ERP de facturación | Facturas emitidas, importes, vencimientos | Qué se debe [S] |
| Pasarela de pagos | Cobros autorizados, comisiones, devoluciones, liquidaciones | Qué se cobró a la tarjeta [S] |
| Banco | Movimientos que llegan a la cuenta, en extracto diario | Qué dinero entró [S] |

Salesforce no sustituye a ninguno. Recibe sus datos, los cruza y registra el resultado. Los datos de entrada no se corrigen en Salesforce: una corrección se registra como ajuste, nunca como cambio sobre el dato de origen. [C]

## 2. AS-IS: cómo funciona hoy

**Proceso actual** [S]:

1. Cada día, un analista exporta los movimientos del banco y los cobros de la pasarela a Excel.
2. Busca cada factura a mano, por número o por importe.
3. Marca lo que cuadra y anota en una hoja aparte lo que no.
4. Las diferencias se resuelven por correo o por llamada. Tarda entre dos y tres días.
5. Al cierre mensual, el contable revisa las notas de la hoja y las pasa al ERP.

**Dolores** [S]:

- Las diferencias se descubren tarde, cuando el cierre ya está cerca.
- Un pago parcial o una transferencia que cubre tres facturas obliga a cuadrar a mano.
- No hay histórico: no se sabe quién resolvió una diferencia ni cómo.
- Si el analista falta, nadie concilia.

**Lo que no sabemos** [F]:

- Quién concilia hoy y cuánto tiempo le lleva. Afecta a la estimación del ahorro, no al diseño.
- Si el banco ofrece un extracto automático o solo un PDF. Afecta al formato de ingesta.

## 3. TO-BE: cómo debe funcionar

Cada día, sin intervención:

1. Llegan los cobros de la pasarela y el extracto bancario. Los avisos de la pasarela pasan por un relé (Cloudflare Worker) que verifica la firma HMAC y llama a Salesforce con OAuth client credentials [C]. La liquidación diaria llega por fichero. El ERP entrega las facturas por carga nocturna.
2. Salesforce valida, guarda y deduplica cada registro. Un aviso repetido no crea un cobro nuevo.
3. Un batch concilia en tres pasos:
   1. **Referencia exacta:** el número de factura aparece en el concepto del pago.
   2. **Importe y cliente** dentro de una ventana de fechas.
   3. **Tolerancia:** diferencia máxima aceptada [S: 0,05 €].
4. Lo que cuadra queda conciliado. Lo que no encaja abre una incidencia con su motivo.
5. Un analista resuelve las incidencias desde un panel. Cada acción queda registrada.
6. Al final, un resumen de la ejecución muestra si cuadra: leídas = conciliadas + incidencias + duplicadas.

**Definición de conciliado: three-way match** [C]. Una factura está conciliada cuando cuadran tres piezas: la factura (ERP), los cobros aplicados (pasarela o transferencia) y el abono en el banco. Los cobros aplicados deben sumar su importe, dentro de la tolerancia. Un cobro pagado sin abono queda como **pendiente de abono**, no como conciliado.

**Liquidación** [C]. El banco no recibe un abono por cada pago con tarjeta. La pasarela agrupa los cobros del día y abona el neto en un solo movimiento. Por eso el abono de tarjeta se comprueba por liquidación:

- Tarjeta: Cobro → Liquidación → MovimientoBanco. Un abono cubre N cobros.
- Transferencia B2B: MovimientoBanco → Cobro (1:1) → AplicacionCobro → Factura(s).

**Relación entre cobros y facturas** [C]: N:M. Una factura puede cobrarse en varios pagos (parciales). Un pago puede cubrir varias facturas (transferencia B2B). La aplicación de un cobro a una factura es un registro propio con su importe.

**Casos que el MVP cubre** [C]:

- Pago parcial de una factura.
- Transferencia que cubre varias facturas.
- Comisión de la pasarela: la liquidación abona el neto. La comisión se registra en cada cobro para que el cuadre sea exacto.
- Devolución o contracargo: un importe negativo que reabre la factura.
- Duplicado: el mismo aviso llega dos veces.

**Fuera del MVP** [C]:

- Multidivisa. Activarla en la org no se puede deshacer, y la org la comparte el proyecto de candidaturas. Un cobro en otra divisa abre una incidencia `Divisa no soportada`.
- Escritura de asientos contables. Salesforce concilia y deja el resultado para el ERP.
- Devolver el estado de conciliación al ERP en tiempo real. Es la fase 2.

## 4. Criterios de aceptación del negocio

Objetivos propuestos [S], que se validan con finanzas:

| # | Criterio | Cómo se mide |
|---|---|---|
| CA-1 | Al menos el 90 % de los cobros se concilian sin intervención | Conciliados automáticamente / cobros del día |
| CA-2 | El cierre diario está listo en menos de 30 minutos tras recibir los ficheros | Hora de fin de la última ejecución |
| CA-3 | Ninguna incidencia abierta más de 48 horas | Antigüedad de incidencias abiertas |
| CA-4 | Cada ejecución cuadra al céntimo | Leídas = conciliadas + incidencias + duplicadas |
| CA-5 | Un aviso repetido no genera dos cobros | Prueba con el mismo id de pasarela dos veces |
| CA-6 | Un usuario sin permiso no ve ni modifica incidencias | Prueba con usuario sin Permission Set |

## 5. Requisitos funcionales (resumen)

| ID | Requisito |
|---|---|
| RF-01 | Recibir cobros de la pasarela por webhook, con firma verificada |
| RF-02 | Recibir liquidaciones diarias de la pasarela, con comisiones |
| RF-03 | Recibir el extracto bancario diario y registrar cada abono |
| RF-04 | Recibir facturas del ERP por carga nocturna, con clave externa |
| RF-05 | Conciliar en batch con reglas configurables (referencia, importe, ventana, tolerancia) |
| RF-06 | Registrar cada aplicación de cobro a factura con su importe |
| RF-07 | Abrir una incidencia por cada diferencia, con motivo y tipo |
| RF-08 | Panel con resumen, lista de incidencias y detalle |
| RF-09 | Resolver una incidencia: aplicar, ajustar o escalar, con registro de la acción |
| RF-10 | Lanzar la conciliación a mano, además de la programada |
| RF-11 | Registrar cada ejecución con su cuadre |
| RF-12 | Retención RGPD: anonimizar datos del pagador pasado el plazo |

## 6. Requisitos no funcionales

- **Volumen** [S]: 20.000 cobros al día, con picos de tres veces a fin de mes. El diseño aguanta diez veces esa cifra (200.000 al día).
- **Idempotencia** [C]: cada registro entrante tiene una clave externa; cargar dos veces el mismo fichero o recibir dos veces el mismo webhook no duplica nada.
- **Privacidad** [C]: ningún dato de tarjeta entra en Salesforce; solo el token, la marca y los cuatro últimos dígitos. El IBAN del ordenante se guarda enmascarado y con un hash para detectar pagos repetidos.
- **Permisos** [C]: un Permission Set por rol. Cuatro roles: analista, responsable, auditor y usuario de integración. Los cuatro usuarios usan licencia Salesforce Platform (4 de 6 libres). El usuario de integración es exclusivo de este proyecto.
- **Inmutabilidad** [C]: cobros, movimientos y facturas solo los cambia su fuente. Desde Salesforce, las correcciones son registros de ajuste con motivo.
- **Auditoría** [C]: toda acción sobre una incidencia queda registrada con usuario y fecha.

## 7. Restricciones de la plataforma

Medidas en la org de desarrollo el 2 de noviembre de 2026 [C]:

| Recurso | Límite | Uso actual | Consecuencia |
|---|---|---|---|
| Almacenamiento de datos | 5,0 MB | 78 KB (2 %) | Unos 2.400 registros en total, con 2 KB cada uno [S] |
| Almacenamiento de archivos | 20,0 MB | 0 B | Sin impacto |
| Big Object | 1.000.000 registros | 0 | No se usa en el MVP (ver documento 05, ADR) |
| Licencia Salesforce Platform | 6 | 0 | 4 usuarios del proyecto |
| Licencia Salesforce Integration | 1 | 1 | Sin libres: el proyecto no la usa |

**Consecuencia para la demo:** no cabe la carga de 50.000 filas en la org. Presupuesto propuesto: unos 1.600 registros [S]:

| Objeto | Registros de demo | Espacio aproximado |
|---|---|---|
| Factura | 400 | 0,8 MB |
| Cobro | 400 | 0,8 MB |
| AplicacionCobro | 450 | 0,9 MB |
| MovimientoBanco | 200 | 0,4 MB |
| Liquidación | 20 | 0,04 MB |
| Incidencia | 100 | 0,2 MB |
| Ejecución | 30 | 0,06 MB |
| Staging | 0 (se borra al procesar) | 0 |
| **Total** | **1.600** | **3,2 MB (64 %)** |

**Volumen de 200.000 al día:** se demuestra con tests de Apex y con el cálculo documentado del diseño, no con datos en la org.

**Histórico** [C]: un registro de ejecución por día en un objeto estándar (365 al año, unos 0,7 MB). El detalle se purga a los 30 días [S]. Big Object descartado para el MVP: con este volumen no compensa, solo admite consultas por los campos de su índice y no admite triggers. Se reconsidera por encima de varios millones de registros de histórico (documento 05).

## 8. Información que falta y cómo afecta

| # | Dato que falta | Cómo afecta al diseño | Propuesta por defecto |
|---|---|---|---|
| F-1 | Quién concilia hoy y cuánto tarda | Solo afecta al ahorro estimado | Estimación del caso: dos días de retraso |
| F-2 | Valor exacto de la tolerancia | Afecta al número de incidencias | 0,05 €, en Custom Metadata |
| F-3 | Pico de volumen real y el histórico a migrar | Afecta a los lotes y a la migración | Pico x3 a fin de mes; migrar solo facturas abiertas |
| F-4 | Formato del extracto bancario (Norma 43, camt.053 u otro) | Afecta a la ingesta | camt.053 (ISO 20022), convertido por script |
| F-5 | Si el banco ofrece extracto automático | Afecta a la frecuencia de la carga | Extracto diario a las 06:00 |
| F-6 | Qué datos del pagador llegan en la pasarela | Afecta a RGPD y a la seguridad | Solo id de cliente y nombre enmascarado |
| F-7 | Si el ERP permite API o solo fichero | Afecta a la integración con el ERP | Fichero nocturno con clave externa |
| F-8 | ~~Quién usa la licencia Salesforce Integration~~ Cerrado 2-11-2026: la usa `Integración Web` (perfil Salesforce API Only System Integrations), del proyecto de candidaturas [C] | No cambia el diseño | Usuario de integración propio con licencia Platform y permiso API Only User |

Ninguno de estos datos bloquea el modelo de datos, porque cada uno tiene una propuesta por defecto. Cada propuesta se valida antes de la historia que depende de ella.

## 9. Decisiones validadas

Validadas por el autor del caso el 2 de noviembre de 2026.

1. **N:M entre cobros y facturas**, con objeto intermedio AplicacionCobro.
2. **Tres fuentes de verdad** (ERP, pasarela, banco). Salesforce guarda el resultado y no corrige los datos de origen: las correcciones son ajustes.
3. **Conciliado = three-way match** (factura, cobro, abono), no solo pagado.
4. **Multidivisa fuera del MVP.** Un cobro en otra divisa abre incidencia.
5. **Liquidación como entidad propia.** El abono de tarjeta se concilia por liquidación.
6. **Sin Big Object en el MVP.** Histórico en objeto estándar con purga del detalle.
7. **Relé de webhooks en Cloudflare Worker.** Verifica la firma HMAC y entra en Salesforce con OAuth client credentials. Descartado: endpoint público en un Site con usuario invitado.

Cada decisión tendrá su ADR con la alternativa descartada en el documento 05.

## 10. Siguiente documento

`02-requisitos.md`: épicas, historias y criterios de aceptación, a partir de los RF y CA de este documento.
