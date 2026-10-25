import { musicAuthFetch } from "@/lib/auth-fetch";

export type TopupStatus = {
  status: string;
  fulfilled: boolean;
  pack_name: string;
  credits: number;
};

export async function fetchTopupStatus(paymentId: string): Promise<TopupStatus> {
  const response = await musicAuthFetch(
    `/api/v3/topups/payments/${encodeURIComponent(paymentId)}`
  );
  if (!response.ok) {
    throw new Error(`Could not check payment (${response.status})`);
  }
  return (await response.json()) as TopupStatus;
}
