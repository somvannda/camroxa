cmake_minimum_required(VERSION 3.16)
project(camxora_encode_bridge LANGUAGES CXX)

# Real NVENC: vendored nvEncodeAPI.h + runtime LoadLibrary(nvEncodeAPI64.dll).
# Do NOT link nvEncodeAPI.lib — the driver DLL provides the entry points.
# CUDA is not required (CPU NV12 upload via nvEncCreateInputBuffer).

add_library(camxora_encode_bridge SHARED
  src/encode_bridge.cpp
  src/nvenc_session.cpp
)

target_include_directories(camxora_encode_bridge
  PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/include
  PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/src
    ${CMAKE_CURRENT_SOURCE_DIR}/third_party/nvidia
)

target_compile_definitions(camxora_encode_bridge
  PRIVATE
    CAMXORA_ENCODE_BRIDGE_EXPORTS
    WIN32_LEAN_AND_MEAN
    NOMINMAX
)

target_compile_features(camxora_encode_bridge PRIVATE cxx_std_17)

if(MSVC)
  target_compile_options(camxora_encode_bridge PRIVATE /W4 /EHsc)
endif()

if(WIN32)
  target_link_libraries(camxora_encode_bridge PRIVATE d3d11 dxgi)
endif()

set_target_properties(camxora_encode_bridge PROPERTIES
  OUTPUT_NAME "camxora_encode_bridge"
  RUNTIME_OUTPUT_DIRECTORY_RELEASE "${CMAKE_BINARY_DIR}/Release"
  RUNTIME_OUTPUT_DIRECTORY_DEBUG "${CMAKE_BINARY_DIR}/Debug"
  LIBRARY_OUTPUT_DIRECTORY_RELEASE "${CMAKE_BINARY_DIR}/Release"
  LIBRARY_OUTPUT_DIRECTORY_DEBUG "${CMAKE_BINARY_DIR}/Debug"
)

install(TARGETS camxora_encode_bridge
  RUNTIME DESTINATION encode
  LIBRARY DESTINATION encode
)

