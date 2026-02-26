export const buildJournalQuery = ({ symbol, timeframe, fromMs, toMs, limit }) => {
  const params = new URLSearchParams();
  if (symbol) params.set("symbol", symbol);
  if (timeframe) params.set("timeframe", timeframe);
  if (fromMs) params.set("from_ms", String(fromMs));
  if (toMs) params.set("to_ms", String(toMs));
  if (limit) params.set("limit", String(limit));
  return params.toString();
};

export const fetchJournalSignals = async (filters) => {
  const query = buildJournalQuery(filters);
  const res = await fetch(`/api/journal/signals?${query}`);
  if (!res.ok) {
    throw new Error(`Journal signals failed (${res.status})`);
  }
  return res.json();
};

export const fetchJournalSignal = async (signalId) => {
  const res = await fetch(`/api/journal/signals/${signalId}`);
  if (!res.ok) {
    throw new Error(`Journal signal failed (${res.status})`);
  }
  return res.json();
};

export const exportJournalJsonl = async (filters, token) => {
  const query = buildJournalQuery(filters);
  const headers = {};
  if (token) {
    headers.Authorization = `Bearer ${token}`;
    headers["X-Admin-Token"] = token;
  }
  const res = await fetch(`/api/journal/export.jsonl?${query}`, { headers });
  if (!res.ok) {
    const text = await res.text();
    const error = new Error(text || `Export failed (${res.status})`);
    error.status = res.status;
    throw error;
  }
  return res.blob();
};
