import api from "./api";

export interface StaffMessage {
  id: string;
  sender_id: string;
  recipient_id: string;
  appointment_id: string | null;
  content: string;
  is_read: boolean;
  created_at: string;
  sender_name: string;
  sender_role: string;
}

export interface InboxResponse {
  unread_count: number;
  messages: StaffMessage[];
}

export interface StaffMember {
  id: string;
  full_name: string;
  role: string;
}

export async function getInbox(): Promise<InboxResponse> {
  const { data } = await api.get<InboxResponse>("/messages/inbox");
  return data;
}

export async function getUnreadCount(): Promise<number> {
  const { data } = await api.get<{ unread_count: number }>("/messages/unread-count");
  return data.unread_count;
}

export async function sendMessage(
  recipientId: string,
  content: string,
  appointmentId?: string,
): Promise<StaffMessage> {
  const { data } = await api.post<StaffMessage>("/messages/", {
    recipient_id: recipientId,
    content,
    appointment_id: appointmentId ?? null,
  });
  return data;
}

export async function markRead(messageId: string): Promise<StaffMessage> {
  const { data } = await api.put<StaffMessage>(`/messages/${messageId}/read`);
  return data;
}

export async function getAppointmentMessages(appointmentId: string): Promise<StaffMessage[]> {
  const { data } = await api.get<StaffMessage[]>(`/messages/appointment/${appointmentId}`);
  return data;
}

/** Fetch messageable staff members (excludes the caller). */
export async function getStaffDirectory(): Promise<StaffMember[]> {
  const { data } = await api.get<StaffMember[]>("/messages/staff-directory");
  return data;
}
