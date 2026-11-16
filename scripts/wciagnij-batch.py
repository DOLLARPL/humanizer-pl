"""Wciaga pary draft -> wersja Jana z pliku batchu do /zapisz (poprawki.md)."""
from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path

API = "http://127.0.0.1:8011/zapisz"


def blocks_after(md: str, marker: str) -> list[str]:
    """Zwraca zawartosc pierwszego bloku ```text po kazdym wystapieniu markera."""
    out = []
    for m in re.finditer(re.escape(marker), md):
        rest = md[m.end():]
        b = re.search(r"```text\n(.*?)```", rest, re.S)
        out.append(b.group(1).strip() if b else "")
    return out


def main(path: str, rejestr: str, tylko: list[int] | None = None, dry: bool = False) -> None:
    md = Path(path).read_text(encoding="utf-8")
    # dziel na sekcje "## N."
    parts = re.split(r"^## (\d+)\..*?$", md, flags=re.M)
    # parts[0] to naglowek, potem pary (numer, tresc)
    pairs = []
    for i in range(1, len(parts), 2):
        nr = int(parts[i])
        body = parts[i + 1]
        if tylko and nr not in tylko:
            continue
        draft = blocks_after(body, "DRAFT:")
        moja = blocks_after(body, "TWOJA WERSJA:")
        d = draft[0] if draft else ""
        m = moja[0] if moja else ""
        dl = blocks_after(body, "DLACZEGO:")
        dl_t = dl[0] if dl else ""
        if not d.strip() or not m.strip():
            print(f"  {nr}. pomijam (draft {len(d)} zn, moja {len(m)} zn)")
            continue
        pairs.append((nr, d, m, dl_t))

    print(f"par do zapisania: {len(pairs)}")
    for nr, d, m, dl_t in pairs:
        opis = f", dlaczego {len(dl_t)} zn" if dl_t else ", bez dlaczego"
        print(f"  {nr}. draft {len(d)} zn -> moja {len(m)} zn ({len(m)-len(d):+d}){opis}")
    if dry:
        return

    tag = Path(path).stem
    payload_pairs = []
    for nr, d, m, dl_t in pairs:
        uwagi = f"{tag}, sytuacja {nr}"
        if dl_t:
            uwagi += f" | dlaczego: {dl_t}"
        payload_pairs.append({"rejestr": rejestr, "draft": d, "moja": m, "uwagi": uwagi})
    for p in payload_pairs:
        req = urllib.request.Request(
            API, data=json.dumps(p, ensure_ascii=False).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as r:
            print("  zapis:", r.status, r.read().decode()[:120])


if __name__ == "__main__":
    p = sys.argv[1]
    rej = sys.argv[2] if len(sys.argv) > 2 else "rejestr-klient"
    dry = "--dry" in sys.argv
    nums = [int(x) for x in sys.argv[3:] if x.isdigit()] or None
    main(p, rej, nums, dry)
