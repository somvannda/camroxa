export function paginate<T>(rows: T[], page: number, pageSize: number) {
  const start = page * pageSize;
  return rows.slice(start, start + pageSize);
}

