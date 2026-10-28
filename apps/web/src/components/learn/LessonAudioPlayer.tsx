"use client";

import { useEffect, useRef, useState } from "react";
import { getToken } from "@/lib/session";
import type { Lesson } from "@/lib/api";

type PlaybackStatus = "idle" | "loading" | "playing" | "paused" | "error";
type Voice = "bf_emma" | "bm_george";

export function LessonAudioPlayer({
  objectiveId,
  lesson,
  onSectionActive,
}: {
  objectiveId: string;
  lesson: Lesson;
  onSectionActive?: (index: number | null) => void;
}) {
  const [activeTab, setActiveTab] = useState<"podcast" | "readout">(
    lesson.podcast_audio_url ? "podcast" : "readout"
  );
  const [status, setStatus] = useState<PlaybackStatus>("idle");
  const [voice, setVoice] = useState<Voice>("bf_emma");
  const [rate, setRate] = useState<number>(1.0);
  const [part, setPart] = useState<"all" | "summary" | "section">("all");
  const [sectionIndex, setSectionIndex] = useState<number>(0);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [audioSrc, setAudioSrc] = useState<string | null>(null);

  // Podcast state
  const [hasPodcastAudio, setHasPodcastAudio] = useState<boolean>(Boolean(lesson.podcast_audio_url));
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [showScript, setShowScript] = useState<boolean>(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const audioRef = useRef<HTMLAudioElement | null>(null);
  const clips = useRef<Map<string, string>>(new Map());

  useEffect(() => {
    const cache = clips.current;
    return () => cache.forEach((url) => URL.revokeObjectURL(url));
  }, []);

  // Check if podcast audio exists on mount if not specified in lesson
  useEffect(() => {
    let cancelled = false;
    const token = getToken();
    fetch(`/api/learn/objectives/${objectiveId}/podcast`, {
      method: "HEAD",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then((res) => {
        if (!cancelled && res.ok) {
          setHasPodcastAudio(true);
        }
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [objectiveId]);

  async function loadClip(): Promise<string> {
    const token = getToken();
    if (activeTab === "podcast") {
      const key = `podcast:${objectiveId}`;
      const cached = clips.current.get(key);
      if (cached) return cached;

      const res = await fetch(`/api/learn/objectives/${objectiveId}/podcast`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) {
        throw new Error("No podcast audio file uploaded for this topic yet. You can upload one from NotebookLM below!");
      }
      const buffer = await res.arrayBuffer();
      if (!buffer || buffer.byteLength < 100) {
        throw new Error("Podcast audio file is empty or preparing.");
      }
      const blob = new Blob([buffer], { type: "audio/mpeg" });
      const url = URL.createObjectURL(blob);
      clips.current.set(key, url);
      return url;
    }

    const query = new URLSearchParams({ part, index: String(sectionIndex), voice });
    const key = query.toString();
    const cached = clips.current.get(key);
    if (cached) return cached;

    const res = await fetch(`/api/learn/objectives/${objectiveId}/audio?${key}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body?.error?.message ?? "The voice isn't available right now.");
    }
    const buffer = await res.arrayBuffer();
    if (!buffer || buffer.byteLength < 100) {
      throw new Error("Voice readout is preparing or empty. Please try again in a moment.");
    }
    const blob = new Blob([buffer], { type: "audio/mpeg" });
    const url = URL.createObjectURL(blob);
    clips.current.set(key, url);
    return url;
  }

  useEffect(() => {
    if (audioRef.current) {
      audioRef.current.playbackRate = rate;
    }
  }, [rate]);

  function handleTogglePlay() {
    const audio = audioRef.current;

    if (status === "playing" && audio) {
      audio.pause();
      setStatus("paused");
      return;
    }

    if (status === "paused" && audioSrc && audio) {
      audio
        .play()
        .then(() => setStatus("playing"))
        .catch(() => {
          setStatus("error");
          setErrorMessage("Failed to resume audio. Tap play again.");
        });
      return;
    }

    // Fresh play request
    setErrorMessage(null);
    setStatus("loading");
    loadClip()
      .then((url) => {
        setAudioSrc(url);
        if (audioRef.current) {
          audioRef.current.src = url;
          audioRef.current.load();
          audioRef.current.playbackRate = rate;
          audioRef.current
            .play()
            .then(() => setStatus("playing"))
            .catch((e) => {
              if (e.name !== "NotAllowedError") {
                setStatus("error");
                setErrorMessage("Audio playback could not start. Please try playing again.");
              } else {
                setStatus("paused");
              }
            });
        }
      })
      .catch((e: Error) => {
        setStatus("error");
        setErrorMessage(e.message);
        onSectionActive?.(null);
      });

    if (activeTab === "readout" && part === "section") {
      onSectionActive?.(sectionIndex);
    } else {
      onSectionActive?.(null);
    }
  }

  function handleStop() {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
    }
    setStatus("idle");
    setCurrentTime(0);
    onSectionActive?.(null);
  }

  function handleSeek(e: React.ChangeEvent<HTMLInputElement>) {
    const target = Number(e.target.value);
    setCurrentTime(target);
    if (audioRef.current) {
      audioRef.current.currentTime = target;
    }
  }

  function handleJump(offsetSeconds: number) {
    if (!audioRef.current) return;
    const newTime = Math.max(0, Math.min(duration, audioRef.current.currentTime + offsetSeconds));
    audioRef.current.currentTime = newTime;
    setCurrentTime(newTime);
  }

  function formatTime(s: number): string {
    if (!Number.isFinite(s) || s < 0) return "0:00";
    const mins = Math.floor(s / 60);
    const secs = Math.floor(s % 60);
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  }

  async function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setIsUploading(true);
    setErrorMessage(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const token = getToken();
      const res = await fetch(`/api/learn/objectives/${objectiveId}/podcast`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: formData,
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body?.error?.message ?? "Failed to upload audio file.");
      }
      // Invalidate cached podcast URL
      clips.current.delete(`podcast:${objectiveId}`);
      setHasPodcastAudio(true);
      handleStop();
      setAudioSrc(null);
      // Auto-play the newly uploaded audio
      setTimeout(() => {
        handleTogglePlay();
      }, 300);
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  const rates = [1.0, 1.25, 1.5, 2.0];
  const podcastScript = lesson.podcast_script ?? [];

  return (
    <div className="flex flex-col gap-3 rounded-2xl border border-blue-200 bg-gradient-to-br from-orange-50/70 via-white to-amber-50/50 p-4 shadow-sm">
      {/* Audio element in DOM */}
      {audioSrc && (
        <audio
          ref={audioRef}
          src={audioSrc}
          preload="auto"
          onTimeUpdate={() => {
            if (audioRef.current) setCurrentTime(audioRef.current.currentTime);
          }}
          onLoadedMetadata={() => {
            if (audioRef.current) setDuration(audioRef.current.duration || 0);
          }}
          onEnded={() => {
            setStatus("idle");
            setCurrentTime(0);
            onSectionActive?.(null);
          }}
          onError={() => {
            setStatus("error");
            setErrorMessage("Audio format not accepted by player.");
            onSectionActive?.(null);
          }}
        />
      )}

      {/* Mode Switcher Tabs */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 pb-2.5">
        <div className="flex items-center gap-1.5 rounded-xl bg-blue-50 p-1 text-xs font-fun font-bold">
          <button
            onClick={() => {
              if (activeTab !== "readout") {
                handleStop();
                setAudioSrc(null);
                setActiveTab("readout");
              }
            }}
            className={`flex items-center gap-1.5 rounded-lg px-3 py-1 transition ${
              activeTab === "readout"
                ? "bg-white text-blue-900 shadow-2xs"
                : "text-slate-600 hover:text-blue-950"
            }`}
          >
            <span>🔊</span>
            <span>Listen to Lesson (UK Voice)</span>
          </button>
          <button
            onClick={() => {
              if (activeTab !== "podcast") {
                handleStop();
                setAudioSrc(null);
                setActiveTab("podcast");
                if (podcastScript.length > 0 && !hasPodcastAudio) {
                  setShowScript(true);
                }
              }
            }}
            className={`flex items-center gap-1.5 rounded-lg px-3 py-1 transition ${
              activeTab === "podcast"
                ? "bg-white text-blue-900 shadow-2xs"
                : "text-slate-600 hover:text-blue-950"
            }`}
          >
            <span>🎙️</span>
            <span>Deep Dive Dialogue</span>
            {(hasPodcastAudio || podcastScript.length > 0) && (
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" title="Ready" />
            )}
          </button>
        </div>

        {/* Upload NotebookLM Audio Button (shown only when in Deep Dive tab) */}
        {activeTab === "podcast" && (
          <div className="flex items-center gap-2">
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileUpload}
              accept="audio/*,.mp3,.m4a"
              className="hidden"
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={isUploading}
              className="inline-flex items-center gap-1.5 rounded-xl border border-blue-200 bg-white px-2.5 py-1 text-xs font-fun font-bold text-blue-800 shadow-2xs hover:bg-blue-50 disabled:opacity-50 transition"
              title="Upload an MP3 audio overview downloaded from NotebookLM"
            >
              <span>📥</span>
              <span>{isUploading ? "Uploading MP3…" : hasPodcastAudio ? "Replace .mp3" : "Attach .mp3"}</span>
            </button>
          </div>
        )}
      </div>

      {/* Main Player Row */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        {/* Play / Pause / Skip / Time */}
        <div className="flex items-center gap-2">
          <button
            onClick={handleTogglePlay}
            disabled={status === "loading"}
            className="flex h-11 w-11 items-center justify-center rounded-2xl bg-gradient-to-tr from-orange-600 to-amber-500 text-white shadow-sm transition hover:brightness-105 disabled:opacity-50"
            title={status === "playing" ? "Pause" : "Play"}
            aria-label={status === "playing" ? "Pause" : "Play"}
          >
            {status === "loading" ? (
              <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
            ) : status === "playing" ? (
              <span className="text-base font-bold">⏸</span>
            ) : (
              <span className="ml-0.5 text-base font-bold">▶</span>
            )}
          </button>

          <button
            onClick={() => handleJump(-15)}
            disabled={status === "idle"}
            className="flex h-8 w-8 items-center justify-center rounded-lg border border-slate-200 bg-white text-xs font-bold text-slate-700 hover:bg-slate-50 disabled:opacity-40"
            title="Jump back 15s"
          >
            -15s
          </button>
          <button
            onClick={() => handleJump(15)}
            disabled={status === "idle"}
            className="flex h-8 w-8 items-center justify-center rounded-lg border border-slate-200 bg-white text-xs font-bold text-slate-700 hover:bg-slate-50 disabled:opacity-40"
            title="Jump forward 15s"
          >
            +15s
          </button>

          {status !== "idle" && (
            <button
              onClick={handleStop}
              className="flex h-8 w-8 items-center justify-center rounded-lg border border-slate-200 bg-white text-xs font-bold text-slate-600 hover:bg-slate-50"
              title="Stop"
            >
              ⏹
            </button>
          )}

          <div className="ml-1">
            <div className="flex items-center gap-1.5 text-xs font-fun font-bold text-slate-900">
              <span>{activeTab === "podcast" ? "🎙️ Maya & Leo · Deep Dive" : "🔊 Kokoro Voice Readout"}</span>
              {status === "loading" && <span className="text-blue-600 font-normal">(Buffering…)</span>}
            </div>
            <div className="text-[11px] font-mono text-slate-500">
              {formatTime(currentTime)} / {formatTime(duration)}
            </div>
          </div>
        </div>

        {/* Tab-Specific Controls */}
        <div className="flex flex-wrap items-center gap-2">
          {activeTab === "readout" && (
            <>
              {/* Part Selection */}
              <select
                value={part === "section" ? `section:${sectionIndex}` : part}
                onChange={(e) => {
                  handleStop();
                  setAudioSrc(null);
                  const val = e.target.value;
                  if (val.startsWith("section:")) {
                    setPart("section");
                    setSectionIndex(Number(val.split(":")[1]));
                  } else {
                    setPart(val as "all" | "summary");
                  }
                }}
                className="rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-xs font-medium text-slate-700 shadow-2xs"
              >
                <option value="all">Full Lesson</option>
                {lesson.summary && <option value="summary">Summary only</option>}
                {lesson.sections.map((sec, idx) => (
                  <option key={idx} value={`section:${idx}`}>
                    Section {idx + 1}: {sec.heading.slice(0, 20)}…
                  </option>
                ))}
              </select>

              {/* Voice Switcher */}
              <select
                value={voice}
                onChange={(e) => {
                  handleStop();
                  setAudioSrc(null);
                  setVoice(e.target.value as Voice);
                }}
                className="rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-xs font-medium text-slate-700 shadow-2xs"
              >
                <option value="bf_emma">Emma (UK 🇬🇧)</option>
                <option value="bm_george">George (UK 🇬🇧)</option>
              </select>
            </>
          )}

          {activeTab === "podcast" && podcastScript.length > 0 && (
            <button
              onClick={() => setShowScript(!showScript)}
              className={`rounded-lg border px-2.5 py-1 text-xs font-fun font-bold transition shadow-2xs ${
                showScript
                  ? "border-orange-400 bg-blue-50 text-blue-950"
                  : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
              }`}
            >
              💬 {showScript ? "Hide Script" : "Show Dialogue Script"}
            </button>
          )}

          {/* Speed Toggle Chips */}
          <div className="flex items-center rounded-lg border border-slate-200 bg-white p-0.5 shadow-2xs">
            {rates.map((r) => (
              <button
                key={r}
                onClick={() => setRate(r)}
                className={`rounded-md px-1.5 py-0.5 text-[10px] font-bold transition ${
                  rate === r ? "bg-orange-600 text-white" : "text-slate-600 hover:text-slate-900"
                }`}
              >
                {r}x
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Scrubber Bar */}
      {duration > 0 && (
        <div className="mt-1 flex items-center gap-2">
          <input
            type="range"
            min={0}
            max={duration}
            step={0.1}
            value={currentTime}
            onChange={handleSeek}
            className="h-1.5 w-full cursor-pointer appearance-none rounded-lg bg-orange-200 accent-orange-600"
          />
        </div>
      )}

      {errorMessage && (
        <div className="rounded-xl border border-rose-200 bg-rose-50/80 p-2.5 text-xs text-rose-800">
          <p className="font-semibold">⚠️ {errorMessage}</p>
          {activeTab === "podcast" && !hasPodcastAudio && (
            <p className="mt-1 text-[11px] text-rose-700">
              💡 <strong>Tip:</strong> You can download the <em>Audio Overview (Deep Dive)</em> from{" "}
              <strong>notebooklm.google.com</strong> and click <strong>&quot;Upload NotebookLM .mp3&quot;</strong> above to listen to it here anytime!
            </p>
          )}
        </div>
      )}

      {/* Interactive Two-Host Conversational Dialogue (Maya & Leo) */}
      {activeTab === "podcast" && showScript && podcastScript.length > 0 && (
        <div className="mt-2 flex flex-col gap-2.5 rounded-xl border border-blue-200 bg-white/90 p-3.5">
          <div className="flex items-center justify-between border-b border-slate-200 pb-1.5">
            <span className="font-fun text-xs font-bold text-blue-950">
              🎙️ Deep Dive Conversation Script
            </span>
            <span className="text-[10px] text-slate-500 font-medium">NotebookLM Style</span>
          </div>
          <div className="flex flex-col gap-2 max-h-72 overflow-y-auto pr-1">
            {podcastScript.map((turn, idx) => {
              const isMaya = turn.speaker.toLowerCase().includes("maya");
              return (
                <div
                  key={idx}
                  className={`flex items-start gap-2.5 rounded-xl p-2.5 text-xs ${
                    isMaya
                      ? "border border-purple-100 bg-purple-50/60"
                      : "border border-slate-100 bg-amber-50/60"
                  }`}
                >
                  <div
                    className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold text-white shadow-2xs ${
                      isMaya ? "bg-purple-600" : "bg-amber-600"
                    }`}
                  >
                    {isMaya ? "M" : "L"}
                  </div>
                  <div className="flex flex-col gap-0.5">
                    <span
                      className={`font-fun font-bold text-[11px] ${
                        isMaya ? "text-purple-900" : "text-amber-900"
                      }`}
                    >
                      {turn.speaker}
                    </span>
                    <p className="leading-relaxed text-slate-800">{turn.text}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
