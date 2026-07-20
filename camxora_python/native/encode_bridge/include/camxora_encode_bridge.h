/**
 * Camxora Native Encode Bridge — C API (REQ-3.5)
 *
 * Optional Windows DLL for hardware NVENC H.264 encode.
 * Runtime loads nvEncodeAPI64.dll from the NVIDIA driver (no link-time
 * nvEncodeAPI.lib). Input path: CPU RGBA→NV12 upload via nvEncCreateInputBuffer
 * (CUDA-free). GL→D3D zero-copy is a follow-up.
 *
 * Output is Annex-B elementary H.264 written to output_path. Python remuxes
 * with audio via ffmpeg `-c:v copy`. Set CAMXORA_NATIVE_ENCODE_STUB=1 to force
 * the not-implemented stub path for tests.
 */

#ifndef CAMXORA_ENCODE_BRIDGE_H
#define CAMXORA_ENCODE_BRIDGE_H

#ifdef __cplusplus
extern "C" {
#endif

#if defined(_WIN32)
#  ifdef CAMXORA_ENCODE_BRIDGE_EXPORTS
#    define CAMXORA_EB_API __declspec(dllexport)
#  else
#    define CAMXORA_EB_API __declspec(dllimport)
#  endif
#else
#  define CAMXORA_EB_API
#endif

#define CAMXORA_EB_OK 0
#define CAMXORA_EB_ERR_NOT_IMPLEMENTED 1
#define CAMXORA_EB_ERR_NO_DEVICE 2
#define CAMXORA_EB_ERR_LOAD 3
#define CAMXORA_EB_ERR_ENCODE 4
#define CAMXORA_EB_ERR_IO 5

typedef struct {
  int width;
  int height;
  int fps;
  int bitrate_kbps; /* 0 = default CBR bitrate from resolution/fps */
  const char* output_path;
} CamxoraEncodeConfig;

/** API version (currently 2 — adds camxora_eb_submit_nv12). */
CAMXORA_EB_API int camxora_eb_version(void);

/**
 * Probe GPU / bridge identity into name_buf (NUL-terminated).
 * Real build returns DXGI adapter description (NVIDIA GPU name).
 * If NVENC is unavailable, may return "no-nvenc" or CAMXORA_EB_ERR_NO_DEVICE.
 * Stub mode (CAMXORA_NATIVE_ENCODE_STUB=1) returns "stub".
 * @return CAMXORA_EB_OK on success, or an error code.
 */
CAMXORA_EB_API int camxora_eb_probe(char* name_buf, int name_buf_len);

/**
 * Create an NVENC encode session. Opens output_path for Annex-B H.264.
 * Returns CAMXORA_EB_ERR_NO_DEVICE if NVENC/GPU unavailable,
 * CAMXORA_EB_ERR_NOT_IMPLEMENTED in stub mode.
 */
CAMXORA_EB_API int camxora_eb_create(const CamxoraEncodeConfig* cfg, void** out_session);

/**
 * Submit one packed RGBA8 frame (stride_bytes = row pitch in bytes).
 * Converts to NV12 (BT.601 limited) on CPU and encodes via NVENC.
 */
CAMXORA_EB_API int camxora_eb_submit_rgba(void* session, const void* rgba, int stride_bytes);

/**
 * Submit one NV12 frame (skip RGBA convert in the DLL).
 * nv12 is contiguous Y plane (height rows of y_stride) then interleaved UV
 * (height/2 rows of y_stride). Prefer this when Python packs with OpenCV.
 */
CAMXORA_EB_API int camxora_eb_submit_nv12(void* session, const void* nv12, int y_stride);

/**
 * Finish encoding: send EOS, flush packets, close output file.
 */
CAMXORA_EB_API int camxora_eb_finish(void* session);

/** Destroy session (safe with NULL). Releases NVENC, D3D11, and file. */
CAMXORA_EB_API void camxora_eb_destroy(void* session);

#ifdef __cplusplus
}
#endif

#endif /* CAMXORA_ENCODE_BRIDGE_H */

