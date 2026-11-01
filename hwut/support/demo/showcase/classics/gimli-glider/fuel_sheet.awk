# fuel_sheet.awk -- MODEL of the fuel-load computation for Air Canada
# Flight 143 at Montreal, 23 July 1983 (Board of Inquiry, final report
# 1985). The fuel gauges were inoperative; the fuel already in the tanks
# was measured with the dripsticks (a reading converted to litres), and the
# fuel to add was computed by hand from the specific gravity the refueller
# gave. The 767 was one of Air Canada's first aircraft with metric fuel
# figures: the flight plan asked for KILOGRAMS.
#
# Input lines '<item> <number> <unit>' ('#' notes):
#     dripstick <litres> L       fuel in the tanks, from the dripsticks
#     required  <mass> kg        fuel the flight plan asks for
#     density   <number> <unit>  the density used: 'kg/L' or 'lb/L'
# The sheet computes in the unit the DENSITY names -- kilograms for kg/L,
# pounds for lb/L (the required mass is converted to pounds then, 1 kg =
# 2.20462 lb) -- and prints every step with its unit:
#     density   <number> <unit>
#     on-board  <mass> <kg|lb>   in the tanks before refuelling
#     to-add    <mass> <kg|lb>
#     add       <litres> L       for the refueller, rounded up
/^#/ || NF < 3 { next }
{ value[$1] = $2; unit[$1] = $3 }
END {
    d = value["density"]
    mass = unit["density"] == "lb/L" ? "lb" : "kg"
    need = value["required"] * (mass == "lb" && unit["required"] == "kg" ? 2.20462 : 1)
    on = value["dripstick"] * d
    add_mass = need - sprintf("%.0f", on)
    add_l = add_mass / d; if (add_l > int(add_l)) add_l = int(add_l) + 1
    printf "density   %s %s\n", d, unit["density"]
    printf "on-board  %.0f %s\n", on, mass
    printf "required  %.0f %s\n", need, mass
    printf "to-add    %.0f %s\n", add_mass, mass
    printf "add       %d L\n", add_l
}
