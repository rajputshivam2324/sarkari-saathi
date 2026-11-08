import { useEffect, useRef } from "react";

interface AudioVisualizerProps {
  state: "idle" | "listening" | "processing" | "speaking";
  barCount?: number;
}

export function AudioVisualizer({ state, barCount = 28 }: AudioVisualizerProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animId: number;
    let t = 0;

    const render = () => {
      t += 0.08;
      const w = canvas.width;
      const h = canvas.height;
      ctx.clearRect(0, 0, w, h);

      const barWidth = w / barCount - 2;
      const mid = h / 2;

      for (let i = 0; i < barCount; i++) {
        let height = 4;
        if (state === "speaking") {
          height = Math.sin(t + i * 0.4) * Math.cos(t * 0.5 + i * 0.2) * (h * 0.42) + (h * 0.15);
        } else if (state === "listening") {
          height = Math.sin(t * 1.5 + i * 0.6) * (h * 0.25) + (h * 0.08);
        } else if (state === "processing") {
          height = Math.sin(t * 2 + i * 0.8) * (h * 0.15) + (h * 0.06);
        } else {
          height = Math.sin(t * 0.5 + i * 0.2) * 3 + 4;
        }

        height = Math.max(3, Math.abs(height));

        const x = i * (barWidth + 2);
        const y = mid - height / 2;

        const grad = ctx.createLinearGradient(0, y, 0, y + height);
        if (state === "speaking") {
          grad.addColorStop(0, "#38bdf8");
          grad.addColorStop(1, "#818cf8");
        } else if (state === "listening") {
          grad.addColorStop(0, "#34d399");
          grad.addColorStop(1, "#059669");
        } else if (state === "processing") {
          grad.addColorStop(0, "#fbbf24");
          grad.addColorStop(1, "#f59e0b");
        } else {
          grad.addColorStop(0, "rgba(148, 163, 184, 0.4)");
          grad.addColorStop(1, "rgba(148, 163, 184, 0.2)");
        }

        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.roundRect(x, y, barWidth, height, 2);
        ctx.fill();
      }

      animId = requestAnimationFrame(render);
    };

    render();

    return () => {
      cancelAnimationFrame(animId);
    };
  }, [state, barCount]);

  return <canvas ref={canvasRef} width={240} height={40} className="audio-visualizer-canvas" />;
}
