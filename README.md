# PhotoGuard

Premium local-first image and video integrity scanner. Media and reports stay on your computer: the API uses `mongodb://localhost:27017` and database `photoguard`; uploads are saved under `backend/local_uploads`.

## Run locally

1. Start your local MongoDB service.
2. In one terminal, set up the Python API:
   ```powershell
   cd backend
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   uvicorn main:app --reload --port 8001
   ```
   The bundled model in `backend/local_model` loads locally; no model download is required. OpenCV enables local video decoding and sampled-frame analysis.
3. In a second terminal, start the React experience:
   ```powershell
   npm install
   npm run dev
   ```

Open `http://localhost:5173`.

## Data stored per scan

The `photoguard.scans` collection stores the Custom Image ID, source filename, absolute local file location and URL reference, media type, model predictions/confidence, visual forensic signals, EXIF/container metadata, SHA-256, perceptual hash, and UTC scan timestamp.

## Detection approach and scope

PhotoGuard's original local ensemble combines a bundled visual AI classifier with recompression/frequency forensic cues and metadata analysis. For video, it samples frames and also records contextual frame-to-frame consistency signals. It accepts JPG, JPEG, PNG, MP4, MOV, AVI, MKV, and WEBM (up to 250 MB).

This implementation is inspired only by publicly described multi-signal detection practices. It does **not** contain, reproduce, or claim to use Sensity AI or Reality Defender proprietary algorithms, models, weights, or results. Audio deepfake classification is not yet included; video reports state that limitation explicitly.

The detection result is intentionally described as `Likely Authentic`, `Likely Manipulated`, or `Review Recommended`; it is evidence to review, not an assertion of certainty.

## Detailed analysis PDF

After a scan completes, the result card in the website displays **Download Detailed PDF**. The local API generates a report for that exact scan with the verdict, risk score, model prediction, weighted evidence signals, metadata, forensic measures, hashes, and limitations. Generated reports are saved under `backend/local_reports` and are never uploaded to a cloud service.
