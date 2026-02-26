import { useEffect, useMemo, useState } from "react";

const fetchJson = async (url, options = {}) => {
  const res = await fetch(url, options);
  if (!res.ok) {
    throw new Error(`${url} failed with ${res.status}`);
  }
  return res.json();
};

const fmt = (value, digits = 2) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "-";
  }
  return Number(value).toFixed(digits);
};

const fmtPct = (value, digits = 2) => (value === null || value === undefined ? "-" : `${fmt(value, digits)}%`);
const fmtMoney = (value) => (value === null || value === undefined ? "-" : `$${fmt(value, 2)}`);
const fmtTs = (value) => (value ? new Date(value).toLocaleString() : "-");
const fmtDuration = (ms) => {
  if (!ms || ms < 0) return "-";
  const totalMinutes = Math.floor(ms / 60000);
  const days = Math.floor(totalMinutes / (24 * 60));
  const hours = Math.floor((totalMinutes % (24 * 60)) / 60);
  const minutes = totalMinutes % 60;
  return `${days}d ${hours}h ${minutes}m`;
};

export default function ForwardTestPage() {
  const [status, setStatus] = useState(null);
  const [summary, setSummary] = useState(null);
  const [equity, setEquity] = useState([]);
  const [tradesData, setTradesData] = useState({ items: [], total: 0, limit: 100, offset: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [tradesFilters, setTradesFilters] = useState({ symbol: "", tf: "", direction: "" });
  const [tradesLimit, setTradesLimit] = useState(100);
  const [tradesOffset, setTradesOffset] = useState(0);

  const loadOverview = async () => {
    const [statusRes, summaryRes, equityRes] = await Promise.all([
      fetchJson("/api/forward_test/status"),
      fetchJson("/api/forward_test/summary"),
      fetchJson("/api/forward_test/equity?limit=3000")
    ]);
    setStatus(statusRes);
    setSummary(summaryRes);
    setEquity(Array.isArray(equityRes.items) ? equityRes.items : []);
  };

  const loadTrades = async () => {
    const params = new URLSearchParams();
    params.set("limit", String(tradesLimit));
    params.set("offset", String(tradesOffset));
    if (tradesFilters.symbol) params.set("symbol", tradesFilters.symbol);
    if (tradesFilters.tf) params.set("tf", tradesFilters.tf);
    if (tradesFilters.direction) params.set("direction", tradesFilters.direction);
    const data = await fetchJson(`/api/forward_test/trades?${params.toString()}`);
    setTradesData(data);
  };

  const refreshAll = async () => {
    setLoading(true);
    try {
      await Promise.all([loadOverview(), loadTrades()]);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refreshAll();
  }, []);

  useEffect(() => {
    loadTrades().catch((err) => setError(err instanceof Error ? err.message : "Unknown error"));
  }, [tradesLimit, tradesOffset, tradesFilters.symbol, tradesFilters.tf, tradesFilters.direction]);

  useEffect(() => {
    const timer = setInterval(() => {
      refreshAll();
    }, 15000);
    return () => clearInterval(timer);
  }, [tradesLimit, tradesOffset, tradesFilters.symbol, tradesFilters.tf, tradesFilters.direction]);

  const metrics = summary?.metrics ?? {};
  const breakdowns = summary?.breakdowns ?? {};
  const charts = summary?.charts ?? {};

  const cardRows = useMemo(
    () => [
      ["Net Profit", fmtMoney(metrics.net_profit)],
      ["Gross Profit", fmtMoney(metrics.gross_profit)],
      ["Gross Loss", fmtMoney(metrics.gross_loss)],
      ["Profit Factor", fmt(metrics.profit_factor, 3)],
      ["Win Rate", fmtPct(metrics.win_rate_pct)],
      ["Loss Rate", fmtPct(metrics.loss_rate_pct)],
      ["Average R:R", fmt(metrics.risk_reward_ratio, 3)],
      ["Expectancy / Trade", fmtMoney(metrics.expectancy_per_trade)],
      ["Average Win", fmtMoney(metrics.average_win)],
      ["Average Loss", fmtMoney(metrics.average_loss)],
      ["Max Drawdown", fmtPct(metrics.max_drawdown_pct)],
      ["Absolute Drawdown", fmtMoney(metrics.absolute_drawdown)],
      ["Sharpe Ratio", fmt(metrics.sharpe_ratio, 3)],
      ["Sortino Ratio", fmt(metrics.sortino_ratio, 3)],
      ["Calmar Ratio", fmt(metrics.calmar_ratio, 3)],
      ["Equity Slope / Day", fmtMoney(metrics.equity_curve_slope_per_day)],
      ["Recovery Factor", fmt(metrics.recovery_factor, 3)],
      ["Total Trades", fmt(metrics.total_trades, 0)],
      ["Funding Fees Paid", fmtMoney(metrics.funding_fees_paid)],
      ["Funding Fees Received", fmtMoney(metrics.funding_fees_received)],
      ["Trading Fees Paid", fmtMoney(metrics.trading_fees_paid)],
      ["Slippage", fmtMoney(metrics.slippage_paid)],
      ["Average Holding Time", fmtDuration(metrics.average_holding_time_ms)],
      ["Exposure Time", fmtPct(metrics.exposure_time_pct)],
      ["Margin Usage Avg", fmtPct(metrics.margin_usage_pct_avg)],
      ["Margin Usage Max", fmtPct(metrics.margin_usage_pct_max)],
      ["Liq Distance Avg", fmtPct(metrics.liquidation_distance_pct_avg)],
      ["Liq Distance Min", fmtPct(metrics.liquidation_distance_pct_min)],
      ["ROE", fmtPct(metrics.return_on_equity_pct)],
      ["Volatility of Returns", fmt(metrics.volatility_of_returns, 4)],
      ["Consecutive Wins", fmt(metrics.consecutive_wins, 0)],
      ["Consecutive Losses", fmt(metrics.consecutive_losses, 0)],
      ["Position Size Consistency", fmt(metrics.position_size_consistency, 4)],
      ["MAE Avg (R)", fmt(metrics.mae_avg_r, 3)],
      ["MFE Avg (R)", fmt(metrics.mfe_avg_r, 3)]
    ],
    [metrics]
  );

  const longShort = breakdowns.long_short_performance ?? [];
  const regimePerf = breakdowns.market_regime_performance ?? [];
  const hourPerf = breakdowns.time_of_day_performance ?? [];
  const dayPerf = breakdowns.day_of_week_performance ?? [];
  const dailyPnl = charts.daily_pnl ?? [];
  const equityCurve = charts.equity_curve?.length ? charts.equity_curve : equity;
  const drawdownCurve = (equityCurve ?? []).map((item) => ({ time: item.time, value: item.drawdown_pct ?? 0 }));
  const maeMfe = charts.mae_mfe ?? [];

  const exportTrades = async () => {
    const token = window.prompt("Enter ADMIN_TOKEN for CSV export:");
    if (!token) return;
    try {
      const res = await fetch("/api/forward_test/export.csv", {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (!res.ok) {
        throw new Error(`export failed with ${res.status}`);
      }
      const text = await res.text();
      const blob = new Blob([text], { type: "text/csv" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "forward_test_trades.csv";
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export failed");
    }
  };

  const setForwardMode = async (enabled) => {
    const token = window.prompt("Enter ADMIN_TOKEN:");
    if (!token) return;
    try {
      await fetchJson("/api/forward_test/mode", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({ enabled })
      });
      await refreshAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Mode update failed");
    }
  };

  return (
    <div className="forward-test-page">
      <section className="panel">
        <div className="panel-header">
          <h1>Forward Test</h1>
          <div className="row gap">
            <button className="btn btn-small" type="button" onClick={refreshAll}>
              Refresh
            </button>
            <button className="btn btn-small" type="button" onClick={() => setForwardMode(true)}>
              Run
            </button>
            <button className="btn btn-small" type="button" onClick={() => setForwardMode(false)}>
              Pause
            </button>
            <button className="btn btn-small" type="button" onClick={exportTrades}>
              Export CSV
            </button>
          </div>
        </div>
        {error ? <p className="error">{error}</p> : null}
        {loading && !summary ? <p className="muted">Loading forward test...</p> : null}
        <div className="forward-status-grid">
          <div className="stat-item">
            <span>Status</span>
            <strong>{status?.enabled ? "Running" : "Paused"}</strong>
          </div>
          <div className="stat-item">
            <span>Start Time</span>
            <strong>{fmtTs(status?.start_time)}</strong>
          </div>
          <div className="stat-item">
            <span>Open Positions</span>
            <strong>{fmt(status?.open_positions, 0)}</strong>
          </div>
          <div className="stat-item">
            <span>Pending Orders</span>
            <strong>{fmt(status?.pending_orders, 0)}</strong>
          </div>
          <div className="stat-item">
            <span>Leverage</span>
            <strong>{fmt(status?.leverage, 0)}x</strong>
          </div>
          <div className="stat-item">
            <span>Risk / Trade</span>
            <strong>{fmtPct((status?.risk_pct ?? 0) * 100)}</strong>
          </div>
        </div>
      </section>

      <section className="panel">
        <h2>Performance Metrics</h2>
        <div className="forward-metrics-grid">
          {cardRows.map(([label, value]) => (
            <div key={label} className="metric-card">
              <span>{label}</span>
              <strong>{value}</strong>
            </div>
          ))}
        </div>
      </section>

      <section className="panel">
        <h2>Equity Curve</h2>
        <SimpleLineChart
          points={(equityCurve ?? []).map((item) => ({ x: item.time, y: item.equity }))}
          yLabel="Equity"
        />
      </section>

      <section className="panel">
        <h2>Drawdown Curve (%)</h2>
        <SimpleLineChart
          points={(drawdownCurve ?? []).map((item) => ({ x: item.time, y: item.value }))}
          yLabel="Drawdown %"
        />
      </section>

      <section className="panel">
        <h2>Daily PnL</h2>
        <SimpleBarChart
          items={(dailyPnl ?? []).map((item) => ({ label: item.day, value: item.net_profit }))}
        />
      </section>

      <section className="panel two-col">
        <div>
          <h2>Time-of-Day Performance</h2>
          <SimpleBarChart
            items={(hourPerf ?? []).map((item) => ({ label: String(item.hour), value: item.net_profit }))}
          />
        </div>
        <div>
          <h2>Day-of-Week Performance</h2>
          <SimpleBarChart
            items={(dayPerf ?? []).map((item) => ({ label: item.day.slice(0, 3), value: item.net_profit }))}
          />
        </div>
      </section>

      <section className="panel two-col">
        <div>
          <h2>Market Regime Performance</h2>
          <SimpleBarChart
            items={(regimePerf ?? []).map((item) => ({ label: item.regime, value: item.net_profit }))}
          />
        </div>
        <div>
          <h2>Long vs Short Performance</h2>
          <SimpleBarChart
            items={(longShort ?? []).map((item) => ({ label: item.side, value: item.net_profit }))}
          />
        </div>
      </section>

      <section className="panel">
        <h2>MAE vs MFE (R)</h2>
        <SimpleScatterChart
          items={(maeMfe ?? []).map((item) => ({ x: item.mae_r, y: item.mfe_r, value: item.net_pnl }))}
          xLabel="MAE (R)"
          yLabel="MFE (R)"
        />
      </section>

      <section className="panel">
        <div className="panel-header">
          <h2>Closed Trades</h2>
          <div className="row gap">
            <input
              placeholder="Symbol"
              value={tradesFilters.symbol}
              onChange={(e) => {
                setTradesOffset(0);
                setTradesFilters((prev) => ({ ...prev, symbol: e.target.value.toUpperCase() }));
              }}
            />
            <select
              value={tradesFilters.tf}
              onChange={(e) => {
                setTradesOffset(0);
                setTradesFilters((prev) => ({ ...prev, tf: e.target.value }));
              }}
            >
              <option value="">All TF</option>
              <option value="15m">15m</option>
              <option value="1h">1h</option>
              <option value="4h">4h</option>
              <option value="1d">1d</option>
            </select>
            <select
              value={tradesFilters.direction}
              onChange={(e) => {
                setTradesOffset(0);
                setTradesFilters((prev) => ({ ...prev, direction: e.target.value }));
              }}
            >
              <option value="">All Sides</option>
              <option value="long">Long</option>
              <option value="short">Short</option>
            </select>
            <select
              value={tradesLimit}
              onChange={(e) => {
                setTradesOffset(0);
                setTradesLimit(Number(e.target.value));
              }}
            >
              <option value={50}>50</option>
              <option value={100}>100</option>
              <option value={200}>200</option>
              <option value={500}>500</option>
            </select>
          </div>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Exit Time</th>
                <th>Symbol</th>
                <th>TF</th>
                <th>Type</th>
                <th>Side</th>
                <th>Entry</th>
                <th>Exit</th>
                <th>PnL</th>
                <th>ROE</th>
                <th>MAE (R)</th>
                <th>MFE (R)</th>
                <th>Hold</th>
                <th>Reason</th>
              </tr>
            </thead>
            <tbody>
              {(tradesData.items ?? []).map((item) => (
                <tr key={item.id}>
                  <td>{fmtTs(item.exit_time)}</td>
                  <td>{item.symbol}</td>
                  <td>{item.tf}</td>
                  <td>{item.signal_type}</td>
                  <td>{item.direction}</td>
                  <td>{fmt(item.entry_price, 4)}</td>
                  <td>{fmt(item.exit_price, 4)}</td>
                  <td className={Number(item.net_pnl) >= 0 ? "pos" : "neg"}>{fmtMoney(item.net_pnl)}</td>
                  <td>{fmtPct(item.roe_pct)}</td>
                  <td>{fmt(item.mae_r, 3)}</td>
                  <td>{fmt(item.mfe_r, 3)}</td>
                  <td>{fmt(item.holding_candles, 0)} candles</td>
                  <td>{item.exit_reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="row gap">
          <button
            className="btn btn-small"
            type="button"
            disabled={tradesOffset <= 0}
            onClick={() => setTradesOffset((prev) => Math.max(0, prev - tradesLimit))}
          >
            Prev
          </button>
          <button
            className="btn btn-small"
            type="button"
            disabled={tradesOffset + tradesLimit >= (tradesData.total ?? 0)}
            onClick={() => setTradesOffset((prev) => prev + tradesLimit)}
          >
            Next
          </button>
          <span className="muted">
            {fmt(tradesOffset + 1, 0)}-{fmt(Math.min(tradesOffset + tradesLimit, tradesData.total ?? 0), 0)} of{" "}
            {fmt(tradesData.total ?? 0, 0)}
          </span>
        </div>
      </section>
    </div>
  );
}

function SimpleLineChart({ points, yLabel }) {
  const width = 980;
  const height = 280;
  const pad = 30;
  if (!Array.isArray(points) || points.length < 2) {
    return <p className="muted">Not enough data.</p>;
  }
  const xs = points.map((item) => Number(item.x));
  const ys = points.map((item) => Number(item.y));
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const xRange = maxX - minX || 1;
  const yRange = maxY - minY || 1;
  const toX = (x) => pad + ((x - minX) / xRange) * (width - pad * 2);
  const toY = (y) => height - pad - ((y - minY) / yRange) * (height - pad * 2);
  const path = points.map((item, idx) => `${idx === 0 ? "M" : "L"} ${toX(item.x)} ${toY(item.y)}`).join(" ");
  return (
    <div className="chart-wrap">
      <svg viewBox={`0 0 ${width} ${height}`} className="svg-chart">
        <rect x="0" y="0" width={width} height={height} fill="var(--panel-bg)" />
        <path d={path} fill="none" stroke="var(--accent-2)" strokeWidth="2" />
        <text x={pad} y={pad - 8} className="chart-label">
          {yLabel}: min {fmt(minY)} / max {fmt(maxY)}
        </text>
      </svg>
    </div>
  );
}

function SimpleBarChart({ items }) {
  const width = 980;
  const height = 280;
  const pad = 30;
  if (!Array.isArray(items) || items.length === 0) {
    return <p className="muted">Not enough data.</p>;
  }
  const values = items.map((item) => Number(item.value) || 0);
  const minVal = Math.min(0, ...values);
  const maxVal = Math.max(0, ...values);
  const range = maxVal - minVal || 1;
  const barWidth = (width - pad * 2) / items.length;
  const zeroY = height - pad - ((0 - minVal) / range) * (height - pad * 2);
  return (
    <div className="chart-wrap">
      <svg viewBox={`0 0 ${width} ${height}`} className="svg-chart">
        <rect x="0" y="0" width={width} height={height} fill="var(--panel-bg)" />
        <line x1={pad} y1={zeroY} x2={width - pad} y2={zeroY} stroke="var(--line-muted)" strokeWidth="1" />
        {items.map((item, idx) => {
          const value = Number(item.value) || 0;
          const x = pad + idx * barWidth + barWidth * 0.1;
          const w = barWidth * 0.8;
          const y = height - pad - ((Math.max(value, 0) - minVal) / range) * (height - pad * 2);
          const y0 = height - pad - ((Math.min(value, 0) - minVal) / range) * (height - pad * 2);
          const h = Math.max(1, Math.abs(y - y0));
          return (
            <g key={`${item.label}-${idx}`}>
              <rect x={x} y={Math.min(y, y0)} width={w} height={h} fill={value >= 0 ? "var(--pos)" : "var(--neg)"} />
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function SimpleScatterChart({ items, xLabel, yLabel }) {
  const width = 980;
  const height = 320;
  const pad = 40;
  if (!Array.isArray(items) || items.length === 0) {
    return <p className="muted">Not enough data.</p>;
  }
  const xs = items.map((item) => Number(item.x) || 0);
  const ys = items.map((item) => Number(item.y) || 0);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const xRange = maxX - minX || 1;
  const yRange = maxY - minY || 1;
  const toX = (x) => pad + ((x - minX) / xRange) * (width - pad * 2);
  const toY = (y) => height - pad - ((y - minY) / yRange) * (height - pad * 2);
  return (
    <div className="chart-wrap">
      <svg viewBox={`0 0 ${width} ${height}`} className="svg-chart">
        <rect x="0" y="0" width={width} height={height} fill="var(--panel-bg)" />
        <text x={pad} y={pad - 12} className="chart-label">
          {xLabel} vs {yLabel}
        </text>
        {items.map((item, idx) => (
          <circle
            key={idx}
            cx={toX(item.x)}
            cy={toY(item.y)}
            r="4"
            fill={(Number(item.value) || 0) >= 0 ? "var(--pos)" : "var(--neg)"}
            opacity="0.85"
          />
        ))}
      </svg>
    </div>
  );
}
