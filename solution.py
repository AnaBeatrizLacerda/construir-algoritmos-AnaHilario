import os
import sys
import requests
import folium
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("SPTRANS_TOKEN", "").strip()
URL_BASE = "https://api.olhovivo.sptrans.com.br/v2.1"
LETREIRO_LINHA = "875A"
ARQUIVO_MAPA = "mapa_frota.html"
TIMEOUT = 30


def autenticar():
    if not TOKEN:
        raise RuntimeError(
            "Token não encontrado. Configure SPTRANS_TOKEN no arquivo .env."
        )

    sessao = requests.Session()

    try:
        resposta = sessao.post(
            f"{URL_BASE}/Login/Autenticar",
            params={"token": TOKEN},
            headers={"Content-Length": "0"},
            timeout=TIMEOUT
        )
    except requests.RequestException as erro:
        raise RuntimeError(
            f"Não foi possível conectar à SPTrans: "
            f"{type(erro).__name__}"
        ) from None

    if resposta.status_code != 200:
        raise RuntimeError(
            f"A SPTrans retornou HTTP {resposta.status_code} "
            "durante a autenticação."
        )

    if resposta.text.strip().lower() != "true":
        raise RuntimeError(
            "A SPTrans recusou a autenticação (resposta false). "
            "Verifique o token no arquivo .env."
        )

    print("Autenticação realizada com sucesso!")
    return sessao


def requisitar_json(sessao, endpoint, params=None):
    try:
        resposta = sessao.get(
            f"{URL_BASE}/{endpoint}",
            params=params,
            timeout=TIMEOUT
        )
        resposta.raise_for_status()
        return resposta.json()

    except requests.RequestException as erro:
        raise RuntimeError(
            f"Erro ao consultar {endpoint}: "
            f"{type(erro).__name__}."
        ) from None

    except ValueError:
        raise RuntimeError(
            f"A API retornou uma resposta inválida em {endpoint}."
        ) from None


def buscar_linha(sessao, letreiro):
    linhas = requisitar_json(
        sessao,
        "Linha/Buscar",
        {"termosBusca": letreiro}
    )

    correspondencias = [
        linha for linha in linhas
        if str(linha.get("lt", "")).strip().upper()
        == letreiro.upper()
    ]

    if not correspondencias:
        raise RuntimeError(
            f"A linha {letreiro} não foi encontrada. "
            "Altere LETREIRO_LINHA no início do arquivo."
        )

    print(f"\nLinhas encontradas para {letreiro}:")
    for indice, linha in enumerate(correspondencias, start=1):
        sentido = linha.get("sl", "?")
        origem = linha.get("tp", "Origem não informada")
        destino = linha.get("ts", "Destino não informado")
        print(
            f"{indice}. Sentido {sentido}: "
            f"{origem} -> {destino} "
            f"(código {linha.get('cl')})"
        )

    if len(correspondencias) > 1 and sys.stdin.isatty():
        while True:
            escolha = input(
                "Escolha o número da linha/sentido desejado: "
            ).strip()

            if escolha.isdigit():
                indice = int(escolha)
                if 1 <= indice <= len(correspondencias):
                    return correspondencias[indice - 1]

            print("Opção inválida. Tente novamente.")

    return correspondencias[0]


def buscar_paradas(sessao, codigo_linha):
    paradas = requisitar_json(
        sessao,
        "Parada/BuscarParadasPorLinha",
        {"codigoLinha": codigo_linha}
    )

    if not isinstance(paradas, list):
        raise RuntimeError(
            "A API não retornou uma lista válida de paradas."
        )

    return paradas


def buscar_onibus(sessao, codigo_linha):
    dados = requisitar_json(
        sessao,
        "Posicao/Linha",
        {"codigoLinha": codigo_linha}
    )

    if not isinstance(dados, dict):
        raise RuntimeError(
            "A API não retornou dados válidos dos veículos."
        )

    return dados.get("vs", []), dados.get("hr", "Não informado")


def criar_mapa(paradas, onibus, letreiro, horario):
    mapa = folium.Map(
        location=[-23.5505, -46.6333],
        zoom_start=12,
        control_scale=True
    )

    coordenadas = []

    camada_paradas = folium.FeatureGroup(
        name="Paradas de ônibus (azul)",
        show=True
    )

    for parada in paradas:
        lat = parada.get("py")
        lon = parada.get("px")

        if lat is None or lon is None:
            continue

        try:
            lat, lon = float(lat), float(lon)
        except (TypeError, ValueError):
            continue

        nome = parada.get("np", "Parada sem nome")
        endereco = parada.get("ed", "Não informado")
        codigo = parada.get("cp", "Não informado")

        folium.Marker(
            location=[lat, lon],
            tooltip=nome,
            popup=folium.Popup(
                f"<b>Parada:</b> {nome}<br>"
                f"<b>Endereço:</b> {endereco}<br>"
                f"<b>Código:</b> {codigo}",
                max_width=350
            ),
            icon=folium.Icon(
                color="blue",
                icon="info-sign"
            )
        ).add_to(camada_paradas)

        coordenadas.append([lat, lon])

    camada_paradas.add_to(mapa)

    camada_onibus = folium.FeatureGroup(
        name="Ônibus em tempo real (vermelho)",
        show=True
    )

    for veiculo in onibus:
        lat = veiculo.get("py")
        lon = veiculo.get("px")

        if lat is None or lon is None:
            continue

        try:
            lat, lon = float(lat), float(lon)
        except (TypeError, ValueError):
            continue

        prefixo = veiculo.get("p", "Não informado")
        acessivel = veiculo.get("a", False)
        horario_veiculo = veiculo.get("ta", "Não informado")

        folium.Marker(
            location=[lat, lon],
            tooltip=f"Ônibus {prefixo}",
            popup=folium.Popup(
                f"<b>Linha:</b> {letreiro}<br>"
                f"<b>Prefixo:</b> {prefixo}<br>"
                f"<b>Acessível:</b> "
                f"{'Sim' if acessivel else 'Não'}<br>"
                f"<b>Horário da posição:</b> {horario_veiculo}",
                max_width=350
            ),
            icon=folium.Icon(
                color="red",
                icon="bus",
                prefix="fa"
            )
        ).add_to(camada_onibus)

        coordenadas.append([lat, lon])

    camada_onibus.add_to(mapa)

    folium.LayerControl(collapsed=False).add_to(mapa)

    if coordenadas:
        mapa.fit_bounds(coordenadas)
    mapa.get_root().html.add_child(folium.Element(
        '<div style="position:fixed; bottom:30px; left:10px; z-index:9999; '
        'background:white; padding:6px; border:1px solid #777; '
        'border-radius:4px; font-size:12px;">'
        f'<b>Monitoramento da linha {letreiro}</b><br>'
        f'Horário de referência da API: {horario}<br>'
        f'Paradas: {len(paradas)} | Ônibus: {len(onibus)}'
        '</div>'
    ))

    mapa.save(ARQUIVO_MAPA)

    print("\nMapa criado com sucesso!")
    print(f"Arquivo: {os.path.abspath(ARQUIVO_MAPA)}")
    print(f"Paradas retornadas: {len(paradas)}")
    print(f"Ônibus retornados: {len(onibus)}")
    print(f"Horário de referência: {horario}")


def main():
    try:
        sessao = autenticar()

        linha = buscar_linha(sessao, LETREIRO_LINHA)
        codigo_linha = linha["cl"]
        letreiro = linha.get("lt", LETREIRO_LINHA)

        print(f"\nLinha selecionada: {letreiro}")
        print(f"Código da linha: {codigo_linha}")

        paradas = buscar_paradas(sessao, codigo_linha)
        onibus, horario = buscar_onibus(sessao, codigo_linha)

        if not paradas and not onibus:
            raise RuntimeError(
                "A API não retornou paradas nem veículos para essa linha."
            )

        criar_mapa(paradas, onibus, letreiro, horario)

    except (RuntimeError, KeyError) as erro:
        print(f"\nErro: {erro}")
        sys.exit(1)


if __name__ == "__main__":
    main()