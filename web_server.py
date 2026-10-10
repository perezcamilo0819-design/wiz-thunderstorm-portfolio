"""Small loopback-only HTTP interface for the WiZ Thunderstorm engine."""

import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


WEB_DIR = Path(__file__).resolve().parent / "web"
PORT = 8765

PRESETS = {
    "relaxing": {
        "name": "Quiet evening",
        "min_interval": 12.0,
        "max_interval": 25.0,
        "rain_intensity": 25,
        "wind_intensity": 20,
        "thunder_volume": 0.30,
        "lightning_brightness": 200,
        "close_weight": 5,
        "medium_weight": 30,
        "far_weight": 65,
    },
    "summer": {
        "name": "Summer storm",
        "min_interval": 7.0,
        "max_interval": 16.0,
        "rain_intensity": 55,
        "wind_intensity": 40,
        "thunder_volume": 0.42,
        "lightning_brightness": 240,
        "close_weight": 15,
        "medium_weight": 50,
        "far_weight": 35,
    },
    "severe": {
        "name": "Heavy weather",
        "min_interval": 3.0,
        "max_interval": 8.0,
        "rain_intensity": 90,
        "wind_intensity": 80,
        "thunder_volume": 0.55,
        "lightning_brightness": 255,
        "close_weight": 35,
        "medium_weight": 50,
        "far_weight": 15,
    },
}

SETTING_LIMITS = {
    "min_interval": (2.0, 30.0),
    "max_interval": (3.0, 45.0),
    "rain_intensity": (0.0, 100.0),
    "wind_intensity": (0.0, 100.0),
    "thunder_volume": (0.0, 1.0),
    "lightning_brightness": (100.0, 255.0),
    "close_weight": (0.0, 100.0),
    "medium_weight": (0.0, 100.0),
    "far_weight": (0.0, 100.0),
}


def run_web_app(command_queue, settings_lock, storm_settings,
                app_state_lock, app_state):
    class StormHandler(BaseHTTPRequestHandler):
        server_version = "StormLocal/1.0"

        def log_message(self, format_string, *args):
            return

        def reply(self, payload, status=200, content_type="application/json; charset=utf-8"):
            if isinstance(payload, (dict, list)):
                payload = json.dumps(payload).encode("utf-8")
            elif isinstance(payload, str):
                payload = payload.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(payload)

        def read_json(self):
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length < 0 or length > 16384:
                    raise ValueError("Request is too large.")
                return json.loads(self.rfile.read(length) or b"{}")
            except (ValueError, json.JSONDecodeError) as error:
                raise ValueError("Invalid request data.") from error

        def do_GET(self):
            if self.path == "/api/state":
                with app_state_lock:
                    current_state = dict(app_state)
                with settings_lock:
                    current_settings = dict(storm_settings)
                self.reply({**current_state, "settings": current_settings})
                return

            pages = {
                "/": ("index.html", "text/html; charset=utf-8"),
                "/styles.css": ("styles.css", "text/css; charset=utf-8"),
                "/app.js": ("app.js", "text/javascript; charset=utf-8"),
            }
            page = pages.get(self.path)
            if page is None:
                self.reply({"error": "Not found."}, 404)
                return
            filename, content_type = page
            try:
                self.reply((WEB_DIR / filename).read_bytes(), content_type=content_type)
            except OSError:
                self.reply({"error": "The interface files could not be read."}, 500)

        def do_POST(self):
            try:
                payload = self.read_json()
                if self.path == "/api/settings":
                    self.save_settings(payload)
                elif self.path == "/api/preset":
                    self.apply_preset(payload)
                elif self.path == "/api/action":
                    self.run_action(payload)
                else:
                    self.reply({"error": "Not found."}, 404)
            except ValueError as error:
                self.reply({"error": str(error)}, 400)

        def save_settings(self, payload):
            if not isinstance(payload, dict):
                raise ValueError("Settings must be sent as an object.")
            clean = {}
            for key, bounds in SETTING_LIMITS.items():
                if key not in payload:
                    continue
                try:
                    value = float(payload[key])
                except (TypeError, ValueError):
                    raise ValueError(f"{key.replace('_', ' ').capitalize()} must be a number.")
                if not (bounds[0] <= value <= bounds[1]):
                    raise ValueError(f"{key.replace('_', ' ').capitalize()} is outside its allowed range.")
                clean[key] = value

            if "audio_only" in payload:
                if not isinstance(payload["audio_only"], bool):
                    raise ValueError("Sound-only mode must be turned on or off.")
                clean["audio_only"] = payload["audio_only"]

            with settings_lock:
                storm_settings.update(clean)
                if storm_settings["max_interval"] < storm_settings["min_interval"]:
                    storm_settings["max_interval"] = storm_settings["min_interval"]
            with app_state_lock:
                app_state["preset"] = "custom"
                preset_name = "Custom"
            self.reply({"ok": True, "preset": preset_name})

        def apply_preset(self, payload):
            preset_key = payload.get("preset") if isinstance(payload, dict) else None
            preset = PRESETS.get(preset_key)
            if preset is None:
                raise ValueError("Choose one of the available storm presets.")
            with settings_lock:
                storm_settings.update({key: value for key, value in preset.items() if key != "name"})
            with app_state_lock:
                app_state["preset"] = preset_key
            self.reply({"ok": True})

        def run_action(self, payload):
            if not isinstance(payload, dict):
                raise ValueError("Action must be sent as an object.")
            action = payload.get("action")
            if action == "start":
                duration = payload.get("duration_minutes")
                if duration is not None:
                    try:
                        duration = float(duration)
                    except (TypeError, ValueError):
                        raise ValueError("Choose a valid storm duration.")
                    if duration <= 0 or duration > 1440:
                        raise ValueError("Storm duration must be between 1 minute and 24 hours.")
                command_queue.put(("start", duration))
            elif action == "stop":
                command_queue.put(("stop", None))
            elif action in ("test_lightning", "test_thunder"):
                strike_type = payload.get("strike_type", "medium")
                if strike_type not in ("close", "medium", "far"):
                    raise ValueError("Choose a valid strike distance.")
                command_queue.put((action, strike_type))
            else:
                raise ValueError("Choose a valid storm action.")
            self.reply({"ok": True})

    class LocalServer(ThreadingHTTPServer):
        daemon_threads = True
        allow_reuse_address = True

    server = LocalServer(("127.0.0.1", PORT), StormHandler)
    url = f"http://127.0.0.1:{PORT}/"
    print(f"WiZ Thunderstorm is running at {url}")
    threading.Timer(0.8, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
