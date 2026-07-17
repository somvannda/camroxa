export interface BackupEntry {
  filename: string;
  created_at: string;
  file_size_bytes: number;
  total_records: number;
  tables: string[];
}

export interface ResetResult {
  status: string;
  backup_filename: string;
  tables_cleared: string[];
  record_counts: Record<string, number>;
  total_records_deleted: number;
  redis_flushed: boolean;
  redis_error?: string | null;
}

export interface RestoreResult {
  status: string;
  backup_filename: string;
  records_restored: number;
  records_skipped: number;
}

export interface ResetRequest {
  password: string;
}

export interface RestoreRequest {
  backup_filename: string;
  password: string;
}

export interface BackupListResponse {
  backups: BackupEntry[];
}
