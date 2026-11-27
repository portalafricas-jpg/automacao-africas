// Formulário das assessorias do Áfricas Play (prévia aprovada por Washington em 27/11/2026).
// Roda no Cloudflare Workers (grátis). Os dados ficam no KV "assessorias":
//   p:<token>          -> dados da página (nome, assessoria, sugestões), gravados pelo robô
//   r:<data>:<token>   -> respostas das assessorias, lidas e apagadas pelo robô
// O robô publica este arquivo pelo GitHub (cloudflare_publicar.py).

const CORES = `:root{--fundo:#0e0e0e;--cartao:#1a1a1a;--amarelo:#ffcc00;--vermelho:#dc1e26;--texto:#fff;--cinza:#c8c8c8;--linha:#333}
*{box-sizing:border-box}body{margin:0;background:var(--fundo);font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;color:var(--texto)}
.pag{max-width:460px;margin:0 auto}.topo{padding:18px 20px 14px;border-bottom:3px solid var(--vermelho)}
.marca{font-weight:900;font-size:20px;letter-spacing:.06em}.marca span{color:var(--amarelo)}.sub{color:var(--cinza);font-size:12px;margin-top:2px}
.corpo{padding:20px}h1{font-size:21px;margin:0 0 8px;line-height:1.25}p{color:var(--cinza);font-size:14px;line-height:1.5;margin:0 0 14px}
label.t{display:block;font-weight:700;font-size:14px;margin:18px 0 6px}.dica{font-weight:400;color:var(--cinza);font-size:12px;display:block;margin-top:2px}
.campo{display:flex;align-items:center;background:var(--cartao);border:1px solid var(--linha);border-radius:10px}
.campo b{color:var(--amarelo);padding:0 4px 0 12px;font-size:16px}.campo input{flex:1;background:transparent;border:0;color:var(--texto);font-size:16px;padding:13px 12px 13px 2px;outline:none;min-width:0}
.sugestoes{background:var(--cartao);border:1px dashed #555;border-radius:10px;padding:10px 12px;margin-top:6px}.sugestoes .tit{font-size:12px;color:var(--amarelo);font-weight:700;margin-bottom:6px}
.op{display:flex;align-items:center;gap:10px;font-size:14px;padding:6px 0}.op input{width:18px;height:18px;accent-color:var(--amarelo)}
.conta{font-size:12px;color:var(--cinza);margin-top:8px}.autoriza{display:flex;gap:10px;align-items:flex-start;font-size:13px;color:var(--cinza);margin-top:18px;line-height:1.45}
.autoriza input{width:18px;height:18px;margin-top:2px;accent-color:var(--amarelo);flex:none}
.botao{display:block;width:100%;background:var(--amarelo);color:#000;font-weight:800;font-size:16px;text-align:center;border:0;border-radius:12px;padding:15px;margin-top:20px;cursor:pointer}
.links{display:flex;flex-direction:column;gap:10px;margin-top:18px;text-align:center}.links a{color:var(--cinza);font-size:13px}
.rodape{border-top:1px solid var(--linha);padding:14px 20px 18px;font-size:12px;color:var(--cinza);line-height:1.5}
.ok{width:64px;height:64px;border-radius:50%;background:var(--amarelo);color:#000;font-size:34px;font-weight:900;display:flex;align-items:center;justify-content:center;margin:6px 0 16px}
.lista{background:var(--cartao);border-radius:10px;padding:12px 14px;font-size:14px;margin-bottom:14px}.lista div{padding:4px 0}.lista b{color:var(--amarelo)}
.erro{background:#3a1012;border:1px solid var(--vermelho);border-radius:10px;padding:10px 12px;font-size:14px;margin-bottom:12px}
.tela-app{margin:18px auto 6px;width:210px;border:6px solid #2b2b2b;border-radius:28px;background:#000;padding:10px 8px 14px;box-shadow:0 8px 24px rgba(0,0,0,.5)}
.tela-app .notch{width:60px;height:6px;background:#2b2b2b;border-radius:6px;margin:0 auto 8px}
.tela-app .cab{display:flex;justify-content:flex-start;gap:4px;font-weight:900;font-size:11px;letter-spacing:.05em;padding:0 4px 6px;border-bottom:2px solid var(--vermelho)}.tela-app .cab span{color:var(--amarelo)}
.card{background:#151515;border-radius:10px;margin-top:8px;overflow:hidden}.card .img{height:84px;background:linear-gradient(135deg,#3a2a00,#ffcc00 55%,#dc1e26);position:relative}
.card .img::after{content:"CULTURA";position:absolute;left:6px;top:6px;background:var(--vermelho);color:#fff;font-size:8px;font-weight:800;padding:2px 5px;border-radius:3px}
.card .tt{font-size:11px;font-weight:800;padding:7px 8px 4px;line-height:1.3}.chips{display:flex;flex-wrap:wrap;gap:4px;padding:2px 8px 8px}
.chip{font-size:9px;background:#262626;color:var(--amarelo);border:1px solid #444;border-radius:20px;padding:2px 6px}.linha-cinza{height:6px;background:#222;border-radius:4px;margin:6px 8px}
.legenda-ilu{text-align:center;font-size:12px;color:var(--cinza);margin:4px 0 6px}
.caminho{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin:16px 0 4px;position:relative}
.passo{text-align:center;font-size:11px;color:var(--cinza);line-height:1.3}.passo b{display:block;color:var(--texto);font-size:11px}
.passo .ic{position:relative;z-index:1;width:46px;height:46px;margin:0 auto 6px;border-radius:14px;background:var(--cartao);border:1px solid var(--linha);display:flex;align-items:center;justify-content:center}
.passo .ic svg{width:24px;height:24px;stroke:var(--amarelo);fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
.seta{position:absolute;top:22px;left:12%;right:12%;height:2px;background:repeating-linear-gradient(90deg,var(--amarelo) 0 6px,transparent 6px 12px);z-index:0}
.lojas{display:flex;gap:10px;justify-content:center;margin:14px 0 6px;flex-wrap:wrap}
.loja{display:flex;align-items:center;gap:8px;background:#000;border:1px solid #777;border-radius:10px;padding:7px 12px;color:#fff;text-decoration:none;min-width:140px}
.loja .sim{font-size:18px;line-height:1}.loja small{display:block;font-size:9px;color:#ccc}.loja strong{display:block;font-size:14px}
.sep{height:1px;background:var(--linha);margin:20px 0 4px}`;

const RODAPE = `<div class="rodape">Dúvidas: redacao@africas.com.br ou WhatsApp (11) 95606-0503.</div>`;
// Ícones simples em linha (sem logos de marca, sem fotos), aprovados em 27/11/2026
const IC = {
  site: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3.5 3 14.5 0 18M12 3c-3 3.5-3 14.5 0 18"/></svg>',
  app: '<svg viewBox="0 0 24 24"><rect x="6" y="2.5" width="12" height="19" rx="2.5"/><path d="M10.5 18.5h3"/></svg>',
  collab: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="4"/><path d="M16 8v5a3 3 0 0 0 5 0v-1a9 9 0 1 0-3.5 7.1"/></svg>',
  video: '<svg viewBox="0 0 24 24"><rect x="2.5" y="5" width="19" height="14" rx="3"/><path d="M10 9.5v5l4.5-2.5z"/></svg>',
};
const CAMINHO = `<div class="caminho"><div class="seta"></div>
<div class="passo"><div class="ic">${IC.site}</div><b>Site</b>a matéria no ar</div>
<div class="passo"><div class="ic">${IC.app}</div><b>App</b>notificação no celular</div>
<div class="passo"><div class="ic">${IC.collab}</div><b>Instagram</b>em collab com vocês</div>
<div class="passo"><div class="ic">${IC.video}</div><b>Facebook e YouTube</b>vídeos e posts</div></div>`;
const LOJAS = `<div class="sep"></div><p style="margin-top:14px"><b style="color:#fff">Acompanhe pelo app Áfricas Play</b><br>As matérias de vocês chegam primeiro por lá.</p>
<div class="lojas"><a class="loja" href="https://apps.apple.com/br/app/%C3%A1fricas-play/id6448585492"><span><small>Baixar na</small><strong>App Store</strong></span></a>
<a class="loja" href="https://play.google.com/store/apps/details?id=br.com.app.gpu2633271.gpuc8cfd42c63ec76c640904e227254c57c"><span class="sim">▶</span><span><small>Disponível no</small><strong>Google Play</strong></span></a></div>`;
function ilustracao(assessoria) {
  return `<div class="tela-app"><div class="notch"></div><div class="cab">ÁFRICAS <span>PLAY</span></div>
<div class="card"><div class="img"></div><div class="tt">Título da matéria da sua assessoria</div>
<div class="chips"><span class="chip">Collab: @suaassessoria</span><span class="chip">@artista</span></div></div>
<div class="linha-cinza"></div><div class="linha-cinza" style="width:60%"></div></div>
<div class="legenda-ilu">Assim a sua matéria aparece: no app e nas redes, com o seu @ junto.</div>`;
}

const ARROBA = /^[a-z0-9_](?:[a-z0-9_.]{0,28}[a-z0-9_])?$/;

function esc(t) {
  return String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function pagina(corpo, rodape = RODAPE) {
  return new Response(
    `<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex"><title>Áfricas Play · Parceria Multimídia Preta</title><style>${CORES}</style></head>
<body><div class="pag"><div class="topo"><div class="marca">ÁFRICAS <span>PLAY</span></div><div class="sub">Parceria Multimídia Preta</div></div>
<div class="corpo">${corpo}</div>${rodape}</div></body></html>`,
    { headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-store" } }
  );
}

function limpar(h) {
  h = String(h || "").trim().toLowerCase();
  const m = h.match(/instagram\.com\/([a-z0-9_.]+)/);
  if (m) h = m[1];
  return h.replace(/^@+/, "").replace(/\/+$/, "").trim();
}

function formulario(t, d, erro = "") {
  const sug = (d.sugestoes || []).slice(0, 4);
  const blocoSug = sug.length
    ? `<div class="sugestoes"><div class="tit">Achamos na matéria "${esc(d.materia || "")}":</div>
       ${sug.map((s, i) => `<label class="op"><input type="checkbox" name="sug" value="${esc(s)}" ${i === 0 ? "checked" : ""}> @${esc(s)}</label>`).join("")}</div>`
    : "";
  return pagina(`${erro ? `<div class="erro">${esc(erro)}</div>` : ""}
<h1>Olá, ${esc(d.nome)}! Falta só o Instagram para ativar o collab.</h1>
<p>Com o Instagram, as matérias da ${esc(d.assessoria || "sua assessoria")} saem nas nossas redes em collab e aparecem também no perfil de vocês. Continua gratuito.</p>
${ilustracao()}
${CAMINHO}
<form method="post" action="/enviar">
<input type="hidden" name="t" value="${esc(t)}">
<label class="t">Instagram da assessoria<span class="dica">Obrigatório</span></label>
<div class="campo"><b>@</b><input name="ig" required placeholder="instagram.da.assessoria" value="${esc(d.instagram || "")}" autocapitalize="none" autocomplete="off"></div>
<label class="t">Mais perfis para o collab<span class="dica">Opcional: artista, espaço cultural ou evento</span></label>
${blocoSug}
<div class="campo" style="margin-top:8px"><b>@</b><input name="outro" placeholder="outro perfil (opcional)" autocapitalize="none" autocomplete="off"></div>
<div class="conta">No máximo 3 perfis por post, contando o da assessoria. É limite do Instagram.</div>
<label class="autoriza"><input type="checkbox" name="autoriza" value="sim" checked><span>Autorizo o Áfricas Play a marcar esses perfis e a convidá-los para collab nas publicações das nossas matérias.</span></label>
<button class="botao" type="submit">Ativar o collab</button>
</form>
<div class="links"><a href="/recusar?t=${encodeURIComponent(t)}&tipo=sem_interesse">Não temos interesse</a>
<a href="/recusar?t=${encodeURIComponent(t)}&tipo=descadastrar">Não quero mais receber e-mails</a></div>`);
}

async function guardar(env, t, d, resposta) {
  const quando = new Date().toISOString();
  await env.KV.put(`r:${quando}:${t}`, JSON.stringify({ token: t, email: d.email, quando, ...resposta }));
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const t = (url.searchParams.get("t") || "").trim();

    if (request.method === "POST" && url.pathname === "/enviar") {
      const f = await request.formData();
      const tk = String(f.get("t") || "");
      const d = tk && (await env.KV.get(`p:${tk}`, "json"));
      if (!d) return pagina(`<h1>Link expirado ou inválido.</h1><p>Responda o nosso e-mail que a gente resolve.</p>`);
      const ig = limpar(f.get("ig"));
      if (!ARROBA.test(ig)) return formulario(tk, d, "Confira o Instagram da assessoria: use só o @, sem espaços.");
      const extras = [];
      for (const s of [...f.getAll("sug"), f.get("outro")]) {
        const h = limpar(s);
        if (h && ARROBA.test(h) && h !== ig && !extras.includes(h)) extras.push(h);
      }
      if (extras.length > 2) return formulario(tk, d, "No máximo 3 perfis no total, contando o da assessoria. Desmarque algum.");
      const autoriza = f.get("autoriza") === "sim";
      await guardar(env, tk, d, { tipo: "instagram", instagram: ig, extras, autoriza });
      return pagina(`<div class="ok">✓</div><h1>Pronto, ${esc(d.nome)}! O collab está ativado.</h1>
<div class="lista"><div>Assessoria: <b>@${esc(ig)}</b></div>${extras.length ? `<div>Também no collab: <b>${extras.map((h) => "@" + esc(h)).join(" ")}</b></div>` : ""}</div>
<p>A partir de agora, as matérias de vocês saem nas nossas redes em collab. É só aceitar o convite que chega no Instagram.</p>
<p style="margin-top:6px"><b style="color:#fff">Agora a sua pauta vai do site para o app e para as redes:</b></p>${CAMINHO}
<p>Vocês também vão receber esta confirmação por e-mail.</p>${LOJAS}`,
        `<div class="rodape">Errou algum @? É só responder o e-mail de confirmação com o certo.</div>`);
    }

    if (url.pathname === "/recusar") {
      const d = t && (await env.KV.get(`p:${t}`, "json"));
      if (!d) return pagina(`<h1>Link expirado ou inválido.</h1><p>Responda o nosso e-mail que a gente resolve.</p>`);
      const tipo = url.searchParams.get("tipo") === "descadastrar" ? "descadastrar" : "sem_interesse";
      await guardar(env, t, d, { tipo });
      return pagina(tipo === "descadastrar"
        ? `<h1>Tudo certo, ${esc(d.nome)}.</h1><p>Vocês não vão mais receber os nossos e-mails. Se mudarem de ideia, é só escrever para redacao@africas.com.br.</p>`
        : `<h1>Obrigado pelo retorno, ${esc(d.nome)}.</h1><p>Não vamos mais insistir neste convite. As portas continuam abertas para as pautas de vocês.</p>`);
    }

    if (url.pathname === "/" && t) {
      const d = await env.KV.get(`p:${t}`, "json");
      if (d) return formulario(t, d);
    }
    return pagina(`<h1>Parceria Multimídia Preta</h1><p>Este endereço é aberto pelo link que enviamos por e-mail. Dúvidas? Escreva para redacao@africas.com.br.</p>`);
  },
};
