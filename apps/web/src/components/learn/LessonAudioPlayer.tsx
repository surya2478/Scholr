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
  const [status, setStatus] = useState<PlaybackStatus>("idle");
  const [voice, setVoice] = useState<Voice>("bf_emma");
  const [rate, setRate] = useState<number>(1.0);
  const [part, setPart] = useState<"all" | "summary" | "section">("all");
  const [sectionIndex, setSectionIndex] = useState<number>(0);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [audioSrc, setAudioSrc] = useState<string | null>(null);

  const audioRef = useRef<HTMLAudioElement | null>(null);
  // Clips already fetched this visit, by part/section/voice, so replaying one makes no second request.
  const clips = useRef<Map<string, string>>(new Map());

  useEffect(() => {
    const cache = clips.current;
    return () => cache.forEach((url) => URL.revokeObjectURL(url));
  }, []);

  // The clip is fetched with the Authorization header and played from a blob: URL. An <audio src> cannot send a
  // header, and a token in the URL would end up in server and proxy logs and in browser history.
  async function loadClip(): Promise<string> {
    const query = new URLSearchParams({ part, index: String(sectionIndex), voice });
    const key = query.toString();
    const cached = clips.current.get(key);
    if (cached) return cached;
    const token = getToken();
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
        .then(() => {
          setStatus("playing");
        })
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

    if (part === "section") {
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

  function formatTime(s: number): string {
    if (!Number.isFinite(s) || s < 0) return "0:00";
    const mins = Math.floor(s / 60);
    const secs = Math.floor(s % 60);
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  }

  const rates = [1.0, 1.25, 1.5];

  return (
    <div className="rounded-2xl border border-orange-200 bg-gradient-to-r from-orange-50 via-white to-amber-50/60 p-3.5 shadow-xs">
      {/* Native HTML5 Audio Tag directly in DOM */}
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
          onCanPlay={() => {
            if (status === "loading" && audioRef.current) {
              audioRef.current.playbackRate = rate;
              audioRef.current
                .play()
                .then(() => setStatus("playing"))
                .catch((e) => {
                  if (e.name !== "NotAllowedError") {
                    setStatus("error");
                    setErrorMessage("Failed to start audio playback");
                  } else {
                    setStatus("paused");
                  }
                });
            }
          }}
          onEnded={() => {
            setStatus("idle");
            setCurrentTime(0);
            onSectionActive?.(null);
          }}
          onError={() => {
            setStatus("error");
            setErrorMessage(
              "Audio format was not accepted by browser media player. Try 'Summary only' or switch voice."
            );
            onSectionActive?.(null);
          }}
        />
      )}

      <div className="flex flex-wrap items-center justify-between gap-3">
        {/* Playback Controls & Status */}
        <div className="flex items-center gap-2">
          <button
            onClick={handleTogglePlay}
            disabled={status === "loading"}
            className="flex h-10 w-10 items-center justify-center rounded-xl bg-orange-600 text-white shadow-xs transition hover:bg-orange-700 disabled:opacity-50"
            title={status === "playing" ? "Pause" : "Play readout"}
            aria-label={status === "playing" ? "Pause" : "Play readout"}
          >
            {status === "loading" ? (
              <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
            ) : status === "playing" ? (
              <span className="text-base font-bold">⏸</span>
            ) : (
              <span className="ml-0.5 text-base font-bold">▶</span>
            )}
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

          <div>
            <div className="flex items-center gap-1.5 text-xs font-fun font-bold text-slate-800">
              <span>🎙 Kokoro Voice Readout</span>
              {status === "loading" && <span className="text-orange-600 font-normal">(Buffering audio…)</span>}
            </div>
            <div className="text-[11px] text-slate-500">
              {formatTime(currentTime)} / {formatTime(duration)}
            </div>
          </div>
        </div>

        {/* Audio Scope & Voice Selectors */}
        <div className="flex flex-wrap items-center gap-2 text-xs">
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
                Section {idx + 1}: {sec.heading.slice(0, 24)}…
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

          {/* Speed Toggle Chips */}
          <div className="flex items-center rounded-lg border border-slate-200 bg-white p-0.5">
            {rates.map((r) => (
              <button
                key={r}
                onClick={() => setRate(r)}
                className={`rounded-md px-2 py-0.5 text-[11px] font-bold transition ${
                  rate === r ? "bg-orange-600 text-white" : "text-slate-600 hover:text-slate-900"
                }`}
              >
                {r}x
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Progress scrubber */}
      {duration > 0 && (
        <div className="mt-2.5 flex items-center gap-2">
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
        <p className="mt-2 text-[11px] font-medium text-rose-600">
          ⚠️ {errorMessage}
        </p>
      )}
    </div>
  );
}
