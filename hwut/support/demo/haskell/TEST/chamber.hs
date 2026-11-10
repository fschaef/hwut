-- @hwut {
--     title     = "Demo: a climate chamber's step response -- regions, units, a string law"
--     build     { framework = "make", target = "%.exe" }
--     tolerance { constraints = ["overshoot <= 0.5 K",
--                                "settle <= 4 min",
--                                "verdict == 'settled'"] }
--     choices {
--         heat { features = ["demo-haskell+cover-region-verbatim", "demo-haskell+cover-region-table", "demo-haskell+cover-region-point-cloud",
--                            "demo-haskell+cover-region-ignore", "demo-haskell+cover-laws-in-units", "demo-haskell+cover-string-binding",
--                            "demo-haskell+cover-test-level-tolerance", "demo-haskell+cover-annotation-lines"] }
--         cool { features = ["demo-haskell+cover-region-verbatim", "demo-haskell+cover-region-table", "demo-haskell+cover-region-point-cloud",
--                            "demo-haskell+cover-region-ignore", "demo-haskell+cover-laws-in-units", "demo-haskell+cover-string-binding",
--                            "demo-haskell+cover-test-level-tolerance", "demo-haskell+cover-annotation-lines"] }
--     }
-- }
--
-- _____________________________________________________________________________
-- SUBJECT  a climate chamber driven from one temperature to another by a PI
--          controller: its configuration, its sensors at the end, its step
--          response, and the three numbers its requirement names.
-- REQUIREMENT  The chamber reaches the setpoint within 4 minutes, overshoots
--              it by no more than 0.5 K, and reports itself 'settled'.
--
-- Every run is seeded by the clock: the sensors are noisy, the four sensor
-- rows come out in a different order, the calibration stamps are today's.
-- Both choices pass on every run anyway; each part of the output says how:
--
-- '##' lines     notes for the reader. The comparison skips them on both
--                sides, anywhere -- even inside a region.
--
-- verbatim       '##! verbatim' ... '####': the configuration as loaded. It is
--                YAML, where indentation is meaning, so nothing is tolerated:
--                no whitespace folding, no numeric band.
--
-- table          '##! table key=0 ignore=1 numeric={2:0.0005}': one row per
--                sensor, matched by its NAME (column 0) whatever the order;
--                column 1, the calibration stamp, is not compared; column 2,
--                the reading in K, within 0.05 %.
--
-- point-cloud    '##! point-cloud limit=0.5 constraint={...}': the step
--                response as points (t, T). Every point lies within 0.5 of a
--                point of the GOOD file ('limit'), AND every point keeps the
--                envelope stated in the region ('constraint') -- the GOOD's
--                points, too, so a GOOD that breaks its envelope is refused.
--
-- ignore         '##! ignore': a picture for the human eye. One noisy sample
--                moves a star; the picture's presence is compared, its
--                contents are not.
--
-- units          '((settle: 150 s))' is a quantity; the law says 'settle <= 4
--                min' and the comparison converts. A temperature DIFFERENCE is
--                printed in K, never in degC (an offset unit).
--
-- string law     '((verdict: "settled"))' binds a string; 'verdict ==
--                'settled'' judges it.
--
-- test-level     the three laws stand ONCE, in the header's own 'tolerance',
-- tolerance      and hold for both choices.
--
-- CHOICES  heat  20 degC -> 40 degC.
--          cool  40 degC -> 20 degC.
--
-- The configuration prints its numbers as the YAML the Python demonstration
-- loads -- '0.15', not Haskell's 'show' -- by the support's 'floatRepr'.
-- _____________________________________________________________________________
module Main (main) where

import Control.Monad      (forM_, when)
import Data.List          (sort)
import Data.Time          (defaultTimeLocale, formatTime, getZonedTime)
import System.Environment (getArgs)
import System.Exit        (ExitCode (..), exitWith)
import Text.Printf        (printf)

import ClockRandom
import Hwut.PyText        (floatRepr)

dtS, bandK, noiseK, tauS, rateKPerS, kp, ki :: Double
dtS       = 1.0       -- simulation step
bandK     = 0.3       -- 'settled' = within 0.3 K of the setpoint
noiseK    = 0.02      -- sensor noise, one sigma
tauS      = 300.0     -- the plant
rateKPerS = 0.15
kp        = 0.6       -- the controller
ki        = 0.01

durationS, sampleS :: Int
durationS = 400       -- simulated time
sampleS   = 20        -- one point of the cloud every 20 s

configText :: String
configText = unlines
    [ "chamber:"
    , "  plant:"
    , printf "    time_constant_s: %.0f" tauS
    , "    heater_rate_K_per_s: " ++ floatRepr rateKPerS
    , "  controller:"
    , "    kind: PI"
    , "    kp: " ++ floatRepr kp
    , "    ki: " ++ floatRepr ki
    , "    output: [-1.0, 1.0]"
    , "  sensors: [top, middle, bottom, door]" ]

-- | Offset of each sensor against the air in the middle of the chamber.
sensorOffsetList :: [(String, Double)]
sensorOffsetList = [("top", 0.10), ("middle", 0.00), ("bottom", -0.10), ("door", -0.40)]

-- | RETURN: IO [(Int, Double)], (t_s, measured_C), one sample per
--           simulation step, of the chamber driven from 'startC' to
--           'setpointC' by the PI controller of 'configText', with sensor
--           noise drawn from 'rng'.
stepResponse :: Rng -> Double -> Double -> IO [(Int, Double)]
stepResponse rng startC setpointC = go 0 startC 0.0
  where
    ambient = 20.0
    go t temp integral
        | t > durationS = return []
        | otherwise     = do
            noise <- gauss rng 0.0 noiseK
            let measured  = temp + noise
                err       = setpointC - measured
                output    = kp * err + ki * integral
                --  anti-windup: integrate only while unsaturated
                integral' = if -1.0 < output && output < 1.0 then integral + err * dtS else integral
                clamped   = max (-1.0) (min 1.0 output)
                temp'     = temp + dtS * ((ambient - temp) / tauS + rateKPerS * clamped)
            ((t, measured) :) <$> go (t + 1) temp' integral'

-- | RETURN: Double, how far in K the chamber went past 'setpointC' in the
--           direction of travel from 'startC'; 0.0 where it never did.
overshootK :: [(Int, Double)] -> Double -> Double -> Double
overshootK sampleList startC setpointC = max 0.0 (maximum [ sign * (temp - setpointC) | (_, temp) <- sampleList ])
  where sign = if setpointC > startC then 1.0 else -1.0

-- | RETURN: Double, the time in s after which every sample stays within
--           'bandK' of 'setpointC' (the step after the last one outside).
settleS :: [(Int, Double)] -> Double -> Double
settleS sampleList setpointC = case [ t | (t, temp) <- sampleList, abs (temp - setpointC) > bandK ] of
    []      -> 0.0
    outside -> fromIntegral (last outside) + dtS

-- | RETURN: IO (); the configuration as loaded, byte for byte, printed.
printConfig :: IO ()
printConfig = do
    putStrLn "configuration, as loaded (YAML: whitespace is meaning):"
    putStrLn "##! verbatim"
    putStr configText
    putStrLn "####"

-- | RETURN: IO (); one row per sensor printed, in a random order, with
--           today's calibration stamp and the reading at the end in K.
printSensors :: Rng -> Double -> IO ()
printSensors rng setpointC = do
    putStrLn "sensors at the end, in K (the order is the bus's):"
    putStrLn "    sensor  calibrated           reading_K"
    putStrLn "##! table key=0 ignore=1 numeric={2:0.0005}"
    nameList <- shuffle rng (map fst sensorOffsetList)
    stamp    <- formatTime defaultTimeLocale "%Y-%m-%dT%H:%M:%S" <$> getZonedTime
    forM_ nameList $ \name -> do
        noise <- gauss rng 0.0 noiseK
        let Just offset = lookup name sensorOffsetList
            reading     = setpointC + offset + noise + 273.15
        printf "    %-6s  %s  %9.2f\n" name stamp reading
    putStrLn "####"

-- | RETURN: IO (); the step response printed, one point (t_s, T_degC)
--           every 'sampleS', framed with the envelope the requirement allows.
printCloud :: [(Int, Double)] -> Double -> Double -> IO ()
printCloud sampleList startC setpointC = do
    let [low0, high0] = sort [startC, setpointC]
        (low, high)   = if setpointC > startC then (low0, high0 + 0.5) else (low0 - 0.5, high0)
    --  0.1 K beyond the envelope on either side: the sensor's noise.
    printf "step response, t in s against T in degC; envelope %.1f .. %.1f:\n" low high
    printf "##! point-cloud limit=0.5 constraint={y >= %.1f and y <= %.1f}\n" (low - 0.1) (high + 0.1)
    forM_ sampleList $ \(t, temp) ->
        when (t `mod` sampleS == 0) (printf "    %5d  %6.2f\n" t temp)
    putStrLn "####"

-- | RETURN: IO (); the step response printed as stars, for the human eye
--           only: one row per 40 s, one column per 0.5 K.
printPicture :: [(Int, Double)] -> Double -> Double -> IO ()
printPicture sampleList startC setpointC = do
    let low = min startC setpointC - 1.0
        column x = round ((x - low) / 0.5) :: Int
    putStrLn "the same, as a picture ('|' the setpoint):"
    putStrLn "##! ignore"
    forM_ sampleList $ \(t, temp) -> when (t `mod` 40 == 0) $ do
        let star = max 0 (min 45 (column temp))
            bar  = column setpointC
            row  = [ if i == star then '*' else if i == bar then '|' else ' ' | i <- [0 .. 45] ]
        printf "    %4d s  %s\n" t (reverse (dropWhile (== ' ') (reverse row)))
    putStrLn "####"

-- | RETURN: IO (); the chamber driven, every part of the report printed.
runChamber :: Double -> Double -> IO ()
runChamber startC setpointC = do
    rng        <- newRng
    sampleList <- stepResponse rng startC setpointC
    printf "## climate chamber, %.0f degC -> %.0f degC, one sample per second\n" startC setpointC
    putStrLn "## '##' lines are for the reader: the comparison skips them."
    printConfig
    printSensors rng setpointC
    printCloud sampleList startC setpointC
    printPicture sampleList startC setpointC
    let over    = overshootK sampleList startC setpointC
        settle  = settleS sampleList setpointC
        verdict = if abs (snd (last sampleList) - setpointC) <= bandK then "settled" else "drifting"
    printf "overshoot  ((overshoot: %.2f K))          law <= 0.5 K\n" over
    printf "settled    ((settle: %.0f s))             law <= 4 min\n" settle
    printf "chamber    ((verdict: \"%s\"))\n" (verdict :: String)

choiceList :: [(String, (Double, Double))]
choiceList = [("heat", (20.0, 40.0)), ("cool", (40.0, 20.0))]

-- | RETURN: IO (); the choice the command line names, run, then
--           '<hwut-end>'; exit 1 where none is named.
main :: IO ()
main = do
    arguments <- getArgs
    case arguments of
        (word : _) | Just (startC, setpointC) <- lookup word choiceList -> do
            runChamber startC setpointC
            putStrLn "<hwut-end>"
        _ -> do
            putStrLn "choices: heat, cool"
            exitWith (ExitFailure 1)
