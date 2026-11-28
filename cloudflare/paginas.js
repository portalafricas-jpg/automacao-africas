// Páginas institucionais do Áfricas Play: política de privacidade e termos de uso.
// Exigidas pelo TikTok (e úteis para Meta, LinkedIn e Threads) para liberar a publicação pelo robô.
// Roda no Cloudflare Workers (grátis), separado do formulário das assessorias.
// Publicado pelo robô paginas-publicar.yml (cloudflare_publicar.py paginas).

const CORES = `:root{--fundo:#0e0e0e;--cartao:#1a1a1a;--amarelo:#ffcc00;--vermelho:#dc1e26;--texto:#fff;--cinza:#c8c8c8;--linha:#333}
*{box-sizing:border-box}body{margin:0;background:var(--fundo);font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;color:var(--texto)}
.pag{max-width:460px;margin:0 auto}.topo{padding:18px 20px 14px;border-bottom:3px solid var(--vermelho)}
.marca{font-weight:900;font-size:20px;letter-spacing:.06em}.marca span{color:var(--amarelo)}.sub{color:var(--cinza);font-size:12px;margin-top:2px}
.corpo{padding:20px}h1{font-size:21px;margin:0 0 8px;line-height:1.25}h2{font-size:16px;margin:22px 0 6px;color:var(--amarelo)}
p,li{color:var(--cinza);font-size:14px;line-height:1.55}p{margin:0 0 12px}ul{margin:0 0 12px;padding-left:18px}li{margin-bottom:4px}
.botao{display:block;width:100%;background:var(--amarelo);color:#000;font-weight:800;font-size:16px;text-align:center;border-radius:12px;padding:15px;margin-top:14px;text-decoration:none}
.botao.sec{background:var(--cartao);color:var(--texto);border:1px solid var(--linha)}
.rodape{border-top:1px solid var(--linha);padding:14px 20px 18px;font-size:12px;color:var(--cinza);line-height:1.5}.rodape a{color:var(--cinza)}
.caixa{background:var(--cartao);border:1px solid var(--linha);border-radius:12px;padding:12px 14px;margin:14px 0}
.caminho{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin:16px 0 4px;position:relative}
.passo{text-align:center;font-size:11px;color:var(--cinza);line-height:1.3}.passo b{display:block;color:var(--texto);font-size:12px}
.passo .ic{position:relative;z-index:1;width:46px;height:46px;margin:0 auto 6px;border-radius:14px;background:var(--cartao);border:1px solid var(--linha);display:flex;align-items:center;justify-content:center}
.ic svg{width:24px;height:24px;stroke:var(--amarelo);fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
.seta{position:absolute;top:22px;left:16%;right:16%;height:2px;background:repeating-linear-gradient(90deg,var(--amarelo) 0 6px,transparent 6px 12px);z-index:0}
.legenda-ilu{text-align:center;font-size:12px;color:var(--cinza);margin:4px 0 6px}
.selo{display:flex;gap:12px;align-items:center}.selo .ic{flex:none;width:46px;height:46px;border-radius:14px;background:#111;border:1px solid var(--linha);display:flex;align-items:center;justify-content:center}
.selo p{margin:0}.en{border-top:1px dashed #555;margin-top:26px;padding-top:6px}
.lojas{display:flex;gap:10px;justify-content:center;margin:14px 0 6px;flex-wrap:wrap}
.loja{display:flex;align-items:center;gap:8px;background:#000;border:1px solid #777;border-radius:10px;padding:7px 12px;color:#fff;text-decoration:none;min-width:140px}
.loja .sim{font-size:18px;line-height:1}.loja small{display:block;font-size:9px;color:#ccc}.loja strong{display:block;font-size:14px}`;

const IC = {
  app: '<svg viewBox="0 0 24 24"><rect x="6" y="2.5" width="12" height="19" rx="2.5"/><path d="M10.5 18.5h3"/></svg>',
  robo: '<svg viewBox="0 0 24 24"><rect x="4" y="7" width="16" height="12" rx="3"/><path d="M12 3v4M9 12h.01M15 12h.01M9 16h6"/></svg>',
  video: '<svg viewBox="0 0 24 24"><rect x="2.5" y="5" width="19" height="14" rx="3"/><path d="M10 9.5v5l4.5-2.5z"/></svg>',
  cadeado: '<svg viewBox="0 0 24 24"><rect x="5" y="10.5" width="14" height="10" rx="2.5"/><path d="M8 10.5V7.5a4 4 0 0 1 8 0v3M12 14.5v2.5"/></svg>',
  doc: '<svg viewBox="0 0 24 24"><path d="M7 2.5h7l4 4v15H7z"/><path d="M14 2.5v4h4M10 12h5M10 16h5"/></svg>',
};

const CAMINHO = `<div class="caminho"><div class="seta"></div>
<div class="passo"><div class="ic">${IC.app}</div><b>Redação</b>produz o conteúdo</div>
<div class="passo"><div class="ic">${IC.robo}</div><b>Robô</b>prepara e envia</div>
<div class="passo"><div class="ic">${IC.video}</div><b>Redes</b>contas oficiais do Áfricas Play</div></div>
<div class="legenda-ilu">O robô só publica nas contas do próprio Áfricas Play.</div>`;

const COFRE = `<div class="caixa selo"><div class="ic">${IC.cadeado}</div>
<p>As chaves de acesso ficam num cofre criptografado. Ninguém de fora vê, e a conta pode cancelar a autorização quando quiser.</p></div>`;

const LOJAS = `<div class="lojas"><a class="loja" href="https://apps.apple.com/br/app/%C3%A1fricas-play/id6448585492"><span><small>Baixar na</small><strong>App Store</strong></span></a>
<a class="loja" href="https://play.google.com/store/apps/details?id=br.com.app.gpu2633271.gpuc8cfd42c63ec76c640904e227254c57c"><span class="sim">▶</span><span><small>Disponível no</small><strong>Google Play</strong></span></a></div>`;

const RODAPE = `<div class="rodape">Áfricas Play · Rua Anunciato Rossi, 160 · Araraquara/SP · CEP 14806-210<br>
Contato: redacao@africas.com.br ou WhatsApp (11) 95606-0503<br>
<a href="/privacidade">Política de privacidade</a> · <a href="/termos">Termos de uso</a> · <a href="https://africas.com.br">africas.com.br</a></div>`;

function pagina(titulo, corpo) {
  return new Response(
    `<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>${titulo} · Áfricas Play</title><style>${CORES}</style></head>
<body><div class="pag"><div class="topo"><div class="marca">ÁFRICAS <span>PLAY</span></div><div class="sub">Cultura e mídia preta</div></div>
<div class="corpo">${corpo}</div>${RODAPE}</div></body></html>`,
    { headers: { "content-type": "text/html; charset=utf-8", "cache-control": "public, max-age=3600" } }
  );
}

const INICIO = `<h1>Ferramenta de publicação do Áfricas Play</h1>
<p>O Áfricas Play é um app e portal de cultura e mídia preta (africas.com.br). Usamos uma ferramenta própria para publicar o conteúdo da nossa redação nas contas oficiais do Áfricas Play nas redes sociais.</p>
${CAMINHO}
<a class="botao" href="/privacidade">Política de privacidade</a>
<a class="botao sec" href="/termos">Termos de uso</a>
<p style="margin-top:20px"><b style="color:#fff">Acompanhe pelo app Áfricas Play</b></p>${LOJAS}`;

const PRIVACIDADE = `<h1>Política de privacidade</h1>
<p>Esta política explica quais dados a ferramenta de publicação do Áfricas Play recebe das redes sociais, para que usa e como protege.</p>
${CAMINHO}
<h2>Quem somos</h2>
<p>Áfricas Play, app e portal de cultura e mídia preta, com sede na Rua Anunciato Rossi, 160, Araraquara/SP, CEP 14806-210. Contato: redacao@africas.com.br.</p>
<h2>O que é a ferramenta</h2>
<p>É um publicador de uso interno. Ele posta vídeos, fotos e textos produzidos pela redação do Áfricas Play nas contas oficiais do Áfricas Play e da sua equipe (como TikTok, Instagram, Facebook, YouTube, Threads e LinkedIn). Não é aberto ao público e não publica em contas de terceiros.</p>
<h2>Dados que recebemos</h2>
<ul><li>Dados básicos da conta que autorizou: identificador, nome de exibição e foto de perfil.</li>
<li>A chave de acesso (token) que a rede entrega depois da autorização.</li>
<li>Informações das nossas próprias postagens, como situação da publicação, visualizações, curtidas e comentários, quando a rede oferece.</li></ul>
<h2>Para que usamos</h2>
<ul><li>Publicar o conteúdo do Áfricas Play nas contas autorizadas.</li>
<li>Conferir se cada postagem foi publicada corretamente.</li>
<li>Acompanhar os resultados das nossas próprias postagens.</li></ul>
<h2>O que não fazemos</h2>
<ul><li>Não vendemos nem alugamos dados.</li>
<li>Não compartilhamos dados com terceiros para publicidade.</li>
<li>Não coletamos dados de seguidores nem de outros usuários.</li></ul>
<h2>Como protegemos</h2>
${COFRE}
<p>As chaves de acesso ficam guardadas em cofre criptografado (GitHub Secrets), usadas só pelos robôs do Áfricas Play.</p>
<h2>Por quanto tempo</h2>
<p>Guardamos os dados enquanto a autorização estiver ativa. A conta pode cancelar a autorização a qualquer momento nas configurações de aplicativos da própria rede social. Depois do cancelamento, apagamos a chave de acesso.</p>
<h2>Seus direitos</h2>
<p>Conforme a Lei Geral de Proteção de Dados (Lei nº 13.709/2018), você pode pedir acesso, correção ou exclusão dos seus dados pelo e-mail redacao@africas.com.br.</p>
<h2>Mudanças nesta política</h2>
<p>Se esta política mudar, a versão em vigor é sempre a publicada nesta página.</p>
<div class="en"><h2>English summary</h2>
<p>Áfricas Play (africas.com.br) uses this internal tool only to publish content produced by its newsroom to its own official social media accounts. We receive the authorizing account's basic profile (ID, display name, avatar), the access token and status/metrics of our own posts. We use them only to publish and check our posts. We do not sell or share data and do not collect data from other users. Tokens are stored encrypted. Access can be revoked at any time in the social network's app settings; we then delete the token. Contact: redacao@africas.com.br.</p></div>`;

const TERMOS = `<h1>Termos de uso</h1>
<p>Estes termos valem para a ferramenta de publicação do Áfricas Play.</p>
${CAMINHO}
<h2>1. O que é</h2>
<p>Ferramenta de uso interno do Áfricas Play para publicar o conteúdo da sua redação nas contas oficiais do Áfricas Play e da sua equipe nas redes sociais.</p>
<h2>2. Quem pode usar</h2>
<p>Só as contas do Áfricas Play e da sua equipe, autorizadas por quem administra cada conta. A ferramenta não é oferecida ao público.</p>
<h2>3. Conteúdo</h2>
<ul><li>Todo conteúdo publicado é produzido ou licenciado pelo Áfricas Play.</li>
<li>Seguimos as regras e as diretrizes de comunidade de cada rede social.</li>
<li>Quem administra a conta pode revisar, editar ou apagar qualquer publicação diretamente na rede.</li></ul>
<h2>4. Autorização</h2>
<p>A conexão com cada rede depende da autorização de quem administra a conta, que pode cancelá-la a qualquer momento nas configurações da própria rede.</p>
<h2>5. Privacidade</h2>
<p>O tratamento dos dados segue a nossa <a href="/privacidade" style="color:var(--amarelo)">política de privacidade</a>.</p>
<h2>6. Lei aplicável</h2>
<p>Estes termos seguem as leis do Brasil.</p>
<h2>7. Contato</h2>
<p>Dúvidas: redacao@africas.com.br ou WhatsApp (11) 95606-0503.</p>
<div class="en"><h2>English summary</h2>
<p>This is an internal publishing tool of Áfricas Play (africas.com.br), used only by Áfricas Play and its team to post newsroom content to their own official social media accounts. All content is produced or licensed by Áfricas Play and follows each platform's rules. Account administrators may revoke access at any time. Data handling follows our privacy policy at /privacidade. Governed by the laws of Brazil. Contact: redacao@africas.com.br.</p></div>`;

export default {
  async fetch(request) {
    const caminho = new URL(request.url).pathname.replace(/\/+$/, "") || "/";
    if (caminho === "/privacidade" || caminho === "/privacy") return pagina("Política de privacidade", PRIVACIDADE);
    if (caminho === "/termos" || caminho === "/terms") return pagina("Termos de uso", TERMOS);
    return pagina("Ferramenta de publicação", INICIO);
  },
};
