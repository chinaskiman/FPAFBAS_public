import { useEffect, useMemo, useRef, useState } from "react";
import { createChart } from "lightweight-charts";

const EMPTY_HEALTH = { status: "loading" };

const fetchJson = async (url, options = {}) => {
  const res = await fetch(url, options);
  if (!res.ok) {
    throw new Error(`${url} failed with ${res.status}`);
  }
  return res.json();
};

export default function DashboardPage({ view = "dashboard" }) {
  const [health, setHealth] = useState(EMPTY_HEALTH);
  const [alertsData, setAlertsData] = useState({ items: [], limit: 100, offset: 0, total: 0 });
  const [alertsError, setAlertsError] = useState("");
  const [alertsTab, setAlertsTab] = useState("history");
  const [alertsFilters, setAlertsFilters] = useState({
    symbol: "",
    tf: "",
    type: "",
    direction: "",
    notified: "",
    sinceMs: ""
  });
  const [alertsLimit, setAlertsLimit] = useState(100);
  const [alertsOffset, setAlertsOffset] = useState(0);
  const [alertsSearch, setAlertsSearch] = useState("");
  const [alertsAutoRefresh, setAlertsAutoRefresh] = useState(false);
  const [alertDetailsId, setAlertDetailsId] = useState(null);
  const [alertDetails, setAlertDetails] = useState(null);
  const [alertDetailsError, setAlertDetailsError] = useState("");
  const [watchlist, setWatchlist] = useState(null);
  const [watchlistFormSymbol, setWatchlistFormSymbol] = useState("");
  const [watchlistBulkSymbols, setWatchlistBulkSymbols] = useState("");
  const [watchlistFormTfs, setWatchlistFormTfs] = useState(["15m", "1h", "4h"]);
  const [watchlistFilter, setWatchlistFilter] = useState("");
  const [watchlistSelectedSymbols, setWatchlistSelectedSymbols] = useState([]);
  const [watchlistFormError, setWatchlistFormError] = useState("");
  const [watchlistSaveStatus, setWatchlistSaveStatus] = useState("");
  const [indicators, setIndicators] = useState(null);
  const [indicatorError, setIndicatorError] = useState("");
  const [pivotStats, setPivotStats] = useState(null);
  const [pivotError, setPivotError] = useState("");
  const [symbols, setSymbols] = useState([]);
  const [selectedSymbol, setSelectedSymbol] = useState("");
  const [levels, setLevels] = useState(null);
  const [levelsError, setLevelsError] = useState("");
  const [pinnedInput, setPinnedInput] = useState("");
  const [disabledInput, setDisabledInput] = useState("");
  const [bias, setBias] = useState(null);
  const [biasError, setBiasError] = useState("");
  const [diPeak, setDiPeak] = useState(null);
  const [diPeakError, setDiPeakError] = useState("");
  const [diTf, setDiTf] = useState("15m");
  const [diWindow] = useState(30);
  const [volData, setVolData] = useState(null);
  const [volError, setVolError] = useState("");
  const [volTf, setVolTf] = useState("15m");
  const [rsiData, setRsiData] = useState(null);
  const [rsiError, setRsiError] = useState("");
  const [rsiTf, setRsiTf] = useState("15m");
  const [levelEvents, setLevelEvents] = useState(null);
  const [levelEventsError, setLevelEventsError] = useState("");
  const [levelEventsTf, setLevelEventsTf] = useState("1h");
  const [setupCandles, setSetupCandles] = useState(null);
  const [setupError, setSetupError] = useState("");
  const [setupTf, setSetupTf] = useState("15m");
  const [openings, setOpenings] = useState(null);
  const [openingsError, setOpeningsError] = useState("");
  const [openingsTf, setOpeningsTf] = useState("15m");
  const [qualitySettings, setQualitySettings] = useState(null);
  const [qualityError, setQualityError] = useState("");
  const [qualitySaveStatus, setQualitySaveStatus] = useState("");
  const [suppressed, setSuppressed] = useState([]);
  const [suppressedError, setSuppressedError] = useState("");
  const [suppressedReason, setSuppressedReason] = useState("all");
  const [chartCandles, setChartCandles] = useState([]);
  const [chartLevels, setChartLevels] = useState([]);
  const [chartLevelEvents, setChartLevelEvents] = useState([]);
  const [chartSetupCandles, setChartSetupCandles] = useState([]);
  const [chartOpenings, setChartOpenings] = useState([]);
  const [chartError, setChartError] = useState("");
  const [chartTf, setChartTf] = useState("15m");
  const [chartLoading, setChartLoading] = useState(false);
  const [chartAutoRefresh, setChartAutoRefresh] = useState(false);
  const [showZones, setShowZones] = useState(true);
  const [showSma7, setShowSma7] = useState(true);
  const [showLevelEvents, setShowLevelEvents] = useState(true);
  const [showSetupCandles, setShowSetupCandles] = useState(true);
  const [showOpenings, setShowOpenings] = useState(true);
  const [showHwcBadge, setShowHwcBadge] = useState(false);
  const [showDiWidget, setShowDiWidget] = useState(false);
  const [showRsiWidget, setShowRsiWidget] = useState(false);
  const [showVolumeWidget, setShowVolumeWidget] = useState(true);
  const [chartLegend, setChartLegend] = useState(null);
  const [chartDetails, setChartDetails] = useState(null);
  const [chartDiPeak, setChartDiPeak] = useState(null);
  const [chartDiError, setChartDiError] = useState("");
  const [chartRsi, setChartRsi] = useState(null);
  const [chartRsiError, setChartRsiError] = useState("");
  const [chartVol, setChartVol] = useState(null);
  const [chartVolError, setChartVolError] = useState("");
  const [replayData, setReplayData] = useState(null);
  const [replaySummary, setReplaySummary] = useState(null);
  const [replayError, setReplayError] = useState("");
  const [replayLoading, setReplayLoading] = useState(false);
  const [replayTf, setReplayTf] = useState("1h");
  const [replayStep, setReplayStep] = useState(1);
  const [replayWarmup, setReplayWarmup] = useState(300);
  const [replayFromMs, setReplayFromMs] = useState("");
  const [replayToMs, setReplayToMs] = useState("");
  const [replayIndex, setReplayIndex] = useState(0);
  const [replayDetails, setReplayDetails] = useState(null);
  const [replaySideFilter, setReplaySideFilter] = useState("all");
  const [replayBiasAlignmentFilter, setReplayBiasAlignmentFilter] = useState("all");
  const [replayOutcomeFilter, setReplayOutcomeFilter] = useState("all");
  const [replaySortBy, setReplaySortBy] = useState("time_desc");
  const [pollerStatus, setPollerStatus] = useState(null);
  const [pollerError, setPollerError] = useState("");
  const [telegramText, setTelegramText] = useState("");
  const [telegramFeedback, setTelegramFeedback] = useState(null);
  const [error, setError] = useState("");

  const watchlistTfOptions = ["15m", "1h", "4h", "1d"];
  const watchlistDefaultTfs = ["15m", "1h", "4h"];
  const watchlistItems = useMemo(() => {
    if (!Array.isArray(watchlist?.symbols)) {
      return [];
    }
    return watchlist.symbols;
  }, [watchlist]);
  const filteredWatchlistItems = useMemo(() => {
    const needle = watchlistFilter.trim().toUpperCase();
    if (!needle) {
      return watchlistItems;
    }
    return watchlistItems.filter((item) => String(item?.symbol || "").toUpperCase().includes(needle));
  }, [watchlistItems, watchlistFilter]);
  const chartContainerRef = useRef(null);
  const volumeContainerRef = useRef(null);
  const chartAbortRef = useRef(null);
  const markerDetailsRef = useRef(new Map());
  const chartTfRef = useRef(chartTf);
  const chartRefs = useRef({
    main: null,
    volume: null,
    candleSeries: null,
    smaSeries: null,
    volumeSeries: null,
    volMa5Series: null,
    volMa10Series: null,
    priceLines: [],
    zoneSeries: []
  });

  useEffect(() => {
    const load = async () => {
      try {
        const [healthData, watchlistData] = await Promise.all([
          fetchJson("/health"),
          fetchJson("/api/watchlist")
        ]);
        setHealth(healthData);
        setWatchlist(watchlistData);
        const symbolsData = await fetchJson("/api/symbols");
        const apiSymbols = Array.isArray(symbolsData.symbols) ? symbolsData.symbols.map((item) => item.symbol) : [];
        const fallbackSymbols = watchlistData?.symbols ? watchlistData.symbols.map((item) => item.symbol) : [];
        const merged = apiSymbols.length > 0 ? apiSymbols : fallbackSymbols;
        setSymbols(merged);
        if (merged.length > 0) {
          setSelectedSymbol(merged[0]);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error");
      }
    };
    load();
  }, []);

  useEffect(() => {
    const valid = new Set(watchlistItems.map((item) => item.symbol));
    setWatchlistSelectedSymbols((prev) => prev.filter((symbol) => valid.has(symbol)));
  }, [watchlistItems]);

  useEffect(() => {
    if (!chartContainerRef.current || !volumeContainerRef.current) {
      return undefined;
    }
    const mainChart = createChart(chartContainerRef.current, {
      height: 360,
      layout: { background: { color: "#ffffff" }, textColor: "#1f1c17" },
      grid: { vertLines: { color: "#efe6d8" }, horzLines: { color: "#efe6d8" } },
      rightPriceScale: { borderColor: "#e0d8c8" },
      timeScale: { borderColor: "#e0d8c8" }
    });
    const candleSeries = mainChart.addCandlestickSeries({
      upColor: "#0f6b5c",
      downColor: "#7a2f2f",
      borderVisible: false,
      wickUpColor: "#0f6b5c",
      wickDownColor: "#7a2f2f"
    });
    const smaSeries = mainChart.addLineSeries({ color: "#1f1c17", lineWidth: 2 });

    const volumeChart = createChart(volumeContainerRef.current, {
      height: 140,
      layout: { background: { color: "#ffffff" }, textColor: "#1f1c17" },
      grid: { vertLines: { color: "#efe6d8" }, horzLines: { color: "#efe6d8" } },
      rightPriceScale: { borderColor: "#e0d8c8" },
      timeScale: { borderColor: "#e0d8c8" }
    });
    const volumeSeries = volumeChart.addHistogramSeries({
      color: "#b8b0a3",
      priceFormat: { type: "volume" }
    });
    const volMa5Series = volumeChart.addLineSeries({ color: "#0f6b5c", lineWidth: 1 });
    const volMa10Series = volumeChart.addLineSeries({ color: "#7a6a45", lineWidth: 1 });

    chartRefs.current = {
      main: mainChart,
      volume: volumeChart,
      candleSeries,
      smaSeries,
      volumeSeries,
      volMa5Series,
      volMa10Series,
      priceLines: [],
      zoneSeries: []
    };

    const handleCrosshairMove = (param) => {
      if (!param || !param.time) {
        setChartLegend(null);
        return;
      }
      const seriesData = param.seriesData.get(candleSeries);
      if (!seriesData) {
        setChartLegend(null);
        return;
      }
      const timeMs = typeof param.time === "number" ? param.time * 1000 : null;
      const open = seriesData.open ?? seriesData.value ?? 0;
      const close = seriesData.close ?? seriesData.value ?? 0;
      const changePct = open ? ((close - open) / open) * 100 : 0;
      setChartLegend({
        time: timeMs,
        open,
        high: seriesData.high ?? open,
        low: seriesData.low ?? open,
        close,
        changePct
      });
    };

    const handleChartClick = (param) => {
      if (!param || !param.time) {
        return;
      }
      const timeSec = typeof param.time === "number" ? param.time : param.time?.timestamp;
      if (!timeSec) {
        return;
      }
      const details = findMarkerDetails(timeSec, markerDetailsRef.current, chartTfRef.current);
      if (details) {
        setChartDetails(details);
      }
    };

    mainChart.subscribeCrosshairMove(handleCrosshairMove);
    mainChart.subscribeClick(handleChartClick);

    const handleResize = () => {
      const mainWidth = chartContainerRef.current?.clientWidth ?? 0;
      const volumeWidth = volumeContainerRef.current?.clientWidth ?? 0;
      if (mainWidth) {
        mainChart.applyOptions({ width: mainWidth });
      }
      if (volumeWidth) {
        volumeChart.applyOptions({ width: volumeWidth });
      }
    };
    handleResize();
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      mainChart.unsubscribeCrosshairMove(handleCrosshairMove);
      mainChart.unsubscribeClick(handleChartClick);
      mainChart.remove();
      volumeChart.remove();
    };
  }, []);

  useEffect(() => {
    chartTfRef.current = chartTf;
  }, [chartTf]);

  const buildAlertsQuery = () => {
    const params = new URLSearchParams();
    if (alertsFilters.symbol) params.set("symbol", alertsFilters.symbol);
    if (alertsFilters.tf) params.set("tf", alertsFilters.tf);
    if (alertsFilters.type) params.set("type", alertsFilters.type);
    if (alertsFilters.direction) params.set("direction", alertsFilters.direction);
    if (alertsFilters.notified !== "") params.set("notified", alertsFilters.notified);
    if (alertsFilters.sinceMs) params.set("since_ms", alertsFilters.sinceMs);
    params.set("limit", String(alertsLimit));
    params.set("offset", String(alertsOffset));
    return params.toString();
  };

  const fetchAlertsPage = async () => {
    try {
      const query = buildAlertsQuery();
      const data = await fetchJson(`/api/alerts?${query}`);
      setAlertsData(data);
      setAlertsError("");
    } catch (err) {
      setAlertsError(err instanceof Error ? err.message : "Unknown error");
    }
  };

  useEffect(() => {
    fetchAlertsPage();
  }, [alertsFilters, alertsLimit, alertsOffset]);

  useEffect(() => {
    if (!alertsAutoRefresh) {
      return undefined;
    }
    const timer = setInterval(() => {
      if (alertDetailsId) {
        return;
      }
      fetchAlertsPage();
    }, 15000);
    return () => clearInterval(timer);
  }, [alertsAutoRefresh, alertDetailsId, alertsFilters, alertsLimit, alertsOffset]);

  useEffect(() => {
    const loadPollerStatus = async () => {
      try {
        const data = await fetchJson("/api/poller/status");
        setPollerStatus(data);
        setPollerError("");
      } catch (err) {
        setPollerError(err instanceof Error ? err.message : "Unknown error");
      }
    };
    loadPollerStatus();
    const timer = setInterval(loadPollerStatus, 10000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    const loadIndicators = async () => {
      try {
        const data = await fetchJson("/api/indicators/BTCUSDT/1h?limit=200");
        setIndicators(data);
      } catch (err) {
        setIndicatorError(err instanceof Error ? err.message : "Unknown error");
      }
    };
    loadIndicators();
  }, []);

  useEffect(() => {
    const loadQuality = async () => {
      try {
        const data = await fetchJson("/api/quality/settings");
        setQualitySettings(data);
        setQualityError("");
      } catch (err) {
        setQualityError(err instanceof Error ? err.message : "Unknown error");
      }
    };
    loadQuality();
  }, []);

  useEffect(() => {
    const loadSuppressed = async () => {
      try {
        const data = await fetchJson("/api/quality/suppressed?limit=20");
        setSuppressed(Array.isArray(data.items) ? data.items : []);
        setSuppressedError("");
      } catch (err) {
        setSuppressedError(err instanceof Error ? err.message : "Unknown error");
      }
    };
    loadSuppressed();
    const timer = setInterval(loadSuppressed, 10000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    const loadLevels = async () => {
      if (!selectedSymbol) {
        return;
      }
      try {
        const data = await fetchJson(`/api/levels/${selectedSymbol}?debug=1`);
        setLevels(data);
        setLevelsError("");
      } catch (err) {
        setLevelsError(err instanceof Error ? err.message : "Unknown error");
      }
    };
    loadLevels();
  }, [selectedSymbol]);

  useEffect(() => {
    const loadBias = async () => {
      if (!selectedSymbol) {
        return;
      }
      try {
        const data = await fetchJson(`/api/hwc/${selectedSymbol}`);
        setBias(data);
        setBiasError("");
      } catch (err) {
        setBiasError(err instanceof Error ? err.message : "Unknown error");
      }
    };
    loadBias();
  }, [selectedSymbol]);

  useEffect(() => {
    const loadDiPeak = async () => {
      if (!selectedSymbol || !diTf) {
        return;
      }
      try {
        const data = await fetchJson(`/api/di_peak/${selectedSymbol}/${diTf}?window=${diWindow}`);
        setDiPeak(data);
        setDiPeakError("");
      } catch (err) {
        setDiPeakError(err instanceof Error ? err.message : "Unknown error");
      }
    };
    loadDiPeak();
  }, [selectedSymbol, diTf, diWindow]);

  useEffect(() => {
    const loadVolume = async () => {
      if (!selectedSymbol || !volTf) {
        return;
      }
      try {
        const data = await fetchJson(`/api/volume/${selectedSymbol}/${volTf}?k=3`);
        setVolData(data);
        setVolError("");
      } catch (err) {
        setVolError(err instanceof Error ? err.message : "Unknown error");
      }
    };
    loadVolume();
  }, [selectedSymbol, volTf]);

  useEffect(() => {
    const loadRsi = async () => {
      if (!selectedSymbol || !rsiTf) {
        return;
      }
      try {
        const data = await fetchJson(`/api/rsi/${selectedSymbol}/${rsiTf}`);
        setRsiData(data);
        setRsiError("");
      } catch (err) {
        setRsiError(err instanceof Error ? err.message : "Unknown error");
      }
    };
    loadRsi();
  }, [selectedSymbol, rsiTf]);

  useEffect(() => {
    const loadLevelEvents = async () => {
      if (!selectedSymbol || !levelEventsTf) {
        return;
      }
      try {
        const data = await fetchJson(`/api/level_events/${selectedSymbol}/${levelEventsTf}?limit=300`);
        setLevelEvents(data);
        setLevelEventsError("");
      } catch (err) {
        setLevelEventsError(err instanceof Error ? err.message : "Unknown error");
      }
    };
    loadLevelEvents();
  }, [selectedSymbol, levelEventsTf]);

  useEffect(() => {
    const loadSetupCandles = async () => {
      if (!selectedSymbol || !setupTf) {
        return;
      }
      try {
        const data = await fetchJson(`/api/setup_candles/${selectedSymbol}/${setupTf}?limit=300`);
        setSetupCandles(data);
        setSetupError("");
      } catch (err) {
        setSetupError(err instanceof Error ? err.message : "Unknown error");
      }
    };
    loadSetupCandles();
  }, [selectedSymbol, setupTf]);

  useEffect(() => {
    const loadOpenings = async () => {
      if (!selectedSymbol || !openingsTf) {
        return;
      }
      try {
        const data = await fetchJson(`/api/openings/${selectedSymbol}/${openingsTf}?limit=300`);
        setOpenings(data);
        setOpeningsError("");
      } catch (err) {
        setOpeningsError(err instanceof Error ? err.message : "Unknown error");
      }
    };
    loadOpenings();
  }, [selectedSymbol, openingsTf]);

  useEffect(() => {
    const loadChartDi = async () => {
      if (!selectedSymbol || !chartTf || !showDiWidget) {
        setChartDiPeak(null);
        setChartDiError("");
        return;
      }
      try {
        const data = await fetchJson(`/api/di_peak/${selectedSymbol}/${chartTf}?window=${diWindow}`);
        setChartDiPeak(data);
        setChartDiError("");
      } catch (err) {
        setChartDiError(err instanceof Error ? err.message : "Unknown error");
      }
    };
    loadChartDi();
  }, [selectedSymbol, chartTf, showDiWidget, diWindow]);

  useEffect(() => {
    const loadChartRsi = async () => {
      if (!selectedSymbol || !chartTf || !showRsiWidget) {
        setChartRsi(null);
        setChartRsiError("");
        return;
      }
      try {
        const data = await fetchJson(`/api/rsi/${selectedSymbol}/${chartTf}`);
        setChartRsi(data);
        setChartRsiError("");
      } catch (err) {
        setChartRsiError(err instanceof Error ? err.message : "Unknown error");
      }
    };
    loadChartRsi();
  }, [selectedSymbol, chartTf, showRsiWidget]);

  useEffect(() => {
    const loadChartVolume = async () => {
      if (!selectedSymbol || !chartTf || !showVolumeWidget) {
        setChartVol(null);
        setChartVolError("");
        return;
      }
      try {
        const data = await fetchJson(`/api/volume/${selectedSymbol}/${chartTf}?k=3`);
        setChartVol(data);
        setChartVolError("");
      } catch (err) {
        setChartVolError(err instanceof Error ? err.message : "Unknown error");
      }
    };
    loadChartVolume();
  }, [selectedSymbol, chartTf, showVolumeWidget]);

  const fetchChartData = async () => {
    if (!selectedSymbol || !chartTf) {
      return;
    }
    if (replayItems.length > 0) {
      return;
    }
    if (chartAbortRef.current) {
      chartAbortRef.current.abort();
    }
    const controller = new AbortController();
    chartAbortRef.current = controller;
    setChartLoading(true);
    try {
      const candles = await fetchJson(`/api/candles/${selectedSymbol}/${chartTf}?limit=500`, {
        signal: controller.signal
      });
      setChartCandles(Array.isArray(candles) ? candles : []);
      setChartError("");

      const requests = await Promise.allSettled([
        fetchJson(`/api/levels/${selectedSymbol}?debug=1`, { signal: controller.signal }),
        fetchJson(`/api/level_events/${selectedSymbol}/${chartTf}?limit=500`, { signal: controller.signal }),
        fetchJson(`/api/setup_candles/${selectedSymbol}/${chartTf}?limit=500`, { signal: controller.signal }),
        fetchJson(`/api/openings/${selectedSymbol}/${chartTf}?limit=500`, { signal: controller.signal })
      ]);

      const levels = requests[0].status === "fulfilled" ? requests[0].value : null;
      const levelEvents = requests[1].status === "fulfilled" ? requests[1].value : null;
      const setupCandles = requests[2].status === "fulfilled" ? requests[2].value : null;
      const openingsData = requests[3].status === "fulfilled" ? requests[3].value : null;

      setChartLevels(levels?.final_levels_detailed ?? []);
      setChartLevelEvents(levelEvents?.events ?? []);
      setChartSetupCandles(setupCandles?.items ?? []);
      setChartOpenings(openingsData?.signals ?? []);
    } catch (err) {
      if (err?.name === "AbortError") {
        return;
      }
      setChartError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setChartLoading(false);
    }
  };

  useEffect(() => {
    fetchChartData();
  }, [selectedSymbol, chartTf, replayData]);

  useEffect(() => {
    setChartDetails(null);
  }, [selectedSymbol, chartTf, replayData]);

  useEffect(() => {
    if (!chartAutoRefresh) {
      return undefined;
    }
    const timer = setInterval(() => {
      fetchChartData();
    }, 30000);
    return () => clearInterval(timer);
  }, [chartAutoRefresh, selectedSymbol, chartTf, replayData]);

  useEffect(() => {
    const replayItemsLocal = Array.isArray(replayData?.items) ? replayData.items : [];
    const replayItemLocal =
      replayItemsLocal.length > 0 ? replayItemsLocal[Math.min(replayIndex, replayItemsLocal.length - 1)] : null;
    const isReplayMode = replayItemsLocal.length > 0;
    if (!isReplayMode && (!chartCandles || chartCandles.length === 0)) {
      return;
    }
    const refs = chartRefs.current;
    if (!refs.candleSeries || !refs.smaSeries) {
      return;
    }
    const candles = isReplayMode ? buildReplayCandles(replayItemsLocal) : chartCandles;
    const candleSeries = toChartCandles(candles);
    refs.candleSeries.setData(candleSeries);
    const sma7 = showSma7 ? computeSmaSeries(candles, 7) : [];
    refs.smaSeries.setData(sma7);

    const volumeSeries = showVolumeWidget ? toVolumeSeries(candles) : [];
    const volMa5 = showVolumeWidget ? computeSmaSeries(candles, 5, "volume") : [];
    const volMa10 = showVolumeWidget ? computeSmaSeries(candles, 10, "volume") : [];
    refs.volumeSeries?.setData(volumeSeries);
    refs.volMa5Series?.setData(volMa5);
    refs.volMa10Series?.setData(volMa10);

    if (Array.isArray(refs.priceLines)) {
      refs.priceLines.forEach((line) => {
        try {
          refs.candleSeries.removePriceLine(line);
        } catch {
          // ignore
        }
      });
      refs.priceLines = [];
    }
    if (Array.isArray(refs.zoneSeries)) {
      refs.zoneSeries.forEach((series) => {
        try {
          refs.main.removeSeries(series);
        } catch {
          // ignore
        }
      });
      refs.zoneSeries = [];
    }

    const levels = isReplayMode ? buildReplayLevels(replayItemLocal) : chartLevels;
    const displayLevels = filterLevelsForChart(levels, candles);
    const timeRange = getTimeRange(candles);
    if (showZones) {
      displayLevels.forEach((level) => {
        if (!timeRange) {
          return;
        }
        const role = level.role ?? "mixed";
        const color =
          role === "support"
            ? "rgba(15, 107, 92, 0.12)"
            : role === "resistance"
              ? "rgba(122, 47, 47, 0.12)"
              : "rgba(122, 106, 69, 0.08)";
        const zoneSeries = refs.main.addAreaSeries({
          topColor: color,
          bottomColor: color,
          lineColor: color,
          lineWidth: 1,
          priceLineVisible: false,
          lastValueVisible: false,
          baseValue: { type: "price", price: level.zone_low }
        });
        zoneSeries.setData([
          { time: timeRange.start, value: level.zone_high },
          { time: timeRange.end, value: level.zone_high }
        ]);
        refs.zoneSeries.push(zoneSeries);
        const label = `${role} ${Number(level.center).toFixed(2)}`;
        const line = refs.candleSeries.createPriceLine({
          price: level.center,
          color: role === "support" ? "#0f6b5c" : role === "resistance" ? "#7a2f2f" : "#7a6a45",
          lineWidth: 1,
          axisLabelVisible: true,
          title: label
        });
        refs.priceLines.push(line);
      });
    }

    const markers = isReplayMode
      ? buildReplayMarkers(replayItemLocal?.signals ?? [])
      : buildWorkspaceMarkers(
          showLevelEvents ? chartLevelEvents : [],
          showSetupCandles ? chartSetupCandles : [],
          showOpenings ? chartOpenings : []
        );
    if (isReplayMode) {
      markerDetailsRef.current = new Map();
    } else {
      markerDetailsRef.current = buildMarkerDetailsMap(
        showLevelEvents ? chartLevelEvents : [],
        showSetupCandles ? chartSetupCandles : [],
        showOpenings ? chartOpenings : [],
        selectedSymbol,
        chartTf,
        chartCandles
      );
    }
    refs.candleSeries.setMarkers(markers);
    refs.main?.timeScale().fitContent();
    refs.volume?.timeScale().fitContent();
  }, [
    chartCandles,
    chartLevels,
    chartLevelEvents,
    chartSetupCandles,
    chartOpenings,
    replayData,
    replayIndex,
    selectedSymbol,
    chartTf,
    showZones,
    showSma7,
    showLevelEvents,
    showSetupCandles,
    showOpenings,
    showVolumeWidget
  ]);

  const loadPivots = async () => {
    try {
      const stats = await fetchPivotCounts();
      setPivotStats(stats);
      setPivotError("");
    } catch (err) {
      setPivotError(err instanceof Error ? err.message : "Unknown error");
    }
  };

  const handleAddPinned = () => {
    const value = Number(pinnedInput);
    if (!Number.isFinite(value)) {
      return;
    }
    setWatchlist((prev) => updateOverrides(prev, selectedSymbol, "add", value));
    setPinnedInput("");
  };

  const handleAddDisabled = () => {
    const value = Number(disabledInput);
    if (!Number.isFinite(value)) {
      return;
    }
    setWatchlist((prev) => updateOverrides(prev, selectedSymbol, "disable", value));
    setDisabledInput("");
  };

  const handleRemovePinned = (value) => {
    setWatchlist((prev) => removeOverride(prev, selectedSymbol, "add", value));
  };

  const handleRemoveDisabled = (value) => {
    setWatchlist((prev) => removeOverride(prev, selectedSymbol, "disable", value));
  };

  const handleSaveLevels = async () => {
    if (!watchlist) {
      return;
    }
    try {
      await saveWatchlist(watchlist);
    } catch (err) {
      setLevelsError(err instanceof Error ? err.message : "Unknown error");
    }
  };

  const saveWatchlist = async (nextWatchlist) => {
    await fetchJson("/api/watchlist", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(nextWatchlist)
    });
    const refreshed = await fetchJson("/api/watchlist");
    setWatchlist(refreshed);
    const updatedSymbols = refreshed?.symbols ? refreshed.symbols.map((item) => item.symbol) : [];
    setSymbols(updatedSymbols);
    if (selectedSymbol && !updatedSymbols.includes(selectedSymbol)) {
      setSelectedSymbol(updatedSymbols[0] ?? "");
    }
    if (selectedSymbol) {
      const updatedLevels = await fetchJson(`/api/levels/${selectedSymbol}`);
      setLevels(updatedLevels);
    }
    setWatchlistSaveStatus("Saved");
  };

  const handleToggleWatchlistTf = (tf) => {
    setWatchlistFormTfs((prev) => {
      if (prev.includes(tf)) {
        return prev.filter((item) => item !== tf);
      }
      return [...prev, tf];
    });
  };

  const handleAddWatchlistSymbol = async () => {
    if (!watchlist) {
      return;
    }
    setWatchlistFormError("");
    setWatchlistSaveStatus("");
    const symbol = watchlistFormSymbol.trim().toUpperCase();
    const validationError = validateWatchlistSymbol(symbol);
    if (validationError) {
      setWatchlistFormError(validationError);
      return;
    }
    const validTfs = watchlistFormTfs.filter((tf) => watchlistTfOptions.includes(tf));
    if (validTfs.length === 0) {
      setWatchlistFormError("Select at least one timeframe.");
      return;
    }
    if (validTfs.length !== watchlistFormTfs.length) {
      setWatchlistFormError("Invalid timeframe selection.");
      return;
    }
    if (watchlist.symbols?.some((item) => item.symbol === symbol)) {
      setWatchlistFormError("Symbol already exists.");
      return;
    }
    const updated = structuredClone(watchlist);
    updated.symbols = [...(updated.symbols ?? []), buildWatchlistSymbolEntry(updated.symbols?.[0], symbol, validTfs)];
    try {
      await saveWatchlist(updated);
      setWatchlistFormSymbol("");
      setWatchlistFormTfs(watchlistDefaultTfs);
      setWatchlistSaveStatus(`Added ${symbol}.`);
    } catch (err) {
      setWatchlistFormError(err instanceof Error ? err.message : "Failed to save watchlist.");
    }
  };

  const handleAddWatchlistSymbolsBulk = async () => {
    if (!watchlist) {
      return;
    }
    setWatchlistFormError("");
    setWatchlistSaveStatus("");
    const validTfs = watchlistFormTfs.filter((tf) => watchlistTfOptions.includes(tf));
    if (validTfs.length === 0) {
      setWatchlistFormError("Select at least one timeframe.");
      return;
    }
    const parsed = parseWatchlistSymbolInput(watchlistBulkSymbols);
    if (parsed.length === 0) {
      setWatchlistFormError("Paste at least one symbol.");
      return;
    }

    const existing = new Set((watchlist.symbols ?? []).map((item) => item.symbol));
    const updated = structuredClone(watchlist);
    const added = [];
    const duplicates = [];
    const invalid = [];
    parsed.forEach((raw) => {
      const symbol = raw.toUpperCase();
      const errorMessage = validateWatchlistSymbol(symbol);
      if (errorMessage) {
        invalid.push(symbol);
        return;
      }
      if (existing.has(symbol)) {
        duplicates.push(symbol);
        return;
      }
      updated.symbols = [
        ...(updated.symbols ?? []),
        buildWatchlistSymbolEntry(updated.symbols?.[0], symbol, validTfs)
      ];
      existing.add(symbol);
      added.push(symbol);
    });

    if (added.length === 0) {
      setWatchlistFormError("No symbols were added. Check duplicates/format.");
      return;
    }

    try {
      await saveWatchlist(updated);
      setWatchlistBulkSymbols("");
      const skipped = duplicates.length + invalid.length;
      setWatchlistSaveStatus(
        `Added ${added.length} symbol(s).${skipped > 0 ? ` Skipped ${skipped} (duplicates/invalid).` : ""}`
      );
    } catch (err) {
      setWatchlistFormError(err instanceof Error ? err.message : "Failed to save watchlist.");
    }
  };

  const handleRemoveWatchlistSymbol = async (symbol) => {
    if (!watchlist) {
      return;
    }
    setWatchlistFormError("");
    setWatchlistSaveStatus("");
    const updated = structuredClone(watchlist);
    updated.symbols = (updated.symbols ?? []).filter((item) => item.symbol !== symbol);
    if (updated.symbols.length === 0) {
      setWatchlistFormError("Watchlist must contain at least one symbol.");
      return;
    }
    try {
      await saveWatchlist(updated);
      setWatchlistSelectedSymbols((prev) => prev.filter((item) => item !== symbol));
      setWatchlistSaveStatus(`Removed ${symbol}.`);
    } catch (err) {
      setWatchlistFormError(err instanceof Error ? err.message : "Failed to save watchlist.");
    }
  };

  const handleToggleWatchlistSelection = (symbol) => {
    setWatchlistSelectedSymbols((prev) => {
      if (prev.includes(symbol)) {
        return prev.filter((item) => item !== symbol);
      }
      return [...prev, symbol];
    });
  };

  const handleSelectAllVisibleWatchlistSymbols = () => {
    setWatchlistSelectedSymbols((prev) => {
      const next = new Set(prev);
      filteredWatchlistItems.forEach((item) => next.add(item.symbol));
      return Array.from(next);
    });
  };

  const handleClearWatchlistSelection = () => {
    setWatchlistSelectedSymbols([]);
  };

  const handleRemoveSelectedWatchlistSymbols = async () => {
    if (!watchlist || watchlistSelectedSymbols.length === 0) {
      return;
    }
    setWatchlistFormError("");
    setWatchlistSaveStatus("");
    const selected = new Set(watchlistSelectedSymbols);
    const currentCount = (watchlist.symbols ?? []).length;
    const nextCount = currentCount - selected.size;
    if (nextCount < 1) {
      setWatchlistFormError("Watchlist must contain at least one symbol.");
      return;
    }
    if (!window.confirm(`Remove ${selected.size} selected symbol(s)?`)) {
      return;
    }
    const updated = structuredClone(watchlist);
    updated.symbols = (updated.symbols ?? []).filter((item) => !selected.has(item.symbol));
    try {
      await saveWatchlist(updated);
      setWatchlistSelectedSymbols([]);
      setWatchlistSaveStatus(`Removed ${selected.size} symbol(s).`);
    } catch (err) {
      setWatchlistFormError(err instanceof Error ? err.message : "Failed to save watchlist.");
    }
  };

  const handleSelectWatchlistSymbol = (symbol) => {
    setSelectedSymbol(symbol);
    const entry = watchlist?.symbols?.find((item) => item.symbol === symbol);
    const entryTfs = Array.isArray(entry?.entry_tfs) && entry.entry_tfs.length > 0 ? entry.entry_tfs : watchlistDefaultTfs;
    if (entryTfs.length > 0) {
      setChartTf(entryTfs[0]);
    }
  };

  const handleToggleWatchlistEntryTf = async (symbol, tf) => {
    if (!watchlist) {
      return;
    }
    setWatchlistFormError("");
    setWatchlistSaveStatus("");
    if (!watchlistTfOptions.includes(tf)) {
      setWatchlistFormError("Invalid timeframe selection.");
      return;
    }
    const updated = structuredClone(watchlist);
    const entry = updated.symbols?.find((item) => item.symbol === symbol);
    if (!entry) {
      return;
    }
    const current = Array.isArray(entry.entry_tfs) && entry.entry_tfs.length > 0 ? entry.entry_tfs : watchlistDefaultTfs;
    const nextTfs = current.includes(tf) ? current.filter((item) => item !== tf) : [...current, tf];
    if (nextTfs.length === 0) {
      setWatchlistFormError("Select at least one timeframe.");
      return;
    }
    entry.entry_tfs = nextTfs;
    try {
      await saveWatchlist(updated);
    } catch (err) {
      setWatchlistFormError(err instanceof Error ? err.message : "Failed to save watchlist.");
    }
  };

  const handleSaveQuality = async () => {
    if (!qualitySettings) {
      return;
    }
    try {
      const data = await fetchJson("/api/quality/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(qualitySettings)
      });
      setQualitySettings(data.quality ?? qualitySettings);
      setQualitySaveStatus("Saved");
      setQualityError("");
    } catch (err) {
      setQualityError(err instanceof Error ? err.message : "Unknown error");
      setQualitySaveStatus("");
    }
  };

  const handleSetPollerMode = async (mode) => {
    try {
      const data = await fetchJson("/api/poller/mode", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode })
      });
      setPollerStatus(data);
      setPollerError("");
    } catch (err) {
      setPollerError(err instanceof Error ? err.message : "Unknown error");
    }
  };

  const handleSendTelegramTest = async () => {
    try {
      const payload = telegramText ? { text: telegramText } : {};
      const data = await fetchJson("/api/telegram/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const message = data.ok ? "Sent" : `Failed: ${data.error ?? "Unknown error"}`;
      setTelegramFeedback({ ok: data.ok, message });
    } catch (err) {
      const message = err instanceof Error ? `Failed: ${err.message}` : "Failed: Unknown error";
      setTelegramFeedback({ ok: false, message });
    }
  };

  const handleReplayQuickRange = (hours) => {
    const now = Date.now();
    setReplayFromMs(String(now - hours * 60 * 60 * 1000));
    setReplayToMs(String(now));
  };

  const handleReplayRun = async () => {
    if (!selectedSymbol) {
      return;
    }
    setReplayError("");
    setReplayLoading(true);
    try {
      const fromMs = Number(replayFromMs);
      const toMs = Number(replayToMs);
      if (!Number.isFinite(fromMs) || !Number.isFinite(toMs)) {
        throw new Error("from_ms and to_ms must be numbers.");
      }
      const params = new URLSearchParams({
        from_ms: String(fromMs),
        to_ms: String(toMs),
        step: String(replayStep),
        warmup: String(replayWarmup),
        debug: "1"
      });
      const [summary, data] = await Promise.all([
        fetchJson(`/api/replay_summary/${selectedSymbol}/${replayTf}?${params}`),
        fetchJson(`/api/replay/${selectedSymbol}/${replayTf}?${params}`)
      ]);
      setReplaySummary(summary);
      setReplayData(data);
      const items = Array.isArray(data.items) ? data.items : [];
      setReplayIndex(items.length > 0 ? items.length - 1 : 0);
      setReplayDetails(null);
    } catch (err) {
      setReplayError(err instanceof Error ? err.message : "Replay failed.");
    } finally {
      setReplayLoading(false);
    }
  };

  const replayItems = Array.isArray(replayData?.items) ? replayData.items : [];
  const replayItem = replayItems[replayIndex];
  const replayTradeOutcomes = useMemo(
    () => buildReplayTradeOutcomes(replayItems, replayData?.symbol, replayData?.tf),
    [replayItems, replayData?.symbol, replayData?.tf]
  );
  const replayTradeRows = useMemo(() => {
    let rows = [...replayTradeOutcomes];
    if (replaySideFilter !== "all") {
      rows = rows.filter((item) => item.direction === replaySideFilter);
    }
    if (replayOutcomeFilter !== "all") {
      rows = rows.filter((item) => item.outcome === replayOutcomeFilter);
    }
    if (replayBiasAlignmentFilter === "aligned_3") {
      rows = rows.filter((item) => item.bias_alignment_count === 3);
    } else if (replayBiasAlignmentFilter === "aligned_2") {
      rows = rows.filter((item) => item.bias_alignment_count === 2);
    } else if (replayBiasAlignmentFilter === "aligned_0_1") {
      rows = rows.filter((item) => item.bias_alignment_count <= 1);
    }

    rows.sort((a, b) => {
      if (replaySortBy === "time_asc") {
        return a.signal_time - b.signal_time;
      }
      if (replaySortBy === "time_desc") {
        return b.signal_time - a.signal_time;
      }
      if (replaySortBy === "max_rr_desc") {
        return b.max_rr - a.max_rr;
      }
      if (replaySortBy === "max_dd_desc") {
        return b.max_drawdown_r - a.max_drawdown_r;
      }
      if (replaySortBy === "duration_rr2_asc") {
        return compareNullableNumber(a.time_to_rr2_ms, b.time_to_rr2_ms);
      }
      if (replaySortBy === "alignment_desc") {
        return b.bias_alignment_count - a.bias_alignment_count || b.signal_time - a.signal_time;
      }
      if (replaySortBy === "direction") {
        const rank = { long: 0, short: 1 };
        return (rank[a.direction] ?? 9) - (rank[b.direction] ?? 9) || b.signal_time - a.signal_time;
      }
      return b.signal_time - a.signal_time;
    });
    return rows;
  }, [replayTradeOutcomes, replaySideFilter, replayOutcomeFilter, replayBiasAlignmentFilter, replaySortBy]);
  const replayTradeStats = useMemo(() => summarizeReplayOutcomes(replayTradeRows), [replayTradeRows]);

  const handleReplaySignalClick = (signal) => {
    setReplayDetails(signal);
  };

  const handleAlertFilterChange = (key, value) => {
    setAlertsFilters((prev) => ({ ...prev, [key]: value }));
    setAlertsOffset(0);
  };

  const handleQuickRange = (hours) => {
    const sinceMs = Date.now() - hours * 60 * 60 * 1000;
    handleAlertFilterChange("sinceMs", String(sinceMs));
  };

  const handleClearRange = () => {
    handleAlertFilterChange("sinceMs", "");
  };

  const handleExportCsv = () => {
    const query = buildAlertsQuery();
    const url = `/api/alerts/export.csv?${query}`;
    window.open(url, "_blank", "noopener");
  };

  const handleAlertRowClick = async (alertId) => {
    if (!alertId) {
      return;
    }
    try {
      setAlertDetailsId(alertId);
      const data = await fetchJson(`/api/alerts/${alertId}`);
      setAlertDetails(data);
      setAlertDetailsError("");
    } catch (err) {
      setAlertDetailsError(err instanceof Error ? err.message : "Unknown error");
    }
  };

  const handleCloseDetails = () => {
    setAlertDetailsId(null);
    setAlertDetails(null);
    setAlertDetailsError("");
  };

  const handleCopyText = async (text) => {
    if (!text) {
      return;
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(text);
    } else {
      window.prompt("Copy to clipboard:", text);
    }
  };

  const alertsItems = Array.isArray(alertsData.items) ? alertsData.items : [];
  const alertSearchTerm = alertsSearch.trim().toLowerCase();
  const filteredAlerts = alertSearchTerm
    ? alertsItems.filter((item) => {
        const haystack = [
          item.symbol,
          item.type,
          item.direction,
          item.level,
          item.notify_error
        ]
          .filter(Boolean)
          .join(" ")
          .toLowerCase();
        return haystack.includes(alertSearchTerm);
      })
    : alertsItems;
  const showingStart = filteredAlerts.length > 0 ? alertsOffset + 1 : 0;
  const showingEnd = alertsOffset + filteredAlerts.length;
  const totalAlerts = alertsData.total ?? 0;

  const suppressedReasons = [
    "all",
    ...Array.from(new Set(suppressed.map((item) => item.reason).filter(Boolean)))
  ];
  const filteredSuppressed =
    suppressedReason === "all"
      ? suppressed
      : suppressed.filter((item) => item.reason === suppressedReason);
  const isReplayActive = replayItems.length > 0;
  const workspaceSignals = buildWorkspaceSignalRows(
    showLevelEvents ? chartLevelEvents : [],
    showSetupCandles ? chartSetupCandles : [],
    showOpenings ? chartOpenings : [],
    selectedSymbol,
    chartTf
  );
  const replayLegend = isReplayActive ? buildLegendFromCandle(replayItem?.candle, replayItem?.time) : null;
  const liveLegend =
    !isReplayActive && chartCandles.length > 0 ? buildLegendFromCandle(chartCandles[chartCandles.length - 1]) : null;
  const chartLegendDisplay = chartLegend ?? replayLegend ?? liveLegend;
  const showDashboard = view === "dashboard";
  const showReplay = view === "replay";
  const showLevels = view === "levels";
  const showSettings = view === "settings";
  const showOps = view === "ops";

  return (
    <div className="app">
      <header className="app-header">
        <div>
          <p className="eyebrow">Binance USDT Perp Scanner</p>
          <h1>Alert Dashboard</h1>
        </div>
        <div className="status-chip">
          <span>Service</span>
          <strong>{health.status ?? "unknown"}</strong>
        </div>
      </header>

      {error ? <div className="error">{error}</div> : null}
      {showSettings ? (
        <section className="card">
        <h2>Watchlist Raw (Debug)</h2>
        {watchlistFormError ? <div className="error">{watchlistFormError}</div> : null}
        {watchlistSaveStatus ? <div className="muted">{watchlistSaveStatus}</div> : null}
        <div className="di-controls">
          <label className="field">
            <span>Add One Symbol</span>
            <input
              type="text"
              value={watchlistFormSymbol}
              onChange={(event) => setWatchlistFormSymbol(event.target.value.toUpperCase())}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  handleAddWatchlistSymbol();
                }
              }}
              placeholder="e.g. BTCUSDT"
            />
          </label>
          <div className="field">
            <span>Timeframes</span>
            <div className="inline-form">
              {watchlistTfOptions.map((tf) => (
                <label key={`tf-${tf}`} className="checkbox">
                  <input
                    type="checkbox"
                    checked={watchlistFormTfs.includes(tf)}
                    onChange={() => handleToggleWatchlistTf(tf)}
                  />
                  <span>{tf}</span>
                </label>
              ))}
            </div>
          </div>
          <button className="btn" type="button" onClick={handleAddWatchlistSymbol}>
            Add One
          </button>
        </div>

        <div className="di-controls">
          <label className="field watchlist-bulk-field">
            <span>Quick Add Symbols (comma / space / newline)</span>
            <textarea
              value={watchlistBulkSymbols}
              onChange={(event) => setWatchlistBulkSymbols(event.target.value.toUpperCase())}
              placeholder={"BTCUSDT ETHUSDT SOLUSDT\nor BTCUSDT,ETHUSDT,SOLUSDT"}
              rows={3}
            />
          </label>
          <button className="btn" type="button" onClick={handleAddWatchlistSymbolsBulk}>
            Add Many
          </button>
        </div>

        {watchlist && Array.isArray(watchlist.symbols) ? (
          <>
            <div className="di-controls">
              <label className="field">
                <span>Find Symbol</span>
                <input
                  type="text"
                  value={watchlistFilter}
                  onChange={(event) => setWatchlistFilter(event.target.value.toUpperCase())}
                  placeholder="e.g. BTC"
                />
              </label>
              <div className="inline-form">
                <button className="btn btn-small" type="button" onClick={handleSelectAllVisibleWatchlistSymbols}>
                  Select Visible
                </button>
                <button className="btn btn-small" type="button" onClick={handleClearWatchlistSelection}>
                  Clear Selection
                </button>
                <button
                  className="btn btn-small"
                  type="button"
                  disabled={watchlistSelectedSymbols.length === 0}
                  onClick={handleRemoveSelectedWatchlistSymbols}
                >
                  Remove Selected ({watchlistSelectedSymbols.length})
                </button>
              </div>
            </div>
            <p className="muted">
              Showing {filteredWatchlistItems.length} of {watchlistItems.length} symbols.
            </p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Pick</th>
                  <th>Symbol</th>
                  <th>Entry TFs</th>
                  <th>Enabled</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {filteredWatchlistItems.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="muted">
                      No symbols match the filter.
                    </td>
                  </tr>
                ) : (
                filteredWatchlistItems.map((item) => (
                  <tr key={`wl-${item.symbol}`}>
                    <td>
                      <input
                        type="checkbox"
                        checked={watchlistSelectedSymbols.includes(item.symbol)}
                        onChange={() => handleToggleWatchlistSelection(item.symbol)}
                      />
                    </td>
                    <td>{item.symbol}</td>
                    <td>
                      <div className="inline-form inline-form-tight">
                        {watchlistTfOptions.map((tf) => {
                          const entryTfs =
                            Array.isArray(item.entry_tfs) && item.entry_tfs.length > 0
                              ? item.entry_tfs
                              : watchlistDefaultTfs;
                          return (
                            <label key={`wl-${item.symbol}-${tf}`} className="checkbox">
                              <input
                                type="checkbox"
                                checked={entryTfs.includes(tf)}
                                onChange={() => handleToggleWatchlistEntryTf(item.symbol, tf)}
                              />
                              <span>{tf}</span>
                            </label>
                          );
                        })}
                      </div>
                    </td>
                    <td>{String(item.enabled)}</td>
                    <td>
                      <div className="inline-form inline-form-tight">
                        <button
                          className="btn btn-small"
                          type="button"
                          onClick={() => handleSelectWatchlistSymbol(item.symbol)}
                        >
                          Select
                        </button>
                        <button
                          className="btn btn-small"
                          type="button"
                          onClick={() => handleRemoveWatchlistSymbol(item.symbol)}
                        >
                          Remove
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
                )}
              </tbody>
            </table>
          </div>
          </>
        ) : (
          <p className="muted">Loading watchlist...</p>
        )}
      </section>
      ) : null}

      {showDashboard || showReplay ? (
      <section className="card">
        <h2>Chart Workspace</h2>
        {chartError ? <div className="error">{chartError}</div> : null}
        <div className="chart-toolbar">
          <label className="field">
            <span>Symbol</span>
            <select value={selectedSymbol} onChange={(event) => setSelectedSymbol(event.target.value)}>
              {symbols.map((symbol) => (
                <option key={`chart-${symbol}`} value={symbol}>
                  {symbol}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Timeframe</span>
            <select value={chartTf} onChange={(event) => setChartTf(event.target.value)}>
              <option value="15m">15m</option>
              <option value="1h">1h</option>
              <option value="4h">4h</option>
              <option value="1d">1d</option>
              <option value="1w">1w</option>
            </select>
          </label>
          <div className="inline-form">
            <button className="btn btn-small" type="button" onClick={fetchChartData} disabled={chartLoading || isReplayActive}>
              Refresh
            </button>
            <button
              className="btn btn-small"
              type="button"
              onClick={() => window.open(getBinanceLink(selectedSymbol), "_blank", "noopener")}
            >
              Open Binance
            </button>
            <button
              className="btn btn-small"
              type="button"
              onClick={() => window.open(getTradingViewLink(selectedSymbol), "_blank", "noopener")}
            >
              Open TradingView
            </button>
          </div>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={chartAutoRefresh}
              onChange={(event) => setChartAutoRefresh(event.target.checked)}
            />
            <span>Auto refresh (30s)</span>
          </label>
        </div>
        <div className="toggle-grid">
          <label className="checkbox">
            <input type="checkbox" checked={showZones} onChange={(event) => setShowZones(event.target.checked)} />
            <span>S/R Zones</span>
          </label>
          <label className="checkbox">
            <input type="checkbox" checked={showSma7} onChange={(event) => setShowSma7(event.target.checked)} />
            <span>SMA7</span>
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={showLevelEvents}
              onChange={(event) => setShowLevelEvents(event.target.checked)}
            />
            <span>Level Events</span>
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={showSetupCandles}
              onChange={(event) => setShowSetupCandles(event.target.checked)}
            />
            <span>Setup Candles</span>
          </label>
          <label className="checkbox">
            <input type="checkbox" checked={showOpenings} onChange={(event) => setShowOpenings(event.target.checked)} />
            <span>Openings</span>
          </label>
          <label className="checkbox">
            <input type="checkbox" checked={showHwcBadge} onChange={(event) => setShowHwcBadge(event.target.checked)} />
            <span>HWC Badge</span>
          </label>
          <label className="checkbox">
            <input type="checkbox" checked={showDiWidget} onChange={(event) => setShowDiWidget(event.target.checked)} />
            <span>DI/ADX Widget</span>
          </label>
          <label className="checkbox">
            <input type="checkbox" checked={showRsiWidget} onChange={(event) => setShowRsiWidget(event.target.checked)} />
            <span>RSI/ATR Widget</span>
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={showVolumeWidget}
              onChange={(event) => setShowVolumeWidget(event.target.checked)}
            />
            <span>Volume</span>
          </label>
        </div>

        {isReplayActive ? <p className="muted">Replay mode active - live refresh paused.</p> : null}
        {chartLoading ? <p className="muted">Loading chart...</p> : null}
        {chartLegendDisplay ? (
          <div className="chart-legend">
            <span>{formatTimestamp(chartLegendDisplay.time)}</span>
            <span>O {formatNumber(chartLegendDisplay.open)}</span>
            <span>H {formatNumber(chartLegendDisplay.high)}</span>
            <span>L {formatNumber(chartLegendDisplay.low)}</span>
            <span>C {formatNumber(chartLegendDisplay.close)}</span>
            <span className={chartLegendDisplay.changePct >= 0 ? "legend-up" : "legend-down"}>
              {chartLegendDisplay.changePct >= 0 ? "+" : ""}
              {chartLegendDisplay.changePct.toFixed(2)}%
            </span>
          </div>
        ) : null}

        {(showHwcBadge || showDiWidget || showRsiWidget || showVolumeWidget) ? (
          <div className="di-grid">
            {showHwcBadge ? (
              <div>
                <span>HWC Bias</span>
                <strong className={`bias-${bias?.hwc_bias ?? "neutral"}`}>{bias?.hwc_bias ?? "-"}</strong>
                <small>
                  Weekly: {bias?.weekly?.bias ?? "-"} / Daily: {bias?.daily?.bias ?? "-"}
                </small>
              </div>
            ) : null}
            {showDiWidget ? (
              <div>
                <span>DI / ADX</span>
                <strong>+{formatNumber(chartDiPeak?.di_plus?.last)} / -{formatNumber(chartDiPeak?.di_minus?.last)}</strong>
                <small>ADX {formatNumber(chartDiPeak?.adx14_last)}</small>
                {chartDiError ? <small className="error-text">{chartDiError}</small> : null}
              </div>
            ) : null}
            {showRsiWidget ? (
              <div>
                <span>RSI / ATR</span>
                <strong>RSI {formatNumber(chartRsi?.rsi14_last)}</strong>
                <small>ATR x{formatNumber(chartRsi?.atr_mult)} / Stop {formatNumber(chartRsi?.atr_stop_distance)}</small>
                {chartRsiError ? <small className="error-text">{chartRsiError}</small> : null}
              </div>
            ) : null}
            {showVolumeWidget ? (
              <div>
                <span>Volume</span>
                <strong>Ratio {formatNumber(chartVol?.vol_ratio)}</strong>
                <small>
                  MA5 slope ok: {String(chartVol?.vol_ma5_slope_ok ?? "-")} / Pullback decline:{" "}
                  {String(chartVol?.pullback_vol_decline ?? "-")}
                </small>
                {chartVolError ? <small className="error-text">{chartVolError}</small> : null}
              </div>
            ) : null}
          </div>
        ) : null}

        <div className="chart-stack">
          <div className="chart-canvas" ref={chartContainerRef} />
          <div className="chart-canvas chart-canvas-small" ref={volumeContainerRef} />
        </div>

        {isReplayActive ? (
          <p className="muted">Replay mode active - workspace signals hidden.</p>
        ) : workspaceSignals.length > 0 ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Type</th>
                  <th>Direction</th>
                  <th>Level</th>
                  <th>Time</th>
                  <th>Source</th>
                </tr>
              </thead>
              <tbody>
                {workspaceSignals.map((row) => (
                  <tr key={row.id} className="clickable" onClick={() => setChartDetails(row.details)}>
                    <td>{row.type}</td>
                    <td>{row.direction ?? "-"}</td>
                    <td>{formatNumber(row.level)}</td>
                    <td>{formatTimestamp(row.time)}</td>
                    <td>{row.source}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="muted">No signal markers yet.</p>
        )}

        {chartDetails ? (
          <div className="drawer">
            <div className="drawer-header">
              <strong>Signal Details</strong>
              <button className="btn btn-small" type="button" onClick={() => setChartDetails(null)}>
                Close
              </button>
            </div>
            <div className="drawer-meta">
              <span>{chartDetails.type}</span>
              <span>{chartDetails.direction}</span>
              <span>Level {formatNumber(chartDetails.level)}</span>
              <span>{formatTimestamp(chartDetails.time)}</span>
            </div>
            <div className="drawer-meta">
              <span>Entry {formatNumber(chartDetails.entry)}</span>
              <span>SL {formatNumber(chartDetails.sl)}</span>
              <span>{chartDetails.sl_reason ?? "-"}</span>
            </div>
            {chartDetails.candle ? (
              <div className="drawer-meta">
                <span>
                  Candle O/H/L/C/V: {chartDetails.candle.open}/{chartDetails.candle.high}/{chartDetails.candle.low}/
                  {chartDetails.candle.close}/{chartDetails.candle.volume}
                </span>
              </div>
            ) : null}
            {chartDetails.level_event ? (
              <div className="drawer-meta">
                <span>break {chartDetails.level_event.break_index ?? "-"}</span>
                <span>retest {chartDetails.level_event.retest_index ?? "-"}</span>
                <span>fakeout {chartDetails.level_event.fakeout_index ?? "-"}</span>
                <span>setup {chartDetails.setup_index ?? "-"}</span>
              </div>
            ) : null}
            <div className="inline-form">
              <button
                className="btn btn-small"
                type="button"
                onClick={() => handleCopyText(JSON.stringify(chartDetails, null, 2))}
              >
                Copy JSON
              </button>
              <button
                className="btn btn-small"
                type="button"
                onClick={() => window.open(getBinanceLink(chartDetails.symbol ?? selectedSymbol), "_blank", "noopener")}
              >
                Open Binance
              </button>
            </div>
            <pre>{JSON.stringify(chartDetails.context ?? {}, null, 2)}</pre>
          </div>
        ) : null}
      </section>
      ) : null}

      {showReplay ? (
      <section className="card">
        <h2>Replay</h2>
        {replayError ? <div className="error">{replayError}</div> : null}
        <div className="di-controls">
          <label className="field">
            <span>Symbol</span>
            <select value={selectedSymbol} onChange={(event) => setSelectedSymbol(event.target.value)}>
              {symbols.map((symbol) => (
                <option key={`replay-${symbol}`} value={symbol}>
                  {symbol}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>TF</span>
            <select value={replayTf} onChange={(event) => setReplayTf(event.target.value)}>
              <option value="15m">15m</option>
              <option value="1h">1h</option>
              <option value="4h">4h</option>
              <option value="1d">1d</option>
              <option value="1w">1w</option>
            </select>
          </label>
          <label className="field">
            <span>Step</span>
            <select value={replayStep} onChange={(event) => setReplayStep(Number(event.target.value))}>
              <option value={1}>1</option>
              <option value={3}>3</option>
              <option value={6}>6</option>
            </select>
          </label>
          <label className="field">
            <span>Warmup</span>
            <input
              type="number"
              value={replayWarmup}
              onChange={(event) => setReplayWarmup(Number(event.target.value))}
            />
          </label>
        </div>
        <div className="di-controls">
          <label className="field">
            <span>From (ms)</span>
            <input type="number" value={replayFromMs} onChange={(event) => setReplayFromMs(event.target.value)} />
          </label>
          <label className="field">
            <span>To (ms)</span>
            <input type="number" value={replayToMs} onChange={(event) => setReplayToMs(event.target.value)} />
          </label>
          <div className="inline-form">
            <button className="btn btn-small" type="button" onClick={() => handleReplayQuickRange(24)}>
              Last 24h
            </button>
            <button className="btn btn-small" type="button" onClick={() => handleReplayQuickRange(24 * 7)}>
              Last 7d
            </button>
            <button className="btn btn-small" type="button" onClick={() => handleReplayQuickRange(24 * 30)}>
              Last 30d
            </button>
          </div>
          <button className="btn" type="button" onClick={handleReplayRun} disabled={replayLoading}>
            {replayLoading ? "Running..." : "Run Replay"}
          </button>
        </div>

        {replaySummary ? (
          <div className="di-grid">
            <div>
              <span>Total Steps</span>
              <strong>{replaySummary.total_steps}</strong>
            </div>
            <div>
              <span>Signals</span>
              <strong>{replaySummary.signals_total}</strong>
            </div>
            <div>
              <span>Break / Setup / Fakeout</span>
              <strong>
                {replaySummary.by_type?.break ?? 0} / {replaySummary.by_type?.setup ?? 0} / {replaySummary.by_type?.fakeout ?? 0}
              </strong>
            </div>
            <div>
              <span>Long / Short</span>
              <strong>
                {replaySummary.by_direction?.long ?? 0} / {replaySummary.by_direction?.short ?? 0}
              </strong>
            </div>
          </div>
        ) : null}

        {replayItems.length > 0 ? (
          <div className="replay-controls">
            <div className="inline-form">
              <input
                type="range"
                min={0}
                max={Math.max(replayItems.length - 1, 0)}
                value={replayIndex}
                onChange={(event) => setReplayIndex(Number(event.target.value))}
              />
              <span className="muted">
                {replayIndex + 1} / {replayItems.length}
              </span>
            </div>
            <div className="muted">
              Selected time: {replayItem ? formatTimestamp(replayItem.time) : "-"}
            </div>
          </div>
        ) : (
          <p className="muted">Run replay to load timeline.</p>
        )}

        {replayItem ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Type</th>
                  <th>Direction</th>
                  <th>Level</th>
                  <th>Entry</th>
                  <th>SL</th>
                </tr>
              </thead>
              <tbody>
                {replayItem.signals.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="muted">
                      No signals on this candle.
                    </td>
                  </tr>
                ) : (
                  replayItem.signals.map((signal, idx) => (
                    <tr
                      key={`replay-signal-${idx}`}
                      className="clickable"
                      onClick={() => handleReplaySignalClick(signal)}
                    >
                      <td>{signal.type}</td>
                      <td>{signal.direction}</td>
                      <td>{signal.level}</td>
                      <td>{signal.entry}</td>
                      <td>{signal.sl ?? "-"}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        ) : null}

        {replayTradeOutcomes.length > 0 ? (
          <div>
            <h3>Replay Trade Outcomes</h3>
            <div className="di-controls">
              <label className="field">
                <span>Side</span>
                <select value={replaySideFilter} onChange={(event) => setReplaySideFilter(event.target.value)}>
                  <option value="all">All</option>
                  <option value="long">Long</option>
                  <option value="short">Short</option>
                </select>
              </label>
              <label className="field">
                <span>Bias Alignment</span>
                <select
                  value={replayBiasAlignmentFilter}
                  onChange={(event) => setReplayBiasAlignmentFilter(event.target.value)}
                >
                  <option value="all">All</option>
                  <option value="aligned_3">3/3 aligned</option>
                  <option value="aligned_2">2/3 aligned</option>
                  <option value="aligned_0_1">0-1/3 aligned</option>
                </select>
              </label>
              <label className="field">
                <span>Outcome</span>
                <select value={replayOutcomeFilter} onChange={(event) => setReplayOutcomeFilter(event.target.value)}>
                  <option value="all">All</option>
                  <option value="win">Win</option>
                  <option value="loss">Loss</option>
                  <option value="open">Open</option>
                </select>
              </label>
              <label className="field">
                <span>Sort</span>
                <select value={replaySortBy} onChange={(event) => setReplaySortBy(event.target.value)}>
                  <option value="time_desc">Newest first</option>
                  <option value="time_asc">Oldest first</option>
                  <option value="max_rr_desc">Max RR (high to low)</option>
                  <option value="max_dd_desc">Max drawdown R (high to low)</option>
                  <option value="duration_rr2_asc">Time to RR2 (fast to slow)</option>
                  <option value="alignment_desc">Bias alignment (high to low)</option>
                  <option value="direction">Direction (long then short)</option>
                </select>
              </label>
            </div>

            <div className="di-grid">
              <div>
                <span>Trades (filtered / total)</span>
                <strong>
                  {replayTradeRows.length} / {replayTradeOutcomes.length}
                </strong>
              </div>
              <div>
                <span>Wins / Losses / Open</span>
                <strong>
                  {replayTradeStats.wins} / {replayTradeStats.losses} / {replayTradeStats.open}
                </strong>
              </div>
              <div>
                <span>Max Drawdown (R)</span>
                <strong>{formatNumber(replayTradeStats.max_drawdown_r)}</strong>
              </div>
              <div>
                <span>Long Win/Loss Ratio</span>
                <strong>{formatWinLossRatio(replayTradeStats.by_side.long)}</strong>
              </div>
              <div>
                <span>Short Win/Loss Ratio</span>
                <strong>{formatWinLossRatio(replayTradeStats.by_side.short)}</strong>
              </div>
              <div>
                <span>Average Win RR</span>
                <strong>{formatNumber(replayTradeStats.avg_win_rr)}</strong>
              </div>
              <div>
                <span>Max Losing Streak</span>
                <strong>{replayTradeStats.max_losing_streak}</strong>
              </div>
            </div>

            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Signal Time</th>
                    <th>Type</th>
                    <th>Direction</th>
                    <th>Entry</th>
                    <th>SL</th>
                    <th>Biases (W / D / H)</th>
                    <th>Alignment</th>
                    <th>Outcome</th>
                    <th>Max RR</th>
                    <th>Max DD (R)</th>
                    <th>Outcome Duration</th>
                    <th>To SL</th>
                    <th>To RR2</th>
                    <th>To RR5</th>
                    <th>To RR10</th>
                  </tr>
                </thead>
                <tbody>
                  {replayTradeRows.length === 0 ? (
                    <tr>
                      <td colSpan={15} className="muted">
                        No replay trades match filters.
                      </td>
                    </tr>
                  ) : (
                    replayTradeRows.map((trade) => (
                      <tr key={trade.id}>
                        <td>{formatTimestamp(trade.signal_time)}</td>
                        <td>{trade.type}</td>
                        <td>{trade.direction}</td>
                        <td>{formatNumber(trade.entry)}</td>
                        <td>{formatNumber(trade.sl)}</td>
                        <td>
                          {trade.weekly_bias} / {trade.daily_bias} / {trade.hwc_bias}
                        </td>
                        <td>{trade.bias_alignment_label}</td>
                        <td>{trade.outcome}</td>
                        <td>{formatNumber(trade.max_rr)}</td>
                        <td>{formatNumber(trade.max_drawdown_r)}</td>
                        <td>{formatDurationMs(trade.outcome_duration_ms)}</td>
                        <td>{formatDurationMs(trade.time_to_sl_ms)}</td>
                        <td>{formatDurationMs(trade.time_to_rr2_ms)}</td>
                        <td>{formatDurationMs(trade.time_to_rr5_ms)}</td>
                        <td>{formatDurationMs(trade.time_to_rr10_ms)}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        ) : null}

        {replayDetails ? (
          <div className="drawer">
            <div className="drawer-header">
              <strong>Replay Signal</strong>
              <button className="btn btn-small" type="button" onClick={() => setReplayDetails(null)}>
                Close
              </button>
            </div>
            <div className="drawer-meta">
              <span>{replayDetails.type}</span>
              <span>{replayDetails.direction}</span>
              <span>Level {replayDetails.level}</span>
              <span>{formatTimestamp(replayDetails.time)}</span>
            </div>
            <div className="drawer-meta">
              <span>Entry {replayDetails.entry}</span>
              <span>SL {replayDetails.sl}</span>
              <span>{replayDetails.sl_reason}</span>
            </div>
            {replayDetails.trigger_candle ? (
              <div className="drawer-meta">
                <span>
                  Candle O/H/L/C: {replayDetails.trigger_candle.open}/{replayDetails.trigger_candle.high}/
                  {replayDetails.trigger_candle.low}/{replayDetails.trigger_candle.close}
                </span>
              </div>
            ) : null}
            {replayDetails.level_event_indices ? (
              <div className="drawer-meta">
                <span>break {replayDetails.level_event_indices.break_index ?? "-"}</span>
                <span>retest {replayDetails.level_event_indices.retest_index ?? "-"}</span>
                <span>fakeout {replayDetails.level_event_indices.fakeout_index ?? "-"}</span>
                <span>setup {replayDetails.setup_index ?? "-"}</span>
              </div>
            ) : null}
            <div className="inline-form">
              <button className="btn btn-small" type="button" onClick={() => handleCopyText(JSON.stringify(replayDetails, null, 2))}>
                Copy JSON
              </button>
              <button className="btn btn-small" type="button" onClick={() => window.open(getBinanceLink(selectedSymbol), "_blank", "noopener")}>
                Open Binance
              </button>
            </div>
            <pre>{JSON.stringify(replayDetails.context ?? {}, null, 2)}</pre>
          </div>
        ) : null}
      </section>
      ) : null}

      {showDashboard ? (
      <section className="card">
        <h2>Alert Review</h2>
        <div className="tabs">
          <button
            className={`tab ${alertsTab === "history" ? "active" : ""}`}
            type="button"
            onClick={() => setAlertsTab("history")}
          >
            History
          </button>
          <button
            className={`tab ${alertsTab === "suppressed" ? "active" : ""}`}
            type="button"
            onClick={() => setAlertsTab("suppressed")}
          >
            Suppressed
          </button>
        </div>
        {alertsTab === "history" ? (
          <div>
            {alertsError ? <div className="error">{alertsError}</div> : null}
            <div className="di-controls">
              <label className="field">
                <span>Symbol</span>
                <select
                  value={alertsFilters.symbol}
                  onChange={(event) => handleAlertFilterChange("symbol", event.target.value)}
                >
                  <option value="">All</option>
                  {symbols.map((symbol) => (
                    <option key={`alert-${symbol}`} value={symbol}>
                      {symbol}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span>TF</span>
                <select value={alertsFilters.tf} onChange={(event) => handleAlertFilterChange("tf", event.target.value)}>
                  <option value="">All</option>
                  <option value="15m">15m</option>
                  <option value="1h">1h</option>
                  <option value="4h">4h</option>
                  <option value="1d">1d</option>
                  <option value="1w">1w</option>
                </select>
              </label>
              <label className="field">
                <span>Type</span>
                <select
                  value={alertsFilters.type}
                  onChange={(event) => handleAlertFilterChange("type", event.target.value)}
                >
                  <option value="">All</option>
                  <option value="break">break</option>
                  <option value="setup">setup</option>
                  <option value="fakeout">fakeout</option>
                </select>
              </label>
              <label className="field">
                <span>Direction</span>
                <select
                  value={alertsFilters.direction}
                  onChange={(event) => handleAlertFilterChange("direction", event.target.value)}
                >
                  <option value="">All</option>
                  <option value="long">long</option>
                  <option value="short">short</option>
                </select>
              </label>
              <label className="field">
                <span>Notified</span>
                <select
                  value={alertsFilters.notified}
                  onChange={(event) => handleAlertFilterChange("notified", event.target.value)}
                >
                  <option value="">All</option>
                  <option value="1">Notified</option>
                  <option value="0">Not notified</option>
                </select>
              </label>
            </div>
            <div className="inline-form">
              <button className="btn" type="button" onClick={() => handleQuickRange(1)}>
                Last 1h
              </button>
              <button className="btn" type="button" onClick={() => handleQuickRange(6)}>
                Last 6h
              </button>
              <button className="btn" type="button" onClick={() => handleQuickRange(24)}>
                Last 24h
              </button>
              <button className="btn" type="button" onClick={() => handleQuickRange(168)}>
                Last 7d
              </button>
              <button className="btn" type="button" onClick={handleClearRange}>
                Clear Range
              </button>
            </div>
            <div className="inline-form">
              <input
                type="text"
                value={alertsSearch}
                onChange={(event) => setAlertsSearch(event.target.value)}
                placeholder="Search symbol/type/level/error"
              />
              <label className="checkbox">
                <input
                  type="checkbox"
                  checked={alertsAutoRefresh}
                  onChange={(event) => setAlertsAutoRefresh(event.target.checked)}
                />
                Auto refresh
              </label>
              <button className="btn" type="button" onClick={handleExportCsv}>
                Export CSV
              </button>
            </div>
            <div className="pagination">
              <span>
                Showing {showingStart}-{showingEnd} of {totalAlerts}
              </span>
              <div className="pagination-actions">
                <button
                  className="btn btn-small"
                  type="button"
                  disabled={alertsOffset === 0}
                  onClick={() => setAlertsOffset((prev) => Math.max(0, prev - alertsLimit))}
                >
                  Prev
                </button>
                <button
                  className="btn btn-small"
                  type="button"
                  disabled={alertsOffset + alertsLimit >= totalAlerts}
                  onClick={() => setAlertsOffset((prev) => prev + alertsLimit)}
                >
                  Next
                </button>
              </div>
            </div>
            {filteredAlerts.length === 0 ? (
              <p className="muted">No alerts match the current filters.</p>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Time</th>
                      <th>Symbol / TF</th>
                      <th>Type / Dir</th>
                      <th>Level</th>
                      <th>Entry / SL</th>
                      <th>Score</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredAlerts.map((alert) => (
                      <tr
                        key={alert.id ?? `${alert.symbol}-${alert.time}`}
                        className="clickable"
                        onClick={() => handleAlertRowClick(alert.id)}
                      >
                        <td>{alert.created_at ? new Date(alert.created_at).toLocaleString() : "-"}</td>
                        <td>
                          {alert.symbol} / {alert.tf}
                        </td>
                        <td>
                          {alert.type} / {alert.direction}
                        </td>
                        <td>{alert.level ?? "-"}</td>
                        <td>
                          {alert.entry ?? "-"} / {alert.sl ?? "-"}
                        </td>
                        <td>
                          {alert.score ?? "-"}
                          {alert.vol_ok !== undefined ? (
                            <span className={`badge ${alert.vol_ok ? "ok" : "bad"}`}>VOL</span>
                          ) : null}
                          {alert.di_ok !== undefined ? (
                            <span className={`badge ${alert.di_ok ? "ok" : "bad"}`}>DI</span>
                          ) : null}
                        </td>
                        <td>{formatAlertStatus(alert)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {alertDetailsId ? (
              <div className="drawer">
                <div className="drawer-header">
                  <strong>Alert {alertDetailsId}</strong>
                  <button className="btn btn-small" type="button" onClick={handleCloseDetails}>
                    Close
                  </button>
                </div>
                {alertDetailsError ? <div className="error">{alertDetailsError}</div> : null}
                {alertDetails ? (
                  <div className="drawer-body">
                    <div className="drawer-meta">
                      <span>
                        {alertDetails.symbol} {alertDetails.tf} {alertDetails.type} {alertDetails.direction}
                      </span>
                      <span>Level: {alertDetails.level ?? "-"}</span>
                    </div>
                    <div className="drawer-meta">
                      <span>Entry: {alertDetails.entry ?? "-"}</span>
                      <span>SL: {alertDetails.sl ?? "-"}</span>
                    </div>
                    <div className="drawer-meta">
                      <span>Notify error: {alertDetails.notify_error ?? "-"}</span>
                    </div>
                    {alertDetails.payload?.candle ? (
                      <div className="drawer-meta">
                        <span>
                          Candle O/H/L/C/V: {alertDetails.payload.candle.open}/{alertDetails.payload.candle.high}/
                          {alertDetails.payload.candle.low}/{alertDetails.payload.candle.close}/
                          {alertDetails.payload.candle.volume}
                        </span>
                      </div>
                    ) : null}
                    {alertDetails.payload?.level_event ? (
                      <div className="drawer-meta">
                        <span>
                          Indices: break {alertDetails.payload.level_event.break_index ?? "-"}, retest{" "}
                          {alertDetails.payload.level_event.retest_index ?? "-"}, fakeout{" "}
                          {alertDetails.payload.level_event.fakeout_index ?? "-"}
                        </span>
                      </div>
                    ) : null}
                    <div className="inline-form">
                      <button
                        className="btn btn-small"
                        type="button"
                        onClick={() => handleCopyText(formatTelegramText(alertDetails))}
                      >
                        Copy Telegram Text
                      </button>
                      <button
                        className="btn btn-small"
                        type="button"
                        onClick={() => handleCopyText(JSON.stringify(alertDetails, null, 2))}
                      >
                        Copy JSON
                      </button>
                      <button
                        className="btn btn-small"
                        type="button"
                        onClick={() => window.open(getBinanceLink(alertDetails.symbol), "_blank", "noopener")}
                      >
                        Open Binance Chart
                      </button>
                    </div>
                    <pre>{JSON.stringify(alertDetails.payload ?? alertDetails, null, 2)}</pre>
                  </div>
                ) : (
                  <p className="muted">Loading alert details...</p>
                )}
              </div>
            ) : null}
          </div>
        ) : (
          <div>
            {suppressedError ? <div className="error">{suppressedError}</div> : null}
            <div className="inline-form">
              <label className="field">
                <span>Reason</span>
                <select value={suppressedReason} onChange={(event) => setSuppressedReason(event.target.value)}>
                  {suppressedReasons.map((reason) => (
                    <option key={reason} value={reason}>
                      {reason}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            {filteredSuppressed.length === 0 ? (
              <p className="muted">No suppressed items yet.</p>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Time</th>
                      <th>Symbol</th>
                      <th>TF</th>
                      <th>Type</th>
                      <th>Dir</th>
                      <th>Level</th>
                      <th>Score</th>
                      <th>Reason</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredSuppressed.map((item, idx) => (
                      <tr key={`${item.time}-${idx}`}>
                        <td>{formatTimestamp(item.time)}</td>
                        <td>{item.symbol}</td>
                        <td>{item.tf}</td>
                        <td>{item.type}</td>
                        <td>{item.direction}</td>
                        <td>{item.level ?? "-"}</td>
                        <td>{item.score ?? "-"}</td>
                        <td>
                          {item.reason}
                          {item.details && item.details.length > 0 ? ` (${item.details.join(", ")})` : ""}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </section>
      ) : null}

      {showOps ? (
      <section className="card">
        <h2>Operator</h2>
        {pollerError ? <div className="error">{pollerError}</div> : null}
        {pollerStatus ? (
          <div className="bias-grid">
            <div>
              <span>Status</span>
              <strong>
                {pollerStatus.is_running
                  ? pollerStatus.mode === "pause_all"
                    ? "Paused (All)"
                    : pollerStatus.mode === "pause_new"
                      ? "Paused (New Alerts)"
                      : "Running"
                  : "Stopped"}
              </strong>
            </div>
            <div>
              <span>Last Tick</span>
              <strong>{formatTimestamp(pollerStatus.last_tick_at)}</strong>
            </div>
            <div>
              <span>Last Scan</span>
              <strong>{formatTimestamp(pollerStatus.last_scan_at)}</strong>
            </div>
            <div>
              <span>Last Scan Count</span>
              <strong>{pollerStatus.last_scan_count ?? "-"}</strong>
            </div>
            <div>
              <span>Last New Alerts</span>
              <strong>{pollerStatus.last_new_alerts ?? "-"}</strong>
            </div>
            <div>
              <span>Suppressed New Alerts</span>
              <strong>
                {pollerStatus.mode === "pause_new" ? pollerStatus.last_suppressed_new_alerts ?? "-" : "-"}
              </strong>
            </div>
            <div>
              <span>Last Error</span>
              <strong className={pollerStatus.last_error ? "error-text" : ""}>
                {pollerStatus.last_error || "-"}
              </strong>
            </div>
          </div>
        ) : (
          <p className="muted">Loading poller status...</p>
        )}
        <div className="inline-form">
          <button
            className="btn"
            type="button"
            onClick={() => handleSetPollerMode("run")}
            disabled={!pollerStatus || pollerStatus.mode === "run"}
          >
            Run
          </button>
          <button
            className="btn"
            type="button"
            onClick={() => handleSetPollerMode("pause_new")}
            disabled={!pollerStatus || pollerStatus.mode === "pause_new"}
          >
            Pause New
          </button>
          <button
            className="btn"
            type="button"
            onClick={() => handleSetPollerMode("pause_all")}
            disabled={!pollerStatus || pollerStatus.mode === "pause_all"}
          >
            Pause All
          </button>
        </div>
        <div className="inline-form">
          <input
            type="text"
            value={telegramText}
            onChange={(event) => setTelegramText(event.target.value)}
            placeholder="Test message (optional)"
          />
          <button className="btn" type="button" onClick={handleSendTelegramTest}>
            Send Test Telegram
          </button>
        </div>
        {telegramFeedback ? (
          <p className={telegramFeedback.ok ? "muted" : "error-text"}>{telegramFeedback.message}</p>
        ) : null}
      </section>
      ) : null}

      {showOps ? (
      <section className="card">
        <h2>Quality</h2>
        {qualityError ? <div className="error">{qualityError}</div> : null}
        {qualitySettings ? (
          <div className="levels-grid">
            <div>
              <h3>Min Score</h3>
              <label className="field">
                <span>Break</span>
                <input
                  type="number"
                  value={qualitySettings.min_score_by_type?.break ?? ""}
                  onChange={(event) =>
                    setQualitySettings((prev) =>
                      updateQuality(prev, ["min_score_by_type", "break"], event.target.value)
                    )
                  }
                />
              </label>
              <label className="field">
                <span>Setup</span>
                <input
                  type="number"
                  value={qualitySettings.min_score_by_type?.setup ?? ""}
                  onChange={(event) =>
                    setQualitySettings((prev) =>
                      updateQuality(prev, ["min_score_by_type", "setup"], event.target.value)
                    )
                  }
                />
              </label>
              <label className="field">
                <span>Fakeout</span>
                <input
                  type="number"
                  value={qualitySettings.min_score_by_type?.fakeout ?? ""}
                  onChange={(event) =>
                    setQualitySettings((prev) =>
                      updateQuality(prev, ["min_score_by_type", "fakeout"], event.target.value)
                    )
                  }
                />
              </label>
            </div>
            <div>
              <h3>Cooldown (min)</h3>
              <label className="field">
                <span>Break</span>
                <input
                  type="number"
                  value={qualitySettings.cooldown_minutes_by_type?.break ?? ""}
                  onChange={(event) =>
                    setQualitySettings((prev) =>
                      updateQuality(prev, ["cooldown_minutes_by_type", "break"], event.target.value)
                    )
                  }
                />
              </label>
              <label className="field">
                <span>Setup</span>
                <input
                  type="number"
                  value={qualitySettings.cooldown_minutes_by_type?.setup ?? ""}
                  onChange={(event) =>
                    setQualitySettings((prev) =>
                      updateQuality(prev, ["cooldown_minutes_by_type", "setup"], event.target.value)
                    )
                  }
                />
              </label>
              <label className="field">
                <span>Fakeout</span>
                <input
                  type="number"
                  value={qualitySettings.cooldown_minutes_by_type?.fakeout ?? ""}
                  onChange={(event) =>
                    setQualitySettings((prev) =>
                      updateQuality(prev, ["cooldown_minutes_by_type", "fakeout"], event.target.value)
                    )
                  }
                />
              </label>
            </div>
            <div>
              <h3>Rate Limits</h3>
              <label className="field">
                <span>Per Symbol / Hour</span>
                <input
                  type="number"
                  value={qualitySettings.max_alerts_per_symbol_per_hour ?? ""}
                  onChange={(event) =>
                    setQualitySettings((prev) =>
                      updateQuality(prev, ["max_alerts_per_symbol_per_hour"], event.target.value)
                    )
                  }
                />
              </label>
              <label className="field">
                <span>Global / Hour</span>
                <input
                  type="number"
                  value={qualitySettings.max_alerts_global_per_hour ?? ""}
                  onChange={(event) =>
                    setQualitySettings((prev) =>
                      updateQuality(prev, ["max_alerts_global_per_hour"], event.target.value)
                    )
                  }
                />
              </label>
            </div>
            <div>
              <h3>Quiet Hours</h3>
              <label className="field">
                <span>Enabled</span>
                <select
                  value={qualitySettings.quiet_hours?.enabled ? "yes" : "no"}
                  onChange={(event) =>
                    setQualitySettings((prev) =>
                      updateQuality(prev, ["quiet_hours", "enabled"], event.target.value === "yes")
                    )
                  }
                >
                  <option value="no">No</option>
                  <option value="yes">Yes</option>
                </select>
              </label>
              <label className="field">
                <span>Start</span>
                <input
                  type="text"
                  value={qualitySettings.quiet_hours?.start ?? ""}
                  onChange={(event) =>
                    setQualitySettings((prev) =>
                      updateQuality(prev, ["quiet_hours", "start"], event.target.value)
                    )
                  }
                />
              </label>
              <label className="field">
                <span>End</span>
                <input
                  type="text"
                  value={qualitySettings.quiet_hours?.end ?? ""}
                  onChange={(event) =>
                    setQualitySettings((prev) =>
                      updateQuality(prev, ["quiet_hours", "end"], event.target.value)
                    )
                  }
                />
              </label>
              <label className="field">
                <span>TZ</span>
                <input
                  type="text"
                  value={qualitySettings.quiet_hours?.tz ?? ""}
                  onChange={(event) =>
                    setQualitySettings((prev) =>
                      updateQuality(prev, ["quiet_hours", "tz"], event.target.value)
                    )
                  }
                />
              </label>
            </div>
          </div>
        ) : (
          <p className="muted">Loading quality settings...</p>
        )}
        <button className="btn" type="button" onClick={handleSaveQuality}>
          Save Quality Settings
        </button>
        {qualitySaveStatus ? <p className="muted">{qualitySaveStatus}</p> : null}
      </section>
      ) : null}

      {showDashboard ? (
      <section className="card">
        <h2>Watchlist</h2>
        {watchlist ? (
          <pre>{JSON.stringify(watchlist, null, 2)}</pre>
        ) : (
          <p className="muted">Loading watchlist...</p>
        )}
      </section>
      ) : null}

      {showDashboard ? (
      <section className="card">
        <h2>Indicator Debug (BTCUSDT 1h)</h2>
        {indicatorError ? <div className="error">{indicatorError}</div> : null}
        {indicators ? (
          <div className="indicator-grid">
            <div>
              <span>RSI(14)</span>
              <strong>{latestValue(indicators.rsi14)}</strong>
            </div>
            <div>
              <span>ATR(5)</span>
              <strong>{latestValue(indicators.atr5)}</strong>
            </div>
            <div>
              <span>SMA(7)</span>
              <strong>{latestValue(indicators.sma7)}</strong>
            </div>
            <div>
              <span>DI+</span>
              <strong>{latestValue(indicators.di_plus)}</strong>
            </div>
            <div>
              <span>DI-</span>
              <strong>{latestValue(indicators.di_minus)}</strong>
            </div>
            <div>
              <span>ADX(14)</span>
              <strong>{latestValue(indicators.adx14)}</strong>
            </div>
          </div>
        ) : (
          <p className="muted">Loading indicators...</p>
        )}
      </section>
      ) : null}

      {showDashboard ? (
      <section className="card">
        <h2>Pivot Debug (BTCUSDT 1h)</h2>
        {pivotError ? <div className="error">{pivotError}</div> : null}
        <button className="btn" type="button" onClick={loadPivots}>
          Load Pivot Counts
        </button>
        {pivotStats ? (
          <div className="pivot-stats">
            <div>
              <span>Pivot Highs</span>
              <strong>{pivotStats.highs}</strong>
            </div>
            <div>
              <span>Pivot Lows</span>
              <strong>{pivotStats.lows}</strong>
            </div>
          </div>
        ) : (
          <p className="muted">Click to load pivot counts.</p>
        )}
      </section>
      ) : null}

      {showDashboard || showLevels ? (
      <section className="card">
        <h2>Levels</h2>
        {levelsError ? <div className="error">{levelsError}</div> : null}
        <label className="field">
          <span>Symbol</span>
          <select value={selectedSymbol} onChange={(event) => setSelectedSymbol(event.target.value)}>
            {symbols.map((symbol) => (
              <option key={symbol} value={symbol}>
                {symbol}
              </option>
            ))}
          </select>
        </label>
        {levels ? (
          <div className="levels-grid">
            <div>
              <h3>Auto Levels</h3>
              <p className="muted">
                Last close: {formatNumber(levels.last_close_used)} | below: {levels.below_count ?? "-"} | above:{" "}
                {levels.above_count ?? "-"} | tol: {formatNumber(levels.tol_pct_used)}
              </p>
              <LevelList items={levels.auto_levels} emptyLabel="No auto levels yet." />
              {Array.isArray(levels.clusters_debug) && levels.clusters_debug.length > 0 ? (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Center</th>
                        <th>Touches</th>
                        <th>Strength</th>
                        <th>Last Idx</th>
                      </tr>
                    </thead>
                    <tbody>
                      {levels.clusters_debug.slice(0, 6).map((cluster) => (
                        <tr key={`cluster-${cluster.center}`}>
                          <td>{formatNumber(cluster.center)}</td>
                          <td>{cluster.touches ?? "-"}</td>
                          <td>{formatNumber(cluster.strength)}</td>
                          <td>{cluster.last_touch_index ?? "-"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : null}
            </div>
            <div>
              <h3>Final Levels</h3>
              <LevelList items={levels.final_levels} emptyLabel="No final levels yet." />
            </div>
            <div>
              <h3>Pinned Levels</h3>
              <div className="inline-form">
                <input
                  type="number"
                  value={pinnedInput}
                  onChange={(event) => setPinnedInput(event.target.value)}
                  placeholder="Add pinned level"
                />
                <button className="btn" type="button" onClick={handleAddPinned}>
                  Add
                </button>
              </div>
              <EditableList items={getOverrides(watchlist, selectedSymbol, "add")} onRemove={handleRemovePinned} />
            </div>
            <div>
              <h3>Disabled Levels</h3>
              <div className="inline-form">
                <input
                  type="number"
                  value={disabledInput}
                  onChange={(event) => setDisabledInput(event.target.value)}
                  placeholder="Disable level"
                />
                <button className="btn" type="button" onClick={handleAddDisabled}>
                  Add
                </button>
              </div>
              <EditableList items={getOverrides(watchlist, selectedSymbol, "disable")} onRemove={handleRemoveDisabled} />
            </div>
          </div>
        ) : (
          <p className="muted">Loading levels...</p>
        )}
        <button className="btn" type="button" onClick={handleSaveLevels}>
          Save Overrides
        </button>
      </section>
      ) : null}

      {showDashboard ? (
      <section className="card">
        <h2>Bias</h2>
        {biasError ? <div className="error">{biasError}</div> : null}
        {bias ? (
          <div className="bias-grid">
            <div>
              <span>HWC Bias</span>
              <strong className={`bias-${bias.hwc_bias}`}>{bias.hwc_bias}</strong>
            </div>
            <div>
              <span>Weekly</span>
              <strong className={`bias-${bias.weekly.bias}`}>{bias.weekly.bias}</strong>
            </div>
            <div>
              <span>Daily</span>
              <strong className={`bias-${bias.daily.bias}`}>{bias.daily.bias}</strong>
            </div>
          </div>
        ) : (
          <p className="muted">Loading bias...</p>
        )}
      </section>
      ) : null}

      {showDashboard ? (
      <section className="card">
        <h2>DI Peak</h2>
        {diPeakError ? <div className="error">{diPeakError}</div> : null}
        <div className="di-controls">
          <label className="field">
            <span>Symbol</span>
            <select value={selectedSymbol} onChange={(event) => setSelectedSymbol(event.target.value)}>
              {symbols.map((symbol) => (
                <option key={symbol} value={symbol}>
                  {symbol}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Timeframe</span>
            <select value={diTf} onChange={(event) => setDiTf(event.target.value)}>
              <option value="15m">15m</option>
              <option value="1h">1h</option>
              <option value="4h">4h</option>
              <option value="1d">1d</option>
              <option value="1w">1w</option>
            </select>
          </label>
        </div>
        {diPeak ? (
          <div className="di-grid">
            <div>
              <span>DI+</span>
              <strong>{formatNumber(diPeak.di_plus?.last)}</strong>
              <small>Peak {formatNumber(diPeak.di_plus?.peak)} | Ratio {formatNumber(diPeak.di_plus?.ratio)}</small>
              <span className="badge">{diPeak.di_plus?.in_peak_zone ? "Zone" : "Out"}</span>
              <span className="badge">{diPeak.di_plus?.is_peak ? "Peak" : "No Peak"}</span>
            </div>
            <div>
              <span>DI-</span>
              <strong>{formatNumber(diPeak.di_minus?.last)}</strong>
              <small>Peak {formatNumber(diPeak.di_minus?.peak)} | Ratio {formatNumber(diPeak.di_minus?.ratio)}</small>
              <span className="badge">{diPeak.di_minus?.in_peak_zone ? "Zone" : "Out"}</span>
              <span className="badge">{diPeak.di_minus?.is_peak ? "Peak" : "No Peak"}</span>
            </div>
            <div>
              <span>Not At Peak (Long)</span>
              <strong>{String(diPeak.not_at_peak_long)}</strong>
            </div>
            <div>
              <span>Not At Peak (Short)</span>
              <strong>{String(diPeak.not_at_peak_short)}</strong>
            </div>
            <div>
              <span>ADX(14)</span>
              <strong>{formatNumber(diPeak.adx14_last)}</strong>
            </div>
          </div>
        ) : (
          <p className="muted">Loading DI peak...</p>
        )}
      </section>
      ) : null}

      {showDashboard ? (
      <section className="card">
        <h2>Volume</h2>
        {volError ? <div className="error">{volError}</div> : null}
        <div className="di-controls">
          <label className="field">
            <span>Symbol</span>
            <select value={selectedSymbol} onChange={(event) => setSelectedSymbol(event.target.value)}>
              {symbols.map((symbol) => (
                <option key={symbol} value={symbol}>
                  {symbol}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Timeframe</span>
            <select value={volTf} onChange={(event) => setVolTf(event.target.value)}>
              <option value="15m">15m</option>
              <option value="1h">1h</option>
              <option value="4h">4h</option>
              <option value="1d">1d</option>
              <option value="1w">1w</option>
            </select>
          </label>
        </div>
        {volData ? (
          <div className="di-grid">
            <div>
              <span>Vol Ratio</span>
              <strong>{formatNumber(volData.vol_ratio)}</strong>
            </div>
            <div>
              <span>MA5 Slope (%)</span>
              <strong>{formatNumber(volData.vol_ma5_slope_pct)}</strong>
              <span className="badge">{volData.vol_ma5_slope_ok ? "Slope OK" : "Slope Low"}</span>
            </div>
            <div>
              <span>Pullback Decline</span>
              <strong>{String(volData.pullback_vol_decline)}</strong>
            </div>
          </div>
        ) : (
          <p className="muted">Loading volume...</p>
        )}
      </section>
      ) : null}

      {showDashboard ? (
      <section className="card">
        <h2>RSI / ATR</h2>
        {rsiError ? <div className="error">{rsiError}</div> : null}
        <div className="di-controls">
          <label className="field">
            <span>Symbol</span>
            <select value={selectedSymbol} onChange={(event) => setSelectedSymbol(event.target.value)}>
              {symbols.map((symbol) => (
                <option key={symbol} value={symbol}>
                  {symbol}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Timeframe</span>
            <select value={rsiTf} onChange={(event) => setRsiTf(event.target.value)}>
              <option value="15m">15m</option>
              <option value="1h">1h</option>
              <option value="4h">4h</option>
              <option value="1d">1d</option>
              <option value="1w">1w</option>
            </select>
          </label>
        </div>
        {rsiData ? (
          <div className="di-grid">
            <div>
              <span>RSI(14)</span>
              <strong>{formatNumber(rsiData.rsi14_last)}</strong>
            </div>
            <div>
              <span>RSI Distance</span>
              <strong>{formatNumber(rsiData.rsi_distance)}</strong>
            </div>
            <div>
              <span>ATR(5)</span>
              <strong>{formatNumber(rsiData.atr5_last)}</strong>
            </div>
            <div>
              <span>ATR Mult</span>
              <strong>{formatNumber(rsiData.atr_mult)}</strong>
            </div>
            <div>
              <span>ATR Stop Dist</span>
              <strong>{formatNumber(rsiData.atr_stop_distance)}</strong>
            </div>
          </div>
        ) : (
          <p className="muted">Loading RSI/ATR...</p>
        )}
      </section>
      ) : null}

      {showDashboard ? (
      <section className="card">
        <h2>Level Events</h2>
        {levelEventsError ? <div className="error">{levelEventsError}</div> : null}
        <div className="di-controls">
          <label className="field">
            <span>Symbol</span>
            <select value={selectedSymbol} onChange={(event) => setSelectedSymbol(event.target.value)}>
              {symbols.map((symbol) => (
                <option key={symbol} value={symbol}>
                  {symbol}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Timeframe</span>
            <select value={levelEventsTf} onChange={(event) => setLevelEventsTf(event.target.value)}>
              <option value="15m">15m</option>
              <option value="1h">1h</option>
              <option value="4h">4h</option>
              <option value="1d">1d</option>
              <option value="1w">1w</option>
            </select>
          </label>
        </div>
        {levelEvents ? (
          levelEvents.events.length === 0 ? (
            <p className="muted">No level events yet.</p>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Level</th>
                    <th>Direction</th>
                    <th>Last Break</th>
                    <th>Retest</th>
                    <th>Fakeout</th>
                  </tr>
                </thead>
                <tbody>
                  {levelEvents.events.map((event) => (
                    <tr key={`${event.level}-${event.last_break?.index ?? "none"}`}>
                      <td>{event.level}</td>
                      <td>{event.direction ?? "-"}</td>
                      <td>{event.last_break ? new Date(event.last_break.time).toLocaleString() : "-"}</td>
                      <td>{String(event.retest_touched)}</td>
                      <td>{event.last_fakeout ? new Date(event.last_fakeout.time).toLocaleString() : "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        ) : (
          <p className="muted">Loading level events...</p>
        )}
      </section>
      ) : null}

      {showDashboard ? (
      <section className="card">
        <h2>Setup Candles</h2>
        {setupError ? <div className="error">{setupError}</div> : null}
        <div className="di-controls">
          <label className="field">
            <span>Symbol</span>
            <select value={selectedSymbol} onChange={(event) => setSelectedSymbol(event.target.value)}>
              {symbols.map((symbol) => (
                <option key={symbol} value={symbol}>
                  {symbol}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Timeframe</span>
            <select value={setupTf} onChange={(event) => setSetupTf(event.target.value)}>
              <option value="15m">15m</option>
              <option value="1h">1h</option>
              <option value="4h">4h</option>
              <option value="1d">1d</option>
              <option value="1w">1w</option>
            </select>
          </label>
        </div>
        {setupCandles ? (
          setupCandles.items.length === 0 ? (
            <p className="muted">No setup candles yet.</p>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Level</th>
                    <th>Direction</th>
                    <th>Time</th>
                    <th>Entry</th>
                    <th>SL</th>
                    <th>Risk</th>
                  </tr>
                </thead>
                <tbody>
                  {setupCandles.items.map((item) => (
                    <tr key={`${item.level}-${item.setup_index}-${item.direction}`}>
                      <td>{item.level}</td>
                      <td>{item.direction}</td>
                      <td>{new Date(item.time).toLocaleString()}</td>
                      <td>{item.entry}</td>
                      <td>{item.sl}</td>
                      <td>{formatNumber(Math.abs(item.entry - item.sl))}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        ) : (
          <p className="muted">Loading setup candles...</p>
        )}
      </section>
      ) : null}

      {showDashboard ? (
      <section className="card">
        <h2>Openings</h2>
        {openingsError ? <div className="error">{openingsError}</div> : null}
        <div className="di-controls">
          <label className="field">
            <span>Symbol</span>
            <select value={selectedSymbol} onChange={(event) => setSelectedSymbol(event.target.value)}>
              {symbols.map((symbol) => (
                <option key={symbol} value={symbol}>
                  {symbol}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Timeframe</span>
            <select value={openingsTf} onChange={(event) => setOpeningsTf(event.target.value)}>
              <option value="15m">15m</option>
              <option value="1h">1h</option>
              <option value="4h">4h</option>
              <option value="1d">1d</option>
              <option value="1w">1w</option>
            </select>
          </label>
        </div>
        {openings ? (
          <div>
            <div className="bias-grid">
              <div>
                <span>HWC Bias</span>
                <strong className={`bias-${openings.hwc_bias}`}>{openings.hwc_bias}</strong>
              </div>
              <div>
                <span>Last Candle</span>
                <strong>{openings.last_candle_time ? new Date(openings.last_candle_time).toLocaleString() : "-"}</strong>
              </div>
            </div>
            {openings.signals.length === 0 ? (
              <p className="muted">No openings on last candle.</p>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Type</th>
                      <th>Direction</th>
                      <th>Level</th>
                      <th>Entry</th>
                      <th>SL</th>
                      <th>Reason</th>
                    </tr>
                  </thead>
                  <tbody>
                  {openings.signals.map((signal, idx) => (
                      <tr key={`${signal.type}-${signal.level}-${idx}`}>
                        <td>{signal.type}</td>
                        <td>
                          {signal.direction}
                          <span className={`badge ${signal.context?.vol_ma5_slope_ok ? "ok" : "bad"}`}>
                            VOL
                          </span>
                          <span
                            className={`badge ${
                              signal.direction === "long"
                                ? signal.context?.not_at_peak_long
                                  ? "ok"
                                  : "bad"
                                : signal.context?.not_at_peak_short
                                  ? "ok"
                                  : "bad"
                            }`}
                          >
                            DI
                          </span>
                        </td>
                        <td>{signal.level}</td>
                        <td>{signal.entry}</td>
                        <td>{signal.sl ?? "-"}</td>
                        <td>{signal.sl_reason}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {openings.signals.length > 0 ? (
              <div className="openings-details">
                {openings.signals.map((signal, idx) => (
                  <div key={`detail-${signal.type}-${idx}`} className="openings-detail">
                    <span>
                      {signal.type} @ {signal.level}: candle O/H/L/C/V{" "}
                      {signal.candle
                        ? `${signal.candle.open}/${signal.candle.high}/${signal.candle.low}/${signal.candle.close}/${signal.candle.volume}`
                        : "-"}
                    </span>
                    <span>
                      indices: break {signal.level_event?.break_index ?? "-"}, retest{" "}
                      {signal.level_event?.retest_index ?? "-"}, fakeout {signal.level_event?.fakeout_index ?? "-"}
                    </span>
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        ) : (
          <p className="muted">Loading openings...</p>
        )}
      </section>
      ) : null}
    </div>
  );
}

function latestValue(series) {
  if (!Array.isArray(series) || series.length === 0) {
    return "-";
  }
  const value = series[series.length - 1];
  if (value === null || Number.isNaN(value)) {
    return "-";
  }
  return Number(value).toFixed(2);
}

function formatNumber(value) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }
  return Number(value).toFixed(2);
}

function formatTimestamp(value) {
  if (!value) {
    return "-";
  }
  return new Date(value).toLocaleString();
}

function formatDurationMs(value) {
  const ms = Number(value);
  if (!Number.isFinite(ms) || ms < 0) {
    return "-";
  }
  const totalMinutes = Math.floor(ms / 60000);
  const days = Math.floor(totalMinutes / (24 * 60));
  const hours = Math.floor((totalMinutes % (24 * 60)) / 60);
  const minutes = totalMinutes % 60;
  if (days > 0) {
    return `${days}d ${hours}h ${minutes}m`;
  }
  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  }
  return `${minutes}m`;
}

function formatWinLossRatio(sideStats) {
  if (!sideStats) {
    return "-";
  }
  const wins = Number(sideStats.wins ?? 0);
  const losses = Number(sideStats.losses ?? 0);
  if (losses <= 0) {
    return wins > 0 ? "inf" : "-";
  }
  return formatNumber(wins / losses);
}

function compareNullableNumber(a, b) {
  const aNum = Number(a);
  const bNum = Number(b);
  const aValid = Number.isFinite(aNum);
  const bValid = Number.isFinite(bNum);
  if (!aValid && !bValid) {
    return 0;
  }
  if (!aValid) {
    return 1;
  }
  if (!bValid) {
    return -1;
  }
  return aNum - bNum;
}

function toFiniteNumber(value) {
  const num = Number(value);
  return Number.isFinite(num) ? num : null;
}

function expectedBiasForDirection(direction) {
  if (direction === "long") {
    return "bullish";
  }
  if (direction === "short") {
    return "bearish";
  }
  return null;
}

function getBiasAlignment(direction, context) {
  const expected = expectedBiasForDirection(direction);
  const weekly = String(context?.weekly_bias || "neutral").toLowerCase();
  const daily = String(context?.daily_bias || "neutral").toLowerCase();
  const hwc = String(context?.hwc_bias || "neutral").toLowerCase();
  const values = [weekly, daily, hwc];
  let aligned = 0;
  if (expected) {
    values.forEach((value) => {
      if (value === expected) {
        aligned += 1;
      }
    });
  }
  return {
    aligned_count: aligned,
    label: `${aligned}/3 aligned`,
    weekly_bias: weekly,
    daily_bias: daily,
    hwc_bias: hwc,
  };
}

function evaluateReplaySignalOutcome(signal, candles) {
  const entry = signal.entry;
  const sl = signal.sl;
  const direction = signal.direction;
  const signalTime = signal.signal_time;
  const risk = Math.abs(entry - sl);
  if (!Number.isFinite(entry) || !Number.isFinite(sl) || !Number.isFinite(signalTime) || risk <= 0) {
    return null;
  }

  const rr2Target = direction === "long" ? entry + risk * 2 : entry - risk * 2;
  const rr5Target = direction === "long" ? entry + risk * 5 : entry - risk * 5;
  const rr10Target = direction === "long" ? entry + risk * 10 : entry - risk * 10;

  let maxRr = 0;
  let maxDrawdownR = 0;
  let outcome = "open";
  let outcomeTime = null;
  let outcomeCandleIndex = -1;
  let rr5Time = null;
  let rr10Time = null;

  for (let idx = 0; idx < candles.length; idx += 1) {
    const candle = candles[idx];
    if (!candle || candle.time <= signalTime) {
      continue;
    }
    const high = toFiniteNumber(candle.high);
    const low = toFiniteNumber(candle.low);
    if (high === null || low === null) {
      continue;
    }

    if (direction === "long") {
      const favorableR = Math.max(0, (high - entry) / risk);
      const adverseR = Math.max(0, (entry - low) / risk);
      const slHit = low <= sl;
      const rr2Hit = high >= rr2Target;
      if (slHit && rr2Hit) {
        outcome = "loss";
        outcomeTime = candle.time;
        outcomeCandleIndex = idx;
        maxDrawdownR = Math.max(maxDrawdownR, 1);
        break;
      }
      if (slHit) {
        outcome = "loss";
        outcomeTime = candle.time;
        outcomeCandleIndex = idx;
        maxDrawdownR = Math.max(maxDrawdownR, 1);
        break;
      }
      if (rr2Hit) {
        outcome = "win";
        outcomeTime = candle.time;
        outcomeCandleIndex = idx;
        maxRr = Math.max(maxRr, 2);
        maxDrawdownR = Math.max(maxDrawdownR, Math.min(1, adverseR));
        rr5Time = candle.time;
        rr10Time = candle.time;
        if (high < rr5Target) {
          rr5Time = null;
        }
        if (high < rr10Target) {
          rr10Time = null;
        }
        break;
      }
      maxRr = Math.max(maxRr, favorableR);
      maxDrawdownR = Math.max(maxDrawdownR, adverseR);
    } else if (direction === "short") {
      const favorableR = Math.max(0, (entry - low) / risk);
      const adverseR = Math.max(0, (high - entry) / risk);
      const slHit = high >= sl;
      const rr2Hit = low <= rr2Target;
      if (slHit && rr2Hit) {
        outcome = "loss";
        outcomeTime = candle.time;
        outcomeCandleIndex = idx;
        maxDrawdownR = Math.max(maxDrawdownR, 1);
        break;
      }
      if (slHit) {
        outcome = "loss";
        outcomeTime = candle.time;
        outcomeCandleIndex = idx;
        maxDrawdownR = Math.max(maxDrawdownR, 1);
        break;
      }
      if (rr2Hit) {
        outcome = "win";
        outcomeTime = candle.time;
        outcomeCandleIndex = idx;
        maxRr = Math.max(maxRr, 2);
        maxDrawdownR = Math.max(maxDrawdownR, Math.min(1, adverseR));
        rr5Time = candle.time;
        rr10Time = candle.time;
        if (low > rr5Target) {
          rr5Time = null;
        }
        if (low > rr10Target) {
          rr10Time = null;
        }
        break;
      }
      maxRr = Math.max(maxRr, favorableR);
      maxDrawdownR = Math.max(maxDrawdownR, adverseR);
    } else {
      return null;
    }
  }

  if (outcome === "win" && outcomeCandleIndex >= 0) {
    for (let idx = outcomeCandleIndex; idx < candles.length; idx += 1) {
      const candle = candles[idx];
      if (!candle || candle.time < outcomeTime) {
        continue;
      }
      const high = toFiniteNumber(candle.high);
      const low = toFiniteNumber(candle.low);
      if (high === null || low === null) {
        continue;
      }
      if (direction === "long") {
        maxRr = Math.max(maxRr, Math.max(0, (high - entry) / risk));
        if (rr5Time === null && high >= rr5Target) {
          rr5Time = candle.time;
        }
        if (rr10Time === null && high >= rr10Target) {
          rr10Time = candle.time;
        }
      } else {
        maxRr = Math.max(maxRr, Math.max(0, (entry - low) / risk));
        if (rr5Time === null && low <= rr5Target) {
          rr5Time = candle.time;
        }
        if (rr10Time === null && low <= rr10Target) {
          rr10Time = candle.time;
        }
      }
    }
  } else {
    rr5Time = null;
    rr10Time = null;
  }

  maxRr = Math.max(0, maxRr);
  maxDrawdownR = Math.max(0, maxDrawdownR);

  const slTime = outcome === "loss" ? outcomeTime : null;
  const rr2Time = outcome === "win" ? outcomeTime : null;

  const toDuration = (hitTime) => (hitTime === null ? null : Math.max(0, hitTime - signalTime));
  const outcomeDuration = outcomeTime === null ? null : toDuration(outcomeTime);

  return {
    outcome,
    outcome_time: outcomeTime,
    outcome_duration_ms: outcomeDuration,
    time_to_sl_ms: toDuration(slTime),
    time_to_rr2_ms: toDuration(rr2Time),
    time_to_rr5_ms: toDuration(rr5Time),
    time_to_rr10_ms: toDuration(rr10Time),
    max_rr: maxRr,
    max_drawdown_r: maxDrawdownR,
    realized_r: outcome === "win" ? 2 : outcome === "loss" ? -1 : 0,
  };
}

function buildReplayTradeOutcomes(items, symbol, tf) {
  if (!Array.isArray(items) || items.length === 0) {
    return [];
  }

  const candles = items
    .map((item) => ({
      time: Number(item?.time ?? 0),
      high: toFiniteNumber(item?.candle?.high),
      low: toFiniteNumber(item?.candle?.low),
    }))
    .filter((item) => Number.isFinite(item.time) && item.time > 0 && item.high !== null && item.low !== null)
    .sort((a, b) => a.time - b.time);

  const rows = [];
  items.forEach((item, itemIndex) => {
    const signals = Array.isArray(item?.signals) ? item.signals : [];
    signals.forEach((signal, signalIndex) => {
      const direction = String(signal?.direction || "").toLowerCase();
      if (direction !== "long" && direction !== "short") {
        return;
      }
      const entry = toFiniteNumber(signal?.entry);
      const sl = toFiniteNumber(signal?.sl);
      const signalTime = toFiniteNumber(signal?.time ?? item?.time);
      if (entry === null || sl === null || signalTime === null || signalTime <= 0) {
        return;
      }
      const risk = Math.abs(entry - sl);
      if (!(risk > 0)) {
        return;
      }

      const alignment = getBiasAlignment(direction, signal?.context || {});
      const outcome = evaluateReplaySignalOutcome(
        {
          direction,
          entry,
          sl,
          signal_time: signalTime,
        },
        candles
      );
      if (!outcome) {
        return;
      }

      rows.push({
        id: `${symbol || "SYM"}-${tf || "TF"}-${itemIndex}-${signalIndex}-${signalTime}`,
        symbol: symbol || "-",
        tf: tf || "-",
        type: signal?.type || "-",
        direction,
        signal_time: signalTime,
        entry,
        sl,
        risk,
        weekly_bias: alignment.weekly_bias,
        daily_bias: alignment.daily_bias,
        hwc_bias: alignment.hwc_bias,
        bias_alignment_count: alignment.aligned_count,
        bias_alignment_label: alignment.label,
        ...outcome,
      });
    });
  });

  return rows.sort((a, b) => b.signal_time - a.signal_time);
}

function summarizeReplayOutcomes(trades) {
  const rows = Array.isArray(trades) ? trades : [];
  const bySide = {
    long: { trades: 0, wins: 0, losses: 0, open: 0 },
    short: { trades: 0, wins: 0, losses: 0, open: 0 },
  };
  let wins = 0;
  let losses = 0;
  let open = 0;
  let winsRrSum = 0;

  rows.forEach((trade) => {
    const side = trade.direction === "short" ? "short" : "long";
    bySide[side].trades += 1;
    if (trade.outcome === "win") {
      wins += 1;
      bySide[side].wins += 1;
      winsRrSum += Number(trade.max_rr ?? 0);
    } else if (trade.outcome === "loss") {
      losses += 1;
      bySide[side].losses += 1;
    } else {
      open += 1;
      bySide[side].open += 1;
    }
  });

  const resolved = rows
    .filter((trade) => trade.outcome === "win" || trade.outcome === "loss")
    .sort((a, b) => (a.outcome_time ?? a.signal_time) - (b.outcome_time ?? b.signal_time));
  let cumulativeR = 0;
  let peakR = 0;
  let maxDrawdownR = 0;
  let losingStreak = 0;
  let maxLosingStreak = 0;
  resolved.forEach((trade) => {
    cumulativeR += Number(trade.realized_r ?? 0);
    peakR = Math.max(peakR, cumulativeR);
    maxDrawdownR = Math.max(maxDrawdownR, peakR - cumulativeR);
    if (trade.outcome === "loss") {
      losingStreak += 1;
      maxLosingStreak = Math.max(maxLosingStreak, losingStreak);
    } else if (trade.outcome === "win") {
      losingStreak = 0;
    }
  });

  return {
    total: rows.length,
    wins,
    losses,
    open,
    avg_win_rr: wins > 0 ? winsRrSum / wins : 0,
    max_losing_streak: maxLosingStreak,
    max_drawdown_r: maxDrawdownR,
    by_side: bySide,
  };
}

function formatAlertStatus(alert) {
  if (alert.notified) {
    return "Notified ✅";
  }
  if (alert.notify_error) {
    if (String(alert.notify_error).includes("quiet_hours")) {
      return "Silent (quiet hours)";
    }
    return `Error: ${alert.notify_error}`;
  }
  return "Pending";
}

function formatTelegramText(alert) {
  if (!alert) {
    return "";
  }
  const payload = alert.payload || {};
  const context = payload.context || alert.context || {};
  const type = String(alert.type || payload.type || "-").toUpperCase();
  const symbol = String(alert.symbol || payload.symbol || "-");
  const tf = String(alert.tf || payload.tf || "-");
  const direction = String(alert.direction || payload.direction || "-").toLowerCase();
  const directionTag = direction === "long" || direction === "short" ? direction.toUpperCase() : "-";
  const level = alert.level ?? payload.level;
  const entry = toFiniteNumber(alert.entry ?? payload.entry);
  const sl = toFiniteNumber(alert.sl ?? payload.sl);
  const slReason = String(alert.sl_reason ?? payload.sl_reason ?? "-");
  const time = alert.time ?? payload.time;
  const weeklyBias = String(context.weekly_bias ?? alert.weekly_bias ?? payload.weekly_bias ?? "-");
  const dailyBias = String(context.daily_bias ?? alert.daily_bias ?? payload.daily_bias ?? "-");
  const hwcBias = String(context.hwc_bias ?? alert.hwc_bias ?? payload.hwc_bias ?? "-");

  const volOk = context.vol_ma5_slope_ok;
  const pullbackVol = context.pullback_vol_decline;
  const diOk =
    direction === "long" ? context.not_at_peak_long : direction === "short" ? context.not_at_peak_short : null;
  const rsiDistance = toFiniteNumber(context.rsi_distance);
  const atrStopDistance = toFiniteNumber(context.atr_stop_distance);

  const risk = entry !== null && sl !== null ? Math.abs(entry - sl) : null;
  const riskPct = risk !== null && entry !== null && entry !== 0 ? risk / Math.abs(entry) : null;
  let rr2 = null;
  if (entry !== null && risk !== null) {
    if (direction === "long") {
      rr2 = entry + risk * 2;
    } else if (direction === "short") {
      rr2 = entry - risk * 2;
    }
  }

  const parts = [];
  parts.push(`${type} ${directionTag} | ${symbol} ${tf}`);
  parts.push(`Time: ${formatTelegramTime(time)}`);
  if (level !== undefined && level !== null) {
    parts.push(`Level: ${formatNumber(level)}`);
  }
  parts.push(`Entry: ${formatNumber(entry)} | SL: ${formatNumber(sl)} | SL reason: ${slReason}`);
  if (risk !== null) {
    parts.push(`Risk (1R): ${formatNumber(risk)} (${formatPercentFraction(riskPct)}) | TP@2R: ${formatNumber(rr2)}`);
  } else {
    parts.push("Risk (1R): - | TP@2R: -");
  }
  parts.push(`Bias: W ${weeklyBias} | D ${dailyBias} | HWC ${hwcBias}`);
  parts.push(
    `Checks: VOL_OK=${formatTelegramBool(volOk)} | DI_OK=${formatTelegramBool(diOk)} | PULLBACK_VOL=${formatTelegramBool(pullbackVol)}`
  );
  const indicators = [];
  if (rsiDistance !== null) {
    indicators.push(`RSI distance: ${formatNumber(rsiDistance)}`);
  }
  if (atrStopDistance !== null) {
    indicators.push(`ATR stop distance: ${formatNumber(atrStopDistance)}`);
  }
  if (indicators.length > 0) {
    parts.push(`Indicators: ${indicators.join(" | ")}`);
  }
  return parts.join("\n");
}

function formatTelegramBool(value) {
  if (value === true) {
    return "yes";
  }
  if (value === false) {
    return "no";
  }
  return "-";
}

function formatPercentFraction(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) {
    return "-";
  }
  return `${(num * 100).toFixed(2)}%`;
}

function formatTelegramTime(value) {
  const ms = Number(value);
  if (!Number.isFinite(ms)) {
    return "-";
  }
  const iso = new Date(ms).toISOString().replace("T", " ").replace(".000Z", " UTC");
  return `${iso} (${Math.trunc(ms)})`;
}

function getBinanceLink(symbol) {
  if (!symbol) {
    return "https://www.binance.com/en/futures";
  }
  return `https://www.binance.com/en/futures/${symbol}`;
}

function getTradingViewLink(symbol) {
  if (!symbol) {
    return "https://www.tradingview.com/chart/";
  }
  return `https://www.tradingview.com/chart/?symbol=BINANCE:${symbol}`;
}

function tfToSeconds(tf) {
  switch (tf) {
    case "15m":
      return 15 * 60;
    case "1h":
      return 60 * 60;
    case "4h":
      return 4 * 60 * 60;
    case "1d":
      return 24 * 60 * 60;
    case "1w":
      return 7 * 24 * 60 * 60;
    default:
      return 0;
  }
}

function findMarkerDetails(timeSec, map, tf) {
  if (!map || map.size === 0) {
    return null;
  }
  if (map.has(timeSec)) {
    return map.get(timeSec);
  }
  const maxGap = tfToSeconds(tf);
  if (!maxGap) {
    return null;
  }
  let best = null;
  let bestDiff = Number.POSITIVE_INFINITY;
  for (const [key, details] of map.entries()) {
    const diff = Math.abs(key - timeSec);
    if (diff < bestDiff && diff <= maxGap) {
      best = details;
      bestDiff = diff;
    }
  }
  return best;
}

function buildWorkspaceMarkers(levelEvents, setupItems, openings) {
  const markers = [];
  if (Array.isArray(levelEvents)) {
    levelEvents.forEach((event) => {
      const direction = event.direction;
      if (event.last_break?.time) {
        markers.push({ type: "break", direction, time: Math.floor(event.last_break.time / 1000) });
      }
      if (event.retest_time) {
        markers.push({ type: "retest", direction, time: Math.floor(event.retest_time / 1000) });
      }
      if (event.last_fakeout?.time) {
        markers.push({ type: "fakeout", direction, time: Math.floor(event.last_fakeout.time / 1000) });
      }
    });
  }
  if (Array.isArray(setupItems)) {
    setupItems.forEach((item) => {
      if (item.time) {
        markers.push({ type: "setup", direction: item.direction, time: Math.floor(item.time / 1000) });
      }
    });
  }
  if (Array.isArray(openings)) {
    openings.forEach((signal) => {
      if (signal?.time) {
        markers.push({ type: signal.type || "opening", direction: signal.direction, time: Math.floor(signal.time / 1000) });
      }
    });
  }

  const mapped = markers.map((marker) => {
    const isBull = marker.direction === "up" || marker.direction === "long";
    let color = "#7a6a45";
    let shape = "circle";
    let position = isBull ? "belowBar" : "aboveBar";
    let text = marker.type?.toUpperCase?.() ?? "M";
    switch (marker.type) {
      case "break":
        color = isBull ? "#0f6b5c" : "#7a2f2f";
        shape = isBull ? "arrowUp" : "arrowDown";
        position = isBull ? "aboveBar" : "belowBar";
        text = "B";
        break;
      case "retest":
        color = "#7a6a45";
        shape = "circle";
        text = "R";
        break;
      case "fakeout":
        color = "#c07a2f";
        shape = "circle";
        text = "F";
        break;
      case "setup":
        color = isBull ? "#2d8f6f" : "#7a2f2f";
        shape = isBull ? "arrowUp" : "arrowDown";
        text = "S";
        break;
      default:
        break;
    }
    return {
      time: marker.time,
      position,
      color,
      shape,
      text
    };
  });
  return mapped.sort((a, b) => a.time - b.time);
}

function buildWorkspaceSignalRows(levelEvents, setupItems, openings, symbol, tf) {
  const rows = [];
  if (Array.isArray(levelEvents)) {
    levelEvents.forEach((event, idx) => {
      const direction = event.direction;
      const levelEvent = {
        break_index: event.last_break?.index ?? null,
        retest_index: event.retest_index ?? null,
        fakeout_index: event.last_fakeout?.index ?? null
      };
      if (event.last_break?.time) {
        rows.push({
          id: `break-${event.level}-${event.last_break.time}-${idx}`,
          type: "break",
          direction,
          level: event.level,
          time: event.last_break.time,
          source: "level_event",
          details: {
            symbol,
            tf,
            type: "break",
            direction,
            level: event.level,
            time: event.last_break.time,
            entry: event.last_break.close,
            sl: null,
            sl_reason: null,
            level_event: levelEvent,
            context: {}
          }
        });
      }
      if (event.retest_time) {
        rows.push({
          id: `retest-${event.level}-${event.retest_time}-${idx}`,
          type: "retest",
          direction,
          level: event.level,
          time: event.retest_time,
          source: "level_event",
          details: {
            symbol,
            tf,
            type: "retest",
            direction,
            level: event.level,
            time: event.retest_time,
            entry: null,
            sl: null,
            sl_reason: null,
            level_event: levelEvent,
            context: {}
          }
        });
      }
      if (event.last_fakeout?.time) {
        rows.push({
          id: `fakeout-${event.level}-${event.last_fakeout.time}-${idx}`,
          type: "fakeout",
          direction,
          level: event.level,
          time: event.last_fakeout.time,
          source: "level_event",
          details: {
            symbol,
            tf,
            type: "fakeout",
            direction,
            level: event.level,
            time: event.last_fakeout.time,
            entry: event.last_fakeout.close,
            sl: null,
            sl_reason: null,
            level_event: levelEvent,
            context: {}
          }
        });
      }
    });
  }
  if (Array.isArray(setupItems)) {
    setupItems.forEach((item, idx) => {
      rows.push({
        id: `setup-${item.level}-${item.setup_index ?? idx}`,
        type: "setup",
        direction: item.direction,
        level: item.level,
        time: item.time,
        source: "setup",
        details: {
          symbol,
          tf,
          type: "setup",
          direction: item.direction,
          level: item.level,
          time: item.time,
          entry: item.entry,
          sl: item.sl,
          sl_reason: "setup_candle",
          setup_index: item.setup_index ?? null,
          level_event: null,
          context: {}
        }
      });
    });
  }
  if (Array.isArray(openings)) {
    openings.forEach((signal, idx) => {
      rows.push({
        id: `opening-${signal.type}-${signal.time}-${idx}`,
        type: signal.type ?? "opening",
        direction: signal.direction,
        level: signal.level,
        time: signal.time,
        source: "opening",
        details: {
          symbol: signal.symbol ?? symbol,
          tf: signal.tf ?? tf,
          ...signal,
          level_event: signal.level_event ?? signal.level_event_indices ?? null
        }
      });
    });
  }
  return rows.sort((a, b) => (b.time ?? 0) - (a.time ?? 0));
}

function buildMarkerDetailsMap(levelEvents, setupItems, openings, symbol, tf, candles = []) {
  const rows = buildWorkspaceSignalRows(levelEvents, setupItems, openings, symbol, tf);
  const candleByTime = new Map();
  if (Array.isArray(candles)) {
    candles.forEach((candle) => {
      if (candle?.time) {
        candleByTime.set(candle.time, candle);
      }
    });
  }
  const priority = { opening: 0, setup: 1, level_event: 2 };
  rows.sort((a, b) => {
    const pa = priority[a.source] ?? 3;
    const pb = priority[b.source] ?? 3;
    if (pa !== pb) {
      return pa - pb;
    }
    return (b.time ?? 0) - (a.time ?? 0);
  });
  const map = new Map();
  rows.forEach((row) => {
    if (!row.time) {
      return;
    }
    if (row.details && !row.details.candle) {
      const candle = candleByTime.get(row.time);
      if (candle) {
        row.details.candle = candle;
      }
    }
    const timeSec = Math.floor(row.time / 1000);
    if (!map.has(timeSec)) {
      map.set(timeSec, row.details);
    }
  });
  return map;
}

function toChartCandles(candles) {
  if (!Array.isArray(candles)) {
    return [];
  }
  return candles.map((candle) => ({
    time: Math.floor(candle.time / 1000),
    open: candle.open,
    high: candle.high,
    low: candle.low,
    close: candle.close
  }));
}

function toVolumeSeries(candles) {
  if (!Array.isArray(candles)) {
    return [];
  }
  return candles.map((candle) => ({
    time: Math.floor(candle.time / 1000),
    value: candle.volume
  }));
}

function computeSmaSeries(candles, period, field = "close") {
  if (!Array.isArray(candles) || candles.length === 0) {
    return [];
  }
  const values = candles.map((candle) => Number(candle[field] ?? candle.close ?? 0));
  const result = [];
  for (let idx = 0; idx < values.length; idx += 1) {
    if (idx + 1 < period) {
      continue;
    }
    const window = values.slice(idx + 1 - period, idx + 1);
    const sum = window.reduce((acc, val) => acc + val, 0);
    const average = sum / period;
    result.push({ time: Math.floor(candles[idx].time / 1000), value: average });
  }
  return result;
}

function buildLegendFromCandle(candle, timeOverride) {
  if (!candle) {
    return null;
  }
  const open = candle.open ?? 0;
  const close = candle.close ?? 0;
  const changePct = open ? ((close - open) / open) * 100 : 0;
  return {
    time: timeOverride ?? candle.time ?? null,
    open,
    high: candle.high ?? open,
    low: candle.low ?? open,
    close,
    changePct
  };
}

function getTimeRange(candles) {
  if (!Array.isArray(candles) || candles.length === 0) {
    return null;
  }
  const first = candles[0].time;
  const last = candles[candles.length - 1].time;
  if (!first || !last) {
    return null;
  }
  return { start: Math.floor(first / 1000), end: Math.floor(last / 1000) };
}

function buildReplayCandles(items) {
  if (!Array.isArray(items)) {
    return [];
  }
  return items
    .filter((item) => item && item.candle)
    .map((item) => ({
      time: item.time,
      open: item.candle.open,
      high: item.candle.high,
      low: item.candle.low,
      close: item.candle.close,
      volume: item.candle.volume
    }));
}

function buildReplayLevels(item) {
  if (!item || !Array.isArray(item.levels)) {
    return [];
  }
  const tol = Number(item.tol_pct_used ?? 0);
  const lastClose = item.candle?.close;
  return item.levels.map((level) => {
    let role = "mixed";
    if (lastClose && tol > 0) {
      const dist = Math.abs(level - lastClose) / lastClose;
      if (dist <= tol) {
        role = "mixed";
      } else if (level < lastClose) {
        role = "support";
      } else {
        role = "resistance";
      }
    }
    return {
      center: level,
      role,
      zone_low: level * (1 - tol),
      zone_high: level * (1 + tol),
      strength: 0
    };
  });
}

function filterLevelsForChart(levels, candles, maxLevels = 8) {
  if (!Array.isArray(levels) || levels.length === 0) {
    return [];
  }

  const normalized = levels
    .map((level) => {
      const center = toFiniteNumber(level?.center);
      if (center === null) {
        return null;
      }
      const roleRaw = level?.role;
      const role = roleRaw === "support" || roleRaw === "resistance" ? roleRaw : "mixed";
      const defaultHalfWidth = Math.max(Math.abs(center) * 0.0015, 1);
      let zoneLow = toFiniteNumber(level?.zone_low);
      let zoneHigh = toFiniteNumber(level?.zone_high);
      if (zoneLow === null) {
        zoneLow = center - defaultHalfWidth;
      }
      if (zoneHigh === null) {
        zoneHigh = center + defaultHalfWidth;
      }
      if (zoneHigh < zoneLow) {
        const tmp = zoneLow;
        zoneLow = zoneHigh;
        zoneHigh = tmp;
      }
      return {
        ...level,
        center,
        role,
        zone_low: zoneLow,
        zone_high: zoneHigh,
        strength: toFiniteNumber(level?.strength) ?? 0
      };
    })
    .filter(Boolean);

  const candleList = Array.isArray(candles) ? candles : [];
  const highs = candleList.map((item) => toFiniteNumber(item?.high)).filter((item) => item !== null);
  const lows = candleList.map((item) => toFiniteNumber(item?.low)).filter((item) => item !== null);
  const lastClose = toFiniteNumber(candleList[candleList.length - 1]?.close);

  let candidates = normalized;
  if (highs.length > 0 && lows.length > 0) {
    const minLow = Math.min(...lows);
    const maxHigh = Math.max(...highs);
    const range = Math.max(maxHigh - minLow, Math.abs(lastClose ?? minLow) * 0.02, 1);
    const bandLow = minLow - range * 0.6;
    const bandHigh = maxHigh + range * 0.6;
    const inBand = normalized.filter((level) => level.center >= bandLow && level.center <= bandHigh);
    if (inBand.length > 0) {
      candidates = inBand;
    }
  }

  const anchor =
    lastClose ??
    (highs.length > 0 && lows.length > 0 ? (Math.min(...lows) + Math.max(...highs)) / 2 : normalized[0].center);

  const sorted = [...candidates].sort((a, b) => {
    const distA = Math.abs(a.center - anchor);
    const distB = Math.abs(b.center - anchor);
    if (distA !== distB) {
      return distA - distB;
    }
    return (b.strength ?? 0) - (a.strength ?? 0);
  });

  if (sorted.length <= maxLevels) {
    return sorted;
  }

  const caps = { support: 3, resistance: 3, mixed: 2 };
  const used = { support: 0, resistance: 0, mixed: 0 };
  const selected = [];

  for (const level of sorted) {
    const roleKey = level.role ?? "mixed";
    if (used[roleKey] >= caps[roleKey]) {
      continue;
    }
    selected.push(level);
    used[roleKey] += 1;
    if (selected.length >= maxLevels) {
      break;
    }
  }

  if (selected.length > 0) {
    return selected;
  }
  return sorted.slice(0, maxLevels);
}

function buildReplayMarkers(signals) {
  if (!Array.isArray(signals)) {
    return [];
  }
  const mapped = signals
    .filter((signal) => signal && signal.time)
    .map((signal) => {
      const direction = signal.direction;
      const isBull = direction === "up" || direction === "long";
      let color = "#7a6a45";
      let shape = "circle";
      let position = isBull ? "belowBar" : "aboveBar";
      let text = signal.type?.toUpperCase?.() ?? "M";
      switch (signal.type) {
        case "break":
          color = isBull ? "#0f6b5c" : "#7a2f2f";
          shape = isBull ? "arrowUp" : "arrowDown";
          position = isBull ? "aboveBar" : "belowBar";
          text = "B";
          break;
        case "fakeout":
          color = "#c07a2f";
          shape = "circle";
          text = "F";
          break;
        case "setup":
          color = isBull ? "#2d8f6f" : "#7a2f2f";
          shape = isBull ? "arrowUp" : "arrowDown";
          text = "S";
          break;
        default:
          break;
      }
      return {
        time: Math.floor(signal.time / 1000),
        position,
        color,
        shape,
        text
      };
    });
  return mapped.sort((a, b) => a.time - b.time);
}

async function fetchPivotCounts() {
  const data = await fetchJson("/api/debug/pivots/BTCUSDT/1h?limit=200");
  const highs = Array.isArray(data.pivot_high) ? data.pivot_high.filter(Boolean).length : 0;
  const lows = Array.isArray(data.pivot_low) ? data.pivot_low.filter(Boolean).length : 0;
  return { highs, lows };
}

function LevelList({ items, emptyLabel }) {
  if (!Array.isArray(items) || items.length === 0) {
    return <p className="muted">{emptyLabel}</p>;
  }
  return (
    <ul className="level-list">
      {items.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  );
}

function EditableList({ items, onRemove }) {
  if (!Array.isArray(items) || items.length === 0) {
    return <p className="muted">None</p>;
  }
  return (
    <ul className="level-list">
      {items.map((item) => (
        <li key={item}>
          <span>{item}</span>
          <button className="btn btn-small" type="button" onClick={() => onRemove(item)}>
            Remove
          </button>
        </li>
      ))}
    </ul>
  );
}

function parseWatchlistSymbolInput(input) {
  if (!input) {
    return [];
  }
  const unique = new Set();
  return String(input)
    .split(/[\s,;]+/)
    .map((item) => item.trim().toUpperCase())
    .filter((item) => {
      if (!item || unique.has(item)) {
        return false;
      }
      unique.add(item);
      return true;
    });
}

function validateWatchlistSymbol(symbol) {
  if (!symbol) {
    return "Symbol is required.";
  }
  if (symbol.length < 6 || symbol.length > 20) {
    return "Symbol must be 6-20 characters.";
  }
  if (!/^[A-Z0-9]+$/.test(symbol)) {
    return "Symbol must be A-Z or 0-9.";
  }
  return "";
}

function buildWatchlistSymbolEntry(template, symbol, entryTfs) {
  const setups = template?.setups
    ? structuredClone(template.setups)
    : { continuation: true, retest: true, fakeout: true, setup_candle: true };
  const levels = template?.levels
    ? structuredClone(template.levels)
    : { auto: true, max_levels: 12, cluster_tol_pct: 0.003, overrides: { add: [], disable: [] } };
  levels.overrides = { add: [], disable: [] };
  return {
    symbol,
    enabled: true,
    entry_tfs: entryTfs,
    setups,
    levels
  };
}

function updateOverrides(watchlist, symbol, key, value) {
  if (!watchlist || !symbol) {
    return watchlist;
  }
  const next = structuredClone(watchlist);
  const entry = next.symbols?.find((item) => item.symbol === symbol);
  if (!entry) {
    return watchlist;
  }
  const list = entry.levels?.overrides?.[key] ?? [];
  if (!list.includes(value)) {
    list.push(value);
  }
  entry.levels.overrides[key] = list;
  return next;
}

function removeOverride(watchlist, symbol, key, value) {
  if (!watchlist || !symbol) {
    return watchlist;
  }
  const next = structuredClone(watchlist);
  const entry = next.symbols?.find((item) => item.symbol === symbol);
  if (!entry) {
    return watchlist;
  }
  const list = entry.levels?.overrides?.[key] ?? [];
  entry.levels.overrides[key] = list.filter((item) => item !== value);
  return next;
}

function getOverrides(watchlist, symbol, key) {
  if (!watchlist || !symbol) {
    return [];
  }
  const entry = watchlist.symbols?.find((item) => item.symbol === symbol);
  return entry?.levels?.overrides?.[key] ?? [];
}

function updateQuality(prev, path, value) {
  if (!prev) {
    return prev;
  }
  const next = structuredClone(prev);
  let target = next;
  for (let i = 0; i < path.length - 1; i += 1) {
    const key = path[i];
    if (!target[key]) {
      target[key] = {};
    }
    target = target[key];
  }
  const lastKey = path[path.length - 1];
  const numericFields = new Set([
    "min_score_by_type.break",
    "min_score_by_type.setup",
    "min_score_by_type.fakeout",
    "cooldown_minutes_by_type.break",
    "cooldown_minutes_by_type.setup",
    "cooldown_minutes_by_type.fakeout",
    "max_alerts_per_symbol_per_hour",
    "max_alerts_global_per_hour"
  ]);
  const pathKey = path.join(".");
  if (numericFields.has(pathKey)) {
    const num = Number(value);
    target[lastKey] = Number.isFinite(num) ? num : target[lastKey];
  } else {
    target[lastKey] = value;
  }
  return next;
}
