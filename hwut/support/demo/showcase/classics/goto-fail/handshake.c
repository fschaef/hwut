/* handshake.c -- the client side of one TLS ServerKeyExchange, three times:
 * the genuine server, a man in the middle who signs with the wrong key, and
 * one who alters the signed parameters. Prints, per case, what
 * SSLVerifySignedServerKeyExchange() returned and whether the client goes on. */
#include <stdlib.h>
#include "crypto_model.h"

static uint8_t state[SSL_SHA1_DIGEST_LEN];

static OSStatus toy_update(SSLBuffer* ctx, const SSLBuffer* data)
{
    for (size_t i = 0; i < data->length; ++i)
        ctx->data[i % SSL_SHA1_DIGEST_LEN] = (uint8_t)(ctx->data[i % SSL_SHA1_DIGEST_LEN] * 31u + data->data[i] + 7u);
    return 0;
}
static OSStatus toy_final(SSLBuffer* ctx, SSLBuffer* out)
{
    memcpy(out->data, ctx->data, SSL_SHA1_DIGEST_LEN);
    return 0;
}
HashReference SSLHashSHA1 = { toy_update, toy_final };

OSStatus ReadyHash(const HashReference* ref, SSLBuffer* ctx)
{
    (void)ref;
    memset(state, 0, sizeof(state));
    ctx->data = state;  ctx->length = sizeof(state);
    return 0;
}
OSStatus SSLFreeBuffer(SSLBuffer* b) { b->data = NULL; b->length = 0; return 0; }

OSStatus sslRawVerify(SSLContext* ctx, const uint8_t* key, const uint8_t* plain, size_t plainLen,
                      const uint8_t* sig, size_t sigLen)
{
    (void)ctx;
    if (plainLen != SSL_SHA1_DIGEST_LEN || sigLen != SSL_SHA1_DIGEST_LEN) return errSSLCrypto;
    for (size_t i = 0; i < SSL_SHA1_DIGEST_LEN; ++i)
        if ((uint8_t)(plain[i] ^ key[i]) != sig[i]) return errSSLCrypto;
    return 0;
}

static void digest(SSLContext* ctx, SSLBuffer params, uint8_t out[SSL_SHA1_DIGEST_LEN])
{   /* what the server signs: the hash over both randoms and the parameters */
    SSLBuffer h, o = { out, SSL_SHA1_DIGEST_LEN };
    SSLBuffer c = { ctx->clientRandom, SSL_CLIENT_SRVR_RAND_SIZE }, s = { ctx->serverRandom, SSL_CLIENT_SRVR_RAND_SIZE };
    ReadyHash(&SSLHashSHA1, &h);
    toy_update(&h, &c); toy_update(&h, &s); toy_update(&h, &params); toy_final(&h, &o);
}

int main(void)
{
    SSLContext ctx;
    uint8_t    params[] = "DHE p=0xF7E1A0 g=2 Ys=0x6C39", forged[] = "DHE p=0xF7E1A0 g=2 Ys=0x0BAD";
    uint8_t    sig[SSL_SHA1_DIGEST_LEN], h[SSL_SHA1_DIGEST_LEN];
    uint8_t    mitm_key[SSL_SHA1_DIGEST_LEN];
    for (int i = 0; i < SSL_CLIENT_SRVR_RAND_SIZE; ++i) { ctx.clientRandom[i] = (uint8_t)(3 * i + 1); ctx.serverRandom[i] = (uint8_t)(5 * i + 2); }
    for (int i = 0; i < SSL_SHA1_DIGEST_LEN; ++i)       { ctx.peerPubKey[i] = (uint8_t)(17 * i + 9);  mitm_key[i] = (uint8_t)(11 * i + 4); }
    struct { const char* name; uint8_t* signed_params; uint8_t* sent_params; uint8_t* key; } c[] = {
        { "genuine server, its own signature",          params, params, ctx.peerPubKey },
        { "man in the middle, signs with his own key",  params, params, mitm_key       },
        { "man in the middle, alters the DH params",    params, forged, ctx.peerPubKey },
    };
    for (int k = 0; k < 3; ++k) {
        SSLBuffer p = { c[k].signed_params, sizeof(params) - 1 }, sent = { c[k].sent_params, sizeof(params) - 1 };
        digest(&ctx, p, h);
        for (int i = 0; i < SSL_SHA1_DIGEST_LEN; ++i) sig[i] = (uint8_t)(h[i] ^ c[k].key[i]);
        OSStatus err = SSLVerifySignedServerKeyExchange(&ctx, false, sent, sig, SSL_SHA1_DIGEST_LEN);
        printf("case %d | %-42s | returns %6d | %s\n", k + 1, c[k].name, (int)err,
               err == 0 ? "client continues the handshake" : "client aborts");
    }
    return 0;
}
