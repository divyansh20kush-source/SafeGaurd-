"""PhotoGuard's original local multimedia integrity analysis API.

This multi-signal ensemble is inspired by public forensic practices. It does not
include proprietary Sensity AI or Reality Defender models, algorithms, or data.
"""
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any
from uuid import uuid4
import io
import os

import imagehash
import numpy as np
from bson import ObjectId
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import ExifTags, Image, ImageChops, ImageStat
from pymongo import ASCENDING, DESCENDING, MongoClient
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from transformers import pipeline

try:
    import cv2
except ModuleNotFoundError:  # Image analysis still works if video support is not installed yet.
    cv2 = None

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "local_uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
REPORT_DIR = BASE_DIR / "local_reports"
REPORT_DIR.mkdir(exist_ok=True)
MODEL_CACHE_DIR = BASE_DIR / ".model_cache"
MODEL_CACHE_DIR.mkdir(exist_ok=True)
os.environ.setdefault("HF_HOME", str(MODEL_CACHE_DIR))
os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(MODEL_CACHE_DIR / "hub"))
os.environ.setdefault("TRANSFORMERS_CACHE", str(MODEL_CACHE_DIR / "transformers"))
MONGO_URI = "mongodb://localhost:27017"
LOCAL_MODEL_DIR = BASE_DIR / "local_model"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}
VIDEO_SUFFIXES = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
MAX_UPLOAD_BYTES = 250 * 1024 * 1024
MAX_VIDEO_SAMPLES = 12
classifier = None
_mongo_client = None
_collection = None


def clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def get_collection():
    global _mongo_client, _collection
    if _collection is not None:
        return _collection
    try:
        _mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2500)
        _mongo_client.admin.command("ping")
        _collection = _mongo_client.photoguard.scans
        _collection.create_index("custom_image_id")
        _collection.create_index("scan_date")
        return _collection
    except Exception as exc:
        _mongo_client = _collection = None
        raise HTTPException(503, "Local MongoDB is unavailable. Start MongoDB at mongodb://localhost:27017.") from exc


def get_classifier():
    global classifier
    if classifier is None:
        if not any((LOCAL_MODEL_DIR / name).exists() for name in ("pytorch_model.bin", "model.safetensors")):
            raise HTTPException(503, "The bundled detector model is unavailable. Restore backend/local_model and try again.")
        classifier = pipeline("image-classification", model=str(LOCAL_MODEL_DIR))
    return classifier


def artificial_probability(predictions: list[dict[str, Any]]) -> float:
    for item in predictions:
        label = str(item.get("label", "")).lower()
        if any(word in label for word in ("artificial", "fake", "synthetic", "generated", "ai", "sdxl")):
            return clamp(float(item.get("score", 0)))
    top = predictions[0] if predictions else {}
    if any(word in str(top.get("label", "")).lower() for word in ("human", "real", "authentic", "genuine", "original")):
        return clamp(1 - float(top.get("score", 0)))
    return 0.5


def model_signal(image: Image.Image) -> tuple[float, dict[str, Any]]:
    predictions = get_classifier()(image.convert("RGB"))
    return artificial_probability(predictions), {
        "label": predictions[0]["label"] if predictions else "Unknown",
        "score": round(float(predictions[0]["score"]), 6) if predictions else 0,
        "top_predictions": [{"label": item["label"], "score": round(float(item["score"]), 6)} for item in predictions[:3]],
    }


def forensic_signal(image: Image.Image) -> tuple[float, dict[str, Any]]:
    """Compression and frequency cues: useful evidence, never standalone proof."""
    rgb = image.convert("RGB")
    buffer = io.BytesIO()
    rgb.save(buffer, format="JPEG", quality=90)
    recompressed = Image.open(io.BytesIO(buffer.getvalue())).convert("RGB")
    ela_mean = sum(ImageStat.Stat(ImageChops.difference(rgb, recompressed)).mean) / (3 * 255)
    gray = np.asarray(rgb.convert("L").resize((224, 224)), dtype=np.float32) / 255.0
    spectrum = np.abs(np.fft.fftshift(np.fft.fft2(gray)))
    h, w = spectrum.shape
    yy, xx = np.ogrid[:h, :w]
    radius = np.sqrt((yy - h / 2) ** 2 + (xx - w / 2) ** 2)
    high_ratio = float(spectrum[radius > min(h, w) * 0.28].mean() / (spectrum.mean() + 1e-8))
    compression = clamp((ela_mean - 0.015) / 0.12)
    frequency = clamp((high_ratio - 0.45) / 1.10)
    return clamp(0.55 * frequency + 0.45 * compression), {
        "compression_difference": round(ela_mean, 4), "high_frequency_ratio": round(high_ratio, 4),
        "note": "Compression and frequency cues are contextual forensic indicators, not proof of a deepfake.",
    }


def read_image_metadata(path: Path) -> dict[str, Any]:
    with Image.open(path) as image:
        raw = image.getexif()
        exif = {ExifTags.TAGS.get(key, str(key)): str(value) for key, value in raw.items() if isinstance(value, (str, int, float))}
        flags = []
        if software := exif.get("Software"):
            flags.append(f"Editing software recorded: {software}")
        if not raw:
            flags.append("No EXIF metadata present")
        return {"format": image.format, "dimensions": {"width": image.width, "height": image.height}, "exif": exif, "suspicious_flags": flags}


def metadata_score(metadata: dict[str, Any]) -> float:
    flags = metadata.get("suspicious_flags", [])
    return 0.35 if any("Editing software" in flag for flag in flags) else 0.12 if flags else 0.0


def assessment(signals: list[dict[str, Any]]) -> tuple[str, float]:
    risk = sum(signal["score"] * signal["weight"] for signal in signals)
    if risk >= 0.65:
        status = "Likely Manipulated"
    elif risk <= 0.35:
        status = "Likely Authentic"
    else:
        status = "Review Recommended"
    return status, round(clamp(risk) * 100, 2)


def explain(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{**signal, "score": round(signal["score"] * 100, 2), "weight": round(signal["weight"] * 100, 1)} for signal in signals]


def analyze_image(path: Path) -> dict[str, Any]:
    with Image.open(path) as opened:
        image = opened.convert("RGB")
        ai_score, prediction = model_signal(image)
        forensic_score, forensic = forensic_signal(image)
        perceptual_hash = str(imagehash.phash(image))
    metadata = read_image_metadata(path)
    signals = [
        {"name": "AI visual classifier", "score": ai_score, "weight": 0.65, "summary": "Bundled classifier's artificial-image likelihood."},
        {"name": "Pixel and frequency forensics", "score": forensic_score, "weight": 0.20, "summary": "Recompression and high-frequency indicators."},
        {"name": "File metadata", "score": metadata_score(metadata), "weight": 0.15, "summary": "Editing-software and EXIF-presence indicators."},
    ]
    status, confidence = assessment(signals)
    return {
        "media_type": "image", "ai_prediction": prediction, "result_status": status, "confidence": confidence,
        "metadata": metadata, "perceptual_hash": perceptual_hash, "forensics": forensic,
        "ensemble": {"version": "original-local-ensemble-v1", "signals": explain(signals), "limitations": ["No individual signal proves authenticity or manipulation.", "This original local ensemble does not use proprietary third-party detector models."]},
        "preview_reference": None,
    }


def analyze_video(path: Path) -> dict[str, Any]:
    if cv2 is None:
        raise HTTPException(503, "Video analysis needs OpenCV. Run: .\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt")
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise HTTPException(422, "The video could not be decoded. Try an MP4 with H.264 video.")
    try:
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0)
        width, height = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)), int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if frame_count < 1 or width < 1 or height < 1:
            raise HTTPException(422, "The video contains no readable frames.")
        indices = np.linspace(0, frame_count - 1, min(MAX_VIDEO_SAMPLES, frame_count), dtype=int)
        ai_scores, forensic_scores, frames, luminance = [], [], [], []
        first_prediction = None
        for index in indices:
            capture.set(cv2.CAP_PROP_POS_FRAMES, int(index))
            valid, frame = capture.read()
            if not valid:
                continue
            image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            ai_score, prediction = model_signal(image)
            forensic_score, _ = forensic_signal(image)
            ai_scores.append(ai_score); forensic_scores.append(forensic_score); frames.append(image)
            luminance.append(np.asarray(image.convert("L").resize((96, 96)), dtype=np.float32) / 255.0)
            first_prediction = first_prediction or prediction
        if not frames:
            raise HTTPException(422, "No video frames could be sampled.")
        preview = UPLOAD_DIR / f"{path.stem}.preview.jpg"
        frames[0].save(preview, format="JPEG", quality=86)
        transitions = [float(np.mean(np.abs(right - left))) for left, right in zip(luminance, luminance[1:])]
        temporal = clamp((np.median(transitions) if transitions else 0) / 0.35)
        metadata = {"format": path.suffix.lstrip(".").upper(), "dimensions": {"width": width, "height": height}, "exif": {}, "suspicious_flags": [], "video": {"frames": frame_count, "fps": round(fps, 2), "duration_seconds": round(frame_count / fps, 2) if fps else None, "sampled_frames": len(frames)}}
        signals = [
            {"name": "Sampled-frame AI classifier", "score": float(np.mean(ai_scores)), "weight": 0.60, "summary": f"Artificial-image likelihood across {len(frames)} sampled frames."},
            {"name": "Pixel and frequency forensics", "score": float(np.mean(forensic_scores)), "weight": 0.20, "summary": "Recompression and high-frequency indicators across sampled frames."},
            {"name": "Temporal consistency", "score": temporal, "weight": 0.12, "summary": "Frame-to-frame variation; fast motion and cuts can raise this contextual cue."},
            {"name": "Container metadata", "score": 0.0, "weight": 0.08, "summary": "Codec, dimensions, duration, and frame-rate inspection."},
        ]
        status, confidence = assessment(signals)
        return {
            "media_type": "video", "ai_prediction": first_prediction or {"label": "Unknown", "score": 0, "top_predictions": []}, "result_status": status, "confidence": confidence,
            "metadata": metadata, "perceptual_hash": str(imagehash.phash(frames[0])),
            "forensics": {"sampled_frame_count": len(frames), "mean_forensic_indicator": round(float(np.mean(forensic_scores)), 4), "median_frame_change": round(float(np.median(transitions)) if transitions else 0, 4)},
            "ensemble": {"version": "original-local-ensemble-v1", "signals": explain(signals), "limitations": ["Audio deepfake classification is not included in this local release.", "Fast motion and scene cuts can affect temporal indicators.", "This original local ensemble does not use proprietary third-party detector models."]},
            "preview_reference": f"/uploads/{preview.name}",
        }
    finally:
        capture.release()


def report_value(value: Any) -> str:
    """Format report values for the PDF without exposing raw HTML markup."""
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def create_detailed_pdf(report: dict[str, Any], destination: Path) -> None:
    """Create an evidence-focused, local PDF for one completed scan."""
    navy, blue, pale, ink, muted, line = (
        colors.HexColor("#112052"), colors.HexColor("#3655BE"), colors.HexColor("#EEF3FF"),
        colors.HexColor("#17224A"), colors.HexColor("#63708D"), colors.HexColor("#D8E0F2"),
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="ReportTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=25, leading=30, textColor=navy, spaceAfter=7))
    styles.add(ParagraphStyle(name="ReportSub", parent=styles["BodyText"], fontName="Helvetica", fontSize=9, leading=13, textColor=muted, spaceAfter=12))
    styles.add(ParagraphStyle(name="ReportH", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=13, leading=17, textColor=blue, spaceBefore=13, spaceAfter=6))
    styles.add(ParagraphStyle(name="ReportBody", parent=styles["BodyText"], fontName="Helvetica", fontSize=9, leading=13, textColor=ink, spaceAfter=5))
    styles.add(ParagraphStyle(name="ReportTiny", parent=styles["BodyText"], fontName="Helvetica", fontSize=7.5, leading=10, textColor=muted))
    styles.add(ParagraphStyle(name="ReportCell", parent=styles["BodyText"], fontName="Helvetica", fontSize=8.3, leading=11, textColor=ink))
    styles.add(ParagraphStyle(name="ReportHead", parent=styles["BodyText"], fontName="Helvetica-Bold", fontSize=8.3, leading=10, textColor=colors.white))

    def para(text: Any, style: str = "ReportBody") -> Paragraph:
        return Paragraph(report_value(text), styles[style])

    def report_table(rows: list[list[Any]], widths: list[float], header: bool = True) -> Table:
        content = [[para(cell, "ReportHead" if header and row_index == 0 else "ReportCell") for cell in row] for row_index, row in enumerate(rows)]
        grid = Table(content, colWidths=widths, hAlign="LEFT", repeatRows=1 if header else 0)
        grid.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), navy) if header else ("BACKGROUND", (0, 0), (-1, -1), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.4, line), ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFF")]),
        ]))
        return grid

    media_type = report.get("media_type", "image").title()
    metadata = report.get("metadata", {})
    forensics = report.get("forensics", {})
    ensemble = report.get("ensemble", {})
    dimensions = metadata.get("dimensions", {})
    scan_date = report.get("scan_date")
    scan_date = scan_date.isoformat() if hasattr(scan_date, "isoformat") else str(scan_date or "Unknown")
    story = [
        Paragraph("PhotoGuard", ParagraphStyle(name="Brand", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=11, textColor=blue, spaceAfter=10)),
        Paragraph("Detailed Media Integrity Report", styles["ReportTitle"]),
        Paragraph("Local evidence report - generated from the completed analysis. Results are decision-support signals, not proof.", styles["ReportSub"]),
    ]
    summary = report_table([
        ["Assessment", "Risk score", "Media type", "Scan time (UTC)"],
        [report.get("result_status", "Unknown"), f"{report.get('confidence', 0):.2f}%", media_type, scan_date],
    ], [4.0*cm, 3.0*cm, 3.0*cm, 7.0*cm])
    summary.setStyle(TableStyle([("BACKGROUND", (0, 1), (-1, 1), pale)]))
    story += [summary, Spacer(1, 10), Paragraph("Media identification", styles["ReportH"]), report_table([
        ["Custom media ID", "Original filename", "Format", "Dimensions"],
        [report.get("custom_image_id", ""), report.get("original_filename", ""), metadata.get("format", "Unknown"), f"{dimensions.get('width', '?')} x {dimensions.get('height', '?')}"],
    ], [4.0*cm, 6.1*cm, 3.0*cm, 3.9*cm]), Spacer(1, 8)]

    prediction = report.get("ai_prediction", {})
    story += [Paragraph("AI visual classification", styles["ReportH"]), report_table([
        ["Leading label", "Model confidence", "Interpretation"],
        [prediction.get("label", "Unknown"), f"{float(prediction.get('score', 0))*100:.2f}%", "The bundled visual model's leading class. This is one signal within the ensemble."],
    ], [4.0*cm, 3.2*cm, 9.8*cm])]

    signal_rows = [["Evidence signal", "Signal score", "Weight", "What it represents"]]
    for signal in ensemble.get("signals", []):
        signal_rows.append([signal.get("name", "Unknown"), f"{float(signal.get('score', 0)):.2f}%", f"{float(signal.get('weight', 0)):.1f}%", signal.get("summary", "")])
    story += [Paragraph("Ensemble evidence", styles["ReportH"]), report_table(signal_rows, [4.2*cm, 2.7*cm, 2.0*cm, 8.1*cm]), Spacer(1, 8)]

    forensic_rows = [["Forensic measure", "Value"]]
    for key, value in forensics.items():
        forensic_rows.append([key.replace("_", " ").title(), value])
    story += [Paragraph("Forensics and metadata", styles["ReportH"]), report_table(forensic_rows, [5.0*cm, 12.0*cm]), Spacer(1, 7)]
    flags = metadata.get("suspicious_flags", [])
    story.append(Paragraph(f"<b>Metadata flags:</b> {report_value(' | '.join(flags) if flags else 'No suspicious metadata flags detected.')}", styles["ReportBody"]))

    video = metadata.get("video")
    if video:
        story += [Paragraph("Video sampling details", styles["ReportH"]), report_table([
            ["Total frames", "FPS", "Duration", "Sampled frames"],
            [video.get("frames", "Unknown"), video.get("fps", "Unknown"), f"{video.get('duration_seconds', 'Unknown')} seconds", video.get("sampled_frames", "Unknown")],
        ], [4.2*cm, 3.0*cm, 5.1*cm, 4.7*cm])]

    story += [Paragraph("File integrity", styles["ReportH"]), report_table([
        ["SHA-256", "Perceptual hash"], [report.get("sha256", ""), report.get("perceptual_hash", "")],
    ], [10.6*cm, 6.4*cm]), Paragraph("Limitations and responsible use", styles["ReportH"])]
    for limitation in ensemble.get("limitations", ["No individual signal proves authenticity or manipulation."]):
        story.append(Paragraph(f"- {report_value(limitation)}", styles["ReportBody"]))
    story.append(Spacer(1, 8))
    story.append(Paragraph("Keep the original media file and use human review or corroborating evidence for any high-impact decision. This report is generated locally by PhotoGuard.", styles["ReportTiny"]))

    def footer(canvas, doc):
        canvas.saveState(); canvas.setStrokeColor(line); canvas.line(1.6*cm, 1.35*cm, 19.4*cm, 1.35*cm)
        canvas.setFillColor(muted); canvas.setFont("Helvetica", 7.5)
        canvas.drawString(1.6*cm, 0.95*cm, "PhotoGuard local detailed analysis report")
        canvas.drawRightString(19.4*cm, 0.95*cm, f"Page {doc.page}"); canvas.restoreState()

    SimpleDocTemplate(str(destination), pagesize=A4, leftMargin=1.6*cm, rightMargin=1.6*cm, topMargin=1.35*cm, bottomMargin=1.2*cm, title="PhotoGuard Detailed Analysis Report").build(story, onFirstPage=footer, onLaterPages=footer)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        get_collection()
    except Exception:
        pass
    yield


app = FastAPI(title="PhotoGuard Local API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")


@app.get("/api/health")
def health():
    get_collection()
    return {"status": "ok", "database": "photoguard", "storage": "local", "capabilities": ["image", "video", "visual-ai", "forensics", "metadata", "temporal"]}


@app.post("/api/scans")
async def create_scan(custom_image_id: str = Form(...), file: UploadFile = File(...)):
    suffix = Path(file.filename or "upload").suffix.lower()
    if suffix not in IMAGE_SUFFIXES | VIDEO_SUFFIXES:
        raise HTTPException(415, "Supported files: JPG, JPEG, PNG, MP4, MOV, AVI, MKV, and WEBM.")
    content = await file.read()
    if not content:
        raise HTTPException(400, "The uploaded file is empty.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "The upload exceeds the 250 MB local scan limit.")
    stored_name = f"{uuid4().hex}{suffix}"
    stored_path = UPLOAD_DIR / stored_name
    stored_path.write_bytes(content)
    try:
        analysis = analyze_image(stored_path) if suffix in IMAGE_SUFFIXES else analyze_video(stored_path)
    except HTTPException:
        stored_path.unlink(missing_ok=True)
        raise
    except Exception as exc:
        stored_path.unlink(missing_ok=True)
        raise HTTPException(422, f"Could not inspect the uploaded media: {exc}") from exc
    report = {"custom_image_id": custom_image_id, "original_filename": file.filename or stored_name, "image_location": str(stored_path), "stored_image_reference": f"/uploads/{stored_name}", "sha256": sha256(content).hexdigest(), "scan_date": datetime.now(timezone.utc), **analysis}
    result = get_collection().insert_one(report)
    return serialize({**report, "_id": result.inserted_id})


@app.get("/api/scans")
def list_scans(q: str = Query("", max_length=100), sort: str = Query("newest")):
    query = {"$or": [{"custom_image_id": {"$regex": q, "$options": "i"}}, {"original_filename": {"$regex": q, "$options": "i"}}]} if q else {}
    ordering = {"newest": ("scan_date", DESCENDING), "oldest": ("scan_date", ASCENDING), "confidence": ("confidence", DESCENDING)}.get(sort, ("scan_date", DESCENDING))
    return [serialize(item) for item in get_collection().find(query).sort(*ordering).limit(100)]


@app.get("/api/scans/{scan_id}/report.pdf")
def download_detailed_report(scan_id: str):
    """Generate a downloadable local PDF for an already completed analysis."""
    if not ObjectId.is_valid(scan_id):
        raise HTTPException(404, "Analysis report not found.")
    report = get_collection().find_one({"_id": ObjectId(scan_id)})
    if report is None:
        raise HTTPException(404, "Analysis report not found.")
    pdf_path = REPORT_DIR / f"photoguard-{scan_id}.pdf"
    try:
        create_detailed_pdf(report, pdf_path)
    except Exception as exc:
        raise HTTPException(500, f"Could not create the detailed PDF report: {exc}") from exc
    media_id = "".join(char if char.isalnum() or char in "-_" else "_" for char in str(report["custom_image_id"]))[:50] or "scan"
    return FileResponse(pdf_path, media_type="application/pdf", filename=f"PhotoGuard-{media_id}-detailed-report.pdf")


def serialize(report: dict[str, Any]) -> dict[str, Any]:
    base_url = "http://localhost:8001"
    return {"id": str(report["_id"]), "custom_image_id": report["custom_image_id"], "original_filename": report["original_filename"], "image_location": report["image_location"], "image_url": f"{base_url}{report['stored_image_reference']}", "preview_url": f"{base_url}{report['preview_reference']}" if report.get("preview_reference") else None, "media_type": report.get("media_type", "image"), "ai_prediction": report["ai_prediction"], "result_status": report["result_status"], "confidence": report["confidence"], "metadata": report["metadata"], "forensics": report.get("forensics", {}), "ensemble": report.get("ensemble", {}), "sha256": report["sha256"], "perceptual_hash": report["perceptual_hash"], "scan_date": report["scan_date"].isoformat()}
