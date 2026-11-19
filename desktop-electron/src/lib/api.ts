import type { ApiRequest, ApiResponse } from "../../electron/shared/types";

export class BridgeError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly detail?: unknown,
    public readonly retryable = false,
  ) {
    super(message);
    this.name = "BridgeError";
  }
}

export async function apiRequest<T = unknown>(request: ApiRequest): Promise<T> {
  const result = await window.camxora.api.request(request);
  if (!result.ok) {
    throw new BridgeError(result.error.code, result.error.message, result.error.detail, result.error.retryable);
  }
  return (result.data as ApiResponse).data as T;
}

export function errorMessage(error: unknown): string {
  if (error instanceof BridgeError) return error.message;
  if (error instanceof Error) return error.message;
  return "Something went wrong.";
}
