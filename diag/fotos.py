import robo
link="https://www.geledes.org.br/comunidades-religiosas-reivindicam-lugar-na-agenda-climatica-em-evento-paralelo-a-cop31/"
o=robo.extrair_materia(link)
print("FOTO principal:", o["imagem"][-60:], "| crédito:", o["credito_foto"], "| veículo:", o["veiculo"])
print("FOTO pode principal?", robo.foto_nao_pode(o["credito_foto"], o["veiculo"], link, True, o["imagem"]) or "sim")
for f in o["fotos_corpo"]:
    print("FOTO corpo:", f["url"][-50:], "|", f["legenda"][:60], "|", f["credito"], "| pode?", robo.foto_nao_pode(f["credito"], o["veiculo"], link, True, f["url"]) or "sim")
print("FOTO teste agência:", robo.foto_nao_pode("Reuters/Fulano", "X", "https://x.com/a", True, "a.jpg"))
