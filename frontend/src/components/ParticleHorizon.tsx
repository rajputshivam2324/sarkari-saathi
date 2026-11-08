import { useEffect, useRef } from "react";

interface ParticleHorizonProps {
  intensity?: "idle" | "listening" | "processing" | "speaking";
  height?: number;
}

export function ParticleHorizon({ intensity = "idle", height = 240 }: ParticleHorizonProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animId: number;
    let width = (canvas.width = canvas.parentElement?.clientWidth || window.innerWidth);
    let h = (canvas.height = height);

    const onResize = () => {
      if (!canvas) return;
      width = canvas.width = canvas.parentElement?.clientWidth || window.innerWidth;
      h = canvas.height = height;
    };
    window.addEventListener("resize", onResize);

    // Grid configuration
    const cols = 55;
    const rows = 28;
    let time = 0;

    const render = () => {
      time += intensity === "speaking" ? 0.035 : intensity === "listening" ? 0.025 : 0.012;
      ctx.clearRect(0, 0, width, h);

      const fov = 320;
      const camY = -70;
      const camZ = -140;

      const amp =
        intensity === "speaking"
          ? 22
          : intensity === "listening"
            ? 16
            : intensity === "processing"
              ? 18
              : 8;

      const speed = intensity === "processing" ? 2.5 : 1.0;

      // Project 3D terrain grid into 2D canvas
      const points: { x: number; y: number; z: number; px: number; py: number; alpha: number }[][] = [];

      for (let r = 0; r < rows; r++) {
        points[r] = [];
        const z = (r * 18) + 80;
        const depthRatio = (z - camZ) / 600;

        for (let c = 0; c < cols; c++) {
          const x = (c - cols / 2) * 28;
          // Undulating cyber terrain with radial curvature
          const distFromCenter = Math.sqrt(x * x + z * z);
          const curvature = Math.pow(distFromCenter / 300, 2) * 14;

          const wave =
            Math.sin(c * 0.25 + time * speed) * Math.cos(r * 0.28 + time * speed) * amp +
            Math.sin(distFromCenter * 0.03 - time * 1.5) * (amp * 0.4);

          const y = wave - curvature;

          const scale = fov / (fov + z - camZ);
          const px = width / 2 + x * scale;
          const py = h - (y - camY) * scale - 20;
          const alpha = Math.max(0, Math.min(1, 1 - depthRatio * 1.1));

          points[r][c] = { x, y, z, px, py, alpha };
        }
      }

      // Draw grid lines
      ctx.lineWidth = 1;
      for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
          const p = points[r][c];
          if (p.alpha <= 0.02) continue;

          // Horizontal connect
          if (c < cols - 1) {
            const pRight = points[r][c + 1];
            ctx.beginPath();
            ctx.moveTo(p.px, p.py);
            ctx.lineTo(pRight.px, pRight.py);
            const lineAlpha = ((p.alpha + pRight.alpha) / 2) * 0.22;
            const hue =
              intensity === "speaking"
                ? "56, 189, 248" // cyan/sky
                : intensity === "listening"
                  ? "52, 211, 153" // emerald
                  : intensity === "processing"
                    ? "251, 191, 36" // amber
                    : "148, 163, 184"; // slate
            ctx.strokeStyle = `rgba(${hue}, ${lineAlpha})`;
            ctx.stroke();
          }

          // Depth connect
          if (r < rows - 1) {
            const pDown = points[r + 1][c];
            ctx.beginPath();
            ctx.moveTo(p.px, p.py);
            ctx.lineTo(pDown.px, pDown.py);
            const lineAlpha = ((p.alpha + pDown.alpha) / 2) * 0.18;
            const hue =
              intensity === "speaking"
                ? "56, 189, 248"
                : intensity === "listening"
                  ? "52, 211, 153"
                  : intensity === "processing"
                    ? "251, 191, 36"
                    : "148, 163, 184";
            ctx.strokeStyle = `rgba(${hue}, ${lineAlpha})`;
            ctx.stroke();
          }

          // Node points
          if (r % 2 === 0 && c % 2 === 0 && p.alpha > 0.15) {
            ctx.beginPath();
            ctx.arc(p.px, p.py, 1.2, 0, Math.PI * 2);
            const dotHue =
              intensity === "speaking"
                ? "186, 230, 253"
                : intensity === "listening"
                  ? "167, 243, 208"
                  : intensity === "processing"
                    ? "253, 230, 138"
                    : "226, 232, 240";
            ctx.fillStyle = `rgba(${dotHue}, ${p.alpha * 0.65})`;
            ctx.fill();
          }
        }
      }

      // Top soft gradient fade to mask horizon
      const grad = ctx.createLinearGradient(0, 0, 0, h);
      grad.addColorStop(0, "rgba(8, 10, 14, 1)");
      grad.addColorStop(0.35, "rgba(8, 10, 14, 0.4)");
      grad.addColorStop(1, "rgba(8, 10, 14, 0)");
      ctx.fillStyle = grad;
      ctx.fillRect(0, 0, width, h);

      animId = requestAnimationFrame(render);
    };

    render();

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener("resize", onResize);
    };
  }, [intensity, height]);

  return (
    <div className="particle-horizon-wrapper" style={{ height, pointerEvents: "none" }}>
      <canvas ref={canvasRef} className="particle-horizon-canvas" />
    </div>
  );
}
