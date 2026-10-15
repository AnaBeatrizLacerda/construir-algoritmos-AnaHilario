# Mapa de monitoramento de frota de ônibus (SPTrans)

Gera `mapa_frota.html` com as paradas (pins azuis) e os ônibus em tempo real (pins vermelhos) da linha configurada em `LETREIRO_LINHA` (padrão: 875A).

## Como executar

1. Instale as dependências:

   ```
   pip install -r requirementes.txt
   ```

2. Copie `.env.example` para `.env` e coloque um token válido da API Olho Vivo:

   ```
   SPTRANS_TOKEN=seu_token_aqui
   ```

3. Rode:

   ```
   python solution.py
   ```

4. Abra o arquivo `mapa_frota.html` no navegador.

## Observações
- Nos meus testes, a API da SPTrans retornou `false` em `POST /Login/Autenticar` mesmo com `Content-Length: 0` (testado via `curl`), por isso o mapa precisa ser gerado com um token que esteja sendo aceito.
