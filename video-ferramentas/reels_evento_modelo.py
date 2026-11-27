# MODELO PADRÃO DE REELS DE EVENTO (aprovado em 27/11/2026, CASE).
# Legenda embaixo (palavra falada em amarelo), 3 a 4 palavras-chave grandes correndo devagar por trás da cabeça
# (máscara do MediaPipe), caixa BAIXE O APP + selos das lojas em carrossel, áudio tratado, abertura e cartão final.
# Entradas: vídeo da fala + saídas de video-ferramentas/processar.py (transcrição e máscara).
import json, subprocess, numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
W,H,FPS=1080,1920,30; T0=4.1; DUR=27.9; NF=int(DUR*FPS)
U='/mnt/user-data/uploads/'
FB='/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf'
FX='/usr/share/fonts/truetype/google-fonts/Poppins-ExtraBold.ttf'
import os
if not os.path.exists(FX): FX=FB
Y=(255,204,0); WH=(255,255,255)
# ---- palavras corrigidas (tempo do vídeo original) ----
segs=json.load(open('/home/claude/automacao-africas/video-ferramentas/saida/case_fala_selfie_fala.json'))
pw=[(w['p'],w['i']) for s in segs for w in s['palavras'] if w['i']>=4.0]
fix={'case.':'CASE.','start':'Startups','-ups':None,'empreendedorismo.':'Empreendedorismo.','conferência':'Conferência',
     'noca.':None,'África':'Áfricas','Estreja':'Play'}
out=[]
for i,(p,t) in enumerate(pw):
    if p in fix:
        if fix[p] is None: continue
        p=fix[p]
    out.append([p,t])
def rep(old_seq,new_seq):
    global out
    ws=[w for w,_ in out]
    for k in range(len(ws)-len(old_seq)+1):
        if ws[k:k+len(old_seq)]==old_seq:
            ts=[out[k+j][1] for j in range(len(old_seq))]
            nw=[[new_seq[j], ts[min(j,len(ts)-1)]] for j in range(len(new_seq))]
            out=out[:k]+nw+out[k+len(old_seq):]; return
rep(['é','meio'],['também','inova.'])
rep(['O','que','é','mais','informações'],['Quer','mais','informações?'])
rep(['é','só'],['É','só'])
words=[(w,t-T0) for w,t in out]
ends=[words[i+1][1] for i in range(len(words)-1)]+[DUR]
# frases (quebra em pontuação ou 5 palavras)
chunks=[]; cur=[]
for i,(w,t) in enumerate(words):
    cur.append(i)
    if w[-1] in '.?!' or len(cur)>=5: chunks.append(cur); cur=[]
if cur: chunks.append(cur)
open('legenda_usada.txt','w').write(' '.join(w for w,_ in words))
fsub=ImageFont.truetype(FB,52)
def sub_layer(t):
    for ci,ch in enumerate(chunks):
        st=words[ch[0]][1]; en=words[chunks[ci+1][0]][1] if ci+1<len(chunks) else DUR
        if st-0.05<=t<en:
            cw=None
            for i in ch:
                if words[i][1]<=t<ends[i]: cw=i
            txt=[(words[i][0],i==cw) for i in ch]
            d0=ImageDraw.Draw(Image.new('RGBA',(1,1))); sp=d0.textlength(' ',font=fsub)
            tw=sum(d0.textlength(w,font=fsub) for w,_ in txt)+sp*(len(txt)-1)
            im=Image.new('RGBA',(W,140),(0,0,0,0)); d=ImageDraw.Draw(im); x=(W-tw)/2
            for w,hl in txt:
                d.text((x,30),w,font=fsub,fill=Y if hl else WH,stroke_width=4,stroke_fill=(0,0,0)); x+=d.textlength(w,font=fsub)+sp
            return im
    return None
# palavras-chave que correm atrás da cabeça
def kw_img(txt,cor,size=420):
    f=ImageFont.truetype(FX,size); w=int(ImageDraw.Draw(Image.new('RGBA',(1,1))).textlength(txt,font=f))+60; h=int(size*1.3)
    sh=Image.new('RGBA',(w,h),(0,0,0,0)); ImageDraw.Draw(sh).text((30,10),txt,font=f,fill=(0,0,0,170)); sh=sh.filter(ImageFilter.GaussianBlur(14))
    im=Image.new('RGBA',(w,h),(0,0,0,0)); im.alpha_composite(sh); ImageDraw.Draw(im).text((30,0),txt,font=f,fill=cor+(255,)); return im
KW=[("CASE",1.8,8.5,Y),("NEGRO",8.6,15.0,WH),("ÁFRICAS PLAY",15.1,22.1,Y),("NOTÍCIA PRETA",22.2,27.9,WH)]
KWI=[(kw_img(t,c),s,e) for t,s,e,c in KW]
# barra do app
fapp=ImageFont.truetype(FX,58)
box=Image.new('RGBA',(400,150),(0,0,0,0)); ImageDraw.Draw(box).rounded_rectangle((0,0,399,149),radius=24,fill=Y+(255,))
bd=ImageDraw.Draw(box); tt="BAIXE O APP"; bd.text(((400-bd.textlength(tt,font=fapp))/2,38),tt,font=fapp,fill=(0,0,0))
strip=Image.open('/home/claude/trab/reels/lojas_strip.png').convert('RGBA')
APP0,APP1=19.2,24.6
handle=Image.open('/home/claude/trab/reels/handle.png').convert('RGBA')
# ---- leitores de vídeo ----
def reader(args,w,h,ch):
    p=subprocess.Popen(["ffmpeg","-v","error"]+args+["-vf",f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}","-r",str(FPS),"-f","rawvideo","-pix_fmt","rgb24" if ch==3 else "gray","-"],stdout=subprocess.PIPE)
    return p
main=reader(["-ss",str(T0),"-t",str(DUR),"-i",U+"1001130913.mp4"],W,H,3)
mask=reader(["-ss",str(T0),"-t",str(DUR),"-i","/home/claude/automacao-africas/video-ferramentas/saida/case_fala_selfie_mascara.mp4"],W,H,1)
c1=reader(["-ss","2","-t","2.6","-i",U+"1001130797.mp4"],W,H,3); C1=(12.0,14.6)
photo=Image.open(U+'87eaf0f3-image.jpg').convert('RGB'); C2=(15.2,18.8)
s=max(W/photo.width,H/photo.height); photo=photo.resize((int(photo.width*s),int(photo.height*s)))
enc=subprocess.Popen(["ffmpeg","-v","error","-y","-f","rawvideo","-pix_fmt","rgb24","-s",f"{W}x{H}","-r",str(FPS),"-i","-",
     "-ss",str(T0),"-t",str(DUR),"-i",U+"1001130913.mp4","-map","0:v","-map","1:a",
     "-af","highpass=f=110,lowpass=f=9000,afftdn=nf=-30:nr=20:tn=1,agate=threshold=0.02:ratio=2:release=200,acompressor=threshold=-20dB:ratio=3:attack=5:release=120,loudnorm=I=-14:TP=-1.5",
     "-c:v","libx264","-preset","veryfast","-crf","21","-pix_fmt","yuv420p","-c:a","aac","-ar","48000","-ac","2","-shortest","B7.mp4"],stdin=subprocess.PIPE)
for n in range(NF):
    t=n/FPS
    fb=main.stdout.read(W*H*3); mb=mask.stdout.read(W*H)
    if len(fb)<W*H*3: break
    base=Image.frombytes('RGB',(W,H),fb).convert('RGBA')
    m=Image.frombytes('L',(W,H),mb) if len(mb)==W*H else Image.new('L',(W,H),0)
    cut=None
    if C1[0]<=t<C1[1]:
        cb=c1.stdout.read(W*H*3)
        if len(cb)==W*H*3: cut=Image.frombytes('RGB',(W,H),cb).convert('RGBA')
    elif C2[0]<=t<C2[1]:
        z=1+0.04*(t-C2[0])/(C2[1]-C2[0]); pw_,ph_=int(photo.width/z),int(photo.height/z)
        x0=(photo.width-pw_)//2; y0=(photo.height-ph_)//3
        cut=photo.crop((x0,y0,x0+pw_,y0+ph_)).resize((W,H)).convert('RGBA')
    frame=cut if cut is not None else base.copy()
    # palavras-chave correndo (atrás da cabeça quando é a fala)
    for im,s_,e_ in KWI:
        if s_<=t<e_:
            p=(t-s_)/(e_-s_); x=int(W-(W+im.width)*p); y=560-im.height//2
            frame.alpha_composite(im,(x,y)) if 0<=x and x+im.width<=W else frame.paste(im,(x,y),im)
    if cut is None:
        frame.paste(base,(0,0),m)  # pessoa por cima das palavras
    # barra do app: caixa à esquerda + selos passando
    if APP0<=t<APP1:
        k=min(1,(t-APP0)/0.35); bx=int(-420+460*k); yb=1300
        off=int((t-APP0)*150); view=Image.new('RGBA',(W,150),(0,0,0,0)); view.paste(strip,(W-off,0),strip)
        frame.alpha_composite(view.crop((0,0,W,150)),(0,yb)) if True else None
        frame.alpha_composite(box,(max(bx,-400),yb)) if bx>-400 else None
    sl=sub_layer(t)
    if sl: frame.alpha_composite(sl,(0,1560))
    frame.alpha_composite(handle,((W-handle.width)//2,1730))
    enc.stdin.write(frame.convert('RGB').tobytes())
enc.stdin.close(); enc.wait(); print('ok',n)
