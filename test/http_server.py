"""HTTP Server for testing."""
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

from .routes import ROUTES


class RequestHandler(BaseHTTPRequestHandler):
    def _set_headers(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()

    def _parse_get(self):
        parsed = urlparse(self.path)
        path = parsed[2]
        query = parsed[4]
        if "&" in query:
            query_params = {q.split('=')[0]: q.split('=')[1]
                            for q in query.split('&')}
        else:
            query_params = None
        return {"path": path, "headers": self.headers, "query_params": query_params}

    def _parse_post(self):
        parsed = urlparse(self.path)
        path = parsed[2]
        length = self.headers.get('content-length')
        if length:
            body = json.loads(self.rfile.read(int(length)).decode('utf-8'))
        else:
            body = None
        return {"path": path, "headers": self.headers, "body": body}

    def do_GET(self):
        try:
            request = self._parse_get()
            path = request['path']
            if path == '/favicon.ico':
                return
            response = ROUTES[self.command][path](request)
            self._set_headers()
            self.wfile.write(bytes(response, 'utf-8'))
        except:
            self.send_error(500)

    def do_POST(self):
        try:
            request = self._parse_post()
            path = request['path']
            response = ROUTES[self.command][path](request)
            self._set_headers()
            self.wfile.write(bytes(response, 'utf-8'))
        except:
            self.send_error(500)

    def do_PUT(self):
        self.do_POST()


def main():
    """To try the server."""
    try:
        server = HTTPServer(('', 10300), RequestHandler)
        print('Server started...')
        server.serve_forever()
    except KeyboardInterrupt:
        print('^C received, shutting down server.')
        server.socket.close()


if __name__ == '__main__':
    main()
