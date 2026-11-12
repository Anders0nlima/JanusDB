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
        assert db.executa("SELECT nome FROM aluno WHERE id = 2") == "Bruno\n(1 linha)"
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


def test_select_tabela_vazia(tmp_path):
    with Engine(str(tmp_path / "banco.db")) as db:
        db.executa("CREATE TABLE aluno (id INT, nome CHAR(10))")
        assert db.executa("SELECT * FROM aluno") == "(0 linhas)"
        assert db.executa("SELECT nome FROM aluno") == "(0 linhas)"


def test_select_projecao_ordem_das_colunas(tmp_path):
    with Engine(str(tmp_path / "banco.db")) as db:
        db.executa("CREATE TABLE aluno (id INT, nome CHAR(10))")
        db.executa("INSERT INTO aluno VALUES (1, 'Ana')")
        db.executa("INSERT INTO aluno VALUES (2, 'Bruno')")
        # Invertendo a ordem das colunas na projeção
        assert db.executa("SELECT nome, id FROM aluno") == "Ana|1\nBruno|2\n(2 linhas)"


def test_select_filtro_where_string(tmp_path):
    with Engine(str(tmp_path / "banco.db")) as db:
        db.executa("CREATE TABLE aluno (id INT, nome CHAR(10))")
        db.executa("INSERT INTO aluno VALUES (1, 'Ana')")
        db.executa("INSERT INTO aluno VALUES (2, 'Bruno')")
        assert db.executa("SELECT id FROM aluno WHERE nome = 'Bruno'") == "2\n(1 linha)"


def test_select_where_sem_correspondencia(tmp_path):
    with Engine(str(tmp_path / "banco.db")) as db:
        db.executa("CREATE TABLE aluno (id INT, nome CHAR(10))")
        db.executa("INSERT INTO aluno VALUES (1, 'Ana')")
        assert db.executa("SELECT * FROM aluno WHERE id = 999") == "(0 linhas)"


def test_tabela_multiplas_paginas_insere_e_seleciona(tmp_path):
    caminho = str(tmp_path / "banco_multi.db")
    with Engine(caminho) as db:
        # Registro: INT (4) + CHAR(24) = 28 bytes. Capacidade por página = 4080 // 28 = 145 linhas.
        db.executa("CREATE TABLE aluno (id INT, nome CHAR(24))")
        # Inserindo 200 linhas (vai preencher a página 1 com 145 e criar a página 2 com 55)
        for i in range(1, 201):
            assert db.executa(f"INSERT INTO aluno VALUES ({i}, 'Aluno_{i}')") == "OK 1"

        resultado = db.executa("SELECT * FROM aluno")
        assert resultado.endswith("(200 linhas)")

        # Testa busca por WHERE na primeira página
        assert db.executa("SELECT nome FROM aluno WHERE id = 1") == "Aluno_1\n(1 linha)"
        assert db.executa("SELECT nome FROM aluno WHERE id = 145") == "Aluno_145\n(1 linha)"

        # Testa busca por WHERE na segunda página
        assert db.executa("SELECT nome FROM aluno WHERE id = 146") == "Aluno_146\n(1 linha)"
        assert db.executa("SELECT nome FROM aluno WHERE id = 200") == "Aluno_200\n(1 linha)"

    # Testa persistência ao reabrir o banco
    with Engine(caminho) as db:
        resultado = db.executa("SELECT * FROM aluno")
        assert resultado.endswith("(200 linhas)")
        assert db.executa("SELECT nome FROM aluno WHERE id = 150") == "Aluno_150\n(1 linha)"


def test_pin_count_zerado_apos_consulta_e_erros(tmp_path):
    caminho = str(tmp_path / "banco_pin.db")
    with Engine(caminho) as db:
        db.executa("CREATE TABLE aluno (id INT, nome CHAR(10))")
        db.executa("INSERT INTO aluno VALUES (1, 'Ana')")
        db.executa("INSERT INTO aluno VALUES (2, 'Bob')")

        db.executa("SELECT * FROM aluno")
        assert db.cache.pin_count == 0

        db.executa("SELECT nome FROM aluno WHERE id = 1")
        assert db.cache.pin_count == 0

        # Erro semântico na validação do WHERE
        with pytest.raises(ErroSemantico):
            db.executa("SELECT * FROM aluno WHERE id = 'texto'")
        assert db.cache.pin_count == 0



