import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import * as api from "../api";
import { AccountMenu } from "../components/AccountMenu";
import { Pagination } from "../components/Pagination";
import { SchemeCard, type SchemeItem } from "../components/SchemeCard";
import { useAuth } from "../auth";
import { usePageTitle } from "../lib/usePageTitle";
import "../desk.css";

type ChatMsg = {
  id?: string;
  role: "user" | "assistant";
  text: string;
  language?: string | null;
  schemes?: SchemeItem[];
};

type AgentState = "idle" | "listening" | "processing" | "speaking";

const LANGUAGES = [
  { code: "hi-IN", label: "हिन्दी · Hindi" },
  { code: "en-IN", label: "English" },
  { code: "hi-en", label: "Hinglish" },
  { code: "ta-IN", label: "தமிழ் · Tamil" },
  { code: "te-IN", label: "తెలుగు · Telugu" },
  { code: "kn-IN", label: "ಕನ್ನಡ · Kannada" },
  { code: "mr-IN", label: "मराठी · Marathi" },
  { code: "bn-IN", label: "বাংলা · Bengali" },
  { code: "gu-IN", label: "ગુજરાતી · Gujarati" },
  { code: "pa-IN", label: "ਪੰਜਾਬੀ · Punjabi" },
];

const STATUS_TEXT: Record<AgentState, string> = {
  idle: "READY",
  listening: "LISTENING",
  processing: "MATCHING",
  speaking: "SPEAKING",
};

const MATCHES_PER_PAGE = 3;

function wsUrl(token: string, sessionId: string) {
  const host = import.meta.env.VITE_WS_URL || "ws://127.0.0.1:8000";
  return `${host}/ws/live?token=${encodeURIComponent(token)}&session_id=${encodeURIComponent(sessionId)}`;
}

const icon = {
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.8,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  "aria-hidden": true,
};

export function DeskPage() {
  usePageTitle("Voice desk");
  const { token, user, expireSession } = useAuth();
  const [params, setParams] = useSearchParams();
  const sessionParam = params.get("session");

  const [sessionId, setSessionId] = useState<string>(() => sessionParam ?? crypto.randomUUID());
  const [sessionLoading, setSessionLoading] = useState(Boolean(sessionParam));
  const [msgs, setMsgs] = useState<ChatMsg[]>([]);
  const [schemes, setSchemes] = useState<SchemeItem[]>([]);
  const [state, setState] = useState<AgentState>("idle");
  const [live, setLive] = useState(false);
  const [text, setText] = useState("");
  const [lang, setLang] = useState("hi-IN");
  const [isMuted, setIsMuted] = useState(false);
  const [partial, setPartial] = useState("");
  const [toast, setToast] = useState<string | null>(null);
  const [showMatches, setShowMatches] = useState(true);
  const [matchPage, setMatchPage] = useState(1);

  const wsRef = useRef<WebSocket | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const workletRef = useRef<AudioWorkletNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const messagesRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const liveRef = useRef(false);
  const mutedRef = useRef(false);
  const pendingTextRef = useRef<{ text: string; language: string } | null>(null);
  const toastTimer = useRef<number | undefined>(undefined);
  const openedSessionRef = useRef<string | null>(null);

  useEffect(() => {
    liveRef.current = live;
  }, [live]);

  useEffect(() => {
    mutedRef.current = isMuted;
  }, [isMuted]);

  // Keep the newest message in view without moving the whole page.
  useEffect(() => {
    const el = messagesRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [msgs, state, partial]);

  // New matches arrive -> show them from the first page.
  useEffect(() => {
    setMatchPage(1);
  }, [schemes]);

  // Open a past conversation from /desk?session=ID (and reset if the user navigates back to plain /desk).
  useEffect(() => {
    if (!token) return;

    if (!sessionParam) {
      if (openedSessionRef.current) {
        openedSessionRef.current = null;
        disconnectLive();
        setSessionId(crypto.randomUUID());
        setMsgs([]);
        setSchemes([]);
        setPartial("");
      }
      setSessionLoading(false);
      return;
    }

    const controller = new AbortController();
    openedSessionRef.current = sessionParam;
    disconnectLive(); // a live connection belongs to the previous session
    setSessionId(sessionParam);
    setMsgs([]);
    setSchemes([]);
    setPartial("");
    setSessionLoading(true);

    api
      .getSession(token, sessionParam, controller.signal)
      .then((res) => {
        setMsgs(
          res.messages.map((m) => ({
            id: m.id,
            role: m.role,
            text: m.text,
            language: m.language,
            schemes: m.schemes ?? undefined,
          })),
        );
        const lastSchemes = [...res.messages].reverse().find((m) => m.schemes?.length)?.schemes;
        setSchemes(lastSchemes ?? []);
        setSessionLoading(false);
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setSessionLoading(false);
        if (err instanceof api.ApiError && err.status === 401) {
          expireSession();
          return;
        }
        const notFound = err instanceof api.ApiError && err.status === 404;
        announce(notFound ? "That conversation could not be found." : "Could not load that conversation.", 6000);
        openedSessionRef.current = null;
        setSessionId(crypto.randomUUID());
        setParams({}, { replace: true });
      });

    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionParam, token]);

  useEffect(() => {
    return () => {
      window.clearTimeout(toastTimer.current);
      stopPlayback();
      stopMic();
      const ws = wsRef.current;
      wsRef.current = null; // so its onclose handler ignores this teardown
      ws?.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function announce(message: string, ms = 4200) {
    setToast(message);
    window.clearTimeout(toastTimer.current);
    toastTimer.current = window.setTimeout(() => setToast(null), ms);
  }

  function notifySpeaking(active: boolean) {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "speaking", active }));
    }
  }

  function stopPlayback() {
    if (audioRef.current) {
      audioRef.current.onended = null;
      audioRef.current.onerror = null;
      audioRef.current.pause();
      audioRef.current.src = "";
      audioRef.current = null;
      notifySpeaking(false);
    }
  }

  function playWavB64(b64: string) {
    if (mutedRef.current) {
      // Not playing: release the server's half-duplex lock so the user can keep talking.
      // Delayed slightly so it can't arrive before the server marks the reply as "speaking".
      window.setTimeout(() => notifySpeaking(false), 600);
      setState(liveRef.current ? "listening" : "idle");
      return;
    }
    stopPlayback();
    setState("speaking");
    notifySpeaking(true);
    const audio = new Audio(`data:audio/wav;base64,${b64}`);
    audioRef.current = audio;
    const finish = () => {
      if (audioRef.current !== audio) return;
      audioRef.current = null;
      notifySpeaking(false);
      setState(liveRef.current ? "listening" : "idle");
    };
    audio.onended = finish;
    audio.onerror = finish;
    void audio.play().catch(finish);
  }

  /** Opens the live socket. `withMic` = the user pressed the mic (vs. only typing). */
  function connect(withMic: boolean) {
    if (!token) return;
    const previous = wsRef.current;
    wsRef.current = null; // detach before closing so the old socket's onclose is ignored
    previous?.close();

    const ws = new WebSocket(wsUrl(token, sessionId));
    ws.binaryType = "arraybuffer";
    wsRef.current = ws;

    ws.onopen = () => {
      if (wsRef.current !== ws) return;
      if (withMic) {
        setLive(true);
        setState("listening");
      }
      const queued = pendingTextRef.current;
      if (queued) {
        pendingTextRef.current = null;
        setState("processing");
        ws.send(JSON.stringify({ type: "text", text: queued.text, language: queued.language }));
      }
    };

    ws.onclose = (ev) => {
      if (wsRef.current !== ws) return;
      if (ev.code === 4401) announce("Your session has expired. Please log in again.", 6000);
      wsRef.current = null;
      stopPlayback();
      stopMic();
      pendingTextRef.current = null;
      setLive(false);
      setState("idle");
      setPartial("");
    };

    ws.onerror = () => {
      if (wsRef.current !== ws) return;
      announce("Live connection failed. Please check that the server is running.", 6000);
    };

    ws.onmessage = (ev) => {
      if (wsRef.current !== ws) return;
      try {
        handleServer(JSON.parse(ev.data as string));
      } catch {
        /* ignore malformed frames */
      }
    };
  }

  function handleServer(data: Record<string, unknown>) {
    const type = data.type as string;
    if (type === "ready") {
      if (typeof data.session_id === "string") setSessionId(data.session_id);
      const hist = (data.history as ChatMsg[]) || [];
      if (hist.length) {
        setMsgs(
          hist.map((m) => ({
            id: m.id,
            role: m.role,
            text: m.text,
            language: m.language,
            schemes: m.schemes as SchemeItem[] | undefined,
          })),
        );
        const lastSchemes = [...hist].reverse().find((m) => m.schemes?.length)?.schemes;
        if (lastSchemes) setSchemes(lastSchemes as SchemeItem[]);
      }
      setPartial("");
    } else if (type === "user") {
      const m = data.message as ChatMsg;
      setPartial("");
      setMsgs((prev) => [...prev, { role: "user", text: m.text, id: m.id }]);
    } else if (type === "assistant" || type === "assistant_partial") {
      if (type === "assistant") {
        const m = data.message as ChatMsg;
        setMsgs((prev) => {
          const next = [...prev];
          if (next.length && next[next.length - 1].role === "assistant" && !next[next.length - 1].id) {
            next[next.length - 1] = {
              role: "assistant",
              text: m.text,
              id: m.id,
              schemes: (data.schemes as SchemeItem[]) || m.schemes,
            };
            return next;
          }
          return [
            ...next,
            {
              role: "assistant",
              text: m.text,
              id: m.id,
              schemes: (data.schemes as SchemeItem[]) || undefined,
            },
          ];
        });
        if (Array.isArray(data.schemes) && data.schemes.length > 0) {
          setSchemes(data.schemes as SchemeItem[]);
          setShowMatches(true);
        }
        if (typeof data.language === "string") setLang(data.language);
        // The reply text has arrived, so stop showing "thinking". If audio follows, "speaking" takes over.
        setState((s) => (s === "processing" ? (liveRef.current ? "listening" : "idle") : s));
      } else if (typeof data.text === "string") {
        setMsgs((prev) => {
          const next = [...prev];
          if (next.length && next[next.length - 1].role === "assistant" && !next[next.length - 1].id) {
            next[next.length - 1] = { ...next[next.length - 1], text: data.text as string };
            return next;
          }
          return [...next, { role: "assistant", text: data.text as string }];
        });
      }
    } else if (type === "transcript_partial") {
      if (typeof data.text === "string") setPartial(data.text);
      if (typeof data.language === "string") setLang(data.language);
      setState("listening");
    } else if (type === "hearing") {
      setState("listening");
    } else if (type === "transcript") {
      setPartial("");
      setState("processing");
    } else if (type === "processing") {
      setState("processing");
    } else if (type === "listening") {
      if (audioRef.current) return;
      setState(liveRef.current ? "listening" : "idle");
    } else if (type === "audio" && typeof data.data === "string") {
      playWavB64(data.data);
    } else if (type === "stt_error" || type === "tts_error" || type === "error") {
      announce(String(data.message || "Voice processing issue"), 6000);
      if (!audioRef.current) setState(liveRef.current ? "listening" : "idle");
    } else if (type === "cleared") {
      setMsgs([]);
      setSchemes([]);
      setPartial("");
    }
  }

  async function startMic(): Promise<boolean> {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      streamRef.current = stream;
      const ctx = new AudioContext();
      audioCtxRef.current = ctx;
      await ctx.audioWorklet.addModule("/pcm-worklet.js");
      const src = ctx.createMediaStreamSource(stream);
      const node = new AudioWorkletNode(ctx, "pcm-worklet");
      workletRef.current = node;
      node.port.onmessage = (e) => {
        if (audioRef.current) return;
        const ws = wsRef.current;
        if (ws && ws.readyState === WebSocket.OPEN) ws.send(e.data);
      };
      src.connect(node);
      const silent = ctx.createGain();
      silent.gain.value = 0;
      node.connect(silent);
      silent.connect(ctx.destination);
      return true;
    } catch {
      stopMic();
      announce("Microphone access is needed to speak with Saathi. You can still type your question.", 6500);
      return false;
    }
  }

  function stopMic() {
    workletRef.current?.disconnect();
    workletRef.current = null;
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    void audioCtxRef.current?.close().catch(() => undefined);
    audioCtxRef.current = null;
  }

  function disconnectLive() {
    stopPlayback();
    stopMic();
    const ws = wsRef.current;
    wsRef.current = null;
    ws?.close();
    setLive(false);
    setState("idle");
    setPartial("");
  }

  async function toggleLive() {
    if (live) {
      disconnectLive();
      return;
    }
    connect(true);
    const ok = await startMic();
    if (!ok) disconnectLive();
  }

  function sendText(e: FormEvent) {
    e.preventDefault();
    const t = text.trim();
    if (!t) {
      inputRef.current?.focus();
      return;
    }
    setText("");
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      setState("processing");
      ws.send(JSON.stringify({ type: "text", text: t, language: lang }));
    } else {
      // No open socket yet: connect for text-only use and send once it opens.
      pendingTextRef.current = { text: t, language: lang };
      connect(false);
    }
  }

  function newTalk() {
    const id = crypto.randomUUID();
    openedSessionRef.current = null;
    if (sessionParam) setParams({}, { replace: true });
    setSessionId(id);
    setMsgs([]);
    setSchemes([]);
    setPartial("");
    setText("");
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "new_session" }));
    }
    announce("A fresh conversation is ready.");
  }

  function focusChat() {
    inputRef.current?.focus();
    inputRef.current?.scrollIntoView({ block: "center", behavior: "smooth" });
  }

  const firstName = (user?.name || user?.username || "").trim().split(/\s+/)[0] || "friend";
  const listening = live && state === "listening";
  const langOptions = LANGUAGES.some((l) => l.code === lang) ? LANGUAGES : [...LANGUAGES, { code: lang, label: lang }];

  const micLabel = !live
    ? "Start speaking"
    : state === "processing"
      ? "Finding schemes…"
      : state === "speaking"
        ? "Saathi is speaking"
        : "Listening…";
  const micHint = !live ? "Speak in your language" : "Tap to stop";

  const caption =
    state === "processing"
      ? "Finding schemes that may fit…"
      : state === "speaking"
        ? "Saathi is speaking…"
        : partial
          ? `“${partial}”`
          : null;

  const totalMatchPages = Math.max(1, Math.ceil(schemes.length / MATCHES_PER_PAGE));
  const currentMatchPage = Math.min(matchPage, totalMatchPages);
  const visibleMatches = schemes.slice((currentMatchPage - 1) * MATCHES_PER_PAGE, currentMatchPage * MATCHES_PER_PAGE);

  return (
    <div className="desk-root">
      <div className="shell">
        <header className="topbar">
          <Link className="brand" to="/" aria-label="Sarkari Saathi home">
            <span className="brand-mark" aria-hidden="true">
              <svg {...icon}>
                <path d="M4 10v4m4-8v12m4-15v18m4-13v8m4-11v14" />
              </svg>
            </span>
            <span className="brand-text">Sarkari Saathi</span>
          </Link>

          <div className="top-actions">
            <span className="status" data-listening={String(listening)} role="status">
              <span className="status-dot" />
              <span>{STATUS_TEXT[state]}</span>
            </span>

            <label className="sr-only" htmlFor="language">
              Choose language
            </label>
            <select className="language" id="language" value={lang} onChange={(e) => setLang(e.target.value)}>
              {langOptions.map((l) => (
                <option key={l.code} value={l.code}>
                  {l.label}
                </option>
              ))}
            </select>

            <Link className="new-chat" to="/history" aria-label="Conversation history">
              <svg {...icon} strokeWidth={1.7}>
                <path d="M3 12a9 9 0 1 0 3-6.7M3 4v5h5" />
                <path d="M12 7v5l3 2" />
              </svg>
              <span>History</span>
            </Link>

            <button className="new-chat" type="button" onClick={newTalk} aria-label="Start a new conversation">
              <svg {...icon} strokeWidth={1.7}>
                <path d="M20 11a8 8 0 0 0-14.9-4M4 4v4h4" />
                <path d="M4 13a8 8 0 0 0 14.9 4M20 20v-4h-4" />
              </svg>
              <span>New conversation</span>
            </button>

            <AccountMenu />
          </div>
        </header>

        <main className="workspace">
          <aside className="conversation" id="conversation" aria-label="Conversation">
            <div className="conversation-head">
              <p className="eyebrow">Your conversation</p>
              <h1>नमस्ते, {firstName}</h1>
              <p>Tell us a little about yourself. We’ll help you find a place to start.</p>
            </div>

            <div className="messages" ref={messagesRef} aria-live="polite">
              {sessionLoading && (
                <div className="message assistant">
                  <span className="sender">Sarkari Saathi</span>
                  <div className="bubble thinking">
                    Opening your conversation<span className="typing-dots" />
                  </div>
                </div>
              )}

              {!sessionLoading && msgs.length === 0 && !partial && (
                <div className="message assistant">
                  <span className="sender">Sarkari Saathi</span>
                  <div className="bubble">
                    Welcome. You can speak naturally or type a question. We’ll take it one step at a time.
                  </div>
                  <span className="starter">
                    <svg {...icon}>
                      <path d="M12 3v18M3 12h18" />
                    </svg>{" "}
                    Start wherever you like
                  </span>
                </div>
              )}

              {msgs.map((m, i) => (
                <div key={m.id || i} className={`message ${m.role}`}>
                  <span className="sender">{m.role === "assistant" ? "Sarkari Saathi" : "You"}</span>
                  <div className="bubble">{m.text}</div>
                </div>
              ))}

              {partial && (
                <div className="message user">
                  <span className="sender">Hearing…</span>
                  <div className="bubble partial">{partial}</div>
                </div>
              )}

              {state === "processing" && (
                <div className="message assistant">
                  <span className="sender">Sarkari Saathi</span>
                  <div className="bubble thinking">
                    Looking for matching schemes<span className="typing-dots" />
                  </div>
                </div>
              )}
            </div>

            {schemes.length > 0 && (
              <section className="matches" aria-label="Matched schemes">
                <div className="matches-head">
                  <h2>Possible schemes ({schemes.length})</h2>
                  <button
                    type="button"
                    className="matches-toggle"
                    aria-expanded={showMatches}
                    onClick={() => setShowMatches((v) => !v)}
                  >
                    {showMatches ? "Hide" : "Show"}
                  </button>
                </div>
                {showMatches && (
                  <>
                    <ul className="matches-list">
                      {visibleMatches.map((s) => (
                        <li key={s.id}>
                          <SchemeCard scheme={s} compact />
                        </li>
                      ))}
                    </ul>
                    <Pagination
                      compact
                      page={currentMatchPage}
                      totalPages={totalMatchPages}
                      onPageChange={setMatchPage}
                      label="Matched scheme pages"
                    />
                  </>
                )}
              </section>
            )}

            <form className="composer" onSubmit={sendText} aria-label="Send a message">
              <input
                ref={inputRef}
                type="text"
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="Type your answer…"
                autoComplete="off"
                aria-label="Type your answer"
                maxLength={1000}
              />
              <button className="send" type="submit" aria-label="Send message">
                <svg {...icon}>
                  <path d="m22 2-7 20-4-9-9-4Z" />
                  <path d="M22 2 11 13" />
                </svg>
              </button>
            </form>
          </aside>

          <section className="stage" aria-label="Voice guide">
            <div className="stage-heading">
              <div>
                <p className="eyebrow">A guide in your language</p>
                <h2>Let’s find your next step.</h2>
                <p className="caption">A simple conversation can make public support easier to find.</p>
              </div>
              <button type="button" className="help-link" onClick={focusChat}>
                Prefer to type? Use the chat&nbsp; ↓
              </button>
            </div>

            <div className="voice-scene">
              <img
                className="scene-photo"
                src="/sarkari-saathi-community.jpg"
                alt="A community worker helping an older woman use a phone"
                width={1600}
                height={1200}
              />
              <div className="scene-overlay" />
              <div className="scene-top">
                <span className="scene-label">
                  <svg {...icon} strokeLinejoin={undefined}>
                    <path d="M4 10v4m4-8v12m4-15v18m4-13v8m4-11v14" />
                  </svg>{" "}
                  Voice guide
                </span>
                <span className="scene-secure">
                  <svg {...icon}>
                    <rect x="4" y="10" width="16" height="11" rx="2" />
                    <path d="M8 10V7a4 4 0 0 1 8 0v3" />
                  </svg>{" "}
                  Your details stay yours
                </span>
              </div>
              <div className="scene-content">
                <p className="welcome">आपकी बात, आपकी भाषा</p>
                <h3>
                  Start speaking.
                  <br />
                  We’re listening.
                </h3>
                <p>
                  Tell us about your family, work, or what you need help with. There’s no form to figure out.
                </p>
                {caption && (
                  <p className="scene-caption" aria-live="polite">
                    {caption}
                  </p>
                )}
              </div>
              <div className="scene-bottom">
                <div className="official-note">
                  <svg {...icon} strokeWidth={1.9}>
                    <path d="m9 12 2 2 4-4" />
                    <path d="M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11Z" />
                  </svg>
                  <span>A first guide, not an eligibility decision. Always confirm details with official sources.</span>
                </div>
                <div className="voice-control">
                  <button
                    className="mic-button"
                    type="button"
                    onClick={toggleLive}
                    aria-label={live ? "Stop speaking" : "Start speaking"}
                    aria-pressed={live}
                    data-listening={String(listening)}
                  >
                    {live ? (
                      <svg {...icon}>
                        <rect x="6" y="6" width="12" height="12" rx="2" />
                      </svg>
                    ) : (
                      <svg {...icon}>
                        <rect x="9" y="2" width="6" height="12" rx="3" />
                        <path d="M5 10v2a7 7 0 0 0 14 0v-2M12 19v3m-4 0h8" />
                      </svg>
                    )}
                  </button>
                  <div className="control-copy">
                    <strong>{micLabel}</strong>
                    <span>{micHint}</span>
                  </div>
                  <button
                    type="button"
                    className="mute-btn"
                    onClick={() => {
                      const next = !isMuted;
                      setIsMuted(next);
                      if (next) stopPlayback();
                    }}
                    aria-pressed={isMuted}
                    aria-label={isMuted ? "Unmute spoken replies" : "Mute spoken replies"}
                  >
                    {isMuted ? "Unmute" : "Mute"}
                  </button>
                </div>
              </div>
            </div>

            <div className="below-scene">
              <span className="secure-copy">
                <svg {...icon}>
                  <path d="M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11Z" />
                  <path d="m9 12 2 2 4-4" />
                </svg>{" "}
                Your information is for guidance only.
              </span>
              <span>Possible matches link to official scheme details.</span>
            </div>
          </section>
        </main>
      </div>

      <div className={`toast${toast ? " show" : ""}`} role="status" aria-live="polite">
        {toast}
      </div>
    </div>
  );
}
