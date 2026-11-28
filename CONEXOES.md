# Conexões do Áfricas Play (fonte única para todas as conversas)

Toda conversa nova do Claude lê este arquivo ANTES de responder ao Washington, e nunca diz que algo "não está conectado" sem checar aqui.
Toda conversa que fizer uma conexão nova, ganhar uma autorização ou mudar o estado de algo atualiza este arquivo na hora (commit no repositório).
A parte entre as marcas AUTOMATICO é refeita sozinha pelo robô conexoes.yml sempre que um robô muda.

## Como acessar
- Repositório principal: portalafricas-jpg/automacao-africas. Numa conversa nova, se o GitHub não responder, usar add_repo (owner=portalafricas-jpg, repo=automacao-africas, access=push) e clonar. Não perguntar ao Washington.
- Segundo repositório: portalafricas-jpg/aplicativo-africasplay (landing pages em aplicativo.africas.com.br, GitHub Pages).
- Rodar um robô: gh api -X POST repos/portalafricas-jpg/automacao-africas/actions/workflows/ARQUIVO.yml/dispatches -f ref=main
- Regra de ouro: se existe API ou robô, usar a API ou o robô. Chrome só quando não houver outro caminho. Não gastar (teto da API do Claude: US$ 10 por dia).
- Nunca pedir chave nem print de chave ao Washington: as chaves ficam nos Secrets do GitHub.
- VÍDEOS (.mp4) NUNCA vão para o galho main (o histórico engorda para sempre). Guardar com `bash guardar_midia.sh "mensagem" caminho/do/video.mp4` (vai para o galho "midia"); os robôs leem com midia.arquivo(). O robô limpa-midia.yml apaga o que tem mais de 7 dias. O .gitignore já barra .mp4 no main.
- Gastos: o robô vigia-gastos.yml confere todo dia útil às 9h espaço do repositório, gasto do Claude e saúde dos robôs; relatório às segundas e alerta vermelho na hora, por e-mail (aviso do GitHub).

## Já conectado
- Meta: Instagram @africasplay e Facebook da página Africas Play (publicar carrossel, story, Reels; ler comentários e métricas).
- Meta, Instagram pessoal @washington_andrade1 (página "Washington Lúcio Andrade"): desde 28/11/2026 a chave META_USER_TOKEN (app AutoShareAfricas, id 3283028915244924) alcança essa página e esse Instagram, com permissão de publicar. As chaves de usuário e de página não vencem; o acesso aos dados vence em 20/02/2027 e se renova com o uso. Desde 28/11/2026 o robô copia carrossel e story no Instagram pessoal, com legenda em primeira pessoa (pessoal.py).
- YouTube: canal @Africasplay (subir vídeos e Shorts, trocar capas, editar textos, playlists, privar).
- API do Claude (robôs do portal, redes, comentários, grupos, assessorias).
- Gmail dos robôs (envio e leitura dos e-mails das assessorias).
- Cloudflare: ATENÇÃO, em 28/11/2026 o robô achou a chave CLOUDFLARE_API_TOKEN vazia no cofre (o formulário das assessorias nunca chegou a ser publicado: não existe assessorias/formulario.json). Falta guardar a chave de novo.
- Unsplash (fotos de reserva).
- Voz gratuita (narração): VoxCPM2, motor de licença Apache-2.0 do VoiceStudio, roda no próprio GitHub sem chave e sem custo (workflow teste-voz.yml). Duas vozes aprovadas por Washington em 27/11/2026: masculina de locutor e feminina de apresentadora. Ainda não ligada aos robôs de vídeo.
- Site africas.com.br: lê os 6 RSS do robô em feeds/ (politica, mundo, cotidiano, cultura, ancestralidade, protagonista). Publicar matéria = gravar no RSS da categoria.
- cron-job.org (conta do Washington): aciona robô do portal (:02, :17, :32, :47), robô das redes e Comente APP.
- Conectores do Claude na conta: Gmail, Google Agenda, Google Drive, Docs, Planilhas, Slides, Canva, Cloudflare, Claude Docs, memória. Claude in Chrome só com o computador do Washington ligado.

## Falta conectar (foco atual: TikTok, Instagram pessoal, LinkedIn pessoal e LinkedIn da empresa)
- TikTok @africasplay: conta de desenvolvedor criada (portalafricas@gmail.com), organização "Áfricas Play" e app "Áfricas Play" (tipo Outro, categoria News, plataforma Web) em rascunho. Falta: verificar o domínio africas.com.br (registro TXT no DNS), ícone 1024x1024, produtos (Login Kit + Content Posting API/Direct Post), guardar Client key/secret nos Secrets e enviar para auditoria. Antes: pedir permissão de postagem e passar pela auditoria (antes dela, posts saem privados). Hoje o dlvr.it posta.
- Instagram pessoal do Washington (@washington_andrade1): autorização da Meta FEITA em 28/11/2026 (página e Instagram incluídos no app AutoShareAfricas, no perfil pessoal do Facebook). Esta sessão não grava Secrets (o GitHub bloqueia esse caminho), por isso a proposta é o robô tirar a chave da página nova na hora, a partir da META_USER_TOKEN, sem chave nova no cofre. Decidido em 28/11/2026: cópia automática (carrossel e story) com legenda em primeira pessoa. Pronto em pessoal.py e ligado ao redes.py, LIGADO em 28/11/2026 às 17h06 com o sim do Washington (pessoal-config.json). Prévia: robô pessoal-previa.yml (não publica). Reels no pessoal: fase 2.
- LinkedIn pessoal e LinkedIn do Áfricas: publicação por API exige aprovação da LinkedIn (Community Management API). Hoje: manual ou pelo Chrome.
- Threads: ajustar a bio; ligar a publicação por API.
- Flickr do Ministério da Igualdade Racial: falta a chave gratuita.
- ElevenLabs: substituída pelo VoxCPM2 gratuito (voz clonada do Washington ainda não testada). OneSignal (push do app), Google Analytics e AdSense: não ligados aos robôs.
- X (Twitter): não será pago.

## Histórico de mudanças (a mais nova em cima)
- 28/11/2026: tratamento de foto (tratamento_foto.py: rosto centralizado com YuNet/MIT, ampliação por IA FSRCNN/Apache 2.0, qualidade sem mudar o tom de pele, melhor foto da própria matéria) e Radar no HyperFrames (hyperframes_radar.py) prontos, atrás das chaves em video-config.json (desligadas até o sim do Washington). Prévia: robô previa-tratamento.yml. Modelos em modelos/. OpenCV fixado na versão 4. Troca de foto por nome na Wikipédia desligada (risco de homônimo). Volume -14 LUFS em todos os vídeos do Radar. ATENÇÃO: desde ~18h de 28/11 o site africas.com.br às vezes devolve página HTML (erro 415) no lugar das fotos para os robôs do GitHub (proteção do servidor); falar com a Portal Administrável.
- 28/11/2026 18h30: cópia automática do @africasplay no Instagram pessoal DESLIGADA (pessoal-config.json). Decisão do Washington: Instagram e LinkedIn pessoais só com conteúdo próprio, em primeira pessoa (CEO, palestrante, eventos e reuniões de que ele participa com o Áfricas). Em cada evento, duas linhas de conteúdo: a do Áfricas (redes, app, site, YouTube) e a pessoal.
- 28/11/2026: HyperFrames (gratuito, Apache 2.0) testado e funcionando no GitHub: robô teste-hyperframes.yml (só gera, não publica), com script em video-hyperframes/teste_hyperframes.py. Renderiza 24 s de Reels em cerca de 45 s, com Node 22 e o Chrome do próprio GitHub, sem chave. Prévia (atual × novo, -14 LUFS) enviada por e-mail para aprovação; vídeos no galho midia (ensaio/hyperframes).
- 28/11/2026: no perfil pessoal do Facebook, em Integrações comerciais > AutoShareAfricas, incluídos a página "Washington Lúcio Andrade" e o Instagram @washington_andrade1 (ver perfil, publicar, ler conteúdo e lista de páginas). Confirmado pelo robô teste-contas-meta.yml: a chave alcança 2 páginas. Esse robô agora também mostra o app que gerou a chave e a validade.
- 28/11/2026: criada a página do Facebook "Washington Lúcio Andrade" e ligada ao Instagram @washington_andrade1. Comente APP: avisos agora só por e-mail (não abre mais issue pública). Ícone do app em assets/marca/icone-app-1024.png. Termos também em https://aplicativo.africas.com.br/termos-de-uso-e-privacidade/.
- 28/11/2026: TikTok: verificação do domínio pedida por Washington à Portal Administrável (DNS de africas.com.br: ns1/ns2.portaladministravel.com.br), resposta só na segunda. Valor TXT: tiktok-developers-site-verification=I8IyaG4rZ0NlhzkbqyAtCrCxSvp5ThZe. Alternativa testada: arquivo de assinatura e página de termos em aplicativo.africas.com.br (repositório aplicativo-africasplay); o TikTok recusou 3 vezes (não achou a assinatura). Rascunho do app ainda não salvo: preencher de novo categoria News, descrição, links dos termos e plataforma Web depois da verificação.
- 28/11/2026: TikTok: conta de desenvolvedor, organização e app "Áfricas Play" criados (rascunho). O TikTok exige verificar o domínio dos termos: registro TXT pendente no DNS de africas.com.br.
- 28/11/2026: política de privacidade e termos para as redes (TikTok, Meta, LinkedIn, Threads): usar https://www.africas.com.br/termos-de-uso-e-privacidade (item 17 novo, contato redacao@africas.com.br). As páginas no Cloudflare (cloudflare/paginas.js) ficam descartadas.
- 28/11/2026: TikTok: decidido seguir só pela postagem direta (robô 100% automático, depois da auditoria). Páginas de privacidade e termos prontas em cloudflare/paginas.js (robô paginas-publicar.yml), mas a publicação falhou porque a chave do Cloudflare está vazia no cofre. Alternativa: publicar em aplicativo.africas.com.br/privacidade/ e /termos/ (repositório aplicativo-africasplay).
- 28/11/2026: voz padrão fixa: os robôs copiam a voz dos arquivos vozes-padrao/masculina.wav e feminina.wav (VoxCPM2 com prompt_wav_path + prompt_text + reference_wav_path). Sem isso, cada frase sai com uma voz diferente. Robôs do Calendário Afro: calendario-imagens, calendario-voz, calendario-voz-teste, calendario-voz-salvar. Artefatos do GitHub não baixam nesta sessão: guardar áudios em ramo (calendario-voz-teste, calendario-audio).
- 28/11/2026: histórico do galho main limpo de todos os vídeos .mp4 (cerca de 124 MB); o main caiu para uns 70 MB. Robô do portal passou a tentar de novo ao gravar.
- 28/11/2026: vídeos saem do galho main e vão para o galho "midia" (apagados após 7 dias pelo limpa-midia.yml); vigia de gastos (vigia-gastos.yml) ligado, com relatório semanal e alerta vermelho por e-mail.
- 27/11/2026: voz gratuita VoxCPM2 (do VoiceStudio) testada no GitHub e aprovada; substitui a ElevenLabs.
- 27/11/2026: arquivo criado a partir da conversa de automação.

<!-- AUTOMATICO:INICIO -->

### Robôs (gerado automaticamente a partir de .github/workflows)
- ajuste-buscas.yml: Ajuste semanal das buscas (agendado (UTC): 0 12 * * 1). Chaves: GITHUB_TOKEN
- alarme-repetidas.yml: Alarme de matérias repetidas (agendado (UTC): 30 10 * * *). Chaves: ANTHROPIC_API_KEY, GITHUB_TOKEN
- assessorias-envio.yml: Assessorias - envio de e-mails (acionado sob demanda ou pelo cron-job.org). Chaves: GMAIL_SENHA_APP
- calendario-imagens.yml: Calendário Afro - pesquisar imagens (acionado sob demanda ou pelo cron-job.org)
- calendario-voz-opcoes.yml: Calendário Afro - opções de voz (acionado sob demanda ou pelo cron-job.org)
- calendario-voz-salvar.yml: Calendário Afro - guardar áudios de um teste (acionado sob demanda ou pelo cron-job.org). Chaves: GITHUB_TOKEN
- calendario-voz-teste.yml: Calendário Afro - teste da voz padrão (acionado sob demanda ou pelo cron-job.org)
- calendario-voz.yml: Calendário Afro - gravar narração (acionado sob demanda ou pelo cron-job.org)
- comentarios.yml: Comente APP (acionado sob demanda ou pelo cron-job.org). Chaves: ANTHROPIC_API_KEY, FB_PAGE_ID, GMAIL_SENHA_APP, IG_USER_ID, META_PAGE_TOKEN
- conexoes.yml: Atualizar conexões (agendado (UTC): 17 11 * * 1)
- diagnostico-bing.yml: Diagnóstico do Bing (acionado sob demanda ou pelo cron-job.org)
- ferramentas-video.yml: Ferramentas de vídeo (transcrição e máscara) (acionado sob demanda ou pelo cron-job.org). Chaves: GITHUB_TOKEN
- formulario-publicar.yml: Assessorias - publicar formulário (acionado sob demanda ou pelo cron-job.org). Chaves: CLOUDFLARE_API_TOKEN
- grupos.yml: Links para os grupos do Facebook (agendado (UTC): 0 11 * * 1-5). Chaves: ANTHROPIC_API_KEY, GITHUB_TOKEN
- instagram-antigos.yml: Ligar posts antigos do Instagram às matérias (acionado sob demanda ou pelo cron-job.org). Chaves: IG_USER_ID, META_PAGE_TOKEN
- legenda-teste.yml: Legenda (transcrever) (acionado sob demanda ou pelo cron-job.org)
- limpa-midia.yml: Limpar depósito de mídia (agendado (UTC): 0 6 * * *). Chaves: GITHUB_TOKEN
- metricas.yml: Resultados das redes (agendado (UTC): 0 10 * * *). Chaves: FB_PAGE_ID, IG_USER_ID, META_PAGE_TOKEN
- paginas-publicar.yml: Publicar páginas de privacidade e termos (acionado sob demanda ou pelo cron-job.org). Chaves: CLOUDFLARE_API_TOKEN
- pessoal-previa.yml: Instagram pessoal - prévia (não publica) (acionado sob demanda ou pelo cron-job.org). Chaves: ANTHROPIC_API_KEY, META_USER_TOKEN
- previa-tratamento.yml: Prévia do tratamento de foto e do Radar novo (não publica) (acionado sob demanda ou pelo cron-job.org). Chaves: ANTHROPIC_API_KEY, GITHUB_TOKEN, GMAIL_SENHA_APP
- redes.yml: Robô das redes (acionado sob demanda ou pelo cron-job.org). Chaves: ANTHROPIC_API_KEY, FB_PAGE_ID, GMAIL_SENHA_APP, IG_USER_ID, META_PAGE_TOKEN, META_USER_TOKEN, YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN
- reels-agora.yml: Publicar Reels agora (teste) (acionado sob demanda ou pelo cron-job.org). Chaves: ANTHROPIC_API_KEY, FB_PAGE_ID, IG_USER_ID, META_PAGE_TOKEN
- robo.yml: Robô Áfricas (acionado sob demanda ou pelo cron-job.org). Chaves: ANTHROPIC_API_KEY, UNSPLASH_ACCESS_KEY
- testar-fontes.yml: Testar fontes (acionado sob demanda ou pelo cron-job.org)
- teste-contas-meta.yml: Teste das contas da Meta (só leitura) (acionado sob demanda ou pelo cron-job.org). Chaves: META_PAGE_TOKEN, META_USER_TOKEN
- teste-direct.yml: Teste do direct com botões (acionado sob demanda ou pelo cron-job.org). Chaves: FB_PAGE_ID, IG_USER_ID, META_PAGE_TOKEN
- teste-hyperframes.yml: Teste do HyperFrames (só gera vídeo, não publica) (acionado sob demanda ou pelo cron-job.org). Chaves: GITHUB_TOKEN, GMAIL_SENHA_APP
- teste-meta.yml: Teste da chave da Meta (acionado sob demanda ou pelo cron-job.org). Chaves: FB_PAGE_ID, IG_USER_ID, META_PAGE_TOKEN, META_USER_TOKEN
- teste-radar-hyperframes.yml: Teste do Radar com HyperFrames (só gera vídeo, não publica) (acionado sob demanda ou pelo cron-job.org). Chaves: ANTHROPIC_API_KEY, GITHUB_TOKEN, GMAIL_SENHA_APP
- teste-reels.yml: Teste do Reels (acionado sob demanda ou pelo cron-job.org). Chaves: ANTHROPIC_API_KEY, GITHUB_TOKEN
- teste-repetidas.yml: Teste do protocolo anti-repetição (só leitura) (acionado sob demanda ou pelo cron-job.org). Chaves: ANTHROPIC_API_KEY
- teste-voz.yml: Teste de vozes gratuitas (só gera áudio) (acionado sob demanda ou pelo cron-job.org)
- teste-youtube.yml: Teste do Radar no YouTube (acionado sob demanda ou pelo cron-job.org). Chaves: ANTHROPIC_API_KEY, YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN
- vigia-gastos.yml: Vigia de gastos (agendado (UTC): 0 12 * * 1-5). Chaves: GITHUB_TOKEN
- yt-canal.yml: Atualizar texto do canal do YouTube (acionado sob demanda ou pelo cron-job.org). Chaves: YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN
- yt-capas.yml: Trocar capas de vídeos no YouTube (acionado sob demanda ou pelo cron-job.org). Chaves: YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN
- yt-criar-playlist.yml: Criar playlist no YouTube (acionado sob demanda ou pelo cron-job.org). Chaves: YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN
- yt-dados.yml: Baixar dados de vídeos do YouTube (preparo de ajustes) (acionado sob demanda ou pelo cron-job.org). Chaves: YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN
- yt-diagnostico.yml: Diagnóstico do YouTube (acionado sob demanda ou pelo cron-job.org). Chaves: YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN
- yt-editar.yml: Editar descrição e tags de vídeos do YouTube (acionado sob demanda ou pelo cron-job.org). Chaves: YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN
- yt-playlist.yml: Pôr vídeo na playlist Radar (avulso) (acionado sob demanda ou pelo cron-job.org). Chaves: YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN
- yt-privar.yml: Deixar vídeos privados no YouTube (acionado sob demanda ou pelo cron-job.org). Chaves: YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN

### Chaves guardadas nos Secrets do GitHub (só os nomes) e quem usa
- ANTHROPIC_API_KEY: alarme-repetidas.yml, comentarios.yml, grupos.yml, pessoal-previa.yml, previa-tratamento.yml, redes.yml, reels-agora.yml, robo.yml, teste-radar-hyperframes.yml, teste-reels.yml, teste-repetidas.yml, teste-youtube.yml
- CLOUDFLARE_API_TOKEN: formulario-publicar.yml, paginas-publicar.yml
- FB_PAGE_ID: comentarios.yml, metricas.yml, redes.yml, reels-agora.yml, teste-direct.yml, teste-meta.yml
- GITHUB_TOKEN: ajuste-buscas.yml, alarme-repetidas.yml, calendario-voz-salvar.yml, ferramentas-video.yml, grupos.yml, limpa-midia.yml, previa-tratamento.yml, teste-hyperframes.yml, teste-radar-hyperframes.yml, teste-reels.yml, vigia-gastos.yml
- GMAIL_SENHA_APP: assessorias-envio.yml, comentarios.yml, previa-tratamento.yml, redes.yml, teste-hyperframes.yml, teste-radar-hyperframes.yml
- IG_USER_ID: comentarios.yml, instagram-antigos.yml, metricas.yml, redes.yml, reels-agora.yml, teste-direct.yml, teste-meta.yml
- META_PAGE_TOKEN: comentarios.yml, instagram-antigos.yml, metricas.yml, redes.yml, reels-agora.yml, teste-contas-meta.yml, teste-direct.yml, teste-meta.yml
- META_USER_TOKEN: pessoal-previa.yml, redes.yml, teste-contas-meta.yml, teste-meta.yml
- UNSPLASH_ACCESS_KEY: robo.yml
- YT_CLIENT_ID: redes.yml, teste-youtube.yml, yt-canal.yml, yt-capas.yml, yt-criar-playlist.yml, yt-dados.yml, yt-diagnostico.yml, yt-editar.yml, yt-playlist.yml, yt-privar.yml
- YT_CLIENT_SECRET: redes.yml, teste-youtube.yml, yt-canal.yml, yt-capas.yml, yt-criar-playlist.yml, yt-dados.yml, yt-diagnostico.yml, yt-editar.yml, yt-playlist.yml, yt-privar.yml
- YT_REFRESH_TOKEN: redes.yml, teste-youtube.yml, yt-canal.yml, yt-capas.yml, yt-criar-playlist.yml, yt-dados.yml, yt-diagnostico.yml, yt-editar.yml, yt-playlist.yml, yt-privar.yml

<!-- AUTOMATICO:FIM -->
