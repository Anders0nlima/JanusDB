import pytest
from src.catalog import Catalogo, ErroSemantico, PAGINA_CATALOGO, TAM_REGISTRO_CATALOGO, MAGIC
from src.storage import PAGE_SIZE, HEADER_SIZE


def test_catalogo_persiste_e_reabre(tmp_path):
    db = str(tmp_path / "banco.db")
    cat = Catalogo(db)
    cat.cria_tabela("aluno", [("id", "INT", 4), ("nome", "CHAR", 20)], 3)
    reaberto = Catalogo(db)
    tabela = reaberto.busca("ALUNO")
    assert tabela.pagina == 3
    assert tabela.colunas[1].tupla() == ("nome", "CHAR", 20)


def test_catalogo_mora_na_pagina_1(tmp_path):
    """Verifica que o catálogo mora fisicamente na página 1 do arquivo .db em registros de 236 bytes."""
    db = str(tmp_path / "banco.db")
    cat = Catalogo(db)
    cat.cria_tabela("aluno", [("id", "INT", 4), ("matricula", "INT", 4), ("nome", "CHAR", 20)], 2)

    with open(db, "rb") as f:
        # Página 1 começa no byte 4096
        f.seek(PAGINA_CATALOGO * PAGE_SIZE)
        header_p1 = f.read(HEADER_SIZE)
        assert header_p1[:4] == MAGIC
        
        # Primeiro registro do catálogo (bytes 4112 a 4348)
        reg = f.read(TAM_REGISTRO_CATALOGO)
        assert len(reg) == 236
        assert reg[:5] == b"aluno"


def test_catalogo_valida_tipos_quantidade_e_colunas(tmp_path):
    cat = Catalogo(str(tmp_path / "banco.db"))
    t = cat.cria_tabela("aluno", [("id", "INT", 4), ("nome", "CHAR", 5)], 0)
    cat.valida_valores(t, [1, "Ana"])
    with pytest.raises(ErroSemantico):
        cat.valida_valores(t, ["Ana", 1])
    with pytest.raises(ErroSemantico):
        cat.valida_valores(t, [1])
    with pytest.raises(ErroSemantico):
        cat.valida_valores(t, [1, "nomes longos"])
    with pytest.raises(ErroSemantico):
        cat.cria_tabela("ALUNO", [("x", "INT", 4)], 1)
    with pytest.raises(ErroSemantico):
        cat.busca_coluna(t, "idade")
