# feature: F00
# Overlay occupies tests/ during acceptance. The parent project still
# add_subdirectory(tests) when testing is enabled at configure time.
# The library target is defined in src/; this directory adds no CMake
# targets. Do not restore the in-tree C++ test binaries here — Python
# suites drive the public library surface.
cmake_minimum_required(VERSION 3.16)
