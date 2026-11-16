"""Serwis HTTP humanizera. Tylko biblioteka standardowa, zero zależności.

Uruchomienie:  python3 -m humanizer.server           (domyślnie 127.0.0.1:8011)
Zmienne:       HUMANIZER_PORT, HUMANIZER_HOST, HUMANIZER_TOKEN, HUMANIZER_STYL_DIR

Endpointy:
  GET  /zdrowie                       -> status, rejestry, liczba przykładów
  POST /sprawdz    {rejestr, tekst}   -> naruszenia + statystyki
  POST /kontekst   {rejestr, zadanie, kto, n, uwagi} -> gotowy prompt
  POST /zapisz     {rejestr, draft, moja, uwagi}     -> dopisanie pary do poprawki.md
  GET  /przyklady?rejestr=            -> robocze przykłady Ady
  POST /przyklad   {rejestr, oferta, odpowiedz, kategoria, lead_key} -> nowy roboczy przykład
  POST /zatwierdz  {rejestr, id}      -> przeniesienie przykładu do przyklady.md
"""
from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import store, validator

TOKEN = os.environ.get("HUMANIZER_TOKEN", "")


def _rejestry() -> dict[str, int]:
    return {r: len(store.examples(r)) for r in store.registers()}


class Handler(BaseHTTPRequestHandler):
    server_version = "humanizer/1.0"

    def _json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _auth(self) -> bool:
        if not TOKEN:
            return True
        return self.headers.get("X-Humanizer-Token") == TOKEN

    def log_message(self, fmt: str, *args) -> None:  # ciszej w logach
        print("%s - %s" % (self.address_string(), fmt % args), flush=True)

    def do_GET(self) -> None:
        if not self._auth():
            return self._json(401, {"blad": "brak tokenu"})
        sciezka = urlparse(self.path)
        if sciezka.path.rstrip("/") in ("/zdrowie", ""):
            return self._json(200, {"status": "ok", "rejestry": _rejestry(), "katalog": str(store.styl_dir())})
        if sciezka.path.rstrip("/") == "/przyklady":
            rejestr = (parse_qs(sciezka.query).get("rejestr") or ["rejestr-klient"])[0]
            return self._json(200, {"przyklady": store.examples_ada(rejestr)})
        return self._json(404, {"blad": "nie ma takiego endpointu"})

    def do_POST(self) -> None:
        if not self._auth():
            return self._json(401, {"blad": "brak tokenu"})
        try:
            dlugosc = int(self.headers.get("Content-Length", "0"))
            dane = json.loads(self.rfile.read(dlugosc) or b"{}")
        except (ValueError, json.JSONDecodeError):
            return self._json(400, {"blad": "niepoprawny JSON"})

        rejestr = dane.get("rejestr", "")
        try:
            if self.path.rstrip("/") == "/sprawdz":
                tekst = dane.get("tekst", "")
                if not tekst:
                    return self._json(400, {"blad": "brak pola tekst"})
                n = validator.validate(tekst, rejestr)
                return self._json(200, {
                    "ok": validator.czy_ok(n),
                    "naruszenia": [{"kod": x.kod, "waga": x.waga, "opis": x.opis} for x in n],
                    "statystyki": validator.statystyki(tekst.strip()),
                })

            if self.path.rstrip("/") == "/kontekst":
                k = store.kontekst(
                    rejestr,
                    zadanie=dane.get("zadanie", ""),
                    kto=dane.get("kto", ""),
                    n=int(dane.get("n", 8)),
                    uwagi=dane.get("uwagi", ""),
                )
                return self._json(200, {"prompt": k.prompt(dane.get("zadanie", ""), dane.get("kto", ""), dane.get("uwagi", "")),
                                        "uzyte_przyklady": len(k.przyklady)})

            if self.path.rstrip("/") == "/pending":
                if not dane.get("draft", "").strip():
                    return self._json(400, {"blad": "brak pola draft"})
                p = store.start_pending(rejestr, dane["draft"], dane.get("zadanie", ""), dane.get("kto", ""))
                return self._json(200, {"ok": True, "plik": str(p)})

            if self.path.rstrip("/") == "/zapisz":
                moja = dane.get("moja", "")
                if dane.get("pending"):
                    p = store.save_pending(moja, dane.get("uwagi", ""))
                else:
                    p = store.append_correction(rejestr, dane.get("draft", ""), moja, dane.get("uwagi", ""))
                return self._json(200, {"ok": True, "plik": str(p)})

            if self.path.rstrip("/") == "/przyklad":
                rejestr = rejestr or "rejestr-klient"
                idx = store.upsert_example(
                    rejestr,
                    dane.get("oferta", ""),
                    dane.get("odpowiedz", ""),
                    autor=dane.get("autor", "Ada"),
                    kategoria=dane.get("kategoria", ""),
                    lead_key=dane.get("lead_key", ""),
                )
                return self._json(200, {"ok": True, "id": idx})

            if self.path.rstrip("/") == "/przywroc":
                rejestr = rejestr or "rejestr-klient"
                wynik = store.remove_for_lead(rejestr, dane.get("lead_key", ""))
                return self._json(200, {"ok": True, **wynik})

            if self.path.rstrip("/") == "/zatwierdz":
                rejestr = rejestr or "rejestr-klient"
                plik = store.approve_example(rejestr, int(dane.get("id", 0)))
                return self._json(200, {"ok": True, "plik": str(plik)})

            return self._json(404, {"blad": "nie ma takiego endpointu"})
        except ValueError as e:
            return self._json(400, {"blad": str(e)})
        except Exception as e:  # nie wywalamy serwisu
            return self._json(500, {"blad": f"{type(e).__name__}: {e}"})


def main() -> None:
    host = os.environ.get("HUMANIZER_HOST", "127.0.0.1")
    port = int(os.environ.get("HUMANIZER_PORT", "8011"))
    print(f"humanizer na http://{host}:{port} | dane: {store.styl_dir()} | rejestry: {_rejestry()}", flush=True)
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    main()
