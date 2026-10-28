#!/usr/bin/env python3
"""
Servidor web y sincronizador autónomo para arenero inteligente Tuya.
Diseñado para despliegue directo en Coolify / Docker / VPS.
"""

import os
import sys
import time
import json
import sqlite3
import hashlib
import hmac
import urllib.parse
from datetime import datetime, timedelta
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
import requests

# ================= CONFIGURACIÓN =================
CLIENT_ID = os.environ.get("TUYA_CLIENT_ID", "h3ckrv4vgper9fgd4x4x")
SECRET = os.environ.get("TUYA_SECRET", "8f1d6e8d57f84667a6e94e1fffa3d801")
BASE_URL = os.environ.get("TUYA_BASE_URL", "https://openapi.tuyaeu.com")
DEVICE_ID = os.environ.get("TUYA_DEVICE_ID", "bf39a8ac3f20224c9535px")
PORT = int(os.environ.get("PORT", "8080"))
SYNC_INTERVAL = int(os.environ.get("SYNC_INTERVAL_MINUTES", "30")) * 60

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(BASE_DIR, "data"))
os.makedirs(DATA_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "cat_weights.db")
OUTPUT_JSON = os.path.join(DATA_DIR, "data.json")

# ================= BASE DE DATOS =================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS weights (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_time INTEGER,
            datetime_str TEXT,
            cat TEXT,
            cat_key TEXT,
            weight_g INTEGER,
            weight_kg REAL,
            duration_s INTEGER DEFAULT 0,
            UNIQUE(datetime_str, weight_g)
        )
    ''')
    conn.commit()
    return conn

# ================= FIRMA TUYA OPENAPI =================
def get_sorted_url(path):
    if "?" not in path:
        return path
    base_path, query = path.split("?", 1)
    params = urllib.parse.parse_qsl(query, keep_blank_values=True)
    sorted_params = sorted(params, key=lambda x: x[0])
    sorted_query = urllib.parse.urlencode(sorted_params)
    return base_path + "?" + sorted_query

def tuya_request(method, path, token=None, body=""):
    t = str(int(time.time() * 1000))
    content_sha256 = hashlib.sha256(body.encode("utf-8")).hexdigest()
    signed_url = get_sorted_url(path)
    string_to_sign = f"{method}\n{content_sha256}\n\n{signed_url}"
    
    if token:
        sign_str = CLIENT_ID + token + t + string_to_sign
    else:
        sign_str = CLIENT_ID + t + string_to_sign
        
    sign = hmac.new(SECRET.encode("utf-8"), sign_str.encode("utf-8"), hashlib.sha256).hexdigest().upper()
    
    headers = {
        "client_id": CLIENT_ID,
        "sign": sign,
        "t": t,
        "sign_method": "HMAC-SHA256"
    }
    if token:
        headers["access_token"] = token
        
    url = BASE_URL + signed_url
    if method == "GET":
        return requests.get(url, headers=headers, timeout=15)
    elif method == "POST":
        headers["Content-Type"] = "application/json"
        return requests.post(url, headers=headers, data=body, timeout=15)

# ================= SINCRONIZACIÓN =================
sync_lock = threading.Lock()
last_sync_info = {"status": "Never synced", "time": None, "count": 0}

def perform_sync():
    with sync_lock:
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{now_str}] Iniciando sincronización con Tuya Cloud...")
        try:
            conn = init_db()
            cur = conn.cursor()
            
            # 1. Obtener Token
            token_res = tuya_request("GET", "/v1.0/token?grant_type=1").json()
            if not token_res.get("success"):
                err_msg = f"Error obteniendo token: {token_res.get('msg')}"
                print(err_msg)
                last_sync_info["status"] = err_msg
                return False
            token = token_res["result"]["access_token"]
            
            # 2. Consultar registros recientes
            now_ms = int(time.time() * 1000)
            seven_days_ago_ms = now_ms - (7 * 24 * 3600 * 1000)
            
            path = f"/v1.0/devices/{DEVICE_ID}/logs?codes=cat_weight&end_time={now_ms}&size=100&start_time={seven_days_ago_ms}&type=7"
            res = tuya_request("GET", path, token=token).json()
            
            if not res.get("success"):
                err_msg = f"Error consultando logs: {res.get('msg')}"
                print(err_msg)
                last_sync_info["status"] = err_msg
                return False
                
            logs = res.get("result", {}).get("logs", [])
            new_count = 0
            
            for l in logs:
                event_time_ms = l["event_time"]
                dt = datetime.fromtimestamp(event_time_ms / 1000.0)
                dt_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                weight_g = int(l["value"])
                weight_kg = round(weight_g / 1000.0, 2)
                
                if weight_g >= 4000:
                    cat = "Mei"
                    cat_key = "mei"
                elif weight_g >= 3000:
                    cat = "Sami"
                    cat_key = "sami"
                else:
                    cat = "Parcial"
                    cat_key = "other"
                    
                cur.execute('''
                    INSERT OR IGNORE INTO weights (event_time, datetime_str, cat, cat_key, weight_g, weight_kg)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (event_time_ms, dt_str, cat, cat_key, weight_g, weight_kg))
                
                if cur.rowcount > 0:
                    new_count += 1
                    
            conn.commit()
            
            # 3. Exportar todo a data.json
            cur.execute('''
                SELECT event_time, datetime_str, cat, cat_key, weight_g, weight_kg
                FROM weights
                ORDER BY datetime_str ASC
            ''')
            rows = cur.fetchall()
            
            export_data = []
            for idx, r in enumerate(rows, 1):
                dt_obj = datetime.strptime(r[1], "%Y-%m-%d %H:%M:%S")
                export_data.append({
                    "id": idx,
                    "dt": r[1],
                    "ts": int(dt_obj.timestamp()),
                    "w": r[5],
                    "cat": r[3],
                    "name": r[2] if r[2] != "Parcial" else "Visita parcial"
                })
                
            with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
                
            last_sync_info["status"] = "OK"
            last_sync_info["time"] = now_str
            last_sync_info["count"] = len(export_data)
            print(f"[{now_str}] Sincronización exitosa. {new_count} nuevos. Total histórico: {len(export_data)}")
            conn.close()
            return True
        except Exception as e:
            err_msg = f"Excepción en sincronización: {str(e)}"
            print(err_msg)
            last_sync_info["status"] = err_msg
            return False

def sync_loop():
    while True:
        try:
            perform_sync()
        except Exception as e:
            print("Error en bucle de sincronización:", e)
        time.sleep(SYNC_INTERVAL)

# ================= SERVIDOR HTTP =================
class AppRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        
        # Health check para Coolify
        if path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "healthy", "last_sync": last_sync_info}).encode("utf-8"))
            return
            
        # API de sincronización manual bajo demanda
        elif path == "/api/sync":
            success = perform_sync()
            self.send_response(200 if success else 500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": success, "last_sync": last_sync_info}).encode("utf-8"))
            return
            
        # Servir data.json
        elif path == "/data.json":
            if os.path.exists(OUTPUT_JSON):
                with open(OUTPUT_JSON, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            else:
                self.send_response(404)
                self.end_headers()
            return
            
        # Servir index.html
        elif path == "/" or path == "/index.html":
            index_path = os.path.join(BASE_DIR, "index.html")
            if os.path.exists(index_path):
                with open(index_path, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            else:
                self.send_response(404)
                self.end_headers()
            return
            
        # Archivos estáticos generales
        else:
            return super().do_GET()

def run_server():
    # Iniciar sincronización inicial
    print("Realizando sincronización inicial de arranque...")
    perform_sync()
    
    # Iniciar hilo de sincronización periódica
    t = threading.Thread(target=sync_loop, daemon=True)
    t.start()
    
    # Iniciar servidor HTTP
    server_address = ("", PORT)
    httpd = HTTPServer(server_address, AppRequestHandler)
    print(f"Servidor iniciado en http://0.0.0.0:{PORT}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")
        httpd.server_close()

if __name__ == "__main__":
    run_server()
