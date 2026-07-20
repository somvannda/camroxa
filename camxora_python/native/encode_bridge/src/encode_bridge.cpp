/**
 * Camxora Native Encode Bridge — C API entry points (REQ-3.5).
 *
 * Real NVENC via nvenc_session (D3D11 + CPU NV12 upload).
 * Force stub with CAMXORA_NATIVE_ENCODE_STUB=1.
 */

#include "camxora_encode_bridge.h"
#include "nvenc_session.h"

#include <cstring>

namespace {

constexpr int kApiVersion = 2;

}  // namespace

extern "C" {

CAMXORA_EB_API int camxora_eb_version(void) {
  return kApiVersion;
}

CAMXORA_EB_API int camxora_eb_probe(char* name_buf, int name_buf_len) {
  return camxora_nvenc_probe(name_buf, name_buf_len);
}

CAMXORA_EB_API int camxora_eb_create(const CamxoraEncodeConfig* cfg, void** out_session) {
  if (out_session != nullptr) {
    *out_session = nullptr;
  }
  if (camxora_eb_stub_forced()) {
    return CAMXORA_EB_ERR_NOT_IMPLEMENTED;
  }
  NvencSession* session = nullptr;
  const int rc = camxora_nvenc_create(cfg, &session);
  if (rc != CAMXORA_EB_OK) {
    return rc;
  }
  if (out_session == nullptr) {
    camxora_nvenc_destroy(session);
    return CAMXORA_EB_ERR_LOAD;
  }
  *out_session = session;
  return CAMXORA_EB_OK;
}

CAMXORA_EB_API int camxora_eb_submit_rgba(void* session, const void* rgba, int stride_bytes) {
  if (camxora_eb_stub_forced()) {
    return CAMXORA_EB_ERR_NOT_IMPLEMENTED;
  }
  return camxora_nvenc_submit_rgba(static_cast<NvencSession*>(session), rgba, stride_bytes);
}

CAMXORA_EB_API int camxora_eb_submit_nv12(void* session, const void* nv12, int y_stride) {
  if (camxora_eb_stub_forced()) {
    return CAMXORA_EB_ERR_NOT_IMPLEMENTED;
  }
  return camxora_nvenc_submit_nv12(static_cast<NvencSession*>(session), nv12, y_stride);
}

CAMXORA_EB_API int camxora_eb_finish(void* session) {
  if (camxora_eb_stub_forced()) {
    return CAMXORA_EB_ERR_NOT_IMPLEMENTED;
  }
  return camxora_nvenc_finish(static_cast<NvencSession*>(session));
}

CAMXORA_EB_API void camxora_eb_destroy(void* session) {
  camxora_nvenc_destroy(static_cast<NvencSession*>(session));
}

}  // extern "C"

