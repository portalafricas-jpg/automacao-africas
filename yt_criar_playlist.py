# Cria uma playlist pública no canal (se ainda não existir uma com o mesmo nome-chave).
import sys
import requests
import youtube as Y

def main(titulo, descricao, chave):
    existente = Y.id_playlist(chave)
    if existente:
        print(f"Já existe playlist com '{chave}': {existente}")
        return
    r = requests.post("https://www.googleapis.com/youtube/v3/playlists", params={"part": "snippet,status"},
                      headers={"Authorization": f"Bearer {Y.token()}"}, timeout=30,
                      json={"snippet": {"title": titulo, "description": descricao, "defaultLanguage": "pt-BR"},
                            "status": {"privacyStatus": "public"}})
    if r.status_code >= 300:
        raise SystemExit(f"Erro {r.status_code}: {r.text[:300]}")
    print("Playlist criada:", r.json()["id"])

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
