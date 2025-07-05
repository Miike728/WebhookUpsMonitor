# 🔌 Monitorización de SAI con Alertas en Discord

Este proyecto contiene un script en Python que vigila un Sistema de Alimentación Ininterrumpida (SAI) usando la herramienta `nut` (`upsc`). Envía notificaciones a un canal de Discord cuando detecta cambios en el estado del SAI, como cortes de suministro, batería baja o microcortes repetidos.

## 🚀 Funcionalidades principales
- Consulta el SAI cada pocos segundos mediante `upsc`.
- Informa por Discord cuando el SAI pasa a batería, vuelve a línea o presenta estados especiales (sobrecarga, bypass, apagado forzado, etc.).
- Envía recordatorios periódicos mientras el SAI está en batería.
- Detecta microcortes (cortes de pocos segundos) y avisa si se producen varios en una misma ventana de tiempo.
- Notifica al arrancar la VM o equipo que ejecuta el script.
- Menciona a un usuario concreto en Discord si la situación es crítica (batería baja o múltiples eventos).

## ⚙️ Configuración
Edita las variables al inicio de `script.py` para adaptarlo a tu entorno:
- `UPS_NAME`: nombre del SAI en `nut`.
- `DISCORD_WEBHOOK_URL`: URL del webhook de Discord donde se enviarán las alertas.
- `DISCORD_USER_ID`: ID del usuario a mencionar en avisos importantes.
- `CHECK_INTERVAL`: intervalo entre chequeos del SAI (segundos).
- `REPORT_INTERVAL`: intervalo de reporte cuando está en batería (segundos).
- `LONG_BATTERY_ALERT`: tiempo máximo en batería antes de avisar (segundos).
- `MULTIPLE_CUTS_WINDOW`: ventana temporal para contar microcortes (segundos).
- `CUT_COUNT_THRESHOLD`: número de cortes dentro de la ventana para generar alerta.
- `MICROCUT_MAX_SECONDS`: duración máxima para considerar un corte como microcorte.

## 🧰 Requisitos
- Python 3.
- Paquete `requests` (`pip install requests`).
- Tener `nut` instalado y funcionando con el comando `upsc`.
- Un webhook de Discord válido.

## 🧪 Uso
Ejecuta el script directamente:
```bash
python3 script.py
```
Se puede añadir como servicio o incluirlo en `rc.local` para que arranque automáticamente junto con la máquina que lo ejecuta.

## 📎 Notas
- Al iniciarse, el script envía un mensaje indicando que la monitorización está activa.
- Ignora errores de red al mandar mensajes para evitar bloqueos.
- Puede adaptarse para interactuar con otros sistemas, como generadores o apagado automático de servidores.
