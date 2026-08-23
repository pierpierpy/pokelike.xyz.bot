#!/usr/bin/env python3
"""Rende leggibile il bundle offuscato di pokelike.xyz.

Il bundle è impacchettato da javascript-obfuscator. Tutte le stringhe stanno in
un unico array restituito da una funzione, e ogni uso è una chiamata
`<alias>(0xNNNN)` a un decoder `f(i){ i = i - OFFSET; return array()[i] }`.
L'array viene rimescolato all'avvio da un IIFE in cima al file, quindi la
tabella si può leggere solo eseguendo quel preambolo, cosa che qui facciamo
con Node.

I nomi delle funzioni cambiano a ogni rilascio, quindi vengono ricavati dal file
invece che scritti a mano.

Uso:
    python3 utils/deobfuscate.py site/js/bundle.<hash>.js

Produce, accanto al bundle:
    strings.json      la tabella decodificata
    bundle.deobf.js   il bundle con le chiamate sostituite dai letterali

Richiede `node` nel PATH.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

# function L(U,R){U=U-0x15d;  ->  nome del decoder + offset degli indici
RE_DECODER = re.compile(r"function\s+([A-Za-z_$][\w$]*)\s*\(\s*([A-Za-z_$][\w$]*)\s*,[^)]*\)\s*\{\s*\2\s*=\s*\2\s*-\s*(0x[0-9a-fA-F]+)\s*;")
# ...}(q,0xbd03a));  ->  nome della funzione-array + fine del preambolo
RE_SHUFFLE = re.compile(r"\}\(\s*([A-Za-z_$][\w$]*)\s*,\s*0x[0-9a-fA-F]+\s*\)\s*\)\s*;")


def match_brace(src: str, start: int) -> int:
    """Indice subito dopo la `}` che chiude la `{` in `start`, saltando le stringhe."""
    i, depth, n = start, 0, len(src)
    while i < n:
        c = src[i]
        if c in "'\"`":
            q, i = c, i + 1
            while i < n:
                if src[i] == "\\":
                    i += 2
                    continue
                if src[i] == q:
                    break
                i += 1
            i += 1
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    raise ValueError("parentesi graffe sbilanciate")


def _funzione(src: str, nome: str) -> str:
    """Il testo completo di `function <nome>(...){...}`."""
    m = re.search(r"function\s+" + re.escape(nome) + r"\s*\(", src)
    if not m:
        raise LookupError(f"funzione {nome}() non trovata")
    return src[m.start():match_brace(src, src.index("{", m.end()))]


def decodifica(src: str, dove: Path) -> dict[str, str]:
    """Esegue il preambolo con Node e restituisce la tabella delle stringhe."""
    md = RE_DECODER.search(src)
    if not md:
        raise LookupError("decoder non trovato: lo schema dell'offuscatore è cambiato")
    decoder, offset = md.group(1), int(md.group(3), 16)

    ms = RE_SHUFFLE.search(src)
    if not ms:
        raise LookupError("preambolo di rimescolamento non trovato")
    array_fn, fine_preambolo = ms.group(1), ms.end()

    print(f"  decoder {decoder}(), array {array_fn}(), offset {hex(offset)}")

    script = dove / "_dump.js"
    tabella = dove / "strings.json"
    script.write_text(
        src[:fine_preambolo] + "\n"
        + _funzione(src, decoder) + "\n"
        + _funzione(src, array_fn) + "\n"
        + f"const a = {array_fn}(), out = {{}};\n"
        + f"for (let i = 0; i < a.length; i++) out['0x' + (i + {offset}).toString(16)] = a[i];\n"
        + f"require('fs').writeFileSync({json.dumps(str(tabella))}, JSON.stringify(out));\n",
        encoding="utf-8",
    )
    subprocess.run(["node", str(script)], check=True)
    script.unlink()
    return json.loads(tabella.read_text(encoding="utf-8"))


def sostituisci(src: str, tabella: dict[str, str]) -> tuple[str, int, int]:
    """Rimpiazza ogni `alias(0xNNNN)` con la stringa corrispondente."""
    # Gli alias nascono per assegnazione semplice (`const UBH=L`, `const d9=UBH`,
    # ...): si parte dal decoder e si chiude l'insieme.
    md = RE_DECODER.search(src)
    assert md
    alias = {md.group(1)}
    for _ in range(12):
        prima = len(alias)
        for m in re.finditer(r"(?:const|let|var|,)\s*([A-Za-z_$][\w$]*)\s*=\s*([A-Za-z_$][\w$]*)\s*[;,)]", src):
            if m.group(2) in alias:
                alias.add(m.group(1))
        if len(alias) == prima:
            break

    pattern = re.compile(
        r"\b(" + "|".join(sorted(map(re.escape, alias), key=len, reverse=True)) + r")\((0x[0-9a-fA-F]+)\)"
    )
    mancati = 0

    def rimpiazza(m):
        nonlocal mancati
        chiave = "0x" + m.group(2)[2:].lower()
        if chiave in tabella:
            return json.dumps(tabella[chiave], ensure_ascii=False)
        mancati += 1
        return m.group(0)

    fuori, n = pattern.subn(rimpiazza, src)
    return fuori, n, mancati


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    percorso = Path(sys.argv[1])
    src = percorso.read_text(encoding="utf-8", errors="replace")
    dove = percorso.parent

    try:
        tabella = decodifica(src, dove)
    except LookupError as e:
        print(f"errore: {e}", file=sys.stderr)
        return 1
    print(f"  {len(tabella)} stringhe decodificate -> {dove / 'strings.json'}")

    fuori, n, mancati = sostituisci(src, tabella)
    uscita = dove / "bundle.deobf.js"
    uscita.write_text(fuori, encoding="utf-8")
    print(f"  {n} chiamate sostituite ({mancati} non risolte) -> {uscita}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
