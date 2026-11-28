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

## Já conectado
- Meta: Instagram @africasplay e Facebook da página Africas Play (publicar carrossel, story, Reels; ler comentários e métricas).
- YouTube: canal @Africasplay (subir vídeos e Shorts, trocar capas, editar textos, playlists, privar).
- API do Claude (robôs do portal, redes, comentários, grupos, assessorias).
- Gmail dos robôs (envio e leitura dos e-mails das assessorias).
- Cloudflare (formulário das assessorias).
- Unsplash (fotos de reserva).
- Site africas.com.br: lê os 6 RSS do robô em feeds/ (politica, mundo, cotidiano, cultura, ancestralidade, protagonista). Publicar matéria = gravar no RSS da categoria.
- cron-job.org (conta do Washington): aciona robô do portal (:02, :17, :32, :47), robô das redes e Comente APP.
- Conectores do Claude na conta: Gmail, Google Agenda, Google Drive, Docs, Planilhas, Slides, Canva, Cloudflare, Claude Docs, memória. Claude in Chrome só com o computador do Washington ligado.

## Falta conectar (foco atual: TikTok, Instagram pessoal, LinkedIn pessoal e LinkedIn da empresa)
- TikTok @africasplay: criar app de desenvolvedor, pedir permissão de postagem e passar pela auditoria (antes dela, posts saem privados). Hoje o dlvr.it posta.
- Instagram pessoal do Washington: conta profissional; falta ligar a uma página do Facebook e à chave da Meta para postar pela API.
- LinkedIn pessoal e LinkedIn do Áfricas: publicação por API exige aprovação da LinkedIn (Community Management API). Hoje: manual ou pelo Chrome.
- Threads: ajustar a bio; ligar a publicação por API.
- Flickr do Ministério da Igualdade Racial: falta a chave gratuita.
- ElevenLabs (voz clonada), OneSignal (push do app), Google Analytics e AdSense: não ligados aos robôs.
- X (Twitter): não será pago.

## Histórico de mudanças (a mais nova em cima)
- 27/11/2026: arquivo criado a partir da conversa de automação.

<!-- AUTOMATICO:INICIO -->

### Robôs (gerado automaticamente a partir de .github/workflows)
- ajuste-buscas.yml: Ajuste semanal das buscas (agendado (UTC): 0 12 * * 1). Chaves: GITHUB_TOKEN
- alarme-repetidas.yml: Alarme de matérias repetidas (agendado (UTC): 30 10 * * *). Chaves: ANTHROPIC_API_KEY, GITHUB_TOKEN
- assessorias-envio.yml: Assessorias - envio de e-mails (acionado sob demanda ou pelo cron-job.org). Chaves: GMAIL_SENHA_APP
- comentarios.yml: Comente APP (acionado sob demanda ou pelo cron-job.org). Chaves: ANTHROPIC_API_KEY, FB_PAGE_ID, GITHUB_TOKEN, IG_USER_ID, META_PAGE_TOKEN
- conexoes.yml: Atualizar conexões (agendado (UTC): 17 11 * * 1)
- diagnostico-bing.yml: Diagnóstico do Bing (acionado sob demanda ou pelo cron-job.org)
- ferramentas-video.yml: Ferramentas de vídeo (transcrição e máscara) (acionado sob demanda ou pelo cron-job.org)
- formulario-publicar.yml: Assessorias - publicar formulário (acionado sob demanda ou pelo cron-job.org). Chaves: CLOUDFLARE_API_TOKEN
- grupos.yml: Links para os grupos do Facebook (agendado (UTC): 0 11 * * 1-5). Chaves: ANTHROPIC_API_KEY, GITHUB_TOKEN
- instagram-antigos.yml: Ligar posts antigos do Instagram às matérias (acionado sob demanda ou pelo cron-job.org). Chaves: IG_USER_ID, META_PAGE_TOKEN
- legenda-teste.yml: Legenda (transcrever) (acionado sob demanda ou pelo cron-job.org)
- metricas.yml: Resultados das redes (agendado (UTC): 0 10 * * *). Chaves: FB_PAGE_ID, IG_USER_ID, META_PAGE_TOKEN
- redes.yml: Robô das redes (acionado sob demanda ou pelo cron-job.org). Chaves: ANTHROPIC_API_KEY, FB_PAGE_ID, GMAIL_SENHA_APP, IG_USER_ID, META_PAGE_TOKEN, YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN
- reels-agora.yml: Publicar Reels agora (teste) (acionado sob demanda ou pelo cron-job.org). Chaves: ANTHROPIC_API_KEY, FB_PAGE_ID, IG_USER_ID, META_PAGE_TOKEN
- robo.yml: Robô Áfricas (acionado sob demanda ou pelo cron-job.org). Chaves: ANTHROPIC_API_KEY, UNSPLASH_ACCESS_KEY
- testar-fontes.yml: Testar fontes (acionado sob demanda ou pelo cron-job.org)
- teste-contas-meta.yml: Teste das contas da Meta (só leitura) (acionado sob demanda ou pelo cron-job.org). Chaves: META_PAGE_TOKEN, META_USER_TOKEN
- teste-direct.yml: Teste do direct com botões (acionado sob demanda ou pelo cron-job.org). Chaves: FB_PAGE_ID, IG_USER_ID, META_PAGE_TOKEN
- teste-meta.yml: Teste da chave da Meta (acionado sob demanda ou pelo cron-job.org). Chaves: FB_PAGE_ID, IG_USER_ID, META_PAGE_TOKEN, META_USER_TOKEN
- teste-reels.yml: Teste do Reels (acionado sob demanda ou pelo cron-job.org). Chaves: ANTHROPIC_API_KEY
- teste-repetidas.yml: Teste do protocolo anti-repetição (só leitura) (acionado sob demanda ou pelo cron-job.org). Chaves: ANTHROPIC_API_KEY
- teste-voz.yml: Teste de vozes gratuitas (só gera áudio) (acionado sob demanda ou pelo cron-job.org)
- teste-youtube.yml: Teste do Radar no YouTube (acionado sob demanda ou pelo cron-job.org). Chaves: ANTHROPIC_API_KEY, YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN
- yt-canal.yml: Atualizar texto do canal do YouTube (acionado sob demanda ou pelo cron-job.org). Chaves: YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN
- yt-capas.yml: Trocar capas de vídeos no YouTube (acionado sob demanda ou pelo cron-job.org). Chaves: YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN
- yt-criar-playlist.yml: Criar playlist no YouTube (acionado sob demanda ou pelo cron-job.org). Chaves: YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN
- yt-dados.yml: Baixar dados de vídeos do YouTube (preparo de ajustes) (acionado sob demanda ou pelo cron-job.org). Chaves: YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN
- yt-diagnostico.yml: Diagnóstico do YouTube (acionado sob demanda ou pelo cron-job.org). Chaves: YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN
- yt-editar.yml: Editar descrição e tags de vídeos do YouTube (acionado sob demanda ou pelo cron-job.org). Chaves: YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN
- yt-playlist.yml: Pôr vídeo na playlist Radar (avulso) (acionado sob demanda ou pelo cron-job.org). Chaves: YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN
- yt-privar.yml: Deixar vídeos privados no YouTube (acionado sob demanda ou pelo cron-job.org). Chaves: YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN

### Chaves guardadas nos Secrets do GitHub (só os nomes) e quem usa
- ANTHROPIC_API_KEY: alarme-repetidas.yml, comentarios.yml, grupos.yml, redes.yml, reels-agora.yml, robo.yml, teste-reels.yml, teste-repetidas.yml, teste-youtube.yml
- CLOUDFLARE_API_TOKEN: formulario-publicar.yml
- FB_PAGE_ID: comentarios.yml, metricas.yml, redes.yml, reels-agora.yml, teste-direct.yml, teste-meta.yml
- GITHUB_TOKEN: ajuste-buscas.yml, alarme-repetidas.yml, comentarios.yml, grupos.yml
- GMAIL_SENHA_APP: assessorias-envio.yml, redes.yml
- IG_USER_ID: comentarios.yml, instagram-antigos.yml, metricas.yml, redes.yml, reels-agora.yml, teste-direct.yml, teste-meta.yml
- META_PAGE_TOKEN: comentarios.yml, instagram-antigos.yml, metricas.yml, redes.yml, reels-agora.yml, teste-contas-meta.yml, teste-direct.yml, teste-meta.yml
- META_USER_TOKEN: teste-contas-meta.yml, teste-meta.yml
- UNSPLASH_ACCESS_KEY: robo.yml
- YT_CLIENT_ID: redes.yml, teste-youtube.yml, yt-canal.yml, yt-capas.yml, yt-criar-playlist.yml, yt-dados.yml, yt-diagnostico.yml, yt-editar.yml, yt-playlist.yml, yt-privar.yml
- YT_CLIENT_SECRET: redes.yml, teste-youtube.yml, yt-canal.yml, yt-capas.yml, yt-criar-playlist.yml, yt-dados.yml, yt-diagnostico.yml, yt-editar.yml, yt-playlist.yml, yt-privar.yml
- YT_REFRESH_TOKEN: redes.yml, teste-youtube.yml, yt-canal.yml, yt-capas.yml, yt-criar-playlist.yml, yt-dados.yml, yt-diagnostico.yml, yt-editar.yml, yt-playlist.yml, yt-privar.yml

<!-- AUTOMATICO:FIM -->
