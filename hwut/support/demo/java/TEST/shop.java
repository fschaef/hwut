/* @hwut {
 *     title     = "Demo: a shop's stock -- what the directory's hwut.conf arranges"
 *     build     { framework = "make", target = "%.exe" }
 *     tolerance { stderr_ignored = true }
 *     choices {
 *         sell   { features = ["demo-java+cover-unordered-table", "demo-java+cover-stderr-ignored", "demo-java+cover-collision"] }
 *         report { features = ["demo-java+cover-output-file", "demo-java+cover-keyed-table-separator", "demo-java+cover-dependency",
 *                              "demo-java+cover-frame-scripts", "demo-java+cover-test-scripts", "demo-java+cover-stderr-ignored"]
 *                  output   = ["<stdout>", "stock.csv"] }
 *     }
 * }
 * ______________________________________________________________________________
 * SUBJECT  the stock of a small shop, kept in an SQLite database: a delivery
 *          comes in, three clerks sell at once, and the stock is reported.
 * REQUIREMENT  Every movement of the stock is journalled, so that the stock
 *              always ADDS UP: opening quantity plus the journal's movements.
 *
 * THE DIRECTORY ARRANGES WHAT NO SINGLE TEST CAN -- in 'hwut.conf' beside
 * this file, read it first. hwut, when it enters this directory:
 *
 *     on_entry        'make fixture.exe shop.exe', then 'fixture.exe open': a
 *                     fresh 'TMP/shop.db', stocked
 *     on_before_test  'fixture.exe check before $HWUT_TEST $HWUT_CHOICE',
 *     on_after_test   'fixture.exe check after ...': around every test run,
 *                     whether the stock adds up, into 'TMP/frame.log' --
 *                     hwut sets the two variables for the run
 *     on_exit         'fixture.exe close'
 *     apps            'delivery.json' is a test, though it carries no
 *                     header: JSON has no comment to carry one. 'admit'
 *                     takes it out of the files hwut ignores by default
 *                     ('*.json'); 'execute' says how it is run --
 *                     'shop.exe deliver delivery.json'.
 *     collision       'delivery.json' and 'shop.java sell' both write the
 *                     database. SQLite lets one writer at a time hold the
 *                     file; one that waits too long fails with 'database
 *                     is locked'. hwut never runs the two at once.
 *     dependency      'shop.java report' runs after both, whatever their
 *                     verdict: it reports what they left.
 *
 * SQLITE is the library itself, called through 'Sqlite.java' beside this
 * file (Java brings no SQLite; see there).
 *
 * STDERR  Every SQL statement is logged on stderr, as a server would. A
 * word on stderr fails a run ('unexpected stderr') unless the header says
 * 'stderr_ignored = true': the words there are on purpose, and no error.
 *
 * CHOICES
 *
 * sell     three clerks sell at once, each in a thread of its own. The sales
 *          are printed as '##! table unordered sep={;}': rows of 'item;qty',
 *          in any order -- and no column is a key, 'apple;1' stands four
 *          times.
 *
 * report   the stock, as '##! table key=0 sep={;}', and the same rows
 *          written to 'stock.csv': 'output' names the file, hwut reads it
 *          after the run and compares it with its own GOOD. Then the frame
 *          log of the shop's tests: what 'on_before_test' and 'on_after_test'
 *          found around the delivery and the sale ('##! potpourri': which
 *          ran first is free), and before this report.
 *
 * deliver  (no choice -- 'execute' of 'delivery.json' calls it) books a
 *          delivery note: every line on the stock and into the journal, in
 *          one transaction.
 * ______________________________________________________________________________
 */
import java.io.IOException;
import java.net.URISyntaxException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

final class Shop {
    static final Path HERE     = here();
    static final Path DB_PATH  = HERE.resolve("TMP").resolve("shop.db");
    static final Path LOG_PATH = HERE.resolve("TMP").resolve("frame.log");

    //  What each clerk sells, one item per sale.
    static final Map<String, List<String>> CLERK_DB = new LinkedHashMap<>();
    static {
        CLERK_DB.put("anna",  List.of("apple", "apple", "pear"));
        CLERK_DB.put("ben",   List.of("apple", "plum"));
        CLERK_DB.put("chloe", List.of("apple"));
    }

    /** RETURN: Path, the directory this test stands in -- the parent of the
     *          classes directory it runs from. */
    static Path here() {
        try { return Path.of(Shop.class.getProtectionDomain().getCodeSource().getLocation().toURI()).getParent(); }
        catch (URISyntaxException error) { throw new IllegalStateException(error); }
    }

    /** RETURN: Sqlite, a connection to the shop's database, every statement
     *          it executes logged on stderr.
     *          Exits 1 where the database does not stand: 'on_entry' writes it. */
    static Sqlite connect() {
        if (!Files.exists(DB_PATH)) {
            System.err.println("shop.java: no " + DB_PATH + " -- 'on_entry' writes it; by hand: "
                               + "'hwut.execute fixture open'");
            System.exit(1);
        }
        return Sqlite.open(DB_PATH.toString(), 10000, sql -> System.err.println("sql: " + sql));
    }

    /** RETURN: nothing; the stock of 'item' was changed by 'delta' and
     *          journalled, in one transaction. */
    static void move(Sqlite db, String item, int delta, String source) {
        db.execute("BEGIN IMMEDIATE");
        db.execute("UPDATE stock SET qty = qty + ? WHERE item = ?", delta, item);
        db.execute("INSERT INTO journal VALUES (?, ?, ?)", item, delta, source);
        db.execute("COMMIT");
    }

    // _________________________________________________________________________
    // JSON, as much as a delivery note needs: objects, lists, strings without
    // escapes beyond '\"' and '\\', integers. Java's library reads no JSON.
    //
    /** RETURN: Object, the JSON value at 'at[0]' of 'text' -- Map, List,
     *          String or Long -- 'at[0]' moved past it; throws
     *          IllegalArgumentException where the text is no such value. */
    static Object json(String text, int[] at) {
        while (Character.isWhitespace(text.charAt(at[0]))) ++at[0];
        char c = text.charAt(at[0]);
        if (c == '{' || c == '[') {
            boolean objectF = c == '{';
            Map<String, Object> map = new LinkedHashMap<>();
            List<Object>        list = new ArrayList<>();
            ++at[0];
            while (true) {
                while (Character.isWhitespace(text.charAt(at[0]))) ++at[0];
                char d = text.charAt(at[0]);
                if (d == (objectF ? '}' : ']')) { ++at[0]; return objectF ? map : list; }
                if (d == ',') { ++at[0]; continue; }
                if (objectF) {
                    String key = (String) json(text, at);
                    while (text.charAt(at[0]) != ':') ++at[0];
                    ++at[0];
                    map.put(key, json(text, at));
                } else {
                    list.add(json(text, at));
                }
            }
        }
        if (c == '"') {
            StringBuilder value = new StringBuilder();
            for (++at[0]; text.charAt(at[0]) != '"'; ++at[0]) {
                if (text.charAt(at[0]) == '\\') ++at[0];
                value.append(text.charAt(at[0]));
            }
            ++at[0];
            return value.toString();
        }
        int begin = at[0];
        while (at[0] < text.length() && (text.charAt(at[0]) == '-' || Character.isDigit(text.charAt(at[0])))) ++at[0];
        if (begin == at[0]) throw new IllegalArgumentException("not JSON at offset " + begin);
        return Long.parseLong(text.substring(begin, at[0]));
    }

    /** RETURN: nothing; the delivery note in 'path' was booked and printed. */
    @SuppressWarnings("unchecked")
    static void deliver(String path) throws IOException {
        Map<String, Object> note = (Map<String, Object>) json(Files.readString(Path.of(path), StandardCharsets.UTF_8), new int[] { 0 });
        List<Map<String, Object>> lineList = (List<Map<String, Object>>) note.get("lines");
        try (Sqlite db = connect()) {
            db.execute("BEGIN IMMEDIATE");
            for (Map<String, Object> line : lineList) {
                db.execute("UPDATE stock SET qty = qty + ? WHERE item = ?", line.get("qty"), line.get("item"));
                db.execute("INSERT INTO journal VALUES (?, ?, ?)", line.get("item"), line.get("qty"), note.get("note"));
            }
            db.execute("COMMIT");
        }
        System.out.println("delivery note " + note.get("note") + " from " + note.get("supplier") + ":");
        for (Map<String, Object> line : lineList)
            System.out.println(String.format("    %-6s +%d", line.get("item"), line.get("qty")));
    }

    /** RETURN: nothing; three clerks sold at once; every sale is printed. */
    static void sell() throws InterruptedException {
        List<String> saleList  = Collections.synchronizedList(new ArrayList<>());
        List<String> errorList = Collections.synchronizedList(new ArrayList<>());
        connect().close();
        List<Thread> pool = new ArrayList<>();
        for (Map.Entry<String, List<String>> clerk : CLERK_DB.entrySet()) {
            pool.add(new Thread(() -> {
                try (Sqlite db = connect()) {
                    for (String item : clerk.getValue()) {
                        move(db, item, -1, clerk.getKey());
                        saleList.add(item + ";1");
                    }
                } catch (RuntimeException error) {
                    errorList.add(clerk.getKey() + ": " + error.getMessage());
                }
            }));
        }
        for (Thread t : pool) t.start();
        for (Thread t : pool) t.join();
        if (!errorList.isEmpty()) {
            System.err.println("shop.java: a sale failed -- " + String.join("; ", errorList));
            System.exit(1);
        }
        System.out.println("sales, item;qty -- in the order the clerks booked them:");
        System.out.println("##! table unordered sep={;}");
        for (String row : saleList) System.out.println(row);
        System.out.println("####");
    }

    /** RETURN: nothing; the stock and the frame log were printed, 'stock.csv'
     *          written. */
    static void report() throws IOException {
        List<List<Object>> rowList;
        try (Sqlite db = connect()) { rowList = db.query("SELECT item, qty FROM stock ORDER BY qty, item"); }
        List<List<Object>> sortedList = new ArrayList<>(rowList);
        sortedList.sort((a, b) -> ((String) a.get(0)).compareTo((String) b.get(0)));
        StringBuilder csv = new StringBuilder("item;qty\n");
        for (List<Object> row : sortedList) csv.append(row.get(0)).append(';').append(row.get(1)).append('\n');
        Files.writeString(HERE.resolve("stock.csv"), csv, StandardCharsets.UTF_8);
        System.out.println("stock, item;qty (also written to stock.csv):");
        System.out.println("##! table key=0 sep={;}");
        for (List<Object> row : rowList) System.out.println(row.get(0) + ";" + row.get(1));
        System.out.println("####");
        List<String> lineList = new ArrayList<>();
        for (String line : Files.readAllLines(LOG_PATH, StandardCharsets.UTF_8)) lineList.add(line.stripTrailing());
        System.out.println("the frame, around the delivery and the sale:");
        System.out.println("##! potpourri");
        for (String line : lineList) if (!line.contains("shop.java report")) System.out.println(line);
        System.out.println("####");
        for (String line : lineList) if (line.contains("shop.java report")) System.out.println(line);
    }

    public static void main(String[] args) throws Exception {
        String command = args.length > 0 ? args[0] : "";
        if      (command.equals("deliver") && args.length > 1) deliver(args[1]);
        else if (command.equals("sell"))                      sell();
        else if (command.equals("report"))                    report();
        else {
            System.out.println("choices: sell, report");
            System.exit(1);
        }
        System.out.println("<hwut-end>");
    }
}
