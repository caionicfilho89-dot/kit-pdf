"""Operações de PDF — sem interface, para dar para testar e reusar.

Tudo offline, usando pypdf (juntar/separar/girar/texto), pikepdf (comprimir) e Pillow (imagens).
"""
import io
import os

from pypdf import PdfReader, PdfWriter


def page_count(path):
    return len(PdfReader(path).pages)


def parse_ranges(spec, n):
    """'1-3,5,8-' -> lista de índices 0-based (1-based na entrada), dentro de 1..n, na ordem pedida."""
    out = []
    for part in str(spec).replace(" ", "").split(","):
        if not part:
            continue
        if "-" in part:
            a, _, b = part.partition("-")
            a = int(a) if a else 1
            b = int(b) if b else n
            step = 1 if b >= a else -1
            for i in range(a, b + step, step):
                if 1 <= i <= n:
                    out.append(i - 1)
        else:
            i = int(part)
            if 1 <= i <= n:
                out.append(i - 1)
    return out


def merge(paths, out):
    """Junta vários PDFs (na ordem dada) num só."""
    if len(paths) < 2:
        raise ValueError("Escolha pelo menos 2 PDFs para juntar.")
    w = PdfWriter()
    for p in paths:
        w.append(p)
    with open(out, "wb") as f:
        w.write(f)
    return out


def extract(path, spec, out):
    """Tira as páginas de `spec` (ex.: '1-3,5') para um novo PDF."""
    r = PdfReader(path)
    idxs = parse_ranges(spec, len(r.pages))
    if not idxs:
        raise ValueError("Nenhuma página válida nesse intervalo.")
    w = PdfWriter()
    for i in idxs:
        w.add_page(r.pages[i])
    with open(out, "wb") as f:
        w.write(f)
    return out, len(idxs)


def split_each(path, out_dir):
    """Cada página vira um PDF. Devolve a lista de arquivos criados."""
    r = PdfReader(path)
    n = len(r.pages)
    base = os.path.splitext(os.path.basename(path))[0]
    os.makedirs(out_dir, exist_ok=True)
    width = len(str(n))
    outs = []
    for i in range(n):
        w = PdfWriter()
        w.add_page(r.pages[i])
        o = os.path.join(out_dir, f"{base}_pag{str(i + 1).zfill(width)}.pdf")
        with open(o, "wb") as f:
            w.write(f)
        outs.append(o)
    return outs


def rotate(path, out, angle, spec=""):
    """Gira as páginas (90, 180 ou 270 graus, horário). spec vazio = todas."""
    angle = int(angle) % 360
    r = PdfReader(path)
    chosen = set(parse_ranges(spec, len(r.pages))) if str(spec).strip() else set(range(len(r.pages)))
    w = PdfWriter()
    for i, pg in enumerate(r.pages):
        if i in chosen and angle:
            pg.rotate(angle)
        w.add_page(pg)
    with open(out, "wb") as f:
        w.write(f)
    return out


def images_to_pdf(image_paths, out):
    """Junta imagens (JPG/PNG/…) num PDF, uma por página."""
    from PIL import Image
    imgs = []
    for p in image_paths:
        im = Image.open(p)
        imgs.append(im.convert("RGB") if im.mode not in ("RGB", "L") else im)
    if not imgs:
        raise ValueError("Escolha pelo menos uma imagem.")
    imgs[0].save(out, "PDF", save_all=True, append_images=imgs[1:])
    return out


def extract_text(path, out):
    """Puxa o texto do PDF para um .txt (vazio se o PDF for só imagem/escaneado)."""
    r = PdfReader(path)
    parts = []
    for i, pg in enumerate(r.pages):
        parts.append(f"--- Página {i + 1} ---\n{pg.extract_text() or ''}".rstrip())
    text = "\n\n".join(parts) + "\n"
    with open(out, "w", encoding="utf-8") as f:
        f.write(text)
    return out, len(text.strip())


def _recompress_images(pdf, quality, max_dim):
    """Best-effort: reduz e recomprime as imagens grandes do PDF. Qualquer imagem problemática é pulada."""
    import pikepdf
    from PIL import Image
    for page in pdf.pages:
        try:
            images = page.images
        except Exception:  # noqa: BLE001
            continue
        for raw in list(images.values()):
            try:
                if "/SMask" in raw or "/Mask" in raw or raw.get("/ImageMask"):
                    continue   # transparência/máscara: mexer pode corromper — deixa quieto
                pimg = pikepdf.PdfImage(raw)
                pil = pimg.as_pil_image()
                w, h = pil.size
                scale = min(1.0, max_dim / max(w, h))
                if scale >= 1.0 and pil.mode in ("RGB", "L"):
                    new = pil            # já pequena e em RGB/cinza: só tenta recomprimir em JPEG
                else:
                    new = pil.resize((max(1, int(w * scale)), max(1, int(h * scale))))
                if new.mode not in ("RGB", "L"):
                    new = new.convert("RGB")
                buf = io.BytesIO()
                new.save(buf, "JPEG", quality=quality)
                data = buf.getvalue()
                if len(data) >= len(raw.read_raw_bytes()):
                    continue   # não ficou menor: mantém o original
                raw.write(data, filter=pikepdf.Name("/DCTDecode"))
                raw.ColorSpace = pikepdf.Name("/DeviceRGB" if new.mode == "RGB" else "/DeviceGray")
                raw.Width, raw.Height = new.size
                raw.BitsPerComponent = 8
                for k in ("/DecodeParms", "/Decode"):
                    if k in raw:
                        del raw[k]
            except Exception:  # noqa: BLE001 - imagem exótica: pula sem derrubar a compressão
                continue


def compress(path, out, images=True, quality=60, max_dim=1600):
    """Diminui o PDF: recompacta os fluxos (sem perda) e, se `images`, reduz/recomprime as imagens.
    Devolve (caminho, tamanho_antes, tamanho_depois)."""
    import pikepdf
    before = os.path.getsize(path)
    pdf = pikepdf.open(path)
    try:
        if images:
            _recompress_images(pdf, quality, max_dim)
        pdf.save(out, compress_streams=True, recompress_flate=True,
                 object_stream_mode=pikepdf.ObjectStreamMode.generate)
    finally:
        pdf.close()
    return out, before, os.path.getsize(out)
