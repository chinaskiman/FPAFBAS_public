import { useState } from "react";

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

const extractCandles = (record) => {
  if (!record) return [];
  return record.candles ?? record.payload?.candles_lookback ?? record.payload?.candles ?? [];
};

const downloadJson = (data, filename) => {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
};

export default function JournalDetail({ record, onClose }) {
  const [showRaw, setShowRaw] = useState(false);
  if (!record) {
    return null;
  }

  const payload = record.payload ?? {};
  const entry = payload.entry ?? {};
  const stop = payload.stop ?? {};
  const tpPlan = payload.take_profit_plan ?? record.tp_plan ?? {};
  const indicators = payload.indicators ?? record.indicators ?? {};
  const candles = extractCandles(record);
  const candleRows = candles.slice(-20);

  return (
    <div className="drawer">
      <div className="drawer-header">
        <strong>
          {record.symbol} {record.timeframe} {record.direction}
        </strong>
        <button className="btn btn-small" type="button" onClick={onClose}>
          Close
        </button>
      </div>
      <div className="drawer-meta">
        <span>{formatTimestamp(record.created_at_ms ?? payload.created_at_ms)}</span>
        <span>Signal ID: {record.signal_id}</span>
      </div>
      <div className="drawer-meta">
        <span>Notification: {payload.notification?.message ?? record.notification?.message ?? "-"}</span>
      </div>

      <h4>Entry</h4>
      <div className="drawer-meta">
        <span>Mode: {entry.mode ?? "NEXT_OPEN"}</span>
        <span>Planned: {formatTimestamp(entry.planned_time_ms)}</span>
        <span>Entry Time: {formatTimestamp(entry.time_ms)}</span>
        <span>Entry Price: {formatNumber(entry.price ?? record.entry_price)}</span>
      </div>

      <h4>Stop + TP plan</h4>
      <div className="drawer-meta">
        <span>SL: {formatNumber(stop.price ?? record.stop_price)}</span>
        <span>Rule: {stop.rule ?? record.stop_rule ?? "-"}</span>
      </div>
      <div className="drawer-meta">
        <span>TP1: RR {tpPlan.tp1?.rr ?? "-"} / {tpPlan.tp1?.qty_pct ?? "-"}% / {formatNumber(tpPlan.tp1?.price)}</span>
        <span>TP2: RR {tpPlan.tp2?.rr ?? "-"} / {tpPlan.tp2?.qty_pct ?? "-"}% / {formatNumber(tpPlan.tp2?.price)}</span>
        <span>TP3: RR {tpPlan.tp3?.rr ?? "-"} / {tpPlan.tp3?.qty_pct ?? "-"}% / {formatNumber(tpPlan.tp3?.price)}</span>
        <span>Runner: {tpPlan.runner?.qty_pct ?? "-"}% / {tpPlan.runner?.rule ?? "-"}</span>
      </div>

      <h4>Indicators (snapshot)</h4>
      <div className="drawer-meta">
        <span>RSI: {formatNumber(indicators.last?.rsi14 ?? indicators.rsi14)}</span>
        <span>ATR: {formatNumber(indicators.last?.atr5 ?? indicators.atr5)}</span>
        <span>ADX: {formatNumber(indicators.last?.adx14 ?? indicators.adx14)}</span>
        <span>+DI: {formatNumber(indicators.last?.di_plus ?? indicators.di_plus)}</span>
        <span>-DI: {formatNumber(indicators.last?.di_minus ?? indicators.di_minus)}</span>
      </div>

      <h4>Candles (last 20)</h4>
      {candles.length === 0 ? (
        <p className="muted">No candles stored.</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Time</th>
                <th>O</th>
                <th>H</th>
                <th>L</th>
                <th>C</th>
                <th>V</th>
              </tr>
            </thead>
            <tbody>
              {candleRows.map((candle) => (
                <tr key={candle.ts_ms}>
                  <td>{formatTimestamp(candle.ts_ms)}</td>
                  <td>{formatNumber(candle.o)}</td>
                  <td>{formatNumber(candle.h)}</td>
                  <td>{formatNumber(candle.l)}</td>
                  <td>{formatNumber(candle.c)}</td>
                  <td>{formatNumber(candle.v)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="inline-form">
        <button
          className="btn btn-small"
          type="button"
          onClick={() => downloadJson(candles, `candles_${record.signal_id}.json`)}
          disabled={candles.length === 0}
        >
          Download candles JSON
        </button>
        <button className="btn btn-small" type="button" onClick={() => setShowRaw((prev) => !prev)}>
          {showRaw ? "Hide Raw JSON" : "Show Raw JSON"}
        </button>
      </div>
      {showRaw ? <pre>{JSON.stringify(record, null, 2)}</pre> : null}
    </div>
  );
}
