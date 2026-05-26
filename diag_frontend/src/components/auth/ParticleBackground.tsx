import { useEffect, useRef } from 'react';

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  radius: number;
  alpha: number;
}

const PARTICLE_COUNT = 80;
const CONNECTION_DIST = 150;
const MOUSE_ATTRACT_RADIUS = 180;
const MOUSE_ATTRACT_FORCE = 0.015;

export default function ParticleBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let w = window.innerWidth;
    let h = window.innerHeight;
    let particles: Particle[] = [];
    let mouseX = -1000;
    let mouseY = -1000;
    let animId: number;

    function initParticles() {
      particles = Array.from({ length: PARTICLE_COUNT }, () => ({
        x: Math.random() * w,
        y: Math.random() * h,
        vx: (Math.random() - 0.5) * 0.4,
        vy: (Math.random() - 0.5) * 0.4,
        radius: Math.random() * 2 + 1.2,
        alpha: Math.random() * 0.4 + 0.15,
      }));
    }

    function draw() {
      ctx!.clearRect(0, 0, w, h);

      // Light theme: indigo/blue tones on light background
      const lineColor = 'rgba(99, 102, 241, 0.1)';
      const dotColor = 'rgba(99, 102, 241, 0.35)';
      const dotColorAlt = 'rgba(59, 130, 246, 0.3)';

      // Draw connections
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const dx = particles[i].x - particles[j].x;
          const dy = particles[i].y - particles[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < CONNECTION_DIST) {
            ctx!.beginPath();
            ctx!.moveTo(particles[i].x, particles[i].y);
            ctx!.lineTo(particles[j].x, particles[j].y);
            ctx!.strokeStyle = lineColor;
            ctx!.lineWidth = 0.5;
            ctx!.stroke();
          }
        }
      }

      // Draw particles
      for (const p of particles) {
        ctx!.beginPath();
        ctx!.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
        ctx!.fillStyle = p.radius > 1.5 ? dotColor : dotColorAlt;
        ctx!.fill();
      }

      // Update positions
      for (const p of particles) {
        // Mouse attraction
        const dx = mouseX - p.x;
        const dy = mouseY - p.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < MOUSE_ATTRACT_RADIUS && dist > 1) {
          const force = (MOUSE_ATTRACT_RADIUS - dist) / MOUSE_ATTRACT_RADIUS;
          p.vx += (dx / dist) * force * MOUSE_ATTRACT_FORCE;
          p.vy += (dy / dist) * force * MOUSE_ATTRACT_FORCE;
        }

        p.x += p.vx;
        p.y += p.vy;

        // Dampen
        p.vx *= 0.999;
        p.vy *= 0.999;

        // Wrap around
        if (p.x < -10) p.x = w + 10;
        if (p.x > w + 10) p.x = -10;
        if (p.y < -10) p.y = h + 10;
        if (p.y > h + 10) p.y = -10;
      }

      animId = requestAnimationFrame(draw);
    }

    function onResize() {
      w = window.innerWidth;
      h = window.innerHeight;
      canvas!.width = w;
      canvas!.height = h;
      initParticles();
    }

    function onMouseMove(e: MouseEvent) {
      mouseX = e.clientX;
      mouseY = e.clientY;
    }

    function onMouseLeave() {
      mouseX = -1000;
      mouseY = -1000;
    }

    canvas.width = w;
    canvas.height = h;
    initParticles();
    animId = requestAnimationFrame(draw);

    window.addEventListener('resize', onResize);
    window.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseleave', onMouseLeave);

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener('resize', onResize);
      window.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseleave', onMouseLeave);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 pointer-events-none z-0"
    />
  );
}
