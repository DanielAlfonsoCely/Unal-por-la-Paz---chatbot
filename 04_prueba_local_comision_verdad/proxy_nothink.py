"""
Proxy minimo entre Dify y Ollama: le agrega "think": false a las peticiones
de chat/generate para que gemma4 no gaste tokens razonando.
Todo lo demas (embeddings, listar modelos, etc.) pasa igual.

Uso:   python proxy_nothink.py
Dify:  Base URL del modelo gemma4:12b -> http://192.168.1.78:11435
(solo libreria estandar, no hay que instalar nada)
"""
import http.client
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

OLLAMA_HOST = os.environ.get("OLLAMA_UPSTREAM_HOST", "127.0.0.1")
OLLAMA_PORT = int(os.environ.get("OLLAMA_UPSTREAM_PORT", "11434"))
LISTEN_PORT = int(os.environ.get("PROXY_PORT", "11435"))
RUTAS_THINK = ("/api/chat", "/api/generate")


class Proxy(BaseHTTPRequestHandler):
    # HTTP/1.0: la respuesta termina al cerrar la conexion, asi el streaming
    # (varios JSON seguidos) pasa tal cual sin lios de Content-Length.
    protocol_version = "HTTP/1.0"

    def _reenviar(self):
        largo = int(self.headers.get("Content-Length") or 0)
        cuerpo = self.rfile.read(largo) if largo else b""

        if self.command == "POST" and self.path.split("?")[0] in RUTAS_THINK:
            try:
                datos = json.loads(cuerpo)
                datos["think"] = False
                cuerpo = json.dumps(datos).encode("utf-8")
                print(f"[proxy] {self.path} modelo={datos.get('model')} -> think=false | options={datos.get('options')}", flush=True)
            except Exception as e:
                print(f"[proxy] no pude leer el JSON, lo dejo pasar igual: {e}", flush=True)

        conn = http.client.HTTPConnection(OLLAMA_HOST, OLLAMA_PORT, timeout=600)
        try:
            headers = {"Content-Type": self.headers.get("Content-Type", "application/json")}
            if cuerpo:
                headers["Content-Length"] = str(len(cuerpo))
            conn.request(self.command, self.path, body=cuerpo or None, headers=headers)
            resp = conn.getresponse()

            self.send_response(resp.status)
            self.send_header("Content-Type", resp.getheader("Content-Type", "application/json"))
            self.send_header("Connection", "close")
            self.end_headers()
            while True:
                trozo = resp.read1(65536)
                if not trozo:
                    break
                self.wfile.write(trozo)
                self.wfile.flush()
        except Exception as e:
            print(f"[proxy] error hablando con Ollama: {e}", flush=True)
            try:
                self.send_error(502, "No pude hablar con Ollama")
            except Exception:
                pass
        finally:
            conn.close()

    do_GET = do_POST = do_DELETE = do_HEAD = _reenviar

    def log_message(self, *args):
        pass  # silencia el log por defecto (solo se ven las lineas [proxy])


if __name__ == "__main__":
    servidor = ThreadingHTTPServer(("0.0.0.0", LISTEN_PORT), Proxy)
    print(f"Proxy escuchando en :{LISTEN_PORT} -> Ollama {OLLAMA_HOST}:{OLLAMA_PORT} (think=false en chat/generate)", flush=True)
    servidor.serve_forever()
