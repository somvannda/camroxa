import { ApiClientError } from "../services/api-client";
import { logger } from "../services/logger";
import { fail } from "../shared/types";

export function toError(error: unknown) {
  if (error instanceof ApiClientError) {
    return fail(error.code, error.message, error.detail, error.retryable);
  }
  logger.error("unhandled ipc error", { error: String(error) });
  return fail("INTERNAL_ERROR", "Something went wrong. Try again.", String(error), true);
}
