"use client";

import { platformJson } from "@/lib/auth-fetch";

export type CreditPack = {
  id: string;
  name: string;
  price_cents: number;
  song_credits: number;
  request_count: number;
  is_active: boolean;
};

export async function listCreditPacks(): Promise<CreditPack[]> {
  return platformJson<CreditPack[]>({
    path: "/credits/packs",
    method: "GET",
  });
}
