//  ----- Empty line for version ---- DO NOT REMOVE ----
const version = '1.0.1';

// We're overriding the modules console.[log/warn/error] (printf etc. in C) to catch library errors for logging
const consoleLog = [];

function logToConsole() {
  consoleLog.push(arguments[0]);
  // TODO set a switch here
  // console.log(arguments[0]);
  postMessage({ action: 'log', log: arguments[0] });
}

logToConsole(`EncodeWorker version: ` + version);
// ------------------------------------------------------------
// Wasm module
const Module = {};

// Safeguard for fatal errors
let closed = false;

// Track if WASM module is ready
let wasmReady = false;

// Used in testing to try webm, should be left at 1 for mp4/mp3 encoding
const fileType = 1;

// Two types of wasm, with/without threads. Only chrome supports threads atm and it still has issues sometimes
let exportVersion = '';

// If we're using a filesystem (only supported in Chrome), use a circular buffer and flush to file when possible
let usingFileSystem = false;
const FS_LOCAL_BUF_SIZE = 1024 * 1024 * 0.5; // 2MB
// Since we keep a local buffer of data here (to reduce the number of write calls)
// we need two offsets when dealing with the filesystem
// one for keeping track of where in the file to write the buffer
// and one for how far into the local buffer we should write when not sending
let previousFileOffset = 0;
let localFSBufferOffset = 0;

// size in 64KiB pages, use webassembly memory as a resizable arraybuffer
const MAXIMUM_WASM_SIZE = 65536;
let memory = new WebAssembly.Memory({ initial: 400, maximum: MAXIMUM_WASM_SIZE });
// Data buffer
let videoData = new Uint8Array(memory.buffer);
// Size of the actual video
let videoSize = 0;

let writeIndex = 0;

// Keep pointers to buffers, to prevent remallocing them every frame
let leftPointer, rightPointer, framePointer;

// postMessage allows for transferring data to workers without copying it via postMessage(frame, [frame.buffer])
// but then we don't know the type of data, so we first postMessage({action: type}) and set the switch
let receivingVideoFrame = false;

function bytesToString(uintArr) {
  let myString = '';
  for (let i = 0; i < uintArr.byteLength; i++) {
    myString += String.fromCharCode(uintArr[i]);
  }
  return myString;
}

function getLog() {
  let str = '';
  try {
    const size = Module._get_log_size();
    const logPtr = Module._get_log();
    const arr = new Uint8Array(Module.HEAPU8.buffer, logPtr, size);
    str = bytesToString(arr);
  } catch (err) {
    str = 'Failed to get log: ' + err.message;
  }
  return str;
}

function handleError(type, title, err, msg) {
  console.error(type, title, err);
  closed = true;
  postMessage({
    action: type,
    errTitle: title,
    errMsg: msg || (err ? err.message : ''),
    stack: err ? err.stack : '',
    log: getLog(),
    version: exportVersion,
    consoleLog,
  });
}

function openVideo(config) {
  const { width, height, fps, bitrate, presetIdx, duration, profileIdx, crf } = config;

  const errorType = exportVersion === 'threaded' ? 'initialize-error' : 'error';
  if (closed) {
    return;
  }

  try {
    framePointer = Module._malloc(width * height * 4);

    Module._open_video(
      width,
      height,
      fps,
      bitrate,
      presetIdx,
      fileType,
      fileType,
      duration,
      profileIdx,
      crf
    );
  } catch (err) {
    handleError(errorType, 'Error initializing video', err);
  }
}

function addAudioFrame(buffer) {
  if (closed) {
    return;
  }

  const audioWindowLength = buffer.length / 2;
  const left = new Float32Array(buffer.slice(0, audioWindowLength));
  const right = new Float32Array(buffer.slice(audioWindowLength, audioWindowLength * 2));

  try {
    Module.HEAPF32.set(left, leftPointer >> 2);
    Module.HEAPF32.set(right, rightPointer >> 2);
    Module._add_audio_frame(leftPointer, rightPointer, audioWindowLength);
  } catch (err) {
    handleError('error', 'Error adding audio frame', err);
    return;
  }

  postMessage({ action: 'ready' });
}

function openAudio(config) {
  const { bitrate, sampleRate } = config;
  if (closed) {
    return;
  }

  const errorType = exportVersion === 'threaded' ? 'initialize-error' : 'error';
  try {
    const NUM_SAMPLES_PER_FRAME = 1152;
    leftPointer = Module._malloc(NUM_SAMPLES_PER_FRAME * 4);
    rightPointer = Module._malloc(NUM_SAMPLES_PER_FRAME * 4);
    Module._open_audio(sampleRate, 2, bitrate, 2);
  } catch (err) {
    handleError(errorType, 'Error initializing audio', err);
  }
}

function writeHeader() {
  const errorType = exportVersion === 'threaded' ? 'initialize-error' : 'error';

  if (closed) {
    return;
  }
  try {
    Module._write_header();
  } catch (err) {
    handleError(errorType, 'Error writing header', err);
    Module._free_buffer();
  }

  //handleError('error', 'Test error', null, 'This is a test error message');
}

function closeStream() {
  if (closed) {
    return;
  }

  try {
    // Check if the WASM module is ready and the function exists
    if (wasmReady && typeof Module._close_stream === 'function') {
      Module._close_stream();
    } else {
      logToConsole('Warning: Attempted to close stream before WASM module was ready');
    }
  } catch (err) {
    handleError('error', 'Error closing streams', err);
  }
}

function flushCurrent() {
  if (localFSBufferOffset > 0) {
    postMessage({
      action: 'flush_to_file',
      offset: previousFileOffset - localFSBufferOffset,
    });

    const data = videoData.slice(0, localFSBufferOffset);
    postMessage(data, [data.buffer]);
    videoData = new Uint8Array(FS_LOCAL_BUF_SIZE);
    localFSBufferOffset = 0;
  }
}

function addVideoFrame(buffer) {
  if (closed) {
    return;
  }

  let size = -1;
  try {
    Module.HEAPU8.set(buffer, framePointer);
    size = Module._add_video_frame(framePointer);
  } catch (err) {
    let msg = err.message;
    if (msg.includes('abort(OOM)')) {
      msg =
        'Out of memory. There is a ~2GB limit on output filesize, so make sure to stay below this.';
    }
    handleError('error', 'Error encoding video frame', err, msg);
  }
  buffer = null;
  postMessage({ action: 'ready' });

  return size;
}

function close(shouldReturnFile) {
  if (closed) {
    return;
  }
  try {
    closeStream(shouldReturnFile);

    // Only free memory if WASM is ready and functions exist
    if (wasmReady) {
      if (typeof Module._free_buffer === 'function') {
        Module._free_buffer();
      }
      if (typeof Module._free === 'function') {
        Module._free(leftPointer);
        Module._free(rightPointer);
        Module._free(framePointer);
      }
    }

    logToConsole(
      `EncodeWorker closing: ${videoSize},  ${videoData.length}, ${usingFileSystem}, ${shouldReturnFile}`
    );
    if (shouldReturnFile) {
      if (!usingFileSystem) {
        const data = videoData.subarray(0, videoSize);

        try {
          postMessage({ action: 'closed' });
          postMessage(data, [data.buffer]);
          memory = new WebAssembly.Memory({ initial: 400, maximum: MAXIMUM_WASM_SIZE });
        } catch (err) {
          // Firefox doesnt allow for transferring the wasm arraybuffer, copy it
          const cpydata = new Uint8Array(data);
          postMessage(cpydata, [cpydata.buffer]);
        }
      } else {
        if (localFSBufferOffset > 0) {
          flushCurrent();
        }
        postMessage({ action: 'closed' });
      }
    } else {
      logToConsole(
        'EncodeWorker: close completed without returning file (no "closed" postMessage).'
      );
    }
  } catch (err) {
    handleError('error', 'Error occurred when closing streams', err);
  }
}

onmessage = e => {
  const { data } = e;
  if (data.action === undefined) {
    if (receivingVideoFrame) {
      addVideoFrame(data);
    } else {
      addAudioFrame(data);
    }

    return;
  }

  switch (data.action) {
    case 'load': {
      exportVersion = data.data;
      logToConsole('EncodeWorker: load received. exportVersion=' + exportVersion);
      videoSize = 0;
      const script =
        exportVersion === 'threaded' ? 'WasmEncoder_threaded.js' : 'WasmEncoder_sequential.js';

      //script = "WasmEncoder.js";
      logToConsole('EncodeWorker: Using ' + script);
      // eslint-disable-next-line no-undef
      importScripts(script);
      logToConsole('EncodeWorker: Script imported');

      const errorType = exportVersion === 'threaded' ? 'initialize-error' : 'error';

      if (usingFileSystem) {
        videoData = new Uint8Array(FS_LOCAL_BUF_SIZE);
      }

      // Set up some functions from emscripten
      Module['mainScriptUrlOrBlob'] = script;
      Module['print'] = logToConsole;
      Module['printErr'] = logToConsole;

      // Threads use a lot of memory, so we add the choice to use less cores when exporting
      // TODO set from ffmpeg?
      Module['get_num_cores'] = () => {
        console.log('Getting number of cores: ', navigator.hardwareConcurrency);
        return navigator.hardwareConcurrency;
      };

      // Instead of using the avio context for handling the file writing we use a write_data callback
      // since realloc seems to fragment the memory, and it requires a copy of the full file at the end
      Module['write_data'] = (bufPtr, size, offset) => {
        writeIndex++;
        // Cast to Uints, since EM_ASM casts to int
        const castBufPtr = bufPtr >>> 0;
        const castOffset = offset >>> 0;

        // Grab pointer to encoded data in wasm memory
        let data = Module.HEAPU8.subarray(castBufPtr, castBufPtr + size);

        // TODO: maybe just send buffer and do in  do in filewriter instead?
        // ffmpeg doesnt always write to the file in order, keep a buffer and batch some writes
        // since writing each time is slow

        if (usingFileSystem) {
          if (videoSize + size > Math.pow(2, 32) - 1) {
            handleError(
              'error',
              'File too large',
              null,
              `The file has exceeded the maximum size for file system export (4GB). This is a limitation of the browser.`
            );
            return;
          }

          // console.log(videoData.length, offset, previousFileOffset);
          // File is continuing
          if (castOffset === previousFileOffset) {
            if (localFSBufferOffset + size > FS_LOCAL_BUF_SIZE) {
              flushCurrent();
            }
            videoData.set(data, localFSBufferOffset);
            localFSBufferOffset += data.length;
          } else {
            if (localFSBufferOffset > 0) {
              flushCurrent();
            }

            // Copy data out of wasm memory, since we're transferring it to the main thread
            data = new Uint8Array(data);
            postMessage({ action: 'flush_to_file', offset: castOffset });
            postMessage(data, [data.buffer]);
          }
          previousFileOffset = castOffset + data.length;
        } else {
          // Check if video-size is larger than 32 bit INT_MAX
          if (videoSize + size > Math.pow(2, 31) - 1) {
            logToConsole(`${bufPtr}, ${size}, ${offset}, ${castOffset}, ${castBufPtr}`);
            handleError(
              'error',
              'File too large',
              null,
              `The file has exceeded the maximum size for in memory export (2GB). This is a limitation of the browser. If you want to export large files, try the file system export.`
            );
            return;
          }

          // the size of our current "chunk"
          if (videoSize + size > videoData.length) {
            // If we dont have an option to write the data to file we use a Uint8Array that we resize
            // Grow by 200 pages (200*64KiB ~ 12MB)
            const growAmount = 200;
            memory.grow(growAmount);
            videoData = new Uint8Array(memory.buffer);
          }
          videoData.set(data, castOffset);
          videoSize += size;
        }
        if (!(writeIndex % 2500)) {
          logToConsole(
            `Write nr ${writeIndex}, bufferSize: ${videoData.length}, writtenAmount: ${videoSize}, ModuleSize: ${Module.HEAPF32.byteLength}`
          );
        }
        data = null;
      };

      try {
        logToConsole('EncodeWorker: Initializing module');
        // eslint-disable-next-line no-undef
        WasmEncoder(Module);
        logToConsole('EncodeWorker: Module initialized');
      } catch (err) {
        logToConsole('Failed to initialize module');
        handleError(errorType, 'Error initializing webassembly', err);
      }

      Module['onRuntimeInitialized'] = () => {
        logToConsole('Runtime initialized');
        wasmReady = true;
        postMessage({ action: 'loaded' });
        // We want to log to the console from the wasm
        Module._set_log(1);
      };

      break;
    }
    case 'audio':
      receivingVideoFrame = false;
      break;
    case 'video':
      receivingVideoFrame = true;
      break;
    case 'init':
      logToConsole('EncodeWorker: Init called');
      closed = false;
      usingFileSystem = data.data.usingFileSystem;
      openVideo(data.data.videoConfig);
      openAudio(data.data.audioConfig);
      logToConsole('Using filesystem: ' + usingFileSystem);
      writeHeader();
      postMessage({ action: 'initialized' });
      break;
    case 'close':
      logToConsole(
        'EncodeWorker: close action received shouldReturnFile: ' + data.shouldReturnFile
      );
      close(data.shouldReturnFile);
      closed = true;
      break;
    case 'reset':
      // For threaded exports, we can't safely reset the WASM module
      // Signal that the worker should be recreated
      if (exportVersion === 'threaded') {
        logToConsole('EncodeWorker: Threaded worker requires recreation');
        postMessage({ action: 'worker_needs_recreation' });
        return;
      }

      // Reset worker state to clean state (sequential only)
      closed = false;
      receivingVideoFrame = false;
      videoSize = 0;
      writeIndex = 0;
      localFSBufferOffset = 0;
      previousFileOffset = 0;

      // Clear any existing data
      if (usingFileSystem) {
        videoData = new Uint8Array(FS_LOCAL_BUF_SIZE);
      } else {
        memory = new WebAssembly.Memory({ initial: 400, maximum: MAXIMUM_WASM_SIZE });
        videoData = new Uint8Array(memory.buffer);
      }

      // Clear console log
      consoleLog.length = 0;

      logToConsole('EncodeWorker: Reset completed');
      break;
    default:
      throw new Error('unknown command');
  }
};
