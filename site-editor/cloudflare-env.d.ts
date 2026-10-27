declare namespace Cloudflare {
  interface Env {
    DB?: D1Database;
    BUCKET?: R2Bucket;
    CDSE_CLIENT_ID?: string;
    CDSE_CLIENT_SECRET?: string;
  }
}
