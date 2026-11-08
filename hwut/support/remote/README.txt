==============================================================================
support/remote -- REMOTE EXECUTION: A TEST APPLICATION DRIVES A BOARD
==============================================================================

    A test application on the host drives a unit under test on a target --
    a board, a simulator, an emulator -- through an agent beside the UUT.
    hwut runs the test where its platform provides the board, and knows
    nothing else of it: hwut imports nothing of this directory, and this
    directory imports nothing of hwut.

    PROTOCOL.txt   the terms, the axes, the line, the verbs, recovery
    MAP.txt        the agent's address space and its implementations
    README.txt     this file: the bench and the writer
    host/          hwut_remote, the package the writer imports; image_id.mk
    target/        the agents: verilog/ (built); c/, python/ (delivery 5)
    proto/         the prototypes a writer copies: iverilog/ (built)

    BUILT (spec/26 delivery steps 1 to 3): PROTOCOL.txt, MAP.txt;
    hwut_remote -- the factory, LinkHub and its ladder, the links serial,
    tcp, udp, ssh, launch, the configuration file, the CLI, 'list'; the
    loader 'none'; target/verilog with its UART and stdio phys, proven
    under iverilog; host/image_id.mk; proto/iverilog end to end. NOT YET
    BUILT, refused by name where reached: the vendor loaders (quartus 4;
    openocd, esptool, copy 5; openfpgaloader 8), the C and Python agents
    (5), 'can' (9), capture.py (7), 'visa' and VisaHub (12); the other
    prototypes. The bus (map 100 and above) is not built in the Verilog
    agent. hwut's side (the 'deploy' stage, exit 77 as '[ABSENT]',
    'provides' and hwut-provided.conf) arrives in the next bundle; until
    then a test exiting 77 is judged as any other exit.


==============================================================================
1  ORIENTATION
==============================================================================

    THE TWO SIDES

                HOST                                      TARGET
     the machine that runs hwut              a board, a simulator or an
     and the test application                emulator

    +---------------------------------+          +------------------------+
    | test application    (writer)    |          | agent                  |
    |   prints rows and '##' lines    |          |   support/remote/      |
    |   hub = create_hub("serial",    |
    |       config_file="max10.conf") |          |   target/<impl>/       |
    |---------------------------------|   link   |   verilog | c | python |
    | hwut_remote      the hub        |<========>|                        |
    |   support/remote/host/          |  serial  |   map <---> UUT        |
    |   session  the protocol         |  tcp     |                        |
    |   line     token, CRC, the line |  udp     +------------------------+
    |   link     the bytes            |  ssh                 ^
    |   entry    the configuration    |  launch              |
    |   <loader> flash, reset: Hub's  |  can, visa           |
    |   capture  rows from captures   |                      |
    +---------------------------------+                      |
           |              |                                  |
           |              +---- loader (vendor tool) --------+
           |                    puts the image on the target
           v
    the test         max10.conf: link, loader, ...: create_hub's (2)
    hwut-root.conf   platform = [ { name = ..., provides = [ <name> ] } ]

    host           the machine that runs hwut and the test application
    hwut_remote    the Python package the writer imports, in
                   support/remote/host/: create_hub, add_plugin, Hub,
                   LinkHub, VisaHub; its modules session, line, link,
                   entry, visa, one module per loader, capture; the CLI
    hub            the object create_hub returns: the host's end of one
                   link to one agent
    target         the board, simulator or emulator
    agent          the program or circuit on the target that drives the
                   UUT for the host; one implementation per directory in
                   support/remote/target/: verilog, c, python
    UUT            the unit under test, beside the agent on the target
    link           the channel between host and agent
    loader         the vendor tool that puts an image on the target, run
                   through its loader module
    bench          a target, its link and
                   its loader
    platform       where hwut runs a bubble (spec/42); a definition that
                   provides a bench's name has that board attached

    WHAT THE USER DOES -- everything else is done by the modules; the
    protocol (Part A) stays hidden from the user.

       user           hwut          make+loader     hwut_remote         agent
         |              |                |                |               |
         |  ONCE PER BENCH                                                |
         |  wire the target; install the vendor tool                      |
         |  write the board's configuration (o-37)                        |
         |  python3 -m hwut_remote list: what is attached, which file     |
         |    names it                                                    |
         |  name it in the 'provides' of the platform it is attached to   |
         |              |                |                |               |
         |  ONCE PER TEST                                                 |
         |  copy a prototype: support/remote/proto/<name>/                |
         |  its bubble specifies the bench: platform = [ "<name>" ]       |
         |  put the UUT beside the agent: verilog -- in the top           |
         |    level; c, python -- write uut_run(stim, report)             |
         |  write the test application: vectors, prints                   |
         |  hwut.play; accept the GOOD                                    |
         |              |                |                |               |
         |  EVERY RUN                                                     |
         |-- hwut.run ->|                |                |               |
         |              |-- run where the name is provided                |
         |              |-- build ------>|                |               |
         |              |-- deploy ---------------------->|               |
         |              |                |                |-- flash ----->|
         |              |                |                |   if stale    |
         |              |-- run a choice ---------------->|               |
         |              |                |                |-- open ------>|
         |              |                |                |-- reset ----->|
         |              |                |                |-- vectors --->|
         |              |<- rows, '##' lines -------------|               |
         |<- verdict ---|                |                |               |

    The protocol of Part A runs inside 'open', 'reset' and 'vectors'.

    The host reads and writes bytes of a map; one verb, 'x', applies a
    stimulus and returns the outcome and the report. Every reply is the
    content of a read. hwut learns two things: which platform provides a
    name, and one exit status, 77 -- the case's infrastructure is absent.
    It holds no bench, looks for no device and never talks to a board.

    Running example: an 8-bit registered adder on a MAX 10 at 50 MHz,
    LATENCY 1; a = 03, b = 04, sum = 007. Stimulus a[15:8] b[7:0]
    (2 bytes), report sum[8:0] (2 bytes).


==============================================================================
2  THE FACTORY AND THE HUB
==============================================================================

    REGISTRY        add_plugin(transport, producer)   transport -> producer
                    built in: serial tcp udp ssh launch can visa
                                      |
    FACTORY         create_hub(transport, address=None, *, config_file=None,
                               note=None, **options) -> Hub
                      1. producer = registry[transport]     unknown: refused
                      2. values  = producer.read(config_file)   the
                                   producer's format; absent: {}
                         values |= options; the address, if given:
                                   the call wins over the file
                      3. the common keys (B, D, E below) checked by the
                         factory, the rest by the producer
                      4. return producer(values, note)       NOT opened
                                      |
    PRODUCT         Hub
                      with hub: ...      opens the link, hello (3); closes
                      hub.flash(image, image_id)   the loader strategy
                                         'loader' names; opens, checks the
                                         image, flashes if stale (5)
                      hub.reset_bench()  the bench reset (6)
                      LinkHub:  reset() vector() read() write() contract()
                      VisaHub:  reset() query() write() opc()       (13)
                                      |
    CLI             python3 -m hwut_remote <transport> [<address>]
                            [--config-file F] [--<key> V ...]
                            flash <image> (<image-id> | --image-id-file F)
                            | reset [<image>]
                    python3 -m hwut_remote list [F ...]
                    the same factory; nothing else

    THE TEST AND ITS DEPLOY SHARE ONE FILE

    max10.conf, the serial producer's format:
        serial = /dev/serial/by-id/usb-Altera_...
        baud = 115200  low_latency = true  boot = 1.0
        loader = quartus  cable = USB-Blaster [1-3]

    the test:      with create_hub("serial", config_file="max10.conf",
                                   note=note) as hub:
    its deploy:    python3 -m hwut_remote serial --config-file max10.conf
                           flash uut.sof --image-id-file TMP/image_id
    in code:       create_hub("serial", "/dev/serial/by-id/usb-Altera_...",
                              baud=115200, boot=1.0, loader="quartus",
                              cable="USB-Blaster [1-3]")

    The address is the value of the key named after the transport: given
    as 'address' in the call, or as 'serial = ...' (tcp, udp, host,
    launch, can, visa = ...) in the file. hwut reads none of it (o-35).

KEYS -- closed; an unknown key is refused

    key           axis  meaning
    ---           ----  -------
    serial        C     the UART device
    tcp           C     host:port
    udp           C     host:port
    host          C     ssh target
    launch        C     the command whose stdio is the link
    can           C     CAN interface (socketcan name, e.g. can0)
    can_ids       C     "<host->agent id>:<agent->host id>", hex
    baud          C     bit rate of the UART on the path
    dtr, rts      C     levels set before open; false = deasserted, the
                        pin high
    low_latency   C     FTDI latency timer 1 ms
    link_margin   C, B  seconds added to every deadline, or inf
    time          B     wall (default) | virtual
    boot          B     seconds the hello may take, or inf; mandatory
    loader        D     quartus | openfpgaloader | openocd | esptool |
                        copy | none
    cable         D     quartus: the cable as jtagconfig lists it
    board         D     openfpgaloader: the board name it knows
    cfg           D     openocd: the board configuration
    image_offset  D     esptool: offset of the merged image
    agent         C, D  ssh and copy: the agent's path on <host>
    power         E     a command that power-cycles the board

    VALIDATION. The factory checks the B, D and E keys; the producer
    checks its transport's C keys and refuses the others by name. A file
    the producer cannot read is refused with its reason. A
    /dev/serial/by-id path names the board on every host.

    THE CLASSES -- hwut_remote, what the writer imports:

    add_plugin(transport, producer)  a transport taken is refused
    producer       an object with read(config_file) -> dict and
                   __call__(values, note) -> Hub
    Hub            with, flash(image, image_id), reset_bench(), close();
                   the base of every hub
    LinkHub        a Hub over the agent's map: vector(stim) -> int |
                   TIMEOUT, read(addr, n), write(addr, bytes), contract(),
                   reset(); a producer gives it open, send(bytes),
                   recv(deadline) -> bytes, close; line, CRC, token and
                   the ladder are LinkHub's (sections 4, 10)
    VisaHub        a Hub over an instrument: query(cmd) -> str,
                   write(cmd), opc(), reset(); no agent, no map (13)
    TIMEOUT        section 9

    The seven built-in producers are registered by add_plugin: six
    LinkHubs, serial, tcp, udp, host (ssh), launch, can, and one VisaHub,
    visa. A system with another protocol (section 13) may implement Hub
    whole and register it the same way. A plugin is registered by the
    test's own code, before create_hub:

        from hwut_remote import create_hub, add_plugin, LinkHub, producer
        add_plugin("bridge", producer(lambda values, note:
                       LinkHub(BridgeLink(values), values, note)))
        with create_hub("bridge", "usb:1-3", boot=2.0, loader="none",
                        note=note) as hub: ...

    'producer(make)' wraps a constructor with the default reader, which
    reads key = value lines.

    THE LIST -- python3 -m hwut_remote list [F ...]: what is attached to
    this machine and which of the configuration files given names it
    (what it reads when none is given: o-38). It looks and prints; it
    writes nothing and opens no link.

    file        transport  address                                  state
    max10.conf  serial     /dev/serial/by-id/usb-Altera_USB-Blaster_ present
    esp.conf    serial     /dev/serial/by-id/usb-Silicon_Labs_CP210x absent
    sim.conf    launch     vvp TMP/uut.vvp                          not probed
    dmm.conf    visa       USB0::0x2A8D::0x1301::MY59001234::INSTR  present
    --          serial     /dev/serial/by-id/usb-FTDI_FT232R_A50285 no file
    --          jtag       USB-Blaster [1-3]  10M50DA               no file
    --          can        can0                                     no file

    state       present, absent (the device path exists; visa:
                listed by pyvisa); not probed; no file -- attached, named
                by no file
    looks at    /dev/serial/by-id; 'jtagconfig' and 'openFPGALoader
                --scan-usb' where on PATH; CAN interfaces (/sys/class/net,
                type 280); pyvisa's list_resources() where pyvisa is
                installed
    The order: files by name, then the unnamed by transport and
    address. A tool not installed is one '##' line: "## not looked:
    jtagconfig".


==============================================================================
3  C -- TRANSPORT, AND OPENING A SESSION
==============================================================================

    transport  address key          the link
    ---------  ---------            --------
    serial     serial = "<device>"  the UART; 'baud', 'dtr', 'rts',
                                    'low_latency' apply
    tcp        tcp = "host:port"    a socket (ser2net, a JTAG-UART bridge);
                                    'baud' applies when a UART is behind it
    udp        udp = "host:port"    one line per datagram, each way; a
                                    datagram may be lost, late or doubled
                                    (PROTOCOL.txt 4: duplicate; PROTOCOL.txt 5)
    ssh        host = "<host>"      ssh -T -o BatchMode=yes <host> exec
                                    <agent>
    launch     launch = "<command>" a process on stdio (vvp, qemu
                                    -serial stdio)
    can        can = "<interface>"  ISO-TP (ISO 15765-2) over CAN or CAN FD
               can_ids = "7e0:7e8"  through python-can; the two ids carry
                                    one byte stream each way; ordered, a
                                    line is one or more ISO-TP messages
    visa       visa = "<resource>"  pyvisa opens the VISA resource, e.g.
               backend = "@py"      "TCPIP0::10.0.0.5::inst0::INSTR";
                                    'backend' is pyvisa's: absent, its
                                    default; "@sim" for pyvisa-sim; SCPI
                                    messages end in '\n' (section 13)

    A hub has exactly one transport: create_hub's first argument, one
    of the seven or a plugin's; a file that names another is refused.

    COMMON CHANNELS, and the transport that reaches each:

    channel                                   transport
    -------                                   ---------
    USB-CDC, FTDI, CP210x, CH340              serial
    SEGGER RTT (openocd 'rtt server', J-Link) tcp
    Intel JTAG-UART                           launch (juart-terminal)
    Xilinx MDM UART                           tcp (xsdb jtagterminal)
    ser2net, raw mode                         tcp
    Ethernet, Wi-Fi (lwIP)                    tcp, udp
    ISO-TP on CAN                             can
    GPIB, USBTMC, LXI/VXI-11, HiSLIP          visa
    QEMU, Renode, a simulator                 launch, tcp (a UART socket)
    a Linux board                             host
    BLE UART service, raw USB bulk, SPI or    a plugin: a LinkHub
      I2C through a bridge, MQTT, WebSocket
    an SCPI instrument on any of them         visa
    XCP, UDS, SOME/IP, ASAM XIL, ROS 2        their own API (section 13);
                                              or a plugin: a whole Hub

    hwut_remote.link.open(values) is the only constructor of a built-in
    channel; create_hub and the loader modules both use it.

    OPENING:

    host                                         agent
    serial: DTR/RTS set before open, exclusive, low latency, input flushed
    '\n'
    t r 0 1a -------------------------------->   t: a random token
          <-- noise, stale replies, boot log      counted
          <-- t <26 bytes>                        the reply: token t, the
                                                  magic

    No reply within 'boot' --> "no agent". The hello is repeated every
    deadline on serial, tcp and udp, sent once on ssh and launch. A
    discarded
    line equal to the line sent is counted as an echo: "no agent: link
    echoes".

    From the hello: proto != 1 --> "protocol <n>"; image != image_id -->
    "stale agent"; else noted: proto, image, lengths, mode, clock,
    timeout, discarded lines, bytes discarded by the host.


==============================================================================
4  B -- TIME DOMAIN
==============================================================================

    time = wall      link_margin and boot are seconds
    time = virtual   link_margin = boot = inf; the choice is bounded by
                     hwut's caps (vvp; qemu with -icount)

    defaults   link_margin  serial 50 ms, tcp 200 ms, udp 200 ms,
                            ssh 500 ms, launch 1 s, visa 2 s (the
                            VISA timeout); a plugin's:
                            its producer's
               boot         mandatory in every configuration


==============================================================================
5  D, F -- LOADER AND IMAGE IDENTITY
==============================================================================

    inputs --> TMP/image_id --> uut.sof --> [board runs it?] --no--> loader
       hash, compared               |yes                              |
                                    +--> nothing to do                v
                                                      [board runs it now?]
                                                        no --> DEPLOY_FAILED
      \__________ build ___________/  \____________ deploy _____________/

    THE MAKEFILE (the writer's); the rule for TMP/image_id is the shared
    fragment host/image_id.mk, included:

    RE        := $(HWUT_REMOTE)
    INPUTS    := $(sort $(wildcard src/*.v $(RE)/target/verilog/*.v) \
                        uut.qsf uut.sdc Makefile)
    TOOLCHAIN := quartus_sh --version
    include $(RE)/host/image_id.mk

    # host/image_id.mk (HWUT_REMOTE: the directory support/remote):
    TMP/image_id: FORCE
    	mkdir -p TMP
    	(cat $(INPUTS); $(TOOLCHAIN)) | sha256sum | cut -c1-8 > $@.new
    	cmp -s $@.new $@ || mv $@.new $@
    	test -f TMP/image_id.vh -a ! TMP/image_id.vh -ot $@ || \
    	  echo "\`define IMAGE_ID 32'h$$(cat $@)" > TMP/image_id.vh
    uut.sof: TMP/image_id
    	quartus_sh --flow compile uut
    .PHONY: FORCE

    INPUTS names everything that changes the image; TOOLCHAIN names the
    compiler's version command. TMP/image_id changes only when the hash
    does.

    THE TEST -- build and deploy, two stages, two meanings (o-41):

        @hwut { build   { framework = "make"  executable = "uut.sof" }
                execute = "python3 test-max10.py"
                deploy  = "python3 -m hwut_remote serial --config-file
                           max10.conf flash uut.sof --image-id-file
                           TMP/image_id" }

    A build makes its 'executable' (default 'app') and the test then runs
    THAT, unless 'execute' states the call (R-68): a Python writer states
    it. The build runs where the Makefile stands, in the test directory.

    'deploy' mirrors 'build': the short form is the scope with its one
    principal key, deploy { flash = "<command>" }; the scope also takes
    'caps'. Its vocabulary is closed and grows (copy over ssh, an install
    to come). The command runs directly, never through make: make would
    turn 77 into 2.

        provision:  build ----------> deploy -----------> execute
                    BUILD_FAILED      77: [ABSENT]         77: [ABSENT]
                    (the code)        else DEPLOY_FAILED   (behaviour)
                                      (the infrastructure)

    The stage deploy runs after the build and before execute, remembered
    as StageBuild is: it runs again only when the build ran again.
    DEPLOY_FAILED is a FAIL with its own report token.

    hub.flash(image, image_id), the same for every loader; its CLI:

        python3 -m hwut_remote <transport> [<address>] [--config-file F] \
                flash <image> (<image-id> | --image-id-file F)
          open (section 3) --> port held by another process: "bench
                                busy", exit 1; device absent: "no
                                device", exit 77; nothing flashed
          hello: image = <image-id> --> "already on the board", exit 0
          else: close; flash; reopen; hello within 'boot';
                exit 0 only if the image is now running

    loader   flash  (a strategy of the Hub, chosen by 'loader')
    ------   -----
    quartus  quartus_pgm -c <cable> -m jtag -o "p;<image>"  (.pof: "pv;")
    openfpgaloader  openFPGALoader -b <board> <image>  (SRAM)
    openocd  openocd -f <cfg> -c "program <image> verify reset exit"
    esptool  esptool --port <serial> write_flash <image_offset> <image>
             (a merged image); run
    copy     scp <image> and the id file into a temporary directory on
             <host>, then mv into <agent>'s directory
    none     -- (launch: the image is the command's argument)

    case                 outcome
    ----                 -------
    inputs changed       new id; compile; flash; confirm
    nothing changed      no flash
    someone reflashed    flash; confirm
    port busy            DEPLOY_FAILED "bench busy"
    device absent        [ABSENT] "no device" (exit 77)
    board unpowered      DEPLOY_FAILED (no agent; the loader fails)
    flash did not take   DEPLOY_FAILED
    the code does not    BUILD_FAILED
      compile


==============================================================================
6  E -- BENCH RESET
==============================================================================

        hub.reset_bench();  python3 -m hwut_remote <transport> ... reset [<image>]

    always with the link closed; scpi alone through the open hub.

    kind     action
    ----     ------
    reload   quartus, openfpgaloader: configure <image> again
    probe    openocd -f <cfg> -c "init; reset run; exit"
    line     esptool --port <serial> --after hard_reset run
    reopen   launch, ssh: end and restart the process
    scpi     visa: '*RST', '*CLS' through the open hub (Hub.reset)
    power    any loader, when 'power' is set: run it first


==============================================================================
7  Q -- OWNERSHIP
==============================================================================

    The tests of one board are a collision group (R-32). The board is
    attached to the platform whose definition provides its bench's name;
    the board's bubble specifies that name (spec/42, 'provides'):

    a hwut-root.conf the walk reads (the name resolves across all):
        platform = [ { name = "local", provides = [ "max10" ] } ]
    the board's bubble, support/remote/proto/de10-lite/hwut-root.conf:
        platform = [ "max10" ]

    A PROVISION IS ONE-WAY: A provides B lets a bubble specifying B run
    on A; a bubble specifying A asks nothing of B. A name both defined
    and provided is a fault (spec/42), so a provided name provides
    nothing: no chain, no cycle. 'provides' names informal
    functionality; it routes, hwut checks nothing of it.

    THE INFRASTRUCTURE ABSENT -- exit status 77. Only the test knows what
    it needs; it says so, and hwut judges nothing:

        create_hub(...)  device absent --> stderr "max10: no device
                                           /dev/serial/by-id/usb-Altera_..."
                                       --> exit 77

        test-max10.py adder [ABSENT]
              NOTE  max10: no device /dev/serial/by-id/usb-Altera_...

    hwut_remote does both where it cannot open the link for want of the
    device; the writer writes nothing. The NOTE is the last line of
    stderr. The verdict is E_TestRunResult.INFRA_ABSENT: not compared,
    not FAIL, counted as a bubble not run is (spec/42 PROTOCOL.txt 4: not in
    RESULTS, no book entry, the last verdict kept, exit status
    unchanged). Every other exit status stays behaviour.

    A VERDICT measured under a provided name shows it once per directory,
    where spec/42 shows '(linux)':

        de10-lite/  (max10 in local)

    CONDITION ON HWUT: no other build or deploy of the group runs between
    the deploy and the run of one application. Delivery step 4 verifies it.

    Two roots holding one board are detected only as "stale agent" or
    "bench busy".


==============================================================================
8  BENCH REQUIREMENTS
==============================================================================

    port names     /dev/serial/by-id/..., never /dev/ttyUSB<n>
    the agent UART carries nothing else: no console, no log, no getty
    micro-ROS      firmware whose UART belongs to micro-ROS gives the agent
                   a second UART, a USB-CDC port or a CAN id pair
    U-Boot         on a board whose console shares the agent UART,
                   autoboot does not wait for a key
    ModemManager   ignores the port: udev ENV{ID_MM_DEVICE_IGNORE}="1"
    CDC-ACM        a port that vanishes on target reset is reopened after
                   the reset, within 'boot'
    FPGA pins      the agent's TX pin has a weak pull-up in the .qsf
    ssh            key login

    TIMEOUTS

    what                      default            set by
    ----                      -------            ------
    agent 'timeout'           TIMEOUT parameter  'w 14 <counts>'
    command deadline          PROTOCOL.txt 5         link_margin
    hello window              --                 boot (mandatory)
    failures before silent    3                  create_hub(failures=)
    loader                    120 s              module argument
    the whole choice          hwut's caps        @hwut { caps { } }


==============================================================================
9  O -- SESSION SCOPE AND THE PICTURE
==============================================================================

    A session is one choice: it opens, resets, applies, closes.
    create_hub() opens the link and says hello; the writer resets;
    Hub.vector() and Hub.write() raise unless this hub has reset; leaving
    the 'with' block closes the link.

    The writer prints the wait contract as a row, Hub.contract().
    Everything else the session knows is a '##' line, delivered through
    'note'.

    ## agent: proto 1  image 3f9a07c1  stim 2  report 2  50 MHz
    ## discarded 12 bytes, 0 lines
    contract: sample 1 cycle after apply, timeout 10000000 counts at 50 MHz
    ## stim = a[15:8] b[7:0]   report = sum[8:0]
    0304 007
    ff01 100
    ffff 1fe
    <hwut-end>

    Hub.vector() returns the report as an int, or hwut_remote.TIMEOUT on
    outcome 02; TIMEOUT formats as 'timeout' under any format spec.
    Outcome 03 raises. A recovery adds a '##' line where it happened and
    leaves the rows unchanged. A read at the bus (100 and above) is
    followed by 'r 19 1' and checked for fresh.


==============================================================================
10  THE TEST, AS THE WRITER WRITES IT
==============================================================================

    # @hwut { build   { framework = "make"  executable = "uut.sof" }
    #         execute = "python3 test-max10.py"
    #         collision = [ "test-max10-timing.py" ]
    #         deploy  = "python3 -m hwut_remote serial --config-file
    #                    max10.conf flash uut.sof --image-id-file
    #                    TMP/image_id" }
    import sys
    from hwut_runner import HwutRunner
    from hwut_remote import create_hub

    VECTORS = [(0x03, 0x04), (0xff, 0x01), (0xff, 0xff)]

    def note(text): print("##", text)

    def adder():
        image = int(open("TMP/image_id").read(), 16)
        with create_hub("serial", config_file="max10.conf", note=note,
                        image_id=image, image="uut.sof") as hub:
            hub.reset()
            print(hub.contract())
            print("## stim = a[15:8] b[7:0]   report = sum[8:0]")
            for x, y in VECTORS:
                print(f"{x:02x}{y:02x} {hub.vector((x << 8) | y):03x}")

    HwutRunner(sys.argv, "Adder on MAX 10;", {"adder": adder}).run()

    Nothing runs at import: '--hwut-info' needs no build and no board.
    The bubble's hwut-root.conf specifies platform = [ "max10" ]; the
    test names its configuration file, never the platform. The hub finds
    the bench reset by 'loader'. The board absent: exit 77 (section 7). The writer never sees a token, a CRC,
    a byte order or a recovery.


==============================================================================
11  A SESSION ON THE WIRE
==============================================================================

    host                                  agent           picture
    ----                                  -----           -------
    [build: make; deploy: flash -- done before the run]
    open, '\n'
    9 r 0 1a *6679 ---------------------->
          <... noise ... discarded, counted
       <-- 9 6877757401000000c1079a3f0202050080f0fa0280969800ff80 *085c
           magic, proto 1, image 3f9a07c1, stim 2,        ## agent: ...
           report 2, mode 05 (sample, LATENCY 1),         ## discarded ...
           0 lines discarded,
           50 MHz, timeout 10000000, last ff, fresh
    a w 3f 01 *e167 --------------------->  UUT reset
       <-- a 00 *1ea6                       outcome 00, fresh 0
                                                          contract: ...
                                                          ## stim = ...
    b x 0403 *2b95 ---------------------->  apply 0x0304
       <-- b 010700 *8bff                                 0304 007
    c x 01ff *29ff ---------------------->  apply 0xff01
       <-- c 010001 *599d                                 ff01 100
    d x ffff *671b ---------------------->  apply 0xffff
       <-- d 01fe01 *7919                                 ffff 1fe
    close                                                 <hwut-end>


==============================================================================
12  THE SIMULATION TWIN
==============================================================================

    test-max10.py                       test-sim.py
    -------------                       -----------
    build: make uut.sof, deploy: flash  build: make TMP/uut.vvp (iverilog)
    max10.conf: serial, wall            sim.conf: launch, virtual
    platform = [ "max10" ]              no platform: runs locally
              |                                   |
              +---- from vectors import adder ----+   the shared code

    Two applications, two GOODs; nothing in hwut chooses between them. The
    agent and the UUT are the same Verilog; only the phy differs.


==============================================================================
13  SYSTEMS WITH THEIR OWN API: HIL, ROS 2, ECUS, INSTRUMENTS
==============================================================================

    A system with its own real-time target and host API -- dSPACE through
    ASAM XIL, NI VeriStand -- with its own middleware -- ROS 2, SOME/IP
    -- or with its own protocol -- an ECU through XCP or UDS, an
    instrument through VISA and SCPI -- takes the
    place of the agent, the line, the map and recovery (sections 4 to
    10). The rest stays:

    ours                               theirs
    ----                               ------
    build: deploy the model or system  the real-time target, its loop rate
      definition; its checksum is the  the stimulus, executed on the target
      image identity, printed as '##'  the capture, triggered and
      and compared                       timestamped on the target
    ownership: collision group,        the host API and its errors
      providing platform
    session: one choice = one run
    picture: rows and '##'

    THE SESSION, for every such system:

        configure -> arm stimulus -> arm capture -> start -> wait until the
        (load,       on the target    with a trigger         capture is
        deploy)                       in model time          complete
                                                               |
        rows <-- capture.rows <-- fetch <-- stop <--------+

    RULES
      rows come only from captured, target-timestamped samples, at stated
        model times; never from a read during the run
      every value has a stated resolution and unit, or is matched by a
        pype quantity
      the system's own verdict (a sequence's return value) is a row
      an error of the host API fails the choice; its text is a '##' line

    ROS 2: the UUT is a node or a stack; the test application is a node
    itself (rclpy). It publishes stimuli and subscribes to results,
    recording each message with its header stamp.
      simulation  Gazebo (or another simulator) publishes /clock;
                  use_sim_time = true for every node; the hub's configuration has
                  time = virtual; the simulator runs in lockstep, so the
                  stamps are model time and the RULES above hold
      real robot  stamps are wall time: rows hold final states and the
                  stack's own verdicts only; every timed value is a '##'
                  line
      build       the colcon workspace; its image identity is the hash of
                  the package sources and the ROS distribution
      provenance  ROS distribution, RMW implementation, ROS_DOMAIN_ID as
                  '##' lines; each test uses its own ROS_DOMAIN_ID

    AUTOMOTIVE ECUS
      XCP         measurement and calibration (pyxcp): DAQ lists bound to
                  ECU events are the capture, their ECU timestamps the
                  model time; the A2L file names the variables; the A2L's
                  EPK is the image identity
      UDS         diagnostics, ISO 14229 (udsoncan, over CAN ISO-TP or
                  DoIP): each request and its positive or negative
                  response is a row; the session (default, extended) and
                  the security access level are part of the row's
                  meaning, printed as rows; timing parameters are '##'
      SOME/IP     Adaptive AUTOSAR services: the ROS 2 rules apply --
                  rows from timestamped messages under simulated time,
                  final states and verdicts on a real network
      AUTOSAR Classic SWCs are reached through the C agent: the writer's
      uut_run calls the component's RTE ports (Rte_Write, Rte_Call,
      Rte_Read); on the host the same seam runs against RTE stubs.

    INSTRUMENTS (SCPI), through VisaHub:

        with create_hub("visa", "USB0::0x2A8D::0x1301::MY59001234::INSTR",
                        boot=5.0, loader="none", note=note) as dmm:
                                                    # '## idn: ...'
            dmm.reset()                             # *RST, *CLS
            dmm.write("CONF:VOLT:DC 10,0.001")
            dmm.write("INIT"); dmm.opc()
            print(f"v = {float(dmm.query('FETC?')):.3f} V")

      open      pyvisa opens the resource; '*IDN?' within 'boot' is a
                '##' line; no answer: "no instrument"
      write, query
                send one message; then 'SYST:ERR?' until '+0': any other
                entry raises with its text, after a '##' line
      opc       '*OPC?' within the VISA timeout; the host never sleeps
      reset     '*RST', '*CLS', the error queue read empty
      a VISA error raises; its text is a '##' line

    capture.rows(samples, times, fmt) -> [str]
      samples  (t, v1, v2, ...) in model time, ascending
      times    the model times to report
      fmt      the row format, e.g. "t={:.3f} rpm={:.1f} torque={:.1f}"
      each row holds the last sample at or before its time; a time before
      the first or after the last sample raises

    The bench README carries seven worked test applications: ASAM XIL
    (dSPACE), VeriStand, ROS 2 with Gazebo, XCP, UDS, SOME/IP, SCPI
    through VisaHub; and one uut_run over RTE ports.


==============================================================================
14  PROTOTYPES
==============================================================================

    A prototype is a directory that runs end to end: a writer copies it,
    replaces the UUT and fills in its configuration file. Together they take
    every value of axes A to E, the two wait modes and the two seams.

    proto           agent    time     transport  loader          reset
    -----           -----    ----     ---------  ------          -----
    iverilog        verilog  virtual  launch     none            reopen
    de10-lite       verilog  wall     serial     quartus         reload
    arty-a7         verilog  wall     serial     openfpgaloader  reload
    nucleo-f4       c        wall     serial     openocd         probe
    esp32-devkitc   c        wall     serial     esptool         line
    qemu            c        virtual  launch     none            reopen
    linux-ssh       python   wall     ssh        copy            reopen
    can-nucleo      c        wall     can        openocd         probe
    ros2-gazebo     --       virtual  --         none            --
    scpi-sim        --       wall     visa       none            scpi

    proto           UUT                mode / seam
    -----           ---                -----------
    iverilog        adder              sample, LATENCY 1
    de10-lite       divider            wait for done
    arty-a7         adder              sample, LATENCY 1
    nucleo-f4       C function         run seam
    esp32-devkitc   C function         poll seam
    qemu            nucleo-f4's code   run seam
    linux-ssh       Python function    --
    can-nucleo      C function         run seam (nucleo-f4 over CAN)
    ros2-gazebo     a ROS 2 node       section 13: rclpy, /clock
    scpi-sim        a DMM in a         backend "@sim"; the same test
                    pyvisa-sim YAML    against a real DMM by its file

    Each holds: README.txt (board, wiring, host setup), the Makefile with
    host/image_id.mk, the top level or port, the configuration file, the
    platform's 'provides' as a hwut-root.conf snippet, the bubble's
    hwut-root.conf specifying the bench, the test application. A GOOD is
    recorded where the board stands; iverilog, qemu and scpi-sim record
    theirs on
    every host. tcp and power are configuration variants, documented in the
    de10-lite README; udp in the esp32-devkitc README.
