"""Live duplex voice WebSocket — patient turn-taking, half-duplex TTS."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import socket
import time
import uuid
from collections import deque
from typing import Any

import jwt
import websockets
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from websockets.exceptions import ConnectionClosed

from app.config import get_settings
from app.db import SessionLocal
from app.models import User
from app.services.agent import handle_utterance
from app.services.chat_history import HistoryWriter, clear_session, load_history, make_message
from app.services.gnani import GnaniError, synthesize_speech
from app.services.languages import greeting, normalize_lang

logger = logging.getLogger(__name__)
router = APIRouter(tags=["live"])
settings = get_settings()

FRAME = 1024
# Wait this long after the *last* STT segment before answering (lets people pause mid-sentence)
UTTERANCE_GAP_SEC = 1.6
# After client finishes local TTS playback, keep STT muted briefly (echo / AGC settle)
TTS_HANGOVER_SEC = 1.0
# Safety: if client never reports playback end, unmute after this
TTS_SAFETY_SEC = 45.0
# Drop tiny fragments (noise / coughs)
MIN_UTTERANCE_CHARS = 4


async def _open_stt(url: str, headers: dict[str, str]) -> "websockets.ClientConnection":
    """Open the Gnani realtime speech-to-text socket.

    api.vachana.ai advertises an IPv6 address first. On networks that advertise IPv6 but cannot
    route it (common on home Wi-Fi and some mobile networks) the default connect hangs for the
    whole timeout and never falls back, which silently kills live voice. So try IPv4 first (about
    0.4 s when it works) and use the library default only if that fails at the network level.
    An authentication error is raised immediately: retrying cannot fix it.
    """
    last: BaseException | None = None
    for kwargs, timeout in (({"family": socket.AF_INET}, 8), ({}, 20)):
        try:
            return await websockets.connect(
                url,
                additional_headers=headers,
                max_size=8 * 1024 * 1024,
                open_timeout=timeout,
                **kwargs,
            )
        except (OSError, TimeoutError, asyncio.TimeoutError) as exc:
            last = exc
            logger.warning("STT connect attempt failed (%s): %s", "IPv4" if kwargs else "default", exc)
    assert last is not None
    raise last


class _SttLink:
    """The Gnani speech-to-text socket, which reconnects by itself.

    Gnani hangs up (close code 1001, "idle_timeout") when it receives no audio for a while. That happens by
    design here: while the assistant thinks and speaks, no audio is sent so it cannot hear itself. Without this
    class the next audio frame hit a dead socket and ended the whole live session.

    - The first connection is opened by start(); if that fails the error is raised, as before.
    - When the socket is found closed, the next send() reconnects (with a short back-off) and the frames that
      arrive meanwhile are kept, up to about 3 s, and replayed in order, so the start of the person's
      speech is not clipped.
    - If reconnecting keeps failing, on_fatal() is told once and audio is dropped.
    """

    MAX_PENDING_FRAMES = 100            # about 3 s of 16 kHz audio in 1024-byte frames
    RECONNECT_ATTEMPTS = 5

    def __init__(self, url: str, headers: dict[str, str], on_message, on_fatal) -> None:
        self._url = url
        self._headers = headers
        self._on_message = on_message
        self._on_fatal = on_fatal
        self._ws: "websockets.ClientConnection | None" = None
        self._reader: "asyncio.Task | None" = None
        self._connecting: "asyncio.Task | None" = None
        self._pending: deque[bytes] = deque(maxlen=self.MAX_PENDING_FRAMES)
        self._closed = False
        self._gave_up = False

    async def start(self) -> None:
        ws = await _open_stt(self._url, self._headers)
        self._attach(ws)

    def _attach(self, ws: "websockets.ClientConnection") -> None:
        self._ws = ws
        self._reader = asyncio.create_task(self._read(ws))

    async def _read(self, ws: "websockets.ClientConnection") -> None:
        try:
            async for raw in ws:
                try:
                    await self._on_message(raw)
                except Exception as exc:       # a bad message must not end the stream
                    logger.warning("STT message handler failed: %s", exc)
        except ConnectionClosed:
            pass
        finally:
            if self._ws is ws:
                self._ws = None                # reconnect on the next send()
            rc = ws.close_code
            logger.info("STT socket closed (code=%s reason=%s)", rc, getattr(ws, "close_reason", ""))

    async def send(self, frame: bytes) -> None:
        if self._closed or self._gave_up:
            return
        ws = self._ws
        if ws is not None and not self._pending:
            try:
                await ws.send(frame)
                return
            except ConnectionClosed:
                if self._ws is ws:
                    self._ws = None
        self._pending.append(frame)           # kept in order until a connection is ready
        if self._ws is None and not (self._connecting and not self._connecting.done()):
            self._connecting = asyncio.create_task(self._reconnect())

    async def _reconnect(self) -> None:
        delay = 0.3
        for attempt in range(1, self.RECONNECT_ATTEMPTS + 1):
            if self._closed:
                return
            try:
                ws = await _open_stt(self._url, self._headers)
            except Exception as exc:
                logger.warning("STT reconnect %d/%d failed: %s", attempt, self.RECONNECT_ATTEMPTS, exc)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 3.0)
                continue
            self._attach(ws)
            logger.info("STT reconnected")
            while self._pending and self._ws is ws:
                frame = self._pending.popleft()
                try:
                    await ws.send(frame)
                except ConnectionClosed:
                    self._pending.appendleft(frame)
                    break
            return
        self._gave_up = True
        self._pending.clear()
        try:
            await self._on_fatal("Speech recognition lost its connection. Please reconnect the microphone.")
        except Exception:
            pass

    async def close(self) -> None:
        self._closed = True
        for t in (self._connecting, self._reader):
            if t and not t.done():
                t.cancel()
        for t in (self._connecting, self._reader):
            if t:
                try:
                    await t
                except (asyncio.CancelledError, Exception):
                    pass
        ws, self._ws = self._ws, None
        if ws is not None:
            try:
                await asyncio.wait_for(ws.close(), timeout=2)
            except Exception:
                pass

    async def __aenter__(self) -> "_SttLink":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()


def _user_from_token(token: str) -> User | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        uid = payload.get("sub")
        if not uid:
            return None
        db = SessionLocal()
        try:
            return db.get(User, uuid.UUID(uid))
        finally:
            db.close()
    except Exception:
        return None


async def _send(ws: WebSocket, payload: dict[str, Any]) -> None:
    await ws.send_json(payload)


async def _tts_b64(text: str, language: str) -> tuple[str | None, str | None]:
    """Synthesize speech. Never raises: returns (base64_wav, None) or (None, error)."""
    try:
        wav = await synthesize_speech(text, language=language)
        return base64.b64encode(wav).decode("ascii"), None
    except GnaniError as exc:
        return None, str(exc)


async def _speak_and_send(
    client: WebSocket,
    text: str,
    language: str,
    synth: "asyncio.Task[tuple[str | None, str | None]] | None" = None,
) -> bool:
    """Push the reply audio. Returns True if audio was sent (client owns playback mute).

    `synth` lets the caller start synthesis early so it overlaps with database writes.
    """
    await _send(client, {"type": "assistant_partial", "text": text, "language": language})
    b64, err = await (synth if synth is not None else _tts_b64(text, language))
    if b64 is None:
        logger.warning("TTS failed: %s", err)
        await _send(client, {"type": "tts_error", "message": err or "speech synthesis failed"})
        return False
    await _send(client, {"type": "audio", "format": "wav", "data": b64, "language": language})
    return True


async def _handle_user_text(
    client: WebSocket,
    *,
    user_id: uuid.UUID,
    session_id: str,
    text: str,
    language: str | None,
    history: list[dict[str, Any]],
    writer: HistoryWriter,
) -> tuple[list[dict[str, Any]], bool]:
    """Returns (history, audio_sent). The database is never waited on: see HistoryWriter."""
    text = (text or "").strip()
    if not text:
        return history, False

    lang = normalize_lang(language)

    user_msg = make_message("user", text, lang)
    writer.save(user_id, session_id, user_msg)
    history = [*history, user_msg]
    await _send(client, {"type": "user", "message": user_msg})

    result = await handle_utterance(text, history=history, language=lang)
    reply = result["reply_text"]
    schemes = result.get("schemes") or []
    lang = result.get("language") or lang

    synth = asyncio.create_task(_tts_b64(reply, lang))  # speech starts while we reply on screen
    try:
        asst = make_message("assistant", reply, lang, schemes)
        writer.save(user_id, session_id, asst)
        history = [*history, asst]
        await _send(
            client,
            {
                "type": "assistant",
                "message": asst,
                "schemes": schemes,
                "ready": result.get("ready"),
                "language": lang,
                "mode": result.get("mode"),
                "models": {
                    "stt": "prisma-v3.0",
                    "tts": "timbre-v3.0",
                    "llm": result.get("source") == "llm",
                },
            },
        )
        audio_sent = await _speak_and_send(client, reply, lang, synth)
    except BaseException:
        synth.cancel()
        raise
    return history, audio_sent


@router.websocket("/ws/live")
async def live_voice(websocket: WebSocket) -> None:
    token = websocket.query_params.get("token") or ""
    session_id = websocket.query_params.get("session_id") or str(uuid.uuid4())
    user = await asyncio.to_thread(_user_from_token, token)
    if user is None:
        await websocket.close(code=4401)
        return

    await websocket.accept()
    user_id = user.id
    language = "hi-IN"
    history: list[dict[str, Any]] = []
    writer = HistoryWriter()

    db = SessionLocal()
    try:
        history = await load_history(db, user_id, session_id)
    finally:
        db.close()

    await _send(
        websocket,
        {
            "type": "ready",
            "session_id": session_id,
            "history": history,
            "languages": [
                "hi-IN",
                "en-IN",
                "ta-IN",
                "te-IN",
                "kn-IN",
                "ml-IN",
                "mr-IN",
                "pa-IN",
                "bn-IN",
                "gu-IN",
            ],
            "greeting": greeting(language),
        },
    )

    # Text greeting only — do NOT speak until the user has talked (stops barge-in on open)
    if not history:
        greet = greeting(language)
        asst = make_message("assistant", greet, language)
        writer.save(user_id, session_id, asst)
        history = [asst]
        await _send(websocket, {"type": "assistant", "message": asst, "schemes": []})

    # Patient conversation VAD — wait for a real pause before closing the utterance
    stt_headers = {
        "x-api-key-id": settings.gnani_api_key,
        "model": settings.gnani_stt_model,
        "language_code": settings.gnani_stt_language,
        "x-sample-rate": "16000",
        "format": "transcribe",
        "x-vad-threshold": "0.62",
        "x-min-silence-ms": "1600",
        "x-min-speech-ms": "250",
        "x-min-segment-ms": "300",
    }

    pcm_buf = bytearray()
    processing = False
    speaking = False
    speak_until = 0.0
    pending_parts: list[str] = []
    pending_lang = language
    flush_task: asyncio.Task | None = None
    safety_task: asyncio.Task | None = None
    mute_upstream = False  # half-duplex: stop feeding STT while TTS plays

    def arm_playback_safety() -> None:
        """Unmute if the browser never reports speaking:false (tab crash, blocked autoplay)."""
        nonlocal safety_task, speaking, mute_upstream, speak_until

        async def _safety() -> None:
            nonlocal speaking, mute_upstream, speak_until
            await asyncio.sleep(TTS_SAFETY_SEC)
            if speaking or mute_upstream:
                logger.warning("TTS safety unmute session=%s", session_id)
                speaking = False
                mute_upstream = False
                speak_until = time.monotonic() + TTS_HANGOVER_SEC
                try:
                    await _send(websocket, {"type": "listening"})
                except Exception:
                    pass

        if safety_task and not safety_task.done():
            safety_task.cancel()
        safety_task = asyncio.create_task(_safety())

    async def flush_utterance() -> None:
        nonlocal processing, history, pending_parts, pending_lang, language, speak_until, mute_upstream, speaking
        if processing or speaking or not pending_parts:
            return
        text = " ".join(pending_parts).strip()
        pending_parts = []
        if len(text) < MIN_UTTERANCE_CHARS:
            await _send(websocket, {"type": "listening"})
            return
        if time.monotonic() < speak_until:
            return

        processing = True
        mute_upstream = True
        language = normalize_lang(pending_lang)
        await _send(
            websocket,
            {
                "type": "transcript",
                "text": text,
                "language": language,
                "final": True,
            },
        )
        try:
            history, audio_sent = await _handle_user_text(
                websocket,
                user_id=user_id,
                session_id=session_id,
                text=text,
                language=language,
                history=history,
                writer=writer,
            )
            if audio_sent:
                # Stay muted until DeskPage reports local playback finished
                speaking = True
                mute_upstream = True
                arm_playback_safety()
            else:
                speak_until = time.monotonic() + TTS_HANGOVER_SEC
                mute_upstream = False
                await _send(websocket, {"type": "listening"})
        except Exception:
            mute_upstream = False
            speaking = False
            await _send(websocket, {"type": "listening"})
            raise
        finally:
            processing = False

    def schedule_flush() -> None:
        nonlocal flush_task

        async def _wait() -> None:
            await asyncio.sleep(UTTERANCE_GAP_SEC)
            await flush_utterance()

        if flush_task and not flush_task.done():
            flush_task.cancel()
        flush_task = asyncio.create_task(_wait())

    async def on_stt_message(raw: Any) -> None:
        nonlocal language, pending_lang, speaking
        try:
            msg = json.loads(raw)
        except Exception:
            return
        kind = msg.get("type")
        if kind == "connected":
            await _send(websocket, {"type": "listening", "detail": msg})
        elif kind == "processing":
            # Show "hearing you" — do not answer yet
            await _send(websocket, {"type": "hearing"})
        elif kind == "transcript":
            # Ignore while we talk or process (half-duplex + no self-echo)
            if processing or speaking or time.monotonic() < speak_until:
                return
            text = (msg.get("text") or msg.get("transcript") or "").strip()
            if not text:
                return
            detected = msg.get("detected_language_code") or language
            pending_lang = normalize_lang(detected)
            # Accumulate segments — person may pause mid-thought
            if pending_parts and text.lower() in " ".join(pending_parts).lower():
                pass
            else:
                pending_parts.append(text)
            await _send(
                websocket,
                {
                    "type": "transcript_partial",
                    "text": " ".join(pending_parts),
                    "language": pending_lang,
                },
            )
            schedule_flush()
        elif kind == "error":
            await _send(
                websocket,
                {
                    "type": "stt_error",
                    "message": msg.get("message") or str(msg),
                },
            )

    async def on_stt_lost(message: str) -> None:
        await _send(websocket, {"type": "stt_error", "message": message})

    try:
        stt = _SttLink(settings.gnani_stt_ws_url, stt_headers, on_stt_message, on_stt_lost)
        await stt.start()
        async with stt as stt_ws:

            try:
                while True:
                    message = await websocket.receive()
                    if message.get("type") == "websocket.disconnect":
                        break

                    if "bytes" in message and message["bytes"] is not None:
                        if mute_upstream or speaking or processing:
                            pcm_buf.clear()
                            continue
                        chunk = message["bytes"]
                        pcm_buf.extend(chunk)
                        while len(pcm_buf) >= FRAME:
                            frame = bytes(pcm_buf[:FRAME])
                            del pcm_buf[:FRAME]
                            try:
                                await stt_ws.send(frame)
                            except ConnectionClosed:
                                raise

                    elif "text" in message and message["text"] is not None:
                        try:
                            data = json.loads(message["text"])
                        except json.JSONDecodeError:
                            continue
                        typ = data.get("type")
                        if typ == "text":
                            if processing or speaking:
                                continue
                            # Cancel pending voice utterance — typed message wins
                            if flush_task and not flush_task.done():
                                flush_task.cancel()
                            pending_parts.clear()
                            processing = True
                            mute_upstream = True
                            try:
                                history, audio_sent = await _handle_user_text(
                                    websocket,
                                    user_id=user_id,
                                    session_id=session_id,
                                    text=data.get("text") or "",
                                    language=data.get("language") or language,
                                    history=history,
                                    writer=writer,
                                )
                                if audio_sent:
                                    speaking = True
                                    mute_upstream = True
                                    arm_playback_safety()
                                else:
                                    speak_until = time.monotonic() + TTS_HANGOVER_SEC
                                    mute_upstream = False
                                    await _send(websocket, {"type": "listening"})
                            except Exception:
                                mute_upstream = False
                                speaking = False
                                await _send(websocket, {"type": "listening"})
                                raise
                            finally:
                                processing = False
                        elif typ == "speaking":
                            # Client reports local playback — this is the real half-duplex gate
                            active = bool(data.get("active"))
                            speaking = active
                            if active:
                                mute_upstream = True
                                pcm_buf.clear()
                                if flush_task and not flush_task.done():
                                    flush_task.cancel()
                                arm_playback_safety()
                            else:
                                if safety_task and not safety_task.done():
                                    safety_task.cancel()
                                speak_until = time.monotonic() + TTS_HANGOVER_SEC
                                mute_upstream = False
                                pcm_buf.clear()
                                await _send(websocket, {"type": "listening"})
                        elif typ == "ping":
                            await _send(websocket, {"type": "pong"})
                        elif typ == "new_session":
                            if flush_task and not flush_task.done():
                                flush_task.cancel()
                            if safety_task and not safety_task.done():
                                safety_task.cancel()
                            pending_parts.clear()
                            speaking = False
                            mute_upstream = False
                            session_id = str(uuid.uuid4())
                            greet = greeting(language)
                            asst = make_message("assistant", greet, language)
                            writer.save(user_id, session_id, asst)
                            history = [asst]
                            await _send(
                                websocket,
                                {
                                    "type": "ready",
                                    "session_id": session_id,
                                    "history": history,
                                    "greeting": greet,
                                },
                            )
                        elif typ == "clear":
                            if flush_task and not flush_task.done():
                                flush_task.cancel()
                            pending_parts.clear()
                            await writer.flush()  # pending saves must land first, or they would come back
                            db = SessionLocal()
                            try:
                                await clear_session(db, user_id, session_id)
                            finally:
                                db.close()
                            history = []
                            await _send(
                                websocket, {"type": "cleared", "session_id": session_id}
                            )
            finally:
                if flush_task and not flush_task.done():
                    flush_task.cancel()
                if safety_task and not safety_task.done():
                    safety_task.cancel()

    except WebSocketDisconnect:
        logger.info("Client disconnected session=%s", session_id)
    except Exception as exc:
        logger.exception("Live voice error: %s", exc)
        try:
            await _send(websocket, {"type": "error", "message": str(exc)})
        except Exception:
            pass
    finally:
        # Never lose a message because the person closed the tab right after a reply.
        await writer.flush()
