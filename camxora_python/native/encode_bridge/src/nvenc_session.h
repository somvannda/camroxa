/**
 * NVENC encode session (D3D11 device + CPU NV12 upload, no CUDA).
 */
#pragma once
#include "camxora_encode_bridge.h"
#include <cstdint>
#include <string>
#include <vector>
struct NvencSession;
/** True when CAMXORA_NATIVE_ENCODE_STUB=1. */
bool camxora_eb_stub_forced();
/** Write probe name into buf; returns Camxora error code. */
int camxora_nvenc_probe(char* name_buf, int name_buf_len);
/** Create session; on success *out_session is non-null. */
int camxora_nvenc_create(const CamxoraEncodeConfig* cfg, NvencSession** out_session);
int camxora_nvenc_submit_rgba(NvencSession* session, const void* rgba, int stride_bytes);
int camxora_nvenc_submit_nv12(NvencSession* session, const void* nv12, int y_stride);
int camxora_nvenc_finish(NvencSession* session);
void camxora_nvenc_destroy(NvencSession* session);

