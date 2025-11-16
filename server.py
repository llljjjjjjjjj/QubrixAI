import os
import io
import uuid
import zipfile
import json
from typing import List, Dict, Any, Tuple

from flask import Flask, request, jsonify, send_from_directory

from pdf2image import convert_from_bytes
import cv2
import numpy as np
import img2pdf
from pyzbar.pyzbar import decode as decode_qr
from PIL import Image
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JOBS_DIR = os.path.join(BASE_DIR, "jobs")
os.makedirs(JOBS_DIR, exist_ok=True)

COLOR_MAP = {
    "signature": (0, 0, 255),
    "stamp": (255, 150, 0),
    "qrcode": (0, 255, 102),
}

GEMINI_MODEL_ID = os.environ.get("GEMINI_MODEL_ID", "gemini-2.5-flash")

if genai is not None:
    try:
        gemini_client = genai.Client()
    except Exception:
        gemini_client = None
else:
    gemini_client = None

app = Flask(__name__, static_folder=".", static_url_path="")


@app.route("/")
def index():
    return app.send_static_file("index.html")


def allowed_file(filename: str) -> bool:
    filename = filename.lower()
    return filename.endswith(".pdf") or filename.endswith(".zip")


def convert_pdf_to_images(pdf_bytes: bytes) -> List[Image.Image]:
    return convert_from_bytes(pdf_bytes, dpi=220)


def _normalize_object_type(raw_name: str) -> str:
    if not raw_name:
        return "unknown"
    name = str(raw_name).lower().strip()
    if name in {"signature", "sign", "sig", "подпись"}:
        return "signature"
    if name in {"stamp", "seal", "stamp_seal", "печать", "штамп", "печать/штамп", "seal/stamp"}:
        return "stamp"
    if name in {"qr", "qr-code", "qr_code", "qrcode", "qr-код"}:
        return "qrcode"
    return name


def _parse_gemini_json_boxes(raw_text: str) -> List[Dict[str, Any]]:
    if not raw_text:
        return []
    start = raw_text.find("[")
    end = raw_text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return []
    candidate = raw_text[start : end + 1]
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError:
        cleaned = candidate.replace("```json", "").replace("```", "").strip()
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            return []
    if not isinstance(data, list):
        return []
    results = []
    for item in data:
        if not isinstance(item, dict):
            continue
        obj_type = item.get("type") or item.get("label")
        obj_type = _normalize_object_type(obj_type)
        if obj_type not in {"signature", "stamp", "qrcode"}:
            continue
        box = item.get("box_2d") or item.get("bbox")
        if not isinstance(box, (list, tuple)) or len(box) != 4:
            continue
        try:
            ymin, xmin, ymax, xmax = [float(v) for v in box]
        except Exception:
            continue
        ymin = max(0.0, min(1000.0, ymin))
        ymax = max(0.0, min(1000.0, ymax))
        xmin = max(0.0, min(1000.0, xmin))
        xmax = max(0.0, min(1000.0, xmax))
        try:
            conf = float(item.get("confidence", 0.9))
        except Exception:
            conf = 0.9
        results.append(
            {
                "type": obj_type,
                "box_2d": [ymin, xmin, ymax, xmax],
                "confidence": conf,
            }
        )
    return results


def detect_objects_with_gemini(pil_img: Image.Image) -> List[Dict[str, Any]]:
    if gemini_client is None or types is None:
        return []
    buf = io.BytesIO()
    pil_img.convert("RGB").save(buf, format="JPEG", quality=90)
    image_bytes = buf.getvalue()
    prompt = """
You are a computer vision system for checking construction documents.
Your task is to find:
- handwritten signatures (type "signature")
- company stamps (type "stamp")
- QR codes (type "qrcode")
Output only JSON array with:
{ "type": "...", "box_2d": [ymin, xmin, ymax, xmax], "confidence": 0-1 }
Coordinates: 0–1000.
Return [] if nothing.
"""
    try:
        response = gemini_client.models.generate_content(
            model=GEMINI_MODEL_ID,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                prompt,
            ],
            config=types.GenerateContentConfig(temperature=0.0),
        )
    except Exception:
        return []
    text = getattr(response, "text", None)
    if not text:
        return []
    return _parse_gemini_json_boxes(text)


def run_ai_on_pil_image(pil_img: Image.Image) -> Tuple[Image.Image, List[Dict[str, Any]]]:
    np_img = np.array(pil_img.convert("RGB"))
    cv_img = cv2.cvtColor(np_img, cv2.COLOR_RGB2BGR)
    h, w, _ = cv_img.shape
    raw_detections = detect_objects_with_gemini(pil_img)
    detections = []
    if not raw_detections:
        annotated_rgb = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        return Image.fromarray(annotated_rgb), detections
    for item in raw_detections:
        obj_type = item.get("type")
        if obj_type not in {"signature", "stamp", "qrcode"}:
            continue
        ymin, xmin, ymax, xmax = item.get("box_2d", [0, 0, 0, 0])
        x1 = int(round(float(xmin) / 1000.0 * w))
        y1 = int(round(float(ymin) / 1000.0 * h))
        x2 = int(round(float(xmax) / 1000.0 * w))
        y2 = int(round(float(ymax) / 1000.0 * h))
        x1 = max(0, min(x1, w - 1))
        x2 = max(0, min(x2, w - 1))
        y1 = max(0, min(y1, h - 1))
        y2 = max(0, min(y2, h - 1))
        if x2 <= x1 or y2 <= y1:
            continue
        conf = float(item.get("confidence", 0.9))
        color_bgr = COLOR_MAP.get(obj_type, (0, 0, 0))
        qr_value = None
        if obj_type == "qrcode":
            roi = cv_img[y1:y2, x1:x2]
            if roi.size > 0:
                gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                decoded = decode_qr(gray)
                if decoded:
                    try:
                        qr_value = decoded[0].data.decode("utf-8")
                    except Exception:
                        qr_value = None
        cv2.rectangle(cv_img, (x1, y1), (x2, y2), color_bgr, 3)
        cv2.putText(
            cv_img,
            f"{obj_type} {conf:.2f}",
            (x1, max(y1 - 6, 10)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            color_bgr,
            2,
            lineType=cv2.LINE_AA,
        )
        det = {
            "type": obj_type,
            "bbox": [x1, y1, x2, y2],
            "confidence": round(conf, 4),
            "color": (
                "red"
                if obj_type == "signature"
                else "blue"
                if obj_type == "stamp"
                else "green"
                if obj_type == "qrcode"
                else "black"
            ),
        }
        if qr_value:
            if isinstance(qr_value, str) and qr_value.startswith(("http://", "https://")):
                det["url"] = qr_value
            else:
                det["value"] = qr_value
        detections.append(det)
    annotated_rgb = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
    return Image.fromarray(annotated_rgb), detections


def create_stats_image(job_dir: str, counts_by_type: Dict[str, int]) -> str:
    labels = list(counts_by_type.keys())
    values = [counts_by_type[k] for k in labels]
    if not labels:
        labels = ["no objects"]
        values = [0]
    plt.figure(figsize=(4.5, 3))
    plt.bar(labels, values)
    plt.title("Detected elements by type")
    plt.xlabel("Type")
    plt.ylabel("Count")
    plt.tight_layout()
    stats_path = os.path.join(job_dir, "stats.png")
    plt.savefig(stats_path, dpi=140)
    plt.close()
    return "stats.png"


def process_single_pdf(pdf_bytes: bytes, original_name: str, job_id: str, job_dir: str) -> Dict[str, Any]:
    doc_id = str(uuid.uuid4())
    doc_dir = os.path.join(job_dir, doc_id)
    os.makedirs(doc_dir, exist_ok=True)
    pages = convert_pdf_to_images(pdf_bytes)
    page_results = []
    annotated_paths = []
    for idx, pil_page in enumerate(pages, start=1):
        annotated_pil, detections = run_ai_on_pil_image(pil_page)
        png_filename = f"page-{idx}.png"
        png_path = os.path.join(doc_dir, png_filename)
        annotated_pil.save(png_path, format="PNG")
        annotated_paths.append(png_path)
        page_results.append(
            {
                "page_number": idx,
                "image_url": f"/api/jobs/{job_id}/docs/{doc_id}/{png_filename}",
                "objects": detections,
            }
        )
    annotated_pdf_path = os.path.join(doc_dir, "annotated.pdf")
    with open(annotated_pdf_path, "wb") as f_out:
        f_out.write(img2pdf.convert(annotated_paths))
    return {
        "id": doc_id,
        "original_filename": original_name,
        "annotated_pdf_url": f"/api/jobs/{job_id}/docs/{doc_id}/annotated.pdf",
        "pages": page_results,
    }


@app.route("/api/process", methods=["POST"])
def api_process():
    if "files" not in request.files:
        return "No files uploaded. Use 'files' field in form-data.", 400
    files = request.files.getlist("files")
    files = [f for f in files if f and allowed_file(f.filename)]
    if not files:
        return "Please upload at least one PDF or ZIP file.", 400
    job_id = str(uuid.uuid4())
    job_dir = os.path.join(JOBS_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)
    documents = []
    total_pages = 0
    total_objects = 0
    counts_by_type = {"signature": 0, "stamp": 0, "qrcode": 0}

    def accumulate_counts(page_objects: List[Dict[str, Any]]):
        nonlocal total_objects
        total_objects += len(page_objects)
        for o in page_objects:
            t = o.get("type")
            if t in counts_by_type:
                counts_by_type[t] += 1

    for uploaded in files:
        filename = uploaded.filename
        data = uploaded.read()
        if filename.lower().endswith(".pdf"):
            doc_result = process_single_pdf(data, filename, job_id, job_dir)
            documents.append(doc_result)
            for p in doc_result["pages"]:
                total_pages += 1
                accumulate_counts(p["objects"])
        elif filename.lower().endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                for name in zf.namelist():
                    if not name.lower().endswith(".pdf"):
                        continue
                    pdf_bytes = zf.read(name)
                    doc_result = process_single_pdf(pdf_bytes, name, job_id, job_dir)
                    documents.append(doc_result)
                    for p in doc_result["pages"]:
                        total_pages += 1
                        accumulate_counts(p["objects"])
    stats_filename = create_stats_image(job_dir, counts_by_type)
    stats_url = f"/api/jobs/{job_id}/{stats_filename}"
    summary = {
        "job_id": job_id,
        "total_documents": len(documents),
        "total_pages": total_pages,
        "total_objects": total_objects,
        "by_type": counts_by_type,
        "stats_image_url": stats_url,
    }
    result = {"summary": summary, "documents": documents}
    return jsonify(result)


@app.route("/api/jobs/<job_id>/<path:filename>")
def api_get_job_file(job_id: str, filename: str):
    job_dir = os.path.join(JOBS_DIR, job_id)
    stats_path = os.path.join(job_dir, filename)
    if os.path.isfile(stats_path) and os.path.basename(filename) == "stats.png":
        return send_from_directory(job_dir, "stats.png")
    parts = filename.split("/")
    if len(parts) >= 2 and parts[0] == "docs":
        doc_id = parts[1]
        rest = "/".join(parts[2:])
        doc_dir = os.path.join(job_dir, doc_id)
        return send_from_directory(doc_dir, rest)
    return "File not found", 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
