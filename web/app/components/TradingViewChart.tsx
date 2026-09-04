"use client";

import { useEffect, useRef } from "react";

declare global {
  interface Window {
    TradingView?: { widget: new (config: Record<string, unknown>) => unknown };
  }
}

let renderCount = 0;

export function TradingViewChart({ symbol }: { symbol: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const idRef = useRef(`tv_${renderCount++}`);

  useEffect(() => {
    const containerId = idRef.current;
    let cancelled = false;

    function init() {
      if (cancelled || !window.TradingView || !containerRef.current) return;
      containerRef.current.innerHTML = `<div id="${containerId}" style="height:100%"></div>`;
      new window.TradingView.widget({
        autosize: true,
        symbol,
        interval: "D",
        timezone: "exchange",
        theme: "dark",
        style: "1",
        locale: "en",
        toolbar_bg: "#111827",
        enable_publishing: false,
        allow_symbol_change: true,
        container_id: containerId,
      });
    }

    const existing = document.getElementById("tradingview-widget-script");
    if (existing && window.TradingView) {
      init();
    } else if (existing) {
      existing.addEventListener("load", init);
    } else {
      const script = document.createElement("script");
      script.id = "tradingview-widget-script";
      script.src = "https://s3.tradingview.com/tv.js";
      script.async = true;
      script.addEventListener("load", init);
      document.body.appendChild(script);
    }

    return () => {
      cancelled = true;
    };
  }, [symbol]);

  return (
    <div className="tradingview-widget-container mt-4" style={{ height: 480 }}>
      <div ref={containerRef} style={{ height: "100%" }} />
    </div>
  );
}
