import os
import struct

from src.storage import (
    escreve_pagina,
    le_pagina,
    calcula_deslocamento,
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
    
    registro = struct.pack('<II', id_registro, matricula)

    dados = bytearray(PAGE_SIZE)
    
    # mockando o cabecalho hexdump (1 slot ocupado, etc.)
    # 01 00 08 00 02 00 00 00 -> 1 slot, 8 bytes record, page 2
    dados[0:8] = bytes([0x01, 0x00, 0x08, 0x00, 0x02, 0x00, 0x00, 0x00])

    # calcula onde o registro deve ficar dentro da página
    # o deslocamento_interno é apenas o offset a partir do byte 0 desta página
    deslocamento_interno = HEADER_SIZE + (slot * RECORD_SIZE)

    # coloca o registro no slot 0
    dados[deslocamento_interno:deslocamento_interno + RECORD_SIZE] = registro

    # escreve a pagina 2 no arquivo
    escreve_pagina(ARQUIVO_TESTE, pagina, bytes(dados))

    # simula o encerramento e reabertura do processo
    pagina_lida = le_pagina(ARQUIVO_TESTE, pagina)

    # le o registro que esta no slot 0
    registro_lido = pagina_lida[deslocamento_interno:deslocamento_interno + RECORD_SIZE]

    assert registro_lido == registro
    
    # extrai de volta pra garantir
    id_lido, matricula_lida = struct.unpack('<II', registro_lido)
    assert id_lido == id_registro
    assert matricula_lida == matricula


def test_calcula_deslocamento_retorna_8208_para_pagina_2_slot_0():
    pagina = 2
    slot = 0
    offset_absoluto = calcula_deslocamento(pagina, slot)
    
    assert offset_absoluto == 8208