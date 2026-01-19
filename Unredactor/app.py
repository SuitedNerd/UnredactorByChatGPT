import os
from flask import Flask, render_template, request, redirect
import fitz
from docx import Document
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"pdf", "docx", "txt", "csv", "xlsx"}
MAX_FILE_SIZE = 20 * 1024 * 1024

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def analyze_file(file_path):
    ext = file_path.lower().rsplit(".", 1)[-1]
    results = []

    try:
        if ext == "pdf":
            doc = fitz.open(file_path)
            for page_number, page in enumerate(doc):
                text = page.get_text().strip()
                if text:
                    results.append({"page": page_number + 1, "snippet": text[:500]})
        elif ext == "docx":
            doc = Document(file_path)
            full_text = "\n".join([para.text for para in doc.paragraphs])
            if full_text.strip():
                results.append({"page": 1, "snippet": full_text[:500]})
        elif ext in ["txt", "csv"]:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
            if text.strip():
                results.append({"page": 1, "snippet": text[:500]})
        elif ext == "xlsx":
            df = pd.read_excel(file_path, engine="openpyxl")
            text = df.astype(str).agg(" ".join, axis=1).str.cat(sep="\n")
            if text.strip():
                results.append({"page": 1, "snippet": text[:500]})
        else:
            results.append({"page": 1, "snippet": f"[Error]: Unsupported file type '{ext}'"})
    except Exception as e:
        results.append({"page": 1, "snippet": f"[Error]: Failed to read file ({e})"})

    return results

def process_file(file):
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)
    leaks = analyze_file(filepath)
    return filename, leaks

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        files = request.files.getlist("files")
        if not files or all(f.filename == "" for f in files):
            return redirect(request.url)

        all_results = {}
        with ThreadPoolExecutor() as executor:
            futures = [executor.submit(process_file, f) for f in files]
            for future in futures:
                filename, leaks = future.result()
                all_results[filename] = leaks

        return render_template("index.html", all_results=all_results)

    return render_template("index.html", all_results=None)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
