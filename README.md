# Kit de PDF

Um kit simples para mexer em PDF **no seu PC, offline** — sem mandar seus arquivos pra site nenhum.
Arrasta os arquivos pra janela e usa:

- 🔗 **Juntar** — vários PDFs num só (na ordem da lista)
- ✂️ **Separar / extrair** — tira um intervalo de páginas (ex.: `1-3,5`) ou quebra o PDF em uma página por arquivo
- 🔄 **Girar** — vira as páginas 90°, 180° ou 270°
- 🗜️ **Comprimir** — deixa o arquivo menor (recompacta os fluxos sem perda e reduz/recomprime as imagens)
- 🖼️ **Imagens → PDF** — junta fotos (JPG/PNG…) num PDF, uma por página
- 📝 **Extrair texto** — salva o texto do PDF num `.txt`

Feito em Python + PyQt6. Roda no Windows.

![Kit de PDF](#) <!-- coloque aqui um print da janela se quiser -->

## Instalar e usar

```sh
pip install -r requirements.txt
python kit_pdf.pyw
```

Arraste PDFs/imagens para a janela (ou “Adicionar arquivos”) e clique na operação. Quando houver mais
de um PDF na lista, clique no que você quer usar antes de separar/girar/comprimir/extrair texto.

## Como funciona (sem nuvem)

Tudo roda localmente com [pypdf](https://pypdf.readthedocs.io) (juntar/separar/girar/texto),
[pikepdf](https://pikepdf.readthedocs.io) (comprimir) e [Pillow](https://python-pillow.org)
(imagens). Nenhum arquivo sai do seu computador.

Sobre a **compressão**: a recompactação dos fluxos é sem perda; o ganho maior vem de reduzir e
recomprimir as imagens embutidas (padrão: no máx. 1600 px no maior lado, JPEG qualidade 60). Imagens
com transparência/máscara são preservadas como estão. Se o PDF já estiver enxuto, ele avisa que não
dava pra reduzir muito — e nunca salva um arquivo maior que o original.

## Licença

MIT.
