export const mockDashboard = {
  metrics: {
    factor_total: 128,
    factor_online: 36,
    factor_research: 74,
    run_7d: 52,
    run_success_rate_7d: 0.92,
    latest_scoring_date: "2026-03-20",
  },
  categoryDistribution: [
    { category: "MOM", count: 28 },
    { category: "TREND", count: 22 },
    { category: "VOL", count: 18 },
    { category: "FUND", count: 20 },
    { category: "QUALITY", count: 16 },
    { category: "OTHER", count: 24 },
  ],
  runTrend30d: Array.from({ length: 30 }).map((_, i) => {
    const d = new Date();
    d.setDate(d.getDate() - (29 - i));
    const run_count = 1 + (i % 8);
    const success_count = Math.max(0, run_count - (i % 9 === 0 ? 1 : 0));
    return {
      date: d.toISOString().slice(0, 10),
      run_count,
      success_count,
    };
  }),
};

