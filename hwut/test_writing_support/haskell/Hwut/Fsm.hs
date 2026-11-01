-- SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
-- _____________________________________________________________________________
--
-- PURPOSE: A STATE MACHINE AS A TEST'S MODEL OF THE SYSTEM UNDER TEST -- the
--          port of 'python/hwut_fsm.py' (see '../python/README-hwut_fsm.txt').
--
--     import Hwut.Fsm
--
--     case fromString defaultOptions protocolText of
--         Left problem   -> putStrLn ("FsmError: " ++ show problem)
--         Right machine  -> mapM_ putStrLn $ execFsm machine $ do
--             _ <- fire "request" (Line 1)       -- True
--             _ <- fire "release" (Line 2)       -- BREACH line 2: ...
--             _ <- report
--             return ()
--
-- THE MACHINE IS A VALUE, ITS RUN A PURE COMPUTATION. 'Machine' holds the
-- model and what was seen of it; an event fired is a transition of the value
-- -- the action 'fire' of the monad 'Fsm', a State over the machine. What
-- Python's machine WRITES (its 'write' callback, 'print' by default) is the
-- monad's LOG, a Writer: every breach line, model finding and report line in
-- order, and the test's own lines among them ('write'). 'execFsm' returns the
-- lines; the test prints them -- IO only at the edge.
--
-- WHAT PYTHON RAISES ('FsmError') is the monad's exception (ExceptT): where
-- the model is read ('fromString', a plain 'Either'), and where a mask names
-- a word the model never names. 'catchFsm' is Python's 'except FsmError'.
-- 'with m.disallowed(...)' is 'disallowed ... block': the mask stands for
-- the block, and is lifted on leaving it, also by an exception.
--
-- 'where' of Python -- an int names a line, a text stands as written, None
-- names no place -- is 'Where': 'Line 3', 'Place "phase"', 'Nowhere'.
-- _____________________________________________________________________________
module Hwut.Fsm
    ( -- * the model
      Machine
    , FsmError (..)
    , Options (..)
    , defaultOptions
    , Where (..)
    , Start (..)
    , newMachine
    , fromString
    , toString
      -- * the run
    , Fsm
    , runFsm
    , execFsm
    , write
    , catchFsm
    , getMachine
    , reset
    , fire
    , disallow
    , allow
    , forbid
    , permit
    , disallowed
    , forbidding
    , state
    , check
    , report
      -- * questions, answered by the value
    , breachN
    , current
    , inState
    , can
    , allowed
    , trace
    , forbiddenNow
    , pathTo
    , stateReachable
    , unreachable
    , deadEnds
    , forbiddenReachable
    ) where

import           Control.Monad        (forM, forM_, unless, when)
import           Control.Monad.Except (ExceptT, catchError, runExceptT, throwError)
import           Control.Monad.State  (StateT, get, modify, put, runStateT)
import           Control.Monad.Writer (Writer, runWriter, tell)
import           Data.Char            (isAlpha, isAlphaNum, isSpace)
import           Data.List            (intercalate, isPrefixOf, sort, sortOn)
import qualified Data.Map.Strict      as Map
import           Data.Maybe           (fromMaybe, isJust, isNothing)
import qualified Data.Set             as Set

type StateName = String
type Event     = String

-- | A model that cannot be meant -- named with its line where read from text.
newtype FsmError = FsmError String

instance Show FsmError where
    show (FsmError message) = message

-- | The place a breach line names.
data Where = Nowhere | Line Int | Place String
    deriving (Eq, Ord)

-- | Where 'pathTo' begins: the initial state, where the machine stands now,
--   or a state named.
data Start = FromInitial | FromNow | From StateName

-- | How a model is read: DFA (one way per event) or not; the machine's name
--   in 'report'.
data Options = Options { dfaF :: Bool, machineName :: String }

-- | RETURN: Options, a DFA named "fsm".
defaultOptions :: Options
defaultOptions = Options True "fsm"

-- | The model, and what was seen of it.
data Machine = Machine
    { name            :: String
    , dfa             :: Bool
    , edgeDb          :: Map.Map (StateName, Event) (Set.Set StateName)
    , initial         :: StateName
    , modelForbidden  :: Set.Set StateName
    , final           :: Set.Set StateName
    , stateList       :: [StateName]                          -- sorted
    , eventList       :: [Event]                              -- sorted
    , maskDb          :: Map.Map (Maybe StateName, Event) Where
    , forbidDb        :: Map.Map StateName Where              -- forbidden now -> since
    , permitDb        :: Map.Map StateName Where
    , currentSet      :: Set.Set StateName
    , visitDb         :: Map.Map StateName Int
    , takenDb         :: Map.Map (StateName, Event, StateName) Int
    , traceReversed   :: [(Where, StateName, Event, StateName)]
    , breachN         :: Int                                  -- ^ breaches seen
    }

-- ------------------------------------------------------------------- reading

-- | RETURN: Either FsmError Machine, the machine over the (state, event,
--           state) triples, standing in 'initial', if success; Left, a DFA
--           with two transitions for one (state, event), or a forbidden or
--           final state no transition names. 'states' names states no
--           transition touches.
newMachine :: Options -> [(StateName, Event, StateName)] -> StateName -> [StateName]
           -> [StateName] -> [StateName] -> Either FsmError Machine
newMachine options triples initial' forbidden' final' states = do
    edges <- foldlM' addEdge Map.empty triples
    let stateSet = Set.unions [ Set.fromList (initial' : states)
                              , Set.fromList (concat [ [s, t] | (s, _, t) <- triples ]) ]
        forbiddenSet = Set.fromList forbidden'
        finalSet     = Set.fromList final'
    forM_ [("forbidden", forbiddenSet), ("final", finalSet)] $ \(label, chosen) -> do
        let unknown = Set.toAscList (chosen `Set.difference` stateSet)
        unless (null unknown) $
            Left (FsmError (label ++ " state(s) " ++ intercalate ", " (map quoted unknown)
                            ++ ": named nowhere else in the model"))
    return $ resetMachine Machine
        { name           = machineName options
        , dfa            = dfaF options
        , edgeDb         = edges
        , initial        = initial'
        , modelForbidden = forbiddenSet
        , final          = finalSet
        , stateList      = Set.toAscList (stateSet `Set.union` forbiddenSet)
        , eventList      = Set.toAscList (Set.fromList (map snd (Map.keys edges)))
        , maskDb = Map.empty, forbidDb = Map.empty, permitDb = Map.empty
        , currentSet = Set.empty, visitDb = Map.empty, takenDb = Map.empty
        , traceReversed = [], breachN = 0
        }
  where
    addEdge db (source, event, target) =
        let targets = Map.findWithDefault Set.empty (source, event) db
        in if dfaF options && not (Set.null targets) && target `Set.notMember` targets
               then Left (FsmError ("'" ++ source ++ "' --(" ++ event ++ ")--> '"
                                    ++ Set.findMin targets ++ "' and '" ++ target
                                    ++ "': a DFA moves one way per event -- or 'DFA=False'"))
               else Right (Map.insert (source, event) (Set.insert target targets) db)
    foldlM' f z xs = foldl (\acc x -> acc >>= \a -> f a x) (Right z) xs

-- | RETURN: Either FsmError Machine, the model the text states, if success;
--           Left naming the line, else. One statement per line, '#' starts a
--           comment:
--
--   > initial: A          forbidden: X, Y          final: A, B
--   > state A
--   > A ---( ev )---> B ---( ev2 )---> C
--   > :  ---( ev )---> D     (':' -- the state that began the line above)
fromString :: Options -> String -> Either FsmError Machine
fromString options text = go (zip [1 ..] (lines text)) [] Map.empty Map.empty Nothing Nothing
  where
    go :: [(Int, String)] -> [(StateName, Maybe (Event, StateName))] -> Map.Map String [StateName]
       -> Map.Map (StateName, Event) (StateName, Int) -> Maybe StateName -> Maybe StateName
       -> Either FsmError Machine
    go [] tripleList declared _ first _ = do
        when (isNothing first && Map.notMember "initial" declared) $
            Left (FsmError "the model names no state")
        let initial' = case Map.lookup "initial" declared of
                           Just (s : _) -> s
                           _            -> fromMaybe "" first
            ordered  = reverse tripleList
        newMachine options [ (s, e, t) | (s, Just (e, t)) <- ordered ] initial'
                   (Map.findWithDefault [] "forbidden" declared)
                   (Map.findWithDefault [] "final" declared)
                   [ s | (s, Nothing) <- ordered ]
    go ((number, raw) : rest) tripleList declared lineOf first previousHead
        | null line = go rest tripleList declared lineOf first previousHead
        | Just (word, after) <- keyOf line = do
            nameList <- forM (filter (not . null . strip) (splitOn ',' after)) (nameOf number)
            when (word == "initial" && length nameList /= 1) $
                Left (FsmError ("line " ++ show number ++ ": 'initial:' names one state"))
            go rest tripleList (Map.insertWith (flip (++)) word nameList declared) lineOf first previousHead
        | [_] <- parts = do
            hd <- nameOf number line
            go rest ((hd, Nothing) : tripleList) declared lineOf (first `orElse` hd) (Just hd)
        | otherwise = do
            when (any (null . strip) (odds parts)) $
                Left (FsmError ("line " ++ show number ++ ": an arrow names no event -- '---( event )--->'"))
            hd <- case strip (head parts) of
                ":" -> maybe (Left (FsmError ("line " ++ show number ++ ": ':' stands for the state of "
                                              ++ "the line above, and none stands there")))
                             Right previousHead
                headText -> nameOf number headText
            (tripleList', lineOf') <- chain number hd (pairs (tail parts)) tripleList lineOf
            go rest tripleList' declared lineOf' (first `orElse` hd) (Just hd)
      where
        line  = strip (takeWhile (/= '#') raw)
        parts = splitArrows line

    chain _ _ [] tripleList lineOf = Right (tripleList, lineOf)
    chain number source ((eventText, targetText) : rest) tripleList lineOf = do
        target <- nameOf number targetText
        let event = strip eventText
        case Map.lookup (source, event) lineOf of
            Just (before, beforeLine) | dfaF options && before /= target ->
                Left (FsmError ("line " ++ show number ++ ": '" ++ source ++ "' --(" ++ event
                                ++ ")--> '" ++ target ++ "', and line " ++ show beforeLine
                                ++ ": --> '" ++ before ++ "' -- a DFA moves one way per event, or 'DFA=False'"))
            _ -> chain number target rest ((source, Just (event, target)) : tripleList)
                       (Map.insertWith (\_ old -> old) (source, event) (target, number) lineOf)

    orElse (Just x) _ = Just x
    orElse Nothing  y = Just y
    odds (_ : x : xs) = x : odds xs
    odds _            = []
    pairs (a : b : xs) = (a, b) : pairs xs
    pairs _            = []

-- | RETURN: Maybe (String, String), the keyword and the rest of a line
--           'initial: A' / 'forbidden: X, Y' / 'final: A' -- Nothing where
--           the line is none of them.
keyOf :: String -> Maybe (String, String)
keyOf line = case [ (w, drop (length w) line) | w <- ["initial", "forbidden", "final"], w `isPrefixOf` line ] of
    ((w, after) : _) -> case dropWhile isSpace after of
        (':' : value) -> Just (w, dropWhile isSpace value)
        _             -> Nothing
    [] -> Nothing

-- | RETURN: Either FsmError StateName, the state 'text' names -- 'A' or
--           'state A' -- if success; Left naming line 'number', else.
nameOf :: Int -> String -> Either FsmError StateName
nameOf number text
    | Just after <- stripStatePrefix t, isName after = Right after
    | isName t                                       = Right t
    | otherwise = Left (FsmError ("line " ++ show number ++ ": '" ++ t
                                  ++ "' names no state -- a state is a word ('A', 'state A')"))
  where
    t = strip text
    stripStatePrefix s
        | "state" `isPrefixOf` s, (c : _) <- drop 5 s, isSpace c = Just (dropWhile isSpace (drop 5 s))
        | otherwise = Nothing
    isName (c : cs) = (isAlpha c || c == '_') && all (\x -> isAlphaNum x || x `elem` "_.-") cs
    isName []       = False

-- | RETURN: [String], the line split at its arrows -- '-+ ( event ) -*>',
--           blanks allowed around the parentheses -- as a regex 'split' with
--           one group splits: [state, event, state, event, state ...].
splitArrows :: String -> [String]
splitArrows = go ""
  where
    go before [] = [reverse before]
    go before s@(c : cs)
        | c == '-', Just (event, after) <- arrowAt s = reverse before : event : go "" after
        | otherwise = go (c : before) cs
    arrowAt s = do
        let afterDashes = dropWhile isSpace (dropWhile (== '-') s)
        ('(' : inside) <- Just afterDashes
        let (content, closing) = break (`elem` "()") inside
        (')' : after) <- Just closing
        ('>' : rest) <- Just (dropWhile (== '-') (dropWhile isSpace after))
        return (strip content, rest)

-- | RETURN: String, the model in the text 'fromString' reads, one
--           transition per line, sorted.
toString :: Machine -> String
toString m = intercalate "\n" $
       [ "initial: " ++ initial m ]
    ++ [ "forbidden: " ++ intercalate ", " (Set.toAscList (modelForbidden m)) | not (Set.null (modelForbidden m)) ]
    ++ [ "final: " ++ intercalate ", " (Set.toAscList (final m)) | not (Set.null (final m)) ]
    ++ [ source ++ " ---( " ++ event ++ " )---> " ++ target | (source, event, target) <- allEdges m ]
    ++ [ "state " ++ s | s <- stateList m, s `Set.notMember` named, s `Set.notMember` modelForbidden m ]
  where
    named = Set.fromList (initial m : concat [ [s, t] | (s, _, t) <- allEdges m ])

-- ------------------------------------------------------------------- the run

-- | A run of a machine: its state, the lines it writes, FsmError raised.
type Fsm = ExceptT FsmError (StateT Machine (Writer [String]))

-- | RETURN: (Either FsmError a, Machine, [String]), what 'action' returned
--           (or raised), the machine after it, and every line written.
runFsm :: Machine -> Fsm a -> (Either FsmError a, Machine, [String])
runFsm m action = let ((result, m'), written) = runWriter (runStateT (runExceptT action) m)
                  in (result, m', written)

-- | RETURN: [String], every line 'action' wrote; an FsmError it did not
--           catch ends the list with 'FsmError: <text>'.
execFsm :: Machine -> Fsm a -> [String]
execFsm m action = case runFsm m action of
    (Left problem, _, written) -> written ++ ["FsmError: " ++ show problem]
    (Right _, _, written)      -> written

-- | RETURN: Fsm (); 'line' is written -- by the machine, or by the test
--           among the machine's lines.
write :: String -> Fsm ()
write line = tell [line]

-- | RETURN: Fsm a, 'action', or 'handler' with the FsmError it raised.
catchFsm :: Fsm a -> (FsmError -> Fsm a) -> Fsm a
catchFsm = catchError

-- | RETURN: Fsm Machine, the machine as it stands.
getMachine :: Fsm Machine
getMachine = get

-- | RETURN: Machine, standing in its initial state under the model as
--           written: what was seen, every mask and every state forbidden or
--           permitted since, forgotten.
resetMachine :: Machine -> Machine
resetMachine m = m
    { maskDb        = Map.empty
    , forbidDb      = Map.fromSet (const Nowhere) (modelForbidden m)
    , permitDb      = Map.empty
    , currentSet    = Set.singleton (initial m)
    , visitDb       = Map.singleton (initial m) 1
    , takenDb       = Map.empty
    , traceReversed = []
    , breachN       = 0
    }

-- | RETURN: Fsm (); the machine is reset ('resetMachine').
reset :: Fsm ()
reset = modify resetMachine

-- | RETURN: Fsm Bool, True where 'event' moved the machine and entered no
--           forbidden state; False where it was not allowed where the
--           machine stands -- a BREACH line is written and the machine stays
--           -- or where it entered a forbidden state, which is written too.
fire :: Event -> Where -> Fsm Bool
fire event at = do
    m <- get
    let sources = Set.toAscList (currentSet m)
        maskedList = [ s | s <- sources, maskedF m s event, Map.member (s, event) (edgeDb m) ]
        moves = [ (s, t) | s <- sources, not (maskedF m s event)
                         , t <- Set.toAscList (Map.findWithDefault Set.empty (s, event) (edgeDb m)) ]
    if null moves
        then do
            let hint
                    | event `notElem` eventList m = "an event the model never names"
                    | (s : _) <- maskedList =
                        "disallowed" ++ sinceText (fromMaybe Nowhere
                            (Map.lookup (Just s, event) (maskDb m) `orElse` Map.lookup (Nothing, event) (maskDb m)))
                    | not (null (allowed m)) = "allowed: " ++ intercalate ", " (allowed m)
                    | otherwise = "no event leaves it"
            put m { breachN = breachN m + 1 }
            write ("BREACH" ++ whereText at ++ ": '" ++ event ++ "' in " ++ here m ++ " -- " ++ hint)
            return False
        else do
            let moved   = Set.fromList (map snd moves)
                taken   = foldl (\db (s, t) -> Map.insertWith (+) (s, event, t) 1 db) (takenDb m) moves
                visits  = foldl (\db s -> Map.insertWith (+) s 1 db) (visitDb m) (Set.toList moved)
                entered = Set.toAscList (moved `Set.intersection` forbiddenNow m)
            put m { currentSet = moved, takenDb = taken, visitDb = visits
                  , traceReversed = reverse [ (at, s, event, t) | (s, t) <- moves ] ++ traceReversed m
                  , breachN = breachN m + length entered }
            forM_ entered $ \s -> do
                let since = Map.findWithDefault Nowhere s (forbidDb m)
                write ("BREACH" ++ whereText at ++ ": '" ++ s ++ "' entered by '" ++ event ++ "' -- "
                       ++ (if s `Set.member` modelForbidden m && since == Nowhere
                               then "a forbidden state" else "forbidden" ++ sinceText since))
            return (null entered)
  where
    orElse (Just x) _ = Just x
    orElse Nothing  y = y

-- ------------------------------------------------------- the law, changing

-- | RETURN: Fsm (), if 'event' and 'state' are named by the model; raises
--           FsmError naming what is not, else.
known :: Maybe Event -> Maybe StateName -> Fsm ()
known event state' = do
    m <- get
    forM_ event $ \e -> unless (e `elem` eventList m) $
        throwError (FsmError ("'" ++ e ++ "': an event the model never names -- events: "
                              ++ intercalate ", " (eventList m)))
    forM_ state' $ \s -> unless (s `elem` stateList m) $
        throwError (FsmError ("'" ++ s ++ "': a state the model never names -- states: "
                              ++ intercalate ", " (stateList m)))

-- | RETURN: Fsm (); from now on 'event' is a breach -- in the state given,
--           or in every state where Nothing -- until 'allow'; the breach line
--           says 'disallowed since <at>'. Raises FsmError where the model
--           names no such event or state.
disallow :: Event -> Maybe StateName -> Where -> Fsm ()
disallow event state' at = do
    known (Just event) state'
    modify $ \m -> m { maskDb = Map.insertWith (\_ old -> old) (state', event) at (maskDb m) }

-- | RETURN: Fsm (); the mask 'disallow event state' set is lifted; a mask of
--           another scope stays. Raises FsmError where the model names no
--           such event or state.
allow :: Event -> Maybe StateName -> Where -> Fsm ()
allow event state' _ = do
    known (Just event) state'
    modify $ \m -> m { maskDb = Map.delete (state', event) (maskDb m) }

-- | RETURN: Fsm (); from now on entering 'state' is a breach, until
--           'permit'. Where the machine STANDS in it, one BREACH line is
--           written at once. Raises FsmError where the model names no such
--           state.
forbid :: StateName -> Where -> Fsm ()
forbid s at = do
    known Nothing (Just s)
    m <- get
    unless (Map.member s (forbidDb m)) $ do
        put m { forbidDb = Map.insert s at (forbidDb m), permitDb = Map.delete s (permitDb m) }
        when (s `Set.member` currentSet m) $ do
            modify $ \m' -> m' { breachN = breachN m' + 1 }
            write ("BREACH" ++ whereText at ++ ": stands in '" ++ s ++ "' -- forbidden" ++ sinceText at)

-- | RETURN: Fsm (); 'state' is no longer forbidden -- one of the model's own
--           'forbidden:' too, until 'forbid' again. Raises FsmError where the
--           model names no such state.
permit :: StateName -> Where -> Fsm ()
permit s at = do
    known Nothing (Just s)
    m <- get
    when (Map.member s (forbidDb m)) $
        put m { forbidDb = Map.delete s (forbidDb m)
              , permitDb = if s `Set.member` modelForbidden m then Map.insert s at (permitDb m)
                                                               else permitDb m }

-- | RETURN: Fsm a, 'block' run with 'event' disallowed (see 'disallow'),
--           allowed again on leaving it -- also by an FsmError.
disallowed :: Event -> Maybe StateName -> Where -> Fsm a -> Fsm a
disallowed event state' at = phase (disallow event state' at) (allow event state' Nowhere)

-- | RETURN: Fsm a, 'block' run with 'state' forbidden (see 'forbid'),
--           permitted again on leaving it -- also by an FsmError.
forbidding :: StateName -> Where -> Fsm a -> Fsm a
forbidding s at = phase (forbid s at) (permit s Nowhere)

-- | RETURN: Fsm a, 'block' between 'enter' and 'leave'; 'leave' also where
--           the block raised, the error passed on.
phase :: Fsm () -> Fsm () -> Fsm a -> Fsm a
phase enter leave block = do
    enter
    result <- block `catchError` (\problem -> leave >> throwError problem)
    leave
    return result

-- --------------------------------------------------------------- questions

-- | RETURN: Fsm StateName, the one state the machine stands in, if success;
--           raises FsmError where a set of states stands (DFA off).
state :: Fsm StateName
state = do
    m <- get
    case Set.toList (currentSet m) of
        [s] -> return s
        _   -> throwError (FsmError ("the machine stands in " ++ here m ++ ": ask 'current()'"))

-- | RETURN: Set StateName, every state the machine stands in.
current :: Machine -> Set.Set StateName
current = currentSet

-- | RETURN: Bool, True where the machine stands in 'state'.
inState :: StateName -> Machine -> Bool
inState s m = s `Set.member` currentSet m

-- | RETURN: Bool, True where 'event' would move the machine now.
can :: Event -> Machine -> Bool
can event m = any (\s -> Map.member (s, event) (edgeDb m) && not (maskedF m s event))
                  (Set.toList (currentSet m))

-- | RETURN: [Event], the events that would move the machine now, sorted.
allowed :: Machine -> [Event]
allowed m = Set.toAscList (Set.fromList [ e | (s, e) <- Map.keys (edgeDb m)
                                            , s `Set.member` currentSet m, not (maskedF m s e) ])

-- | RETURN: [(Where, StateName, Event, StateName)], every transition fired,
--           in order.
trace :: Machine -> [(Where, StateName, Event, StateName)]
trace = reverse . traceReversed

-- | RETURN: Set StateName, the states forbidden NOW.
forbiddenNow :: Machine -> Set.Set StateName
forbiddenNow = Map.keysSet . forbidDb

-- | RETURN: Bool, True where 'event' is disallowed in 'state' now -- in
--           every state, or in that one.
maskedF :: Machine -> StateName -> Event -> Bool
maskedF m s event = Map.member (Nothing, event) (maskDb m) || Map.member (Just s, event) (maskDb m)

-- | RETURN: String, where the machine stands: "'idle'", or "{'a', 'b'}".
here :: Machine -> String
here m = case Set.toAscList (currentSet m) of
    [s] -> quoted s
    ss  -> "{" ++ intercalate ", " (map quoted ss) ++ "}"

-- ----------------------------------------------------------- the model alone

-- | RETURN: Map StateName [(Event, StateName)], the transitions leaving each
--           state, sorted -- under the masks where 'maskedFlag', as written
--           else.
successorDb :: Bool -> Machine -> Map.Map StateName [(Event, StateName)]
successorDb maskedFlag m = Map.map sort $ Map.fromListWith (++)
    [ (source, [(event, target)]) | ((source, event), targets) <- Map.toList (edgeDb m)
                                  , not (maskedFlag && maskedF m source event)
                                  , target <- Set.toList targets ]

-- | RETURN: Maybe [Event], the shortest sequence of events from 'start' into
--           'goal' -- the first in event order among equally short ones, []
--           where 'start' is 'goal'; Nothing where 'goal' cannot be reached.
--           Under the masks standing now where 'maskedFlag'.
pathTo :: Start -> Bool -> StateName -> Machine -> Maybe [Event]
pathTo start maskedFlag goal m
    | goal `Set.member` startSet = Just []
    | otherwise                  = bfs [ (s, []) | s <- Set.toAscList startSet ] startSet
  where
    startSet = case start of
        FromNow     -> currentSet m
        FromInitial -> Set.singleton (initial m)
        From s      -> Set.singleton s
    successors = successorDb maskedFlag m
    bfs [] _ = Nothing
    bfs ((hereState, path) : queue) seen = visit (Map.findWithDefault [] hereState successors) queue seen
      where
        visit [] queue' seen' = bfs queue' seen'
        visit ((event, target) : rest) queue' seen'
            | target `Set.member` seen' = visit rest queue' seen'
            | target == goal            = Just (reverse (event : path))
            | otherwise                 = visit rest (queue' ++ [(target, event : path)]) (Set.insert target seen')

-- | RETURN: Bool, True where 'goal' can be reached from 'start' ('pathTo').
stateReachable :: Start -> Bool -> StateName -> Machine -> Bool
stateReachable start maskedFlag goal m = isJust (pathTo start maskedFlag goal m)

-- | RETURN: Set StateName, the states forbidden now where 'maskedFlag', the
--           model's own else.
forbiddenOf :: Bool -> Machine -> Set.Set StateName
forbiddenOf maskedFlag m = if maskedFlag then forbiddenNow m else modelForbidden m

-- | RETURN: [StateName], the states no path from the initial state reaches,
--           forbidden ones left out -- sorted.
unreachable :: Bool -> Machine -> [StateName]
unreachable maskedFlag m = [ s | s <- stateList m, s `Set.notMember` forbiddenOf maskedFlag m
                               , not (stateReachable FromInitial maskedFlag s m) ]

-- | RETURN: [StateName], the states no event leaves that are neither final
--           nor forbidden -- where a system would hang -- sorted.
deadEnds :: Bool -> Machine -> [StateName]
deadEnds maskedFlag m = [ s | s <- stateList m, Map.notMember s successors
                            , s `Set.notMember` final m, s `Set.notMember` forbiddenOf maskedFlag m ]
  where successors = successorDb maskedFlag m

-- | RETURN: [StateName], the forbidden states the model lets the system
--           reach from the initial state -- sorted.
forbiddenReachable :: Bool -> Machine -> [StateName]
forbiddenReachable maskedFlag m = [ s | s <- Set.toAscList (forbiddenOf maskedFlag m)
                                      , stateReachable FromInitial maskedFlag s m ]

-- | RETURN: Fsm Int, how many findings the MODEL has, each written as one
--           line 'MODEL: ...'; 0 where it has none. Under the masks standing
--           now where 'maskedFlag'.
check :: Bool -> Fsm Int
check maskedFlag = do
    m <- get
    let found = [ "MODEL: '" ++ s ++ "' cannot be reached" | s <- unreachable maskedFlag m ]
             ++ [ "MODEL: '" ++ s ++ "' is a dead end -- no event leaves it" | s <- deadEnds maskedFlag m ]
             ++ [ "MODEL: forbidden '" ++ s ++ "' is reachable: "
                  ++ unwords (fromMaybe [] (pathTo FromInitial maskedFlag s m))
                | s <- forbiddenReachable maskedFlag m ]
    mapM_ write found
    return (length found)

-- ------------------------------------------------------------------ the end

-- | RETURN: Fsm Int, the breaches seen, counting a non-final end; written
--           before, sorted, what the events covered of the model -- states
--           counted without the forbidden ones -- and what still stands of
--           the changing law.
report :: Fsm Int
report = do
    m <- get
    let edges   = allEdges m
        endF    = Set.null (final m) || not (Set.null (currentSet m `Set.intersection` final m))
        n       = breachN m + (if endF then 0 else 1)
        goal    = [ s | s <- stateList m, s `Set.notMember` modelForbidden m ]
        visited = [ s | s <- goal, Map.member s (visitDb m) ]
    write (name m ++ ": " ++ show (length visited) ++ " of " ++ show (length goal) ++ " states visited, "
           ++ show (Map.size (takenDb m)) ++ " of " ++ show (length edges) ++ " transitions taken, "
           ++ show n ++ " breach" ++ (if n == 1 then "" else "es"))
    forM_ edges $ \edge@(source, event, target) -> do
        let taken = Map.findWithDefault 0 edge (takenDb m)
        write ("  " ++ (if taken > 0 then "taken    " else "not taken") ++ "  " ++ source ++ " ---( "
               ++ event ++ " )---> " ++ target ++ (if taken > 1 then "   x" ++ show taken else ""))
    forM_ (stateList m) $ \s ->
        when (Map.notMember s (visitDb m) && s `Set.notMember` modelForbidden m) $
            write ("  never in   " ++ quoted s)
    write ("  ended in   " ++ here m)
    forM_ (sortOn (\((s, e), _) -> (e, fromMaybe "" s)) (Map.toList (maskDb m))) $ \((s, e), since) ->
        write ("  disallowed '" ++ e ++ "' " ++ maybe "in every state" (\x -> "in " ++ quoted x) s
               ++ sinceText since)
    forM_ (Map.toAscList (forbidDb m)) $ \(s, since) ->
        when (s `Set.notMember` modelForbidden m) $ write ("  forbidden  " ++ quoted s ++ sinceText since)
    forM_ (Map.toAscList (permitDb m)) $ \(s, since) ->
        write ("  permitted  " ++ quoted s ++ sinceText since)
    unless endF $
        write ("BREACH: ended in " ++ here m ++ " -- final: " ++ intercalate ", " (Set.toAscList (final m)))
    return n

-- -------------------------------------------------------------------- texts

-- | RETURN: [(StateName, Event, StateName)], every transition, sorted.
allEdges :: Machine -> [(StateName, Event, StateName)]
allEdges m = [ (s, e, t) | ((s, e), targets) <- Map.toAscList (edgeDb m), t <- Set.toAscList targets ]

-- | RETURN: String, ' line 3', ' <text>', or '' -- the place a breach names.
whereText :: Where -> String
whereText Nowhere    = ""
whereText (Line n)   = " line " ++ show n
whereText (Place t)  = " " ++ t

-- | RETURN: String, ' since line 9', ' since <text>', or ''.
sinceText :: Where -> String
sinceText Nowhere = ""
sinceText at      = " since" ++ whereText at

-- | RETURN: String, the name in single quotes.
quoted :: String -> String
quoted s = "'" ++ s ++ "'"

-- | RETURN: String, without the blanks at both ends.
strip :: String -> String
strip = dropWhile isSpace . reverse . dropWhile isSpace . reverse

-- | RETURN: [String], the text split at every 'separator'.
splitOn :: Char -> String -> [String]
splitOn separator text = case break (== separator) text of
    (piece, [])       -> [piece]
    (piece, _ : rest) -> piece : splitOn separator rest
