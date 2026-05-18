import dayjs from "dayjs";

export function formatDateTime(value?: string): string {
  if (!value) return "-";
  const d = dayjs(value);
  if (!d.isValid()) return value;
  return d.format("YYYY-MM-DD HH:mm:ss");
}

export function formatDate(value?: string): string {
  if (!value) return "-";
  const d = dayjs(value);
  if (!d.isValid()) return value;
  return d.format("YYYY-MM-DD");
}

