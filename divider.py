import os
from pypdf import PdfReader, PdfWriter

BASENAME = ""
INPUT_PDF = f"{BASENAME}.pdf"

def split_pdf_by_file_count(input_path: str, output_dir: str, split_count: int):
    # PDFの読み込み
    reader = PdfReader(input_path)
    total_pages = len(reader.pages)
    
    # 分割数が総ページ数を上回る場合は、総ページ数に合わせる
    if split_count > total_pages:
        split_count = total_pages
    elif split_count <= 0:
        raise ValueError("分割数は1以上にしてください。")
        
    os.makedirs(output_dir, exist_ok=True)
    
    # 1ファイルあたりの基本ページ数と余りのページ数を計算
    base_pages = total_pages // split_count
    remainder = total_pages % split_count
    
    current_page = 0
    
    # 指定したファイル数分だけループ
    for i in range(split_count):
        writer = PdfWriter()
        
        # 余りがある場合は、前半のファイルに1ページ多く割り当てる
        pages_for_this_file = base_pages + (1 if i < remainder else 0)
        end_page = current_page + pages_for_this_file
        
        # 該当範囲のページをWriter(?)に追加
        for j in range(current_page, end_page):
            writer.add_page(reader.pages[j])
            
        # ファイルを保存
        output_filename = os.path.join(output_dir, f"split_part{i+1}_{current_page+1}_to_{end_page}.pdf")
        with open(output_filename, "wb") as output_file:
            writer.write(output_file)
            
        # 次のファイルの開始ページを更新
        current_page = end_page

if __name__ == "__main__":
    split_pdf_by_file_count(INPUT_PDF, "./output", 10)
