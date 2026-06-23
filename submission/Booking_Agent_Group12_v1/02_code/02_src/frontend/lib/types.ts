// Mirrors the FastAPI /v1 contract (booking_agent.api + agent.policy).

export interface EventOut {
  id: number;
  title: string;
  venue: string;
  city: string;
  starts_at: string;
  image_url?: string | null;
  detail_url?: string | null;
  status: string;
  price_from_sar?: string;
}

export interface Member {
  tier: string | null;
  discount_label: string;
  ticket_cap: number;
  is_member: boolean;
  label: string;
}

export interface CategoryPrice {
  category: string;
  base_sar: string;
  discounted_sar: string;
  available: number;
}

export interface Quote {
  category: string;
  quantity: number;
  lines: string[];
  total_sar: string;
}

export interface Hold {
  seat_ids: string[];
  expires_at: string;
  ttl_minutes: number;
}

export interface Confirmation {
  event_title: string;
  when: string;
  venue: string;
  seats: string[];
  subtotal_sar: string;
  vat_sar: string;
  total_sar: string;
  expires_at: string;
}

export interface Payment {
  booking_id: number;
  total_sar: string;
}

export interface Ticket {
  booking_id: number;
  event_title: string;
  seats: string[];
  total_sar: string;
  email: string;
  qr_url: string;
}

export interface AgentReply {
  session_id: string;
  reply: string;
  step: string;
  suggestions: string[];
  events: EventOut[] | null;
  member: Member | null;
  categories: CategoryPrice[] | null;
  quote: Quote | null;
  seatmap_url: string | null;
  hold: Hold | null;
  confirmation: Confirmation | null;
  payment: Payment | null;
}

export interface Health {
  status: string;
  provider: string;
  model: string;
  currency: string;
  vat_rate: number;
  hold_ttl_minutes: number;
  llm_configured: boolean;
}
