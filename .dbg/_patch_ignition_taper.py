from pathlib import Path

path = Path("camxora_python/visualizer/gpu_render.py")
text = path.read_text(encoding="utf-8")

old1 = """                    else:  # orbit-spikes / ignition-flare fallback
                        if style_preset in (\"ignition-flare\", \"neon-pulse\"):
                            pulse = 1.0 + logo_audio_env * 0.18 + particle_audio_env * 0.12
                            h_val *= pulse
                            wx *= 1.2
                            wy *= 1.2
                        p0x = px_arr[i] - wx
                        p0y = py_arr[i] - wy
                        p1x = px_arr[i] + wx
                        p1y = py_arr[i] + wy
                        p2x = px_arr[i] + dx_arr[i] * h_val + wx
                        p2y = py_arr[i] + dy_arr[i] * h_val + wy
                        p3x = px_arr[i] + dx_arr[i] * h_val - wx
                        p3y = py_arr[i] + dy_arr[i] * h_val - wy"""

new1 = """                    else:  # orbit-spikes / ignition-flare fallback
                        if style_preset in (\"ignition-flare\", \"neon-pulse\"):
                            pulse = 1.0 + logo_audio_env * 0.18 + particle_audio_env * 0.12
                            h_val *= pulse
                            wx_base = wx * 1.35
                            wy_base = wy * 1.35
                            wx_tip = wx * 0.55
                            wy_tip = wy * 0.55
                            p0x = px_arr[i] - wx_base
                            p0y = py_arr[i] - wy_base
                            p1x = px_arr[i] + wx_base
                            p1y = py_arr[i] + wy_base
                            p2x = px_arr[i] + dx_arr[i] * h_val + wx_tip
                            p2y = py_arr[i] + dy_arr[i] * h_val + wy_tip
                            p3x = px_arr[i] + dx_arr[i] * h_val - wx_tip
                            p3y = py_arr[i] + dy_arr[i] * h_val - wy_tip
                        else:
                            p0x = px_arr[i] - wx
                            p0y = py_arr[i] - wy
                            p1x = px_arr[i] + wx
                            p1y = py_arr[i] + wy
                            p2x = px_arr[i] + dx_arr[i] * h_val + wx
                            p2y = py_arr[i] + dy_arr[i] * h_val + wy
                            p3x = px_arr[i] + dx_arr[i] * h_val - wx
                            p3y = py_arr[i] + dy_arr[i] * h_val - wy"""

old2 = """                    else:
                        if style_preset in (\"ignition-flare\", \"neon-pulse\"):
                            pulse = 1.0 + logo_audio_env * 0.18 + particle_audio_env * 0.12
                            h_val *= pulse
                            wx *= 1.2
                            wy *= 1.2
                        p0x = px_arr[i] - wx
                        p0y = py_arr[i] - wy
                        p1x = px_arr[i] + wx
                        p1y = py_arr[i] + wy
                        p2x = px_arr[i] + dx_arr[i] * h_val + wx
                        p2y = py_arr[i] + dy_arr[i] * h_val + wy
                        p3x = px_arr[i] + dx_arr[i] * h_val - wx
                        p3y = py_arr[i] + dy_arr[i] * h_val - wy"""

new2 = """                    else:
                        if style_preset in (\"ignition-flare\", \"neon-pulse\"):
                            pulse = 1.0 + logo_audio_env * 0.18 + particle_audio_env * 0.12
                            h_val *= pulse
                            wx_base = wx * 1.35
                            wy_base = wy * 1.35
                            wx_tip = wx * 0.55
                            wy_tip = wy * 0.55
                            p0x = px_arr[i] - wx_base
                            p0y = py_arr[i] - wy_base
                            p1x = px_arr[i] + wx_base
                            p1y = py_arr[i] + wy_base
                            p2x = px_arr[i] + dx_arr[i] * h_val + wx_tip
                            p2y = py_arr[i] + dy_arr[i] * h_val + wy_tip
                            p3x = px_arr[i] + dx_arr[i] * h_val - wx_tip
                            p3y = py_arr[i] + dy_arr[i] * h_val - wy_tip
                        else:
                            p0x = px_arr[i] - wx
                            p0y = py_arr[i] - wy
                            p1x = px_arr[i] + wx
                            p1y = py_arr[i] + wy
                            p2x = px_arr[i] + dx_arr[i] * h_val + wx
                            p2y = py_arr[i] + dy_arr[i] * h_val + wy
                            p3x = px_arr[i] + dx_arr[i] * h_val - wx
                            p3y = py_arr[i] + dy_arr[i] * h_val - wy"""

print("old1", text.count(old1))
print("old2", text.count(old2))
text = text.replace(old1, new1)
text = text.replace(old2, new2)
path.write_text(text, encoding="utf-8")
print("done")
