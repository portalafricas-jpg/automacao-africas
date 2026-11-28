# Tratamento de foto do Áfricas Play (aprovado por Washington em 28/11/2026): vale para 100% das imagens e vídeos.
#
# 1) Rosto no lugar certo: acha os rostos (detector YuNet, licença MIT) e, ao recortar para o tamanho da peça
#    (em pé, quadrado etc.), centraliza o rosto ou o grupo, na parte de cima, longe da manchete.
# 2) Padrão de qualidade: brilho e contraste acertados, cor corrigida, chuvisco removido, nitidez na medida e
#    foto pequena ampliada por inteligência artificial (FSRCNN, licença Apache 2.0).
# 3) Foto ruim: mede nitidez, tamanho e se é print de rede social; entre as fotos da própria matéria, fica a melhor.
#    Foto de outra pessoa nunca entra (a troca só acontece por foto da mesma matéria ou da pessoa citada).
#
# Tudo gratuito e rodando no GitHub. Se o OpenCV não estiver instalado, cai no tratamento simples antigo.

import json
import os
from datetime import datetime

from PIL import Image, ImageEnhance, ImageFilter

try:
    import cv2
    import numpy as np
    TEM_CV = True
except Exception:  # robôs que não instalam o OpenCV continuam funcionando
    TEM_CV = False

PASTA = os.path.dirname(os.path.abspath(__file__))
MODELO_ROSTO = os.path.join(PASTA, "modelos", "rosto-yunet.onnx")
MODELO_X2 = os.path.join(PASTA, "modelos", "ampliar-fsrcnn-x2.pb")
MODELO_X4 = os.path.join(PASTA, "modelos", "ampliar-fsrcnn-x4.pb")
ARQ_FRACAS = os.path.join(PASTA, "estado", "fotos-fracas.json")

LARGURA_BOA = 1080          # abaixo disso a foto é ampliada por IA
NITIDEZ_FRACA = 60          # variação do Laplaciano: abaixo disso a foto é considerada borrada
_detector = None
_ampliadores = {}


def log(t):
    print(t, flush=True)


def ligado():
    """Chave em video-config.json ("tratamento_foto"). A prévia força com TRATAMENTO_FORCAR=1."""
    if os.environ.get("TRATAMENTO_FORCAR") == "1":
        return True
    try:
        return bool(json.load(open(os.path.join(PASTA, "video-config.json"))).get("tratamento_foto"))
    except Exception:
        return False


# ---------------- conversões ----------------
def _para_cv(img):
    return cv2.cvtColor(np.array(img.convert("RGB")), cv2.COLOR_RGB2BGR)


def _para_pil(arr):
    return Image.fromarray(cv2.cvtColor(arr, cv2.COLOR_BGR2RGB))


# ---------------- medidas ----------------
def nitidez(img):
    if not TEM_CV:
        return 999
    g = cv2.cvtColor(_para_cv(img), cv2.COLOR_BGR2GRAY)
    if g.shape[1] > 800:
        g = cv2.resize(g, (800, int(g.shape[0] * 800 / g.shape[1])), interpolation=cv2.INTER_AREA)
    return float(cv2.Laplacian(g, cv2.CV_64F).var())


def eh_print(img):
    """Print de rede social (Instagram, X): muito fundo branco liso com texto."""
    p = img.convert("L").resize((200, int(200 * img.height / max(1, img.width))))
    dados = list(p.getdata())
    branco = sum(1 for v in dados if v > 238) / len(dados)
    return branco > 0.32


def qualidade(img):
    """Nota de 0 a 100 para escolher a melhor foto entre as candidatas."""
    if img is None:
        return -1
    n = nitidez(img)
    nota = min(40, n / 4)                                  # nitidez
    nota += min(35, img.width / LARGURA_BOA * 35)          # tamanho
    b = sum(img.convert("L").resize((64, 64)).getdata()) / 4096
    nota += 15 if 60 <= b <= 200 else 5                    # brilho aproveitável
    nota += 10 if rostos(img) else 0                       # tem gente na foto
    if eh_print(img):
        nota -= 45
    return round(nota, 1)


def fraca(img):
    return img is None or eh_print(img) or img.width < 500 or nitidez(img) < NITIDEZ_FRACA


# ---------------- rostos ----------------
def rostos(img):
    """Lista de rostos (x, y, w, h) na escala da imagem."""
    global _detector
    if not TEM_CV or not os.path.exists(MODELO_ROSTO):
        return []
    arr = _para_cv(img)
    h, w = arr.shape[:2]
    escala = min(1.0, 640 / max(h, w))
    peq = cv2.resize(arr, (int(w * escala), int(h * escala))) if escala < 1 else arr
    try:
        if _detector is None:
            _detector = cv2.FaceDetectorYN.create(MODELO_ROSTO, "", (peq.shape[1], peq.shape[0]), 0.8, 0.3, 50)
        _detector.setInputSize((peq.shape[1], peq.shape[0]))
        _, achados = _detector.detect(peq)
    except Exception as e:
        log(f"Tratamento: detector de rosto falhou ({e})")
        return []
    saida = []
    for f in (achados if achados is not None else []):
        x, y, fw, fh = [float(v) / escala for v in f[:4]]
        if fw >= w * 0.035:                       # ignora rostinhos minúsculos no fundo
            saida.append((x, y, fw, fh))
    return saida


# ---------------- qualidade ----------------
def _ampliar(arr, fator):
    if fator not in _ampliadores:
        sr = cv2.dnn_superres.DnnSuperResImpl_create()
        sr.readModel(MODELO_X4 if fator == 4 else MODELO_X2)
        sr.setModel("fsrcnn", fator)
        _ampliadores[fator] = sr
    return _ampliadores[fator].upsample(arr)


def tratar(img, historica=False):
    """Padrão de qualidade. Não muda o enquadramento (o recorte é feito em recortar)."""
    if img is None:
        return None
    if img.info.get("tratada"):
        return img
    img = img.convert("RGB")
    if not TEM_CV:
        pequena = img.width < 900 or img.height < 700
        img = img.filter(ImageFilter.UnsharpMask(radius=3 if pequena else 2, percent=140 if pequena else 90,
                                                 threshold=2))
        img = ImageEnhance.Contrast(img).enhance(1.06 if pequena else 1.03)
        img.info["tratada"] = True
        return img
    arr = _para_cv(img)
    # 1) foto pequena: ampliação por IA (até ~1600 px de largura; o resto é ajuste fino no recorte)
    menor_lado = min(arr.shape[:2])
    if menor_lado < LARGURA_BOA and os.path.exists(MODELO_X2):
        try:
            fator = 4 if menor_lado < 400 else 2
            if max(arr.shape[:2]) * fator <= 4200:
                arr = _ampliar(arr, fator)
        except Exception as e:
            log(f"Tratamento: ampliação falhou ({e})")
    # 2) chuvisco: limpeza leve (sem deixar a pele "de plástico")
    arr = cv2.fastNlMeansDenoisingColored(arr, None, 3, 3, 7, 21)
    # 3) brilho e contraste: foto bem exposta não muda de tom (protege o tom de pele).
    #    Só a foto apagada (sem contraste) ou bem escura recebe ajuste de luz.
    lab = cv2.cvtColor(arr, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    baixo, alto = np.percentile(l, (1, 99))
    media = float(l.mean())
    caras = rostos(_para_pil(arr))
    tem_rosto = bool(caras)
    if tem_rosto:   # com gente na foto, quem decide se está escura é o rosto, não o fundo
        x, y, w, h = [int(v) for v in caras[0]]
        rosto_l = l[max(0, y):y + h, max(0, x):x + w]
        media = float(rosto_l.mean()) * 0.8 if rosto_l.size else media   # pele negra não é "foto escura"
    if not tem_rosto and 30 < alto - baixo < 170:  # foto apagada e sem gente: devolve um pouco do contraste
        esticado = np.clip((l.astype(np.float32) - baixo) * 255.0 / (alto - baixo), 0, 255)
        l = (0.4 * esticado + 0.6 * l).astype(np.uint8)
    if media < (45 if tem_rosto else 70):           # foto bem escura: clareia sem estourar
        gama = max(0.9 if tem_rosto else 0.75, np.log(95 / 255) / np.log(max(media, 20) / 255))
        l = (255 * (l / 255.0) ** gama).astype(np.uint8)
    # 4) cor: o tom de pele é preservado sempre. Correção de cor só em foto SEM rosto e com cor puxada forte
    #    (ex.: palco todo azul); foto histórica fica como está.
    desvio_a, desvio_b = float(a.mean()) - 128, float(b.mean()) - 128
    if not historica and not tem_rosto and max(abs(desvio_a), abs(desvio_b)) > 10:
        a = (a.astype(np.float32) - desvio_a * 0.3).clip(0, 255).astype(np.uint8)
        b = (b.astype(np.float32) - desvio_b * 0.3).clip(0, 255).astype(np.uint8)
    arr = cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2BGR)
    saida = _para_pil(arr)
    saida.info["tratada"] = True
    return saida


def recortar(img, largura, altura, topo=0.33):
    """Preenche o tamanho sem distorcer, com o rosto (ou o grupo) centralizado na parte de cima."""
    img = img.convert("RGB")
    caras = rostos(img)
    escala = max(largura / img.width, altura / img.height)
    nova = img.resize((int(img.width * escala) + 1, int(img.height * escala) + 1), Image.LANCZOS)
    if caras:
        x0 = min(c[0] for c in caras) * escala
        x1 = max(c[0] + c[2] for c in caras) * escala
        y0 = min(c[1] for c in caras) * escala
        y1 = max(c[1] + c[3] for c in caras) * escala
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        x = int(cx - largura / 2)
        y = int(cy - altura * topo)
    else:
        x = (nova.width - largura) // 2
        y = int((nova.height - altura) * 0.4)       # sem rosto: um pouco acima do meio
    x = max(0, min(x, nova.width - largura))
    y = max(0, min(y, nova.height - altura))
    final = nova.crop((x, y, x + largura, y + altura))
    final = final.filter(ImageFilter.UnsharpMask(radius=1.4, percent=55, threshold=3))   # nitidez final
    final.info["tratada"] = True
    return final


def escolher(imagens, titulo=""):
    """Entre as candidatas (mesma matéria ou mesma pessoa), fica a de melhor qualidade."""
    validas = [i for i in imagens if i is not None]
    if not validas:
        return None
    notas = [(qualidade(i), n, i) for n, i in enumerate(validas)]
    notas.sort(key=lambda t: (-t[0], t[1]))
    melhor = notas[0][2]
    if fraca(melhor):
        registrar_fraca(titulo, notas[0][0])
    return melhor


def registrar_fraca(titulo, nota):
    """Guarda as matérias com foto fraca, para o aviso ao Washington trocar a foto no painel."""
    try:
        lista = json.load(open(ARQ_FRACAS, encoding="utf-8")) if os.path.exists(ARQ_FRACAS) else []
    except Exception:
        lista = []
    if titulo and not any(x.get("titulo") == titulo for x in lista):
        lista.append({"titulo": titulo, "nota": nota, "em": datetime.now().isoformat(timespec="minutes")})
        os.makedirs(os.path.dirname(ARQ_FRACAS), exist_ok=True)
        json.dump(lista[-100:], open(ARQ_FRACAS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    log(f"Tratamento: foto fraca (nota {nota}) em: {titulo[:70]}")


# ---------------- vídeo gravado ----------------
# Filtro do ffmpeg com o mesmo padrão para vídeos gravados (limpeza leve, contraste, cor e nitidez).
FILTRO_VIDEO = "hqdn3d=1.5:1.5:6:6,eq=contrast=1.05:saturation=1.05:gamma=1.02,unsharp=5:5:0.55:5:5:0.0"
