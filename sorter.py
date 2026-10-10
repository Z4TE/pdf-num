import os
import io
from collections import Counter
from pypdf import PdfReader, PdfWriter, PageObject, Transformation
from pypdf.generic import ContentStream, FloatObject
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# 設定

BASENAME = ""
TARGET_DIR = f"./{BASENAME}"
OUTPUT_PDF = f"{BASENAME}.pdf"

FONT_NAME = ""
FONT_PATH = ""
DEFAULT_FONT_NAME = "Default"

COLS, ROWS = 4, 2

#INPUT INDEX               [0, 1, 2, 3, 4, 5, 6, 7]
#INPUT ORDER               [8, 1, 2, 7, 6, 3, 4, 5]
READING_ORDER: list[int] = [1, 2, 5, 6, 7, 4, 3, 0]

VERIFY_TEXT: bool = False

# フォント登録
try:
    if not os.path.exists(FONT_PATH):
        print(f"Warning: Font file not found at '{FONT_PATH}'. Using default '{DEFAULT_FONT_NAME}'.")
        FONT_NAME = DEFAULT_FONT_NAME
    else:
        pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_PATH))

except NameError:
    print(f"Warning: FONT_NAME or FONT_PATH is not defined. Using default '{DEFAULT_FONT_NAME}'.")
    FONT_NAME = DEFAULT_FONT_NAME
except Exception as e:
    print(f"Warning: Failed to register font ({e}). Using default '{DEFAULT_FONT_NAME}'.")
    FONT_NAME = DEFAULT_FONT_NAME

# 補助関数
def get_half_page(data: bytes, page_index: int, side: int):
    # バイト列から独立したReader(?)を作り、左(0)/右(1)半分にクリップしたページを返す。
    page = PdfReader(io.BytesIO(data)).pages[page_index]
    left = float(page.mediabox.left)
    bottom = float(page.mediabox.bottom)
    w = float(page.mediabox.width)
    h = float(page.mediabox.height)

    half_w = w / 2
    x0 = left + half_w * side

    cs = ContentStream(page.get_contents(), page.pdf)
    cs.operations.insert(0, ([], b"q"))
    cs.operations.insert(1, ([FloatObject(x0), FloatObject(bottom),
                              FloatObject(half_w), FloatObject(h)], b"re"))
    cs.operations.insert(2, ([], b"W"))
    cs.operations.insert(3, ([], b"n"))
    cs.operations.append(([], b"Q"))
    page.replace_contents(cs)
    return page, x0, bottom, half_w, h


def make_label_page(text, width, height):
    # ファイル名ラベルを描画したPDFページを作成
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=(width, height))
    can.setFont(FONT_NAME, 16)
    can.drawString(16, height - 16, text)
    can.showPage()
    can.save()
    packet.seek(0)
    return PdfReader(packet).pages[0]


def make_id_overlay(width, height, cell_labels, cell_w, cell_h):
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=(width, height))
    can.setFont(FONT_NAME, 14)
    for col, row, text in cell_labels:
        # セルの左上から少しマージンを空けて配置
        tx = col * cell_w + 12
        ty = height - row * cell_h - 36 
        can.drawString(tx, ty, text)
    can.showPage()
    can.save()
    packet.seek(0)
    return PdfReader(packet).pages[0]


def words_of(page):
    try:
        return Counter((page.extract_text() or "").split())
    except Exception:
        return Counter()


def build_sheet_pdf(input_pdf_path, label):
    # 1ファイル(最大4ページ)から、1ページだけのPDFを作る
    with open(input_pdf_path, "rb") as f:
        data = f.read()

    reader = PdfReader(io.BytesIO(data))
    n_pages = len(reader.pages)
    
    if n_pages > 4:
        print(f"Skip: {os.path.basename(input_pdf_path)} has {n_pages} pages (> 4)")
        return None

    # 4ページ未満の場合は空ページを挿入して調整
    if n_pages < 4:
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
            
        # サイズの基準を取得（ページが0枚の場合はA4サイズを仮定）
        if n_pages > 0:
            w = float(reader.pages[0].mediabox.width)
            h = float(reader.pages[0].mediabox.height)
        else:
            w, h = 595.276, 841.890
            
        for _ in range(4 - n_pages):
            writer.add_blank_page(width=w, height=h)
            
        # 修正されたPDFデータとしてバイト列を更新
        buf = io.BytesIO()
        writer.write(buf)
        data = buf.getvalue()

    # 左右に分割 → INPUT ORDERの順に対応する元の面インデックスは 0~7
    halves = [get_half_page(data, i, side) for i in range(4) for side in (0, 1)]

    # 1〜8の順に並べ替え 元の面インデックスも一緒に保持する
    ordered = [(READING_ORDER[i], halves[READING_ORDER[i]]) for i in range(8)]

    # 縮小して4x2に配置
    _, _, _, half_w, h = ordered[0][1]
    out_w, out_h = half_w * 2, h
    cell_w, cell_h = out_w / COLS, out_h / ROWS
    scale = min(cell_w / half_w, cell_h / h)

    sheet = PageObject.create_blank_page(width=out_w, height=out_h)
    cell_labels = []

    for n, (src_idx, (pg, x0, y0, _, _)) in enumerate(ordered):
        col, row = n % COLS, n // COLS
        tx = col * cell_w
        ty = out_h - (row + 1) * cell_h
        t = (Transformation()
             .translate(tx=-x0, ty=-y0)
             .scale(sx=scale, sy=scale)
             .translate(tx=tx, ty=ty))
        sheet.merge_transformed_page(pg, t)
        
        # IDを記録
        id_text = f"[{src_idx + 1}]"
        cell_labels.append((col, row, id_text))

    # ラベルと各セルのIDを重ねる
    sheet.merge_page(make_label_page(label, out_w, out_h))
    sheet.merge_page(make_id_overlay(out_w, out_h, cell_labels, cell_w, cell_h))

    # 単一ファイルだけの1ページPDFとして確定
    buf = io.BytesIO()
    w = PdfWriter()
    w.add_page(sheet)
    w.write(buf)
    buf.seek(0)

    # 混在チェック
    if VERIFY_TEXT:
        src = Counter()
        for p in PdfReader(io.BytesIO(data)).pages:
            src += words_of(p)
        if sum(src.values()) > 0:
            expected = Counter({k: v * 2 for k, v in src.items()})
            expected.update(label.split())
            # IDテキストも期待値に含める
            for _, _, text in cell_labels:
                expected.update(text.split())
                
            actual = words_of(PdfReader(io.BytesIO(buf.getvalue())).pages[0])
            if actual != expected:
                diff = (actual - expected) + (expected - actual)
                print(f"  WARNING: {os.path.basename(input_pdf_path)}: "
                      f"text mismatch ({sum(diff.values())} words differ)")
            else:
                print("  verify: OK")
        else:
            print("  verify: skipped (no extractable text)")

    buf.seek(0)
    return buf

def process_and_merge_pdfs(input_dir, output_pdf_path):
    if not os.path.exists(input_dir):
        print(f"Error: Directory not found: {input_dir}")
        return

    pdf_files = sorted(f for f in os.listdir(input_dir) if f.lower().endswith('.pdf'))
    if not pdf_files:
        print(f"Error: No PDF files found in {input_dir}")
        return

    final = PdfWriter()
    done = 0
    for filename in pdf_files:
        path = os.path.join(input_dir, filename)
        label = os.path.splitext(filename)[0]
        print(f"Processing: {filename}")

        sheet_buf = build_sheet_pdf(path, label)
        if sheet_buf is None:
            continue
        final.add_page(PdfReader(sheet_buf).pages[0])
        done += 1

    with open(output_pdf_path, "wb") as f:
        final.write(f)
    print(f"Done! {done} file(s) -> {output_pdf_path}")


# 実行
process_and_merge_pdfs(TARGET_DIR, OUTPUT_PDF)