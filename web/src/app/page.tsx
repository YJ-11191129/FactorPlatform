import {
  AlertOutlined,
  ApartmentOutlined,
  BarChartOutlined,
  CloudServerOutlined,
  CompassOutlined,
  ControlOutlined,
  DatabaseOutlined,
  DeploymentUnitOutlined,
  FundProjectionScreenOutlined,
  LineChartOutlined,
  RadarChartOutlined,
  SafetyCertificateOutlined,
} from "@ant-design/icons";
import Link from "next/link";

import styles from "./page.module.css";

const assets = [
  { symbol: "XAU/USD", state: "Elevated vol", delta: "+0.42%", price: "2,438.10", confidence: "74%" },
  { symbol: "BTC/USD", state: "Event watch", delta: "+1.28%", price: "69,420", confidence: "61%" },
  { symbol: "S&P 500", state: "Trend check", delta: "+0.16%", price: "5,326.2", confidence: "67%" },
  { symbol: "USD/JPY", state: "Range risk", delta: "-0.18%", price: "156.82", confidence: "58%" },
];

const features = [
  {
    title: "Multi-Agent Market Reasoning",
    description: "Economist, quant, technical, risk, news, and contrarian agents compare evidence before a signal is surfaced.",
    metric: "6 agents",
    icon: ApartmentOutlined,
  },
  {
    title: "Volatility Regime Detection",
    description: "Classifies volatility, trend, liquidity, and tail-risk context so research is framed by the current market state.",
    metric: "Elevated",
    icon: RadarChartOutlined,
  },
  {
    title: "Signal Screening Engine",
    description: "Ranks candidates by probability, confidence interval, trigger quality, and rejection evidence.",
    metric: "Screened",
    icon: ControlOutlined,
  },
  {
    title: "Scenario-Based Forecasting",
    description: "Builds base, upside, and defensive paths with explicit assumptions and invalidation levels.",
    metric: "3 paths",
    icon: CompassOutlined,
  },
  {
    title: "Risk-Aware Position Context",
    description: "Shows stop discipline, reward/risk estimates, horizon, and exposure context before any decision support output.",
    metric: "2.3:1",
    icon: SafetyCertificateOutlined,
  },
  {
    title: "Research Copilot",
    description: "Ask structured market questions, retrieve signal rationale, and explain why candidates were rejected.",
    metric: "Audit ready",
    icon: CloudServerOutlined,
  },
];

const agents = [
  { name: "Economist Agent", note: "Real-yield sensitivity and central-bank path review." },
  { name: "Quant Agent", note: "Factor strength, drawdown behavior, and sample stability." },
  { name: "Technical Agent", note: "Trend structure, acceptance levels, and failed-breakout risk." },
  { name: "Risk Agent", note: "Exposure cap, stop discipline, and adverse scenario pressure." },
  { name: "News Agent", note: "Event windows, headline drift, and catalyst freshness." },
  { name: "Contrarian Agent", note: "Crowding, consensus overreach, and rejection evidence." },
];

const scenarios = [
  { label: "Bullish continuation", probability: "42%", tone: "positive" },
  { label: "Neutral consolidation", probability: "36%", tone: "neutral" },
  { label: "Defensive reversal", probability: "22%", tone: "risk" },
];

const terminalMetrics = [
  { label: "AI Confidence", value: "74%", detail: "3-agent agreement", tone: "positive" },
  { label: "Volatility Regime", value: "Elevated", detail: "ATR + event window", tone: "warningText" },
  { label: "Risk/Reward Estimate", value: "2.3:1", detail: "after invalidation level", tone: "neutral" },
  { label: "Stop-Loss Discipline", value: "Required", detail: "prior value area break", tone: "risk" },
];

const signalRows = [
  { label: "Candidate", value: "XAU/USD continuation" },
  { label: "Probability range", value: "62-81%" },
  { label: "Risk level", value: "Elevated", tone: "warningText" },
  { label: "Trigger condition", value: "Acceptance above prior high" },
  { label: "Rejected alternative", value: "BTC/USD breakout - liquidity confirmation failed" },
];

const pricing = [
  {
    tier: "Free",
    price: "$0",
    description: "For initial research workflow evaluation.",
    items: ["Research workspace", "Limited signal history", "Market regime snapshot", "Starter copilot queries"],
  },
  {
    tier: "Pro",
    price: "$49",
    description: "For active market research and signal screening.",
    items: ["Signal history", "Market regime dashboard", "AI copilot queries", "Advanced risk analytics"],
  },
  {
    tier: "Institutional",
    price: "Custom",
    description: "For teams running governed research and review workflows.",
    items: ["Team workflow", "Private data integrations", "Audit lineage", "Institutional reporting"],
  },
];

function TerminalMockup() {
  return (
    <div className={styles.terminal} aria-label="AI Research Terminal mockup">
      <div className={styles.terminalHeader}>
        <div>
          <span className={styles.terminalKicker}>AI Research Terminal</span>
          <h2>Cross-market signal review</h2>
        </div>
        <span className={styles.terminalStatus}>Research mode</span>
      </div>

      <div className={styles.assetStrip}>
        {assets.map((asset) => (
          <button key={asset.symbol} className={styles.assetButton} type="button">
            <span>{asset.symbol}</span>
            <small>{asset.state}</small>
            <em>{asset.price}</em>
            <strong className={asset.delta.startsWith("+") ? styles.positive : styles.negative}>{asset.delta}</strong>
            <small>AI confidence {asset.confidence}</small>
          </button>
        ))}
      </div>

      <div className={styles.terminalGrid}>
        <section className={styles.chartPanel}>
          <div className={styles.chartHeader}>
            <span>XAU/USD scenario path</span>
            <strong>Horizon: 3-7D</strong>
          </div>
          <svg className={styles.chart} viewBox="0 0 640 260" role="img" aria-label="Simulated low contrast market chart">
            <defs>
              <linearGradient id="lineFade" x1="0" x2="1" y1="0" y2="0">
                <stop offset="0%" stopColor="#22D3EE" stopOpacity="0.25" />
                <stop offset="62%" stopColor="#22D3EE" stopOpacity="0.95" />
                <stop offset="100%" stopColor="#34D399" stopOpacity="0.85" />
              </linearGradient>
              <linearGradient id="areaFade" x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%" stopColor="#22D3EE" stopOpacity="0.16" />
                <stop offset="100%" stopColor="#22D3EE" stopOpacity="0" />
              </linearGradient>
            </defs>
            {[40, 80, 120, 160, 200, 240].map((y) => (
              <line key={y} x1="0" x2="640" y1={y} y2={y} className={styles.gridLine} />
            ))}
            {[80, 160, 240, 320, 400, 480, 560].map((x) => (
              <line key={x} x1={x} x2={x} y1="24" y2="248" className={styles.gridLine} />
            ))}
            <path
              d="M 18 202 C 78 178, 120 186, 176 150 S 278 115, 332 130 S 438 88, 498 96 S 584 72, 622 48 L 622 248 L 18 248 Z"
              fill="url(#areaFade)"
            />
            <path
              d="M 18 202 C 78 178, 120 186, 176 150 S 278 115, 332 130 S 438 88, 498 96 S 584 72, 622 48"
              fill="none"
              stroke="url(#lineFade)"
              strokeWidth="3"
              strokeLinecap="round"
            />
            <path d="M 18 214 C 142 206, 238 174, 352 168 S 520 126, 622 122" fill="none" stroke="#A78BFA" strokeOpacity="0.42" strokeWidth="2" strokeDasharray="6 8" />
            <circle cx="498" cy="96" r="5" fill="#34D399" />
            <circle cx="622" cy="48" r="5" fill="#22D3EE" />
          </svg>
          <div className={styles.chartMetaGrid}>
            <div>
              <span>Trigger</span>
              <strong>Close above 2,445 + USD beta stable</strong>
            </div>
            <div>
              <span>Invalidation</span>
              <strong>Break below prior value area</strong>
            </div>
            <div>
              <span>Model uncertainty</span>
              <strong>Medium - event risk active</strong>
            </div>
          </div>
        </section>

        <aside className={styles.metricsPanel}>
          {terminalMetrics.map((metric) => (
            <div key={metric.label} className={styles.metricCard}>
              <span>{metric.label}</span>
              <strong className={styles[metric.tone]}>{metric.value}</strong>
              <em>{metric.detail}</em>
            </div>
          ))}
        </aside>
      </div>

      <div className={styles.terminalFooter}>
        <div className={styles.researchNote}>
          <span>Signal rationale</span>
          <p>Momentum remains constructive while volatility is elevated. Confirmation requires price acceptance above the prior high and stable USD sensitivity.</p>
        </div>
        <div className={styles.researchNote}>
          <span>Scenario analysis</span>
          <p>Base case favors continuation, but a defensive reversal remains active if real-yield pressure reappears.</p>
        </div>
        <div className={styles.researchNote}>
          <span>Stop-loss discipline</span>
          <p>Stop-loss discipline, exposure cap, and time horizon are required before any decision support output is acted on.</p>
        </div>
        <div className={styles.researchNote}>
          <span>Market microstructure notes</span>
          <p>Liquidity is thinner around event windows. Avoid interpreting single-candle extensions as confirmation.</p>
        </div>
      </div>
    </div>
  );
}

export default function Home() {
  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <Link href="/" className={styles.logo} aria-label="FactorPlatform home">
          <span className={styles.logoMark}>FP</span>
          <span>FactorPlatform</span>
        </Link>
        <nav className={styles.nav} aria-label="Primary navigation">
          <a href="#product">Product</a>
          <a href="#features">Features</a>
          <a href="#markets">Markets</a>
          <a href="#pricing">Pricing</a>
        </nav>
        <div className={styles.headerActions}>
          <Link href="/settings" className={styles.secondaryHeaderLink}>Login</Link>
          <Link href="/dashboard" className={styles.headerCta}>Launch App</Link>
        </div>
      </header>

      <section className={styles.hero} id="product">
        <div className={styles.heroCopy}>
          <h1>
            <span>AI Market Intelligence</span>
            <span>for Risk-Aware</span>
            <span>Trading Research</span>
          </h1>
          <p>
            Transform market noise into structured signals, scenario analysis, and volatility-aware insights across forex,
            commodities, crypto, and indices. Designed for research and decision support, not blind signal following.
          </p>
          <div className={styles.heroActions}>
            <Link href="#features" className={styles.primaryCta}>Explore Platform</Link>
            <Link href="/dashboard" className={styles.secondaryCta}>View Research Terminal</Link>
          </div>
          <div className={styles.trustRow}>
            <span>Probabilistic insight</span>
            <span>Risk filters</span>
            <span>Not financial advice</span>
          </div>
        </div>
        <TerminalMockup />
      </section>

      <section className={styles.section} id="features">
        <div className={styles.sectionHeader}>
          <span>Multi-agent intelligence</span>
          <h2>Structured analysis before signal consideration</h2>
          <p>Each module is designed to support research judgment by separating evidence, uncertainty, and risk context.</p>
        </div>
        <div className={styles.featureGrid}>
          {features.map((feature) => {
            const Icon = feature.icon;
            return (
              <article key={feature.title} className={styles.featureCard}>
                <div className={styles.featureTopline}>
                  <span className={styles.iconWrap}><Icon /></span>
                  <span className={styles.featureMetric}>{feature.metric}</span>
                </div>
                <h3>{feature.title}</h3>
                <p>{feature.description}</p>
              </article>
            );
          })}
        </div>
      </section>

      <section className={styles.splitSection} id="markets">
        <div className={styles.agentPanel}>
          <span className={styles.sectionLabel}>Agent review</span>
          <h2>Multiple perspectives, one controlled research workflow</h2>
          <p>
            The platform is built around agent disagreement, rejection evidence, and market regime context. It is meant to
            make research assumptions visible before a trade idea moves forward.
          </p>
          <div className={styles.agentList}>
            {agents.map((agent) => (
              <article key={agent.name}>
                <strong>{agent.name}</strong>
                <span>{agent.note}</span>
              </article>
            ))}
          </div>
        </div>
        <div className={styles.signalPanel}>
          <div className={styles.panelHeader}>
            <LineChartOutlined />
            <span>Signal screening view</span>
          </div>
          <div className={styles.screeningSummary}>
            <div>
              <span>Screening decision</span>
              <strong>Conditional research candidate</strong>
            </div>
            <div className={styles.probabilityRail} aria-label="Qualifying probability 68 percent">
              <span style={{ width: "68%" }} />
            </div>
          </div>
          {signalRows.map((row) => (
            <div key={row.label} className={styles.screeningRow}>
              <span>{row.label}</span>
              <strong className={row.tone ? styles[row.tone] : undefined}>{row.value}</strong>
            </div>
          ))}
          <div className={styles.scenarioStack}>
            {scenarios.map((item) => (
              <div key={item.label} className={styles.scenarioItem}>
                <span>{item.label}</span>
                <strong className={styles[item.tone]}>{item.probability}</strong>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className={styles.copilotSection}>
        <div className={styles.sectionHeader}>
          <span>MarketGPT / AI Copilot</span>
          <h2>Ask research questions, not performance promises</h2>
          <p>Use the copilot to inspect regime changes, summarize drivers, compare trend strength, and audit rejected signals.</p>
        </div>
        <div className={styles.promptGrid}>
          {[
            "What changed in the USD/JPY risk regime?",
            "Summarize gold volatility drivers.",
            "Compare trend strength across major indices.",
            "Explain why this signal was rejected.",
          ].map((prompt) => (
            <div key={prompt} className={styles.promptCard}>
              <DatabaseOutlined />
              <span>{prompt}</span>
            </div>
          ))}
        </div>
      </section>

      <section className={styles.riskSection}>
        <div>
          <span className={styles.sectionLabel}>Risk-aware by design</span>
          <h2>Decision support with explicit uncertainty</h2>
          <p>
            Outputs are probabilistic research aids, not deterministic predictions. Signal rejection, risk filters, model
            uncertainty, and market regime context remain visible throughout the workflow.
          </p>
        </div>
        <div className={styles.riskGrid}>
          <div><AlertOutlined /><span>Probabilistic outputs, not deterministic predictions</span></div>
          <div><SafetyCertificateOutlined /><span>Signal rejection and risk filters</span></div>
          <div><FundProjectionScreenOutlined /><span>Uncertainty-aware model interpretation</span></div>
          <div><BarChartOutlined /><span>Market regime context</span></div>
        </div>
        <p className={styles.disclaimer}>FactorPlatform provides research tooling and decision support. It is not financial advice.</p>
      </section>

      <section className={styles.section} id="pricing">
        <div className={styles.sectionHeader}>
          <span>Pricing</span>
          <h2>Research workflows for individuals and institutions</h2>
          <p>Choose a workspace based on evidence depth, collaboration needs, and risk analytics requirements.</p>
        </div>
        <div className={styles.pricingGrid}>
          {pricing.map((plan) => (
            <article key={plan.tier} className={styles.pricingCard}>
              <h3>{plan.tier}</h3>
              <strong>{plan.price}</strong>
              <p>{plan.description}</p>
              <ul>
                {plan.items.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
              <Link href="/dashboard" className={styles.planButton}>Explore workspace</Link>
            </article>
          ))}
        </div>
      </section>

      <section className={styles.finalCta}>
        <DeploymentUnitOutlined />
        <h2>Build a more disciplined market research workflow</h2>
        <p>Review signals, scenarios, regimes, and risk context inside one institutional research terminal.</p>
        <Link href="/dashboard" className={styles.primaryCta}>View Research Terminal</Link>
      </section>

      <footer className={styles.footer}>
        <span>FactorPlatform</span>
        <p>Risk disclaimer: market analysis is probabilistic and intended for research use only. Terms / Privacy</p>
      </footer>
    </main>
  );
}
