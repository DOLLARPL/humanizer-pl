"""CLI: styl sprawdz | styl kontekst | styl zapisz | styl rejestry"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import store, validator


def _tekst(args) -> str:
    if args.plik:
        return Path(args.plik).read_text(encoding="utf-8")
    if args.tekst:
        return args.tekst
    return sys.stdin.read()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="styl", description="Humanizer Jana: walidator i kontekst")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("sprawdz", help="sprawdź tekst regułami rejestru")
    s.add_argument("--rejestr", required=True)
    s.add_argument("--plik")
    s.add_argument("--tekst")

    k = sub.add_parser("kontekst", help="zbuduj prompt z karty i przykładów")
    k.add_argument("--rejestr", required=True)
    k.add_argument("--zadanie", default="")
    k.add_argument("--kto", default="")
    k.add_argument("--uwagi", default="")
    k.add_argument("--n", type=int, default=8)

    z = sub.add_parser("zapisz", help="dopisz parę draft → moja do poprawki.md")
    z.add_argument("--rejestr", default="")
    z.add_argument("--draft", default="")
    z.add_argument("--moja", required=True)
    z.add_argument("--uwagi", default="")
    z.add_argument("--pending", action="store_true", help="sparuj z ostatnio wysłanym draftem")

    pd = sub.add_parser("pending", help="zapamiętaj draft wysłany Janowi")
    pd.add_argument("--rejestr", required=True)
    pd.add_argument("--draft", required=True, help="plik z draftem")
    pd.add_argument("--zadanie", default="")
    pd.add_argument("--kto", default="")

    sub.add_parser("rejestry", help="lista rejestrów i liczba przykładów")

    args = ap.parse_args(argv)

    if args.cmd == "rejestry":
        for r in store.registers():
            print(f"{r:20s} {len(store.examples(r)):4d} przykładów")
        return 0

    if args.cmd == "sprawdz":
        t = _tekst(args)
        n = validator.validate(t, args.rejestr)
        st = validator.statystyki(t.strip())
        print("OK" if validator.czy_ok(n) else "NIE PRZECHODZI", "|", st)
        for x in n:
            print(" ", x)
        return 0 if validator.czy_ok(n) else 1

    if args.cmd == "kontekst":
        ctx = store.kontekst(args.rejestr, args.zadanie, args.kto, args.n, args.uwagi)
        print(ctx.prompt(args.zadanie, args.kto, args.uwagi))
        return 0

    if args.cmd == "pending":
        p = store.start_pending(args.rejestr, Path(args.draft).read_text(encoding="utf-8"),
                                args.zadanie, args.kto)
        print(f"zapamiętane: {p}")
        return 0

    if args.cmd == "zapisz":
        moja = Path(args.moja).read_text(encoding="utf-8")
        if args.pending:
            p = store.save_pending(moja, args.uwagi)
        else:
            if not args.rejestr or not args.draft:
                print("bez --pending podaj --rejestr i --draft", file=sys.stderr)
                return 2
            p = store.append_correction(args.rejestr, Path(args.draft).read_text(encoding="utf-8"), moja, args.uwagi)
        print(f"zapisane: {p}")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
