# 07. Pruebas de permisos por rol

Objetivo: comprobar que cada Permission Set da el acceso que dice el doc 06 (sección 5).

No hay licencias para más usuarios, así que todas las rondas se hacen con un solo usuario, el Analista, cambiando el Permission Set (PS) asignado.

## Antes de empezar

1. Como administrador, crea estos registros de prueba. Ponles el prefijo `TEST-PERM` en el nombre:
   - 1 Factura__c
   - 1 Cobro__c
   - 1 Liquidacion__c
   - 1 CargaFichero__c
   - 1 AvisoPasarela__c
   - 1 Incidencia__c en estado Escalada
2. Usuario de prueba: Conciliación Pagos, Analista (`conciliacion.analista@pedro.romero.demo`).
3. En cada ronda:
   - Quita todos los PS de Conciliación al usuario.
   - Asigna solo el PS de la ronda.
   - Cierra sesión y vuelve a entrar. Sin esto, el cambio puede no aplicarse.
4. Al terminar, borra los registros de prueba y los Ajustes y AplicacionCobro que hayas creado.

## Matriz esperada (doc 06)

Sí o No por rol. La columna "Sin permiso" es el usuario sin ningún PS.

| # | Operación | Integración | Analista | Responsable | Auditor | Sin permiso |
|---|---|---|---|---|---|---|
| 1 | Ver la app "Conciliación de cobros" | No | Sí | Sí | Sí | No |
| 2 | Ver pestañas Factura, Cobro, AplicacionCobro, Ajuste e Incidencia | No | Sí | Sí | Sí | No |
| 3 | Leer Factura | Sí | Sí | Sí | Sí | No |
| 4 | Leer Cobro | Sí | Sí | Sí | Sí | No |
| 5 | Leer Liquidación | Sí | Sí | Sí | Sí | No |
| 6 | Leer CargaFichero (staging) | Sí | No | Sí | Sí | No |
| 7 | Leer AvisoPasarela | Sí | No | Sí | Sí | No |
| 8 | Crear Factura | Sí | No | No | No | No |
| 9 | Editar Factura | Sí | No | No | No | No |
| 10 | Crear CargaFichero | Sí | No | No | No | No |
| 11 | Crear Ajuste | No | Sí | Sí | No | No |
| 12 | Crear AplicacionCobro | No | Sí | Sí | No | No |
| 13 | Editar Incidencia | No | Sí | Sí | No | No |
| 14 | Cerrar una Incidencia escalada | No | No | Sí | No | No |
| 15 | Crear Cobro | Sí | No | No | No | No |
| 16 | Crear Liquidación | Sí | No | No | No | No |
| 17 | Editar Liquidación | No | No | No | No | No |

## Qué hacer en cada fila

1. Abre el App Launcher y busca "Conciliación de cobros".
2. Mira la barra de pestañas de esa app.
3. Abre el registro de Factura de prueba.
4. Abre el registro de Cobro de prueba.
5. Abre el registro de Liquidación de prueba.
6. Abre la pestaña de CargaFichero. Si no hay pestaña, usa la lista relacionada o el enlace directo.
7. Abre el registro de AvisoPasarela de prueba.
8. Intenta crear una Factura nueva. Guárdala y bórrala después.
9. Abre la Factura de prueba e intenta cambiar un campo editable. Guarda o cancela.
10. Intenta crear un CargaFichero nuevo.
11. Intenta crear un Ajuste ligado a la Factura de prueba.
12. Intenta crear una AplicacionCobro ligada a Factura y Cobro de prueba.
13. Abre la Incidencia de prueba e intenta cambiar un campo editable.
14. Abre la Incidencia escalada e intenta cambiar el estado a Cerrada.
15. Crea un Cobro de prueba con importe.
16. Crea una Liquidación de prueba.
17. Abre la Liquidación de prueba e intenta cambiar un campo editable.

## Resultados

Una ronda por rol, en este orden: Integración, Analista, Responsable, Auditor y, al final, Sin permiso. En cada ronda, rellena la columna de ese rol: PASA si coincide con la matriz, FALLA si no.

| # | Int | Analista | Resp | Auditor | Sin permiso |
|---|---|---|---|---|---|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |
| 4 | | | | | |
| 5 | | | | | |
| 6 | | | | | |
| 7 | | | | | |
| 8 | | | | | |
| 9 | | | | | |
| 10 | | | | | |
| 11 | | | | | |
| 12 | | | | | |
| 13 | | | | | |
| 14 | | | | | |
| 15 | | | | | |
| 16 | | | | | |
| 17 | | | | | |

## Qué hacer con un FALLA

- Si el PS da más o menos acceso que el doc: corrige el PS en `force-app/main/default/permissionsets/`.
- Si el doc está mal: corrige el doc 06 y deja constancia en este documento.
- Si la regla de la fila 14 no existe en el repo: trae primero la validation rule desde la org.

## Decisiones ya tomadas

1. El doc 06 se ajustó a las historias de requisitos. Integración crea staging, facturas, cobros y liquidaciones (H1.1, H1.3, H1.4, H2.1, H3.1) y edita facturas (H3.2).
2. Analista no lee CargaFichero, LineaFichero ni AvisoPasarela. Es intencionado: el analista trabaja con el modelo de conciliación, no con el staging.

## Pendiente

- Pendiente de decisión: el PS de Integración concede editar Cobro y Liquidación, y ninguna historia lo exige. El script los marca PENDIENTE, no FALLA. Decidir: quitar el permiso del PS, o justificarlo con una historia. Hasta entonces la fila 17 falla en Integración por diseño.
- La regla que impide cerrar una escalada, `Incidencia_Cerrar_Escalada`, existe en la org pero no en el repo. La fila 14 prueba la org, no el repo, hasta que traigamos esa regla.
