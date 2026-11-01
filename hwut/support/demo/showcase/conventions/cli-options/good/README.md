# benchctl

Talks to the motor bench over its serial port.

## Options

| Option              | Default        | Meaning                              |
|---------------------|----------------|--------------------------------------|
| `-p`, `--port`      | `/dev/ttyUSB0` | serial device                        |
| `-b`, `--baud`      | `115200`       | baud rate                            |
| `-t`, `--timeout`   | `2`            | answer timeout in seconds            |
|       `--retries`   | `3`            | resend a frame N times on timeout    |
| `-l`, `--log-level` | `info`         | debug, info, warning, error          |
| `-n`, `--dry-run`   |                | print the frames, send nothing       |
| `-h`, `--help`      |                | the option summary                   |
