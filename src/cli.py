"""REPL simples: python -m src.cli dados.db"""
import sys
from .catalog import ErroSemantico
from .parser import ErroSintatico
from .tokenizer import ErroLexico
from .engine import Engine


def main():
    if len(sys.argv) != 2:
        print("Uso: python -m src.cli caminho.db", file=sys.stderr)
        return 2
    try:
        with Engine(sys.argv[1]) as banco:
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
    except OSError as exc:
        print(f"erro de I/O: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
