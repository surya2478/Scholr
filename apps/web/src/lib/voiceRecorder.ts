// Records a spoken question and returns it as a 16 kHz mono WAV (docs/STUDENT-APP.md §16).
//
// The recording stays in the browser until she stops; it is then sent once to Scholr's API, which has the
// `speech_to_text` role transcribe it and keeps nothing. Browsers record in different formats (WebM/Opus in
// Chrome, MP4/AAC in Safari), so it is decoded here and re-encoded as plain PCM WAV — one format the API checks
// and the model reads. No browser speech service is involved: nothing goes to Google or Microsoft.

const TARGET_RATE = 16000;
export const MAX_SECONDS = 60;

export type Recording = { stop: () => Promise<Blob>; cancel: () => void };

export async function startRecording(): Promise<Recording> {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const recorder = new MediaRecorder(stream);
  const chunks: Blob[] = [];
  recorder.ondataavailable = (e) => {
    if (e.data.size > 0) chunks.push(e.data);
  };
  recorder.start();
  const release = () => stream.getTracks().forEach((t) => t.stop());

  return {
    stop: () =>
      new Promise<Blob>((resolve, reject) => {
        recorder.onstop = async () => {
          release();
          try {
            resolve(await toWav(new Blob(chunks, { type: recorder.mimeType })));
          } catch (err) {
            reject(err);
          }
        };
        recorder.stop();
      }),
    cancel: () => {
      recorder.onstop = null;
      if (recorder.state !== "inactive") recorder.stop();
      release();
    },
  };
}

async function toWav(recorded: Blob): Promise<Blob> {
  const context = new AudioContext();
  let decoded: AudioBuffer;
  try {
    decoded = await context.decodeAudioData(await recorded.arrayBuffer());
  } finally {
    void context.close();
  }
  const seconds = Math.min(decoded.duration, MAX_SECONDS);
  const offline = new OfflineAudioContext(1, Math.max(1, Math.ceil(seconds * TARGET_RATE)), TARGET_RATE);
  const source = offline.createBufferSource();
  source.buffer = decoded; // mixed down to one channel by the offline context
  source.connect(offline.destination);
  source.start();
  const mono = (await offline.startRendering()).getChannelData(0);
  return encodeWav(mono, TARGET_RATE);
}

function encodeWav(samples: Float32Array, rate: number): Blob {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  const text = (offset: number, value: string) => {
    for (let i = 0; i < value.length; i++) view.setUint8(offset + i, value.charCodeAt(i));
  };
  text(0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  text(8, "WAVE");
  text(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true); // PCM
  view.setUint16(22, 1, true); // mono
  view.setUint32(24, rate, true);
  view.setUint32(28, rate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  text(36, "data");
  view.setUint32(40, samples.length * 2, true);
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return new Blob([buffer], { type: "audio/wav" });
}

export async function toBase64(blob: Blob): Promise<string> {
  const bytes = new Uint8Array(await blob.arrayBuffer());
  let binary = "";
  for (let i = 0; i < bytes.length; i += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  }
  return btoa(binary);
}
