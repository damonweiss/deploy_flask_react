from __future__ import annotations
import os, json
from flask import Flask, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO
import threading
import paho.mqtt.client as mqtt

socketio = SocketIO(cors_allowed_origins="*")  # binds in create_app()

def _mqtt_thread(app: Flask):
    host = os.environ.get("MQTT_HOST", "localhost")
    port = int(os.environ.get("MQTT_PORT", "1883"))
    username = os.environ.get("MQTT_USERNAME", "") or None
    password = os.environ.get("MQTT_PASSWORD", "") or None
    topics = (os.environ.get("MQTT_TOPICS", "vela/#") or "vela/#").split(",")

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    if username and password:
        client.username_pw_set(username, password)

    def on_connect(c, userdata, flags, reason_code, properties=None):
        try:
            for t in topics:
                c.subscribe(t.strip(), qos=0)
        except Exception:
            pass

    def on_message(c, userdata, msg):
        payload = msg.payload
        try:
            text = payload.decode("utf-8", errors="replace")
            data = json.loads(text)
        except Exception:
            data = {"raw": payload.hex(), "text": payload.decode("utf-8", errors="replace")}
        socketio.emit("mqtt_message", {
            "topic": msg.topic,
            "qos": msg.qos,
            "data": data
        })

    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(host, port, keepalive=30)
    client.loop_forever(retry_first_connection=True)

def create_app():
    app = Flask(__name__)
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    socketio.init_app(app)

    @app.get("/api/health")
    def health():
        import time
        return jsonify({"status": "ok", "service": "backend", "ts": time.time()})

    # start MQTT worker
    th = threading.Thread(target=_mqtt_thread, args=(app,), daemon=True)
    th.start()
    return app
