"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

type Matchup = {
  gameId: string | number;
  date: string;
  homeTeam: string;
  awayTeam: string;
  probability: { home: number; away: number };
  projectedTotalGoals?: number | null;
};

type TodayResponse = { date: string; matchups: Matchup[] };

function logoUrl(abbrev: string) {
  return `https://assets.nhle.com/logos/nhl/svg/${abbrev.toUpperCase()}_light.svg`;
}

function fmtOdds(x: number, percentMode: boolean) {
  return percentMode ? `${(x * 100).toFixed(2)}%` : x.toFixed(2);
}

function inRange(x: number, lo: number, hi: number) {
  return x >= lo && x <= hi;
}

export default function Page() {
  const [data, setData] = useState<TodayResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const [query, setQuery] = useState("");
  const [percentMode, setPercentMode] = useState(true);

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

  const all = data?.matchups ?? [];

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return all;
    return all.filter(
      (m) =>
        m.homeTeam.toLowerCase().includes(q) ||
        m.awayTeam.toLowerCase().includes(q)
    );
  }, [all, query]);

  const tossUps = useMemo(() => {
    return filtered.filter((m) => {
      const ph = m.probability.home;
      const pa = m.probability.away;
      return inRange(ph, 0.4, 0.6) && inRange(pa, 0.4, 0.6);
    });
  }, [filtered]);

  const heavyFavs = useMemo(() => {
    return filtered.filter(
      (m) => m.probability.home >= 0.9 || m.probability.away >= 0.9
    );
  }, [filtered]);

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

  return (
    <div className="min-h-screen bg-[#141414] text-white">
      <div className="mx-auto max-w-6xl p-6">
        <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
          <div>
            <div className="text-2xl font-bold">Today</div>
            <div className="mt-1 text-sm text-white/60">{data.date}</div>
          </div>

          <div className="flex flex-col gap-2 md:flex-row md:items-center">
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search team…"
              className="w-full md:w-72 rounded-xl border border-white/15 bg-[#141414] px-3 py-2 text-sm outline-none focus:border-white/30"
            />

            <button
              onClick={() => setPercentMode((v) => !v)}
              className="rounded-xl border border-white/15 px-3 py-2 text-sm font-semibold hover:border-white/30"
            >
              {percentMode ? "%" : "0–1"}
            </button>
          </div>
        </div>

        <Section title="Toss ups">
          <MatchupGrid matchups={tossUps} percentMode={percentMode} />
        </Section>

        <Section title="Heavy favourites">
          <MatchupGrid matchups={heavyFavs} percentMode={percentMode} />
        </Section>

        <Section title="All matchups">
          <MatchupGrid matchups={filtered} percentMode={percentMode} />
        </Section>
      </div>
    </div>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="mt-8">
      <div className="mb-3 text-lg font-bold">{title}</div>
      {children}
    </section>
  );
}

function MatchupGrid({
  matchups,
  percentMode,
}: {
  matchups: Matchup[];
  percentMode: boolean;
}) {
  if (!matchups.length) {
    return (
      <div className="rounded-2xl border border-white/10 bg-[#181818] p-4 text-sm text-white/60">
        —
      </div>
    );
  }

  return (
    <div className="grid gap-3 md:grid-cols-2">
      {matchups.map((m) => (
        <MatchupCard key={String(m.gameId)} m={m} percentMode={percentMode} />
      ))}
    </div>
  );
}

function MatchupCard({ m, percentMode }: { m: Matchup; percentMode: boolean }) {
  const ph = m.probability.home;
  const pa = m.probability.away;
  const fav = ph >= pa ? m.homeTeam : m.awayTeam;

  return (
    <Link
      href={`/game/${m.gameId}`}
      className="block rounded-2xl border border-white/10 bg-[#181818] p-4 hover:border-white/25"
    >
      <div className="grid gap-2">
        <Row
          team={m.awayTeam}
          bold={fav === m.awayTeam}
          right={fmtOdds(pa, percentMode)}
        />
        <Row
          team={m.homeTeam}
          bold={fav === m.homeTeam}
          right={fmtOdds(ph, percentMode)}
        />

        <div className="mt-1 text-sm">
          <span className="text-white/60">Projected total:</span>{" "}
          <span className="font-bold">
            {typeof m.projectedTotalGoals === "number"
              ? m.projectedTotalGoals.toFixed(2)
              : "—"}
          </span>
        </div>
      </div>
    </Link>
  );
}

function Row({
  team,
  bold,
  right,
}: {
  team: string;
  bold: boolean;
  right: string;
}) {
  return (
    <div className="flex items-center justify-between gap-3">
      <div className="flex items-center gap-3">
        <div className="relative h-6 w-6 shrink-0">
          <Image
            src={logoUrl(team)}
            alt=""
            fill
            sizes="24px"
            className="object-contain"
          />
        </div>
        <div className={bold ? "font-bold" : "font-medium"}>{team}</div>
      </div>
      <div className={bold ? "font-bold tabular-nums" : "font-medium tabular-nums"}>
        {right}
      </div>
    </div>
  );
}
