# Protocolo de assessorias (aprovado por Washington em 27/11/2026)

Os textos dos e-mails e as regras de envio estão em `emails/modelos.md`. Este arquivo diz como o cadastro funciona.

## Arquivos

- `cadastro.json`: todas as pessoas da lista do Drive "Lista Assessorias + Colunistas + equipe + colaborador".
- `arrobas.json`: a tabela de arrobas, para reaproveitar em collab e legendas.

## Cadastro

- **O e-mail é a chave.** Nome repetido com o mesmo e-mail vira um cadastro só, e os outros nomes ficam como apelidos.
- **Mesmo e-mail de empresa usado por várias pessoas:** continua um cadastro por e-mail, com os nomes como apelidos. O e-mail vai uma vez só.
- **Mesmo nome com e-mails diferentes:** cada e-mail recebe o seu envio. O campo `mesma_pessoa` só liga os dois, para os lembretes pararem nos dois quando a pessoa responder em um deles.
- **E-mails corrigidos:** só erro certo, como o Gmail com ".com.br". Casos duvidosos ficam como vieram, com observação.
- **Situação:**
  - `ativo`: aparece no RSS do site. Recebe o modelo 7.
  - `parado`: está na lista e ainda não apareceu no RSS. Recebe o convite (modelo 1).
  - `novo`: pediu pauta e não está no cadastro. Pede-se nome, e-mail e Instagram, e depois vai o modelo 6.
  - Equipe, colunistas e colaboradores não recebem os e-mails de assessoria.
- **Sem janela de tempo.** A partir de 27/11/2026, toda vez que alguém aparecer no RSS, passa para `ativo`.
- **Atualização:** Washington completa a lista no Drive durante a semana, avisa, e o cadastro é sincronizado. Nada é apagado: quem sai da lista fica marcado.

## Tabela de arrobas

- **Espaço `assessoria`:** os @ que a assessoria mandou, pelo formulário ou por e-mail. Valem mais que os do sistema.
- **Espaço `sistema`:** os @ que o robô acha no texto das matérias (de artista, espaço cultural, evento ou projeto). Foi montado com as matérias já guardadas no GitHub, sem entrar no site.
- O robô consulta a tabela pelo nome (sem diferenciar maiúsculas e acentos) antes de pedir @ à assessoria e ao montar o collab (até 3 perfis).
- Nome marcado "a confirmar" não é usado na legenda até ser conferido.
