"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

type BreakdownItem = {
  factor: string;
  team: string | null;
  points: number;
  reason: string;
};

type Matchup = {
  gameId: string | number;
  date: string;
  homeTeam: string;
  awayTeam: string;
  probability: { home: number; away: number };
  projectedTotalGoals?: number | null;
  breakdown: BreakdownItem[];
};

type TodayResponse = { date: string; matchups: Matchup[] };

function prettyFactor(f: string) {
  const map: Record<string, string> = {
    points_pct: "Record",
    home_away: "Home/Away",
    injuries: "Injuries",
    goals: "Goals",
    form: "Form",
    goalie: "Goalie",
    h2h_recent: "H2H",
  };
  return map[f] ?? f;
}

export default function GamePage() {
  const params = useParams<{ gameId: string }>();
  const gameId = params.gameId;

  const [data, setData] = useState<TodayResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    const base = process.env.NEXT_PUBLIC_API_BASE;
    fetch(`${base}/today`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(setData)
      .catch((e) => setErr(String(e)));
  }, []);

  const matchup = useMemo(() => {
    const all = data?.matchups ?? [];
    return all.find((m) => String(m.gameId) === String(gameId)) ?? null;
  }, [data, gameId]);

  if (err)
    return (
      <div className="min-h-screen bg-[#141414] text-white p-6">
        Error: {err}
      </div>
    );
  if (!data)
    return (
      <div className="min-h-screen bg-[#141414] text-white p-6">
        Loading…
      </div>
    );
  if (!matchup)
    return (
      <div className="min-h-screen bg-[#141414] text-white p-6">
        Game not found.
      </div>
    );

  const home = matchup.homeTeam;
  const away = matchup.awayTeam;

  const ph = matchup.probability.home;
  const pa = matchup.probability.away;

  const fav = ph >= pa ? home : away;

    const rawItems = (matchup.breakdown ?? []).map((b) => {
    let signed = 0;
    if (b.team === home) signed = b.points;
    else if (b.team === away) signed = -b.points;
    return { ...b, signed };
    });

    // --- Form dedupe logic ---
    // Keep only the single most significant "form" item.
    // If both form items have the same absolute impact, show none.
    const formItems = rawItems.filter((x) => x.factor === "form");
    const nonFormItems = rawItems.filter((x) => x.factor !== "form");

    let finalItems = nonFormItems;

    if (formItems.length > 0) {
    const absVals = formItems.map((x) => Math.abs(x.signed));
    const maxVal = Math.max(...absVals);
    const winners = formItems.filter((x) => Math.abs(x.signed) === maxVal);

    // if exactly one winner, keep it; if tie, keep none
    if (winners.length === 1) {
        finalItems = [...nonFormItems, winners[0]];
    }
    }

    const items = finalItems;


  const maxAbs = Math.max(3, ...items.map((x) => Math.abs(x.signed)));

  return (
    <div className="min-h-screen bg-[#141414] text-white">
      <div className="mx-auto max-w-3xl p-6">
        <div className="text-2xl font-bold">
          {away} @ {home}
        </div>

        <div className="mt-2 text-sm text-white/60">
          <span className="font-semibold text-white">Favourite:</span>{" "}
          <span className="font-bold">{fav}</span>
        </div>

        <div className="mt-1 text-sm text-white/60">
          <span className="font-semibold text-white">Projected total:</span>{" "}
          <span className="font-bold">
            {typeof matchup.projectedTotalGoals === "number"
              ? matchup.projectedTotalGoals.toFixed(2)
              : "—"}
          </span>
        </div>

        <div className="mt-1 text-sm text-white/60">
          <span className="font-semibold text-white">Odds:</span>{" "}
          <span className="font-bold">{(pa * 100).toFixed(2)}%</span> {away} •{" "}
          <span className="font-bold">{(ph * 100).toFixed(2)}%</span> {home}
        </div>

        <div className="mt-6 grid gap-3">
          {items.map((b, idx) => (
            <div
              key={idx}
              className="rounded-2xl border border-white/10 bg-[#181818] p-4"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="text-sm font-bold">{prettyFactor(b.factor)}</div>
                  <div className="mt-1 text-xs text-white/60">{b.reason}</div>
                </div>
              </div>

              <div className="mt-3">
                <input
                  type="range"
                  min={-maxAbs}
                  max={maxAbs}
                  value={b.signed}
                  readOnly
                  className="w-full accent-white"
                />
                <div className="mt-1 flex justify-between text-[11px] text-white/60">
                  <span>{away}</span>
                  <span>{home}</span>
                </div>
              </div>
            </div>
          ))}
        </div>

        <Link
          href="/"
          className="mt-8 inline-block rounded-xl border border-white/15 px-3 py-2 text-sm font-semibold hover:border-white/30"
        >
          Back
        </Link>
      </div>
    </div>
  );
}
