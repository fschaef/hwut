/* ______________________________________________________________________________
 * THE SHOP'S FIXTURE -- no test, a helper the directory's 'hwut.conf' calls.
 *
 *     fixture.exe open            a fresh 'TMP/shop.db', stocked as below, and
 *                                 an empty 'TMP/frame.log' ('on_entry', and
 *                                 'hwut.execute fixture open')
 *     fixture.exe close           both removed ('on_exit')
 *     fixture.exe check <when> <app> [<choice>]
 *                                 'when' is 'before' or 'after': whether the
 *                                 stock adds up around the test run '<app>
 *                                 <choice>', appended to 'TMP/frame.log'
 *                                 ('on_before_test', 'on_after_test')
 *
 * 'hwut.conf' passes '<app>' and '<choice>' as '$HWUT_TEST $HWUT_CHOICE',
 * which hwut sets for the run the check stands around; a test without
 * choices has none. 'check' concerns the shop's tests alone. The stock
 * ADDS UP where every item's quantity is its opening quantity plus every
 * movement of the journal.
 *
 * 'make fixture.exe' builds it -- 'on_entry' does, before it opens the shop.
 * ______________________________________________________________________________
 */
import java.io.IOException;
import java.net.URISyntaxException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

final class Fixture {
    static final Path HERE     = here();
    static final Path DB_PATH  = HERE.resolve("TMP").resolve("shop.db");
    static final Path LOG_PATH = HERE.resolve("TMP").resolve("frame.log");
    static final Map<String, Integer> OPENING_DB = new LinkedHashMap<>();
    static { OPENING_DB.put("apple", 10); OPENING_DB.put("pear", 5); OPENING_DB.put("plum", 5); }
    static final Set<String> SHOP_TEST_SET = Set.of("delivery.json", "shop.java");

    /** RETURN: Path, the directory this program stands in -- the parent of
     *          the classes directory it runs from. */
    static Path here() {
        try { return Path.of(Fixture.class.getProtectionDomain().getCodeSource().getLocation().toURI()).getParent(); }
        catch (URISyntaxException error) { throw new IllegalStateException(error); }
    }

    /** RETURN: nothing; a fresh, stocked database and an empty log were written. */
    static void openShop() throws IOException {
        Files.createDirectories(DB_PATH.getParent());
        Files.deleteIfExists(DB_PATH);
        Files.deleteIfExists(LOG_PATH);
        try (Sqlite db = Sqlite.open(DB_PATH.toString(), 10000, null)) {
            db.execute("BEGIN");
            db.execute("CREATE TABLE opening (item TEXT PRIMARY KEY, qty INTEGER)");
            db.execute("CREATE TABLE stock   (item TEXT PRIMARY KEY, qty INTEGER)");
            db.execute("CREATE TABLE journal (item TEXT, delta INTEGER, source TEXT)");
            for (Map.Entry<String, Integer> e : OPENING_DB.entrySet()) {
                db.execute("INSERT INTO opening VALUES (?, ?)", e.getKey(), e.getValue());
                db.execute("INSERT INTO stock   VALUES (?, ?)", e.getKey(), e.getValue());
            }
            db.execute("COMMIT");
        }
        Files.write(LOG_PATH, new byte[0]);
    }

    /** RETURN: nothing; the database and the log are removed. */
    static void closeShop() throws IOException {
        Files.deleteIfExists(DB_PATH);
        Files.deleteIfExists(LOG_PATH);
    }

    /** RETURN: true, if every item's stock is its opening quantity plus its
     *          journal's movements;
     *          false, else. */
    static boolean addsUp() {
        try (Sqlite db = Sqlite.open(DB_PATH.toString(), 10000, null)) {
            List<List<Object>> rowList = db.query(
                "SELECT o.item, o.qty + COALESCE(SUM(j.delta), 0), s.qty"
                + "  FROM opening o JOIN stock s ON s.item = o.item"
                + "  LEFT JOIN journal j ON j.item = o.item GROUP BY o.item");
            for (List<Object> row : rowList) if (!row.get(1).equals(row.get(2))) return false;
            return true;
        }
    }

    /** RETURN: nothing; one line is appended to the log for a shop test run. */
    static void check(String when, String test, String choice) throws IOException {
        if (!SHOP_TEST_SET.contains(test)) return;
        String run  = (test + " " + choice).strip();
        String line = String.format("%-6s %-15s %s%n", when, run, addsUp() ? "stock adds up" : "STOCK BROKEN");
        Files.writeString(LOG_PATH, line, StandardCharsets.UTF_8, StandardOpenOption.CREATE, StandardOpenOption.APPEND);
    }

    public static void main(String[] args) throws IOException {
        String command = args.length > 0 ? args[0] : "";
        if      (command.equals("open"))                    openShop();
        else if (command.equals("close"))                   closeShop();
        else if (command.equals("check") && args.length >= 3) check(args[1], args[2], args.length > 3 ? args[3] : "");
        else {
            System.err.println("usage: fixture.exe open | close | check before|after <app> <choice>");
            System.exit(2);
        }
    }
}
