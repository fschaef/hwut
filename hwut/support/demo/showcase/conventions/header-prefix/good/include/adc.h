/* adc.h -- ADC sampling, module prefix ADC_ */
#ifndef ADC_H
#define ADC_H

#define ADC_CHANNELS        8u
#define ADC_VREF_MV         3300u
#define ADC_TO_MV(raw)      ((raw) * ADC_VREF_MV / 4095u)

unsigned adc_read(unsigned channel);

#endif /* ADC_H */
