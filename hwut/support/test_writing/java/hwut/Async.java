/* SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: COROUTINES AS 'asyncio' RUNS THEM -- the part of asyncio the
 *          timeline ('TriggerDispatcher') and its tests stand on, for a
 *          language that has none.
 *
 *     Async.run(() -> { ... });                    asyncio.run(main())
 *     Async.sleep0();                              await asyncio.sleep(0)
 *     Async.Task t = Async.createTask(() -> ...);  asyncio.create_task(...)
 *     t.cancel();  t.await_();                     task.cancel(); await task
 *     Async.gather(a, b);                          await asyncio.gather(a(), b())
 *
 * A TASK IS A THREAD THAT RUNS ONLY WHEN IT HOLDS THE BATON: one task runs
 * at a time, from one yield to the next ('sleep0', 'await_', 'gather', its
 * end), and the loop hands the baton on in asyncio's order -- the ready
 * tasks first come, first served. So what a test prints is the same on
 * every run, as with asyncio: no two tasks ever run at once.
 *
 * A CANCELLED task is told at its next yield: 'sleep0' (or 'await_') throws
 * 'CancelledError' in it, which passes out of its function unless caught --
 * and 'await_' on that task throws 'CancelledError' too. A task cancelled
 * before it first ran never runs. What 'run' leaves unfinished is cancelled
 * before 'run' returns.
 * _____________________________________________________________________________
 */
package hwut;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.Semaphore;

public final class Async {
    /** WHAT A CANCELLED TASK IS TOLD -- asyncio's 'CancelledError'. */
    public static final class CancelledError extends RuntimeException {
        /** RETURN: CancelledError, without a message (as asyncio's). */
        public CancelledError() { super(null, null, false, false); }
    }

    /** ONE COROUTINE, running in the loop that made it. */
    public static final class Task {
        private final Loop       loop;
        private final Runnable   function;
        private final Semaphore  go = new Semaphore(0);
        private final List<Task> waiterList = new ArrayList<>();
        private boolean          doneF, cancelRequestedF, cancelledF;
        private Task             awaiting;          // the task this one awaits
        private Throwable        error;

        private Task(Loop loop, Runnable function) { this.loop = loop; this.function = function; }

        /** RETURN: boolean, true where the task has ended (returned, thrown,
         *          or been cancelled). */
        public boolean done() { synchronized (loop) { return doneF; } }

        /** RETURN: boolean, true where the task ended by its cancellation. */
        public boolean cancelled() { synchronized (loop) { return cancelledF; } }

        /** RETURN: boolean, true where the cancellation was requested now;
         *          false where the task had already ended. It is told at its
         *          next yield ('CancelledError'); a task that awaits another
         *          cancels that one, and is told when it ends (asyncio's
         *          way). */
        public boolean cancel() {
            synchronized (loop) {
                if (doneF) return false;
                if (awaiting != null && awaiting.cancel()) return true;
                cancelRequestedF = true;
                return true;
            }
        }

        /** RETURN: nothing, once the task has ended by returning;
         *          throws what it threw, 'CancelledError' where it was
         *          cancelled. The calling task yields until then. */
        public void await_() {
            Task self = current();
            boolean waitF;
            synchronized (loop) {
                waitF = !doneF;
                if (waitF) { waiterList.add(self); self.awaiting = this; }
            }
            if (waitF) {
                self.suspend(false);
                synchronized (loop) { self.awaiting = null; }
            } else self.checkCancel();
            synchronized (loop) {
                if (cancelledF)                                      throw new CancelledError();
                if (error instanceof RuntimeException e)             throw e;
                if (error instanceof Error e)                        throw e;
            }
        }

        /** RETURN: nothing; the task's function ran on its own thread, and
         *          its waiters are ready. Runs once the loop first hands it
         *          the baton. */
        private void body() {
            CURRENT.set(this);
            go.acquireUninterruptibly();
            try {
                checkCancel();
                function.run();
            } catch (CancelledError e) {
                synchronized (loop) { cancelledF = true; }
            } catch (Throwable e) {
                synchronized (loop) { error = e; }
            }
            synchronized (loop) {
                doneF = true;
                loop.ready.addAll(waiterList);
                waiterList.clear();
            }
            loop.back.release();
        }

        /** RETURN: nothing, once the loop hands the baton back to this task;
         *          throws CancelledError where it was cancelled meanwhile.
         *          'readyF': the task stands in the ready queue (a plain
         *          yield); else something else readies it. */
        private void suspend(boolean readyF) {
            synchronized (loop) { if (readyF) loop.ready.add(this); }
            loop.back.release();
            go.acquireUninterruptibly();
            checkCancel();
        }

        /** RETURN: nothing; throws CancelledError where cancellation was
         *          requested and not yet told. */
        private void checkCancel() {
            synchronized (loop) {
                if (!cancelRequestedF) return;
                cancelRequestedF = false;
            }
            throw new CancelledError();
        }
    }

    /** THE LOOP: the ready queue, and the baton's way back to it. */
    private static final class Loop {
        final ArrayDeque<Task> ready = new ArrayDeque<>();
        final List<Task>       all   = new ArrayList<>();
        final Semaphore        back  = new Semaphore(0);
    }

    private static final ThreadLocal<Task> CURRENT = new ThreadLocal<>();

    private Async() {}

    /** RETURN: nothing, once 'main' -- run as the loop's first task -- has
     *          returned; every task it left unfinished is then cancelled and
     *          run to its end. Throws what 'main' threw (CancelledError
     *          where it was cancelled). The calling thread is the loop. */
    public static void run(Runnable main) {
        Loop loop = new Loop();
        Task first = spawn(loop, main);
        schedule(loop, first);
        List<Task> left;
        synchronized (loop) { left = new ArrayList<>(loop.all); }
        for (Task t : left) t.cancel();
        schedule(loop, null);
        if (first.cancelled())                                  throw new CancelledError();
        if (first.error instanceof RuntimeException e)         throw e;
        if (first.error instanceof Error e)                    throw e;
    }

    /** RETURN: Task, 'function' as a task of the running loop, ready to run
     *          at the caller's next yield; throws IllegalStateException
     *          outside a loop. */
    public static Task createTask(Runnable function) {
        Task self = current();
        return spawn(self.loop, function);
    }

    /** RETURN: nothing, once the other ready tasks had their turn -- the
     *          yield 'await asyncio.sleep(0)' is; throws CancelledError
     *          where this task was cancelled meanwhile. */
    public static void sleep0() { current().suspend(true); }

    /** RETURN: nothing, once every function -- each made a task, in the
     *          order given -- has ended; throws the first one's error (in
     *          that order) where one threw. */
    public static void gather(Runnable... function) {
        List<Task> taskList = new ArrayList<>();
        for (Runnable f : function) taskList.add(createTask(f));
        for (Task t : taskList) t.await_();
    }

    /** RETURN: Task, the task the calling thread runs; throws
     *          IllegalStateException where it runs none. */
    private static Task current() {
        Task self = CURRENT.get();
        if (self == null) throw new IllegalStateException("no task runs here: call it within 'Async.run'");
        return self;
    }

    /** RETURN: Task, 'function' on a daemon thread of its own, in 'loop's
     *          ready queue, waiting for the baton. */
    private static Task spawn(Loop loop, Runnable function) {
        Task   task   = new Task(loop, function);
        Thread thread = new Thread(task::body, "hwut-async-task");
        thread.setDaemon(true);
        synchronized (loop) { loop.ready.add(task); loop.all.add(task); }
        thread.start();
        return task;
    }

    /** RETURN: nothing, once 'until' has ended -- or, 'until' null, once no
     *          task is ready any more. The baton goes to the ready tasks in
     *          turn; the loop waits for it to come back each time. */
    private static void schedule(Loop loop, Task until) {
        while (true) {
            Task next;
            synchronized (loop) {
                if (until != null && until.doneF) return;
                next = loop.ready.poll();
                if (next != null && next.doneF) continue;
            }
            if (next == null) {
                if (until == null) return;
                throw new IllegalStateException("deadlock: the main task waits, nothing is ready");
            }
            next.go.release();
            loop.back.acquireUninterruptibly();
        }
    }
}
