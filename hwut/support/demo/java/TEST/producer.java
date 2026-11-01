/* ______________________________________________________________________________
 * THE PRODUCER OF 'protocol.sh clean' -- no test, a program the test runs.
 *
 *     java producer.java
 *
 * Five clients talk to a service at once, each in a thread of its own: a
 * request, a moment later its response; then the service shuts down. The
 * order of the lines is the scheduler's. It prints no '<hwut-end>': the
 * pype that reads it does, at '<eof>'.
 * ______________________________________________________________________________
 */
import java.util.ArrayList;
import java.util.List;
import java.util.Random;

final class Producer {
    static final Random RANDOM = new Random(System.nanoTime());

    /** RETURN: nothing; 'text' was printed as one line, at once, and no
     *          other thread's line ran into it. */
    static synchronized void say(String text) {
        System.out.println(text);
        System.out.flush();
    }

    /** RETURN: nothing; the current thread slept up to 20 ms, drawn at random. */
    static void pause() {
        try { Thread.sleep(RANDOM.nextInt(21)); }
        catch (InterruptedException error) { Thread.currentThread().interrupt(); }
    }

    public static void main(String[] args) throws InterruptedException {
        List<Thread> pool = new ArrayList<>();
        for (int n = 1; n <= 5; ++n) {
            final int id = n;
            pool.add(new Thread(() -> {
                pause(); say("request " + id);
                pause(); say("response " + id);
            }));
        }
        for (Thread t : pool) t.start();
        for (Thread t : pool) t.join();
        say("shutdown");
    }
}
