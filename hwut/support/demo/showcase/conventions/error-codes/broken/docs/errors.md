# Error codes

Every code a device, the backend or a host tool can report.

| Code | Name              | Meaning                                   |
|------|-------------------|-------------------------------------------|
| 1001 | ERR_TIMEOUT       | a peripheral did not answer in time       |
| 1002 | ERR_CRC           | a frame failed its checksum               |
| 1003 | ERR_FLASH_WRITE   | writing the flash failed                  |
| 1004 | ERR_NO_MEMORY     | the heap is exhausted                     |
| 1010 | ERR_SENSOR_RANGE  | a sensor reading lies outside its range   |
| 2001 | E_BAD_REQUEST     | the request is malformed                  |
| 2002 | E_UNAUTHORIZED    | no valid session                          |
| 2003 | E_RATE_LIMIT      | too many requests                         |
| 2010 | E_DEVICE_OFFLINE  | the device has not reported for 5 minutes |
| 3001 | USAGE             | wrong command line                        |
| 3002 | NO_DEVICE         | no device on the bus                      |
| 3005 | IMAGE_FORMAT      | the firmware image is not an ELF file     |
