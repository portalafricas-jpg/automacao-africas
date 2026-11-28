# Calendário Afro: monta o vídeo do episódio a partir do roteiro, da decupagem, das fotos conferidas e da narração.
# Gratuito: Python (Pillow) + ffmpeg. Não publica nada: gera só a prévia.
# Uso: python calendario_montar.py PASTA PASTA_VOZ SAIDA.mp4 [--quadros]
#   PASTA_VOZ: pasta com b1_0.wav, b1_1.wav... (se faltar, usa tempo estimado, só para teste)
#   --quadros: desenha só alguns quadros em PNG, para conferir antes de montar

import json
import math
import os
import random
import shutil
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

W, H, FPS = 1920, 1080, 30
S = 2                                  # desenha em 2x para o zoom não tremer
CW, CH = W * S, H * S
PAUSA_FRASE, PAUSA_BLOCO, INICIO = 0.30, 0.55, 0.40
AMARELO, VERMELHO, FUNDO, PAPEL = (255, 204, 0), (220, 30, 38), (14, 14, 14), (236, 226, 204)
GF = "/usr/share/fonts/truetype/google-fonts/ofl"
F_TITULO = f"{GF}/anton/Anton-Regular.ttf"
F_JORNAL = f"{GF}/cardo/Cardo-Bold.ttf"
F_JORNAL_IT = f"{GF}/cardo/Cardo-Italic.ttf"
F_TEXTO = f"{GF}/montserrat/Montserrat[wght].ttf"
RAIZ = os.path.dirname(os.path.abspath(__file__))
LOGO = os.path.join(RAIZ, "AP_500_140_negativo.png")


def fonte(caminho, tam, peso=None):
    f = ImageFont.truetype(caminho, tam)
    if peso:
        try:
            f.set_variation_by_name(peso)
        except Exception:
            pass
    return f


def duracao(arquivo):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", arquivo],
                       capture_output=True, text=True)
    return float(r.stdout.strip())


# ---------------- linha do tempo ----------------
def linha_do_tempo(roteiro, pasta_voz):
    frases, t = {}, INICIO
    for b in roteiro["blocos"]:
        for i, fr in enumerate(b["frases"]):
            chave = f"{b['id']}_{i}"
            wav = os.path.join(pasta_voz or "", f"{chave}.wav")
            d = duracao(wav) if pasta_voz and os.path.exists(wav) else max(1.2, len(fr["fala"].split()) / 2.5)
            frases[chave] = {"ini": t, "dur": d, "legenda": fr["legenda"], "wav": wav}
            t += d + PAUSA_FRASE
        t += PAUSA_BLOCO - PAUSA_FRASE
    return frases


def tempos_dos_planos(planos, frases):
    marcas = []
    for p in planos:
        f0 = p["frases"][0]
        chave, _, parte = f0.partition("@")
        fr = frases[chave]
        ini = fr["ini"] + (fr["dur"] / 2 if parte == "1" else 0)
        marcas.append(ini)
    inicios = [0.0] + [max(0.0, m - PAUSA_FRASE / 2) for m in marcas[1:]]
    ult = planos[-1]
    fim_total = frases[ult["frases"][-1].split("@")[0]]["ini"] + frases[ult["frases"][-1].split("@")[0]]["dur"] + ult.get("extra", 1.0)
    fins = inicios[1:] + [fim_total]
    return [(a, b) for a, b in zip(inicios, fins)], fim_total


# ---------------- tratamento de foto ----------------
def tom_antigo(img):
    g = ImageOps.grayscale(img)
    g = ImageOps.autocontrast(g, cutoff=1)
    return ImageOps.colorize(g, black=(18, 14, 10), white=(242, 232, 210), mid=(128, 114, 96))


def vinheta(img, forca=0.55):
    m = Image.new("L", (img.width // 8, img.height // 8), 0)
    d = ImageDraw.Draw(m)
    d.ellipse((-m.width * 0.25, -m.height * 0.3, m.width * 1.25, m.height * 1.3), fill=255)
    m = m.filter(ImageFilter.GaussianBlur(m.width // 8)).resize(img.size)
    escuro = Image.new("RGB", img.size, (0, 0, 0))
    return Image.composite(img, Image.blend(img, escuro, forca), m)


def grao(img, forca=14):
    ruido = Image.effect_noise(img.size, forca).convert("RGB")
    return Image.blend(img, ImageOps.autocontrast(ruido), 0.06)


def preparar_foto(caminho, plano):
    img = Image.open(caminho).convert("RGB")
    try:  # tratamento de foto (28/11/2026): qualidade e ampliação por IA; cor histórica preservada
        import tratamento_foto
        img = tratamento_foto.tratar(img, historica=True)
    except Exception as e:
        print(f"Tratamento de foto indisponível ({e})")
    if plano.get("recorte"):
        x0, y0, x1, y1 = plano["recorte"]
        img = img.crop((int(x0 * img.width), int(y0 * img.height), int(x1 * img.width), int(y1 * img.height)))
    img = tom_antigo(img)
    if plano.get("destaque"):
        cx, cy, r = plano["destaque"]
        d = ImageDraw.Draw(img)
        R_ = r * img.width
        lw = max(3, int(img.width / 220))
        d.ellipse((cx * img.width - R_, cy * img.height - R_, cx * img.width + R_, cy * img.height + R_),
                  outline=AMARELO, width=lw)
    # fundo: a própria foto ampliada e desfocada
    fundo = ImageOps.fit(img, (CW, CH)).filter(ImageFilter.GaussianBlur(60))
    fundo = Image.blend(fundo, Image.new("RGB", (CW, CH), (0, 0, 0)), 0.55)
    escala = min(CW / img.width, CH / img.height)
    if img.width / img.height > 1.45:                      # foto deitada: ocupa a tela toda
        frente = ImageOps.fit(img, (CW, CH), centering=tuple(plano.get("foco", [0.5, 0.5])))
        fundo.paste(frente, (0, 0))
    else:
        nw, nh = int(img.width * escala), int(img.height * escala)
        frente = img.resize((nw, nh), Image.LANCZOS)
        fundo.paste(frente, ((CW - nw) // 2, (CH - nh) // 2))
    out = vinheta(fundo, 0.65 if plano.get("escuro") else 0.45)
    if plano.get("escuro"):
        out = Image.blend(out, Image.new("RGB", out.size, (0, 0, 0)), 0.25)
    return grao(out)


# ---------------- artes ----------------
def papel(cor=PAPEL, escuro=False):
    base = Image.new("RGB", (CW, CH), FUNDO if escuro else cor)
    return grao(vinheta(base, 0.5 if escuro else 0.35), 30)


def centro(d, y, texto, f, cor):
    w = d.textlength(texto, font=f)
    d.text(((CW - w) / 2, y), texto, font=f, fill=cor)


def quebrar(d, texto, f, largura):
    linhas, atual = [], ""
    for p in texto.split():
        t = (atual + " " + p).strip()
        if d.textlength(t, font=f) <= largura:
            atual = t
        else:
            linhas.append(atual)
            atual = p
    linhas.append(atual)
    return linhas


def arte(plano):
    tipo = plano["arte"]
    if tipo == "numero":
        img = papel(escuro=True); d = ImageDraw.Draw(img)
        centro(d, CH * 0.12, plano["texto"][0], fonte(F_TITULO, 1100), VERMELHO)
        centro(d, CH * 0.70, plano["texto"][1], fonte(F_TITULO, 220), (240, 240, 240))
        return img
    if tipo == "ano":
        img = papel(escuro=True); d = ImageDraw.Draw(img)
        anos = ["1880", "1895", "1910", "1912", "1969", "2008"]
        y = int(CH * 0.80); x0, x1 = int(CW * 0.10), int(CW * 0.90)
        d.line((x0, y, x1, y), fill=(120, 120, 120), width=8)
        f_peq = fonte(F_TEXTO, 64, "Bold")
        for i, a in enumerate(anos):
            x = x0 + (x1 - x0) * i / (len(anos) - 1)
            ativo = a == plano["ano"]
            r = 34 if ativo else 18
            d.ellipse((x - r, y - r, x + r, y + r), fill=AMARELO if ativo else (150, 150, 150))
            w = d.textlength(a, font=f_peq)
            d.text((x - w / 2, y + 60), a, font=f_peq, fill=AMARELO if ativo else (170, 170, 170))
        centro(d, CH * 0.06, plano["ano"], fonte(F_TITULO, 620), AMARELO)
        f_txt = fonte(F_TEXTO, 104, "SemiBold")
        for j, linha in enumerate(quebrar(d, plano["texto"], f_txt, CW * 0.78)):
            centro(d, CH * 0.50 + j * 132, linha, f_txt, (240, 240, 240))
        return img
    if tipo == "baia":
        img = papel(escuro=True); d = ImageDraw.Draw(img)
        centro(d, CH * 0.10, "BAÍA DE GUANABARA", fonte(F_TITULO, 230), AMARELO)
        centro(d, CH * 0.30, "Rio de Janeiro, capital do país · novembro de 1910", fonte(F_TEXTO, 90, "SemiBold"), (220, 220, 220))
        # quatro navios estilizados
        for i in range(4):
            cx = CW * (0.20 + 0.20 * i); cy = CH * 0.56
            casco = [(cx - 300, cy), (cx + 300, cy), (cx + 230, cy + 90), (cx - 250, cy + 90)]
            d.polygon(casco, fill=(200, 200, 200))
            d.rectangle((cx - 120, cy - 90, cx + 140, cy), fill=(200, 200, 200))
            d.rectangle((cx - 40, cy - 190, cx, cy - 90), fill=(200, 200, 200))
            d.line((cx + 140, cy - 50, cx + 330, cy - 80), fill=(200, 200, 200), width=22)
        for k in range(14):
            yy = CH * 0.72 + k * 6
            d.line((CW * 0.06, yy, CW * 0.94, yy), fill=(40, 60, 80), width=3)
        centro(d, CH * 0.80, "4 navios de guerra · mais de 2.300 marinheiros", fonte(F_TEXTO, 104, "Bold"), (245, 245, 245))
        return img
    if tipo == "frase":
        img = papel(); d = ImageDraw.Draw(img)
        d.rectangle((CW * 0.06, CH * 0.08, CW * 0.94, CH * 0.92), outline=(60, 50, 40), width=10)
        d.line((CW * 0.06, CH * 0.20, CW * 0.94, CH * 0.20), fill=(60, 50, 40), width=6)
        centro(d, CH * 0.105, "CORREIO DA MANHÃ · 1910", fonte(F_JORNAL, 110), (60, 50, 40))
        centro(d, CH * 0.33, plano["texto"][0], fonte(F_JORNAL, 330), (20, 16, 12))
        centro(d, CH * 0.66, plano["texto"][1], fonte(F_JORNAL_IT, 110), (70, 58, 46))
        return img
    if tipo == "sobreviventes":
        img = papel(escuro=True); d = ImageDraw.Draw(img)
        f_n = fonte(F_TITULO, 560); f_t = fonte(F_TEXTO, 110, "Bold")
        d.text((CW * 0.13, CH * 0.14), "18", font=f_n, fill=(235, 235, 235))
        d.text((CW * 0.15, CH * 0.70), "PRESOS NA CELA", font=f_t, fill=(200, 200, 200))
        d.text((CW * 0.60, CH * 0.14), "2", font=f_n, fill=AMARELO)
        d.text((CW * 0.56, CH * 0.70), "SAÍRAM VIVOS", font=f_t, fill=AMARELO)
        d.line((CW * 0.5, CH * 0.18, CW * 0.5, CH * 0.82), fill=(90, 90, 90), width=6)
        return img
    if tipo == "lei":
        img = papel(); d = ImageDraw.Draw(img)
        centro(d, CH * 0.12, "LEI Nº 11.756", fonte(F_JORNAL, 300), (20, 16, 12))
        centro(d, CH * 0.38, "de 23 de julho de 2008", fonte(F_JORNAL_IT, 130), (70, 58, 46))
        f_t = fonte(F_JORNAL, 120)
        for j, linha in enumerate(quebrar(d, "Concede anistia post mortem a João Cândido Felisberto e aos demais participantes da Revolta da Chibata.", f_t, CW * 0.76)):
            centro(d, CH * 0.56 + j * 150, linha, f_t, (30, 24, 18))
        return img
    if tipo == "final":
        img = papel(escuro=True); d = ImageDraw.Draw(img)
        logo = Image.open(LOGO).convert("RGBA")
        lw = int(CW * 0.46); logo = logo.resize((lw, int(logo.height * lw / logo.width)), Image.LANCZOS)
        img.paste(logo, ((CW - lw) // 2, int(CH * 0.14)), logo)
        centro(d, CH * 0.44, "Histórias pretas todos os dias", fonte(F_TEXTO, 120, "Bold"), (245, 245, 245))
        centro(d, CH * 0.55, "BAIXE O APP", fonte(F_TITULO, 200), AMARELO)
        f_b = fonte(F_TEXTO, 90, "Bold")
        for i, rot in enumerate(["App Store", "Google Play"]):
            bx = CW * (0.27 + 0.27 * i); by = CH * 0.78
            d.rounded_rectangle((bx - 420, by - 100, bx + 420, by + 100), radius=50, fill=(245, 245, 245))
            w = d.textlength(rot, font=f_b)
            d.text((bx - w / 2, by - 55), rot, font=f_b, fill=(14, 14, 14))
        return img
    raise ValueError(tipo)


# ---------------- vídeo ----------------
def render_plano(img, mov, foco, dur, saida, tmp):
    png = os.path.join(tmp, "q.png"); img.save(png)
    n = max(2, round(dur * FPS))
    z0, z1 = {"in": (1.0, 1.10), "in2": (1.10, 1.22), "out": (1.12, 1.0), "pan": (1.10, 1.10)}.get(mov, (1.0, 1.0))
    fx, fy = foco
    z = f"{z0}+({z1}-{z0})*on/{n - 1}"
    if mov == "pan":
        x = f"(iw-iw/zoom)*on/{n - 1}"
    else:
        x = f"max(0,min(iw-iw/zoom,{fx}*iw-iw/zoom/2))"
    y = f"max(0,min(ih-ih/zoom,{fy}*ih-ih/zoom/2))"
    vf = f"zoompan=z='{z}':x='{x}':y='{y}':d={n}:s={W}x{H}:fps={FPS},format=yuv420p"
    temp = saida.replace(".mp4", ".tmp.mp4")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", png, "-vf", vf, "-frames:v", str(n),
                    "-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-r", str(FPS), temp],
                   check=True)
    os.replace(temp, saida)


def ass_tempo(t):
    h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def legendas_ass(frases, planos, tempos, arquivo):
    cab = (
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\nWrapStyle: 0\n\n"
        "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: Fala,Montserrat SemiBold,54,&H00FFFFFF,&H00FFFFFF,&H3C000000,&H3C000000,0,0,0,0,100,100,0,0,3,14,0,2,240,240,64,1\n"
        "Style: Rotulo,Montserrat SemiBold,32,&H0000CCFF,&H0000CCFF,&H50000000,&H50000000,0,0,0,0,100,100,0,0,3,10,0,7,60,60,50,1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
    linhas = []
    for chave, fr in frases.items():
        texto = fr["legenda"]
        # frases longas: divide em duas partes, cada uma no seu tempo
        partes = [texto]
        if len(texto) > 90:
            palavras = texto.split(); meio = len(palavras) // 2
            partes = [" ".join(palavras[:meio]), " ".join(palavras[meio:])]
        total = sum(len(p) for p in partes); t = fr["ini"]
        for p in partes:
            d = fr["dur"] * len(p) / total
            linhas.append(f"Dialogue: 0,{ass_tempo(t)},{ass_tempo(t + d)},Fala,,0,0,0,,{p}")
            t += d
    for p, (a, b) in zip(planos, tempos):
        if p.get("rotulo"):
            linhas.append(f"Dialogue: 1,{ass_tempo(a + 0.3)},{ass_tempo(b - 0.1)},Rotulo,,0,0,0,,{p['rotulo']}")
    with open(arquivo, "w", encoding="utf-8") as f:
        f.write(cab + "\n".join(linhas) + "\n")


def main():
    pasta, pasta_voz, saida = sys.argv[1], sys.argv[2], sys.argv[3]
    so_quadros = "--quadros" in sys.argv
    roteiro = json.load(open(os.path.join(pasta, "roteiro.json"), encoding="utf-8"))
    dec = json.load(open(os.path.join(pasta, "decupagem.json"), encoding="utf-8"))
    planos = dec["planos"]
    if not os.path.isdir(pasta_voz):
        pasta_voz = None
        print("AVISO: sem narração, usando tempo estimado")
    frases = linha_do_tempo(roteiro, pasta_voz)
    tempos, total = tempos_dos_planos(planos, frases)
    print(f"duração total: {total:.1f} s, {len(planos)} planos")

    tmp = tempfile.mkdtemp()
    imagens = []
    for i, p in enumerate(planos):
        img = arte(p) if "arte" in p else preparar_foto(os.path.join(pasta, "imagens", p["foto"]), p)
        imagens.append(img)
        if so_quadros:
            img.resize((W, H), Image.LANCZOS).save(os.path.join(saida, f"quadro_{i:02d}.jpg"), quality=88)
    if so_quadros:
        return

    lista = os.path.join(tmp, "lista.txt")
    with open(lista, "w") as f:
        for i, (p, img, (a, b)) in enumerate(zip(planos, imagens, tempos)):
            arq = os.path.join(tmp, f"p{i:02d}.mp4")
            render_plano(img, p.get("mov", "still"), p.get("foco", [0.5, 0.5]), b - a, arq, tmp)
            f.write(f"file '{arq}'\n")
            print(f"plano {i + 1}/{len(planos)} pronto ({b - a:.1f} s)")
    mudo = os.path.join(tmp, "mudo.mp4")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lista, "-c", "copy", mudo], check=True)

    # narração: cada frase no seu tempo; trilha baixinha por baixo
    entradas, filtros, rotulos = [], [], []
    if pasta_voz:
        for k, (chave, fr) in enumerate(frases.items()):
            entradas += ["-i", fr["wav"]]
            ms = int(fr["ini"] * 1000)
            filtros.append(f"[{k}:a]aresample=48000,loudnorm=I=-16:TP=-1.5:LRA=7,aresample=48000,aformat=channel_layouts=stereo,adelay={ms}|{ms}[v{k}]")
            rotulos.append(f"[v{k}]")
    n = len(rotulos)
    musica = os.path.join(RAIZ, dec["musica"])
    entradas += ["-stream_loop", "-1", "-i", musica]
    filtros.append(f"[{n}:a]aresample=48000,aformat=channel_layouts=stereo,volume=0.07,atrim=0:{total:.2f},"
                   f"afade=t=in:d=1.5,afade=t=out:st={total - 2.5:.2f}:d=2.5[mus]")
    if n:
        filtros.append("".join(rotulos) + f"amix=inputs={n}:normalize=0[voz]")
        filtros.append("[voz][mus]amix=inputs=2:normalize=0,atrim=0:" + f"{total:.2f}[a]")
    else:
        filtros.append("[mus]anull[a]")
    audio = os.path.join(tmp, "audio.m4a")
    subprocess.run(["ffmpeg", "-y", "-v", "error"] + entradas + ["-filter_complex", ";".join(filtros), "-map", "[a]",
                    "-c:a", "aac", "-b:a", "192k", audio], check=True)

    ass = os.path.join(tmp, "legendas.ass")
    legendas_ass(frases, planos, tempos, ass)
    temp = saida.replace(".mp4", ".tmp.mp4")
    vf = f"ass={ass},fade=t=in:st=0:d=0.6,fade=t=out:st={total - 1.0:.2f}:d=1.0"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", mudo, "-i", audio, "-vf", vf, "-map", "0:v", "-map", "1:a",
                    "-c:v", "libx264", "-crf", "20", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-c:a", "copy",
                    "-movflags", "+faststart", "-shortest", temp], check=True)
    os.replace(temp, saida)
    shutil.rmtree(tmp, ignore_errors=True)
    print("vídeo pronto:", saida)


if __name__ == "__main__":
    main()
