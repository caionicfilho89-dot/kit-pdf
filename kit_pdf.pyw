"""Kit de PDF — juntar, separar, girar, comprimir, imagens→PDF e extrair texto. Tudo offline, no seu PC."""
import os
import sys

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import (QAbstractItemView, QApplication, QFileDialog, QFrame, QGridLayout,
                             QHBoxLayout, QInputDialog, QLabel, QListWidget, QListWidgetItem,
                             QMessageBox, QPushButton, QVBoxLayout, QWidget)

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pdfops  # noqa: E402

IMG_EXT = (".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tif", ".tiff", ".webp")

QSS = """
QWidget { background:#11131a; color:#e7e9f0; font:10pt 'Segoe UI'; }
#title { font:700 20pt 'Segoe UI'; }
#sub { color:#8a93a8; }
QListWidget { background:#1b202b; border:2px dashed #39415a; border-radius:12px; padding:6px; }
QListWidget:focus { border-color:#7c5cff; }
QListWidget::item { padding:6px 8px; border-radius:6px; }
QListWidget::item:selected { background:#2d3550; }
QPushButton { background:#222a38; border:0; border-radius:12px; padding:14px; text-align:left; }
QPushButton:hover { background:#2d3550; }
QPushButton:disabled { color:#5b6377; }
#small { padding:8px 14px; }
#go { background:#7c5cff; color:#fff; font-weight:600; }
#go:hover { background:#8f74ff; }
#status { color:#8a93a8; padding-top:4px; }
"""

TOOLS = [
    ("merge",    "🔗  Juntar",          "Vários PDFs num só"),
    ("split",    "✂️  Separar / extrair", "Tira páginas ou quebra em várias"),
    ("rotate",   "🔄  Girar",           "Vira páginas de lado / de cabeça"),
    ("compress", "🗜️  Comprimir",        "Deixa o arquivo menor"),
    ("img2pdf",  "🖼️  Imagens → PDF",    "Junta fotos num PDF"),
    ("text",     "📝  Extrair texto",    "Salva o texto num .txt"),
]


class Task(QThread):
    done = pyqtSignal(bool, str, str)   # ok, mensagem, pasta do resultado

    def __init__(self, fn, parent=None):
        super().__init__(parent)
        self.fn = fn

    def run(self):
        try:
            msg, folder = self.fn()
            self.done.emit(True, msg, folder or "")
        except Exception as e:  # noqa: BLE001
            self.done.emit(False, str(e), "")


def app_icon():
    pm = QPixmap(64, 64)
    pm.fill(QColor("transparent"))
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor("#7c5cff"))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(8, 6, 48, 52, 10, 10)
    p.setPen(QColor("white"))
    p.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
    p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, "PDF")
    p.end()
    return QIcon(pm)


class KitPDF(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Kit de PDF")
        self.setWindowIcon(app_icon())
        self.setAcceptDrops(True)
        self.resize(560, 620)
        self.last_folder = ""
        self.task = None

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 16)
        root.setSpacing(10)

        title = QLabel("Kit de PDF")
        title.setObjectName("title")
        sub = QLabel("Tudo no seu PC, offline. Arraste os arquivos aqui ou clique em “Adicionar”.")
        sub.setObjectName("sub")
        root.addWidget(title)
        root.addWidget(sub)

        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list.setMinimumHeight(150)
        root.addWidget(self.list, 1)

        row = QHBoxLayout()
        add = QPushButton("➕  Adicionar arquivos")
        add.setObjectName("small")
        add.clicked.connect(self.add_files)
        clear = QPushButton("🗑️  Limpar")
        clear.setObjectName("small")
        clear.clicked.connect(self.clear_files)
        row.addWidget(add)
        row.addWidget(clear)
        row.addStretch(1)
        root.addLayout(row)

        grid = QGridLayout()
        grid.setSpacing(8)
        self.tool_btns = []
        for i, (key, label, desc) in enumerate(TOOLS):
            b = QPushButton(f"{label}\n{desc}")
            b.setObjectName("go" if key == "merge" else "")
            b.setMinimumHeight(58)
            b.clicked.connect(lambda _c, k=key: self.run_tool(k))
            grid.addWidget(b, i // 2, i % 2)
            self.tool_btns.append(b)
        root.addLayout(grid)

        bottom = QHBoxLayout()
        self.status = QLabel("Pronto.")
        self.status.setObjectName("status")
        self.status.setWordWrap(True)
        self.open_btn = QPushButton("📂  Abrir pasta do resultado")
        self.open_btn.setObjectName("small")
        self.open_btn.setEnabled(False)
        self.open_btn.clicked.connect(self.open_result)
        bottom.addWidget(self.status, 1)
        bottom.addWidget(self.open_btn)
        root.addLayout(bottom)

    # ---- lista de arquivos -------------------------------------------------
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        self._add([u.toLocalFile() for u in e.mimeData().urls()])

    def add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Escolher arquivos", "", "PDF e imagens (*.pdf *.jpg *.jpeg *.png *.bmp *.gif *.tif *.tiff *.webp)")
        self._add(paths)

    def _add(self, paths):
        existing = {self.list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.list.count())}
        for p in paths:
            if not p or p in existing or not os.path.isfile(p):
                continue
            if p.lower().endswith((".pdf",) + IMG_EXT):
                it = QListWidgetItem(("📄 " if p.lower().endswith(".pdf") else "🖼️ ") + os.path.basename(p))
                it.setData(Qt.ItemDataRole.UserRole, p)
                self.list.addItem(it)
                existing.add(p)
        self.set_status(f"{self.list.count()} arquivo(s) na lista.")

    def clear_files(self):
        self.list.clear()
        self.set_status("Lista limpa.")

    def _paths(self, kind=None):
        """Todos os caminhos da lista (na ordem). kind='pdf' ou 'img' para filtrar."""
        out = []
        for i in range(self.list.count()):
            p = self.list.item(i).data(Qt.ItemDataRole.UserRole)
            is_pdf = p.lower().endswith(".pdf")
            if kind == "pdf" and not is_pdf:
                continue
            if kind == "img" and is_pdf:
                continue
            out.append(p)
        return out

    def _selected_paths(self, kind=None):
        sel = []
        for it in self.list.selectedItems():
            p = it.data(Qt.ItemDataRole.UserRole)
            if kind == "pdf" and not p.lower().endswith(".pdf"):
                continue
            if kind == "img" and p.lower().endswith(".pdf"):
                continue
            sel.append(p)
        return sel

    def _one_pdf(self):
        """O PDF para operar: o selecionado, ou o único da lista."""
        sel = self._selected_paths("pdf")
        if len(sel) == 1:
            return sel[0]
        pdfs = self._paths("pdf")
        if len(pdfs) == 1:
            return pdfs[0]
        if not pdfs:
            self.warn("Adicione um PDF primeiro.")
        else:
            self.warn("Tem mais de um PDF na lista. Clique no que você quer usar.")
        return None

    # ---- operações ---------------------------------------------------------
    def run_tool(self, key):
        if self.task and self.task.isRunning():
            return
        getattr(self, f"op_{key}")()

    def op_merge(self):
        pdfs = self._paths("pdf")
        if len(pdfs) < 2:
            return self.warn("Adicione pelo menos 2 PDFs para juntar (eles entram na ordem da lista).")
        out = self.save_as("juntado.pdf")
        if out:
            self.start(lambda: (pdfops.merge(pdfs, out), f"Juntei {len(pdfs)} PDFs → {os.path.basename(out)}",
                                os.path.dirname(out))[1:], out)

    def op_split(self):
        pdf = self._one_pdf()
        if not pdf:
            return
        n = pdfops.page_count(pdf)
        spec, ok = QInputDialog.getText(
            self, "Separar / extrair", f"O PDF tem {n} páginas.\n\nPáginas a extrair (ex.: 1-3,5).\n"
            "Deixe VAZIO para quebrar em uma página por arquivo:")
        if not ok:
            return
        spec = spec.strip()
        if spec:
            out = self.save_as(os.path.splitext(os.path.basename(pdf))[0] + "_extraido.pdf")
            if out:
                self.start(lambda: (lambda _o, ne: (f"Extraí {ne} página(s) → {os.path.basename(out)}",
                                                     os.path.dirname(out)))(*pdfops.extract(pdf, spec, out)), out)
        else:
            folder = QFileDialog.getExistingDirectory(self, "Pasta para salvar as páginas")
            if folder:
                self.start(lambda: (lambda outs: (f"Quebrei em {len(outs)} arquivos.", folder))(
                    pdfops.split_each(pdf, folder)), folder)

    def op_rotate(self):
        pdf = self._one_pdf()
        if not pdf:
            return
        ang, ok = QInputDialog.getItem(self, "Girar", "Quanto girar (horário)?",
                                       ["90°", "180°", "270°"], 0, False)
        if not ok:
            return
        angle = int(ang.rstrip("°"))
        out = self.save_as(os.path.splitext(os.path.basename(pdf))[0] + "_girado.pdf")
        if out:
            self.start(lambda: (pdfops.rotate(pdf, out, angle),
                                (f"Girei {angle}° → {os.path.basename(out)}", os.path.dirname(out)))[1], out)

    def op_compress(self):
        pdf = self._one_pdf()
        if not pdf:
            return
        out = self.save_as(os.path.splitext(os.path.basename(pdf))[0] + "_menor.pdf")
        if out:
            def work():
                _, b, a = pdfops.compress(pdf, out)
                pct = round(100 * (1 - a / b)) if b else 0
                return (f"{_mb(b)} → {_mb(a)} ({pct}% menor)" if a < b else
                        f"Já estava otimizado ({_mb(a)}); não dava pra reduzir muito.", os.path.dirname(out))
            self.start(work, out)

    def op_img2pdf(self):
        imgs = self._paths("img")
        if not imgs:
            return self.warn("Adicione imagens (JPG/PNG…) para virar PDF.")
        out = self.save_as("imagens.pdf")
        if out:
            self.start(lambda: (pdfops.images_to_pdf(imgs, out),
                                (f"Montei um PDF com {len(imgs)} imagem(ns).", os.path.dirname(out)))[1], out)

    def op_text(self):
        pdf = self._one_pdf()
        if not pdf:
            return
        out = self.save_as(os.path.splitext(os.path.basename(pdf))[0] + ".txt", "Texto (*.txt)")
        if out:
            def work():
                _, nchars = pdfops.extract_text(pdf, out)
                if nchars == 0:
                    return ("Salvei, mas esse PDF não tem texto (parece escaneado/imagem).", os.path.dirname(out))
                return (f"Texto salvo ({nchars} caracteres) → {os.path.basename(out)}", os.path.dirname(out))
            self.start(work, out)

    # ---- execução em thread ------------------------------------------------
    def start(self, fn, result_path):
        self.last_folder = os.path.dirname(result_path) if result_path else ""
        self.set_busy(True)
        self.set_status("Trabalhando…")
        self.task = Task(fn, self)
        self.task.done.connect(self.finished)
        self.task.start()

    def finished(self, ok, msg, folder):
        self.set_busy(False)
        if folder:
            self.last_folder = folder
        self.open_btn.setEnabled(ok and bool(self.last_folder))
        self.status.setStyleSheet("color:%s; padding-top:4px;" % ("#3ddc97" if ok else "#ff6b6b"))
        self.status.setText(("✓ " if ok else "✕ ") + msg)

    def set_busy(self, busy):
        for b in self.tool_btns:
            b.setEnabled(not busy)

    # ---- utilidades --------------------------------------------------------
    def save_as(self, suggested, flt="PDF (*.pdf)"):
        start = os.path.join(self.last_folder or os.path.expanduser("~"), suggested)
        out, _ = QFileDialog.getSaveFileName(self, "Salvar como", start, flt)
        if out and flt.startswith("PDF") and not out.lower().endswith(".pdf"):
            out += ".pdf"
        return out

    def set_status(self, text):
        self.status.setStyleSheet("color:#8a93a8; padding-top:4px;")
        self.status.setText(text)

    def warn(self, text):
        QMessageBox.information(self, "Kit de PDF", text)

    def open_result(self):
        if self.last_folder and os.path.isdir(self.last_folder):
            os.startfile(self.last_folder)  # noqa: S606 (Windows)


def _mb(n):
    return f"{n / 1048576:.1f} MB" if n >= 1048576 else f"{n / 1024:.0f} KB"


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(QSS)
    w = KitPDF()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
