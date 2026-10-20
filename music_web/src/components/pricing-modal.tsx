'use client';

import TopupModal from '@/components/topup-modal';

type PricingModalProps = {
  isOpen: boolean;
  onClose: () => void;
  /**
   * Kept only for call-site compatibility. Packs have no billing cycle, so the
   * value is ignored.
   */
  defaultBillingCycle?: 'monthly' | 'yearly';
};

/**
 * Pricing is packs-only now.
 *
 * Subscriptions are no longer sold on music.camxora.com, so this is a thin
 * wrapper over the single credit-pack dialog. Keeping the same component name
 * means every existing entry point (site header, footer, shell switcher, credit
 * header, upgrade modal) shows the same pack store with no call-site changes.
 */
export default function PricingModal({ isOpen, onClose }: PricingModalProps) {
  return <TopupModal isOpen={isOpen} onClose={onClose} />;
}
