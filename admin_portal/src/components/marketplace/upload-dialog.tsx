import { useCallback, useRef, useState } from 'react';
import { AlertCircle, Loader2, Upload } from 'lucide-react';

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { useUploadTemplate } from '@/hooks/use-marketplace';
import type { AxiosError } from 'axios';

const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10 MB

interface ApiErrorResponse {
  error?: {
    code?: string;
    message?: string;
    details?: Record<string, unknown>;
  };
}

interface UploadDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function UploadDialog({ open, onOpenChange }: UploadDialogProps) {
  const uploadTemplate = useUploadTemplate();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [clientError, setClientError] = useState<string | null>(null);
  const [apiErrors, setApiErrors] = useState<string[]>([]);

  const isUploading = uploadTemplate.isPending;

  const resetState = useCallback(() => {
    setSelectedFile(null);
    setClientError(null);
    setApiErrors([]);
    uploadTemplate.reset();
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  }, [uploadTemplate]);

  function handleOpenChange(nextOpen: boolean) {
    if (!nextOpen) {
      resetState();
    }
    onOpenChange(nextOpen);
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    setClientError(null);
    setApiErrors([]);
    uploadTemplate.reset();

    const file = e.target.files?.[0] ?? null;

    if (!file) {
      setSelectedFile(null);
      return;
    }

    if (!file.name.toLowerCase().endsWith('.zip')) {
      setClientError('Only .zip files are accepted.');
      setSelectedFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
      return;
    }

    if (file.size > MAX_FILE_SIZE) {
      setClientError(
        `File size (${(file.size / 1024 / 1024).toFixed(1)} MB) exceeds the 10 MB limit.`,
      );
      setSelectedFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
      return;
    }

    setSelectedFile(file);
  }

  function handleUpload() {
    if (!selectedFile) return;

    setApiErrors([]);

    uploadTemplate.mutate(selectedFile, {
      onSuccess: () => {
        resetState();
        onOpenChange(false);
      },
      onError: (error) => {
        const axiosError = error as AxiosError<ApiErrorResponse>;
        const apiError = axiosError.response?.data?.error;

        if (apiError) {
          const messages: string[] = [];
          if (apiError.message) {
            messages.push(apiError.message);
          }

          // Extract detailed field/file errors from details
          if (apiError.details) {
            const details = apiError.details;

            if (details.missing_files && Array.isArray(details.missing_files)) {
              messages.push(
                `Missing files: ${(details.missing_files as string[]).join(', ')}`,
              );
            }

            if (details.invalid_fields && typeof details.invalid_fields === 'object') {
              const fields = details.invalid_fields as Record<string, string>;
              Object.entries(fields).forEach(([field, reason]) => {
                messages.push(`${field}: ${reason}`);
              });
            }

            if (details.name && details.version) {
              messages.push(
                `Duplicate: "${details.name}" version ${details.version} already exists.`,
              );
            }
          }

          setApiErrors(messages.length > 0 ? messages : ['Upload failed. Please try again.']);
        } else {
          setApiErrors([
            axiosError.message || 'Upload failed. Please try again.',
          ]);
        }
      },
    });
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Upload Template</DialogTitle>
          <DialogDescription>
            Upload a template bundle (.zip) containing template.json, preview.png, and manifest.json
            at the zip root or inside one folder.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {/* File input */}
          <div className="space-y-2">
            <label
              htmlFor="template-file"
              className="text-sm font-medium text-slate-200"
            >
              Template Bundle
            </label>
            <input
              ref={fileInputRef}
              id="template-file"
              type="file"
              accept=".zip"
              onChange={handleFileChange}
              disabled={isUploading}
              className="block w-full text-sm text-slate-300 file:mr-4 file:rounded-lg file:border-0 file:bg-slate-800 file:px-4 file:py-2 file:text-sm file:font-medium file:text-slate-200 hover:file:bg-slate-700 disabled:opacity-50"
            />
            <p className="text-xs text-slate-500">
              Maximum file size: 10 MB
            </p>
          </div>

          {/* Upload progress */}
          {isUploading && (
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-sm text-slate-400">
                <Loader2 className="h-4 w-4 animate-spin" />
                Uploading…
              </div>
              <Progress value={undefined} className="h-2" />
            </div>
          )}

          {/* Client-side validation error */}
          {clientError && (
            <div className="flex items-start gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-3">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-400" />
              <p className="text-sm text-red-300">{clientError}</p>
            </div>
          )}

          {/* API validation errors */}
          {apiErrors.length > 0 && (
            <div className="space-y-1 rounded-lg border border-red-500/30 bg-red-500/10 p-3">
              <div className="flex items-center gap-2">
                <AlertCircle className="h-4 w-4 shrink-0 text-red-400" />
                <span className="text-sm font-medium text-red-300">
                  Upload failed
                </span>
              </div>
              <ul className="ml-6 list-disc space-y-0.5">
                {apiErrors.map((msg, i) => (
                  <li key={i} className="text-sm text-red-300">
                    {msg}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Selected file info */}
          {selectedFile && !isUploading && apiErrors.length === 0 && !clientError && (
            <div className="flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-800/50 p-3">
              <Upload className="h-4 w-4 text-slate-400" />
              <span className="text-sm text-slate-300">{selectedFile.name}</span>
              <span className="text-xs text-slate-500">
                ({(selectedFile.size / 1024 / 1024).toFixed(2)} MB)
              </span>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => handleOpenChange(false)}
            disabled={isUploading}
          >
            Cancel
          </Button>
          <Button
            type="button"
            onClick={handleUpload}
            disabled={!selectedFile || isUploading || !!clientError}
          >
            {isUploading && <Loader2 className="h-4 w-4 animate-spin" />}
            Upload
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
