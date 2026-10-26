import pytest
from src.catalog import Catalogo, ErroSemantico


def test_catalogo_persiste_e_reabre(tmp_path):
    db = str(tmp_path / "banco.db")
    cat = Catalogo(db)
    cat.cria_tabela("aluno", [("id", "INT", 4), ("nome", "CHAR", 20)], 3)
    reaberto = Catalogo(db)
    tabela = reaberto.busca("ALUNO")
    assert tabela.pagina == 3
    assert tabela.colunas[1].tupla() == ("nome", "CHAR", 20)


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
