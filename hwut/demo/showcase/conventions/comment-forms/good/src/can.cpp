// can.cpp -- CAN frame dispatch
#include "can.hpp"

namespace bus {

void Can::dispatch(const Frame& f)
{
    switch (f.id) {
    case 0x101: motor_.set_target(f.as_float()); break;
    case 0x102: motor_.stop(); break;
    default:    ++unknown_; break;      // counted, never answered
    }
}

}  // namespace bus
