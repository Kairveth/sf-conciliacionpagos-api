# 05. Registro de decisiones de arquitectura (ADR)

Versión 0.1 · 2 de noviembre de 2026 · Parte de: `01` (v0.2), `02` (v0.2), `03` (v0.1) y `04` (v0.1)

Formato: contexto, decisión, alternativa descartada y lo que la haría cambiar. Estado: **Aceptada** (validada en el 01) o **Propuesta** (pendiente de revisión). Versión 0.2: todas aceptadas.

| ADR | Decisión | Estado |
|---|---|---|
| 001 | Relé de webhooks en Cloudflare Worker | Aceptada |
| 002 | Batch Apex para la conciliación, no Queueable | Aceptada |
| 003 | Sin Big Object en el MVP | Aceptada |
| 004 | AplicacionCobro como objeto de unión con dos master-detail | Aceptada |
| 005 | Liquidación como entidad propia | Aceptada |
| 006 | Conciliado = three-way match | Aceptada |
| 007 | Multidivisa fuera del MVP | Aceptada |
| 008 | Ingesta del ERP por fichero nocturno | Aceptada |
| 009 | Motor de reglas: clases fijas con orden en Custom Metadata, sin interfaz | Aceptada |
| 010 | OWD Public Read Only y control por Permission Set | Aceptada |
| 011 | Usuario de integración propio con licencia Platform | Aceptada |
| 012 | Agentforce y scratch orgs fuera del MVP | Aceptada |

---

## ADR-001. Relé de webhooks en Cloudflare Worker

**Contexto.** La pasarela firma sus avisos con HMAC y no sabe autenticarse contra Salesforce con OAuth. Un endpoint de Salesforce expuesto a internet obliga a dar permisos a un usuario invitado.

**Decisión.** Un Worker verifica la firma y obtiene un token OAuth con client credentials. Reenvía el aviso a la API REST de Salesforce. No guarda nada.

**Alternativa descartada.** Endpoint público en un Site de Salesforce con usuario invitado. Expone la org a internet y el invitado necesita permisos sobre el staging.

**Qué la haría cambiar.** Una pasarela que soporte OAuth o un webhook firmado que Salesforce pueda verificar de forma nativa. En ese caso se elimina el relé.

**Consecuencias.** Una pieza más que mantener. El relé es el único punto que conoce el secreto de la pasarela y las credenciales OAuth, ambos en variables secretas del Worker.

## ADR-002. Batch Apex para la conciliación, no Queueable

**Contexto.** La conciliación recorre los cobros del día. El volumen es de 20.000 al día con picos de x3 a fin de mes [S]. CLAUDE.md del repo indica que el batch se justifica desde decenas de miles de registros, y el Queueable por defecto.

**Decisión.** `Database.Batchable` con alcance por cobro y lotes de 200. Cada lote aplica las reglas y registra aplicaciones e incidencias.

**Alternativa descartada.** Queueable encadenado con Finalizer, que procesa un lote y lanza el siguiente. Para cientos de registros sirve. Para 20.000 al día, el encadenamiento es largo y cada salto consume una transacción nueva sin una vista global del avance.

**Qué la haría cambiar.** Un volumen de cientos de cobros al día. En ese caso, Queueable con Finalizer es más sencillo. También si la conciliación se disparase por evento y no por calendario.

**Consecuencias.** Un batch con estado guarda los contadores de la ejecución. La ejecución se bloquea a sí misma (un solo `En curso`). El reintento de un lote fallido se hace con la ejecución siguiente, no dentro del mismo batch.

## ADR-003. Sin Big Object en el MVP

**Contexto.** El histórico de ejecuciones crece cada día. La org tiene 1.000.000 de registros de Big Object disponibles y ninguno usado. El documento 01 lo planteaba como solución inicial.

**Decisión.** Un registro de ejecución por día en objeto estándar, unos 365 al año (0,7 MB). El detalle de ejecuciones con más de 30 días se purga. El resumen se conserva.

**Alternativa descartada.** Big Object para el histórico. Solo admite consultas por los campos de su índice, en el orden de ese índice. No admite triggers ni la mayoría de las consultas que necesita un panel. Con 365 registros al año, el coste no compensa.

**Qué la haría cambiar.** Varios millones de registros de histórico [S]. Entonces Big Object para el histórico y un objeto estándar solo para los últimos 30 días.

**Consecuencias.** La purga es un batch más que hay que probar (H4.9). El histórico operativo cabe en el límite de 5,0 MB de la org de demo.

## ADR-004. AplicacionCobro como objeto de unión con dos master-detail

**Contexto.** Un cobro puede cubrir varias facturas (transferencia B2B), y una factura puede cobrarse con varios pagos (parciales). Los saldos deben calcularse sin Apex.

**Decisión.** `AplicacionCobro__c` con master-detail a Factura y a Cobro. Roll-up en ambos lados.

**Alternativa descartada.** Lookup en ambos lados. Los roll-up no funcionan sobre lookups y el saldo habría que calcularlo en Apex en cada ejecución, con más riesgo de descuadre.

**Qué la haría cambiar.** Un límite de la plataforma que impida dos master-detail en el mismo objeto de unión. En ese caso, un lookup con el saldo calculado en un batch de recálculo.

**Consecuencias.** Cada alta bloquea la factura y el cobro a la vez. Por eso el batch agrupa por cobro (ADR-002). El borrado en cascada se desactiva: no se borra ninguna aplicación.

## ADR-005. Liquidación como entidad propia

**Contexto.** La pasarela no abona un importe por cobro. Abona el neto de todos los cobros del día en un solo movimiento. Si el cobro se conciliara directamente con el abono, no cuadraría nunca.

**Decisión.** Objeto `Liquidacion__c`. Cada cobro de tarjeta apunta a su liquidación. El abono se concilia contra la liquidación, no contra el cobro.

**Alternativa descartada.** Conciliar cada cobro con un abono 1:1. No es posible con tarjeta: la liquidación no mantiene relación uno a uno con los cobros.

**Qué la haría cambiar.** Una pasarela que abone por cobro. En ese caso, la liquidación sigue como registro de control, pero el abono se concilia 1:1.

**Consecuencias.** Hay que validar que la suma de cobros de una liquidación cuadra con su neto (H1.3). Una liquidación descuadrada es incidencia, no error de carga.

## ADR-006. Conciliado = three-way match

**Contexto.** Un cobro puede estar pagado y no abonado. Una factura puede estar cubierta por cobros que el banco aún no ha abonado.

**Decisión.** Una factura está conciliada cuando hay factura, cobros aplicados que suman su importe y abono bancario de esos cobros. Un cobro pagado sin abono queda como `Pendiente de abono`.

**Alternativa descartada.** Conciliado = pagado. Un cobro devuelto o sin abono aparecería como conciliado y el banco nunca lo confirmaría.

**Qué la haría cambiar.** Que finanzas acepte cerrar en "pagado" con un plazo de abono. En ese caso, el estado `Pendiente de abono` se convierte en un aviso con plazo.

**Consecuencias.** Un cobro puede tener estado de abono pendiente durante días. El panel lo muestra como tal, no como incidencia, hasta pasar el plazo (H4.7).

## ADR-007. Multidivisa fuera del MVP

**Contexto.** La org comparte la configuración con el proyecto de candidaturas. Activar la multidivisa no se puede deshacer.

**Decisión.** Moneda única EUR. Un cobro en otra divisa abre incidencia `Divisa no soportada`. La org queda con la multidivisa desactivada.

**Alternativa descartada.** Activar la multidivisa ahora. Activarla altera el modelo de todos los objetos y no se revierte. Sin un caso de cobro en otra divisa en el alcance, no hay razón para asumir ese coste.

**Qué la haría cambiar.** Un cliente real con cobros en otra divisa. En ese caso, una org de demo nueva para probarlo.

**Consecuencias.** La versión de demo no puede mostrar conversión de divisas. Se documenta como límite conocido.

## ADR-008. Ingesta del ERP por fichero nocturno

**Contexto.** El ERP no tiene API confirmada [F-7]. Entrega facturas y, al menos, puede exportar un CSV.

**Decisión.** Fichero CSV nocturno con clave externa `NumeroFactura__c`. Se carga con `sf data upsert bulk` en la demo. En producción, Bulk API 2.0 desde el ERP o desde la herramienta de carga.

**Alternativa descartada.** API REST del ERP con consultas por tramos. Sin una API confirmada, es suponer una integración que no existe.

**Qué la haría cambiar.** Confirmar que el ERP tiene API. Entonces se consultan solo las facturas modificadas desde la última carga.

**Consecuencias.** Hay una ventana de hasta 24 h entre la factura emitida y su llegada. El motor no concilia facturas que aún no han llegado: un cobro sin factura queda como `Sin factura` hasta la siguiente carga.

## ADR-009. Motor de reglas: clases fijas con orden en Custom Metadata

**Contexto.** Hay dos reglas de casación (referencia exacta e importe y cliente) y el orden entre ellas debe poder cambiar sin deploy. CLAUDE.md del repo exige una segunda implementación real antes de crear una abstracción.

**Decisión.** Dos métodos Apex, `PorReferencia` y `PorImporteCliente`, sin interfaz. El orden de ejecución y si cada regla está activa se leen de `ReglaConciliacion__mdt`. La tolerancia y la ventana se leen de `ConfiguracionConciliacion__mdt`.

**Alternativa descartada.** Interfaz `ReglaCasacion` con una implementación por regla y fábrica. Con dos casos, la interfaz no tiene segundo punto de sustitución. Es la abstracción que CLAUDE.md descarta.

**Qué la haría cambiar.** Una tercera regla o reglas definidas por el cliente. A partir de tres casos, la interfaz se justifica.

**Consecuencias.** Añadir una regla exige código y deploy. Cambiar el orden o desactivarla no. Un método nuevo sin entrada en Custom Metadata no se ejecuta, y eso se cubre con un test.

## ADR-010. OWD Public Read Only y control por Permission Set

**Contexto.** Hay cuatro roles con permisos distintos sobre los mismos objetos (CLAUDE.md: Permission Sets, no Profiles).

**Decisión.** OWD Public Read Only en todos los objetos custom. Los permisos de objeto se dan por Permission Set. No hay reglas de compartición.

**Alternativa descartada.** OWD Private con reglas de compartición por rol. Un cambio de sharing exige recalcular y es más difícil de revisar en el código.

**Qué la haría cambiar.** Un requisito de visibilidad por cliente, por ejemplo, que un comercial solo vea sus cobros. En ese caso, OWD Private y reglas por propietario.

**Consecuencias.** Todo lo que el usuario puede leer, lo ve cualquier usuario con el objeto. Por eso los datos personales van enmascarados desde el origen (H6.3), y no dependen del sharing.

## ADR-011. Usuario de integración propio con licencia Platform

**Contexto.** La única licencia Salesforce Integration de la org la usa `Integración Web`, del proyecto de candidaturas [C]. Compartir usuario mezcla permisos entre proyectos.

**Decisión.** Un usuario de integración para conciliación con licencia Salesforce Platform y permiso `API Only User`. Los analistas, responsables y auditores también usan licencia Platform (4 de 6 libres).

**Alternativa descartada.** Reutilizar `Integración Web`. Mezcla permisos entre proyectos y el día que se revoque uno, se rompe el otro.

**Qué la haría cambiar.** Un límite de licencias Platform. En ese caso, comprar licencias o compartir el usuario de integración con permisos mínimos.

**Consecuencias.** Hay que crear el usuario y el Permission Set de integración, y probarlo con el Worker (H1.5). El usuario `API Only User` no puede entrar por la interfaz.

## ADR-012. Agentforce y scratch orgs fuera del MVP

**Contexto.** El plan original incluía una fase opcional con Agentforce y la posibilidad de scratch orgs.

**Decisión.** Fuera del MVP. Agentforce se evalúa en una fase 3 si el MVP sale. Las scratch orgs se usan solo si la prueba de carga no cabe en la org de demo.

**Alternativa descartada.** Incluir Agentforce en el MVP. Añade una dependencia sin requisito del 02 que la justifique.

**Qué la haría cambiar.** Un requisito de triage automático en el alcance. Entonces se mide frente al triage manual, con tiempos reales.

**Consecuencias.** El MVP no tiene IA. El documento 02 no tiene historias de Agentforce.

---

## Riesgos abiertos

| Riesgo | Impacto | Probabilidad | Mitigación | Dueño |
|---|---|---|---|---|
| La pasarela no firma con HMAC en cabecera | Cambia el relé | Media [F] | Confirmar antes del Worker (04, pendiente 1) | Pedro |
| Retención de Field History insuficiente para auditoría | La promesa de auditoría se reduce | Baja [F] | Comprobar el plazo y documentar | Pedro |
| Formato del CSV de liquidación distinto del supuesto | Cambia el parser (H1.3) | Media [F-4, F-6] | Pedir ejemplo real a la pasarela o usar el formato de su sandbox | Pedro |
| Límite de llamadas REST (15.000 por 24 h en la org de demo) | El webhook se corta en pico | Baja con 20.000 cobros [S] | Pasar a Platform Event (F2) | Pedro |
| Bloqueo de filas en roll-ups por alta concurrencia | Lotes lentos o fallidos | Media | Agrupar por cobro (ADR-002, ADR-004) | Pedro |

## Hasta qué volumen aguanta

El diseño cubre 20.000 cobros al día y se calcula para 200.000 [S]. Los cambios para crecer más son de proceso: lotes más grandes, índices en `EstadoConciliacion__c` por encima de un millón de facturas, y purga más frecuente de staging. No cambia el modelo de datos.

## Siguiente documento

`06-plan-pruebas-despliegue.md`: casos de prueba por historia, prueba de carga en bulk (200 registros), prueba de fallo (Named Credential con 500 controlado) y orden de despliegue con dry run.
