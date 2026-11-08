"""Where the bulk file may come from, and a proxy in the way: S1 (security), P4.

These run the script against its own Scryfall base, `https://api.scryfall.com` (no
`DECKWRIGHT_SCRYFALL_API`), through a local HTTPS proxy given as `HTTPS_PROXY`. The proxy answers
`CONNECT` for Scryfall's hosts by terminating TLS itself, with a certificate made here for
`api.scryfall.com`, `data.scryfall.io` and the hosts a hostile listing names, under a test CA the
script trusts through `SSL_CERT_FILE`; behind it are the stand-in's own handlers (conftest.py). So
nothing leaves the machine, and a listing can point the script anywhere a real one could.

`refuse_connect` makes the proxy answer every `CONNECT` with a 403, as a proxy that blocks Scryfall
does: the script sees a URLError, not an HTTP answer.
"""

from __future__ import annotations

import json
import re
import shutil
import socketserver
import ssl
import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from conftest import (
    BULK_FILE,
    BULK_PATH,
    EXIT_UNREACHABLE,
    _serve,
    _serve_data,
    jsonl_gz,
    load_recorded,
)

# Hosts the proxy terminates TLS for. The last two are not Scryfall's, whatever their names say.
HOSTS = ["api.scryfall.com", "data.scryfall.io", "evil.example", "data.scryfall.io.evil.example"]


def _openssl(*args: str, cwd: Path):
    subprocess.run(["openssl", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture(scope="module")
def certificates(tmp_path_factory) -> dict[str, Path]:
    """A test CA and one server certificate for HOSTS, signed by it."""
    if not shutil.which("openssl"):
        pytest.skip("openssl is needed to make the proxy's certificates")
    d = tmp_path_factory.mktemp("tls")
    _openssl(
        "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "2", "-subj", "/CN=deckwright test CA",
        "-keyout", "ca.key", "-out", "ca.pem",
        "-addext", "basicConstraints=critical,CA:TRUE", "-addext", "keyUsage=critical,keyCertSign,cRLSign",
        cwd=d,
    )
    _openssl("req", "-newkey", "rsa:2048", "-nodes", "-subj", "/CN=api.scryfall.com", "-keyout", "host.key",
             "-out", "host.csr", cwd=d)
    (d / "host.ext").write_text(
        "basicConstraints=critical,CA:FALSE\n"
        "keyUsage=critical,digitalSignature,keyEncipherment\n"
        "extendedKeyUsage=serverAuth\n"
        "subjectKeyIdentifier=hash\n"
        "authorityKeyIdentifier=keyid\n"
        "subjectAltName=" + ",".join(f"DNS:{h}" for h in HOSTS) + "\n",
        encoding="utf-8",
    )
    _openssl("x509", "-req", "-in", "host.csr", "-CA", "ca.pem", "-CAkey", "ca.key", "-CAcreateserial",
             "-days", "2", "-extfile", "host.ext", "-out", "host.pem", cwd=d)
    return {"ca": d / "ca.pem", "cert": d / "host.pem", "key": d / "host.key"}


@dataclass
class Proxy:
    url: str = ""
    connects: list[str] = field(default_factory=list)
    plain: list[str] = field(default_factory=list)
    refuse_connect: bool = False


@pytest.fixture
def proxy(scryfall, certificates):
    """An HTTPS proxy in front of the stand-in, on the hosts Scryfall really uses."""
    state = Proxy()
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certificates["cert"], certificates["key"])
    recorded = load_recorded()
    api_handler, data_handler = _serve(scryfall, recorded), _serve_data(scryfall)

    class Handler(socketserver.StreamRequestHandler):
        def handle(self):
            line = self.rfile.readline().decode("latin-1").strip()
            while self.rfile.readline() not in (b"\r\n", b"\n", b""):
                pass
            if not line:
                return
            method, target, *_ = line.split()
            if method != "CONNECT":
                # A plain http:// request through the proxy: answered with a good bulk file, so a
                # script that followed such a link would succeed and the test would see it.
                state.plain.append(target)
                payload = jsonl_gz(scryfall.bulk)
                self.wfile.write(
                    b"HTTP/1.1 200 OK\r\nContent-Type: application/gzip\r\n"
                    + f"Content-Length: {len(payload)}\r\nConnection: close\r\n\r\n".encode()
                    + payload
                )
                return
            state.connects.append(target)
            host = target.rsplit(":", 1)[0]
            if state.refuse_connect or host not in HOSTS:
                self.wfile.write(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n")
                return
            self.wfile.write(b"HTTP/1.1 200 Connection established\r\n\r\n")
            self.wfile.flush()
            try:
                tls = context.wrap_socket(self.connection, server_side=True)
            except (ssl.SSLError, OSError):
                return
            # Every host but the API serves the Default Cards file at BULK_PATH, as the data host does.
            handler = api_handler if host == "api.scryfall.com" else data_handler
            try:
                handler(tls, self.client_address, self.server)
            except OSError:
                pass

    server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    state.url = f"http://127.0.0.1:{server.server_address[1]}"
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield state
    server.shutdown()
    server.server_close()


def through(deck, proxy, certificates) -> dict:
    """The environment of a command run against Scryfall's real base, through the proxy."""
    return {
        "DECKWRIGHT_SCRYFALL_API": None,
        "HTTPS_PROXY": proxy.url,
        "https_proxy": proxy.url,
        "HTTP_PROXY": proxy.url,
        "http_proxy": proxy.url,
        "SSL_CERT_FILE": str(certificates["ca"]),
        "DECKWRIGHT_CACHE": str(deck.cache),
    }


def listing_pointing_at(scryfall, uri: str):
    listing = scryfall.listing()
    for entry in listing["data"]:
        if entry["type"] == "default_cards":
            entry["jsonl_download_uri"] = uri
    return lambda: listing


def said(proc) -> str:
    return proc.stdout + proc.stderr


# S1 ----------------------------------------------------------------------------------


def test_bulk_host_scryfall_followed(deck, scryfall, proxy, certificates):
    """The control: a listing on the real base pointing at https://data.scryfall.io is followed."""
    scryfall.listing = listing_pointing_at(scryfall, "https://data.scryfall.io" + BULK_PATH)
    env = through(deck, proxy, certificates)
    entry = json.loads(deck.run("lookup", "Sol Ring", env=env).stdout)[0]
    assert entry["result"] == "found", entry
    assert proxy.connects == ["api.scryfall.com:443", "data.scryfall.io:443"], proxy.connects
    assert [r.path for r in scryfall.requests] == ["/bulk-data"]
    assert [r.path for r in scryfall.data_requests] == [BULK_PATH]
    assert (deck.cache / BULK_FILE).is_file()


@pytest.mark.parametrize(
    "where",
    ["plain http on the data host", "plain http on another host", "file", "https on another host",
     "https on a look-alike host"],
)
def test_bulk_host_not_scryfall_refused(deck, scryfall, proxy, certificates, tmp_path, where):
    """On the real base, a `jsonl_download_uri` that is not https on a Scryfall host is never fetched."""
    planted = tmp_path / "planted.jsonl.gz"
    planted.write_bytes(jsonl_gz(scryfall.bulk))
    uri = {
        "plain http on the data host": "http://data.scryfall.io" + BULK_PATH,
        "plain http on another host": scryfall.data_url + BULK_PATH,
        "file": planted.as_uri(),
        "https on another host": "https://evil.example" + BULK_PATH,
        "https on a look-alike host": "https://data.scryfall.io.evil.example" + BULK_PATH,
    }[where]
    scryfall.listing = listing_pointing_at(scryfall, uri)
    env = through(deck, proxy, certificates)

    proc = deck.run("lookup", "Sol Ring", env=env, expect=EXIT_UNREACHABLE)
    assert "Traceback" not in proc.stderr, proc.stderr
    assert "Sol Ring" in said(proc)
    assert proxy.connects == ["api.scryfall.com:443"], f"only the listing was asked for: {proxy.connects}"
    assert not proxy.plain, f"no plain request was made: {proxy.plain}"
    assert not scryfall.data_requests, "the data host was never asked"
    assert not (deck.cache / BULK_FILE).exists(), "nothing is kept"


# P4 ----------------------------------------------------------------------------------


def test_bulk_proxy_refuses_connect(deck, proxy, certificates):
    """A proxy that refuses CONNECT is Scryfall out of reach: exit 3, a plain message, nothing kept."""
    proxy.refuse_connect = True
    env = through(deck, proxy, certificates)

    for args in (("lookup", "Sol Ring"), ("collection", str(write_list(deck)))):
        proc = deck.run(*args, env=env, expect=EXIT_UNREACHABLE)
        assert "Traceback" not in proc.stderr, proc.stderr
        assert re.search(r"scryfall", said(proc), re.I) and re.search(r"reach", said(proc), re.I), said(proc)
    assert proxy.connects and all(c == "api.scryfall.com:443" for c in proxy.connects), proxy.connects
    assert not (deck.cache / BULK_FILE).exists()


def write_list(deck) -> Path:
    path = deck.cwd.parent / "list.txt"
    path.write_text("1 Sol Ring\n", encoding="utf-8")
    return path
