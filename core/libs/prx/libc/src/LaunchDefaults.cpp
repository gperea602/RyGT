// GT7.exe started without the launcher (a double-click, a shortcut, Steam): the launcher's Play sets
// environment variables the runtime and the renderer need (where guest memory goes, which ranges
// stay in guest memory) and some of its settings. Without them GT7 stopped at start ("fixed guest
// mapping overlaps a guest arena range"). The ones missing are set here the way Play sets them,
// from the launcher's settings next to GT7.exe, before anything reads them. A variable already set
// (by the launcher, or by hand) is left alone, so Play works as before.
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <string>

#ifdef _WIN32
#include <windows.h>
#endif
#include "GameSerial.hpp"

namespace LaunchDefaults {
namespace {

#ifdef _WIN32
std::string ExeFolder() {
    wchar_t path[MAX_PATH * 2];
    const DWORD length = GetModuleFileNameW(nullptr, path, MAX_PATH * 2);
    if (length == 0 || length >= MAX_PATH * 2) return {};
    std::wstring wide(path, length);
    wide.resize(wide.find_last_of(L"\\/") + 1);
    const int bytes = WideCharToMultiByte(CP_UTF8, 0, wide.c_str(), -1, nullptr, 0, nullptr, nullptr);
    std::string narrow(bytes > 0 ? bytes - 1 : 0, '\0');
    if (bytes > 0) WideCharToMultiByte(CP_UTF8, 0, wide.c_str(), -1, narrow.data(), bytes, nullptr, nullptr);
    return narrow;
}

std::string ReadFile(const std::string& path) {
    std::string text;
    const int length = MultiByteToWideChar(CP_UTF8, 0, path.c_str(), -1, nullptr, 0);
    std::wstring wide(length > 0 ? length - 1 : 0, L'\0');
    if (length > 0) MultiByteToWideChar(CP_UTF8, 0, path.c_str(), -1, wide.data(), length);
    if (FILE* file = _wfopen(wide.c_str(), L"rb")) {
        char buffer[4096];
        size_t read;
        while ((read = std::fread(buffer, 1, sizeof(buffer), file)) > 0) text.append(buffer, read);
        std::fclose(file);
    }
    return text;
}
#endif

/// The raw value after "key": in the GPU section of the launcher's settings, or "" (the file is
/// small and flat; the keys are unique to GPU).
std::string Setting(const std::string& config, const char* key) {
    const std::string quoted = std::string("\"") + key + "\"";
    const size_t at = config.find(quoted);
    if (at == std::string::npos) return {};
    size_t begin = config.find_first_not_of(" \t\r\n:", at + quoted.size());
    if (begin == std::string::npos) return {};
    size_t end = config.find_first_of(",}\r\n", begin);
    std::string value = config.substr(begin, end == std::string::npos ? std::string::npos : end - begin);
    while (!value.empty() && (value.back() == ' ' || value.back() == '\t')) value.pop_back();
    if (value.size() >= 2 && value.front() == '"' && value.back() == '"') value = value.substr(1, value.size() - 2);
    return value;
}

void SetIfMissing(const char* name, const std::string& value) {
    const char* current = std::getenv(name);
    if (current != nullptr && *current != '\0') return;
#ifdef _WIN32
    // The process block for the libraries loaded later (each reads its environment from it), and
    // this C runtime's copy.
    SetEnvironmentVariableA(name, value.c_str());
    _putenv_s(name, value.c_str());
#else
    setenv(name, value.c_str(), 0);
#endif
}

int Clamp(const std::string& text, int fallback, int low, int high) {
    if (text.empty()) return fallback;
    char* end = nullptr;
    const long value = std::strtol(text.c_str(), &end, 10);
    if (end == text.c_str()) return fallback;
    return static_cast<int>(value < low ? low : value > high ? high : value);
}

// FIX-RT-004: launchers built before FIX-RT-002 (RyGT7.exe, RyGTLauncher.exe and RyGTS.exe of
// 2026-11-15) still pass GT7's old in-place list, which leaves 0x10201de000-0x1020235000 out. GT7's
// depth pyramid moves visibility data there (more of it on tracks with rain), and those reads went
// through a renderer region again: scenery missing or unlit for single frames. SetIfMissing keeps
// a launcher's value, so the old default is replaced here, before the launcher check below. Only
// that exact string: a list set by hand is left alone.
constexpr const char* kOldInplaceRanges = "1020000000+1de000,1020235000+1dd000,1020407000+b000,200000000+8000000";
constexpr const char* kInplaceRanges = "1020000000+412000,200000000+8000000";

void ReplaceOldInplaceRanges() {
    const char* current = std::getenv("RYGT_NATIVE_INPLACE_RANGES");
    if (current == nullptr || std::strcmp(current, kOldInplaceRanges) != 0) return;
#ifdef _WIN32
    SetEnvironmentVariableA("RYGT_NATIVE_INPLACE_RANGES", kInplaceRanges);
    _putenv_s("RYGT_NATIVE_INPLACE_RANGES", kInplaceRanges);
#else
    setenv("RYGT_NATIVE_INPLACE_RANGES", kInplaceRanges, 1);
#endif
    std::fprintf(stderr, "[launch] FIX-RT-004: the launcher's old GT7 in-place list replaced with %s\n",
                 kInplaceRanges);
}

} // namespace

void Apply() {
    static bool applied = false;
    if (applied) return;
    applied = true;
    ReplaceOldInplaceRanges(); // FIX-RT-004: also when the launcher started the game
    // Started by the launcher: it set all of these.
    const char* fromLauncher = std::getenv("RYTY_INTEROP_BASE");
    if (fromLauncher != nullptr && *fromLauncher != '\0') return;
#ifdef _WIN32
    const std::string root = ExeFolder();
    // FEAT-GTS-291: these are GT7's settings (its write-back ranges, its 30 fps race lock). GT Sport's
    // launcher sets no RYTY_INTEROP_BASE, so under GTSport.exe they were applied as well and capped
    // GT Sport at 30 fps. Only a GT7.exe started without its launcher takes them.
    if (!GameSerial::RunningGt7()) return;
    // user\custom_configs\CUSA24769.json (CUSA03220.json in a GT7 folder from before GAME-004).
    const std::string configPath = GameSerial::GameConfigPath(root, true);
    const std::string config = ReadFile(configPath);
#else
    const std::string root;
    const std::string configPath;
    const std::string config;
#endif
    // As the launcher's StartGame (loader/RyGTLoader.cs) sets them; keep the two in step.
    SetIfMissing("RYTY_INTEROP_BASE", "8000000000");
    // FIX-RT-002: GT7's GPU culling memory as one range, gap included. In PS4 Pro mode its larger
    // depth pyramid moves visibility data into 0x10201de000-0x1020235000, between the ranges
    // listed for the base PS4, and those writes went through a renderer region again (scenery
    // missing for single frames). The same list serves the base PS4, Pro and Pro at 4K.
    SetIfMissing("RYGT_NATIVE_INPLACE_RANGES", kInplaceRanges);
    SetIfMissing("RYGT_NATIVE_INPLACE_FROM", "e000000000");
    if (!root.empty()) SetIfMissing("RYGT_LOG_DIRECTORY", root + "logs\\" + GameSerial::GameSerial());
    SetIfMissing("SHADGT_FPS_LOCK", Setting(config, "race_fps_lock") == "60" ? "60" : "30");
    const long cacheMb = Setting(config, "driver_cache_unlimited") == "true"
                             ? -1
                             : Clamp(Setting(config, "driver_cache_gb"), 5, 0, 100) * 1024L;
    SetIfMissing("RYGT_DRIVER_CACHE_MAX_MB", std::to_string(cacheMb));
    SetIfMissing("RYGT_AMD_SINGLE_SAMPLE_BARYCENTRIC", Setting(config, "amd_graphics_fix") == "true" ? "1" : "0");
    SetIfMissing("RYGT_DLSSG_FRAMES", std::to_string(Clamp(Setting(config, "dlssg_frames"), 1, 1, 5)));
    const std::string quality = Setting(config, "upscale_quality");
    SetIfMissing("RYGT_UPSCALE_QUALITY", quality.empty() ? "auto" : quality);
    const std::string bias = Setting(config, "texture_lod_bias");
    SetIfMissing("RYGT_TEXTURE_LOD_BIAS", bias.empty() ? "0" : bias);
    // FEAT-RT-905: mirror the GT7 launcher when starting GT7.exe directly.
    const std::string language = Setting(config, "system_language");
    if (!language.empty()) SetIfMissing("RYGT_SYSTEM_LANGUAGE", language);
    std::fprintf(stderr, "[launch] started without the launcher: its settings applied from %s\n",
                 config.empty() ? "defaults" : configPath.substr(root.size()).c_str());
}

namespace {
// At libc's load, before the other libraries load and read their environment.
const int applied_at_load = (Apply(), 0);
} // namespace

} // namespace LaunchDefaults

namespace Libc {
const char* RunningGameSerial() { return GameSerial::GameSerial(); }
}

// FEAT-GTS-291: SettingsIni.hpp.
extern "C" const char* RuntimeSettingsIni_nid_no_patch() {
    thread_local std::string path;
    path = GameSerial::SettingsIniPath(std::filesystem::path(), GameSerial::GameSerial()).string();
    return path.c_str();
}
