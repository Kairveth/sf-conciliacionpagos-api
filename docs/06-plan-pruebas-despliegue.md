# 06. Plan de pruebas y despliegue

Versión 0.1 · 3 de noviembre de 2026 · Parte de: `02` (v0.2), `03` (v0.1), `04` (v0.2) y `05` (v0.2)

Etiquetas: **[C]** validado · **[D]** decisión de este documento · **[S]** supuesto · **[F]** falta · **[NV]** no verificado en la org.

Ningún test ni despliegue se ha ejecutado todavía. Este documento define qué se prueba, con qué datos y en qué orden se despliega. Sin dry run aprobado no hay deploy.

---

## 1. Niveles de prueba

| Nivel | Qué cubre | Dónde | Herramienta |
|---|---|---|---|
| Unitario Apex | Motor de reglas, validación de lotes, permisos y cuadre | Org de demo | Apex tests con aserciones |
| Bulk Apex | Trigger, batch y carga de 200 registros | Org de demo | Apex tests con 200 registros |
| Integración webhook | Relé Worker → REST de Salesforce | Worker en local o Miniflare + org de demo | Script de envío con firma válida e inválida |
| Carga de datos | Cuadre de un extracto real del volumen de demo | Org de demo | `sf data upsert bulk` y consultas de cuadre |
| LWC | Panel de tres componentes | Local | Jest (`sfdx-lwc-jest`) |
| Permisos | Qué ve y qué puede hacer cada rol | Org de demo | Login As con cada usuario |
| Manual | Flujo de resolución de incidencias | Org de demo | Lista de comprobación en el apartado 5 |

Límite conocido: la org de demo no es sandbox de producción. Los tiempos medidos en ella no son el rendimiento real, solo una referencia [D].

## 2. Pruebas por historia

Cada historia de `02` tiene al menos una prueba. Las marcadas como **Bulk** también prueban 200 registros en un solo test.

### E1. Cobros de la pasarela

| Historia | Prueba | Tipo | Resultado esperado |
|---|---|---|---|
| H1.1 | Aviso válido con token válido | Integración | 201, registro en staging `Recibido` |
| H1.1 | Token inválido | Integración | 401, sin registro |
| H1.1 | Usuario sin permiso de creación | Permisos | 403, sin registro |
| H1.1 | Payload mal formado | Unitario | 400, sin datos personales en log |
| H1.2 | Mismo IdEvento dos veces | Unitario + Bulk | Un único registro, segundo `Duplicado`, respuesta 200 |
| H1.3 | Liquidación con 50 cobros que cuadra | Unitario | Liquidación `Abonada` o `Pendiente de abono` según banco |
| H1.3 | Liquidación descuadrada | Unitario | Incidencia `Liquidación descuadrada` |
| H1.4 | Devolución sobre cobro con factura conciliada | Unitario | Factura pasa a `Abierta` si el saldo es positivo |
| H1.5 | Firma HMAC inválida | Integración | 401 del relé, Salesforce no recibe llamada |
| H1.5 | Salesforce responde 500 | Integración | El relé devuelve 5xx, no guarda nada |

### E2. Extracto bancario

| Historia | Prueba | Tipo | Resultado esperado |
|---|---|---|---|
| H2.1 | Extracto con abonos y cargos | Carga | Solo abonos creados, cargos contados aparte |
| H2.2 | Fichero con suma de importes descuadrada | Carga | Fichero rechazado, cero movimientos |
| H2.3 | Mismo fichero dos veces | Carga | Segunda carga: cero nuevos, resumen con omitidos |

### E3. Facturas del ERP

| Historia | Prueba | Tipo | Resultado esperado |
|---|---|---|---|
| H3.1 | Carga de 200 facturas en bulk | Bulk | 200 facturas, sin duplicados |
| H3.1 | Fila con importe no numérico | Carga | Esa fila rechazada, las demás cargadas, error por fila |
| H3.2 | Cambio de importe en factura conciliada | Unitario | Incidencia `Importe cambiado`, importe sin cambiar |

### E4. Motor de conciliación

| Historia | Prueba | Tipo | Resultado esperado |
|---|---|---|---|
| H4.1 | Dos ejecuciones simultáneas | Unitario | La segunda no arranca y deja aviso |
| H4.2 | Concepto con número de factura y mismo importe | Unitario + Bulk | Aplicación creada, factura conciliada si está abonada |
| H4.3 | Dos facturas candidatas del mismo importe | Unitario | Incidencia `Ambigüedad` con las dos |
| H4.4 | Cambio de tolerancia en Custom Metadata | Unitario | Se aplica en la siguiente ejecución, sin deploy |
| H4.5 | Transferencia que cubre tres facturas | Unitario | Tres aplicaciones con suma igual al pago |
| H4.5 | Transferencia sin números de factura | Unitario | Incidencia `Sin referencia` |
| H4.6 | Dos pagos parciales que suman el importe | Unitario | Factura `Conciliada` |
| H4.6 | Sobrepago | Unitario | Incidencia `Sobrepago` |
| H4.7 | Cobro de tarjeta sin liquidación abonada | Unitario | `Pendiente de abono` |
| H4.7 | Abono llega después | Unitario | Pasa a `Abonado` y se reevalúa la factura |
| H4.8 | Ejecución de 200 cobros | Bulk | Leídos = conciliados + incidencias + duplicados |
| H4.8 | Ejecución que no cuadra | Unitario | Estado `Error de cuadre` |
| H4.9 | Purga de detalle con más de 30 días | Unitario | Detalle borrado, resumen conservado |

### E5. Incidencias y panel

| Historia | Prueba | Tipo | Resultado esperado |
|---|---|---|---|
| H5.1 | Misma diferencia en dos ejecuciones | Unitario | Una sola incidencia (`ClaveOrigen`) |
| H5.2 | Panel con incidencias de más de 48 h | Jest + manual | Contador y marca visibles |
| H5.3 | Ajustar sin motivo | Unitario | Error, no guarda |
| H5.3 | Ajustar con motivo | Unitario | Registro de ajuste, origen sin cambios |
| H5.4 | Responsable cierra escalada | Permisos | Permitido |
| H5.4 | Analista intenta cerrar escalada | Permisos | Bloqueado por validation rule |

### E6. Permisos, RGPD y auditoría

| Historia | Prueba | Tipo | Resultado esperado |
|---|---|---|---|
| H6.1 | Usuario sin Permission Set | Permisos | No ve objetos de conciliación (CA-6) |
| H6.1 | Auditor intenta editar una incidencia | Permisos | Bloqueado |
| H6.2 | Consulta de lista con usuario de analista | Unitario | Solo registros que el usuario puede ver |
| H6.3 | Payload con número de tarjeta completo | Unitario | El número no aparece en ningún campo |
| H6.4 | Pagador con más de 24 meses | Unitario | Nombre `Anonimizado`, importe conservado |
| H6.5 | Cambio de estado de incidencia | Manual | Historial con usuario y fecha |

## 3. Pruebas de carga

**Objetivo:** demostrar que el diseño aguanta el volumen de 20.000 cobros al día sin cambios de estructura [S].

- **En la org de demo:** carga de 1.600 registros (presupuesto de `03`). Se mide tiempo de carga y de batch, y se comprueba cuadre exacto [D].
- **En tests Apex:** 200 registros por lote, en el trigger y en el batch [D].
- **Límite:** 5,0 MB de almacenamiento. Las pruebas de carga se hacen con datos de demo y se borran al terminar. No se llega a 20.000 registros reales.
- **Extrapolación:** el tiempo medido en 1.600 registros se multiplica por la relación de volúmenes. Se presenta como estimación, no como medida [D].

Criterio: cuadre exacto en todas las ejecuciones (CA-4) y 0 duplicados (CA-5).

## 4. Pruebas de fallo

| Fallo | Cómo se provoca | Resultado esperado |
|---|---|---|
| Relé no alcanza Salesforce | Worker apunta a una URL que devuelve 500 | El relé devuelve 5xx a la pasarela, no guarda nada |
| Token OAuth caducado | Token de prueba inválido | 401, el relé no reintenta sin límite |
| Batch falla a mitad | Excepción forzada en un lote de test | Ejecución en `Error`, lotes ya procesados coherentes |
| Fichero corrupto | CSV con columnas que faltan | Rechazo entero, cero movimientos |

Nota sobre candidaturas: AUD-005 sigue sin verificar en el camino de fallo. La prueba de fallo del 500 controlado se hace en candidaturas antes de dar el hallazgo por cerrado. Es independiente de este proyecto.

## 5. Permisos: prueba con Login As

Antes de cada prueba de permisos, comprobar que el usuario tiene el Permission Set asignado.

| Usuario | Puede ver | Puede crear | Puede editar | Puede cerrar escalada |
|---|---|---|---|---|
| Integración | Staging, avisos de pasarela, facturas, cobros, liquidaciones | Staging (CargaFichero, LineaFichero, AvisoPasarela), facturas, cobros y liquidaciones (H1.1, H1.3, H1.4, H2.1, H3.1) | Facturas (H3.2) | No |
| Analista | Modelo de conciliación, sin staging ni avisos de pasarela | Aplicaciones y ajustes | Incidencias | No |
| Responsable | Todo el modelo | Aplicaciones y ajustes | Incidencias | Sí |
| Auditor | Todo el modelo | No | No | No |
| Sin permiso | Nada | No | No | No |

Hasta que existan los Permission Sets, la prueba de permisos queda pendiente. Login As permite probar cada rol sin conocer su contraseña [NV: comprobar que el admin tiene el permiso de inicio de sesión como usuario].

## 6. Orden de despliegue

Cada paso tiene su dry run. Ningún paso se despliega sin tu confirmación explícita (CLAUDE.md, sección 7).

| Paso | Contenido | Dependencia |
|---|---|---|
| 1 | Objetos y campos (metadata XML) | Ninguna |
| 2 | Custom Metadata y valores por defecto | Paso 1 |
| 3 | Permission Sets | Paso 1 |
| 4 | Clases Apex y tests | Pasos 1 y 2 |
| 5 | Trigger y handler | Paso 4 |
| 6 | LWC y FlexiPages | Paso 4 |
| 7 | Carga de demo y prueba de cuadre | Pasos 1 a 6 |

Comando de validación: `sf project deploy validate` con `-l RunSpecifiedTests` y la lista de tests del paso. Solo cuando el dry run pasa, se ejecuta el deploy real, y con tu visto bueno.

**Rollback:** redesplegar el commit anterior. No hay migración de datos, así que la vuelta atrás es solo de metadatos [D]. Los datos de demo se borran con una carga de limpieza.

## 7. Criterios de salida

1. Todos los tests de Apex pasan.
2. Cobertura mínima 75 % por requisito de Salesforce. Objetivo propio: 90 % en clases de negocio [D].
3. Jest del LWC pasa.
4. Cuadre exacto en la carga de demo.
5. Las pruebas de permisos del apartado 5 pasan para los cinco casos.
6. Ninguna consulta ni DML dentro de bucles (autorrevisión de CLAUDE.md, sección 8).
7. Ningún dato de tarjeta ni IBAN en claro en la org.

## 8. Riesgos de prueba

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Almacenamiento de 5 MB | Las cargas de prueba no caben | Datos de demo borrados entre pruebas |
| Límite de 15.000 llamadas REST por 24 h | Pruebas del webhook cortadas | Pruebas espaciadas y en bloques |
| Test que depende del orden | Resultados falsos | Cada test prepara sus datos en `@TestSetup` |
| Permisos de Login As no disponibles | Prueba de roles pendiente | Usar la prueba con el propio usuario admin y el de integración |

## 9. Información que falta

| # | Dato | Afecta a |
|---|---|---|
| F-11 | Firma HMAC de la pasarela (cabecera y algoritmo) | H1.5 |
| F-12 | Permiso de Login As del admin | Prueba de roles |
| F-13 | Sandbox de la pasarela para pruebas | Integración del webhook |

## 10. Siguiente paso

Cuando los tres usuarios de rol estén creados, se prepara el primer paso del despliegue: metadata de objetos y campos, en el repo, con dry run. Antes, se confirma el alcance con tu visto bueno.
