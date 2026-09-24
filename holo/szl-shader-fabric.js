/*
 * SZL SHADER FABRIC v1.1 — clean-room estate hologram engine
 * SZL Holdings — Doctrine v11 — Apache-2.0
 *
 * Rule zero: nothing glows that didn't earn it.
 * Estate entries carry honesty states; MEASURED glows, BLOCKED dims,
 * UNKNOWN renders neutral, malformed input renders NOTHING (fail-closed).
 *
 * API silhouette follows Shadertoy channel conventions
 * (iResolution / iTime / iMouse). All code original.
 *
 * v1.1 sweep (no bandaids, no dead code):
 *  - feedback buffers are intentionally deferred until a complete,
 *    tested ping-pong render path exists; no sampler is declared in v1.x.
 *  - ASCII-only identifiers (SzlShaderFabric).
 */
'use strict';

const HONESTY_MODES = Object.freeze({
  MEASURED: 1.0,   // full glow — earned
  PROMOTED: 0.85,  // promoted lane — bright, cooler tint
  UNKNOWN:  0.30,  // neutral — no claim
  BLOCKED:  0.05,  // dim — gate denied
  INVALID:  0.0    // stand-down — renders nothing
});

const VERT_SRC = `
attribute vec2 aPos;
void main() { gl_Position = vec4(aPos, 0.0, 1.0); }`;

const FRAG_SRC = `
precision highp float;
uniform vec2  iResolution;
uniform float iTime;
uniform vec2  iMouse;
uniform vec3  uEstates[64];       // xy = position, z = honesty gain
uniform int   uEstateCount;
uniform vec3  uTint[64];          // per-estate color

void main() {
  vec2 uv = gl_FragCoord.xy / iResolution.xy;
  vec3 col = vec3(0.012, 0.014, 0.020);   // ambient fabric baseline

  for (int i = 0; i < 64; ++i) {
    if (i >= uEstateCount) break;
    float gain  = uEstates[i].z;
    if (gain <= 0.0) continue;            // INVALID = no glow
    vec2  p     = uEstates[i].xy;
    float d     = distance(uv, p);
    float pulse = 0.55 + 0.45 * sin(iTime * 1.7 + float(i) * 2.4);
    float glow  = gain * pulse * 0.040 / max(d * d * 900.0, 0.0004);
    col += uTint[i] * glow;
    col += uTint[i] * smoothstep(0.0035, 0.0, d) * gain;   // core kernel
  }

  // receipt hash particles — deterministic sweep, no unbound samplers
  float scan = fract(sin(dot(floor(gl_FragCoord.xy / 6.0), vec2(12.9898, 78.233))) * 43758.5453);
  float band = abs(uv.y - fract(iTime * 0.011 + scan));
  col += vec3(0.02, 0.05, 0.04) * scan * smoothstep(0.4, 0.0, band);

  float dMouse = distance(uv, iMouse / iResolution);
  col += vec3(0.015, 0.03, 0.028) / max(dMouse * 140.0, 1.0);

  gl_FragColor = vec4(col, 1.0);
}`;

function compileShader(gl, type, src) {
  const shader = gl.createShader(type);
  gl.shaderSource(shader, src);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    console.error('[szl-fabric] shader compile failed:', gl.getShaderInfoLog(shader));
    gl.deleteShader(shader);
    return null;
  }
  return shader;
}

function linkProgram(gl, vs, fs) {
  const prog = gl.createProgram();
  gl.attachShader(prog, vs);
  gl.attachShader(prog, fs);
  gl.linkProgram(prog);
  if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) {
    console.error('[szl-fabric] link failed:', gl.getProgramInfoLog(prog));
    return null;
  }
  return prog;
}

/**
 * validateEstate — fail-closed admission gate.
 * An estate earns glow ONLY with a declared, known honesty state.
 * Malformed entries are dropped. Unknown state defaults to UNKNOWN.
 */
export function validateEstate(e) {
  if (!e || typeof e !== 'object') return null;
  if (typeof e.x !== 'number' || typeof e.y !== 'number') return null;
  if (e.x < -0.25 || e.x > 1.25 || e.y < -0.25 || e.y > 1.25) return null;
  const state = String(e.state || 'UNKNOWN').toUpperCase();
  const gain = HONESTY_MODES[state] !== undefined ? HONESTY_MODES[state]
                                                : HONESTY_MODES.UNKNOWN;
  const tint = Array.isArray(e.tint) && e.tint.length === 3
    ? e.tint : [0.35, 0.8, 0.7];   // default SZL teal
  return { x: e.x, y: e.y, gain, tint, id: String(e.id || 'unnamed') };
}

export class SzlShaderFabric {
  constructor(canvas, estates = []) {
    this.canvas = canvas;
    this.gl = canvas.getContext('webgl2', { antialias: false, alpha: false })
           || canvas.getContext('webgl',  { antialias: false, alpha: false });
    this.staticFallback = false;
    if (!this.gl) {
      // honest static fallback rash: no claims, no glow, plain notice
      this.staticFallback = true;
      const ctx = canvas.getContext('2d');
      if (ctx) {
        ctx.fillStyle = '#05070a';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.fillStyle = '#40514e';
        ctx.font = '12px monospace';
        ctx.fillText('SZL FABRIC: WebGL unavailable — static honest fallback', 16, 24);
      }
      return;
    }
    this.estates = estates.map(validateEstate).filter(Boolean).slice(0, 64);
    this.dropped = estates.length - this.estates.length;
    if (this.dropped > 0) {
      console.warn(`[szl-fabric] ${this.dropped} malformed estate(s) dropped — fail-closed`);
    }
    this._build();
    this._running = false;
  }

  _build() {
    const gl = this.gl;
    const vs = compileShader(gl, gl.VERTEX_SHADER, VERT_SRC);
    const fs = compileShader(gl, gl.FRAGMENT_SHADER, FRAG_SRC);
    if (!vs || !fs) return;
    this.prog = linkProgram(gl, vs, fs);
    if (!this.prog) return;

    const buf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER,
      new Float32Array([-1,-1, 1,-1, -1,1, -1,1, 1,-1, 1,1]), gl.STATIC_DRAW);
    const loc = gl.getAttribLocation(this.prog, 'aPos');
    gl.enableVertexAttribArray(loc);
    gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);

    gl.useProgram(this.prog);
    this.u = {
      res: gl.getUniformLocation(this.prog, 'iResolution'),
      time: gl.getUniformLocation(this.prog, 'iTime'),
      mouse: gl.getUniformLocation(this.prog, 'iMouse'),
      estates: gl.getUniformLocation(this.prog, 'uEstates'),
      count: gl.getUniformLocation(this.prog, 'uEstateCount'),
      tint: gl.getUniformLocation(this.prog, 'uTint')
    };

    this.mouse = [0, 0];
    this.canvas.addEventListener('pointermove', e => {
      const r = this.canvas.getBoundingClientRect();
      this.mouse = [e.clientX - r.left, r.height - (e.clientY - r.top)];
    });
  }

  /** Load the estate field from the canonical estates.json */
  static async fromEstateJson(canvas, estatesUrl) {
    let raw;
    try {
      const res = await fetch(estatesUrl);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      raw = (data.estates || []).map((e, i, arr) => ({
        id: e.name || e.id,
        x: typeof e.x === 'number' ? e.x : (0.1 + 0.8 * (i / Math.max(arr.length - 1, 1))),
        y: typeof e.y === 'number' ? e.y : (0.3 + 0.4 * Math.abs(Math.sin(i * 1.7))),
        state: e.state || e.honesty || 'UNKNOWN',
        tint: e.tint
      }));
    } catch (err) {
      console.error('[szl-fabric] estate fetch failed — fail-closed empty field:', err);
      raw = [];
    }
    return new SzlShaderFabric(canvas, raw);
  }

  start() {
    if (!this.prog || this._running) return;
    this._running = true;
    const gl = this.gl;
    const est = new Float32Array(192);
    const tint = new Float32Array(192);
    this.estates.forEach((e, i) => {
      est[i*3] = e.x; est[i*3+1] = e.y; est[i*3+2] = e.gain;
      tint[i*3] = e.tint[0]; tint[i*3+1] = e.tint[1]; tint[i*3+2] = e.tint[2];
    });
    const frame = t => {
      if (!this._running) return;
      const w = this.canvas.width = this.canvas.clientWidth;
      const h = this.canvas.height = this.canvas.clientHeight;
      gl.viewport(0, 0, w, h);
      gl.uniform2f(this.u.res, w, h);
      gl.uniform1f(this.u.time, t * 0.001);
      gl.uniform2f(this.u.mouse, this.mouse[0], this.mouse[1]);
      gl.uniform3fv(this.u.estates, est);
      gl.uniform1i(this.u.count, this.estates.length);
      gl.uniform3fv(this.u.tint, tint);
      gl.drawArrays(gl.TRIANGLES, 0, 6);
      requestAnimationFrame(frame);
    };
    requestAnimationFrame(frame);
  }

  stop() { this._running = false; }
}

export default SzlShaderFabric;