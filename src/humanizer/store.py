"""Wczytywanie kart stylu i przykładów z katalogu danych.

Dane to pliki markdown w vaultcie. Ten moduł nie zapisuje niczego poza poprawki.md.
Katalog można nadpisać zmienną HUMANIZER_STYL_DIR.
"""
from __future__ import annotations

import json
import os
import random
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DIR = "/opt/data/home/Dom/01-JNX/projekty/styl-jana"
STOP = set(
    """a i o u w z na do nie to sie się jest sa są jak co czy ze że by mi ty ja my wy on ona
    ale lub oraz dla przy pod nad po za przed przez bez tak nie juz już tylko tez też
    prosze proszę bardzo ten ta te tego tej tym which the and for with you are was""".split()
)


def styl_dir() -> Path:
    return Path(os.environ.get("HUMANIZER_STYL_DIR", DEFAULT_DIR))


def registers() -> list[str]:
    root = styl_dir()
    if not root.is_dir():
        return []
    return sorted(p.name for p in root.iterdir() if p.is_dir() and p.name.startswith("rejestr-"))


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def karta(rejestr: str) -> str:
    return _read(styl_dir() / rejestr / "karta.md")


def _blocks(md: str) -> list[str]:
    """Wyciąga przykłady: bloki ```text ... ``` albo linie listy '- ...'."""
    out = [b.strip() for b in re.findall(r"```text\n(.*?)```", md, re.S)]
    poza_blokami = re.sub(r"```.*?```", "", md, flags=re.S)
    for line in poza_blokami.splitlines():
        s = line.strip()
        if s.startswith("- ") and len(s) > 3:
            out.append(s[2:].strip())
    return [b for b in out if b]


def examples(rejestr: str) -> list[str]:
    return _blocks(_read(styl_dir() / rejestr / "przyklady.md"))


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-ząćęłńóśźż0-9]{4,}", text.lower())
    return {w for w in words if w not in STOP}


def pick(rejestr: str, zadanie: str = "", n: int = 8) -> list[str]:
    """Wybiera n przykładów: najtrafniejsze tematycznie + 2 najkrótsze jako wzorzec rytmu."""
    pool = examples(rejestr)
    if not pool:
        return []
    if not zadanie:
        random.seed(0)
        return random.sample(pool, min(n, len(pool)))
    want = _tokens(zadanie)
    scored = sorted(
        pool,
        key=lambda e: (-len(want & _tokens(e)), len(e)),
    )
    picked = scored[: max(0, n - 2)]
    short = sorted(pool, key=len)[:2]
    seen, out = set(), []
    for e in picked + short:
        if e not in seen:
            seen.add(e)
            out.append(e)
    return out[:n]


@dataclass(frozen=True)
class Kontekst:
    rejestr: str
    karta: str
    przyklady: list[str]

    def prompt(self, zadanie: str, kto: str = "", uwagi: str = "") -> str:
        przyklady = "\n\n".join(f"--- przykład {i + 1} ---\n{e}" for i, e in enumerate(self.przyklady))
        czesci = [
            "Piszesz wiadomość, której nadawcą jest Jan Noga. Nie jesteś asystentem, jesteś nim.",
            f"Rejestr: {self.rejestr}.",
            "",
            "## Karta stylu (obowiązkowa)",
            self.karta.strip(),
            "",
            "## Przykłady jego własnych wiadomości w tym rejestrze",
            "To wzorzec rytmu i długości. Przy sprzeczności z kartą wygrywają przykłady.",
            przyklady,
            "",
            "## Zadanie",
            f"Do kogo: {kto}" if kto else "",
            f"O co chodzi: {zadanie}",
        ]
        if uwagi:
            czesci += ["", f"Uwagi: {uwagi}"]
        czesci += [
            "",
            "Zwróć wyłącznie treść wiadomości, bez komentarza i bez nagłówków.",
        ]
        return "\n".join(c for c in czesci if c is not None).strip()


def kontekst(rejestr: str, zadanie: str = "", kto: str = "", n: int = 8, uwagi: str = "") -> Kontekst:
    if rejestr not in registers():
        raise ValueError(f"nieznany rejestr: {rejestr}; dostępne: {', '.join(registers())}")
    return Kontekst(rejestr=rejestr, karta=karta(rejestr), przyklady=pick(rejestr, zadanie, n))


PENDING_NAME = ".pending.json"


def start_pending(rejestr: str, draft: str, zadanie: str = "", kto: str = "") -> Path:
    """Zapamiętuje draft wysłany Janowi, żeby jego odpowiedź dała się sparować."""
    if rejestr not in registers():
        raise ValueError(f"nieznany rejestr: {rejestr}")
    if not draft.strip():
        raise ValueError("pusty draft")
    path = styl_dir() / PENDING_NAME
    path.write_text(
        json.dumps(
            {
                "rejestr": rejestr,
                "draft": draft.strip(),
                "zadanie": zadanie,
                "kto": kto,
                "kiedy": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
                "uzyty": False,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def pending() -> dict | None:
    path = styl_dir() / PENDING_NAME
    if not path.exists():
        return None
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None
    return d if isinstance(d, dict) and d.get("draft") else None


def save_pending(moja: str, uwagi: str = "") -> Path:
    """Zapisuje poprawkę do ostatniego draftu i oznacza go jako wykorzystany."""
    p = pending()
    if not p:
        raise ValueError("brak zapamiętanego draftu; użyj --draft albo najpierw /pending")
    if p.get("uzyty"):
        raise ValueError("ten draft został już zapisany jako poprawka")
    path = append_correction(p["rejestr"], p["draft"], moja, uwagi or f'zadanie: {p.get("zadanie", "")}'.strip())
    p["uzyty"] = True
    (styl_dir() / PENDING_NAME).write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def append_correction(rejestr: str, draft: str, moja: str, uwagi: str = "") -> Path:
    """Zapisuje parę draft -> wersja Jana. Jedyne źródło wiedzy o tym, co agent robi źle."""
    if not draft.strip() or not moja.strip():
        raise ValueError("draft i moja muszą być niepuste")
    path = styl_dir() / "poprawki.md"
    now = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M")
    blok = [
        f"## {now} · {rejestr}",
        f"uwagi: {uwagi}" if uwagi else "",
        "",
        "DRAFT (agent):",
        "```text",
        draft.strip(),
        "```",
        "",
        "MOJE (Jan):",
        "```text",
        moja.strip(),
        "```",
        "",
    ]
    if not path.exists():
        path.write_text("# Poprawki — pary draft → wersja Jana\n\n", encoding="utf-8")
    with path.open("a", encoding="utf-8") as f:
        f.write("\n".join(b for b in blok if b is not None) + "\n")
    return path

# --- przykłady Ady: warsztat i zatwierdzanie --------------------------------

EXAMPLE_NAME = "przyklady-ada.md"


def _example_path(rejestr: str) -> Path:
    return styl_dir() / rejestr / EXAMPLE_NAME


def _example_sections(md: str) -> list[dict]:
    """Parsuje plik warsztatu Ady na sekcje. Format jest stały, patrz append_example."""
    out: list[dict] = []
    for part in re.split(r"(?m)^## ", md)[1:]:
        lines = part.splitlines()
        head = lines[0].strip() if lines else ""
        body = "\n".join(lines[1:])
        m = re.match(r"(\d+)\s*[·\-]\s*(.*)$", head)
        idx = int(m.group(1)) if m else len(out) + 1
        title = (m.group(2) if m else head).strip()
        meta: dict[str, str] = {}
        mm = re.search(r"(?m)^data:\s*(.+)$", body)
        if mm:
            czesci = [c.strip() for c in mm.group(1).split("·")]
            if czesci:
                meta["data"] = czesci[0]
            for czesc in czesci[1:]:
                if ":" in czesc:
                    k, v = czesc.split(":", 1)
                    meta[k.strip()] = v.strip()
        mo = re.search(r"(?m)^oferta:\s*(.+)$", body)
        bloki = re.findall(r"```text\n(.*?)```", body, re.S)
        out.append(
            {
                "id": idx,
                "title": title,
                "meta": meta,
                "oferta": mo.group(1).strip() if mo else "",
                "odpowiedz": bloki[-1].strip() if bloki else "",
                "status": meta.get("status", "robocza"),
            }
        )
    return out


def examples_ada(rejestr: str) -> list[dict]:
    p = _example_path(rejestr)
    if not p.is_file():
        return []
    return _example_sections(p.read_text(encoding="utf-8"))


def append_example(
    rejestr: str,
    oferta: str,
    odpowiedz: str,
    autor: str = "Ada",
    kategoria: str = "",
    lead_key: str = "",
) -> int:
    """Dopisuje roboczy przykład Ady. Nie wchodzi do promptów, dopóki nie zatwierdzony."""
    if rejestr not in registers():
        raise ValueError(f"nieznany rejestr: {rejestr}")
    odpowiedz = (odpowiedz or "").strip()
    if not odpowiedz:
        raise ValueError("pusta odpowiedź")
    oferta = (oferta or "").strip()
    path = _example_path(rejestr)
    istniejace = examples_ada(rejestr)
    idx = max((e["id"] for e in istniejace), default=0) + 1
    now = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M")
    meta = (
        f"data: {now} · autor: {autor or 'Ada'} · kategoria: {kategoria or 'brak'} · "
        f"lead: {lead_key or 'brak'} · status: robocza"
    )
    blok = "\n".join(
        [
            f"## {idx} · {oferta[:80] or 'Przykład'}",
            meta,
            "",
            f"oferta: {oferta[:600]}",
            "odpowiedź:",
            "```text",
            odpowiedz,
            "```",
            "",
        ]
    )
    if path.is_file():
        tekst = path.read_text(encoding="utf-8").rstrip() + "\n\n" + blok
    else:
        tekst = (
            "# Przykłady Ady — rejestr klient\n\n"
            "Robocze odpowiedzi na oferty. Do promptów wchodzą dopiero po zatwierdzeniu.\n\n" + blok
        )
    path.write_text(tekst, encoding="utf-8")
    return idx


def approve_example(rejestr: str, idx: int) -> Path:
    """Przenosi zatwierdzony przykład do przyklady.md, czyli do puli promptu."""
    if rejestr not in registers():
        raise ValueError(f"nieznany rejestr: {rejestr}")
    path = _example_path(rejestr)
    if not path.is_file():
        raise ValueError("brak pliku przykładów Ady")
    tekst = path.read_text(encoding="utf-8")
    wzor = re.compile(rf"(?ms)^## {idx} · .*?(?=^## |\Z)")
    m = wzor.search(tekst)
    if not m:
        raise ValueError(f"nie ma przykładu {idx}")
    sekcja = m.group(0)
    if "status: zatwierdzona" in sekcja:
        raise ValueError(f"przykład {idx} już zatwierdzony")
    bloki = re.findall(r"```text\n(.*?)```", sekcja, re.S)
    if not bloki:
        raise ValueError(f"przykład {idx} nie ma treści")
    odpowiedz = bloki[-1].strip()
    tytul = re.match(r"## \d+ · (.*)", sekcja.splitlines()[0])
    tytul = (tytul.group(1) if tytul else "Przykład").strip()
    meta_m = re.search(r"(?m)^data:\s*(.+)$", sekcja)
    meta = (meta_m.group(1) if meta_m else "").replace("status: robocza", "status: wzorcowa").strip()
    if meta and not meta.startswith("data:"):
        meta = "data: " + meta
    pula = styl_dir() / rejestr / "przyklady.md"
    pula_tekst = pula.read_text(encoding="utf-8") if pula.is_file() else "# Przykłady\n"
    numery = [int(n) for n in re.findall(r"(?m)^## (\d+)\.", pula_tekst)]
    numer = max(numery, default=0) + 1
    now = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M")
    nowy = "\n".join(
        [
            f"## {numer}. {tytul}",
            f"{meta} · dodano: {now}",
            "",
            "```text",
            odpowiedz,
            "```",
            "",
        ]
    )
    pula.write_text(pula_tekst.rstrip() + "\n\n" + nowy, encoding="utf-8")
    path.write_text(
        tekst.replace(sekcja, sekcja.replace("status: robocza", f"status: zatwierdzona {now}")),
        encoding="utf-8",
    )
    return pula

def _example_block(idx: int, oferta: str, odpowiedz: str, autor: str, kategoria: str,
                   lead_key: str, now: str) -> str:
    meta = (
        f"data: {now} · autor: {autor or 'Ada'} · kategoria: {kategoria or 'brak'} · "
        f"lead: {lead_key or 'brak'} · status: robocza"
    )
    return "\n".join(
        [
            f"## {idx} · {oferta[:80] or 'Przykład'}",
            meta,
            "",
            f"oferta: {oferta[:600]}",
            "odpowiedź:",
            "```text",
            odpowiedz,
            "```",
            "",
        ]
    )


def replace_example(
    rejestr: str,
    idx: int,
    oferta: str,
    odpowiedz: str,
    autor: str = "Ada",
    kategoria: str = "",
    lead_key: str = "",
) -> int:
    """Nadpisuje istniejący roboczy przykład; status wraca na robocza (do ponownego zatwierdzenia)."""
    path = _example_path(rejestr)
    tekst = path.read_text(encoding="utf-8")
    wzor = re.compile(rf"(?ms)^## {idx} · .*?(?=^## |\Z)")
    m = wzor.search(tekst)
    if not m:
        raise ValueError(f"nie ma przykładu {idx}")
    now = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M")
    blok = _example_block(idx, oferta, odpowiedz, autor, kategoria, lead_key, now)
    path.write_text(tekst[: m.start()] + blok + tekst[m.end() :], encoding="utf-8")
    return idx


def upsert_example(
    rejestr: str,
    oferta: str,
    odpowiedz: str,
    autor: str = "Ada",
    kategoria: str = "",
    lead_key: str = "",
) -> int:
    """Jeden przykład na ofertę: ponowny zapis nadpisuje, nie dubluje."""
    if lead_key:
        for e in examples_ada(rejestr):
            if e["meta"].get("lead") == lead_key:
                return replace_example(rejestr, e["id"], oferta, odpowiedz, autor, kategoria, lead_key)
    return append_example(rejestr, oferta, odpowiedz, autor, kategoria, lead_key)

def _sekcja_ma_lead(sekcja: str, lead_key: str) -> bool:
    m = re.search(r"(?m)^data:\s*(.+)$", sekcja)
    if not m:
        return False
    return any(cz.strip() == f"lead: {lead_key}" for cz in m.group(1).split("·"))


def remove_example(rejestr: str, idx: int) -> None:
    path = _example_path(rejestr)
    tekst = path.read_text(encoding="utf-8")
    wzor = re.compile(rf"(?ms)^## {idx} · .*?(?=^## |\Z)")
    m = wzor.search(tekst)
    if not m:
        raise ValueError(f"nie ma przykładu {idx}")
    path.write_text(tekst[: m.start()] + tekst[m.end() :], encoding="utf-8")


def remove_pool_by_lead(rejestr: str, lead_key: str) -> int:
    """Usuwa z puli promptu wpisy dla tej oferty (jeśli były zatwierdzone)."""
    if not lead_key:
        return 0
    pula = styl_dir() / rejestr / "przyklady.md"
    if not pula.is_file():
        return 0
    tekst = pula.read_text(encoding="utf-8")
    czesci = re.split(r"(?m)^## ", tekst)
    zachowane = [czesci[0]]
    usuniete = 0
    for czesc in czesci[1:]:
        if _sekcja_ma_lead(czesc, lead_key):
            usuniete += 1
        else:
            zachowane.append("## " + czesc)
    if usuniete:
        pula.write_text("".join(zachowane), encoding="utf-8")
    return usuniete


def remove_for_lead(rejestr: str, lead_key: str) -> dict:
    """Przywraca ofertę do zadań: kasuje wpis warsztatu i kopię w puli."""
    idx = None
    for e in examples_ada(rejestr):
        if e["meta"].get("lead") == lead_key:
            idx = e["id"]
            break
    if idx is not None:
        remove_example(rejestr, idx)
    return {"id": idx, "pula": remove_pool_by_lead(rejestr, lead_key)}
