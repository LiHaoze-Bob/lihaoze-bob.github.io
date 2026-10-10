import functools
import http.server
import threading
from urllib.request import urlopen

import pytest

import scripts.site as site


@pytest.mark.parametrize(('published_url', 'request_path'), [
    ('https://lihaoze-bob.github.io/', '/'),
    ('https://example.com/notes-site/', '/notes-site/'),
])
def test_preview_serves_pages_and_assets_at_published_base(tmp_path, monkeypatch, published_url, request_path):
    output = tmp_path / 'site'
    output.mkdir()
    (output / 'index.html').write_text('<img src="' + request_path + 'assets/image.svg">')
    assets = output / 'assets'
    assets.mkdir()
    (assets / 'image.svg').write_text('<svg/>')
    runtime = tmp_path / '.runtime'
    runtime.mkdir()
    # An existing preview directory must also work after the root migration.
    (runtime / 'preview').mkdir()
    monkeypatch.setattr(site, 'ROOT', tmp_path)
    monkeypatch.setattr(site, 'RUNTIME', runtime)
    monkeypatch.setattr(site, 'config', lambda: {'site': {'url': published_url}})

    directory, preview_url = site.preview_location()
    assert preview_url == 'http://127.0.0.1:8765' + request_path
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(directory))
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        origin = 'http://127.0.0.1:' + str(server.server_port)
        with urlopen(origin + request_path) as response:
            assert response.read().decode() == '<img src="' + request_path + 'assets/image.svg">'
        with urlopen(origin + request_path + 'assets/image.svg') as response:
            assert response.read() == b'<svg/>'
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
