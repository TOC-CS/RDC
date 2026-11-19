declare namespace Cloudflare {
  interface Env {
    DB?: D1Database;
    BUCKET?: R2Bucket;
    RDC_WAKE_CHANNEL?: DurableObjectNamespace;
    RDC2_DEVICE?: DurableObjectNamespace;
    RDC2_INTERNAL_KEY?: string;
    RDC2_OWNER_BOOTSTRAP?: string;
    RDC2_RUNTIME_ENABLED?: string;
    RDC_DEVICE_ID?: string;
    RDC_DEVICE_SECRET?: string;
    RDC_OWNER_BOOTSTRAP?: string;
  }
}
