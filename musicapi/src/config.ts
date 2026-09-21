import "dotenv/config";
import { randomUUID } from "node:crypto";

export const config = {
  /** Full cookie header (optional, sent as `Cookie` on Clerk requests). */
  cookie: process.env.SUNO_COOKIE ?? "",
  /** Durable Clerk `__client` cookie value — used to mint/refresh JWTs. */
  clientCookie: process.env.SUNO_CLIENT_COOKIE ?? "",
  /** One-off JWT (simplest; expires ~1h). Mutually preferred if set. */
  jwt: process.env.SUNO_JWT ?? "",
  clerkUrl: process.env.SUNO_CLERK_URL ?? "https://auth.suno.com",
  apiUrl: process.env.SUNO_API_URL ?? "https://studio-api-prod.suno.com",
  model: process.env.SUNO_MODEL ?? "chirp-auk-turbo",
  captchaToken: process.env.SUNO_CAPTCHA_TOKEN ?? "",
  twoCaptchaKey: process.env.TWOCAPTCHA_KEY ?? "",
  // device-id is the browser's ajs_anonymous_id / suno_device_id value.
  deviceId: process.env.SUNO_DEVICE_ID ?? randomUUID(),
  databaseUrl:
    process.env.DATABASE_URL ?? "postgres://postgres:postgres@localhost:5432/sunoapi",
  jwtSecret: process.env.JWT_SECRET ?? "dev-secret-change-me",
  bakong: {
    apiToken: process.env.BAKONG_API_TOKEN ?? "",
    accountId: process.env.BAKONG_ACCOUNT_ID ?? "",
    merchantName: process.env.BAKONG_MERCHANT_NAME ?? "Camxora Music API",
    merchantCity: process.env.BAKONG_MERCHANT_CITY ?? "Phnom Penh",
    apiBaseUrl: process.env.BAKONG_API_BASE_URL ?? "https://api-bakong.nbc.gov.kh",
    useSit: (process.env.BAKONG_USE_SIT ?? "false") === "true",
  },
};
