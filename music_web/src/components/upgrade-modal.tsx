'use client';

import PricingModal from '@/components/pricing-modal';

interface UpgradeModalProps {
  isOpen: boolean;
  onClose: () => void;
}

/**
 * UpgradeModal now wraps PricingModal to show pricing plans from database.
 * This ensures consistency across the app.
 */
export function UpgradeModal({ isOpen, onClose }: UpgradeModalProps) {
  return <PricingModal isOpen={isOpen} onClose={onClose} />;
}
