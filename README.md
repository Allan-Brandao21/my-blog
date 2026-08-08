This is a [Next.js](https://nextjs.org/) project bootstrapped with [`create-next-app`](https://github.com/vercel/next.js/tree/canary/packages/create-next-app).

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `pages/index.js`. The page auto-updates as you edit the file.

[API routes](https://nextjs.org/docs/api-routes/introduction) can be accessed on [http://localhost:3000/api/hello](http://localhost:3000/api/hello). This endpoint can be edited in `pages/api/hello.js`.

The `pages/api` directory is mapped to `/api/*`. Files in this directory are treated as [API routes](https://nextjs.org/docs/api-routes/introduction) instead of React pages.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js/) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/deployment) for more details.

---

# Lâmpada — plano de leitura (`lampada-plano-de-leitura.html`)

App de página única (HTML + CSS + JS puro). **Sem npm, sem build, sem dependências**:
basta abrir o arquivo no navegador. O progresso fica no `localStorage` e, se você
quiser, é espelhado numa nuvem à sua escolha.

## Onde o progresso pode ser guardado

No rodapé do app, botão **☁️ Sincronizar**, campo **Onde salvar**:

| Backend | O que faz |
|---|---|
| **Só neste aparelho** (padrão) | Nada sai do navegador. |
| **GitHub** | Grava um `progresso.json` num repositório privado seu. |
| **Supabase** | Grava numa tabela `lampada` do seu projeto Supabase. |
| **Endpoint próprio** | Qualquer endereço que responda `GET` (lê) e `PUT` (grava). |

O `localStorage` é sempre a fonte primária: se a rede cair, o app funciona igual,
a fila fica pendente e é enviada sozinha depois. Antes de **toda** gravação remota
o app lê o remoto e mescla os dois lados — a etapa lida no celular nunca é apagada
pelo computador.

---

## Passo a passo do backend GitHub

### 1. Criar o repositório privado do progresso

1. Acesse <https://github.com/new>.
2. **Repository name:** `lampada-progresso` (ou o nome que preferir).
3. Marque **Private**.
4. Marque **Add a README file** — o repositório precisa ter pelo menos um commit
   para que a branch `main` exista.
5. Clique em **Create repository**.

Não é preciso criar o `progresso.json` à mão: o app cria o arquivo no primeiro
salvamento (a API devolve 404, e o app trata isso como "ainda não existe").

### 2. Gerar o token fine-grained

1. Vá em **Settings** (do seu perfil) → **Developer settings** →
   **Personal access tokens** → **Fine-grained tokens** →
   **Generate new token**. Atalho: <https://github.com/settings/personal-access-tokens/new>.
2. **Token name:** `lampada`.
3. **Expiration:** escolha o prazo. Quando expirar, gere outro e cole de novo no app.
4. **Resource owner:** sua conta.
5. **Repository access:** marque **Only select repositories** e escolha
   **apenas** o `lampada-progresso`.
6. **Permissions → Repository permissions:** localize **Contents** e mude para
   **Read and write**. Deixe **todo o resto em "No access"**.
   (O GitHub adiciona **Metadata: Read-only** sozinho — é obrigatório, pode deixar.)
7. **Generate token** e copie o valor (`github_pat_…`). Ele só aparece uma vez.

> O token fica salvo **no navegador** (`localStorage`), como qualquer senha que
> você manda o navegador lembrar. Por isso ele precisa ser fine-grained e limitado
> a um único repositório com `contents: write`: mesmo vazando, ele não alcança
> nada além do arquivo de progresso. Não use um token clássico (`ghp_…`), que dá
> acesso a tudo. Se perder o aparelho, revogue o token na mesma tela.

### 3. Conectar o app

1. Abra o app, role até o rodapé e clique em **☁️ Sincronizar**.
2. Em **Onde salvar**, escolha **GitHub (repositório privado)**.
3. Preencha:
   - **Usuário ou organização:** seu usuário do GitHub
   - **Repositório:** `lampada-progresso`
   - **Arquivo:** `progresso.json`
   - **Branch:** `main`
   - **Token de acesso:** o `github_pat_…` copiado
4. Clique em **Testar conexão**. Deve aparecer
   *"✓ Leitura e gravação funcionando"*. Se der erro, a mensagem exibida é a
   resposta real da API do GitHub:
   - `HTTP 401 — Bad credentials` → token errado, expirado ou revogado
   - `HTTP 404 — Not Found` → nome do usuário/repositório errado, ou o token não
     tem esse repositório em **Only select repositories**
   - `HTTP 403 — Resource not accessible by personal access token` → falta a
     permissão **Contents: Read and write**
   - `HTTP 409/422` → o app já refaz a leitura e tenta de novo sozinho
5. Clique em **Conectar e sincronizar**. Pronto — repita os mesmos passos no
   outro aparelho, com o mesmo repositório e o mesmo token (ou um token novo
   apontando para o mesmo repositório).

### Como fica o histórico

Cada gravação é um commit com a mensagem `progresso: 12/60 etapas`. O envio é
adiado em **8 segundos** para não gerar um commit por tecla digitada nas
anotações; o salvamento local continua instantâneo. Ao fechar a aba, o envio
pendente é disparado com `keepalive`.

---

## Publicar no GitHub Pages

O arquivo é estático — dá para abrir direto do disco. Publicar só serve para
abrir pela mesma URL no celular e no computador.

1. Crie um **segundo** repositório para hospedar a página (ex.: `lampada`).
   Pages em repositório **privado** exige plano pago; se o seu é gratuito,
   deixe este repositório **público**. Não tem problema: o token não está no
   arquivo, ele fica no `localStorage` de cada navegador. O repositório do
   *progresso* continua privado.
2. Envie o arquivo, renomeando para `index.html`:
   ```bash
   git clone https://github.com/SEU-USUARIO/lampada.git
   cd lampada
   cp .../lampada-plano-de-leitura.html index.html
   git add index.html
   git commit -m "publica o plano de leitura"
   git push
   ```
   (Ou use **Add file → Upload files** pela interface do GitHub.)
3. No repositório: **Settings** → **Pages** → em **Source** escolha
   **Deploy from a branch**, branch `main`, pasta `/ (root)` → **Save**.
4. Em um a dois minutos a página estará em
   `https://SEU-USUARIO.github.io/lampada/`. Abra no celular e use
   **Compartilhar → Adicionar à Tela de Início**.
5. Configure o backend GitHub (passo 3 acima) em cada aparelho.

> A página do Pages passa por CDN e fica em cache por alguns minutos. Isso afeta
> só o *app*: o progresso é sempre lido pela `api.github.com` com `Cache-Control:
> no-cache`, nunca pela URL do Pages. Se você atualizar o HTML e não vir a
> mudança, force um recarregamento.

---

## Backup manual

Independente do backend, os botões **↓ Baixar backup** e **↑ Restaurar backup**
continuam funcionando e salvam/leem um `.json` local. É a rede de segurança que
não depende de nada.

## Backends alternativos

- **Supabase:** precisa de uma tabela `lampada` com as colunas `id` (text,
  primary key) e `data` (jsonb). Preencha URL do projeto, chave anon e um código
  pessoal.
- **Endpoint próprio:** qualquer endereço que responda `GET` devolvendo o estado
  em JSON (ou 404 se ainda não existe) e aceite `PUT` gravando o corpo enviado.
  O campo de token, se preenchido, vira um header `Authorization: Bearer …`.
