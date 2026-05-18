"use client";

import React, { useEffect, useRef } from "react";

export function TradingViewExternalWidget(props: {
  scriptSrc: string;
  config: Record<string, unknown>;
  className?: string;
  style?: React.CSSProperties;
}) {
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    while (el.firstChild) el.removeChild(el.firstChild);

    const script = document.createElement("script");
    script.type = "text/javascript";
    script.async = true;
    script.src = props.scriptSrc;
    script.innerHTML = JSON.stringify(props.config);
    el.appendChild(script);
  }, [props.scriptSrc, props.config]);

  return <div ref={ref} className={props.className} style={props.style} />;
}

