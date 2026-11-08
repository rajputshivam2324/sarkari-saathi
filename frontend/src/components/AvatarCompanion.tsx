import { useState, useRef, useEffect } from "react";
import { Sparkles, Video, Eye, Mic, Radio } from "lucide-react";
import { AudioVisualizer } from "./AudioVisualizer";

interface AvatarCompanionProps {
  state: "idle" | "listening" | "processing" | "speaking";
  live: boolean;
  language: string;
  onToggleLive: () => void;
  error?: string | null;
}

export function AvatarCompanion({
  state,
  live,
  language,
  onToggleLive,
  error,
}: AvatarCompanionProps) {
  const [viewMode, setViewMode] = useState<"avatar" | "camera" | "orb">("avatar");
  const [cameraStream, setCameraStream] = useState<MediaStream | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);

  // Handle webcam mirror mode if user wants camera on
  useEffect(() => {
    if (viewMode === "camera") {
      navigator.mediaDevices
        ?.getUserMedia({ video: true, audio: false })
        .then((stream) => {
          setCameraStream(stream);
          if (videoRef.current) {
            videoRef.current.srcObject = stream;
          }
        })
        .catch(() => {
          setViewMode("avatar");
        });
    } else {
      if (cameraStream) {
        cameraStream.getTracks().forEach((t) => t.stop());
        setCameraStream(null);
      }
    }
    return () => {
      if (cameraStream) {
        cameraStream.getTracks().forEach((t) => t.stop());
      }
    };
  }, [viewMode]);

  const stateLabels: Record<string, { text: string; color: string; badge: string }> = {
    idle: { text: "Standby — Press Start Speaking", color: "#94a3b8", badge: "IDLE" },
    listening: { text: "Listening to your voice…", color: "#34d399", badge: "LISTENING" },
    processing: { text: "Finding matching schemes…", color: "#fbbf24", badge: "MATCHING" },
    speaking: { text: "Saathi is speaking", color: "#38bdf8", badge: "SPEAKING" },
  };

  const currentInfo = stateLabels[state] || stateLabels.idle;

  return (
    <div className={`avatar-container avatar-container--${state} ${live ? "is-live" : ""}`}>
      {/* Dynamic Glow Halo */}
      <div className={`avatar-halo avatar-halo--${state}`} />

      {/* Main Avatar Window */}
      <div className="avatar-frame">
        {viewMode === "avatar" && (
          <div className="avatar-media-wrapper">
            {/* Listening Avatar Image */}
            <img
              src="/avatar-listening.jpg"
              alt="Sarkari Saathi AI Companion Listening"
              className={`avatar-img avatar-img--listening ${state !== "speaking" ? "is-active" : "is-hidden"}`}
            />
            {/* Speaking Avatar Image with smooth crossfade & subtle speech motion */}
            <img
              src="/avatar-speaking.jpg"
              alt="Sarkari Saathi AI Companion Speaking"
              className={`avatar-img avatar-img--speaking ${state === "speaking" ? "is-active" : "is-hidden"}`}
            />
            {/* Dynamic scan line effect when processing */}
            {state === "processing" && <div className="avatar-scanline" />}
          </div>
        )}

        {viewMode === "camera" && (
          <div className="avatar-camera-wrapper">
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              className="avatar-video-feed"
            />
            <div className="avatar-pip">
              <img
                src={state === "speaking" ? "/avatar-speaking.jpg" : "/avatar-listening.jpg"}
                alt="Saathi"
                className="avatar-pip-img"
              />
            </div>
          </div>
        )}

        {viewMode === "orb" && (
          <div className="avatar-orb-wrapper">
            <div className={`neural-orb neural-orb--${state}`}>
              <div className="neural-orb-core" />
              <div className="neural-orb-ring ring-1" />
              <div className="neural-orb-ring ring-2" />
              <div className="neural-orb-ring ring-3" />
              <Sparkles className="neural-orb-sparkle" size={32} />
            </div>
          </div>
        )}

        {/* Ambient Top Bar Over Video */}
        <div className="avatar-overlay-top">
          <div className="avatar-status-pill">
            <span className={`status-indicator-dot dot--${state}`} />
            <span className="status-indicator-badge">{currentInfo.badge}</span>
            <span className="status-indicator-lang">{language.toUpperCase()}</span>
          </div>

          <div className="avatar-controls-top">
            <button
              type="button"
              className={`mode-toggle-btn ${viewMode === "avatar" ? "active" : ""}`}
              onClick={() => setViewMode("avatar")}
              title="AI Companion View"
            >
              <Eye size={15} />
            </button>
            <button
              type="button"
              className={`mode-toggle-btn ${viewMode === "camera" ? "active" : ""}`}
              onClick={() => setViewMode(viewMode === "camera" ? "avatar" : "camera")}
              title="Camera Mirror / Face-to-Face"
            >
              <Video size={15} />
            </button>
            <button
              type="button"
              className={`mode-toggle-btn ${viewMode === "orb" ? "active" : ""}`}
              onClick={() => setViewMode("orb")}
              title="3D Neural Orb View"
            >
              <Radio size={15} />
            </button>
          </div>
        </div>

        {/* Center Prompt when idle */}
        {!live && (
          <div className="avatar-start-overlay" onClick={onToggleLive}>
            <div className="start-pulse-button">
              <Mic size={28} />
            </div>
            <div className="start-prompt-text">
              <h4>Start Speaking</h4>
              <p>Speak in Hindi, English or regional languages</p>
            </div>
          </div>
        )}

        {/* Ambient Bottom Bar Over Video */}
        <div className="avatar-overlay-bottom">
          <div className="avatar-caption-box">
            <div className="avatar-name-row">
              <span className="avatar-name">Saathi AI Companion</span>
              <span className="avatar-tech-tag">Prisma v3.0</span>
            </div>
            <p className="avatar-status-text">{currentInfo.text}</p>
          </div>

          <div className="avatar-waveform-box">
            <AudioVisualizer state={state} barCount={20} />
          </div>
        </div>

        {error && (
          <div className="avatar-error-banner">
            <span>{error}</span>
          </div>
        )}
      </div>
    </div>
  );
}
