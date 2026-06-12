# 📱 Como ver o FielCup no celular

Você tem dois caminhos. O **caminho 2 (nuvem)** é o recomendado: gera um
**link público** que abre em qualquer celular, de qualquer lugar, sem o seu
computador precisar estar ligado.

---

## Caminho 1 — Agora, na mesma rede Wi-Fi (rápido, temporário)

Serve para testar na hora. Funciona só enquanto o seu computador estiver
ligado e o celular estiver no **mesmo Wi-Fi**.

1. No computador, dentro da pasta do projeto, rode:
   ```bash
   source venv/bin/activate
   streamlit run app/dashboard.py
   ```
2. No **celular** (mesmo Wi-Fi), abra no navegador:
   ```
   http://192.168.4.51:8521
   ```
   > Esse é o IP do seu computador agora. Se mudar de rede, descubra o novo
   > com: `ipconfig getifaddr en0`

---

## Caminho 2 — Na nuvem, link público (recomendado) 🌐

Publica o dashboard de graça no **Streamlit Community Cloud**. Depois é só
salvar o link nos favoritos do celular. Atualiza sozinho sempre que você der
`git push`.

### Passo a passo (uma vez só, ~3 minutos)

1. Acesse **https://share.streamlit.io** e clique em **"Continue with GitHub"**.
   Faça login com a sua conta **Willian-Yudy-F** e autorize o acesso.

2. Clique em **"Create app"** → **"Deploy a public app from GitHub"**.

3. Preencha exatamente assim:
   - **Repository:** `Willian-Yudy-F/FielCup`
   - **Branch:** `main`
   - **Main file path:** `app/dashboard.py`

4. Clique em **"Deploy"**. Espere 1–3 minutos (ele instala tudo sozinho a
   partir do `requirements.txt`).

5. Pronto! Você recebe um link parecido com:
   ```
   https://fielcup.streamlit.app
   ```
   Abra esse link no celular e **adicione à tela inicial** (no Safari/Chrome:
   menu → "Adicionar à Tela de Início"). Vira quase um aplicativo. ✅

### Observações
- O link é **público** — qualquer pessoa com ele vê o dashboard (ótimo para
  mostrar no portfólio / mandar para alguém).
- Os placares que você digitar **na versão da nuvem** são temporários (somem
  quando o app reinicia). Para registro permanente, use no computador e dê
  `git push` do `db/fielcup.db`.
- Para **atualizar** o app publicado, basta `git push` na branch `main`: a
  nuvem republica sozinha.

---

## Qual escolher?

| | Caminho 1 (Wi-Fi) | Caminho 2 (Nuvem) |
|---|---|---|
| Abre de qualquer lugar | ❌ só no mesmo Wi-Fi | ✅ sim |
| Precisa do PC ligado | ✅ sim | ❌ não |
| Link fixo p/ favoritar | ❌ | ✅ |
| Bom para portfólio | ❌ | ✅ |

➡️ Para o seu objetivo (ver no celular e entender o que está acontecendo),
**use o Caminho 2**.
