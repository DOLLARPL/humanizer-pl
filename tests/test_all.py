"""Testy bez pytest: python3 tests/test_all.py (albo pytest)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("HUMANIZER_STYL_DIR", "/opt/data/home/Dom/01-JNX/projekty/styl-jana")

from humanizer import store, validator  # noqa: E402

FAIL = []


def check(name, warunek, info=""):
    if warunek:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name} {info}")
        FAIL.append(name)


def kody(t, r):
    return {n.kod for n in validator.validate(t, r)}


print("walidator: rejestr klient")
check("AI-fraza 'kompleksowe rozwiązania'", "fraza" in kody("Oferuję kompleksowe rozwiązania dla Państwa firmy.", "rejestr-klient"))
check("'Mam nadzieję, że'", "fraza" in kody("Mam nadzieję, że u Pana wszystko dobrze.", "rejestr-klient"))
check("'Szanowni Państwo'", "fraza" in kody("Szanowni Państwo, proszę o wycenę.", "rejestr-klient"))
check("emoji", "emoji" in kody("Dzień dobry, wysyłam ofertę 🚀", "rejestr-klient"))
check("dwa wykrzykniki", "wykrzykniki" in kody("Dziękuję!! To super!", "rejestr-klient"))
check("poprawny mail przechodzi bez błędów", validator.czy_ok(validator.validate(
    "Dzień dobry,\n\nprośba o dodanie rekordu DNS:\n\nType: A\nName: panel\n\nPo dodaniu proszę o potwierdzenie — wystawiam certyfikat.\n\nPozdrawiam,\nJan",
    "rejestr-klient")))

print("walidator: rejestr bliscy")
check("'Cześć Mamo' zakazane", "fraza" in kody("Cześć Mamo, jak się masz?", "rejestr-bliscy"))
check("trzy zdania to błąd", "zdania" in kody("Dojechałem. Wszystko ok. Zadzwonię później.", "rejestr-bliscy"))
check("za długie", "dlugosc" in kody("x" * 250, "rejestr-bliscy"))
check("'Dojechałem' przechodzi", validator.czy_ok(validator.validate("Dojechałem", "rejestr-bliscy")))

print("walidator: rejestr znajomi")
check("jedno emoji przechodzi (14 na 1257 w materiale)", validator.czy_ok(validator.validate("siema 😎", "rejestr-znajomi")))
check("dwa emoji to ostrzeżenie", "emoji" in kody("siema 😎😎", "rejestr-znajomi"))
check("emoji w mailu to błąd", "emoji" in kody("Dzień dobry, oferta 😀", "rejestr-klient"))
check("Pan/Pani zakazane", "forma" in kody("Panie Marku, idziesz?", "rejestr-znajomi"))
check("'Co tam' przechodzi", validator.czy_ok(validator.validate("Co tam", "rejestr-znajomi")))
check("XD przechodzi", validator.czy_ok(validator.validate("Na murku przy flankach XD", "rejestr-znajomi")))

print("store: dane")
regs = store.registers()
check("cztery rejestry", set(regs) == {"rejestr-bliscy", "rejestr-klient", "rejestr-znajomi", "rejestr-firma"}, regs)
for r in regs:
    check(f"{r}: karta niepusta", len(store.karta(r)) > 500, len(store.karta(r)))
    ex = store.examples(r)
    # rejestr-firma otwarty 30.10.2026, zbiera pary od Ady; usun wyjatek, gdy ma 10+ przykladow
    if r == "rejestr-firma" and len(ex) < 10:
        check(f"{r}: rejestr w budowie, progi przykladów pominięte", True, len(ex))
        continue
    check(f"{r}: przykłady >= 10", len(ex) >= 10, len(ex))
    ctx = store.kontekst(r, zadanie="prośba o dodanie rekordu DNS", n=8)
    p = ctx.prompt("prośba o dodanie rekordu DNS", "klient")
    check(f"{r}: prompt zawiera kartę i przykłady", "Karta stylu" in p and "przykład 1" in p, len(p))

print("store: poprawki")
before = (store.styl_dir() / "poprawki.md").read_text(encoding="utf-8") if (store.styl_dir() / "poprawki.md").exists() else ""
p = store.append_correction("rejestr-znajomi", "Dzień dobry, chciałbym zapytać o spotkanie.", "siema, co tam", "test")
after = p.read_text(encoding="utf-8")
check("para dopisana", "DRAFT (agent):" in after and "MOJE (Jan):" in after)
# sprzątanie wpisu testowego
p.write_text(before, encoding="utf-8")

print("store: pending (para z draftu wysłanego Janowi)")
before = (store.styl_dir() / "poprawki.md").read_text(encoding="utf-8") if (store.styl_dir() / "poprawki.md").exists() else ""
pend_file = store.styl_dir() / ".pending.json"
pend_before = pend_file.read_text(encoding="utf-8") if pend_file.exists() else None
store.start_pending("rejestr-bliscy", "Cześć Mamo, dotarłem na miejsce.", "mama pyta czy dojechałem")
p = store.pending()
check("pending zapisany", p and p["rejestr"] == "rejestr-bliscy", p)
store.save_pending("Dojechałem")
after = (store.styl_dir() / "poprawki.md").read_text(encoding="utf-8")
check("para z pending trafiła do poprawek", "Dojechałem" in after and "dotarłem na miejsce" in after)
try:
    store.save_pending("drugi raz")
    check("drugi zapis pending odrzucony", False)
except ValueError:
    check("drugi zapis pending odrzucony", True)
# sprzątanie
(store.styl_dir() / "poprawki.md").write_text(before, encoding="utf-8")
if pend_before is None:
    pend_file.unlink(missing_ok=True)
else:
    pend_file.write_text(pend_before, encoding="utf-8")

print()
if FAIL:
    print(f"NIEPOWODZENIA: {len(FAIL)} -> {FAIL}")
    raise SystemExit(1)
print("wszystkie testy przeszły")
