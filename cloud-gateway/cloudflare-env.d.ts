declare namespace Cloudflare {
  interface Env {
    DB?: D1Database;
    BUCKET?: R2Bucket;
    RDC_DEVICE_ID?: string;
    RDC_DEVICE_SECRET?: string;
    RDC_OWNER_BOOTSTRAP?: string;
  }
}
