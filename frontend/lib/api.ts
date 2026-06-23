import type { AgentReply, EventOut, Health, SeatMapData, Ticket, VenueLayout } from "./types";

const BASE =
  process.env.NEXT_PUBLIC_API_BASE?.replace(/\/$/, "") || "http://localhost:8000";

/** Prefix a relative /v1 path (seat-map / QR images) with the API origin. */
export function mediaUrl(path: string): string {
  return /^https?:/.test(path) ? path : `${BASE}${path}`;
}

async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
    cache: "no-store",
  });
  const text = await res.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }
  if (!res.ok) {
    const msg =
      data && typeof data === "object" && "detail" in data
        ? String((data as { detail: unknown }).detail)
        : `HTTP ${res.status}`;
    throw new Error(msg);
  }
  return data as T;
}

export const health = () => req<Health>("GET", "/v1/healthz");

export const listEvents = (query?: string) =>
  req<EventOut[]>(
    "GET",
    `/v1/events${query ? `?query=${encodeURIComponent(query)}` : ""}`,
  );

export const createSession = async () =>
  (await req<{ session_id: string }>("POST", "/v1/sessions", {})).session_id;

export const chat = (sessionId: string, message: string) =>
  req<AgentReply>("POST", "/v1/chat", { session_id: sessionId, message });

export const pay = (bookingId: number) =>
  req<{ ticket: Ticket }>("POST", `/v1/pay/${bookingId}`, {});

export const seats = (eventId: number, category: string) =>
  req<SeatMapData>(
    "GET",
    `/v1/events/${eventId}/seats?category=${encodeURIComponent(category)}`,
  );

export const venue = (eventId: number) =>
  req<VenueLayout>("GET", `/v1/events/${eventId}/venue`);
