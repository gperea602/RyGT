// FEAT-RT-905: standalone regression test, no game or GPU required.
#include "../../core/libs/prx/libSceSystemService/SystemLanguage.hpp"
#include <cassert>
#include <string>
int main() {
    using SystemLanguage::Resolve;
    assert(Resolve(nullptr, nullptr) == 1);
    assert(Resolve("", "es-419") == 20);
    assert(Resolve("20", "3") == 20);
    assert(Resolve("es", nullptr) == 3);
    assert(Resolve("es-ES", nullptr) == 3);
    assert(Resolve("es-LA", nullptr) == 20);
    assert(Resolve("es-419", nullptr) == 20);
    for (int i = 0; i <= 30; ++i) assert(Resolve(std::to_string(i).c_str(), nullptr) == i);
    for (const char* s : {"-1", "31", "20x", "invalid", "999999999999999999999999"}) assert(Resolve(s, nullptr) == 1);
    assert(Resolve("invalid", "20") == 1);
}
