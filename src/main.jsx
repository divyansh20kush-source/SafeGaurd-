import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { motion, useReducedMotion } from 'framer-motion';
import { ArrowDown, ArrowRight, CheckCircle2, ChevronDown, Clock3, Download, Eye, FileSearch, Fingerprint, History, Info, LoaderCircle, Search, ShieldCheck, Sparkles, Upload, X } from 'lucide-react';
import axios from 'axios';
import './styles.css';
import './media.css';

const api = axios.create({ baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8001/api' });
const mediaPattern = /\.(jpe?g|png|mp4|mov|avi|mkv|webm)$/i;
const videoPattern = /\.(mp4|mov|avi|mkv|webm)$/i;
const stages = [
  { icon: Sparkles, title: 'AI Deepfake Detection', copy: 'A pretrained vision model evaluates visual synthesis and manipulation cues in images and sampled video frames.' },
  { icon: FileSearch, title: 'Metadata & File Analysis', copy: 'Embedded camera, editing, container, and file-structure information is inspected locally.' },
  { icon: Fingerprint, title: 'Forensics & Video Signals', copy: 'Frequency, recompression, image fingerprints, and temporal frame-consistency signals are combined as evidence.' },
];

function OrbitalObjects() {
  const reduced = useReducedMotion();
  return <div className="objects" aria-hidden="true">
    <motion.div className="orb orb-one" animate={reduced ? {} : { y: [0, -18, 0], rotate: [0, 18, 0] }} transition={{ duration: 7, repeat: Infinity, ease: 'easeInOut' }} />
    <motion.div className="orb orb-two" animate={reduced ? {} : { y: [0, 22, 0], x: [0, 9, 0] }} transition={{ duration: 9, repeat: Infinity, ease: 'easeInOut' }} />
    <motion.div className="cube" animate={reduced ? {} : { rotateX: 360, rotateY: 360 }} transition={{ duration: 18, repeat: Infinity, ease: 'linear' }} />
    <motion.div className="ring ring-one" animate={reduced ? {} : { rotate: 360 }} transition={{ duration: 14, repeat: Infinity, ease: 'linear' }} />
    <motion.div className="ring ring-two" animate={reduced ? {} : { rotate: -360 }} transition={{ duration: 18, repeat: Infinity, ease: 'linear' }} />
    <motion.div className="tube" animate={reduced ? {} : { rotate: [12, 36, 12], y: [0, -10, 0] }} transition={{ duration: 8, repeat: Infinity, ease: 'easeInOut' }} />
  </div>;
}

function Header({ jump }) { return <header><button className="brand" onClick={() => jump('home')}><span>✦</span> PhotoGuard</button><nav>{[['Home', 'home'], ['Analyze Media', 'analyze'], ['History', 'history'], ['About', 'about']].map(([name, id]) => <button key={id} onClick={() => jump(id)}>{name}</button>)}</nav><button className="nav-cta" onClick={() => jump('analyze')}>Secure scan <ArrowRight size={15} /></button></header>; }

function Hero({ jump }) {
  return <section id="home" className="scene hero"><OrbitalObjects /><div className="ambient ambient-a" /><div className="ambient ambient-b" /><motion.div className="hero-card glass" initial={{ opacity: 0, scale: .94, y: 24 }} animate={{ opacity: 1, scale: 1, y: 0 }} transition={{ duration: 1.05, ease: [0.16, 1, 0.3, 1] }}>
    <div className="eyebrow"><span className="live-dot" /> Image & video integrity, clarified</div><div className="wordmark" aria-label="PhotoGuard">{'PhotoGuard'.split('').map((letter, i) => <motion.span key={i} initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: .42 + i * .06, duration: .45 }}>{letter}</motion.span>)}</div>
    <h1>Detect What<br /><em>Is Real.</em></h1><p>AI-assisted image and video deepfake detection, metadata inspection, and forensic evidence in one secure report.</p>
    <div className="hero-actions"><button className="primary" onClick={() => jump('analyze')}>Start Analysis <ArrowRight size={18} /></button><button className="secondary" onClick={() => jump('history')}><History size={17} /> View History</button></div><div className="trust-row"><ShieldCheck size={16} /> Private local scanning <i /> No cloud storage required</div>
  </motion.div><button className="scroll-hint" onClick={() => jump('analyze')} aria-label="Scroll to analyze"><span>Explore</span><ArrowDown size={16} /></button></section>;
}

function UploadPanel({ onReport }) {
  const [file, setFile] = useState(null); const [mediaId, setMediaId] = useState(''); const [drag, setDrag] = useState(false); const [busy, setBusy] = useState(false); const [error, setError] = useState('');
  const select = candidate => { if (candidate && mediaPattern.test(candidate.name)) { setFile(candidate); setError(''); } else if (candidate) setError('Choose JPG, JPEG, PNG, MP4, MOV, AVI, MKV, or WEBM.'); };
  const isVideo = file && videoPattern.test(file.name);
  async function analyze() {
    if (!file || !mediaId.trim()) { setError('Add a Custom Media ID and a file to continue.'); return; }
    setBusy(true); setError('');
    try { const data = new FormData(); data.append('custom_image_id', mediaId.trim()); data.append('file', file); onReport((await api.post('/scans', data)).data); } catch (e) { setError(e.response?.data?.detail || 'The scan could not be completed. Confirm the local API and MongoDB are running.'); } finally { setBusy(false); }
  }
  return <section id="analyze" className="scene pale-section"><div className="section-intro"><div className="section-label">01 / Analyze</div><h2>Let every frame<br />tell its story.</h2><p>Upload an image or video for a layered authenticity assessment. Your file is retained locally alongside its secure report.</p></div><motion.div className="upload-card glass" initial={{ opacity: 0, y: 30 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, amount: .3 }}>
    <div className="card-heading"><span className="small-shield"><ShieldCheck /></span><div><b>New media analysis</b><small>Secure local processing · 250 MB maximum</small></div></div><label>Custom Media ID<input value={mediaId} onChange={e => setMediaId(e.target.value)} placeholder="MEDIA-2026-001" /></label>
    <label className={'dropzone ' + (drag ? 'drag' : '')} onDragOver={e => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)} onDrop={e => { e.preventDefault(); setDrag(false); select(e.dataTransfer.files[0]); }}><input type="file" accept="image/jpeg,image/png,video/mp4,video/quicktime,video/x-msvideo,video/x-matroska,video/webm" onChange={e => select(e.target.files[0])} />{file ? <>{isVideo ? <video src={URL.createObjectURL(file)} muted /> : <img src={URL.createObjectURL(file)} alt="Selected media preview" />}<span><b>{file.name}</b><small>{isVideo ? 'Video ready to inspect' : 'Image ready to inspect'} · click to replace</small></span><X size={17} /></> : <><span className="upload-icon"><Upload size={22} /></span><span><b>Drop your image or video here</b><small>or browse from your computer</small></span><span className="formats">JPG · PNG · MP4 · MOV · AVI · MKV · WEBM</span></>}</label>
    {error && <div className="error"><Info size={15} />{error}</div>}<button className="primary full" disabled={busy} onClick={analyze}>{busy ? <><LoaderCircle className="spin" size={18} /> Running local analysis…</> : <>Analyze Media <ArrowRight size={18} /></>}</button><p className="privacy"><ShieldCheck size={14} /> Stored on your computer; never uploaded to cloud storage.</p>
  </motion.div></section>;
}

function Process() { return <section id="about" className="scene dark-section"><div className="section-intro light"><div className="section-label">02 / Method</div><h2>Three layers of<br /><em>evidence.</em></h2><p>PhotoGuard combines independent local signals into a more thoughtful integrity assessment.</p></div><div className="pipeline">{stages.map((stage, i) => { const Icon = stage.icon; return <React.Fragment key={stage.title}><motion.article className="process-card" initial={{ opacity: 0, y: 24 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: i * .12 }} whileHover={{ y: -8, rotateX: 2, rotateY: -2 }}><span className="step">0{i + 1}</span><span className="process-icon"><Icon /></span><h3>{stage.title}</h3><p>{stage.copy}</p></motion.article>{i < 2 && <div className="connector"><span /></div>}</React.Fragment>; })}</div></section>; }

function Evidence({ title, value, icon }) { return <div className="evidence-card"><span>{icon}</span><small>{title}</small><b>{value}</b><CheckCircle2 size={16} /></div>; }

function Result({ report, jump }) {
  const status = report?.result_status || 'Review Recommended'; const risk = report?.confidence ?? 50; const metadata = report?.metadata || {};
  const pdfUrl = report ? `${api.defaults.baseURL}/scans/${report.id}/report.pdf` : null;
  return <section id="result" className="scene result-section"><div className="section-intro"><div className="section-label">03 / Report preview</div><h2>Know what needs<br />a closer look.</h2><p>Signals are presented as evidence, not a verdict. Review the complete context before making a decision.</p></div><motion.div className="report glass" initial={{ opacity: 0, scale: .97 }} whileInView={{ opacity: 1, scale: 1 }} viewport={{ once: true }}><div className="report-top"><div><span className="muted">{report?.media_type === 'video' ? 'Video integrity assessment' : 'Image integrity assessment'}</span><h3>{status}</h3><span className="review"><Eye size={14} /> {report ? 'Live local ensemble result' : 'Illustrative result'}</span></div><div className="confidence"><svg viewBox="0 0 120 120"><circle cx="60" cy="60" r="50" /><circle className="meter" cx="60" cy="60" r="50" pathLength="100" style={{ strokeDasharray: `${risk} 100` }} /></svg><strong>{Math.round(risk)}<small>%</small></strong><span>risk score</span></div></div><div className="evidence"><Evidence title="AI prediction" value={report?.ai_prediction?.label || 'Synthetic visual signals'} icon={<Sparkles />} /><Evidence title="Metadata status" value={metadata.suspicious_flags?.length ? 'Review recommended' : 'No clear flags'} icon={<FileSearch />} /><Evidence title={report?.media_type === 'video' ? 'Sampled frames' : 'Image fingerprint'} value={report?.media_type === 'video' ? `${report.forensics?.sampled_frame_count || 0} visual frames` : report ? `${report.perceptual_hash?.slice(0, 12)}…` : 'Fingerprint generated'} icon={<Fingerprint />} /></div><div className="report-actions"><button className="secondary report-button" onClick={() => jump('history')}>View History <ArrowRight size={16} /></button>{pdfUrl && <a className="primary report-button download-report" href={pdfUrl} target="_blank" rel="noreferrer"><Download size={16} /> Download Detailed PDF</a>}</div></motion.div></section>;
}

function HistorySection({ refreshKey }) {
  const [scans, setScans] = useState([]); const [query, setQuery] = useState(''); const [sort, setSort] = useState('newest'); const [loading, setLoading] = useState(true); const [flip, setFlip] = useState(null);
  useEffect(() => { let alive = true; setLoading(true); api.get('/scans', { params: { q: query, sort } }).then(r => alive && setScans(r.data)).catch(() => alive && setScans([])).finally(() => alive && setLoading(false)); return () => { alive = false; }; }, [query, sort, refreshKey]);
  return <section id="history" className="scene history-section"><div className="history-head"><div><div className="section-label">04 / Archive</div><h2>Your scan history.</h2><p>Every local report, searchable when you need it.</p></div><div className="history-controls"><label className="search"><Search size={17} /><input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search Media ID or filename" /></label><label className="sort"><ChevronDown size={14} /><select value={sort} onChange={e => setSort(e.target.value)}><option value="newest">Newest first</option><option value="oldest">Oldest first</option><option value="confidence">Highest risk score</option></select></label></div></div><div className="history-grid">{loading ? <div className="empty"><LoaderCircle className="spin" /> Loading local reports…</div> : scans.length ? scans.map(scan => <motion.article className={'history-card ' + (flip === scan.id ? 'flipped' : '')} key={scan.id} whileHover={{ y: -7, rotateX: 2, rotateY: -2 }} onClick={() => setFlip(flip === scan.id ? null : scan.id)}><div className="card-inner"><div className="card-front">{scan.media_type === 'video' ? <video src={scan.image_url} poster={scan.preview_url || undefined} muted preload="metadata" /> : <img src={scan.image_url} alt="Scanned" />}<span className={'status ' + scan.result_status.toLowerCase().replaceAll(' ', '-')}>{scan.result_status}</span><div className="scan-details"><small>{scan.custom_image_id} · {scan.media_type || 'image'}</small><h3>{scan.original_filename}</h3><div><b>{Math.round(scan.confidence)}% risk score</b><time><Clock3 size={13} />{new Date(scan.scan_date).toLocaleDateString()}</time></div></div></div><div className="card-back"><small>Forensics & metadata</small><b>SHA-256</b><code>{scan.sha256}</code><b>Perceptual hash</b><code>{scan.perceptual_hash}</code><p>{scan.metadata?.suspicious_flags?.length ? scan.metadata.suspicious_flags.join(' · ') : scan.media_type === 'video' ? `Sampled ${scan.forensics?.sampled_frame_count || 0} frames for local analysis.` : 'No suspicious metadata flags detected.'}</p><span>Click to return</span></div></div></motion.article>) : <div className="empty"><History size={24} /><b>No matching scans yet</b><span>Run an analysis to start your local evidence archive.</span></div>}</div></section>;
}

function App() { const [report, setReport] = useState(null); const [refreshKey, setRefreshKey] = useState(0); const root = useRef(); const jump = id => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' }); const received = reportData => { setReport(reportData); setRefreshKey(key => key + 1); setTimeout(() => jump('result'), 120); }; useEffect(() => { const move = event => root.current?.style.setProperty('--mx', `${(event.clientX / window.innerWidth - .5) * 16}px`); window.addEventListener('mousemove', move); return () => window.removeEventListener('mousemove', move); }, []); return <main ref={root}><Header jump={jump} /><Hero jump={jump} /><UploadPanel onReport={received} /><Process /><Result report={report} jump={jump} /><HistorySection refreshKey={refreshKey} /><footer><span>✦ PhotoGuard</span><p>Evidence-led image and video integrity assessments.</p><span>Local-first · 2026</span></footer></main>; }

createRoot(document.getElementById('root')).render(<App />);
