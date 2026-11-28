#pragma once
// FEAT-RT-905: port of the upstream RyGT system language selector (PRs #64, #114).
#include "SystemService.hpp"
#include <cstdlib>
#include <cstring>
namespace SystemLanguage {
inline int Resolve(const char* preferred, const char* legacy) {
    const char* text = preferred;
    if (!text || !*text) text = legacy;
    if (!text || !*text) return SYSTEM_SERVICE_PARAM_LANG_ENGLISH_US;
    if (std::strcmp(text, "es") == 0 || std::strcmp(text, "es-ES") == 0) return SYSTEM_SERVICE_PARAM_LANG_SPANISH;
    if (std::strcmp(text, "es-419") == 0 || std::strcmp(text, "es-LA") == 0) return SYSTEM_SERVICE_PARAM_LANG_SPANISH_LA;
    char* end = nullptr;
    const long id = std::strtol(text, &end, 10);
    if (end == text || *end != '\0' || id < 0 || id > SYSTEM_SERVICE_PARAM_LANG_LAST)
        return SYSTEM_SERVICE_PARAM_LANG_ENGLISH_US;
    return static_cast<int>(id);
}
}
