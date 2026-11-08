const API = import.meta.env.VITE_API_URL ?? "/api";

export type User = {
  id: string;
  username: string;
  name: string | null;
};

export type SchemeMatch = {
  id: string;
  name: string;
  name_hi: string;
  category: string;
  description: string;
  description_hi: string;
  official_url: string;
  score?: number;
};

export type TurnResponse = {
  transcript: string;
  detected_language_code?: string | null;
  follow_up?: string | null;
  reply_text: string;
  schemes: SchemeMatch[];
  context?: Record<string, unknown>;
  ready?: boolean;
  models: {
    stt?: string | null;
    tts?: string | null;
    voice?: string | null;
  };
  evon_ran: boolean;
  reply_audio_b64?: string | null;
};

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function authHeaders(token: string | null): HeadersInit {
  const h: Record<string, string> = {};
  if (token) h.Authorization = `Bearer ${token}`;
  return h;
}

async function readError(res: Response): Promise<string> {
  try {
    const data = await res.json();
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail)) {
      return data.detail
        .map((d: { msg?: string }) => d.msg ?? JSON.stringify(d))
        .join(", ");
    }
    return JSON.stringify(data);
  } catch {
    return res.statusText || "Request failed";
  }
}

export type CatalogScheme = {
  id: string;
  name: string;
  name_hi?: string;
  short_title?: string;
  slug?: string;
  official_url: string;
  description?: string;
  category?: string;
  source?: string;
};

export type SchemePage = {
  total: number;
  offset: number;
  limit: number;
  query: string | null;
  schemes: CatalogScheme[];
};

export async function listSchemes(
  opts: { page: number; pageSize: number; q?: string },
  signal?: AbortSignal,
): Promise<SchemePage> {
  const params = new URLSearchParams({
    limit: String(opts.pageSize),
    offset: String((Math.max(1, opts.page) - 1) * opts.pageSize),
  });
  if (opts.q?.trim()) params.set("q", opts.q.trim());
  const res = await fetch(`${API}/schemes?${params.toString()}`, { signal });
  if (!res.ok) throw new ApiError(await readError(res), res.status);
  return res.json();
}

export type ChatSessionSummary = {
  session_id: string;
  title: string;
  language: string | null;
  started_at: string | null;
  last_at: string | null;
  message_count: number;
};

export type ChatSessionPage = {
  total: number;
  offset: number;
  limit: number;
  sessions: ChatSessionSummary[];
};

export type ChatMessageDto = {
  id: string;
  role: "user" | "assistant";
  text: string;
  language: string | null;
  schemes: SchemeMatch[] | null;
  created_at: string | null;
};

export async function listSessions(
  token: string,
  opts: { page: number; pageSize: number },
  signal?: AbortSignal,
): Promise<ChatSessionPage> {
  const params = new URLSearchParams({
    limit: String(opts.pageSize),
    offset: String((Math.max(1, opts.page) - 1) * opts.pageSize),
  });
  const res = await fetch(`${API}/chat/sessions?${params.toString()}`, {
    headers: authHeaders(token),
    signal,
  });
  if (!res.ok) throw new ApiError(await readError(res), res.status);
  return res.json();
}

export async function getSession(
  token: string,
  sessionId: string,
  signal?: AbortSignal,
): Promise<{ session_id: string; messages: ChatMessageDto[] }> {
  const res = await fetch(`${API}/chat/sessions/${encodeURIComponent(sessionId)}`, {
    headers: authHeaders(token),
    signal,
  });
  if (!res.ok) throw new ApiError(await readError(res), res.status);
  return res.json();
}

export async function deleteSession(token: string, sessionId: string): Promise<void> {
  const res = await fetch(`${API}/chat/sessions/${encodeURIComponent(sessionId)}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
  if (!res.ok) throw new ApiError(await readError(res), res.status);
}

export async function register(
  username: string,
  password: string,
  name?: string,
): Promise<{ access_token: string; user: User }> {
  const res = await fetch(`${API}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password, name: name || null }),
  });
  if (!res.ok) throw new ApiError(await readError(res), res.status);
  return res.json();
}

export async function login(
  username: string,
  password: string,
): Promise<{ access_token: string; user: User }> {
  const res = await fetch(`${API}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) throw new ApiError(await readError(res), res.status);
  return res.json();
}

export async function me(token: string): Promise<User> {
  const res = await fetch(`${API}/auth/me`, { headers: authHeaders(token) });
  if (!res.ok) throw new ApiError(await readError(res), res.status);
  return res.json();
}

export async function voiceTurn(
  token: string,
  opts: { audio?: Blob; text?: string; context?: Record<string, unknown> },
): Promise<TurnResponse> {
  const form = new FormData();
  if (opts.audio) form.append("audio", opts.audio, "speech.webm");
  if (opts.text) form.append("text", opts.text);
  if (opts.context) form.append("context", JSON.stringify(opts.context));
  const res = await fetch(`${API}/voice/turn`, {
    method: "POST",
    headers: authHeaders(token),
    body: form,
  });
  if (!res.ok) throw new ApiError(await readError(res), res.status);
  return res.json();
}

export function playBase64Wav(b64: string): HTMLAudioElement {
  const audio = new Audio(`data:audio/wav;base64,${b64}`);
  void audio.play();
  return audio;
}
