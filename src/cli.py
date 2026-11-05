"""REPL e executor SQL do JanusDB (M4)."""
import sys

from .catalog import ErroSemantico
from .engine import Engine
from .parser import ErroSintatico
from .tokenizer import ErroLexico


def main(argv=None):
    if argv is None:
        argv = sys.argv
    if len(argv) != 2:
        print("Uso: minidb caminho.db", file=sys.stderr)
        return 2

    caminho_db = argv[1]
    is_interactive = sys.stdin.isatty()

    try:
        with Engine(caminho_db) as banco:
            if is_interactive:
                while True:
                    try:
                        sql = input("janusdb> ")
                    except EOFError:
                        break
                    if not sql.strip():
                        continue
                    try:
                        print(banco.executa(sql))
                    except (ErroLexico, ErroSintatico, ErroSemantico, ValueError) as exc:
                        print(f"erro: {exc}", file=sys.stderr)
            else:
                for linha in sys.stdin:
                    linha = linha.strip()
                    if not linha:
                        continue
                    # Ignora comentários SQL (-- ...)
                    if linha.startswith("--"):
                        continue
                    if "--" in linha:
                        linha = linha.split("--", 1)[0].strip()
                        if not linha:
                            continue
                    try:
                        print(banco.executa(linha))
                    except (ErroLexico, ErroSintatico, ErroSemantico, ValueError) as exc:
                        print(f"erro: {exc}", file=sys.stderr)
    except OSError as exc:
        print(f"erro de I/O: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
