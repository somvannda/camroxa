import { useEffect, useRef, useState } from "react";

export interface AudioMetrics {
  bass: number;
  mid: number;
  treble: number;
  kick: number;
  fft: Float32Array; // 64 bins
}

export function useSpectrumAudio(audioUrl: string | null) {
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const sourceRef = useRef<MediaElementAudioSourceNode | null>(null);
  const audioElRef = useRef<HTMLAudioElement | null>(null);
  
  const [isPlaying, setIsPlaying] = useState(false);
  const [isReady, setIsReady] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);

  // We want exactly 64 bins, but FFT_SIZE=128 gives us 64 bins up to Nyquist (e.g. 22kHz).
  // The upper half of these bins (above ~11kHz) are usually empty or very quiet in MP3s.
  // To make the graphic bars fill the space nicely without a flat tail, we will only use the lower N bins.
  // Or we can increase FFT size and crop.// Let's use FFT_SIZE = 1024 to get high enough resolution in the bass frequencies for logarithmic mapping
  const FFT_SIZE = 1024;
  const BINS = 64; // We map the high-res FFT down to 64 visual bins

  const dataArrayRef = useRef(new Uint8Array(FFT_SIZE / 2));
  const metricsRef = useRef<AudioMetrics>({
    bass: 0,
    mid: 0,
    treble: 0,
    kick: 0,
    fft: new Float32Array(BINS),
  });

  // Transient kick detector refs
  const bassFastRef = useRef(0);
  const bassSlowRef = useRef(0);
  const kickEnvRef = useRef(0);

  useEffect(() => {
    if (!audioUrl) {
      setIsReady(false);
      setIsPlaying(false);
      if (audioElRef.current) {
        audioElRef.current.pause();
        audioElRef.current.src = "";
      }
      if (sourceRef.current) {
        try {
          sourceRef.current.disconnect();
        } catch {}
        sourceRef.current = null;
      }
      return;
    }

    setIsReady(false);
    setIsPlaying(false);
    setCurrentTime(0);
    setDuration(0);

    if (audioElRef.current) {
      audioElRef.current.pause();
    }
    if (sourceRef.current) {
      try {
        sourceRef.current.disconnect();
      } catch {}
      sourceRef.current = null;
    }

    const audio = new Audio();
    audio.preload = "auto";
    audio.src = audioUrl;
    audio.load();
    audioElRef.current = audio;

    const onCanPlay = () => setIsReady(true);
    const onEnded = () => setIsPlaying(false);
    const onTimeUpdate = () => setCurrentTime(audio.currentTime);
    const onLoadedMetadata = () => {
      setDuration(audio.duration);
      setIsReady(true);
    };
    const onError = () => {
      setIsReady(false);
      setIsPlaying(false);
      const err = audio.error;
      console.error("[useSpectrumAudio] audio error", { code: err?.code ?? null, message: err?.message ?? "" });
    };
    
    audio.addEventListener("canplay", onCanPlay);
    audio.addEventListener("ended", onEnded);
    audio.addEventListener("timeupdate", onTimeUpdate);
    audio.addEventListener("loadedmetadata", onLoadedMetadata);
    audio.addEventListener("error", onError);

    return () => {
      audio.removeEventListener("canplay", onCanPlay);
      audio.removeEventListener("ended", onEnded);
      audio.removeEventListener("timeupdate", onTimeUpdate);
      audio.removeEventListener("loadedmetadata", onLoadedMetadata);
      audio.removeEventListener("error", onError);
      audio.pause();
      audio.src = "";
      if (sourceRef.current) {
        try {
          sourceRef.current.disconnect();
        } catch {}
        sourceRef.current = null;
      }
    };
  }, [audioUrl]);

  const initAudio = () => {
    if (!audioContextRef.current) {
      const Ctx = window.AudioContext || (window as any).webkitAudioContext;
      audioContextRef.current = new Ctx();
    }
    const ctx = audioContextRef.current;
    
    if (ctx.state === "suspended") {
      ctx.resume();
    }

    if (!analyserRef.current) {
      analyserRef.current = ctx.createAnalyser();
      analyserRef.current.fftSize = FFT_SIZE;
      analyserRef.current.smoothingTimeConstant = 0.8; // Will be overridden by Zustand settings
    }

    if (!sourceRef.current && audioElRef.current) {
      try {
        sourceRef.current = ctx.createMediaElementSource(audioElRef.current);
        sourceRef.current.connect(analyserRef.current);
        analyserRef.current.connect(ctx.destination);
      } catch (e) {
        console.error("[useSpectrumAudio] createMediaElementSource failed", e);
        sourceRef.current = null;
      }
    }
  };

  const togglePlay = () => {
    const audio = audioElRef.current;
    if (!audio) return;

    initAudio();

    if (audio.paused) {
      audio.play().then(() => setIsPlaying(true)).catch(console.error);
    } else {
      audio.pause();
      setIsPlaying(false);
    }
  };

  const seek = (time: number) => {
    const audio = audioElRef.current;
    if (audio) {
      audio.currentTime = time;
      setCurrentTime(time);
    }
  };

  const updateMetrics = (smoothing: number, sensitivity: number) => {
    const analyser = analyserRef.current;
    if (!analyser) return metricsRef.current;

    // Update smoothing dynamically from UI
    analyser.smoothingTimeConstant = Math.max(0, Math.min(0.99, smoothing));

    const dataArray = dataArrayRef.current;
    analyser.getByteFrequencyData(dataArray);

    const fft = metricsRef.current.fft;
    const sampleRate = audioContextRef.current?.sampleRate || 44100;
    const nyquist = sampleRate / 2;
    
    // We want to map the linear FFT data into 64 logarithmically spaced bins.
    // This spreads the bass and mids across more visual bars, preventing a single massive spike.
    const minFreq = 20;
    const maxFreq = 12000;
    const minLog = Math.log10(minFreq);
    const maxLog = Math.log10(maxFreq);

    for (let i = 0; i < BINS; i++) {
      // Calculate the frequency range for this visual bin
      const logFreq = minLog + (i / BINS) * (maxLog - minLog);
      const freq = Math.pow(10, logFreq);
      
      // Find the corresponding index in the linear dataArray
      const linearIndex = (freq / nyquist) * (FFT_SIZE / 2);
      
      // Interpolate between the two nearest linear bins for smoothness
      const idx1 = Math.floor(linearIndex);
      const idx2 = Math.min(Math.ceil(linearIndex), (FFT_SIZE / 2) - 1);
      const frac = linearIndex - idx1;
      
      let rawVal = 0;
      if (idx1 === idx2) {
        rawVal = dataArray[idx1] || 0;
      } else {
        const val1 = dataArray[idx1] || 0;
        const val2 = dataArray[idx2] || 0;
        rawVal = val1 * (1 - frac) + val2 * frac;
      }

      // Apply frequency boost to mimic Python's visual output (boost higher frequencies)
      const freqBoost = 1.0 + Math.pow(i / BINS, 2) * 2.0;
      const boostedVal = rawVal * freqBoost;
      
      // Python uses max(0.01, min(1.0, val)) where val is float [0..1]
      // Since data is 0..255, we divide by 255
      const normalizedVal = Math.max(0.01, Math.min(1.0, boostedVal / 255.0));

      // Logarithmic temporal smoothing (spring-like motion matching Vizzy / AE)
      fft[i] = fft[i] * smoothing + normalizedVal * (1 - smoothing);
    }

    // Feature extraction (Bass, Mid, Treble)
    const binCount = FFT_SIZE / 2;
    const getAvg = (startHz: number, endHz: number) => {
      const startIdx = Math.floor((startHz / nyquist) * binCount);
      const endIdx = Math.floor((endHz / nyquist) * binCount);
      let sum = 0;
      for (let i = startIdx; i <= endIdx; i++) sum += dataArray[i] || 0;
      return (sum / Math.max(1, endIdx - startIdx + 1)) / 255.0;
    };

    const rawBass = getAvg(20, 200);
    const mid = getAvg(200, 2000);
    const treble = getAvg(2000, 8000);
    
    // Fast/Slow transient kick detection (matching Python particles system)
    bassFastRef.current = bassFastRef.current * 0.7 + rawBass * 0.3;
    bassSlowRef.current = bassSlowRef.current * 0.95 + rawBass * 0.05;
    const kickRaw = Math.max(0, bassFastRef.current - bassSlowRef.current);
    const kick0 = Math.max(0, Math.min(1, kickRaw * 4.0));
    kickEnvRef.current = Math.max(kick0, kickEnvRef.current * 0.9);
    const kickPow = Math.pow(Math.max(0, Math.min(1, kickEnvRef.current)), 2);

    metricsRef.current = {
      bass: rawBass,
      mid,
      treble,
      kick: kickPow,
      fft: fft,
    };

    return metricsRef.current;
  };

  return {
    isReady,
    isPlaying,
    currentTime,
    duration,
    togglePlay,
    seek,
    updateMetrics,
  };
}
