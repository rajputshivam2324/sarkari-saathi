/**
 * Downsample to 16 kHz mono Int16 and emit 1024-byte PCM frames for Gnani Prisma.
 */
class PcmWorkletProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this._buf = [];
    this._ratio = sampleRate / 16000;
    this._acc = 0;
  }

  process(inputs) {
    const input = inputs[0]?.[0];
    if (!input) return true;

    for (let i = 0; i < input.length; i++) {
      this._acc += 1;
      if (this._acc >= this._ratio) {
        this._acc -= this._ratio;
        let s = input[i];
        s = Math.max(-1, Math.min(1, s));
        this._buf.push((s < 0 ? s * 0x8000 : s * 0x7fff) | 0);
      }
    }

    // 512 samples = 1024 bytes
    while (this._buf.length >= 512) {
      const frame = this._buf.splice(0, 512);
      const ab = new ArrayBuffer(1024);
      const view = new Int16Array(ab);
      for (let i = 0; i < 512; i++) view[i] = frame[i];
      this.port.postMessage(ab, [ab]);
    }
    return true;
  }
}

registerProcessor("pcm-worklet", PcmWorkletProcessor);
