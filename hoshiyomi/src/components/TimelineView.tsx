/* タイムライン（§9）— 日・月・年・人生のズーム切替コンテナ。
   日=DayDetail、月=CalendarView（既存を接続）。年・人生は TimelineEvent[] を消費する。 */

import { useMemo, useState } from "react";
import { C, SANS } from "../theme";
import type { ChartData } from "../lib/parseYaml";
import {
  fromTransitDaily, fromKeyDates, fromUserEvent, mergeEvents, yearOf,
  type TimelineEvent, type TimelineScale, type UserEventInput,
} from "../lib/timeline";
import { listUserEvents, saveUserEvent, deleteUserEvent, listLifeEvents } from "../lib/storage";
import DiaryPanel from "./DiaryPanel";
import CalendarView from "./CalendarView";
import DayDetail from "./DayDetail";
import YearView from "./YearView";
import LifeView from "./LifeView";
import UserEventEditor from "./UserEventEditor";

const SCALES: { id: TimelineScale; label: string }[] = [
  { id: "day", label: "日" },
  { id: "month", label: "月" },
  { id: "year", label: "年" },
  { id: "life", label: "人生" },
];

// 年ビューに出す占術イベントの orb 閾値（タイトなアスペクトに絞る）
const YEAR_VIEW_ORB_MAX = 0.5;

export default function TimelineView({
  data,
  selected,
  onSelectDate,
  onAskAI,
}: {
  data: ChartData;
  selected: string;
  onSelectDate: (date: string) => void;
  onAskAI: (date: string) => void;
}) {
  const [scale, setScale] = useState<TimelineScale>("month");
  const [year, setYear] = useState(() => yearOf(data.transit.todayDate));
  const [userEvents, setUserEvents] = useState<TimelineEvent[]>(() =>
    listUserEvents(data.profileId),
  );
  const [editing, setEditing] = useState<TimelineEvent | "new" | null>(null);

  // life_events.yaml（§10.2）は読み込み時に localStorage へ保存される。ここでは読むだけ
  const lifeEvents = useMemo(() => listLifeEvents(data.profileId), [data.profileId]);

  const astroEvents = useMemo(
    () =>
      mergeEvents(
        fromTransitDaily(data.transit.daily, YEAR_VIEW_ORB_MAX),
        fromKeyDates(data.transit.summary),
        lifeEvents,
      ),
    [data, lifeEvents],
  );
  const allEvents = useMemo(
    () => mergeEvents(astroEvents, userEvents),
    [astroEvents, userEvents],
  );
  const transitDates = useMemo(
    () => new Set(data.transit.daily.map((d) => d.date)),
    [data],
  );

  const openDay = (date: string) => {
    onSelectDate(date);
    setScale("day");
  };
  const openYear = (y: number) => {
    setYear(y);
    setScale("year");
  };
  const saveEvent = (input: UserEventInput, id?: string) => {
    setUserEvents(saveUserEvent(data.profileId, fromUserEvent(input, id)));
    setEditing(null);
  };
  const removeEvent = (id: string) => {
    setUserEvents(deleteUserEvent(data.profileId, id));
  };

  return (
    <div>
      {/* ズーム切替（§9.2） */}
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 18, flexWrap: "wrap" }}>
        <div style={{ display: "inline-flex", border: `1px solid ${C.line}`, borderRadius: 9, overflow: "hidden" }}>
          {SCALES.map((s) => (
            <button
              key={s.id}
              onClick={() => setScale(s.id)}
              aria-pressed={scale === s.id}
              style={{
                background: scale === s.id ? C.panel2 : "transparent",
                color: scale === s.id ? C.text : C.sub,
                border: "none",
                borderBottom: `2px solid ${scale === s.id ? C.dawn : "transparent"}`,
                padding: "8px 18px", fontSize: 13.5, cursor: "pointer",
                fontFamily: SANS, letterSpacing: "0.1em",
              }}
            >
              {s.label}
            </button>
          ))}
        </div>
        {(scale === "year" || scale === "life") && (
          <button
            onClick={() => setEditing("new")}
            style={{
              background: "transparent", border: `1px solid ${C.dawn}`, color: C.dawn,
              borderRadius: 8, padding: "7px 14px", cursor: "pointer", fontSize: 13, fontFamily: SANS,
            }}
          >
            ＋ 予定を追加
          </button>
        )}
      </div>

      {editing !== null && (
        <UserEventEditor
          initial={editing === "new" ? null : editing}
          onSave={saveEvent}
          onCancel={() => setEditing(null)}
        />
      )}

      {scale === "day" && (
        <>
          <DayDetail data={data} date={selected} onNavigate={onSelectDate} onAskAI={onAskAI} />
          <DiaryPanel
            date={selected}
            entry={userEvents.find((e) => e.source === "diary" && e.id === `diary:${selected}`) ?? null}
            onSave={(text) =>
              setUserEvents(
                saveUserEvent(data.profileId, {
                  id: `diary:${selected}`,
                  type: "diary",
                  date: selected,
                  title: text,
                  source: "diary",
                }),
              )
            }
            onDelete={() => setUserEvents(deleteUserEvent(data.profileId, `diary:${selected}`))}
          />
        </>
      )}
      {scale === "month" && (
        <CalendarView data={data} selected={selected} onSelect={openDay} />
      )}
      {scale === "year" && (
        <YearView
          year={year}
          onYearChange={setYear}
          events={allEvents}
          transitDates={transitDates}
          onOpenDay={openDay}
          onOpenMonth={() => setScale("month")}
          onEdit={(ev) => setEditing(ev)}
          onDelete={removeEvent}
        />
      )}
      {scale === "life" && (
        <LifeView
          birthYear={yearOf(data.birthDate)}
          events={allEvents}
          transitDates={transitDates}
          onOpenYear={openYear}
          onOpenDay={openDay}
          onEdit={(ev) => setEditing(ev)}
          onDelete={removeEvent}
        />
      )}
    </div>
  );
}
