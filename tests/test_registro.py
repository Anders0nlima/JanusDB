import os

from src.storage import (
    Pager,
    calcula_deslocamento,
    serializa_registro,
    desserializa_registro,
    PAGE_SIZE,
    HEADER_SIZE,
    RECORD_SIZE,
)

ARQUIVO_TESTE = "data/teste_registro.db"

def setup_module():
    os.makedirs("data", exist_ok=True)
    if os.path.exists(ARQUIVO_TESTE):
        os.remove(ARQUIVO_TESTE)


def test_escreve_e_le_registro_da_pagina_2():
    pagina = 2
    slot = 0
    id_registro = 1
    matricula = 20260001
    
    # 1. serializa o registro (transforma em bytes)
    registro_bytes = serializa_registro(id_registro, matricula)

    # 2. cria a página
    pager = Pager(ARQUIVO_TESTE)
    
    # vamos garantir que o arquivo tenha pelo menos 3 páginas (0, 1 e 2)
    # usando o aloca()
    while pager.n_paginas <= pagina:
        pager.aloca()

    # le a página vazia que foi alocada
    dados = pager.le(pagina)
    
    # mockando o cabeçalho
    dados[0:8] = bytes([0x01, 0x00, 0x08, 0x00, 0x02, 0x00, 0x00, 0x00])

    # 3. calcula o deslocamento interno e insere
    deslocamento_interno = HEADER_SIZE + (slot * RECORD_SIZE)
    dados[deslocamento_interno:deslocamento_interno + RECORD_SIZE] = registro_bytes

    # 4. escreve a pagina 2 no arquivo
    pager.escreve(pagina, bytes(dados))
    
    # 5. força a gravação física (sync) simulando a resistência a kill -9
    pager.sync()
    pager.fecha()

    # 6. simula o encerramento e reabertura do processo
    pager_reaberto = Pager(ARQUIVO_TESTE)
    pagina_lida = pager_reaberto.le(pagina)

    # 7. le os bytes do slot 0
    registro_lido_bytes = pagina_lida[deslocamento_interno:deslocamento_interno + RECORD_SIZE]

    # verifica se os bytes estão corretos
    assert registro_lido_bytes == registro_bytes
    
    # 8. desserializa de volta pra garantir
    id_lido, matricula_lida = desserializa_registro(registro_lido_bytes)
    assert id_lido == id_registro
    assert matricula_lida == matricula
    
    pager_reaberto.fecha()


def test_calcula_deslocamento_retorna_8208_para_pagina_2_slot_0():
    offset_absoluto = calcula_deslocamento(pagina=2, slot=0)
    assert offset_absoluto == 8208