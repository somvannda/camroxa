import type { Metadata } from "next";
import { Suspense } from "react";
import { CheckoutView } from "@/components/CheckoutView";

export const metadata: Metadata = {
  title: "Checkout",
};

export default function CheckoutPage() {
  return (
    <Suspense fallback={<p className="fine">Preparing checkout…</p>}>
      <CheckoutView />
    </Suspense>
  );
}
