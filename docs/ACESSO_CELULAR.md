# Como ver o FielCup no celular

Use o link estático do GitHub Pages:

```text
https://willian-yudy-f.github.io/FielCup/
```

Essa página não usa Streamlit. Ela é um HTML leve, abre direto no navegador do
celular e mostra automaticamente os jogos da data atual. Também tem um botão
para ir direto ao próximo dia em que o Brasil joga.

## Como atualizar a página

No computador, depois de atualizar resultados no banco:

```bash
python scripts/build_static_reports.py
git add docs/index.html db/fielcup.db
git commit -m "Update mobile match report"
git push origin main
```

O GitHub Pages publica a nova versão automaticamente.

## Plano B: mesma rede Wi-Fi

Se quiser abrir o dashboard completo do Streamlit dentro de casa, rode:

```bash
streamlit run app/dashboard.py --server.address 0.0.0.0
```

Depois, no celular conectado ao mesmo Wi-Fi, abra o endereço que aparecer como
`Network URL`.
