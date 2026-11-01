/* ______________________________________________________________________________
 * A TERMINAL FILE VIEWER -- the program 'screen.java' tests; no test itself.
 *
 *     viewer.exe <file>           ('make viewer.exe' builds it)
 *
 * Full screen, on the terminal's alternate screen: a title bar (reverse
 * video), as many lines of the file as fit, and a status line: the keys
 * flush left, the lines shown flush right. Keys: 'j' or down one line
 * further, 'k' or up one line back, 'q' quits.
 *
 * JAVA HAS NO 'termios': the terminal is put into raw mode, asked for its
 * size and restored by 'stty' on the viewer's own terminal (its stdin) --
 * 'stty -g' saves the settings, 'stty raw -echo' is Python's 'tty.setraw',
 * 'stty size' is 'os.get_terminal_size'.
 * ______________________________________________________________________________
 */
import java.io.FileDescriptor;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.List;

final class Viewer {
    /** RETURN: String, what 'stty <args>' printed, run on this process's
     *          terminal (stdin), stripped; throws IOException where it fails. */
    static String stty(String... args) throws IOException {
        String[] argv = new String[args.length + 1];
        argv[0] = "stty";
        System.arraycopy(args, 0, argv, 1, args.length);
        Process process = new ProcessBuilder(argv).redirectInput(ProcessBuilder.Redirect.INHERIT)
                                                  .redirectError(ProcessBuilder.Redirect.INHERIT).start();
        String output = new String(process.getInputStream().readAllBytes(), StandardCharsets.UTF_8).strip();
        try {
            if (process.waitFor() != 0) throw new IOException("stty " + String.join(" ", args) + " failed");
        } catch (InterruptedException error) {
            throw new IOException(error);
        }
        return output;
    }

    /** RETURN: String, 'text' padded with blanks to 'width' characters on
     *          the right ('ljust'), then cut to 'width'. */
    static String ljustCut(String text, int width) {
        String padded = text.length() < width ? text + " ".repeat(width - text.length()) : text;
        return padded.substring(0, width);
    }

    /** RETURN: nothing; the whole screen is drawn with the file's line 'top'
     *          first, after 'before' -- in ONE write: a screen that stood
     *          half drawn for a moment would be seen half drawn. */
    static void draw(OutputStream out, String before, String name, List<String> lineList, int top, int rowN, int columnN) throws IOException {
        int bodyN = rowN - 2;
        List<String> shown = lineList.subList(Math.min(top, lineList.size()), Math.min(top + bodyN, lineList.size()));
        StringBuilder text = new StringBuilder(before).append("\u001b[H\u001b[2J");
        text.append("\u001b[7m").append(ljustCut(" " + name, columnN)).append("\u001b[0m\r\n");
        for (String line : shown) text.append(line, 0, Math.min(columnN, line.length())).append("\r\n");
        text.append("\r\n".repeat(bodyN - shown.size()));
        String where = "lines " + (top + 1) + "-" + (top + shown.size()) + " of " + lineList.size();
        String keys  = "j k q";
        int    width = columnN - 1 - keys.length();
        String right = where.length() < width ? " ".repeat(width - where.length()) + where : where;
        text.append("\u001b[").append(rowN).append(";1H").append(keys).append(right);
        out.write(text.toString().getBytes(StandardCharsets.UTF_8));
        out.flush();
    }

    /** RETURN: int, 0 once 'q' was pressed. */
    static int main(String path) throws IOException {
        List<String> lineList = Files.readString(Path.of(path), StandardCharsets.UTF_8).lines().toList();
        String[] size    = stty("size").split("\\s+");
        int      rowN    = Integer.parseInt(size[0]);
        int      columnN = Integer.parseInt(size[1]);
        OutputStream    out = new FileOutputStream(FileDescriptor.out);
        FileInputStream in  = new FileInputStream(FileDescriptor.in);
        String saved = stty("-g");
        stty("raw", "-echo");
        String before = "\u001b[?1049h";            // the alternate screen, with the first draw
        String name   = Path.of(path).getFileName().toString();
        int top = 0;
        byte[] buffer = new byte[8];
        try {
            while (true) {
                draw(out, before, name, lineList, top, rowN, columnN);
                before = "";
                int n = in.read(buffer);
                if (n < 0) break;
                byte[] key = Arrays.copyOf(buffer, n);
                if      (Arrays.equals(key, new byte[] { 'q' })) break;
                else if (Arrays.equals(key, new byte[] { 'j' }) || Arrays.equals(key, new byte[] { 27, '[', 'B' }))
                    top = Math.min(top + 1, Math.max(0, lineList.size() - (rowN - 2)));
                else if (Arrays.equals(key, new byte[] { 'k' }) || Arrays.equals(key, new byte[] { 27, '[', 'A' }))
                    top = Math.max(top - 1, 0);
            }
        } finally {
            out.write("\u001b[?1049l".getBytes(StandardCharsets.US_ASCII));
            out.flush();
            stty(saved);
        }
        return 0;
    }

    public static void main(String[] args) throws IOException {
        System.exit(main(args[0]));
    }
}
