"""Walidator stylu. Deterministyczny: te same reguły dla każdego modelu, koszt zero.

Reguły pochodzą z kart stylu, a liczby w komentarzach to zmierzone wartości z materiału
(73 maile własne, 55 SMS-ów do mamy, 1 196 wiadomości na Messengerze).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

EMOJI = re.compile(r"[\U0001F300-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F]")

AI_FRAZY = [
    "warto podkreślić",
    "warto zaznaczyć",
    "podsumowując",
    "w dzisiejszym",
    "kluczowy element",
    "kluczowym elementem",
    "odgrywa kluczową rolę",
    "w dynamicznie",
    "kompleksow",
    "holistyczn",
    "synergi",
    "innowacyjn",
    "dedykowan",
    "mam nadzieję",
    "mam przyjemność",
]

KLIENT_ZAKAZANE = AI_FRAZY + [
    "chciałbym zapytać",
    "byłbym wdzięczny",
    "z góry dziękuję",
    "liczę na odpowiedź",
    "pozdrawiam serdecznie",
    "z wyrazami szacunku",
    "miłego dnia",
    "w razie pytań",
    "jestem do dyspozycji",
    "szanowni państwo",
    "witam",
    "poniżej przedstawiam",
    "chętnie pomogę",
    "zoptymaliz",
]

BLISCY_ZAKAZANE = [
    "pozdrawiam",
    "z poważaniem",
    "dzień dobry",
    "cześć",
    "hej",
    "witam",
    "miłego dnia",
    "dziękuję za",
    "jak się masz",
]

ZNAJOMI_ZAKAZANE = [
    "pozdrawiam",
    "miłego dnia",
    "jak się masz",
    "z poważaniem",
    "dzień dobry",
    "dziękuję za wiadomość",
]


@dataclass(frozen=True)
class Naruszenie:
    kod: str
    waga: str  # "blad" | "ostrzezenie"
    opis: str

    def __str__(self) -> str:
        return f"[{self.waga}] {self.kod}: {self.opis}"


def zdania(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+|\n+", text.strip()) if s.strip()]


def statystyki(text: str) -> dict:
    s = zdania(text)
    slowa = text.split()
    return {
        "znaki": len(text),
        "zdania": len(s),
        "slowa": len(slowa),
        "srednia_slow_w_zdaniu": round(len(slowa) / len(s), 1) if s else 0.0,
        "znaki_bez_spacji": len(re.sub(r"\s", "", text)),
    }


def _frazy(text: str, lista: list[str], kod: str) -> list[Naruszenie]:
    low = text.lower()
    out = []
    for f in lista:
        if f in low:
            out.append(Naruszenie(kod, "blad", f'fraza zakazana: "{f}"'))
    return out


def validate(text: str, rejestr: str) -> list[Naruszenie]:
    if rejestr not in ("rejestr-klient", "rejestr-bliscy", "rejestr-znajomi", "rejestr-firma"):
        raise ValueError(f"nieznany rejestr: {rejestr}")
    t = text.strip()
    v: list[Naruszenie] = []
    if not t:
        return [Naruszenie("puste", "blad", "brak treści")]

    st = statystyki(t)

    # wspólne: w mailach i do rodziny emoji nie ma wcale; u znajomych 14 na 1257 (1,1%), jako reakcja
    emoji_l = EMOJI.findall(t)
    if emoji_l and rejestr != "rejestr-znajomi":
        v.append(Naruszenie("emoji", "blad", "emoji nie występują w mailach ani w wiadomościach do rodziny (0 na 400 maili, 0 na 55 SMS-ów)"))
    elif len(emoji_l) > 1 and rejestr == "rejestr-znajomi":
        v.append(Naruszenie("emoji", "ostrzezenie", f"{len(emoji_l)} emoji w jednej wiadomości; u ciebie 14 na 1257, zwykle jeden"))
    if re.search(r"[„”]", t):
        v.append(Naruszenie("cudzyslowy", "ostrzezenie", "użyj polskich cudzysłowów „…”"))

    if rejestr in ("rejestr-klient", "rejestr-firma"):
        v += _frazy(t, KLIENT_ZAKAZANE, "fraza")
        if t.count("!") > 1:
            v.append(Naruszenie("wykrzykniki", "blad", f"wykrzyknik {t.count('!')}× — w materiale 3 na 73 maile"))
        if t.count("—") > 1:
            v.append(Naruszenie("em-dash", "ostrzezenie", "więcej niż jeden em-dash; w materiale zawsze jedno wtrącenie"))
        if st["znaki"] > 4000:
            v.append(Naruszenie("dlugosc", "ostrzezenie", f'{st["znaki"]} znaków; mediana twoich maili to 918'))
        if st["zdania"] and st["srednia_slow_w_zdaniu"] > 18:
            v.append(Naruszenie("zdania", "ostrzezenie", f'średnio {st["srednia_slow_w_zdaniu"]} słów na zdanie; mediana to 7'))
        if re.search(r"(?i)\bproszę o (szybką|pilną) odpowiedź\b", t):
            v.append(Naruszenie("nacisk", "blad", "nacisk na odpowiedź, którego nie używasz"))

    elif rejestr == "rejestr-bliscy":
        v += _frazy(t, BLISCY_ZAKAZANE, "fraza")
        if st["zdania"] > 2:
            v.append(Naruszenie("zdania", "blad", f'{st["zdania"]} zdań; do mamy mediana to 9 znaków i jedno zdanie'))
        if st["znaki"] > 200:
            v.append(Naruszenie("dlugosc", "blad", f'{st["znaki"]} znaków; najdłuższy SMS do mamy ma 121'))
        if st["slowa"] > 15:
            v.append(Naruszenie("slowa", "ostrzezenie", f'{st["slowa"]} słów; podziel na dwie wiadomości'))
        if t.endswith("."):
            v.append(Naruszenie("kropka", "ostrzezenie", "89% twoich SMS-ów do mamy nie kończy się kropką"))
        if t[:1].islower():
            v.append(Naruszenie("wielka-litera", "ostrzezenie", "96% twoich wiadomości zaczyna się z wielkiej litery"))

    else:  # rejestr-znajomi
        v += _frazy(t, ZNAJOMI_ZAKAZANE, "fraza")
        if re.search(r"[!?]{2,}", t):
            v.append(Naruszenie("interpunkcja", "blad", "podwójne !!/?? nie występuje w materiale (0 na 1196)"))
        if st["znaki"] > 400:
            v.append(Naruszenie("dlugosc", "ostrzezenie", f'{st["znaki"]} znaków; p90 to 78'))
        if re.search(r"\b(Pan|Pana|Panu|Panie|Panem|Pani|Panią|Państwo|Państwa|Państwu)\b", t):
            v.append(Naruszenie("forma", "blad", "do znajomych nie piszesz na Pan/Pani"))
        if st["zdania"] and st["srednia_slow_w_zdaniu"] > 15:
            v.append(Naruszenie("zdania", "ostrzezenie", "za długie zdania jak na rejestr znajomi"))

    # sygnały typowo modelowe, niezależne od rejestru
    if re.search(r"(?i)\bnie tylko\b.{0,40}\bale (także|też)\b", t):
        v.append(Naruszenie("paralelizm", "ostrzezenie", '"nie tylko… ale także" to wzorzec modelowy'))
    if re.search(r"(?i)^(oczywiście|certainly|jasne, że)", t):
        v.append(Naruszenie("otwarcie", "blad", "otwarcie w stylu asystenta"))
    return v


def czy_ok(naruszenia: list[Naruszenie]) -> bool:
    return not any(n.waga == "blad" for n in naruszenia)
