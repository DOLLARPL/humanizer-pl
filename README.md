# humanizer-pl

A deterministic Polish style checker. It reads a style card (rules plus real examples), inspects a draft against those rules and returns a verdict with numbers. No model sits inside the checker, so the same text gets the same verdict every time, at zero cost.

I built it because "write like me" prompts drift. A model given the same instruction twice produces two different voices, and neither can be measured. Rules can be measured.

## What it does

- **Rules per register.** A business email to a client, a message to family and a LinkedIn post are different jobs. Each register has its own card with banned phrases, sentence-length limits, dash and emoji policy, and the openers that make a text sound machine-written.
- **Banned-phrase detection.** AI clichés in Polish (`warto podkreślić`, `kluczowy element`, `kompleksowe rozwiązanie`, `mam przyjemność`), plus register-specific bans: `chciałbym zapytać`, `z góry dziękuję`, `szanowni państwo` for client mail, `pozdrawiam` for close contacts.
- **Measurements, not adjectives.** Each rule carries the number it was calibrated against: 73 emails, 55 SMS messages and 1,196 Messenger conversations written by the same person. The card says "average sentence 11 words, 8% of sentences over 20" because that is what the material shows.
- **Context builder.** It assembles the prompt for whichever model the caller uses: style card, closest examples, the task. The checker never calls a model, so swapping the model does not change the rules.
- **Correction loop.** When a draft is rejected, the pair (draft, corrected version) is appended to the card as a new example. The rules stay, the examples accumulate.

## Layout

```
src/humanizer/store.py       reads style cards and examples, builds prompts, appends corrections
src/humanizer/validator.py   the rules, grouped by register
src/humanizer/server.py      HTTP service on 127.0.0.1:8011 (standard library only)
src/humanizer/cli.py         rejestry | sprawdz | kontekst | zapisz | pending
tests/test_all.py            test suite, runs without pytest
```

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/zdrowie` | status, registers, example counts |
| POST | `/sprawdz` | `{rejestr, tekst}` → violations and statistics |
| POST | `/kontekst` | `{rejestr, zadanie, kto, n, uwagi}` → ready prompt |
| POST | `/zapisz` | `{rejestr, draft, moja, uwagi}` → append a correction pair |
| POST | `/przyklad`, `/przywroc`, `/zatwierdz` | example lifecycle |

## Running it

```bash
export HUMANIZER_STYL_DIR=/path/to/style-cards   # default: the vault directory
PYTHONPATH=src python3 -m humanizer.cli rejestry
PYTHONPATH=src python3 -m humanizer.cli sprawdz --rejestr rejestr-klient --plik draft.txt
PYTHONPATH=src python3 -m humanizer.server        # 127.0.0.1:8011
python3 tests/test_all.py
```

No dependencies. Python 3.11 or newer. The service runs as a systemd unit with `Restart=always`.

## Scope and limits

The rules are Polish-specific: inflection, honorifics and the register conventions of Polish business writing. The style cards are data, not code, so the engine works for any language once a card exists. The examples in this repository are synthetic; the real cards stay in a private vault.

## Contact

Jan Noga, [jnxautomation.pl](https://jnxautomation.pl), jannoga@jnxautomation.pl

MIT licence, see [LICENSE](LICENSE).
