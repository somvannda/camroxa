import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs))
}

export function detectImageMimeType(imageBase64: string): string {
  if (imageBase64.startsWith('/9j/')) {
    return 'image/jpeg'
  }
  if (imageBase64.startsWith('iVBORw0KGgo')) {
    return 'image/png'
  }
  if (imageBase64.startsWith('UklGR')) {
    return 'image/webp'
  }
  if (imageBase64.startsWith('R0lGOD')) {
    return 'image/gif'
  }
  if (imageBase64.startsWith('Qk')) {
    return 'image/bmp'
  }
  return 'image/png'
}

export function toImageDataUrl(imageBase64: string): string {
  return `data:${detectImageMimeType(imageBase64)};base64,${imageBase64}`
}

export function getImageFileExtension(imageBase64: string): string {
  const mimeType = detectImageMimeType(imageBase64)
  if (mimeType === 'image/jpeg') {
    return 'jpg'
  }
  if (mimeType === 'image/webp') {
    return 'webp'
  }
  if (mimeType === 'image/gif') {
    return 'gif'
  }
  if (mimeType === 'image/bmp') {
    return 'bmp'
  }
  return 'png'
}
