// main.js — Mikrofon (Web Speech API) → WebSocket → Antwort abspielen.
import { startOrb } from "./orb.js";

const $ = (id) => document.getElementById(id);
const status = (s) => ($("status").textContent = s);

let ws, recog, audioCtx, analyser;
let speaking = 0;        // wie viele Sätze noch in der Warteschlange
let synthPulse = false;  // Browser-Stimme liefert keine Pegel → künstlicher Puls
const queue = [];
let playing = false;

function level() {
  if (synthPulse) return 0.5 + 0.3 * Math.sin(performance.now() / 90);
  if (!analyser) return 0;
  const d = new Uint8Array(analyser.fftSize);
  analyser.getByteTimeDomainData(d);
  let sum = 0;
  for (const v of d) sum += ((v - 128) / 128) ** 2;
  return Math.min(1, Math.sqrt(sum / d.length) * 4);
}

function connect() {
  ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
  ws.onopen = () => status("hört zu");
  ws.onclose = () => { status("getrennt, verbinde neu"); setTimeout(connect, 1500); };
  ws.onmessage = (e) => {
    const m = JSON.parse(e.data);
    if (m.type === "thinking") { status("denkt nach"); $("say").textContent = ""; }
    if (m.type === "sentence") { queue.push(m); speaking++; pump(); }
    if (m.type === "done" && speaking === 0) status("hört zu");
  };
}

async function pump() {
  if (playing || !queue.length) return;
  playing = true;
  const m = queue.shift();
  status("spricht");
  $("say").textContent = m.text;
  try { recog?.stop(); } catch {}
  await (m.audio ? playMp3(m.audio) : speakBrowser(m.text));
  speaking--;
  playing = false;
  if (queue.length) return pump();
  status("hört zu");
  listen();
}

async function playMp3(b64) {
  const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
  const buf = await audioCtx.decodeAudioData(bytes.buffer);
  const src = audioCtx.createBufferSource();
  src.buffer = buf;
  src.connect(analyser);
  return new Promise((r) => { src.onended = r; src.start(); });
}

function speakBrowser(text) {
  return new Promise((resolve) => {
    const u = new SpeechSynthesisUtterance(text);
    u.lang = "de-DE";
    const v = speechSynthesis.getVoices().find((v) => v.lang.startsWith("de"));
    if (v) u.voice = v;
    u.onstart = () => (synthPulse = true);
    u.onend = u.onerror = () => { synthPulse = false; resolve(); };
    speechSynthesis.speak(u);
  });
}

function setupRecognition() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) { status("Spracherkennung fehlt, bitte Chrome nutzen"); return; }
  recog = new SR();
  recog.lang = "de-DE";
  recog.continuous = true;
  recog.interimResults = true;
  recog.onresult = (e) => {
    let interim = "";
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const r = e.results[i];
      if (r.isFinal) {
        const text = r[0].transcript.trim();
        $("you").textContent = text;
        if (text && ws?.readyState === 1) ws.send(JSON.stringify({ type: "transcript", text }));
      } else interim += r[0].transcript;
    }
    if (interim) $("you").textContent = interim;
  };
  // Chrome beendet die Erkennung nach Stille; solange Jarvis nicht spricht, neu starten.
  recog.onend = () => { if (!playing) listen(); };
}

function listen() {
  try { recog?.start(); } catch {}  // wirft, wenn sie schon läuft
}

$("start").onclick = () => {
  $("start").remove();
  audioCtx = new AudioContext();
  analyser = audioCtx.createAnalyser();
  analyser.fftSize = 512;
  analyser.connect(audioCtx.destination);
  startOrb($("orb"), level);
  setupRecognition();
  connect();
  listen();
};
