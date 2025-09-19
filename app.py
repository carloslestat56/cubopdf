from flask import Flask, render_template, request, send_file, redirect, url_for, flash, jsonify
from werkzeug.utils import secure_filename
import os, uuid, io, zipfile, subprocess, shutil
from PyPDF2 import PdfReader, PdfWriter, PdfMerger
import pikepdf
from pdf2image import convert_from_path
from PIL import Image
import img2pdf
import pdfplumber
from docx import Document

app = Flask(__name__)

# rota para servir sitemap direto da pasta static
@app.route("/sitemap.xml")
def sitemap():
    return app.send_static_file("sitemap.xml")
    
app.secret_key = os.environ.get("SECRET_KEY", "change-me-secret")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
OUTPUT_FOLDER = os.path.join(BASE_DIR, "output")
ALLOWED_PDF = {"pdf"}
ALLOWED_IMG = {"jpg", "jpeg", "png"}
ALLOWED_DOCX = {"docx"}
MAX_CONTENT_LENGTH_MB = int(os.environ.get("MAX_UPLOAD_MB", 50))
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH_MB * 1024 * 1024

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def allowed_file(filename, allowed):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed

def unique_path(directory, filename):
    name, ext = os.path.splitext(secure_filename(filename))
    return os.path.join(directory, f"{name}-{uuid.uuid4().hex}{ext}")

def parse_ranges(ranges_str, num_pages):
    pages = set()
    if not ranges_str:
        return []
    for part in ranges_str.split(","):
        part = part.strip()
        if "-" in part:
            try:
                a, b = part.split("-", 1)
                start = max(1, int(a))
                end = min(num_pages, int(b))
                for p in range(start, end + 1):
                    pages.add(p - 1)
            except:
                continue
        else:
            try:
                p = int(part)
                if 1 <= p <= num_pages:
                    pages.add(p - 1)
            except:
                continue
    return sorted(pages)

#------------Politica-------
@app.route("/politica-de-privacidade")
def politica():
    return render_template("politica.html" show_ads=False)

#------------Termos---------
@app.route("/termos-de-uso")
def termos():
    return render_template("termos.html", show_ads=False)

# --------- Contato ---------
@app.route("/contato")
def contato():
    return render_template("contato.html" show_ads=False)
    
# ---------- Home ----------
@app.route("/")
def index():
    return render_template("index.html", max_mb=MAX_CONTENT_LENGTH_MB, show_ads=True)

# ---------- MERGE ----------
@app.route("/juntar-pdf", methods=["GET", "POST"])
def merge():
    if request.method == "POST":
        files = request.files.getlist("pdfs")
        pdf_paths = []
        for f in files:
            if f and allowed_file(f.filename, ALLOWED_PDF):
                path = unique_path(UPLOAD_FOLDER, f.filename)
                f.save(path)
                pdf_paths.append(path)
        if len(pdf_paths) < 2:
            flash("Envie ao menos 2 PDFs válidos.")
            return redirect(url_for("merge"))
        merger = PdfMerger()
        for p in pdf_paths:
            merger.append(p)
        out_path = unique_path(OUTPUT_FOLDER, "merged.pdf")
        with open(out_path, "wb") as out:
            merger.write(out)
        merger.close()
        return send_file(out_path, as_attachment=True, download_name="cubopdf_merged.pdf")
    return render_template("merge.html"show_ads=True)

# ---------- SPLIT ----------
@app.route("/dividir-pdf", methods=["GET", "POST"])
def split():
    if request.method == "POST":
        f = request.files.get("pdf")
        ranges = request.form.get("ranges", "")
        if not (f and allowed_file(f.filename, ALLOWED_PDF)):
            flash("Envie um PDF válido.")
            return redirect(url_for("split"))
        in_path = unique_path(UPLOAD_FOLDER, f.filename)
        f.save(in_path)
        reader = PdfReader(in_path)
        indices = parse_ranges(ranges, len(reader.pages))
        if not indices:
            flash("Informe páginas válidas (ex.: 1-3,5,8)")
            return redirect(url_for("split"))
        writer = PdfWriter()
        for i in indices:
            writer.add_page(reader.pages[i])
        out_path = unique_path(OUTPUT_FOLDER, "extracted.pdf")
        with open(out_path, "wb") as out:
            writer.write(out)
        return send_file(out_path, as_attachment=True, download_name="cubopdf_extracted.pdf")
    return render_template("split.html"show_ads=True)

# ---------- REMOVE ----------
@app.route("/remover-paginas", methods=["GET", "POST"])
def remove():
    if request.method == "POST":
        f = request.files.get("pdf")
        ranges = request.form.get("ranges", "")
        if not (f and allowed_file(f.filename, ALLOWED_PDF)):
            flash("Envie um PDF válido.")
            return redirect(url_for("remove"))
        in_path = unique_path(UPLOAD_FOLDER, f.filename)
        f.save(in_path)
        reader = PdfReader(in_path)
        to_remove = set(parse_ranges(ranges, len(reader.pages)))
        writer = PdfWriter()
        for i in range(len(reader.pages)):
            if i not in to_remove:
                writer.add_page(reader.pages[i])
        out_path = unique_path(OUTPUT_FOLDER, "removed.pdf")
        with open(out_path, "wb") as out:
            writer.write(out)
        return send_file(out_path, as_attachment=True, download_name="cubopdf_removed.pdf")
    return render_template("remove.html"show_ads=True)

# ---------- COMPRESS ----------
def compress_with_ghostscript(input_pdf, output_pdf, quality="ebook"):
    qs_map = {"low":"/screen","medium":"/ebook","high":"/printer","max":"/prepress"}
    setting = qs_map.get(quality,"/ebook")
    cmd = [
        "gs", "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.4",
        f"-dPDFSETTINGS={setting}",
        "-dNOPAUSE", "-dQUIET", "-dBATCH",
        f"-sOutputFile={output_pdf}", input_pdf
    ]
    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return True, None
    except Exception as e:
        return False, str(e)

def compress_with_pikepdf(input_pdf, output_pdf):
    try:
        with pikepdf.open(input_pdf) as pdf:
            pdf.save(output_pdf, compress_streams=True, object_stream_mode=pikepdf.ObjectStreamMode.generate)
        return True, None
    except Exception as e:
        return False, str(e)

@app.route("/comprimir-pdf", methods=["GET", "POST"])
def compress():
    if request.method == "POST":
        f = request.files.get("pdf")
        quality = request.form.get("quality", "medium")
        quality_key = quality if quality in {"low","medium","high","max"} else "medium"
        if not (f and allowed_file(f.filename, ALLOWED_PDF)):
            flash("Envie um PDF válido.")
            return redirect(url_for("compress"))
        in_path = unique_path(UPLOAD_FOLDER, f.filename)
        f.save(in_path)
        out_path = unique_path(OUTPUT_FOLDER, "compressed.pdf")
        ok, err = compress_with_ghostscript(in_path, out_path, quality_key)
        if not ok:
            ok2, err2 = compress_with_pikepdf(in_path, out_path)
            if not ok2:
                flash("Falha ao comprimir PDF. Instale Ghostscript para melhor compressão.")
                return redirect(url_for("compress"))
        return send_file(out_path, as_attachment=True, download_name="cubopdf_compressed.pdf")
    return render_template("compress.html"show_ads=True)

# ---------- PDF -> IMAGE ----------
@app.route("/pdf-para-imagem", methods=["GET", "POST"])
def pdf2img():
    if request.method == "POST":
        f = request.files.get("pdf")
        fmt = request.form.get("format", "png").lower()
        dpi = int(request.form.get("dpi", 150))
        if not (f and allowed_file(f.filename, ALLOWED_PDF)):
            flash("Envie um PDF válido.")
            return redirect(url_for("pdf2img"))
        in_path = unique_path(UPLOAD_FOLDER, f.filename)
        f.save(in_path)
        try:
            images = convert_from_path(in_path, dpi=dpi, fmt=fmt)
        except Exception as e:
            flash("Erro na conversão. Verifique se Poppler está instalado.")
            return redirect(url_for("pdf2img"))
        if len(images) == 1:
            out_name = f"page1.{fmt}"
            out_path = unique_path(OUTPUT_FOLDER, out_name)
            images[0].save(out_path)
            return send_file(out_path, as_attachment=True, download_name=out_name)
        else:
            zip_name = unique_path(OUTPUT_FOLDER, "pages_images.zip")
            with zipfile.ZipFile(zip_name, "w", zipfile.ZIP_DEFLATED) as zf:
                for idx, img in enumerate(images, start=1):
                    buf = io.BytesIO()
                    img.save(buf, format=fmt.upper())
                    zf.writestr(f"page{idx}.{fmt}", buf.getvalue())
            return send_file(zip_name, as_attachment=True, download_name="cubopdf_pages.zip")
    return render_template("pdf2img.html"show_ads=True)

# ---------- IMAGE -> PDF ----------
@app.route("/imagem-para-pdf", methods=["GET", "POST"])
def img2pdf_route():
    if request.method == "POST":
        files = request.files.getlist("images")
        img_paths = []
        for f in files:
            if f and allowed_file(f.filename, ALLOWED_IMG):
                p = unique_path(UPLOAD_FOLDER, f.filename)
                f.save(p)
                img_paths.append(p)
        if not img_paths:
            flash("Envie ao menos 1 imagem JPG/PNG.")
            return redirect(url_for("img2pdf_route"))
        out_path = unique_path(OUTPUT_FOLDER, "images.pdf")
        with open(out_path, "wb") as f_out:
            f_out.write(img2pdf.convert(img_paths))
        return send_file(out_path, as_attachment=True, download_name="cubopdf_images.pdf")
    return render_template("img2pdf.html"show_ads=True)

# ---------- PDF -> WORD ----------
@app.route("/pdf-para-word", methods=["GET", "POST"])
def pdf2word():
    if request.method == "POST":
        f = request.files.get("pdf")
        if not (f and allowed_file(f.filename, ALLOWED_PDF)):
            flash("Envie um PDF válido.")
            return redirect(url_for("pdf2word"))
        in_path = unique_path(UPLOAD_FOLDER, f.filename)
        f.save(in_path)
        out_path = unique_path(OUTPUT_FOLDER, "converted.docx")
        doc = Document()
        try:
            with pdfplumber.open(in_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text() or ""
                    doc.add_paragraph(text)
                    doc.add_page_break()
            doc.save(out_path)
        except Exception as e:
            flash("Falha ao extrair texto do PDF.")
            return redirect(url_for("pdf2word"))
        return send_file(out_path, as_attachment=True, download_name="cubopdf_converted.docx")
    return render_template("pdf2word.html"show_ads=True)

# ---------- WORD -> PDF ----------
def try_docx2pdf(input_path, output_path):
    try:
        import docx2pdf
        out_dir = os.path.dirname(output_path)
        os.makedirs(out_dir, exist_ok=True)
        docx2pdf.convert(input_path, out_dir)
        base = os.path.splitext(os.path.basename(input_path))[0]
        produced = os.path.join(out_dir, base + ".pdf")
        if os.path.exists(produced):
            os.replace(produced, output_path)
            return True, None
        return False, "docx2pdf não gerou o arquivo esperado."
    except Exception as e:
        return False, str(e)

def try_libreoffice(input_path, output_path):
    try:
        out_dir = os.path.dirname(output_path)
        os.makedirs(out_dir, exist_ok=True)
        cmd = ["soffice", "--headless", "--convert-to", "pdf", "--outdir", out_dir, input_path]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        base = os.path.splitext(os.path.basename(input_path))[0]
        produced = os.path.join(out_dir, base + ".pdf")
        if os.path.exists(produced):
            os.replace(produced, output_path)
            return True, None
        return False, "LibreOffice não gerou o arquivo esperado."
    except Exception as e:
        return False, str(e)

@app.route("/word-para-pdf", methods=["GET", "POST"])
def word2pdf():
    if request.method == "POST":
        f = request.files.get("docx")
        if not (f and allowed_file(f.filename, ALLOWED_DOCX)):
            flash("Envie um arquivo .docx válido.")
            return redirect(url_for("word2pdf"))
        in_path = unique_path(UPLOAD_FOLDER, f.filename)
        f.save(in_path)
        out_path = unique_path(OUTPUT_FOLDER, "word.pdf")
        ok, err = try_docx2pdf(in_path, out_path)
        if not ok:
            ok2, err2 = try_libreoffice(in_path, out_path)
            if not ok2:
                flash("Falha na conversão. Instale MS Word ou LibreOffice.")
                return redirect(url_for("word2pdf"))
        return send_file(out_path, as_attachment=True, download_name="cubopdf_word.pdf")
    return render_template("word2pdf.html"show_ads=True)

# Clean uploads/output (utility route - not exposed in production)
@app.route("/_cleanup", methods=["POST"])
def cleanup():
    for d in (UPLOAD_FOLDER, OUTPUT_FOLDER):
        for fn in os.listdir(d):
            try:
                os.remove(os.path.join(d, fn))
            except:
                pass
    return jsonify({"ok": True})

@app.errorhandler(413)
def too_large(e):
    flash(f"Arquivo muito grande. Limite: {MAX_CONTENT_LENGTH_MB} MB.")
    return redirect(request.url)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="127.0.0.1", port=port, debug=True)
