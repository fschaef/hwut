/* spi.h -- SPI master, module prefix SPI_ */
#ifndef SPI_H
#define SPI_H

#define SPI_MODE_0          0u
#define SPI_MODE_3          3u
#define MAX_XFER            64u
#ifndef SPI_TRACE
#  define SPI_TRACE         0   /* build with -DSPI_TRACE=1 to log every frame */
#endif

int spi_transfer(const void* tx, void* rx, unsigned n);

#endif /* SPI_H */
