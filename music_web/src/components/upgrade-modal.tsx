'use client';

import PricingModal from '@/components/pricing-modal';

interface UpgradeModalProps {
  isOpen: boolean;
  onClose: () => void;
  headline?: string;
  message?: string;
}

/**
 * UpgradeModal now wraps PricingModal to show pricing plans from database.
 * This ensures consistency across the app.
 */
export function UpgradeModal({ isOpen, onClose, headline, message }: UpgradeModalProps) {
  return <PricingModal isOpen={isOpen} onClose={onClose} headline={headline} message={message} />;
}
