# Monitor Extra

**Autoria do projeto e validação prática: Matheus Oliveira.**

O Monitor Extra transforma a tela de um notebook Windows em um monitor adicional de outro PC Windows pela rede local. É possível arrastar janelas para o notebook e manter aplicativos diferentes nas telas físicas do desktop.

## Contexto e resultado

O desktop estava conectado por cabo Ethernet e o notebook por Wi‑Fi na mesma rede local. O desktop não tinha suporte à projeção Miracast nessa configuração. A solução usa um driver de monitor virtual no desktop e envia pela rede a imagem dessa tela adicional. Matheus confirmou que o notebook funcionou como monitor extra no cenário real.

## Passo a passo

### No desktop principal

1. Coloque o desktop e o notebook na mesma rede local. O desktop pode ficar no cabo e o notebook no Wi‑Fi.
2. Abra o executável e escolha **Desktop principal**. Se o Apollo ainda não estiver instalado, clique em **Instalar Apollo**. O instalador inclui o driver de monitor virtual e pede autorização de administrador.
3. Abra **Abrir painel e PIN**. Na primeira configuração, crie um acesso local para administrar o Apollo.
4. Se o firewall bloquear a conexão, use **Autorizar no firewall** em uma rede de confiança com perfil **Privado**. O app configura as portas padrão do Apollo para a sub-rede local. O botão **Ver IP deste PC** mostra os endereços que podem ser usados no notebook.

### No notebook

1. Abra o mesmo executável e selecione **Notebook como monitor**.
2. Selecione o desktop encontrado e clique em **Parear selecionado**. Se ele não aparecer, use **Localizar por IP** e informe o IPv4 do desktop.
3. Digite no painel local do Apollo, no desktop, o PIN que o Moonlight mostrou no notebook.
4. No notebook, clique em **Abrir monitor extra**. O app abre a sessão **Virtual Display**. No desktop, clique em **Estender** se o Windows ainda não tiver guardado a disposição desejada. Em **Configurações → Sistema → Tela**, use **Identificar** para descobrir a posição da tela virtual e ajuste sua posição.
5. Deixe **Abrir automaticamente neste notebook** marcado se quiser repetir a sessão nas próximas aberturas. O app guarda somente o endereço local selecionado. O Moonlight mantém o pareamento no próprio perfil. Se o IP mudar, selecione o desktop novamente. Desmarque a opção para apagar o endereço salvo.

## Manter o áudio no desktop

1. No desktop, abra **Desktop principal → Áudio no Monitor 1**.
2. Selecione a saída que corresponde ao monitor ou aos alto-falantes e clique em **Usar como saída padrão**. O Windows mostra os nomes dos dispositivos de áudio, que podem ser diferentes do número da tela.
3. Inicie ou reconecte a sessão pelo botão **Abrir monitor extra** no notebook. O app inicia o Moonlight com o áudio do desktop ativo.
4. Para ouvir somente no desktop, use **Abrir áudio no Apollo**, desative **Stream Audio** em **Configuração → Áudio/Vídeo** e reconecte. Essa preferência desativa a transmissão de som em todas as sessões do Apollo.

## Escolhas técnicas e contrapartidas

| Decisão | Por que foi escolhida | Limitação |
| --- | --- | --- |
| Driver virtual SudoVDA incluído no Apollo | O Windows ganha uma tela independente, que aparece nas configurações de vídeo. | A instalação inicial exige administrador. A tela fica disponível durante a sessão, e drivers virtuais de outros programas podem interferir. |
| Apollo e Moonlight | Reaproveita transmissão de vídeo e pareamento já implementados, com suporte à codificação por hardware. | São componentes separados. Qualidade, resolução e latência dependem do hardware e da rede. |
| Rede local | Permite combinar cabo e Wi‑Fi, sem depender de Miracast ou de um serviço externo para transmitir. | Rede de convidados, isolamento entre dispositivos e perfis do firewall podem impedir a conexão. |
| Descoberta automática com opção de IP | Simplifica o primeiro acesso quando os anúncios de rede funcionam. | A descoberta pode falhar em redes que filtram multicast. O endereço salvo pode mudar por DHCP. |
| Lembrar o desktop no notebook | Depois de escolher o desktop, o app pode abrir o monitor automaticamente nas próximas execuções. | A primeira seleção e a autorização por PIN continuam necessárias. Cada computador mantém sua própria configuração local. |
| Um executável para os dois PCs | Inclui a interface, o instalador do Apollo e o Moonlight portátil. Python e downloads de componentes separados são dispensáveis para rodar o pacote. | O arquivo é maior que a interface isolada. A instalação do driver continua sujeita às políticas do Windows. |
| Python e Tkinter | Interface simples e um script de construção fácil de reproduzir. | Captura, codificação e driver continuam a cargo dos projetos especializados. |

O fluxo não exige assinatura mensal. O pacote gerado não é assinado com Authenticode. A confirmação do PIN e os avisos do Windows continuam válidos. O projeto não configura encaminhamento de portas no roteador.

## Criar o executável

Requisitos de construção: Windows, Python 3.14 de 64 bits e acesso à internet para obter as dependências e os arquivos de distribuição.

```powershell
python -m pip install -r requirements-build.txt
python build.py
```

O script confere o SHA-256 dos componentes oficiais, empacota o programa e testa a inicialização do executável. O arquivo final fica em `dist/MonitorExtra-Audio.exe`.

## Projetos utilizados

- [Apollo](https://github.com/ClassicOldSong/Apollo/tree/v0.4.6), responsável pelo driver virtual e pela transmissão.
- [Moonlight](https://github.com/moonlight-stream/moonlight-qt/tree/v6.2.0), responsável pelo pareamento e pela exibição.
- [python-zeroconf](https://github.com/python-zeroconf/python-zeroconf), usado para localizar hosts na rede.
- [Pycaw](https://github.com/AndreMiras/pycaw), usado para listar e escolher a saída padrão no Windows.
- [PyInstaller](https://pyinstaller.org/), usado para empacotar a aplicação Python.

A autoria indicada acima se refere ao projeto Monitor Extra. Cada componente mantém sua própria autoria e licença.
