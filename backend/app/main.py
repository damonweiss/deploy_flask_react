from flask import Flask, jsonify
try:
    from flask_cors import CORS
except Exception:
    CORS = None  # optional

def create_app():
    app = Flask(__name__)

    if CORS:
        CORS(app, resources={r"/api/*": {"origins": [
            "http://localhost:5173", "http://127.0.0.1:5173"
        ]}})

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok", "service": "backend", "version": "1.0.0"})

    return app

# WSGI default
app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
