from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import io
import os

# フォント名 (小文字に統一)
FONT_NAME = "sfmono" 

# TTFファイルのパス
FONT_PATH = "SF-Mono-Regular.ttf" 

INPUT_PDF = ".pdf"
OUTPUT_PDF = INPUT_PDF + "_numbered.pdf"
# ----------------------------------------------------------------------

# ReportLabにフォントを登録する
if not os.path.exists(FONT_PATH):
    # ファイルが見つからない場合は終了
    print(f"Error: couldn't find font: {FONT_PATH}")
    exit()

try:
    pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_PATH))
except Exception as e:
    print(f"Fatal error: Failed to register font(s): {e}")
    exit()

# ----------------------------------------------------------------------

def add_numbers_to_odd_pages(input_pdf_path, output_pdf_path):
    # 奇数ページの左上に連番を挿入する
    
    reader = PdfReader(input_pdf_path)
    writer = PdfWriter()
    total_pages = len(reader.pages)
    current_number = 1 # 挿入する最初の番号
    
    for i in range(total_pages):
        page = reader.pages[i]
        page_num = i + 1
        
        # 奇数ページ (ページ番号が奇数、インデックス i は偶数) の場合
        if page_num % 2 != 0:
            
            packet = io.BytesIO()
            page_width = float(page.mediabox.width)
            page_height = float(page.mediabox.height)
            
            can = canvas.Canvas(packet, pagesize=(page_width, page_height))
            
            # フォント指定
            can.setFont(FONT_NAME, 16)
            
            # 描画するテキスト
            text_to_insert = str(current_number)
            
            # 描画位置
            x_position = 16
            y_position = page_height - 16
            
            can.drawString(x_position, y_position, text_to_insert)
            
            can.showPage()
            can.save()
            packet.seek(0)
            
            # 元のページに数字のページを重ね合わせる
            number_pdf = PdfReader(packet)
            page.merge_page(number_pdf.pages[0])
            
            current_number += 1

        # ページを新しいWriterに追加
        writer.add_page(page)

    # PDFを書き出し
    with open(output_pdf_path, "wb") as output_file:
        writer.write(output_file)

    print(f"Done!: {output_pdf_path}")

# 実行
add_numbers_to_odd_pages(INPUT_PDF, OUTPUT_PDF)