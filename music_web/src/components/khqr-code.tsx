'use client';

import { QRCodeSVG } from 'qrcode.react';

type KhqrCodeProps = {
  value: string;
  size?: number;
};

export default function KhqrCode({ value, size = 240 }: KhqrCodeProps) {
  return (
    <div className="flex items-center justify-center rounded-2xl bg-white p-4">
      <QRCodeSVG value={value} size={size} level="M" marginSize={0} />
    </div>
  );
}
