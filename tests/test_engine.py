import pytest
from src.engine import Engine
from src.catalog import ErroSemantico


def test_fluxo_sql_e_persistencia(tmp_path):
    caminho = str(tmp_path / "banco.db")
    with Engine(caminho) as db:
        assert db.executa("CREATE TABLE aluno (id INT, nome CHAR(20));") == "OK"
        assert db.executa("INSERT INTO aluno VALUES (1, 'Ana');") == "OK 1"
        assert db.executa("INSERT INTO aluno VALUES (2, 'Bruno')") == "OK 1"
        assert db.executa("SELECT * FROM aluno") == "1|Ana\n2|Bruno\n(2 linhas)"
        assert db.executa("SELECT nome FROM aluno WHERE id = 2") == "Bruno\n(1 linhas)"
    with Engine(caminho) as db:
        assert db.executa("SELECT * FROM aluno") == "1|Ana\n2|Bruno\n(2 linhas)"


def test_erros_semanticos_nao_inserem(tmp_path):
    with Engine(str(tmp_path / "banco.db")) as db:
        db.executa("CREATE TABLE aluno (id INT, nome CHAR(4))")
        with pytest.raises(ErroSemantico):
            db.executa("INSERT INTO inexistente VALUES (1, 'Ana')")
        with pytest.raises(ErroSemantico):
            db.executa("INSERT INTO aluno VALUES ('Ana', 1)")
        with pytest.raises(ErroSemantico):
            db.executa("INSERT INTO aluno VALUES (1, 'muito longo')")
        assert db.executa("SELECT * FROM aluno") == "(0 linhas)"


def test_select_coluna_inexistente(tmp_path):
    with Engine(str(tmp_path / "banco.db")) as db:
        db.executa("CREATE TABLE aluno (id INT)")
        with pytest.raises(ErroSemantico):
            db.executa("SELECT idade FROM aluno")
