# Motor bench service

Collects the measurements of the bench and serves them over HTTP.

## Configuration

The service reads an INI file (sections and keys below) and a few
environment variables.

| Key             | Where | Default            | Meaning                         |
|-----------------|-------|--------------------|---------------------------------|
| `server.host`   | ini   | -                  | address to listen on            |
| `server.port`   | ini   | -                  | TCP port                        |
| `db.pool_size`  | ini   | -                  | database connections kept open  |
| `db.dsn`        | ini   | -                  | database to connect to          |
| `APP_CONFIG`    | env   | /etc/bench/app.ini | the INI file to read            |
| `APP_LOG_LEVEL` | env   | info               | debug, info, warning or error   |
| `APP_REGION`    | env   | (required)         | region tag of every measurement |
| `APP_DATA_DIR`  | env   | /var/lib/bench     | working directory of service    |

## Running

    APP_REGION=eu-1 deploy/run.sh
