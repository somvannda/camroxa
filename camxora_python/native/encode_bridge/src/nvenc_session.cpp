/**
 * NVENC session: D3D11 device + nvEncCreateInputBuffer NV12 CPU upload.
 *
 * Does not require CUDA or linking nvEncodeAPI.lib — loads
 * nvEncodeAPI64.dll at runtime from the NVIDIA driver.
 */

#include "nvenc_session.h"

#include <d3d11.h>
#include <dxgi.h>

#include <algorithm>
#include <cstring>
#include <cstdio>
#include <mutex>
#include <string>

#include "nvEncodeAPI.h"

#pragma comment(lib, "d3d11.lib")
#pragma comment(lib, "dxgi.lib")

namespace {

constexpr int kApiVersion = 2;

using NvEncodeAPICreateInstance_t =
    NVENCSTATUS(NVENCAPI*)(NV_ENCODE_API_FUNCTION_LIST* functionList);

struct NvencApi {
  HMODULE module = nullptr;
  NV_ENCODE_API_FUNCTION_LIST fn{};
  bool ready = false;
};

std::mutex g_api_mu;
NvencApi g_api;

bool env_truthy(const char* name) {
  char buf[16] = {};
  const DWORD n = GetEnvironmentVariableA(name, buf, static_cast<DWORD>(sizeof(buf)));
  if (n == 0 || n >= sizeof(buf)) {
    return false;
  }
  return (buf[0] == '1' && buf[1] == '\0') ||
         _stricmp(buf, "true") == 0 ||
         _stricmp(buf, "yes") == 0 ||
         _stricmp(buf, "on") == 0;
}

bool copy_cstr(char* dst, int dst_len, const char* src) {
  if (dst == nullptr || dst_len <= 0 || src == nullptr) {
    return false;
  }
  const size_t n = std::strlen(src);
  if (static_cast<int>(n) + 1 > dst_len) {
    return false;
  }
  std::memcpy(dst, src, n + 1);
  return true;
}

std::string wide_to_utf8(const WCHAR* w) {
  if (w == nullptr || w[0] == L'\0') {
    return {};
  }
  const int needed =
      WideCharToMultiByte(CP_UTF8, 0, w, -1, nullptr, 0, nullptr, nullptr);
  if (needed <= 1) {
    return {};
  }
  std::string out(static_cast<size_t>(needed - 1), '\0');
  WideCharToMultiByte(CP_UTF8, 0, w, -1, out.data(), needed, nullptr, nullptr);
  return out;
}

bool find_nvidia_adapter(IDXGIAdapter** out_adapter, std::string* out_name) {
  if (out_adapter == nullptr) {
    return false;
  }
  *out_adapter = nullptr;

  IDXGIFactory1* factory = nullptr;
  HRESULT hr = CreateDXGIFactory1(__uuidof(IDXGIFactory1),
                                  reinterpret_cast<void**>(&factory));
  if (FAILED(hr) || factory == nullptr) {
    return false;
  }

  IDXGIAdapter* chosen = nullptr;
  std::string chosen_name;
  for (UINT i = 0;; ++i) {
    IDXGIAdapter* adapter = nullptr;
    hr = factory->EnumAdapters(i, &adapter);
    if (hr == DXGI_ERROR_NOT_FOUND) {
      break;
    }
    if (FAILED(hr) || adapter == nullptr) {
      continue;
    }
    DXGI_ADAPTER_DESC desc{};
    if (FAILED(adapter->GetDesc(&desc))) {
      adapter->Release();
      continue;
    }
    // Skip Microsoft Basic Render Driver / software adapters.
    if (desc.VendorId == 0x1414 && desc.DeviceId == 0x8c) {
      adapter->Release();
      continue;
    }
    const std::string name = wide_to_utf8(desc.Description);
    const bool is_nvidia = (desc.VendorId == 0x10DE) ||
                           (name.find("NVIDIA") != std::string::npos) ||
                           (name.find("GeForce") != std::string::npos) ||
                           (name.find("Quadro") != std::string::npos) ||
                           (name.find("Tesla") != std::string::npos) ||
                           (name.find("RTX") != std::string::npos) ||
                           (name.find("GTX") != std::string::npos);
    if (is_nvidia) {
      if (chosen != nullptr) {
        chosen->Release();
      }
      chosen = adapter;
      chosen_name = name;
      // Prefer first NVIDIA adapter; keep looking only if empty name.
      if (!chosen_name.empty()) {
        break;
      }
    } else {
      adapter->Release();
    }
  }
  factory->Release();

  if (chosen == nullptr) {
    return false;
  }
  *out_adapter = chosen;
  if (out_name != nullptr) {
    *out_name = chosen_name.empty() ? std::string("NVIDIA GPU") : chosen_name;
  }
  return true;
}

bool ensure_nvenc_api() {
  std::lock_guard<std::mutex> lock(g_api_mu);
  if (g_api.ready) {
    return true;
  }

  HMODULE mod = LoadLibraryA("nvEncodeAPI64.dll");
  if (mod == nullptr) {
    return false;
  }

  using GetMaxVer_t = NVENCSTATUS(NVENCAPI*)(uint32_t*);
  auto get_max = reinterpret_cast<GetMaxVer_t>(
      GetProcAddress(mod, "NvEncodeAPIGetMaxSupportedVersion"));
  if (get_max != nullptr) {
    uint32_t max_ver = 0;
    if (get_max(&max_ver) == NV_ENC_SUCCESS) {
      // Driver reports (major << 4) | minor
      const uint32_t client_ver =
          (static_cast<uint32_t>(NVENCAPI_MAJOR_VERSION) << 4) |
          static_cast<uint32_t>(NVENCAPI_MINOR_VERSION);
      if (client_ver > max_ver) {
        FreeLibrary(mod);
        return false;
      }
    }
  }

  auto create = reinterpret_cast<NvEncodeAPICreateInstance_t>(
      GetProcAddress(mod, "NvEncodeAPICreateInstance"));
  if (create == nullptr) {
    FreeLibrary(mod);
    return false;
  }

  NV_ENCODE_API_FUNCTION_LIST fn{};
  fn.version = NV_ENCODE_API_FUNCTION_LIST_VER;
  const NVENCSTATUS st = create(&fn);
  if (st != NV_ENC_SUCCESS || fn.nvEncOpenEncodeSessionEx == nullptr) {
    FreeLibrary(mod);
    return false;
  }

  g_api.module = mod;
  g_api.fn = fn;
  g_api.ready = true;
  return true;
}

void rgba_to_nv12_bt601_limited(const uint8_t* rgba,
                                int stride_bytes,
                                int width,
                                int height,
                                uint8_t* dst,
                                uint32_t dst_pitch) {
  // BT.601 limited-range (studio swing): Y in [16,235], UV in [16,240].
  uint8_t* y_plane = dst;
  uint8_t* uv_plane = dst + static_cast<size_t>(dst_pitch) * static_cast<size_t>(height);

  for (int y = 0; y < height; ++y) {
    const uint8_t* row = rgba + static_cast<size_t>(y) * static_cast<size_t>(stride_bytes);
    uint8_t* y_row = y_plane + static_cast<size_t>(y) * static_cast<size_t>(dst_pitch);
    for (int x = 0; x < width; ++x) {
      const int r = row[x * 4 + 0];
      const int g = row[x * 4 + 1];
      const int b = row[x * 4 + 2];
      int Y = ((66 * r + 129 * g + 25 * b + 128) >> 8) + 16;
      y_row[x] = static_cast<uint8_t>(std::clamp(Y, 0, 255));
    }
  }

  for (int y = 0; y < height; y += 2) {
    const uint8_t* row0 = rgba + static_cast<size_t>(y) * static_cast<size_t>(stride_bytes);
    const uint8_t* row1 =
        rgba + static_cast<size_t>(std::min(y + 1, height - 1)) *
                   static_cast<size_t>(stride_bytes);
    uint8_t* uv_row =
        uv_plane + static_cast<size_t>(y / 2) * static_cast<size_t>(dst_pitch);
    for (int x = 0; x < width; x += 2) {
      const int x1 = std::min(x + 1, width - 1);
      const int r00 = row0[x * 4 + 0], g00 = row0[x * 4 + 1], b00 = row0[x * 4 + 2];
      const int r01 = row0[x1 * 4 + 0], g01 = row0[x1 * 4 + 1], b01 = row0[x1 * 4 + 2];
      const int r10 = row1[x * 4 + 0], g10 = row1[x * 4 + 1], b10 = row1[x * 4 + 2];
      const int r11 = row1[x1 * 4 + 0], g11 = row1[x1 * 4 + 1], b11 = row1[x1 * 4 + 2];
      const int r = (r00 + r01 + r10 + r11 + 2) >> 2;
      const int g = (g00 + g01 + g10 + g11 + 2) >> 2;
      const int b = (b00 + b01 + b10 + b11 + 2) >> 2;
      int U = ((-38 * r - 74 * g + 112 * b + 128) >> 8) + 128;
      int V = ((112 * r - 94 * g - 18 * b + 128) >> 8) + 128;
      uv_row[x] = static_cast<uint8_t>(std::clamp(U, 0, 255));
      uv_row[x + 1] = static_cast<uint8_t>(std::clamp(V, 0, 255));
    }
  }
}

uint32_t default_bitrate_bps(int width, int height, int fps) {
  // ~0.1 bit per pixel per frame as a reasonable default CBR.
  const int64_t bpp = 1;
  const int64_t bps =
      (static_cast<int64_t>(width) * height * fps * bpp) / 10;
  return static_cast<uint32_t>(std::max<int64_t>(bps, 500000));
}

}  // namespace

struct NvencSession {
  ID3D11Device* device = nullptr;
  ID3D11DeviceContext* context = nullptr;
  void* encoder = nullptr;
  NV_ENC_INPUT_PTR input_buffer = nullptr;
  NV_ENC_OUTPUT_PTR bitstream_buffer = nullptr;
  FILE* out = nullptr;
  int width = 0;
  int height = 0;
  int fps = 0;
  uint32_t frame_idx = 0;
  bool finished = false;
  bool encoder_initialized = false;
};

bool camxora_eb_stub_forced() {
  return env_truthy("CAMXORA_NATIVE_ENCODE_STUB");
}

int camxora_nvenc_probe(char* name_buf, int name_buf_len) {
  if (name_buf == nullptr || name_buf_len <= 0) {
    return CAMXORA_EB_ERR_LOAD;
  }
  if (camxora_eb_stub_forced()) {
    return copy_cstr(name_buf, name_buf_len, "stub") ? CAMXORA_EB_OK
                                                     : CAMXORA_EB_ERR_LOAD;
  }

  IDXGIAdapter* adapter = nullptr;
  std::string name;
  if (!find_nvidia_adapter(&adapter, &name)) {
    return copy_cstr(name_buf, name_buf_len, "no-nvenc") ? CAMXORA_EB_OK
                                                           : CAMXORA_EB_ERR_LOAD;
  }
  adapter->Release();

  if (!ensure_nvenc_api()) {
    return copy_cstr(name_buf, name_buf_len, "no-nvenc") ? CAMXORA_EB_OK
                                                           : CAMXORA_EB_ERR_LOAD;
  }

  if (!copy_cstr(name_buf, name_buf_len, name.c_str())) {
    return CAMXORA_EB_ERR_LOAD;
  }
  return CAMXORA_EB_OK;
}

static void release_session_resources(NvencSession* s) {
  if (s == nullptr) {
    return;
  }
  if (s->out != nullptr) {
    std::fclose(s->out);
    s->out = nullptr;
  }
  if (g_api.ready && s->encoder != nullptr) {
    if (s->input_buffer != nullptr) {
      g_api.fn.nvEncDestroyInputBuffer(s->encoder, s->input_buffer);
      s->input_buffer = nullptr;
    }
    if (s->bitstream_buffer != nullptr) {
      g_api.fn.nvEncDestroyBitstreamBuffer(s->encoder, s->bitstream_buffer);
      s->bitstream_buffer = nullptr;
    }
    g_api.fn.nvEncDestroyEncoder(s->encoder);
    s->encoder = nullptr;
  }
  if (s->context != nullptr) {
    s->context->Release();
    s->context = nullptr;
  }
  if (s->device != nullptr) {
    s->device->Release();
    s->device = nullptr;
  }
}

int camxora_nvenc_create(const CamxoraEncodeConfig* cfg, NvencSession** out_session) {
  if (out_session == nullptr) {
    return CAMXORA_EB_ERR_LOAD;
  }
  *out_session = nullptr;
  if (cfg == nullptr || cfg->output_path == nullptr || cfg->output_path[0] == '\0') {
    return CAMXORA_EB_ERR_LOAD;
  }
  if (cfg->width < 2 || cfg->height < 2 || (cfg->width % 2) != 0 ||
      (cfg->height % 2) != 0 || cfg->fps <= 0) {
    return CAMXORA_EB_ERR_LOAD;
  }
  if (camxora_eb_stub_forced()) {
    return CAMXORA_EB_ERR_NOT_IMPLEMENTED;
  }
  if (!ensure_nvenc_api()) {
    return CAMXORA_EB_ERR_NO_DEVICE;
  }

  IDXGIAdapter* adapter = nullptr;
  std::string gpu_name;
  if (!find_nvidia_adapter(&adapter, &gpu_name)) {
    return CAMXORA_EB_ERR_NO_DEVICE;
  }

  NvencSession* s = new NvencSession();
  s->width = cfg->width;
  s->height = cfg->height;
  s->fps = cfg->fps;

  D3D_FEATURE_LEVEL feature_level = D3D_FEATURE_LEVEL_11_0;
  const D3D_FEATURE_LEVEL levels[] = {
      D3D_FEATURE_LEVEL_11_1,
      D3D_FEATURE_LEVEL_11_0,
  };
  HRESULT hr = D3D11CreateDevice(
      adapter,
      D3D_DRIVER_TYPE_UNKNOWN,
      nullptr,
      0,
      levels,
      static_cast<UINT>(sizeof(levels) / sizeof(levels[0])),
      D3D11_SDK_VERSION,
      &s->device,
      &feature_level,
      &s->context);
  adapter->Release();
  if (FAILED(hr) || s->device == nullptr) {
    // Fallback: default hardware device (still may be NVIDIA on single-GPU PCs).
    hr = D3D11CreateDevice(
        nullptr,
        D3D_DRIVER_TYPE_HARDWARE,
        nullptr,
        0,
        levels,
        static_cast<UINT>(sizeof(levels) / sizeof(levels[0])),
        D3D11_SDK_VERSION,
        &s->device,
        &feature_level,
        &s->context);
  }
  if (FAILED(hr) || s->device == nullptr) {
    release_session_resources(s);
    delete s;
    return CAMXORA_EB_ERR_NO_DEVICE;
  }

  NV_ENC_OPEN_ENCODE_SESSION_EX_PARAMS open_params{};
  open_params.version = NV_ENC_OPEN_ENCODE_SESSION_EX_PARAMS_VER;
  open_params.deviceType = NV_ENC_DEVICE_TYPE_DIRECTX;
  open_params.device = s->device;
  open_params.apiVersion = NVENCAPI_VERSION;
  NVENCSTATUS st =
      g_api.fn.nvEncOpenEncodeSessionEx(&open_params, &s->encoder);
  if (st != NV_ENC_SUCCESS || s->encoder == nullptr) {
    release_session_resources(s);
    delete s;
    return CAMXORA_EB_ERR_NO_DEVICE;
  }

  NV_ENC_PRESET_CONFIG preset_config{};
  preset_config.version = NV_ENC_PRESET_CONFIG_VER;
  preset_config.presetCfg.version = NV_ENC_CONFIG_VER;
  const GUID preset_guid = NV_ENC_PRESET_P4_GUID;
  const NV_ENC_TUNING_INFO tuning = NV_ENC_TUNING_INFO_LOW_LATENCY;
  if (g_api.fn.nvEncGetEncodePresetConfigEx != nullptr) {
    st = g_api.fn.nvEncGetEncodePresetConfigEx(
        s->encoder,
        NV_ENC_CODEC_H264_GUID,
        preset_guid,
        tuning,
        &preset_config);
  } else if (g_api.fn.nvEncGetEncodePresetConfig != nullptr) {
    st = g_api.fn.nvEncGetEncodePresetConfig(
        s->encoder, NV_ENC_CODEC_H264_GUID, preset_guid, &preset_config);
  } else {
    st = NV_ENC_ERR_UNIMPLEMENTED;
  }
  if (st != NV_ENC_SUCCESS) {
    release_session_resources(s);
    delete s;
    return CAMXORA_EB_ERR_ENCODE;
  }

  NV_ENC_CONFIG encode_config = preset_config.presetCfg;
  encode_config.version = NV_ENC_CONFIG_VER;
  encode_config.gopLength = static_cast<uint32_t>(std::max(cfg->fps, 1) * 2);
  encode_config.frameIntervalP = 1;  // I/P only — no B-frames (simpler flush)
  encode_config.rcParams.rateControlMode = NV_ENC_PARAMS_RC_CBR;
  encode_config.rcParams.zeroReorderDelay = 1;
  encode_config.rcParams.enableLookahead = 0;
  const uint32_t bitrate =
      cfg->bitrate_kbps > 0
          ? static_cast<uint32_t>(cfg->bitrate_kbps) * 1000u
          : default_bitrate_bps(cfg->width, cfg->height, cfg->fps);
  encode_config.rcParams.averageBitRate = bitrate;
  encode_config.rcParams.maxBitRate = bitrate;
  encode_config.encodeCodecConfig.h264Config.repeatSPSPPS = 1;
  encode_config.encodeCodecConfig.h264Config.idrPeriod = encode_config.gopLength;
  encode_config.encodeCodecConfig.h264Config.chromaFormatIDC = 1;

  NV_ENC_INITIALIZE_PARAMS init_params{};
  init_params.version = NV_ENC_INITIALIZE_PARAMS_VER;
  init_params.encodeGUID = NV_ENC_CODEC_H264_GUID;
  init_params.presetGUID = preset_guid;
  init_params.tuningInfo = tuning;
  init_params.encodeWidth = static_cast<uint32_t>(cfg->width);
  init_params.encodeHeight = static_cast<uint32_t>(cfg->height);
  init_params.darWidth = static_cast<uint32_t>(cfg->width);
  init_params.darHeight = static_cast<uint32_t>(cfg->height);
  init_params.frameRateNum = static_cast<uint32_t>(cfg->fps);
  init_params.frameRateDen = 1;
  init_params.enableEncodeAsync = 0;
  init_params.enablePTD = 1;
  init_params.encodeConfig = &encode_config;
  init_params.maxEncodeWidth = init_params.encodeWidth;
  init_params.maxEncodeHeight = init_params.encodeHeight;

  st = g_api.fn.nvEncInitializeEncoder(s->encoder, &init_params);
  if (st != NV_ENC_SUCCESS) {
    release_session_resources(s);
    delete s;
    return CAMXORA_EB_ERR_ENCODE;
  }
  s->encoder_initialized = true;

  NV_ENC_CREATE_INPUT_BUFFER create_input{};
  create_input.version = NV_ENC_CREATE_INPUT_BUFFER_VER;
  create_input.width = static_cast<uint32_t>(cfg->width);
  create_input.height = static_cast<uint32_t>(cfg->height);
  create_input.bufferFmt = NV_ENC_BUFFER_FORMAT_NV12;
  st = g_api.fn.nvEncCreateInputBuffer(s->encoder, &create_input);
  if (st != NV_ENC_SUCCESS || create_input.inputBuffer == nullptr) {
    release_session_resources(s);
    delete s;
    return CAMXORA_EB_ERR_ENCODE;
  }
  s->input_buffer = create_input.inputBuffer;

  NV_ENC_CREATE_BITSTREAM_BUFFER create_bs{};
  create_bs.version = NV_ENC_CREATE_BITSTREAM_BUFFER_VER;
  st = g_api.fn.nvEncCreateBitstreamBuffer(s->encoder, &create_bs);
  if (st != NV_ENC_SUCCESS || create_bs.bitstreamBuffer == nullptr) {
    release_session_resources(s);
    delete s;
    return CAMXORA_EB_ERR_ENCODE;
  }
  s->bitstream_buffer = create_bs.bitstreamBuffer;

  FILE* out_file = nullptr;
#if defined(_MSC_VER)
  if (fopen_s(&out_file, cfg->output_path, "wb") != 0) {
    out_file = nullptr;
  }
#else
  out_file = std::fopen(cfg->output_path, "wb");
#endif
  s->out = out_file;
  if (s->out == nullptr) {
    release_session_resources(s);
    delete s;
    return CAMXORA_EB_ERR_IO;
  }

  *out_session = s;
  (void)kApiVersion;
  return CAMXORA_EB_OK;
}

static int write_bitstream(NvencSession* s) {
  NV_ENC_LOCK_BITSTREAM lock_bs{};
  lock_bs.version = NV_ENC_LOCK_BITSTREAM_VER;
  lock_bs.outputBitstream = s->bitstream_buffer;
  lock_bs.doNotWait = 0;
  NVENCSTATUS st = g_api.fn.nvEncLockBitstream(s->encoder, &lock_bs);
  if (st != NV_ENC_SUCCESS) {
    return CAMXORA_EB_ERR_ENCODE;
  }
  if (lock_bs.bitstreamSizeInBytes > 0 && lock_bs.bitstreamBufferPtr != nullptr) {
    const size_t n = static_cast<size_t>(lock_bs.bitstreamSizeInBytes);
    const size_t written = std::fwrite(lock_bs.bitstreamBufferPtr, 1, n, s->out);
    if (written != n) {
      g_api.fn.nvEncUnlockBitstream(s->encoder, s->bitstream_buffer);
      return CAMXORA_EB_ERR_IO;
    }
  }
  st = g_api.fn.nvEncUnlockBitstream(s->encoder, s->bitstream_buffer);
  if (st != NV_ENC_SUCCESS) {
    return CAMXORA_EB_ERR_ENCODE;
  }
  return CAMXORA_EB_OK;
}

static void copy_nv12_into_locked(const uint8_t* nv12,
                                  int y_stride,
                                  int width,
                                  int height,
                                  uint8_t* dst,
                                  uint32_t dst_pitch) {
  // Contiguous source: height rows of Y (y_stride each), then height/2 UV rows.
  for (int y = 0; y < height; ++y) {
    std::memcpy(dst + static_cast<size_t>(y) * static_cast<size_t>(dst_pitch),
                nv12 + static_cast<size_t>(y) * static_cast<size_t>(y_stride),
                static_cast<size_t>(width));
  }
  const uint8_t* src_uv =
      nv12 + static_cast<size_t>(y_stride) * static_cast<size_t>(height);
  uint8_t* dst_uv =
      dst + static_cast<size_t>(dst_pitch) * static_cast<size_t>(height);
  for (int y = 0; y < height / 2; ++y) {
    std::memcpy(dst_uv + static_cast<size_t>(y) * static_cast<size_t>(dst_pitch),
                src_uv + static_cast<size_t>(y) * static_cast<size_t>(y_stride),
                static_cast<size_t>(width));
  }
}

static int encode_nv12_picture(NvencSession* session, uint32_t pitch) {
  NV_ENC_PIC_PARAMS pic{};
  pic.version = NV_ENC_PIC_PARAMS_VER;
  pic.inputBuffer = session->input_buffer;
  pic.outputBitstream = session->bitstream_buffer;
  pic.bufferFmt = NV_ENC_BUFFER_FORMAT_NV12;
  pic.inputWidth = static_cast<uint32_t>(session->width);
  pic.inputHeight = static_cast<uint32_t>(session->height);
  pic.inputPitch = pitch;
  pic.pictureStruct = NV_ENC_PIC_STRUCT_FRAME;
  pic.frameIdx = session->frame_idx;
  pic.inputTimeStamp = session->frame_idx;
  ++session->frame_idx;

  NVENCSTATUS st = g_api.fn.nvEncEncodePicture(session->encoder, &pic);
  if (st == NV_ENC_ERR_NEED_MORE_INPUT) {
    // B-frame / lookahead buffering — not expected with our config, but safe.
    return CAMXORA_EB_OK;
  }
  if (st != NV_ENC_SUCCESS) {
    return CAMXORA_EB_ERR_ENCODE;
  }
  return write_bitstream(session);
}

int camxora_nvenc_submit_rgba(NvencSession* session,
                              const void* rgba,
                              int stride_bytes) {
  if (session == nullptr || rgba == nullptr || session->finished ||
      !session->encoder_initialized) {
    return CAMXORA_EB_ERR_LOAD;
  }
  if (stride_bytes < session->width * 4) {
    return CAMXORA_EB_ERR_LOAD;
  }

  NV_ENC_LOCK_INPUT_BUFFER lock_in{};
  lock_in.version = NV_ENC_LOCK_INPUT_BUFFER_VER;
  lock_in.inputBuffer = session->input_buffer;
  NVENCSTATUS st = g_api.fn.nvEncLockInputBuffer(session->encoder, &lock_in);
  if (st != NV_ENC_SUCCESS || lock_in.bufferDataPtr == nullptr) {
    return CAMXORA_EB_ERR_ENCODE;
  }

  const uint32_t pitch =
      lock_in.pitch != 0 ? lock_in.pitch : static_cast<uint32_t>(session->width);
  rgba_to_nv12_bt601_limited(static_cast<const uint8_t*>(rgba),
                             stride_bytes,
                             session->width,
                             session->height,
                             static_cast<uint8_t*>(lock_in.bufferDataPtr),
                             pitch);

  st = g_api.fn.nvEncUnlockInputBuffer(session->encoder, session->input_buffer);
  if (st != NV_ENC_SUCCESS) {
    return CAMXORA_EB_ERR_ENCODE;
  }

  return encode_nv12_picture(session, pitch);
}

int camxora_nvenc_submit_nv12(NvencSession* session,
                              const void* nv12,
                              int y_stride) {
  if (session == nullptr || nv12 == nullptr || session->finished ||
      !session->encoder_initialized) {
    return CAMXORA_EB_ERR_LOAD;
  }
  if (y_stride < session->width) {
    return CAMXORA_EB_ERR_LOAD;
  }

  NV_ENC_LOCK_INPUT_BUFFER lock_in{};
  lock_in.version = NV_ENC_LOCK_INPUT_BUFFER_VER;
  lock_in.inputBuffer = session->input_buffer;
  NVENCSTATUS st = g_api.fn.nvEncLockInputBuffer(session->encoder, &lock_in);
  if (st != NV_ENC_SUCCESS || lock_in.bufferDataPtr == nullptr) {
    return CAMXORA_EB_ERR_ENCODE;
  }

  const uint32_t pitch =
      lock_in.pitch != 0 ? lock_in.pitch : static_cast<uint32_t>(session->width);
  copy_nv12_into_locked(static_cast<const uint8_t*>(nv12),
                        y_stride,
                        session->width,
                        session->height,
                        static_cast<uint8_t*>(lock_in.bufferDataPtr),
                        pitch);

  st = g_api.fn.nvEncUnlockInputBuffer(session->encoder, session->input_buffer);
  if (st != NV_ENC_SUCCESS) {
    return CAMXORA_EB_ERR_ENCODE;
  }

  return encode_nv12_picture(session, pitch);
}

int camxora_nvenc_finish(NvencSession* session) {
  if (session == nullptr || !session->encoder_initialized) {
    return CAMXORA_EB_ERR_LOAD;
  }
  if (session->finished) {
    return CAMXORA_EB_OK;
  }

  NV_ENC_PIC_PARAMS pic{};
  pic.version = NV_ENC_PIC_PARAMS_VER;
  pic.encodePicFlags = NV_ENC_PIC_FLAG_EOS;
  NVENCSTATUS st = g_api.fn.nvEncEncodePicture(session->encoder, &pic);
  // EOS may return SUCCESS (with packet) or NEED_MORE_INPUT then SUCCESS on flush.
  if (st == NV_ENC_SUCCESS) {
    const int wr = write_bitstream(session);
    if (wr != CAMXORA_EB_OK) {
      return wr;
    }
  } else if (st != NV_ENC_ERR_NEED_MORE_INPUT && st != NV_ENC_SUCCESS) {
    // Some drivers return SUCCESS only; treat other errors as encode failure
    // unless bitstream already flushed.
    if (st != NV_ENC_ERR_INVALID_PARAM) {
      return CAMXORA_EB_ERR_ENCODE;
    }
  }

  // Drain any remaining buffered frames (defensive; I/P-only usually empty).
  for (int i = 0; i < 8; ++i) {
    NV_ENC_LOCK_BITSTREAM lock_bs{};
    lock_bs.version = NV_ENC_LOCK_BITSTREAM_VER;
    lock_bs.outputBitstream = session->bitstream_buffer;
    lock_bs.doNotWait = 1;
    st = g_api.fn.nvEncLockBitstream(session->encoder, &lock_bs);
    if (st != NV_ENC_SUCCESS) {
      break;
    }
    if (lock_bs.bitstreamSizeInBytes > 0 && lock_bs.bitstreamBufferPtr != nullptr) {
      const size_t n = static_cast<size_t>(lock_bs.bitstreamSizeInBytes);
      const size_t written =
          std::fwrite(lock_bs.bitstreamBufferPtr, 1, n, session->out);
      g_api.fn.nvEncUnlockBitstream(session->encoder, session->bitstream_buffer);
      if (written != n) {
        return CAMXORA_EB_ERR_IO;
      }
    } else {
      g_api.fn.nvEncUnlockBitstream(session->encoder, session->bitstream_buffer);
      break;
    }
  }

  if (session->out != nullptr) {
    std::fflush(session->out);
    std::fclose(session->out);
    session->out = nullptr;
  }
  session->finished = true;
  return CAMXORA_EB_OK;
}

void camxora_nvenc_destroy(NvencSession* session) {
  if (session == nullptr) {
    return;
  }
  release_session_resources(session);
  delete session;
}

