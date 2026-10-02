# Diagramas

HTML autocontenidos: se abren en cualquier navegador, sin conexión y sin instalar nada. Cada uno existe en español y en inglés (`_en`).

| Archivo | Qué muestra |
|---|---|
| `arquitectura.html` | El mapa completo, para técnicos: contenedores, proyectos, protocolos, claves y bases. |
| `circuito.html` | De la mesa a la factura, en seis pasos. |
| `facturacion.html` | Qué pasa si se cae Facturación o ARCA: outbox, cola y estados con versión. |
| `instalacion.html` | La instalación en el local y por qué funciona sin internet. |

No se editan a mano: los generan `tools/architecture.py` y `tools/diagrams.py`, y `tools/record.py` los graba como GIF en `docs/media/`, cuadro por cuadro, pausando las animaciones en cada instante. El sitio los copia de acá con `scripts/sync_diagrams.py`.

```bash
python tools/architecture.py
python tools/diagrams.py
python tools/record.py        # necesita Playwright y ffmpeg
```
