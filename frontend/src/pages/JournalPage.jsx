import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { exportJournalJsonl, fetchJournalSignals } from "../api/journal.js";

const formatNumber = (value) => {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }
  return Number(value).toFixed(2);
};

const formatTimestamp = (value) => {
  if (!value) return "-";
  return new Date(value).toLocaleString();
};

const getLocalMs = (date, endOfDay = false) => {
  if (!date) return null;
  const iso = endOfDay ? `${date}T23:59:59` : `${date}T00:00:00`;
  const ms = new Date(iso).getTime();
  return Number.isFinite(ms) ? ms : null;
};

const downloadBlob = (blob, filename) => {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
};

export default function JournalPage({ symbols = [] }) {
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [filters, setFilters] = useState({
    symbol: "",
    timeframe: "",
    fromDate: "",
    toDate: "",
    limit: 100
  });
  const [search, setSearch] = useState("");
  const [adminToken, setAdminToken] = useState("");
  const [exportStatus, setExportStatus] = useState("");

  const loadSignals = async () => {
    setLoading(true);
    setError("");
    try {
      const fromMs = getLocalMs(filters.fromDate);
      const toMs = getLocalMs(filters.toDate, true);
      const data = await fetchJournalSignals({
        symbol: filters.symbol,
        timeframe: filters.timeframe,
        fromMs,
        toMs,
        limit: filters.limit
      });
      setItems(Array.isArray(data.items) ? data.items : []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load journal");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSignals();
  }, [filters.symbol, filters.timeframe, filters.fromDate, filters.toDate, filters.limit]);

  const quickRange = (days) => {
    const now = new Date();
    const from = new Date(now.getTime() - days * 24 * 60 * 60 * 1000);
    setFilters((prev) => ({
      ...prev,
      fromDate: from.toISOString().slice(0, 10),
      toDate: now.toISOString().slice(0, 10)
    }));
  };

  const filteredItems = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (!term) return items;
    return items.filter((item) => {
      const haystack = [item.symbol, item.signal_id].filter(Boolean).join(" ").toLowerCase();
      return haystack.includes(term);
    });
  }, [items, search]);

  const uniqueSymbols = useMemo(() => {
    if (symbols.length > 0) return symbols;
    return Array.from(new Set(items.map((item) => item.symbol).filter(Boolean)));
  }, [symbols, items]);

  const handleSelectDetail = (signalId) => {
    navigate(`/journal/${signalId}`);
  };

  const handleExport = async () => {
    setExportStatus("");
    try {
      const fromMs = getLocalMs(filters.fromDate);
      const toMs = getLocalMs(filters.toDate, true);
      const blob = await exportJournalJsonl(
        {
          symbol: filters.symbol,
          timeframe: filters.timeframe,
          fromMs,
          toMs,
          limit: filters.limit
        },
        adminToken.trim()
      );
      const stamp = new Date().toISOString().slice(0, 10).replace(/-/g, "");
      downloadBlob(blob, `journal_export_${stamp}.jsonl`);
      setExportStatus("Exported");
    } catch (err) {
      if (err?.status === 401 || err?.status === 403) {
        setExportStatus("Invalid token");
      } else {
        setExportStatus(err instanceof Error ? err.message : "Export failed");
      }
    }
  };

  return (
    <section className="card" id="journal">
      <h2>Journal</h2>
      {error ? <div className="error">{error}</div> : null}

      <div className="di-controls">
        <label className="field">
          <span>Symbol</span>
          <select value={filters.symbol} onChange={(event) => setFilters((prev) => ({ ...prev, symbol: event.target.value }))}>
            <option value="">All</option>
            {uniqueSymbols.map((symbol) => (
              <option key={`journal-${symbol}`} value={symbol}>
                {symbol}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Timeframe</span>
          <select value={filters.timeframe} onChange={(event) => setFilters((prev) => ({ ...prev, timeframe: event.target.value }))}>
            <option value="">All</option>
            <option value="15m">15m</option>
            <option value="1h">1h</option>
            <option value="4h">4h</option>
            <option value="1d">1d</option>
            <option value="1w">1w</option>
          </select>
        </label>
        <label className="field">
          <span>From</span>
          <input type="date" value={filters.fromDate} onChange={(event) => setFilters((prev) => ({ ...prev, fromDate: event.target.value }))} />
        </label>
        <label className="field">
          <span>To</span>
          <input type="date" value={filters.toDate} onChange={(event) => setFilters((prev) => ({ ...prev, toDate: event.target.value }))} />
        </label>
        <label className="field">
          <span>Limit</span>
          <select value={filters.limit} onChange={(event) => setFilters((prev) => ({ ...prev, limit: Number(event.target.value) }))}>
            <option value={50}>50</option>
            <option value={100}>100</option>
            <option value={200}>200</option>
          </select>
        </label>
      </div>

      <div className="inline-form">
        <button className="btn btn-small" type="button" onClick={() => quickRange(1)}>
          Last 24h
        </button>
        <button className="btn btn-small" type="button" onClick={() => quickRange(7)}>
          Last 7d
        </button>
        <button className="btn btn-small" type="button" onClick={() => quickRange(30)}>
          Last 30d
        </button>
        <button className="btn btn-small" type="button" onClick={loadSignals}>
          Refresh
        </button>
      </div>

      <div className="di-controls">
        <label className="field">
          <span>Search</span>
          <input type="text" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="symbol or signal_id" />
        </label>
      </div>

      <div className="di-controls">
        <label className="field">
          <span>Admin Token (for export)</span>
          <input type="password" value={adminToken} onChange={(event) => setAdminToken(event.target.value)} />
        </label>
        <button className="btn" type="button" onClick={handleExport}>
          Export JSONL
        </button>
        {exportStatus ? <span className="muted">{exportStatus}</span> : null}
      </div>

      {loading ? <p className="muted">Loading...</p> : null}
      {!loading && filteredItems.length === 0 ? <p className="muted">No signals found.</p> : null}
      {filteredItems.length > 0 ? (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Time</th>
                <th>Symbol</th>
                <th>TF</th>
                <th>Direction</th>
                <th>Strategy</th>
                <th>Entry</th>
                <th>SL</th>
              </tr>
            </thead>
            <tbody>
              {filteredItems.map((item) => (
                <tr key={item.signal_id} className="clickable" onClick={() => handleSelectDetail(item.signal_id)}>
                  <td>{formatTimestamp(item.created_at_ms ?? item.payload?.created_at_ms)}</td>
                  <td>{item.symbol}</td>
                  <td>{item.timeframe}</td>
                  <td>{item.direction}</td>
                  <td>
                    {(item.payload?.strategy?.id ?? item.meta?.strategy_id ?? "-")}@
                    {(item.payload?.strategy?.version ?? item.meta?.strategy_version ?? "-")}
                  </td>
                  <td>{formatNumber(item.entry_price ?? item.payload?.entry?.price)}</td>
                  <td>{formatNumber(item.stop_price ?? item.payload?.stop?.price)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

    </section>
  );
}
