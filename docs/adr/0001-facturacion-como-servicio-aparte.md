# 1. Facturación como servicio aparte

Fecha: 2026-10-01. Estado: aceptada e implementada.

## Contexto

Comanda empezó como un solo servicio .NET con la facturación adentro: la caja emitía la factura, una cola interna la mandaba a ARCA y reintentaba si ARCA no respondía.

La facturación se diferencia del resto del sistema en tres cosas:

- **Depende de un tercero que se cae.** ARCA tiene caídas y cortes programados. El salón, la cocina y la caja no dependen de nadie de afuera.
- **Tiene su propio material sensible.** Facturar de verdad necesita el certificado digital del local, que no tiene por qué estar al alcance del resto del sistema.
- **Cambia por motivos propios.** Una resolución nueva de ARCA o un cambio de proveedor de facturación no debería obligar a tocar ni a redesplegar el sistema del salón.

Salón, caja, cocina y stock quedan juntos: cobrar una cuenta toca a los cuatro y tiene que quedar completo o no quedar, en una sola transacción.

## Decisión

La facturación es un servicio .NET aparte (`src/Comanda.Billing`), en el mismo repositorio, con su propia base (`billing`) y su propia imagen.

- **Comanda pide, Facturación decide.** El pedido lleva todo lo que la factura necesita: ítems, descuento, total, IVA por alícuota y receptor. Facturación nunca lee la base de Comanda. Los mensajes están en `Comanda.Contracts`, que define solo su forma, sin reglas.
- **Nada se pierde si uno de los dos está caído.** Cada servicio guarda lo que tiene que mandarle al otro en un outbox, en la misma transacción que el cambio, y lo manda después con reintentos (`Comanda.Messaging`).
  - Comanda caída: los estados de las facturas esperan en el outbox de Facturación.
  - Facturación caída: los pedidos esperan en el outbox de Comanda.
- **El cajero se entera en el momento.** Comanda guarda el pedido y además intenta mandarlo enseguida. Si Facturación lo rechaza (un DNI mal cargado, por ejemplo), el cajero ve el motivo ahí mismo. Si no responde, la factura queda "esperando a Facturación" y sale sola.
- **Repetir no duplica.** Cada pedido lleva un id: el mismo pedido dos veces es una sola factura. Cada estado lleva un número de versión: un estado viejo que llega tarde no pisa a uno nuevo.
- **Comanda tiene una copia de cómo está cada factura.** De ella leen la caja, la lista de cuentas sin facturar y los avisos de ARCA caída. Se actualiza con los estados que manda Facturación.
- **El orden se mantiene por destino.** Un pedido nuevo nunca se adelanta a otro mensaje para Facturación que todavía no salió, así la numeración sigue en orden. Que notify-router esté caído no frena los pedidos de factura.
- **Los dos servicios se autentican con claves.** Hay una clave para cada dirección (`BILLING_KEY` y `BILLING_CALLBACK_KEY`). Facturación no publica puertos: solo el servidor de Comanda le habla, dentro de la red de Docker.

## Alternativas descartadas

- **Seguir como un módulo dentro de Comanda.** Es más simple, pero ata el ciclo de vida del salón al de ARCA y deja el certificado al alcance de todo el sistema.
- **Un repositorio aparte.** No suma nada mientras lo mantenga una sola persona. El límite lo marcan el proyecto, la base y la imagen, no el repositorio.
- **Solo llamadas HTTP, sin outbox.** Con Facturación caída, la caja no podría pedir facturas y habría que reintentar a mano.
- **Un broker de mensajes (RabbitMQ, Kafka).** Corre en una PC del local y son dos servicios: un outbox en PostgreSQL da la misma garantía sin otra pieza que instalar y mantener.

## Consecuencias

- Hay dos servicios para desplegar y dos claves para configurar. El Compose del local los levanta juntos y no arranca si faltan las claves.
- La entrega es al menos una vez, así que todo lo que se recibe tiene que ser idempotente. Lo es, por id de pedido y por versión.
- Un mensaje que el otro servicio rechaza (por ejemplo, una factura vieja cuyo número ya existe) queda apartado con el motivo a la vista. No se reintenta para siempre.
- Los respaldos tienen que incluir las dos bases.

## Cómo se hizo la mudanza

En cuatro fases, cada una con los tests en verde antes de pasar a la siguiente:

1. El servicio de Facturación con su base, sus contratos y su outbox, sin que nadie lo usara todavía.
2. Comanda le pide las facturas por HTTP y guarda la copia; se apaga la facturación interna.
3. Una migración convierte, en una sola transacción, las facturas y los datos fiscales que tenía Comanda en mensajes para Facturación y borra las tablas viejas. Facturación las importa con su número y su CAE originales.
4. Facturación en el Compose del local.

## Comprobado

Con el Compose del local y las imágenes de producción:

- una factura sale autorizada;
- con Facturación detenida, la caja recibe "esperando a Facturación" y la factura sale sola unos 14 segundos después de que vuelve;
- con ARCA caída (simulada), la factura queda pendiente con el error a la vista y sale cuando ARCA vuelve;
- con el servidor de Comanda detenido, Facturación autoriza igual, guarda el aviso y Comanda se pone al día al volver;
- el servidor arranca aunque Facturación esté caída;
- después de bajar y levantar todo, las facturas y los datos fiscales siguen ahí.
