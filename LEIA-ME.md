# Mondego IA

(antes «Estuda Comigo») Assistente de estudo para estudantes e professores, em português europeu: assistente
explicador, resumos, slides, quizzes, testes, flashcards com repetição espaçada, planos de estudo, cronómetro e
calendário académico, com base nos teus próprios documentos.

## Como abrir

```
cd "C:\Users\Miguel Silva\Documents\escola\python\estuda-comigo"
py -3.14 -m streamlit run app.py
```

Também podes fazer duplo clique em `iniciar.bat`.

## Ficheiros

| Ficheiro | O que guarda |
|---|---|
| `app.py` | A aplicação (interface Streamlit). |
| `identidade.py` | Símbolo, logótipo, temas claro/escuro/automático e animação de carregamento. |
| `academico.py` | Listas do onboarding: licenciaturas e departamentos da UC (catálogo oficial), áreas e disciplinas do secundário. |
| `repeticao.py` | Repetição espaçada dos flashcards (caixas de Leitner). |
| `salas.py` | Regras das Salas (quem vê cada ficheiro, quem escreve no chat, códigos de convite). |
| `salas_backend.py` | Armazenamento das Salas: modo **local** (SQLite, `salas_local.sqlite`) ou **Supabase** (online). |
| `supabase/esquema.sql` | Tabelas e regras de privacidade (RLS) para o Supabase, incluindo os dados de estudo de cada conta (`dados_utilizador`). |
| `supabase/servidor_falso.py` | Supabase simulado (só na memória) usado pelos testes `testes_nuvem.py`. |
| `assets/` | Imagens do logótipo enviadas (referência). |
| `estudio3d.py` | Formato dos modelos 3D (peças geométricas reais), validação, edição por operações, moléculas (SDF) e superfícies. |
| `biblioteca3d.py` | Modelos 3D: versões, publicação, pesquisa, gostos, favoritos, coleções, partilha e remix (SQLite local ou Supabase). |
| `gerador3d.py` | Ligação preparada ao Meshy (malhas 3D realistas). **Não testada** — precisa de uma chave paga. |
| `motor_blender.py` | Motor Blender: envia a forma das peças ao Blender (deste computador ou de um servidor) e guarda o GLB melhorado. |
| `blender/` | Scripts que correm dentro do Blender: `construir_modelo.py` (biséis, superfícies lisas, relevo, materiais, exporta GLB) e `geometria.py` (as mesmas formas do visualizador). |
| `servidor_blender/` | Servidor Blender para a app online (`servidor.py` + `Dockerfile`), para que todos os utilizadores tenham modelos feitos no Blender. |
| `voz_tts.py` | Voz do assistente: a resposta passa a fala com a voz masculina «Charon» da Google (modelos TTS do Gemini) e a gravação do microfone passa a texto (`transcrever`: modelo de transcrição da Google, com reserva num modelo de texto). |
| `laboratorio.py` | Química (tabela periódica, massa molar, acerto de equações), Biologia (código genético, Punnett), Matemática (funções sem `eval`). |
| `componentes/mondego/` | Componentes que correm no browser: visualizador 3D (Three.js), simulações de Física, tabela periódica, mapa (Leaflet + OpenStreetMap), linha do tempo e editor de Python (Pyodide). Carregam as bibliotecas da web na primeira utilização. |
| `avaliacoes.py` | Lógica das avaliações e do calendário (criar, editar, apagar, validar, planos). Não depende do Streamlit. |
| `inicio_sessao.py` | Início de sessão: credenciais do Google, da Microsoft e do Auth0 (Facebook e Apple) em `.streamlit/secrets.toml`, sessões lembradas por browser (cookie), administradores e passagem dos dados antigos para a conta. |
| `desempenho.py` | Velocidade das respostas: cache da lista de modelos, escolha do modelo por tarefa, excertos relevantes dos documentos e histórico da conversa com limite. |
| `exercicios.py` | Testes dos Laboratórios: pedido à IA, validação, correção (exata nas objetivas, pela IA nas abertas), diagnóstico e adaptação. |
| `lab_historia.py` | Laboratório de História: instruções de rigor, documentos, cronologias, comparações e resumos (validação do que a IA devolve). |
| `lab_biologia.py` | Laboratório de Biologia: processos passo a passo, divisão celular em SVG, exercícios de genética, Hardy-Weinberg, osmose, experiências, dados e glossário. |
| `laboratorio.json` | (na pasta da conta) O trabalho do Laboratório: explicações, análises, cronologias, comparações, resumos, testes e glossário. |
| `historico.py` | Histórico das conversas do Assistente: fixadas, grupos por data, pesquisa e títulos curtos feitos pela IA. |
| `pesquisa_web.py` | Pesquisa na web feita pela app quando a pesquisa Google do Gemini não está disponível na chave, só em fontes fiáveis: Tavily (com chave grátis; sem Wikipédia, fóruns nem sites de perguntas e respostas, e com os sites oficiais, as universidades e as revistas científicas à frente) ou, sem chave, Google Notícias (coisas recentes), Open-Meteo (tempo) e OpenAlex (artigos de revisão, livros e capítulos académicos). A Wikipédia só entra quando nada mais encontra resultados. |
| `preparar.py` | Assistente pedagógico «Preparar com a IA» (professores): o que a IA pergunta na conversa guiada, os pedidos dos materiais (plano de aula, ficha, teste com critérios e as 9 sugestões), as versões guardadas e a exportação para Word e PDF. A página está em `app.py` (`pagina_preparar`). |
| `plano_estudo.py` | Regras do Plano de Estudo Inteligente: preferências (dias e ritmo), limpeza dos temas propostos pela IA, distribuição das tarefas pelos dias (revisões espaçadas, cadeiras intercaladas, carga equilibrada), reorganizar o que ficou por fazer, resumo e progresso. Sem horas nem durações. |
| `definicoes.py` | Regras das Definições (sem Streamlit): categorias, valores por omissão e limpeza das preferências, pesquisa, CSS da acessibilidade (tamanho do texto, contraste, leitura, foco, menos movimento), instruções da IA a partir das preferências, avisos do Início, resumo do foco e validação da palavra-passe. |
| `avaliacoes.json` | **Fonte única de todas as provas.** Cada prova tem um `id` que nunca muda. |
| `dados/<cadeira>.json` | Documentos, objetivo (nota pretendida, dificuldade), plano de preparação, resumos, quizzes, etc. |
| `perfil.json` | Nome, conversas, plano geral, preferências do plano (`plano_prefs`), tarefas do plano feitas (`feitas`), tempo na app por dia (`uso`), sessões de foco (`foco`), a opção `guardar_estatisticas`, as **preferências das Definições** (`preferencias`, seguem a conta para qualquer dispositivo), os avisos dispensados hoje (`avisos_vistos`) e quando abriste cada sala pela última vez (`salas_vistas`). |
| `config.json` | Fornecedor da IA, chave e velocidade. |
| `.streamlit/secrets.toml.exemplo` | Modelo para ligar o login com Google / Facebook / Microsoft. Copia para `secrets.toml` (esse ficheiro nunca é exportado nem partilhado). |
| `backup/` | Cópias de segurança feitas antes de migrações. |
| `testes_avaliacoes.py`, `testes_modulos.py`, `testes_salas.py`, `testes_3d.py`, `testes_laboratorio.py`, `testes_matematica.py`, `testes_voz.py`, `testes_blender.py`, `testes_plano.py`, `testes_pesquisa.py`, `testes_historico.py`, `testes_inicio_sessao.py`, `testes_nuvem.py`, `testes_laboratorios.py`, `testes_desempenho.py`, `testes_definicoes.py`, `testes_preparar.py` | Testes automáticos (ex.: `py -3.14 testes_3d.py`). Usam pastas temporárias e não precisam de internet nem do Blender. |

## Preparar com a IA (professores)

Página própria (menu lateral e cartão do Início). A IA começa a conversa e faz uma pergunta de cada vez, com respostas de um clique; não pergunta o que já sabe pelo perfil e pelas turmas e faz no máximo 4 perguntas. Dá para voltar atrás e mudar uma resposta ou mandar criar já com o que tem. Materiais: plano de aula, ficha de exercícios (por níveis, com espaço para as respostas e soluções à parte), teste com cotações e critérios, e as sugestões de «Em que posso ajudar hoje?» (ideias de aula, jogo, alunos com dificuldades, níveis, grelha de avaliação, apresentação, planificação semanal, consolidação, motivação). Cada material fica em «Os teus materiais» (no perfil da conta) com as versões: mais fácil, mais difícil, nova versão, alterações pedidas, edição à mão e respostas alteradas. Exporta para Word (python-docx) e PDF (PyMuPDF, com a letra Arial do Windows para os símbolos). O professor pode anexar um modelo (teste da escola, ficha antiga, grelha; PDF, Word, PowerPoint, texto ou fotografia), na página inicial ou a meio da conversa: a IA tira dele o que puder e pergunta se é para seguir o formato, fazer um novo a partir dele ou adaptá-lo. Testes: `py -3.14 testes_preparar.py`.

## Calendário académico

- Página **Calendário** na barra lateral, com vista **Mês**, **Semana** e **Agenda**, botões ‹ › e **Hoje**,
  filtros por cadeira e tipo e uma legenda de cores (Exame, Teste, Trabalho, Apresentação, Outro).
- **Nova avaliação**: nome, cadeira (das já existentes), tipo, data (obrigatória), hora (opcional) e notas.
  Sem hora, a prova é de dia inteiro: nunca se inventa uma hora e não fica "atrasada" durante esse dia.
- Clicar numa prova abre os detalhes, com **Editar** e **Apagar** (pede confirmação). Editar mantém o mesmo
  registo: mudar a data move a prova no calendário e a mudança fica gravada.
- Clicar no número de um dia mostra as provas e as tarefas do plano de estudo desse dia (podes marcá-las como feitas).
- As provas passadas continuam visíveis (riscadas e mais claras) e na Agenda em **Passadas**.
- **No telemóvel** o calendário é compacto: o mês e ‹ Hoje › numa linha, as vistas e o **+** (nova avaliação) na de
  baixo, e o mês num só cartão, com o número de cada dia num círculo (hoje preenchido), um **ponto** por avaliação (cor
  do tipo) e um **anel** por tarefa de estudo (cor da sala). Tocar em qualquer sítio do dia abre esse dia com tudo. A
  janela **Nova avaliação** põe Sala e Tipo lado a lado, e Data e Hora lado a lado. No computador o calendário fica
  igual (a janela Nova avaliação só perdeu a moldura que sobrava à volta dos campos).
- Uma sala com uma cor escolhida (terracota, amarelo, cinzento…) aparece com essa cor nas tarefas do calendário e do plano.

### Uma só fonte de dados

As datas das provas existem **só** em `avaliacoes.json`. Tudo o resto lê daí:

- a tabela **Editar cadeiras, avaliação principal e objetivos** (no Painel e nas perguntas iniciais) edita a
  avaliação principal de cada cadeira no mesmo ficheiro;
- o Painel, o chat, os cartões das cadeiras e o contexto enviado à IA usam sempre as datas atuais;
- os planos de estudo são gerados com as datas atuais.

Na primeira vez que abres esta versão, as datas antigas (uma por cadeira, dentro de `dados/<cadeira>.json`) são
passadas automaticamente para `avaliacoes.json`. Antes disso é guardada uma cópia em `backup/`.

### Plano de estudo com IA (Plano de Estudo Inteligente)

O plano diz **o que estudar em cada dia** — nunca horários nem durações: o tempo organizas tu. Cada dia é uma lista
simples de tarefas concretas, como «**Matemática** — Estudar funções: domínio e contradomínio».

- **Assistente em 4 passos** (Calendário → Plano → «Novo plano com IA», Início → «Criar plano de estudo», ou a
  avaliação/cadeira → «Criar plano de preparação»):
  1. **O que planear**: todas as cadeiras com avaliações ou só uma avaliação.
  2. **Como estudas**: os **dias em que estudas**, o **ritmo** (Leve: até 3 tarefas por dia; Equilibrado: até 4;
     Intenso: até 6, com todas as cadeiras juntas), por onde começar, estilo (teoria, exercícios, testes) e, por cadeira,
     **como a sentes** (fácil, média, difícil) e a **nota que queres**. Fica guardado para os próximos planos.
  3. **Perguntas da IA**: a IA lê as fontes e pergunta-te o que achas mais difícil (com os temas reais da matéria), o que
     já estudaste, etc. Podes acrescentar o que quiseres.
  4. **O teu plano**: vês um cartão por dia antes de guardar. **Refazer** com o que quiseres mudar («começa por
     integrais») ou **Guardar no calendário** (podes manter as tarefas que já fizeste: esses temas só voltam em revisões).
- **A IA só propõe os temas** de cada cadeira (pela ordem da matéria), com a dificuldade, a importância e três tarefas
  concretas por tema (estudar, praticar, rever). **A distribuição pelos dias é feita pela app**, sempre da mesma maneira:
  - cada tema: estudar → praticar (exercícios) → revisões espaçadas (mais e mais cedo nos temas difíceis e importantes;
    nos difíceis, também «refazer os exercícios que correram pior»);
  - as cadeiras são intercaladas e a matéria nova de cada uma é espalhada por igual até à avaliação;
  - nos últimos dias antes de cada avaliação: revisão geral e um teste de treino;
  - nenhum dia passa o ritmo escolhido; se faltar pouco tempo, estudar e praticar juntam-se numa tarefa e os dias
    sobem por igual (nunca fica tudo no último dia); as revisões extra que não cabem ficam de fora (a matéria nunca);
  - nada no passado, nos dias em que não estudas, no dia da avaliação ou depois; nenhuma tarefa repetida.
- **Vista «Plano»** no Calendário (e no separador Plano de cada cadeira): progresso, **um cartão por dia** (nome do dia,
  data e um progresso discreto, ex.: 2/4) com uma caixa para marcar cada tarefa. O que ficou por fazer em dias que já
  passaram aparece em **«Ficaram por fazer»**, com **Reorganizar o plano**: espalha o que falta pelos dias até à
  avaliação, sem sobrecarregar nenhum dia, e o que já fizeste não muda. **Refazer** ou **Apagar** o plano a qualquer
  momento.
- **Uma tarefa** (botão «…» ou clicar no calendário): marcar como feita, **passar para o próximo dia** em que estudas,
  mudar o dia, o tipo ou o texto, apagar ou abrir a cadeira.
- **No calendário**: cada tarefa aparece no seu dia, na cor da cadeira (riscada quando feita). No Início, arrastar uma
  tarefa para outro dia muda-lhe o dia; «Plano de hoje» mostra as tarefas de hoje para marcar, **Ver o plano** e **Gerir**.
- Planos antigos (com horas) continuam a funcionar; as horas deixam de aparecer e saem quando a tarefa é mudada ou o
  plano reorganizado.

### Planos de estudo e mudanças de data

- Cada plano de preparação fica ligado a uma avaliação (`avaliacao_id`) e à data que tinha quando foi criado.
- Se a data de uma prova mudar, **o plano não é alterado sozinho**. Aparece um aviso no Calendário, no Painel e
  na página da cadeira, com o botão **Reorganizar o plano**. Ao reorganizar (sem IA), as tarefas já feitas ficam e as
  que estão por fazer são espalhadas pelos dias até à nova data; as de avaliações que já passaram saem do plano.
- O plano geral guarda as datas de todas as provas no momento em que é criado e avisa quando alguma muda.

## Navegação

Barra lateral (recolhe-se no botão «« do topo): **Nova conversa** · **Pesquisar conversas** · **Início** ·
**Salas** · **Calendário** · conversas **recentes** (fixadas primeiro, depois por data) · no fundo, o teu **Perfil** e as
**Definições**. Já não há «Cadeiras»: **as cadeiras passaram a ser salas só tuas** (ver «Salas»), e o **Laboratório**
também deixou de ser uma página: é uma opção de cada sala. O 3D Studio continua
escondido (ver mais abaixo).

Identidade visual «Mondego»: azul-rio (o acento), tinta azul-noite (o texto), papel frio (o fundo) e dourado só como
destaque, com a letra Inter; temas Claro, Escuro e Automático.

**Sistema de design** (em `identidade.py`, variáveis CSS iguais nos dois temas): cantos (`--r-sm` 8 px, `--r-md` 10 px,
`--r-lg` 14 px, `--r-xl` 18 px), espaçamentos (`--e-1`…`--e-6`), tamanhos de letra (`--t-xs`…`--t-2xl`), três sombras
(`--sombra-1/2/3`), anel de foco (`--foco`) e cores de estado (`--sucesso`, `--aviso`, `--erro`). Todos os componentes
(botões, campos, separadores, menus, janelas, notificações, avisos, números, tabelas, zona de ficheiros) usam estes
valores, com os mesmos estados: passar por cima, carregar, foco do teclado e desligado.
- **Páginas**: o mesmo cabeçalho em todas (título grande, descrição e ações à direita: `cabecalho()` /
  `cabecalho_pagina()`), os mesmos títulos de cartão (`titulo_cartao()`), a mesma fila de números (`mi-dia`) e os
  mesmos cartões e estados vazios. O CSS comum está no `ESTILO` de `app.py`; cada página só acrescenta o que é dela.
- **Início**: primeiro o dia num relance (próxima avaliação, foco, plano de hoje, flashcards), depois o Assistente
  Mondego, as próximas avaliações e o calendário; à direita o plano de hoje e o cronómetro.
- As animações mexem-se sempre, mesmo com «reduzir movimento» ligado no sistema (pedido do utilizador). Só a opção
  **Reduzir animações** das Definições (Personalização ou Acessibilidade) as tira — e nunca mexe nos laboratórios.
- **Movimento com intenção**: as animações respondem ao que fazes (carregar num botão, abrir um cartão, guardar), curtas
  (120–240 ms) e iguais em todas as páginas; nada se mexe sozinho para enfeitar.
- **Claro e escuro a sério**: o Streamlit tem um tema claro e um escuro (`.streamlit/config.toml`, `[theme.light]` e
  `[theme.dark]`) com as cores da app. A «Cor da aplicação» (Definições) manda nos dois: o script `identidade.tema_js()`
  põe o tema do Streamlit igual ao da app (se for preciso, a página recarrega uma vez). Assim, no modo escuro, as
  caixas de escrita, menus, janelas, listas e componentes (voz, cronómetro…) também são escuros, com contraste AA
  (letra ≥ 4,5:1; bordas das caixas ≥ 3:1). Cores dos campos e menus: `--campo`, `--campo-texto`, `--campo-suave`,
  `--borda-campo`, `--menu`, `--menu-hover`.
- **Ecrãs**: no tablet (e com a barra lateral aberta num ecrã estreito) as colunas ficam umas por baixo das outras,
  como no telemóvel; no telemóvel o botão do menu (☰) fica bem visível e as ferramentas de cada cadeira ficam numa
  faixa que desliza para o lado. O texto em inglês do Streamlit (ex.: «Upload», «200MB per file») aparece em português.

- **Início**:
  - **Assistente Mondego** (só por voz): carregas na esfera, fazes a pergunta em voz alta e ele responde a falar, em
    português de Portugal. Há «Responder em voz alta», «Conversa contínua» (volta a ouvir depois de responder, quando a
    pergunta foi falada) e uma caixa pequena para escrever se não puderes falar. Estas duas opções ficam guardadas na
    conta (as mesmas das Definições → Inteligência artificial).
    - **Estados da esfera**: Inativa, A ouvir, A processar, A responder, Em pausa e Erro — cada um com cor, ícone e
      texto próprios e anunciado aos leitores de ecrã. Enquanto ouves, o que dizes aparece escrito em tempo real.
      Controlos: «Acabei de falar» (a ouvir), «Pausar»/«Continuar» e «Parar» (a responder), «Tentar outra vez» (erro).
      Carregar na esfera enquanto fala põe em pausa; carregar outra vez continua; **Esc** para. Os erros dizem o que
      fazer (microfone bloqueado, sem microfone, sem rede); se não ouvir nada volta a Inativa com um aviso. Para escrever com anexos (PDFs,
    fotografias) há o botão «Preferes escrever?», que abre o **Assistente**.
    - **Ouvir** (como num assistente de voz a sério): a esfera grava o que dizes com cancelamento de eco, redução de
      ruído e ganho automático e percebe sozinha que acabaste (uma pausa de 1,5 s depois de falares; desiste ao fim de
      8 s sem ouvir nada; no máximo 1 minuto). Só a parte em que falaste vai para a app, que a transcreve com a Google
      (modelo de transcrição `gemini-3.5-transcribe`, em português de Portugal ou inglês, conforme o idioma da app), com
      as palavras que é provável dizeres: as tuas cadeiras, as avaliações, os nomes dos documentos e das partes da app.
      Se esse modelo não estiver disponível para a tua chave, um modelo de texto rápido ouve a gravação com a conversa
      recente para perceber palavras ambíguas. O texto que aparece enquanto falas é do reconhecimento do browser e fica
      de reserva: se a transcrição falhar (sem rede, limite atingido), a pergunta segue com ele e não se perde. Em
      browsers sem reconhecimento de voz (ex.: Firefox) a esfera também ouve, desde que a app tenha a chave do Gemini.
      Sem a chave do Gemini (ou com o Claude escolhido) ouve só com o browser, como antes. A chave nunca vai para o
      browser; a gravação não fica guardada na app e o pedido de transcrição pede à Google para não a guardar
      (`store: false`).
    - **Voz**: o Mondego fala sempre com a voz masculina **Charon** da Google (usa a chave do Gemini). A resposta aparece
      logo escrita e a fala chega a seguir; «▶ Ouvir outra vez» repete. Só se a voz da Google não estiver disponível é
      que usa a voz do browser.
    - **Sabe da tua app**: próximas avaliações, plano de hoje, minutos de foco, flashcards por rever, último quiz e os teus
      documentos. Pergunta, por exemplo, «o que tenho de estudar hoje?» ou «quando é o próximo teste?». Para notícias,
      resultados ou horários pesquisa na web (com o Gemini).
    - **Faz coisas por ti**: «abre os flashcards de Álgebra», «põe o cronómetro a 40 minutos», «abre as salas».
      Primeiro responde, depois abre a página (para não cortar a fala).
  - **Resumo do dia**: próxima avaliação, minutos de foco hoje, plano de hoje e flashcards por rever.
  - **Avisos** (notificações dentro da app): avaliações a chegar (com a antecedência escolhida), plano de hoje, tarefas
    que ficaram por fazer, flashcards para rever, temas a rever (os do último quiz com mais erros) e mensagens novas nas
    salas. Os urgentes primeiro; cada um tem a ação que leva ao sítio certo e «Dispensar» (some por hoje, na conta).
    Noutras páginas, o Início na barra lateral mostra quantos avisos esperam. Configuram-se em Definições →
    Notificações. **Não há email nem notificações do telemóvel** — a app diz isso nas Definições.
  - Calendário arrastável, cronómetro e plano de hoje. O calendário completo (mês, semana, agenda e filtros) abre daqui.
- **Barra lateral**: sempre as conversas recentes. Nas Salas aparecem também as tuas salas, cada uma com o seu ícone na
  sua cor: primeiro as só tuas (pela avaliação mais próxima, com quanto falta — a destaque a 3 dias ou menos), depois as
  partilhadas; e ainda «Nova sala», «Entrar numa sala» e «Rever flashcards». As próximas avaliações e o plano de hoje
  estão no Início.
- **Sala só tua** (o que antes era uma cadeira; estilo NotebookLM), numa só coluna, de cima para baixo. Em cima,
  «← Salas»; o cabeçalho tem o ícone e a cor da sala, «Só tu», a próxima avaliação e os botões Fontes, Avaliações e
  **Definições** (nome, ícone, cor, descrição, a nota que queres tirar, como sentes a matéria e **apagar a sala**).
  Mudar o nome leva tudo com ela: fontes, flashcards, quizzes, plano, avaliações, tarefas feitas e conversas.
  - **Cabeçalho**: nome da cadeira, próxima avaliação (e quanto falta), objetivo e tema em foco, e três botões:
    **Fontes · N** (janela para adicionar fontes, escolher as que entram — Todas / Nenhuma, procurar —, apagar e focar
    num tema; as fontes desligadas ficam guardadas na cadeira), **Avaliações** (as próximas, Nova avaliação, abrir o
    calendário) e **Mais** (apagar a cadeira, com confirmação).
  - **Resumo em quatro números**: próxima avaliação, fontes selecionadas, flashcards para hoje e média dos quizzes e
    testes.
  - **Separadores**: Conversa, Resumo, Guia, Mapa, Quiz, Flashcards (repetição espaçada), Teste, Slides, Plano e
    Progresso — um de cada vez, na largura toda, com uma frase a dizer o que faz. A cadeira lembra-se do separador onde
    estavas.
  - **Conversa**: responde só com as fontes selecionadas e indica de onde vem cada resposta; caixa de pergunta fixa no
    fundo, como no Assistente.
  - **Quiz** (como no NotebookLM): uma pergunta de cada vez, opções em cartões, dica, explicação de cada opção depois de
    responder, Anterior/Seguinte, atalhos (1–4, ← →, D) e ecrã final com a nota, os temas e a revisão das erradas.
  - **Flashcards**: cartão que vira (clique ou Espaço). **Estudar** (setas, baralhar, «Explicar») ou **Rever hoje**
    (Errei / Difícil / Sabia, teclas 1–3), que atualiza a repetição espaçada.
  - As fórmulas aparecem como no papel (KaTeX).
- **Estilo das respostas (como no Claude)**: as instruções originais da IA mantêm-se (português de Portugal, fontes e
  citações, fórmulas em LaTeX, regras da web) e juntam-se blocos partilhados: começa pela resposta, sem preâmbulos nem
  frases de fecho; tamanho proporcional à pergunta; prosa por defeito e listas, títulos, negrito e tabelas só quando
  ajudam; tom caloroso e honesto, sem bajulação, a corrigir erros com clareza e a dizer quando não tem a certeza; usa o
  contexto do aluno só quando muda a resposta; conhece os caminhos da app; em conversas novas responde logo, sem se
  apresentar. Os pedidos com formato exato (JSON) seguem esse formato à letra.
- **Histórico do Assistente (barra lateral)**: «Nova conversa» no topo, pesquisa nas conversas (título e conteúdo),
  conversas fixadas primeiro e as outras por Hoje, Ontem, Últimos 7 dias, Últimos 30 dias e Mais antigas (30 de cada vez,
  com «Mostrar todas»). Depois da primeira resposta, a IA dá um título curto à conversa. Em «Mais», no cabeçalho da
  conversa: fixar no topo, mudar o nome e apagar.
- **Assistente** («Nova conversa»): a caixa é como a do Claude — o texto em cima e, por baixo, o **+** à esquerda e o
  botão de enviar à direita. O **+** abre um menu:
  - **Adicionar ficheiros ou fotos** (PDF, Word, PowerPoint, texto e fotografias PNG, JPG ou WebP — a IA lê o texto
    das fotografias);
  - no computador, **Tirar captura de ecrã** (o browser pergunta se queres partilhar o ecrã inteiro, uma janela ou um
    separador; a imagem fica nos anexos); no telemóvel, **Tirar fotografia** (a câmara só liga quando carregas);
  - **Pesquisar na web**, **Documentos** (todas as cadeiras ou só uma: a IA responde com os documentos dessa cadeira e
    os anexos ficam guardados nela) e **Estilo das respostas** (Respostas, Nível, Idioma — ficam na conta, como em
    Definições → Inteligência artificial).
  Os anexos aparecem dentro da caixa, por cima do texto (as imagens com miniatura), cada um com o seu **×**, e há
  **Resumir** (envia só os anexos e pede um resumo). Também podes arrastar ou colar ficheiros para a caixa. Na conversa
  aberta, a mesma barra fica fixa no fundo.
  - **Em cada resposta**: **Copiar** (copia o texto original, com as fórmulas em LaTeX) e, na última, **Gerar outra
    resposta**. **Em cada pergunta**: **Editar** (a conversa continua a partir da pergunta editada). Se a IA falhar, a
    pergunta fica na conversa com **Tentar outra vez**. Os avisos da pesquisa ficam junto da resposta.
  - **Conversas longas**: aparecem as 40 mensagens mais recentes («Mostrar as N mensagens anteriores»); a IA recebe as
    mensagens recentes que cabem num limite (as antigas muito longas vão encurtadas).
  - **Os teus documentos**: a IA recebe só os excertos das cadeiras que têm a ver com a pergunta (se nenhum tiver, não
    recebe nenhum). Os resumos, quizzes, flashcards e planos estão nas cadeiras.
  - Em «Mais» (no cabeçalho da conversa): fixar, mudar o nome e apagar. As opções da IA estão no **+** da barra.
  Com **Pesquisar na web** ligado:
  - com o Gemini, a IA pesquisa na Google antes de responder e mostra os sites no fim (experimenta todos os modelos);
  - se a tua chave do Gemini não tiver quota para a pesquisa Google (a Google responde «429 RESOURCE_EXHAUSTED» — foi o
    que aconteceu com a chave usada nos testes), **a app pesquisa sozinha**. A IA primeiro vê de que tipo é a pergunta:
    algo recente (lançamentos, datas, notícias, resultados) → **Google Notícias**; tempo → previsão da **Open-Meteo**;
    conhecimento geral → **Wikipédia** (só ficam as páginas que têm a ver com a pesquisa). As perguntas sobre o tempo
    reconhecem-se mesmo sem a IA, com a cidade tirada da pergunta (sem cidade, Coimbra). Nada disto precisa de chave. Com uma chave grátis da **Tavily** (Perfil → Administração → Pesquisa na web) pesquisa em toda a web. A IA responde diretamente com esses resultados (sem dizer que «não
    está nos documentos») e mostra os sites. Durante 30 minutos não volta a tentar a da Google (para não perder tempo);
  - se nada der, diz-te claramente que não conseguiu pesquisar e não inventa dados atuais (tempo, notícias, resultados);
  - enquanto trabalha, o indicador mostra o passo em curso: «A pesquisar na web» (com as palavras e onde procura),
    «A ler N fontes» (com os nomes dos sites) ou «A pensar»; o avatar ganha um anel a girar.
- **Modelos sobrecarregados**: se a Google responder «503 UNAVAILABLE» (muita procura), a app passa ao modelo seguinte;
  se estiverem todos assim, diz que é passageiro.
- **Calendário arrastável**: componente `streamlit-calendar` (FullCalendar), instalado pelo `iniciar.bat`.
- **Cronómetro**: escolhes os minutos (15, 25, 45, 60, 90 ou outro valor até 240), a pausa a seguir e, se quiseres, a
  cadeira. Conta no browser a partir da hora de fim (não perde segundos ao mudar de página nem com o separador em segundo
  plano; dois separadores abertos ficam iguais) e no fim guarda o tempo de foco em `perfil.json` → `foco`.
  - Mostra o **resumo de hoje** (minutos, sessões e dias seguidos) e tem o **Histórico de foco** (últimas sessões, total
    por cadeira e apagar uma registada por engano).
  - **Noutras páginas** o cronómetro que está a correr aparece em pequeno na barra lateral (tempo, pausar/retomar e
    terminar); quando está parado não ocupa espaço.
  - Nas salas, **Estudar** (no cabeçalho da sala) começa uma sessão de foco com a cadeira da sala. Não aparece com o
    separador Laboratório aberto, para o Laboratório ficar exatamente como estava.
- **Perfil** (barra lateral → «<nome> · Perfil»): **Editar perfil** muda o nome e a fotografia (cortada em quadrado e
  guardada em `perfil.json`) e dá acesso ao perfil académico. Se tiveres sessão iniciada nas Salas, o nome e a
  fotografia também mudam na conta (os colegas veem-nos). Mostra ainda o tempo na aplicação (hoje, 7 dias, total), o
  tempo de estudo, quizzes, flashcards revistos, o gráfico dos últimos 14 dias, o tempo por cadeira e o que criaste com IA
  (conversas, materiais, linhas do tempo, mapas) e o **progresso por cadeira** (tarefas do plano feitas, média e último
  quiz, foco nos últimos 7 dias, flashcards por rever e a próxima avaliação). Os atalhos levam às Definições (Conta, Privacidade, Notificações, Acessibilidade).
- **Definições** (barra lateral → Definições): uma página própria, com navegação lateral no computador e, no
  telemóvel, a lista das categorias (ao abrir uma, «← Definições» volta à lista). Tem **pesquisa** (procura em todas as
  opções e nas perguntas frequentes, com ou sem acentos). As escolhas simples guardam-se logo («Guardado às hh:mm»); os
  formulários (nome, palavra-passe, perfil académico) mostram «Alterações por guardar» e, se saíres a meio, a app
  pergunta se queres continuar a editar ou descartar (também ao fechar o separador). Ficam na conta
  (`perfil.json` → `preferencias`), por isso voltam ao entrares noutro dispositivo. Se a página recarregar (por
  exemplo ao mudar o tema), volta à mesma categoria.
  - **Conta e perfil**: nome, fotografia, email, mudar a palavra-passe (pede a atual; contas Google/Microsoft mudam-na
    lá), terminar sessão neste e nos outros dispositivos lembrados, e apagar a conta (com confirmação).
  - **Perfil académico**: o resumo do perfil académico (com «Editar»), a dificuldade e a nota pretendida de cada
    cadeira, e as preferências do plano de estudo (dias de folga e ritmo).
  - **Personalização**: tema (Automático, Claro, Escuro), página inicial ao entrar, animação de entrada e reduzir
    animações.
  - **Notificações**: os avisos do Início (ligar/desligar cada tipo e com quantos dias de antecedência avisar das
    avaliações).
  - **Inteligência artificial**: velocidade, idioma, tamanho das respostas, nível das explicações, tom, pesquisar na
    web e as opções da voz (responder em voz alta, conversa contínua, velocidade). A IA recebe estas escolhas em cada
    pedido. Ao administrador mostra o atalho para a chave da IA.
  - **Privacidade e segurança**: guardar estatísticas, descarregar os dados (.zip, sem chaves), importar, apagar as
    conversas ou as estatísticas (com confirmação).
  - **Acessibilidade**: tamanho do texto, contraste alto, leitura confortável, realce do foco do teclado e menos
    movimento (fora dos laboratórios), com «Repor».
  - **Ajuda e suporte**: perguntas frequentes, relatório de problema para descarregar, contacto de suporte (definido
    pelo administrador) e a versão da aplicação.
  A chave da IA, a pesquisa na web (Tavily) e as Salas online continuam no **Perfil → Administração da app**, que só o
  administrador vê.
- **Os teus dados (RGPD)**: Definições → Privacidade e segurança → descarregar tudo (.zip, sem chaves) ou, em Conta e
  perfil, apagar a conta e os dados.

## Início de sessão, contas e administração

Ao abrir a app aparece o ecrã de entrada, como nas outras apps: o cartão «Iniciar sessão» com email e palavra-passe e,
em baixo, «Ainda não tens conta? **Criar conta**» (só o email e a palavra-passe). Por cima aparecem os
botões **Continuar com Google**, **Microsoft**, **Apple** ou **Facebook** que já estiverem ligados: carregas, escolhes a
conta e entras. À direita há uma pré-visualização da app.

- **Primeira entrada** (logo a seguir a criar a conta): um cartão por pergunta, com os passos em cima.
  1. **Como vais usar o Mondego IA?** — «Sou aluno» ou «Sou professor» (é a primeira pergunta e decide o resto; aqui
     também se podem trazer os dados de outro computador, .zip). 2. **Como te chamas?** 3. **Onde estudas?** (nível,
     instituição, grau e curso, ou a área no secundário) ou, para professores, **Onde ensinas?** (nível, instituição e
     departamentos, ou as disciplinas no secundário). Quem gere a app e ainda não tem a chave da IA vê mais um passo
     para a ligar. Não se criam salas nem se juntam documentos aqui: isso faz-se dentro da app. No fim, o nome e
     «aluno ou professor» passam para a conta (é o que os colegas veem nas salas). Até lá, a conta nova tem o próprio
     email como nome. Muda-se depois no Perfil → editar o perfil académico.
- **Aluno ou professor muda a app.** Para quem é **professor**: o Início mostra as turmas (alunos, mensagens novas),
  os avisos, o Assistente por voz, o calendário e **Preparar com a IA** (planear uma aula, criar uma ficha de
  exercícios, fazer um teste com critérios — cada um abre uma conversa com o pedido já feito); não há plano de estudo
  nem cronómetro no Início. O assistente sabe que fala com um professor (ajuda a ensinar, não a estudar para
  avaliações). Em «Criar sala» a primeira escolha é **Turma** (os alunos entram com o código) e há «Só para mim»
  para preparar as aulas.
- **Cada pessoa tem os seus dados.** O perfil, as cadeiras, as avaliações, as conversas e as preferências (cor,
  velocidade, idioma) ficam em `utilizadores/<id da conta>/`. Ninguém vê os dados dos outros.
- **Os dados de antes das contas** passam, na primeira vez, para a primeira conta que entra (no computador do dono). Os
  originais ficam guardados em `antes_das_contas/`, para nada se perder.
- **«Manter a sessão iniciada»** fica só nesse browser (cookie): cada telemóvel, tablet ou computador tem a sua sessão. A
  sessão termina em «Terminar sessão» (no perfil, na barra lateral) ou ao fim de 30 dias.
- **Uma só conta para tudo**: é a mesma das Salas e do 3D Studio. Com o Google (ou outro), liga-se à conta com o mesmo
  email.
- **«Apagar a conta e os dados»** (Definições → Conta e perfil) apaga só a conta e os dados dessa pessoa.
- **Administração (só para quem gere a app).** As «coisas da API» nunca aparecem aos utilizadores: a chave da IA, a
  pesquisa na web (Tavily), as Salas online (Supabase) e as credenciais do Google, Microsoft, Apple e Facebook estão no
  **Perfil → Administração da app**, que só os administradores veem. A primeira conta que entra fica administradora (ou
  os emails em `[admin]` no `secrets.toml`). Aos outros, se faltar a chave, a app só diz «Avisa quem gere a app».
- **Chaves no servidor**: em vez do Perfil, podem ir para `.streamlit/secrets.toml` (`[ia]`, `[supabase]`, `[admin]`;
  ver `secrets.toml.exemplo`). Nunca são escritas no `config.json` nem exportadas.
- **Ligar o Google** (feito uma vez pelo administrador, no Perfil → Administração → Início de sessão): consola da Google
  Cloud, ID do cliente OAuth do tipo Aplicação Web, URI `http://localhost:8501/oauth2callback` (ou o endereço da app
  publicada) e publicar a app no ecrã de consentimento. Microsoft: Microsoft Entra ID, contas pessoais. Facebook e Apple:
  pelo Auth0 (o Apple pede uma conta de programador da Apple, paga). É preciso o Authlib.
- Não há «Esqueci-me da palavra-passe» no modo local, porque a app não envia emails.
- **Online (Supabase):** as contas e os dados ficam no Supabase; ver «Publicar a app».

## Usar no telemóvel e no tablet

**No telemóvel, a app comporta-se como a do Claude** (o computador fica como está):
- abre na **conversa nova**, pronta para escrever, com a saudação ao meio e a caixa fixa no fundo (se escolheres outra
  página inicial em Definições → Personalização, abre essa);
- o **menu** (botão redondo ☰) começa fechado; ao abrir desliza da esquerda e ocupa quase o ecrã, a página fica
  encostada à direita, esbatida, e tocar nela fecha o menu; escolher uma página também o fecha; **+ Nova conversa**
  fica numa pílula no fundo do menu;
- no **+** da caixa aparece **Tirar fotografia** (no computador é **Tirar captura de ecrã**);
- a página está marcada como **português de Portugal** e sem tradução automática: antes, o browser do telemóvel
  traduzia-a sozinho (os ícones apareciam como palavras e o texto em português do Brasil). Se o browser ainda oferecer
  tradução, escolhe «Nunca traduzir este site».

- **Na mesma rede Wi-Fi (já funciona):** com a app aberta no computador, o PowerShell mostra o «Network URL» (por
  exemplo `http://192.168.1.20:8501`). Abre esse endereço no telemóvel ou no tablet e entra com o email e a palavra-passe.
  Cada pessoa entra com a sua conta. O Google não funciona por este endereço (a Google só aceita `localhost` ou `https`).
- **Em qualquer lado:** publica a app (secção seguinte). Fica com um endereço `https` que abre em qualquer telemóvel,
  tablet ou computador, e os dados de cada pessoa ficam guardados online.

## Publicar a app (online, com os dados no Supabase)

Com o Supabase ligado, cada conta e os seus dados (perfil, conversas, cadeiras com os documentos, avaliações) ficam
guardados na base de dados do Supabase. A app traz os dados ao entrar e envia uma cópia sempre que grava, por isso o
disco do servidor pode apagar-se (como no Streamlit Community Cloud quando a app reinicia) sem se perder nada. Tudo é
grátis para começar; não é preciso cartão.

**1. Supabase (contas e dados)**

1. Em [supabase.com](https://supabase.com) cria uma conta e um projeto novo (escolhe uma região na Europa e guarda a
   palavra-passe da base de dados).
2. **SQL Editor → New query**: cola todo o `supabase/esquema.sql` e carrega em **Run**.
3. **Storage → New bucket**: cria um bucket **privado** chamado `salas` (ficheiros das Salas).
4. **Project Settings → API Keys**: copia o **Project URL** e a chave **anon / public** (ou a **publishable**,
   `sb_publishable_…`). **Nunca** uses a `service_role` / `secret`: a app recusa-a.
5. **Authentication → Sign In / Providers → Email**: deixa **Confirm email** ligado (assim ninguém cria uma conta com
   o email de outra pessoa). O envio de emails grátis do Supabase tem limites baixos; com muita gente, configura um
   SMTP próprio em **Authentication → Emails**.
6. **Google** (o mesmo para **Azure** = Microsoft, **Facebook** e **Apple**): em **Sign In / Providers → Google**, liga-o
   e cola o Client ID e o Client Secret criados na consola da Google Cloud (ID do cliente OAuth, Aplicação Web). Na
   Google, o URI de redirecionamento autorizado é o que o Supabase mostra nessa página
   (`https://<o-teu-projeto>.supabase.co/auth/v1/callback`). Só aparecem na app os botões dos fornecedores ligados aqui.
7. **Authentication → URL Configuration**: em **Site URL** põe o endereço da app (ex.:
   `https://mondego-ia.streamlit.app`) e em **Redirect URLs** junta `https://mondego-ia.streamlit.app/**`.

**2. GitHub (o código)**

Cria um repositório (pode ser privado) e envia a pasta da app. O `.gitignore` deixa de fora os dados das pessoas, o
`config.json` e o `secrets.toml`. No PowerShell, dentro da pasta da app:

```powershell
git init
git add .
git status          # confirma que não aparece secrets.toml, config.json, perfil.json, dados/ nem utilizadores/
git commit -m "Mondego IA"
git branch -M main
git remote add origin https://github.com/O-TEU-UTILIZADOR/mondego-ia.git
git push -u origin main
```

**3. Streamlit Community Cloud (a app online)**

1. Em [share.streamlit.io](https://share.streamlit.io) entra com o GitHub → **Create app** → escolhe o repositório, o
   ramo `main` e o ficheiro `app.py`, e escolhe o endereço (ex.: `mondego-ia`).
2. Em **Advanced settings**, escolhe a versão mais recente do Python e cola em **Secrets** (com os teus valores):

```toml
[app]
url = "https://mondego-ia.streamlit.app"

[admin]
emails = ["o-teu-email@gmail.com"]   # só estas contas veem a Administração

[ia]
fornecedor = "Gemini"
gemini = "a tua chave do Google AI Studio"
# tavily = "tvly-..."                 # opcional: pesquisa em toda a web

[supabase]
url = "https://o-teu-projeto.supabase.co"
chave = "a chave anon ou publishable"
```

3. **Deploy**. Online, a secção `[auth]` não é precisa: quem trata do Google, da Microsoft, do Facebook e da Apple é o
   Supabase. As chaves ficam só nos segredos do servidor: nenhum utilizador as vê (nem o administrador, no browser).

**4. Levar os teus dados do computador para a app online**

1. Na app do computador: **Definições → Privacidade e segurança → Preparar o .zip** e descarrega.
2. Na app online: **Criar conta** (com o email que está em `[admin]`) ou **Continuar com Google**.
3. No primeiro ecrã aparece «**Já usavas o Mondego IA noutro computador? Traz os teus dados (.zip)**»: escolhe o
   ficheiro, marca «Substituir os dados desta conta pelos do ficheiro» e carrega em **Importar**. (Também está em
   Definições → Privacidade e segurança.) Os modelos do 3D Studio não vão no .zip.

**Como funciona e limites**

- **Sessão por dispositivo:** «Manter a sessão iniciada» guarda no browser um código do Supabase que muda sempre que a
  sessão se renova. «Terminar sessão» termina-a também no Supabase. Sem internet ao abrir, a sessão não se perde.
- **Sem ligação a meio:** a app continua com o que está no servidor e envia o que ficou por enviar quando a ligação
  voltar (enquanto o servidor não reiniciar).
- **Dois dispositivos ao mesmo tempo:** cada ficheiro (o perfil com as conversas, cada cadeira, as avaliações) fica com
  a última gravação. Uma cadeira apagada num dispositivo desaparece também nos outros.
- **Apagar a conta** (Definições → Conta e perfil) apaga a conta e os dados no Supabase (função `apagar_a_minha_conta`).
- **A app no computador** continua a funcionar como antes, com as contas e os dados deste computador. Se puseres a mesma
  secção `[supabase]` no `secrets.toml` do computador, passa a usar as contas e os dados online.
- **Testes:** `testes_nuvem.py` testa a ligação com um Supabase simulado (`supabase/servidor_falso.py`), sem internet.
  **Ainda não foi testada com um projeto Supabase a sério**: se algum passo falhar, a mensagem de erro do Supabase
  aparece na app.

## Salas

**Ícone da sala**: cada sala tem um ícone (Matemática, Física, Química, Biologia, Programação, História, Línguas…),
escolhido ao criar a sala ou nas Definições da sala. Em «Automático», a app escolhe-o pelo nome, pela cadeira e pela
descrição (por exemplo, «Grupo de Álgebra» → funções; «estudos» ou «Revisões» → escola, se o nome não disser a
matéria; sem pistas, um grupo fica com «Grupo»). Aparece no cartão da sala e no cabeçalho, num quadrado com a cor da
sala, e na barra lateral do computador também num quadradinho com a cor da sala (no telemóvel a barra fica como estava). Fica guardado na sala (`icone`; no Supabase, a coluna `icone` do `esquema.sql` — um projeto que ainda não a
tenha continua a funcionar, só sem o ícone escolhido).

- **Só há Salas** (as cadeiras passaram a ser salas). Há dois tipos:
  - **Só tuas**: as antigas cadeiras aparecem aqui sozinhas, com tudo o que tinham (os ficheiros de dados não mudam).
    Têm as fontes, a conversa com elas, resumos, quizzes, flashcards, testes, o plano e as avaliações.
  - **Partilhadas**: grupos de estudo (alunos) e **turmas** (professores), com materiais, conversa ou avisos,
    assistente da sala, membros e, se quiseres, Laboratório. Convites por **código** ou **link** (`?sala=CÓDIGO`).
- **Lista**: todas num só sítio, em cartões clicáveis com o ícone na cor da sala. As só tuas mostram «Só tu», a próxima
  avaliação e quanto falta, as fontes e os flashcards para rever; as partilhadas mostram o papel, os membros, os
  documentos e «Laboratório»/«Avisos». Com **pesquisa** e filtros (**Todas**, **Só tuas**, **Partilhadas**). Em baixo
  vê-se com que conta estás (é a mesma da app). Sem salas, a página explica o que fazer (diferente para alunos e
  professores).
- **Criar sala** (botão no topo ou «Nova sala» na barra lateral): primeiro **para quem é** — «Só para mim» ou «Com
  colegas» (para professores: «Turma» ou «Só para mim»), depois o nome, a descrição e a **aparência**: a cor (cada uma
  com a sua bolinha) e o ícone, com a sala a aparecer logo como vai ficar. Nas partilhadas, as regras e o Laboratório
  estão em «Regras e Laboratório». As **Definições** de cada sala têm a mesma aparência com pré-visualização.
- **Sala aberta**: «← Salas», nome e descrição grandes, fotografias dos membros, **Convidar** (código e link) e
  **Definições** (só o criador); as secções são separadores.
- **Conversa** como numa app de mensagens: as tuas à direita, as dos outros com nome e fotografia, separadores por dia
  (Hoje, Ontem, data), mensagens seguidas da mesma pessoa juntas, a lista começa nas mais recentes e a caixa de escrever
  fica em baixo. O texto é mostrado tal como foi escrito (nada de HTML). Apagar mensagens fica em «Apagar mensagens».
- **Assistente da sala**: ecrã de boas-vindas com ideias para começar (um clique pergunta), botão de copiar em cada
  resposta e «Nova conversa».
- **Só quem cria a sala a configura** (ao criar e depois em **Definições**):
  - **Conversa entre membros**: todos escrevem, **só eu escrevo** (canal de avisos) ou sem conversa;
  - **Quem pode pôr documentos nos materiais da sala**: só eu ou todos os membros;
  - **Ficheiros privados** de cada membro (só ele e o seu assistente os veem): sim ou não;
  - **Assistente de IA da sala**: ligado ou desligado;
  - **Quem vê o código de convite** (todos ou só eu) e **aceitar novos membros** (fechar a sala);
  - nome, descrição, cor e um **aviso fixo** que aparece no topo da sala.
  Por omissão, nas salas de cadeira só o professor publica e escreve avisos; nos grupos de estudo todos partilham e
  conversam.
- O criador também **modera**: apaga documentos e mensagens de outros, **remove membros** e **gera um código novo**
  (o antigo deixa de funcionar). Os membros podem sair da sala.
- **Secções de cada sala** (só se desenha a que está aberta): **Assistente** (responde só com os documentos que podes
  ver, com as fontes), **Laboratório** (se a sala o tiver), **Materiais** (da sala e os teus privados, com descarregar),
  **Conversa** ou **Avisos** (atualiza a cada 5 segundos) e **Membros** (fotografias, papéis e convite).
- **Regras e Laboratório** (salas partilhadas): as **funcionalidades e regras** e o **Laboratório**: «Ativar Laboratório nesta
  sala» e, se estiver ligado, as ferramentas que os membros vão ter, por área (História e Geografia, Biologia, Química,
  Física, Matemática, Programação). As escolhas ficam guardadas na sala (também no Supabase: colunas `laboratorio` e
  `ferramentas_lab`) e mudam-se em **Definições**. Sem Laboratório, a sala não mostra nada dele.
- As salas antigas passam sozinhas para o formato novo (a conversa e quem publica são deduzidos das definições antigas).
- **Modo local** (por defeito): funciona já neste computador, com contas próprias (palavras-passe guardadas com scrypt).
  Serve para experimentar, por exemplo com uma conta de professor e outra de aluno.
- **Modo Supabase** (para colegas noutros computadores): cria um projeto em supabase.com, corre
  `supabase/esquema.sql`, cria o bucket privado `salas` e cola o Project URL e a chave anon em
  **Perfil → Administração → Salas online**. Este modo ainda não foi testado com um projeto real.

## Laboratório (dentro das salas)

O Laboratório está em cada sala que o tenha ligado (Salas → Criar sala → «Ativar Laboratório nesta sala»). Quem cria a
sala escolhe as ferramentas; os membros usam-nas dentro da sala, por áreas e ferramentas no topo. As ferramentas de
História e Biologia podem usar **os materiais da sala** («Usar os materiais da sala»: só os documentos que podes ver).
O trabalho de cada pessoa (explicações, análises, cronologias, comparações, resumos, testes, glossário) fica em
`laboratorio.json`, na pasta da conta (e no Supabase, com a app publicada). Para fazer um laboratório só para ti, cria
uma sala só tua.

**História e Geografia** — um assistente de aprendizagem histórica:

- **Explicar**: contexto, causas, desenvolvimento, tabela dos principais acontecimentos, consequências, personagens,
  importância histórica, **factos e interpretações** e «Para memorizar», ao nível do aluno (secundário/superior).
- **Documentos**: cola ou carrega um documento (PDF, Word, imagem…): natureza da fonte, autor e data **com grau de
  certeza** (confirmado, aproximado, incerto), contexto, assunto, intenção do autor, público-alvo, mensagem, relação
  com os acontecimentos e, separados, **factos**, **interpretações** e **o que não se pode confirmar**.
- **Cronologia**: linha do tempo interativa; cada acontecimento com data, descrição, contexto, importância, relações
  (só com acontecimentos da própria cronologia, também num esquema) e grau de certeza.
- **Comparar**: períodos, regimes, revoluções, civilizações ou personagens numa tabela por critérios, com
  semelhanças, diferenças, conclusão e debates entre historiadores.
- **Testes**: escolha múltipla, verdadeiro/falso, associação, desenvolvimento e análise de documentos. As objetivas
  corrigem-se na app (resultado exato); as abertas, pela IA, com critérios. No fim: nota, temas fortes e a melhorar,
  conselhos e a resposta modelo de cada pergunta. O teste seguinte é **adaptativo** (insiste nos temas fracos e muda a
  dificuldade com os resultados).
- **Resumos**: por tema, período, acontecimento, capítulo (dos materiais) ou objetivo de estudo, com datas-chave,
  conceitos, personagens e causas → consequências.
- **Mapas**: os mapas interativos de sempre.
- **Rigor**: as instruções proíbem inventar datas, nomes ou acontecimentos; com «Pesquisar na web» ligado, a
  cronologia e a comparação usam fontes da web (Wikipédia, ou toda a web com a Tavily) e a explicação e o resumo usam a
  pesquisa Google (ou a da app); as fontes aparecem sempre. A IA pode errar: confirma as datas importantes.

**Biologia**:

- **Explicar**: definição, funcionamento, componentes, processos, exemplos, relações, erros comuns.
- **Processos passo a passo**: mitose, meiose, fotossíntese, respiração celular, síntese proteica, replicação do DNA,
  transcrição e tradução, transporte através da membrana, circulação sanguínea e sistemas do organismo — conteúdo
  escrito para o ensino (não depende da IA), com esquema e etapas numeradas. Na mitose e na meiose, a **divisão celular
  desenhada fase a fase** (2n = 4, cromossomas de origem materna e paterna, crossing-over). Outros processos: a IA
  organiza-os em etapas.
- **Genética**: **exercícios gerados e corrigidos na app** (monoibridismo, cruzamento-teste, diibridismo,
  hereditariedade ligada ao X, grupos sanguíneos AB0) com a resolução passo a passo e o quadro de Punnett; o quadro de
  Punnett e «Do DNA à proteína» de sempre; e o equilíbrio de **Hardy-Weinberg**.
- **Experiências**: problema, hipótese, variáveis (independente, dependente, controladas), controlo, procedimento,
  resultados, conclusões, erros experimentais e o que não se pode concluir.
- **Gráficos e dados**: carrega uma tabela (CSV/Excel) — a app faz o gráfico e calcula mínimo, máximo, média e
  tendência, e a IA interpreta com esses números — ou uma fotografia de um gráfico.
- **Testes**: escolha múltipla, resposta curta, desenvolvimento, associação, interpretação de experiências e análise de
  gráficos/tabelas, com correção, diagnóstico e o próximo teste adaptado.
- **Glossário**: conceito, definição, exemplo e conceitos relacionados; pesquisa, apagar e descarregar em CSV.
- **Simulações**: divisão celular, **osmose** (soluto de cada lado da membrana e o fluxo de água até ao equilíbrio) e
  simulações pedidas à IA.

**Química** (IA, tabela periódica, massa molar, acerto de equações, moléculas 3D do PubChem), **Física** (IA com
simulações a pedido), **Matemática** (IA, gráficos 2D e 3D) e **Programação** (IA, editor de Python no browser com
exercícios) continuam iguais, agora como ferramentas das salas. A IA de cada área explica e, a pedido, faz um modelo
(simulação, esquema, linha do tempo ou mapa); as simulações da IA correm isoladas (sem acesso à app nem à internet).

## De onde vêm as respostas (assistente)

Escolhe-se no «+» da conversa e em Definições → Inteligência artificial (o texto da caixa de conversa diz o modo):

- **Só os meus documentos**: a IA responde só com os excertos dos teus documentos, cita ficheiro e página e diz «Isto não está nos teus documentos» quando não está; não junta conhecimento geral nem a web. Sem documentos, a app avisa logo (sem gastar um pedido à IA).
- **Documentos e conhecimento da IA**: os documentos primeiro; o resto vem do que a IA sabe, e ela diz que não vem deles.
- **Também a web (fontes fiáveis)**: pesquisa na web em sites oficiais, universidades, revistas científicas e obras de referência; a Wikipédia não serve de fonte (ver `pesquisa_web.py`).

Velocidade (`desempenho.py`): o modelo «pensa» o mínimo nas perguntas simples e nos títulos, pouco no normal e mais nas difíceis em «Equilibrada»; a temperatura só vai para os modelos que a usam; as instruções e a conversa vão primeiro e os excertos e a pergunta nova no fim, para a Google reaproveitar o início do pedido (cache implícita); a pesquisa de reserva faz as consultas ao mesmo tempo e não espera mais de 8 s por site.

## Velocidade das respostas

Medido com a IA simulada (`bench_desempenho` dos testes), com as cadeiras reais do teu computador:

- A lista de modelos da Google fica em cache 1 hora (antes: um pedido antes de **cada** resposta e de cada título).
- A IA recebe só os excertos dos documentos que interessam à pergunta: o pedido passou de ~130 mil caracteres para
  ~7 mil numa pergunta sem relação com os documentos e ~38 mil numa pergunta sobre eles.
- Sem quota da pesquisa Google, a app deixou de tentar todos os modelos (6 chamadas em série antes do primeiro texto
  → 2) e lembra-se disso 30 minutos para todas as sessões.
- **Modelo por tarefa**: títulos e perguntas simples vão para o modelo mais rápido (flash-lite); contas, «passo a
  passo», código, análises e documentos anexados vão para um modelo flash completo, mesmo na velocidade «Rápida».
  A escolha manual de modelo (Administração) continua a mandar.
- As secções das salas só se desenham quando estão abertas (a conversa da sala deixou de se atualizar a cada 5 segundos
  noutras secções).

## 3D Studio (escondido por agora)

O 3D Studio está **escondido** (não aparece na barra lateral, no Laboratório nem no assistente de voz), mas todo o código
e os modelos guardados continuam na app. Para voltar a mostrá-lo: no `config.json`, acrescenta `"estudio3d": true`
(e volta a abrir a app).

Três secções: **Explorar** (biblioteca da comunidade, pesquisa e filtros), **Criar com IA** e **Os meus modelos**.

- **Criar com IA**: escreves exatamente o que queres e a IA faz isso mesmo (as opções de tipo, detalhe, complexidade e
  estilo estão em «Opções» e por omissão ficam em «Automático»). No fim, «Verificar e completar» compara o modelo com o
  teu pedido e corrige o que faltar. O modelo é feito de peças geométricas reais (esferas, tubos, superfícies de
  revolução, formas orgânicas, extrusões...), cada uma com nome, grupo, cor, material, etiqueta, explicação, função e um
  «Sabias que…». Também podes abrir ficheiros **GLB/glTF** ou `.mondego3d.json`.
- **Visualizador**: rodar, aproximar, clicar numa peça (nome, grupo, explicação, função, curiosidade, **Isolar**,
  **Centrar**, **Esconder**), etiquetas que não se sobrepõem, sombras, corte transversal, vista explodida, capturar a
  capa e descarregar em `.glb`.
  - **Estruturas**: lista das peças por grupo, procurar, esconder/mostrar cada uma e **Raio-X** (transparência).
  - **Testa-te**: o visualizador pede-te para encontrares estruturas no modelo e dá a pontuação no fim.
- **Edição por conversa**: pedes alterações em linguagem natural; a IA altera só o que pediste (ou só a peça selecionada).
  Também há edição direta da peça (cor, material, opacidade, etiqueta, tamanho, visibilidade).
- **Versões**: cada alteração fica guardada. **Desfazer** e **Recuperar** nunca apagam o histórico. **Duplicar** cria uma cópia.
- **Publicar**: título, descrição, categoria, etiquetas, capa, visibilidade (pública ou privada) e créditos/licença.
  Os públicos aparecem logo na pesquisa; os privados só para ti e para quem partilhares (por email).
- **Remix com IA**: em modelos públicos com licença que o permita, cria uma cópia tua com os créditos do original. O
  original nunca muda.
- Usa as mesmas contas das Salas. No modo deste computador tudo fica em `salas_local.sqlite`.

### Motor Blender (modelos muito mais detalhados)

O Blender refaz as peças de cada modelo com muito mais qualidade: **arestas arredondadas** (caixas, cilindros, placas),
**superfícies lisas com relevo natural** (órgãos, células, rochas), **rebordos suaves** (vasos, garrafas, colunas) e
**materiais físicos** (metal, vidro com transparência real, verniz, tecido, luz). O ficheiro vem comprimido (Draco), por
isso abre depressa.

- Acontece **sozinho** depois de a IA criar ou alterar um modelo (Perfil → Administração → Chave da IA → Motor Blender → «Melhorar
  automaticamente»). Por baixo do visualizador diz se o modelo está desenhado com o Blender e há o botão **Melhorar com o
  Blender** / **Refazer no Blender**.
- A cor, a posição, o tamanho, as etiquetas e os textos continuam editáveis sem voltar ao Blender. Se mudares a forma de
  uma peça, só essa volta a ser simples até carregares em «Refazer no Blender».
- **Neste computador**: a app encontra o Blender instalado (aqui: `C:\Program Files\Blender Foundation\Blender 5.2`).
  Em Perfil → Administração → Chave da IA → Motor Blender há **Testar o Blender**, que constrói um modelo de teste.
- **Para todos os utilizadores (app online)**: o Blender tem de estar num servidor sempre ligado. Na pasta
  `servidor_blender` está tudo pronto:
  1. `docker build -f servidor_blender/Dockerfile -t mondego-blender .` (na pasta da app; instala o Blender 4.5 LTS);
  2. `docker run -p 8080:8080 -e MONDEGO_TOKEN=uma-chave-longa-e-secreta mondego-blender` num serviço com HTTPS
     (por exemplo um VPS ou um alojamento de contentores; é pago, normalmente poucos euros por mês);
  3. na app online, em `.streamlit/secrets.toml`: `[blender]` com `url = "https://..."` e `token = "a mesma chave"`
     (ou em Perfil → Administração → Chave da IA → Servidor Blender, com «Testar ligação»).
- Segurança: o Blender só recebe a forma das peças em JSON e corre sempre o mesmo script; nunca executa código vindo da
  IA nem dos utilizadores. O servidor pede a chave em todos os pedidos.

### O que depende de serviços externos

| Funcionalidade | Estado |
|---|---|
| Criar e editar modelos com o Gemini | Funciona com a chave Gemini que já usas. |
| Malhas 3D realistas (Meshy) | **Preparado, não testado.** Falta uma chave da API Meshy (serviço pago, meshy.ai) em Perfil → Administração → Chave da IA. |
| Biblioteca partilhada entre computadores | **Não testada.** Precisa do Supabase: corre `supabase/esquema.sql` (inclui a secção 3D Studio) e liga-o em Perfil → Administração → Salas online. |
| Visualizador, simulações, mapas e Python no browser | Precisam de internet para carregar Three.js, Leaflet, OpenStreetMap e Pyodide (ficam em cache). |
| Moléculas 3D | Dados do PubChem (precisa de internet). |
| Assistente por voz | Permite o microfone. Com a chave do Gemini, a app transcreve a gravação com a Google (funciona em qualquer browser recente); sem ela, usa o reconhecimento de voz do browser (**Chrome ou Edge**). O microfone só funciona em `localhost` ou `https` (no telemóvel pelo endereço da rede local, `http://192.168…`, o browser não o deixa usar). A fala usa a voz **Charon** da Google (modelo TTS do Gemini, com a tua chave); sem ela, a voz do browser. |
| Motor Blender | Usa o Blender instalado neste computador. **Para todos os utilizadores** precisa do servidor Blender (`servidor_blender`, Docker) num alojamento com HTTPS: preparado e testado sem o Blender (pedidos, chave, validação); a imagem Docker ainda não foi construída. |
| Login com Google / Facebook / Microsoft | **Por configurar.** Precisa das credenciais em `.streamlit/secrets.toml` e do `Authlib` (ver acima). |
