cmake_minimum_required(VERSION 3.20)
project(RetroVaultNative LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_definitions(-DUNICODE -D_UNICODE -DWIN32_LEAN_AND_MEAN)

# Windows security hardening flags
if(MSVC)
    add_compile_options(/W4 /WX- /guard:cf)
    add_link_options(/DYNAMICBASE /NXCOMPAT /HIGHENTROPYVA /GUARD:CF)
else()
    # Clang / GCC MinGW
    add_compile_options(-Wall -Wextra -O3 -fstack-protector-strong)
    add_link_options(-static -static-libgcc -static-libstdc++ -Wl,--dynamicbase -Wl,--nxcompat -Wl,--high-entropy-va)
endif()

set(SOURCES
    src/scanner.cpp
    src/file_io.cpp
    src/usn_provider.cpp
    src/vss_provider.cpp
)

add_library(retrovault_native SHARED ${SOURCES})

target_include_directories(retrovault_native PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/include
)

set_target_properties(retrovault_native PROPERTIES
    OUTPUT_NAME "retrovault_native"
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/bin"
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/bin"
)
