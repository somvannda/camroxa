import { Metadata } from 'next';
import PricingPageClient from '@/components/pricing-page-client';

export const metadata: Metadata = {
  title: 'Pricing',
  description: 'Choose the perfect plan for your music creation needs',
};

export default function PricingPage() {
  return <PricingPageClient />;
}
