from datetime import datetime
import os
import time
import subprocess
import requests

# === CONFIGURACIÓN ===
UPS_NAME = "apc"
DISCORD_WEBHOOK_URL = "WEBHOOK_URL"
DISCORD_USER_ID = "USER_ID"
CHECK_INTERVAL = 0.5
REPORT_INTERVAL = 300
LONG_BATTERY_ALERT = 1800
MULTIPLE_CUTS_WINDOW = 900
CUT_COUNT_THRESHOLD = 2
MICROCUT_MAX_SECONDS = 5

# === ETIQUETAS DE ESTADO ===
status_labels = {
    "OB": "🔋 EN BATERÍA (OB)",
    "OL": "🟢 EN LÍNEA (OL)",
    "LB": "🔴 BATERÍA BAJA (LB)",
    "OVER": "⚠️ SOBRECARGA (OVER)",
    "BYPASS": "🔁 BYPASS ACTIVO",
    "CHRG": "🔌 CARGANDO",
    "DISCHRG": "🔋 DESCARGANDO",
    "OFF": "⚫ APAGADO (OFF)",
    "FSD": "⚠️ APAGADO FORZADO (FSD)"
}

# === ESTADO INTERNO ===
last_status_flags = {}
on_battery = False
charging = False
battery_start_time = None
cut_start_time = None
last_onbattery_report = 0
last_lowbatt_report = 0
last_longbatt_alert = 0
cut_history = []
buffer_event = None
buffer_timestamp = None
charging_after_cut = False
last_battery_voltage = None


def read_ups_values():
    try:
        result = subprocess.run(["upsc", UPS_NAME], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        lines = result.stdout.splitlines()
        data = {}
        for line in lines:
            if ":" in line:
                key, val = line.split(":", 1)
                data[key.strip()] = val.strip()
        return data
    except Exception:
        return {}


def send_discord_embed(title, color, fields_dict, mention_user=False):
    embed = {
        "title": title,
        "color": color,
        "fields": [{"name": name, "value": value, "inline": True} for name, value in fields_dict.items()],
        "timestamp": datetime.utcnow().isoformat()
    }
    payload = {"embeds": [embed]}
    if mention_user:
        payload["content"] = f"<@{DISCORD_USER_ID}>"
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=payload)
    except:
        pass


# === INICIALIZACIÓN ===
boot_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
send_discord_embed(
    "🖥️ La VM de monitoreo del SAI se ha iniciado",
    0x95a5a6,
    {"Hora": boot_time}
)

init_data = read_ups_values()
if init_data:
    ups_status = init_data.get("ups.status", "")
    for flag in status_labels:
        last_status_flags[flag] = flag in ups_status
    on_battery = "OB" in ups_status
    charging = "CHRG" in ups_status
    if on_battery:
        battery_start_time = time.time()
        cut_start_time = battery_start_time
        last_onbattery_report = battery_start_time
        last_lowbatt_report = battery_start_time
        last_longbatt_alert = 0
        last_battery_voltage = init_data.get("battery.voltage", "N/A")

# === LOOP PRINCIPAL ===
while True:
    data = read_ups_values()
    now = time.time()
    current_voltage = data.get("battery.voltage", "N/A")

    current_flags = {
        flag: flag in data.get("ups.status", "")
        for flag in status_labels
    }

    if on_battery and not current_flags["OB"] and (
        current_flags["OL"] or current_flags["CHRG"]
    ):
        on_battery = False
        battery_end_time = now
        duration = battery_end_time - cut_start_time
        mins = int(duration // 60)
        secs = int(duration % 60)
        charge = data.get("battery.charge", "N/A")
        estado = "Cargando" if current_flags["CHRG"] else "En espera"
        cut_history.append(
            {
                "timestamp": battery_end_time,
                "duration": duration,
                "type": "normal",
                "charge": charge,
            }
        )
        volt_before = last_battery_voltage if last_battery_voltage is not None else "N/A"
        volt_after = current_voltage
        send_discord_embed(
            "✅ El SAI ha vuelto a línea",
            0x2ecc71,
            {
                "Tiempo en batería": f"{mins} min {secs} s",
                "Carga actual": f"{charge} %",
                "Voltaje antes": f"{volt_before} V",
                "Voltaje en línea": f"{volt_after} V",
                "Estado": estado,
            },
        )
        last_battery_voltage = None
        charging_after_cut = current_flags["CHRG"]

    if current_flags["OB"] and not on_battery and buffer_event is None:
        buffer_event = data
        buffer_timestamp = now

    elif buffer_event:
        if not current_flags["OB"]:
            # Volvió antes de los 5s
            duration = now - buffer_timestamp
            if duration < MICROCUT_MAX_SECONDS:
                charge = data.get("battery.charge", buffer_event.get("battery.charge", "N/A"))
                volt = data.get("battery.voltage", buffer_event.get("battery.voltage", "N/A"))
                estado = "Cargando" if current_flags["CHRG"] else "En línea"
                cut_history.append({"timestamp": now, "duration": duration, "type": "micro", "charge": charge})
                send_discord_embed(
                    "⚡ Microcorte detectado",
                    0xf39c12,
                    {
                        "Duración": f"{duration:.1f} segundos",
                        "Estado": estado,
                        "Carga batería": f"{charge} %",
                        "Voltaje": f"{volt} V"
                    }
                )

                recent = [c for c in cut_history if now - c["timestamp"] <= MULTIPLE_CUTS_WINDOW]
                micro = [c for c in recent if c["type"] == "micro"]
                normales = [c for c in recent if c["type"] == "normal"]
                total_seg = sum(c["duration"] for c in recent)
                min_charge = min((int(c["charge"]) for c in recent if str(c["charge"]).isdigit()), default="N/A")

                if len(recent) >= CUT_COUNT_THRESHOLD:
                    send_discord_embed(
                        "⚠️ Múltiples eventos detectados",
                        0xe67e22,
                        {
                            "Microcortes": str(len(micro)),
                            "Cortes normales": str(len(normales)),
                            "Total duración sin línea": f"{total_seg:.1f} s",
                            "Carga mínima registrada": f"{min_charge} %"
                        },
                        mention_user=True
                    )
            buffer_event = None
        elif now - buffer_timestamp >= MICROCUT_MAX_SECONDS:
            on_battery = True
            battery_start_time = buffer_timestamp
            cut_start_time = buffer_timestamp
            last_onbattery_report = buffer_timestamp
            last_battery_voltage = buffer_event.get("battery.voltage", "N/A")
            volt = last_battery_voltage
            runtime = buffer_event.get("battery.runtime", "N/A")
            charge = buffer_event.get("battery.charge", "N/A")
            send_discord_embed(
                "🔋 El SAI ha pasado a modo batería",
                0xf1c40f,
                {
                    "Voltaje batería": f"{volt} V",
                    "Runtime estimado": f"{runtime} s",
                    "Carga actual": f"{charge} %"
                }
            )
            buffer_event = None

    if charging_after_cut and charging and not current_flags["CHRG"]:
        send_discord_embed(
            "🔋 Batería completamente cargada",
            0x27ae60,
            {"Estado": "Batería ha finalizado la carga"}
        )
        charging_after_cut = False
    charging = current_flags["CHRG"]

    if on_battery:
        if now - last_onbattery_report >= REPORT_INTERVAL:
            volt = data.get("battery.voltage", "N/A")
            runtime = data.get("battery.runtime", "N/A")
            charge = data.get("battery.charge", "N/A")
            send_discord_embed(
                "📊 Actualización en modo batería",
                0x3498db,
                {
                    "Voltaje": f"{volt} V",
                    "Runtime": f"{runtime} s",
                    "Carga": f"{charge} %"
                }
            )
            last_onbattery_report = now

        if current_flags["LB"]:
            if last_lowbatt_report == 0 or now - last_lowbatt_report >= 60:
                send_discord_embed(
                    "🔴 Batería baja",
                    0xe74c3c,
                    {"Estado": "La batería está por debajo del umbral"},
                    mention_user=True,
                )
                last_lowbatt_report = now
        else:
            last_lowbatt_report = 0

        if battery_start_time and now - battery_start_time >= LONG_BATTERY_ALERT:
            if last_longbatt_alert == 0 or now - last_longbatt_alert >= REPORT_INTERVAL:
                mins = int((now - battery_start_time) / 60)
                send_discord_embed(
                    "⏳ Batería activa por tiempo prolongado",
                    0xe67e22,
                    {"Duración": f"{mins} minutos en batería"},
                )
                last_longbatt_alert = now

    elif on_battery and not current_flags["OB"] and (current_flags["OL"] or current_flags["CHRG"]):
        on_battery = False
        battery_end_time = now
        duration = battery_end_time - cut_start_time
        mins = int(duration // 60)
        secs = int(duration % 60)
        charge = data.get("battery.charge", "N/A")
        estado = "Cargando" if current_flags["CHRG"] else "En espera"
        cut_history.append({
            "timestamp": battery_end_time,
            "duration": duration,
            "type": "normal",
            "charge": charge
        })
        volt_before = last_battery_voltage if last_battery_voltage is not None else "N/A"
        volt_after = current_voltage
        send_discord_embed(
            "✅ El SAI ha vuelto a línea",
            0x2ecc71,
            {
                "Tiempo en batería": f"{mins} min {secs} s",
                "Carga actual": f"{charge} %",
                "Voltaje antes": f"{volt_before} V",
                "Voltaje en línea": f"{volt_after} V",
                "Estado": estado
            }
        )
        last_battery_voltage = None

    if on_battery:
        last_battery_voltage = current_voltage

    last_status_flags = current_flags.copy()
    time.sleep(CHECK_INTERVAL)
