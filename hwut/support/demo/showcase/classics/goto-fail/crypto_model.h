/* crypto_model.h -- just enough of Secure Transport's types for the model of
 * SSLVerifySignedServerKeyExchange() to compile and run. The 'hash' and the
 * 'signature' are toys: a signature is the digest XOR the server's key.
 * What matters is the CONTROL FLOW of the function under test.            */
#ifndef CRYPTO_MODEL_H
#define CRYPTO_MODEL_H
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

typedef int32_t  OSStatus;
typedef uint16_t UInt16;
#define SSL_SHA1_DIGEST_LEN       20
#define SSL_CLIENT_SRVR_RAND_SIZE 32
#define errSSLCrypto          (-9809)

typedef struct { uint8_t* data; size_t length; } SSLBuffer;
typedef struct {
    uint8_t clientRandom[SSL_CLIENT_SRVR_RAND_SIZE];
    uint8_t serverRandom[SSL_CLIENT_SRVR_RAND_SIZE];
    uint8_t peerPubKey[SSL_SHA1_DIGEST_LEN];
} SSLContext;

typedef struct {
    OSStatus (*update)(SSLBuffer* ctx, const SSLBuffer* data);
    OSStatus (*final)(SSLBuffer* ctx, SSLBuffer* out);
} HashReference;

extern HashReference SSLHashSHA1;
OSStatus ReadyHash(const HashReference* ref, SSLBuffer* ctx);
OSStatus SSLFreeBuffer(SSLBuffer* b);
OSStatus sslRawVerify(SSLContext* ctx, const uint8_t* key, const uint8_t* plain, size_t plainLen,
                      const uint8_t* sig, size_t sigLen);
#define sslErrorLog(...) printf("log: " __VA_ARGS__)

OSStatus SSLVerifySignedServerKeyExchange(SSLContext *ctx, bool isRsa, SSLBuffer signedParams,
                                          uint8_t *signature, UInt16 signatureLen);
#endif
