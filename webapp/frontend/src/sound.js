// Web Audio helpers: earcons (mic start/stop chimes) and level meters that
// drive the orb's audio reactivity. Meters publish the current loudness as a
// CSS custom property (--voice-level, 0..1) at requestAnimationFrame rate --
// CSS reads it for scale/glow, so React never re-renders at 60fps.
let _ctx = null

function audioCtx() {
  if (!_ctx) _ctx = new (window.AudioContext || window.webkitAudioContext)()
  if (_ctx.state === 'suspended') _ctx.resume()
  return _ctx
}

// Two-note sine chime, Siri-style: rising = mic opened, falling = mic closed.
// Synthesized on the fly -- no audio assets to ship.
export function playEarcon(kind) {
  try {
    const c = audioCtx()
    const t = c.currentTime
    const freqs = kind === 'start' ? [523.25, 784.0] : [784.0, 523.25]
    freqs.forEach((f, i) => {
      const osc = c.createOscillator()
      const gain = c.createGain()
      osc.type = 'sine'
      osc.frequency.value = f
      const t0 = t + i * 0.09
      gain.gain.setValueAtTime(0.0001, t0)
      gain.gain.exponentialRampToValueAtTime(0.1, t0 + 0.02)
      gain.gain.exponentialRampToValueAtTime(0.0001, t0 + 0.15)
      osc.connect(gain).connect(c.destination)
      osc.start(t0)
      osc.stop(t0 + 0.16)
    })
  } catch {
    // no audio context (rare) -- chimes are decorative, never fatal
  }
}

function runMeter(analyser, extraCleanup) {
  const data = new Uint8Array(analyser.fftSize)
  let raf
  const tick = () => {
    analyser.getByteTimeDomainData(data)
    let sum = 0
    for (let i = 0; i < data.length; i++) {
      const d = (data[i] - 128) / 128
      sum += d * d
    }
    const rms = Math.sqrt(sum / data.length)
    const level = Math.min(1, rms * 3.5)
    document.documentElement.style.setProperty('--voice-level', level.toFixed(3))
    raf = requestAnimationFrame(tick)
  }
  tick()
  return () => {
    cancelAnimationFrame(raf)
    document.documentElement.style.setProperty('--voice-level', '0')
    extraCleanup?.()
  }
}

// Meter the user's microphone while recording. Returns a stop() function.
export function meterMicStream(stream) {
  try {
    const c = audioCtx()
    const src = c.createMediaStreamSource(stream)
    const analyser = c.createAnalyser()
    analyser.fftSize = 512
    src.connect(analyser)
    return runMeter(analyser, () => src.disconnect())
  } catch {
    return () => {}
  }
}

// Meter the TTS <audio> element while the answer plays. A media element can
// only ever be wired into one MediaElementSource, so cache per element.
const _elementSources = new WeakMap()

export function meterAudioElement(el) {
  try {
    const c = audioCtx()
    let src = _elementSources.get(el)
    if (!src) {
      src = c.createMediaElementSource(el)
      src.connect(c.destination) // rerouted through the context -- keep it audible
      _elementSources.set(el, src)
    }
    const analyser = c.createAnalyser()
    analyser.fftSize = 512
    src.connect(analyser)
    return runMeter(analyser, () => {
      try { src.disconnect(analyser) } catch { /* already gone */ }
    })
  } catch {
    return () => {}
  }
}
