! @hwut {
!     title     = "Demo: a climate chamber's step response -- regions, units, a string law"
!     build     { framework = "make", target = "%.exe" }
!     tolerance { constraints = ["overshoot <= 0.5 K",
!                                "settle <= 4 min",
!                                "verdict == 'settled'"] }
!     choices {
!         heat { features = ["region-verbatim", "region-table", "region-point-cloud",
!                            "region-ignore", "laws-in-units", "string-binding",
!                            "test-level-tolerance", "annotation-lines"] }
!         cool { features = ["region-verbatim", "region-table", "region-point-cloud",
!                            "region-ignore", "laws-in-units", "string-binding",
!                            "test-level-tolerance", "annotation-lines"] }
!     }
! }
!
! _____________________________________________________________________________
! SUBJECT  a climate chamber driven from one temperature to another by a PI
!          controller: its configuration, its sensors at the end, its step
!          response, and the three numbers its requirement names.
! REQUIREMENT  The chamber reaches the setpoint within 4 minutes, overshoots
!              it by no more than 0.5 K, and reports itself 'settled'.
!
! Every run is seeded by the clock: the sensors are noisy, the four sensor
! rows come out in a different order, the calibration stamps are today's.
! Both choices pass on every run anyway; each part of the output says how:
!
! '##' lines     notes for the reader. The comparison skips them on both
!                sides, anywhere -- even inside a region.
! verbatim       '##! verbatim' ... '####': the configuration as loaded. It is
!                YAML, where indentation is meaning, so nothing is tolerated.
! table          '##! table key=0 ignore=1 numeric={2:0.0005}': one row per
!                sensor, matched by its NAME whatever the order; the stamp
!                not compared; the reading in K within 0.05 %.
! point-cloud    '##! point-cloud limit=0.5 constraint={...}': the step
!                response as points (t, T), near GOOD's and inside the
!                envelope.
! ignore         '##! ignore': a picture for the human eye.
! units          '((settle: 150 s))' against the law 'settle <= 4 min'.
! string law     '((verdict: "settled"))' judged by 'verdict == 'settled''.
! test-level     the three laws stand ONCE, in the header's own 'tolerance'.
! tolerance
!
! CHOICES  heat  20 degC -> 40 degC.
!          cool  40 degC -> 20 degC.
! _____________________________________________________________________________
module chamber_model
    use, intrinsic :: iso_fortran_env, only: real64
    use hwut_text
    implicit none
    private
    public :: run

    real(real64), parameter :: DT_S = 1.0_real64, DURATION_S = 400.0_real64
    integer, parameter      :: SAMPLE_S = 20
    real(real64), parameter :: BAND_K = 0.3_real64, NOISE_K = 0.02_real64
    real(real64), parameter :: TAU_S = 300.0_real64, RATE_K_PER_S = 0.15_real64
    real(real64), parameter :: KP = 0.6_real64, KI = 0.01_real64

    character(6), parameter :: SENSOR(4) = ["top   ", "middle", "bottom", "door  "]
    ! Offset of each sensor against the air in the middle of the chamber.
    real(real64), parameter :: SENSOR_OFFSET(4) = [0.10_real64, 0.0_real64, -0.10_real64, -0.40_real64]

contains

    real(real64) function gauss(mu, sigma)
        ! RETURN: a number drawn from the normal distribution (mu, sigma),
        !         by Box and Muller.
        real(real64), intent(in) :: mu, sigma
        real(real64)             :: u1, u2
        call random_number(u1)
        call random_number(u2)
        gauss = mu + sigma * sqrt(-2.0_real64 * log(1.0_real64 - u1)) &
                           * cos(2.0_real64 * acos(-1.0_real64) * u2)
    end function

    function fixed(x, width, digits) result(text)
        ! RETURN: 'x' with 'digits' digits after the point, blanks before it
        !         to 'width' -- Python's '%<width>.<digits>f'.
        real(real64), intent(in)  :: x
        integer, intent(in)       :: width, digits
        character(:), allocatable :: text
        character(48)             :: buffer
        character(16)             :: form
        write(form, '("(F47.", i0, ")")') digits
        write(buffer, form) x
        text = trim(adjustl(buffer))
        if( digits == 0 ) text = text(1:len(text) - 1)        ! 'F' writes '300.'
        text = repeat(" ", max(0, width - len(text))) // text
    end function

    subroutine step_response(start_c, setpoint_c, measured)
        ! RETURN: nothing; 'measured(0:400)' holds one sample per simulation
        !         step of the chamber driven from 'start_c' to 'setpoint_c'
        !         by the PI controller of the configuration, with noise.
        real(real64), intent(in)  :: start_c, setpoint_c
        real(real64), intent(out) :: measured(0:)
        real(real64)              :: temp, integral, error, output
        real(real64), parameter   :: AMBIENT = 20.0_real64
        integer                   :: t
        temp     = start_c
        integral = 0.0_real64
        do t = 0, int(DURATION_S)
            measured(t) = temp + gauss(0.0_real64, NOISE_K)
            error  = setpoint_c - measured(t)
            output = KP * error + KI * integral
            if( output > -1.0_real64 .and. output < 1.0_real64 ) then  ! anti-windup: integrate
                integral = integral + error * DT_S                    ! only while unsaturated
            end if
            output = max(-1.0_real64, min(1.0_real64, output))
            temp = temp + DT_S * ((AMBIENT - temp) / TAU_S + RATE_K_PER_S * output)
        end do
    end subroutine

    subroutine print_config()
        ! RETURN: nothing; prints the configuration as loaded, byte for byte.
        call say("configuration, as loaded (YAML: whitespace is meaning):")
        call say("##! verbatim")
        call say("chamber:")
        call say("  plant:")
        call say("    time_constant_s: 300")
        call say("    heater_rate_K_per_s: 0.15")
        call say("  controller:")
        call say("    kind: PI")
        call say("    kp: 0.6")
        call say("    ki: 0.01")
        call say("    output: [-1.0, 1.0]")
        call say("  sensors: [top, middle, bottom, door]")
        call say("####")
    end subroutine

    subroutine print_sensors(setpoint_c)
        ! RETURN: nothing; prints one row per sensor, in a random order, with
        !         today's calibration stamp and the reading at the end in K.
        real(real64), intent(in) :: setpoint_c
        integer                  :: order(4), i, j, swap
        real(real64)             :: u, reading
        character(8)             :: day
        character(10)            :: clock
        character(19)            :: stamp
        call say("sensors at the end, in K (the order is the bus's):")
        call say("    sensor  calibrated           reading_K")
        call say("##! table key=0 ignore=1 numeric={2:0.0005}")
        order = [1, 2, 3, 4]
        do i = 4, 2, -1
            call random_number(u)
            j = 1 + min(i - 1, int(u * i))
            swap = order(i); order(i) = order(j); order(j) = swap
        end do
        call date_and_time(day, clock)
        stamp = day(1:4) // "-" // day(5:6) // "-" // day(7:8) // "T" &
                // clock(1:2) // ":" // clock(3:4) // ":" // clock(5:6)
        do i = 1, 4
            reading = setpoint_c + SENSOR_OFFSET(order(i)) + gauss(0.0_real64, NOISE_K) + 273.15_real64
            call say("    " // SENSOR(order(i)) // "  " // stamp // "  " // fixed(reading, 9, 2))
        end do
        call say("####")
    end subroutine

    subroutine print_cloud(measured, start_c, setpoint_c)
        ! RETURN: nothing; prints the step response, one point (t_s, T_degC)
        !         every SAMPLE_S, framed with the envelope the requirement
        !         allows.
        real(real64), intent(in) :: measured(0:), start_c, setpoint_c
        real(real64)             :: low, high
        integer                  :: t
        low  = min(start_c, setpoint_c)
        high = max(start_c, setpoint_c)
        if( setpoint_c > start_c ) then
            high = high + 0.5_real64
        else
            low  = low - 0.5_real64
        end if
        ! 0.1 K beyond the envelope on either side: the sensor's noise.
        call say("step response, t in s against T in degC; envelope " // fixed(low, 0, 1) &
                 // " .. " // fixed(high, 0, 1) // ":")
        call say("##! point-cloud limit=0.5 constraint={y >= " // fixed(low - 0.1_real64, 0, 1) &
                 // " and y <= " // fixed(high + 0.1_real64, 0, 1) // "}")
        do t = 0, ubound(measured, 1), SAMPLE_S
            call say("    " // fixed(real(t, real64), 5, 0) // "  " // fixed(measured(t), 6, 2))
        end do
        call say("####")
    end subroutine

    subroutine print_picture(measured, start_c, setpoint_c)
        ! RETURN: nothing; prints the step response as stars, for the human
        !         eye only: one row per 40 s, one column per 0.5 K.
        real(real64), intent(in) :: measured(0:), start_c, setpoint_c
        character(46)            :: row
        real(real64)             :: low
        integer                  :: t
        low = min(start_c, setpoint_c) - 1.0_real64
        call say("the same, as a picture ('|' the setpoint):")
        call say("##! ignore")
        do t = 0, ubound(measured, 1), 40
            row = " "
            row(nint((setpoint_c - low) / 0.5_real64) + 1:nint((setpoint_c - low) / 0.5_real64) + 1) = "|"
            associate( k => max(0, min(45, nint((measured(t) - low) / 0.5_real64))) + 1 )
                row(k:k) = "*"
            end associate
            call say("    " // fixed(real(t, real64), 4, 0) // " s  " // trim(row))
        end do
        call say("####")
    end subroutine

    subroutine run(start_c, setpoint_c)
        ! RETURN: nothing; drives the chamber and prints every part of the
        !         report.
        real(real64), intent(in) :: start_c, setpoint_c
        real(real64)             :: measured(0:int(DURATION_S)), sign, over, settle
        character(:), allocatable :: verdict
        integer                  :: t
        call step_response(start_c, setpoint_c, measured)
        call say("## climate chamber, " // fixed(start_c, 0, 0) // " degC -> " // fixed(setpoint_c, 0, 0) &
                 // " degC, one sample per second")
        call say("## '##' lines are for the reader: the comparison skips them.")
        call print_config()
        call print_sensors(setpoint_c)
        call print_cloud(measured, start_c, setpoint_c)
        call print_picture(measured, start_c, setpoint_c)
        ! How far in K the chamber went past the setpoint in the direction
        ! of travel; 0 where it never did.
        sign = merge(1.0_real64, -1.0_real64, setpoint_c > start_c)
        over = max(0.0_real64, maxval(sign * (measured - setpoint_c)))
        ! The time after which every sample stays within the band: the step
        ! after the last one outside.
        settle = 0.0_real64
        do t = ubound(measured, 1), 0, -1
            if( abs(measured(t) - setpoint_c) > BAND_K ) then
                settle = real(t, real64) + DT_S
                exit
            end if
        end do
        call say("overshoot  ((overshoot: " // fixed(over, 0, 2) // " K))          law <= 0.5 K")
        call say("settled    ((settle: " // fixed(settle, 0, 0) // " s))             law <= 4 min")
        verdict = merge("settled ", "drifting", abs(measured(ubound(measured, 1)) - setpoint_c) <= BAND_K)
        call say('chamber    ((verdict: "' // trim(verdict) // '"))')
    end subroutine

end module chamber_model

program chamber
    use, intrinsic :: iso_fortran_env, only: real64
    use chamber_model
    use hwut_text, only: say
    implicit none
    character(16) :: choice

    call random_init(repeatable = .false., image_distinct = .true.)
    call get_command_argument(1, choice)
    select case( trim(choice) )
    case( "heat" ); call run(20.0_real64, 40.0_real64)
    case( "cool" ); call run(40.0_real64, 20.0_real64)
    case default
        call say("choices: heat, cool")
        stop 1, quiet = .true.
    end select
    call say("<hwut-end>")
end program chamber
