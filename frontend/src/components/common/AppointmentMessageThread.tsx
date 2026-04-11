import { useEffect, useRef, useState } from "react";
import {
  getAppointmentMessages,
  getStaffDirectory,
  markRead,
  sendMessage,
} from "../../services/messages";
import type { StaffMember, StaffMessage } from "../../services/messages";
import { useAuth } from "../../context/AuthContext";

const ROLE_LABEL: Record<string, string> = {
  scheduler: "Scheduler",
  nurse: "Nurse",
  physician: "Physician",
};

const ROLE_COLOR: Record<string, string> = {
  scheduler: "bg-green-100 text-green-700",
  nurse: "bg-purple-100 text-purple-700",
  physician: "bg-amber-100 text-amber-700",
};

interface Props {
  appointmentId: string;
}

export function AppointmentMessageThread({ appointmentId }: Props) {
  const { user } = useAuth();
  const [messages, setMessages] = useState<StaffMessage[]>([]);
  const [staff, setStaff] = useState<StaffMember[]>([]);
  const [recipientId, setRecipientId] = useState("");
  const [content, setContent] = useState("");
  const [sending, setSending] = useState(false);
  const [open, setOpen] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    getAppointmentMessages(appointmentId).then((msgs) => {
      setMessages(msgs);
      // Mark unread messages as read
      msgs
        .filter((m) => !m.is_read && m.recipient_id === user?.id)
        .forEach((m) => markRead(m.id).catch(() => {}));
    });
    getStaffDirectory().then(setStaff);
  }, [open, appointmentId, user?.id]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async () => {
    if (!content.trim() || !recipientId) return;
    setSending(true);
    try {
      const msg = await sendMessage(recipientId, content.trim(), appointmentId);
      setMessages((prev) => [...prev, msg]);
      setContent("");
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="bg-white rounded-xl shadow">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center justify-between w-full p-5"
      >
        <div className="flex items-center gap-2">
          <svg className="h-5 w-5 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
          </svg>
          <h3 className="text-base font-semibold text-gray-900">Staff Messages</h3>
          {messages.filter((m) => !m.is_read && m.recipient_id === user?.id).length > 0 && (
            <span className="inline-flex items-center justify-center h-5 w-5 rounded-full bg-primary-600 text-white text-xs font-bold">
              {messages.filter((m) => !m.is_read && m.recipient_id === user?.id).length}
            </span>
          )}
        </div>
        <svg
          className={`h-4 w-4 text-gray-400 transition-transform ${open ? "rotate-180" : ""}`}
          fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
        <div className="border-t border-gray-100 p-5 space-y-4">
          {/* Thread */}
          <div className="space-y-3 max-h-72 overflow-y-auto pr-1">
            {messages.length === 0 ? (
              <p className="text-sm text-gray-400 text-center py-4">No messages yet.</p>
            ) : (
              messages.map((msg) => {
                const isMe = msg.sender_id === user?.id;
                return (
                  <div key={msg.id} className={`flex gap-3 ${isMe ? "flex-row-reverse" : ""}`}>
                    <div
                      className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${
                        ROLE_COLOR[msg.sender_role] ?? "bg-gray-100 text-gray-600"
                      }`}
                    >
                      {msg.sender_name.split(" ").map((n) => n[0]).join("").slice(0, 2).toUpperCase()}
                    </div>
                    <div className={`max-w-xs ${isMe ? "items-end" : "items-start"} flex flex-col`}>
                      <div className="flex items-center gap-1.5 mb-1">
                        <span className="text-xs font-medium text-gray-700">{isMe ? "You" : msg.sender_name}</span>
                        <span className="text-xs text-gray-400">{ROLE_LABEL[msg.sender_role] ?? msg.sender_role}</span>
                        <span className="text-xs text-gray-300">
                          {new Date(msg.created_at).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })}
                        </span>
                      </div>
                      <div
                        className={`rounded-xl px-3 py-2 text-sm ${
                          isMe
                            ? "bg-primary-600 text-white rounded-tr-sm"
                            : "bg-gray-100 text-gray-800 rounded-tl-sm"
                        }`}
                      >
                        {msg.content}
                      </div>
                    </div>
                  </div>
                );
              })
            )}
            <div ref={bottomRef} />
          </div>

          {/* Compose */}
          <div className="space-y-2 border-t border-gray-100 pt-4">
            <div className="flex gap-2">
              <select
                value={recipientId}
                onChange={(e) => setRecipientId(e.target.value)}
                className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none"
              >
                <option value="">Send to…</option>
                {staff.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.full_name} ({ROLE_LABEL[s.role] ?? s.role})
                  </option>
                ))}
              </select>
            </div>
            <div className="flex gap-2">
              <input
                type="text"
                value={content}
                onChange={(e) => setContent(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
                placeholder="Type a message…"
                className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none"
              />
              <button
                onClick={handleSend}
                disabled={sending || !content.trim() || !recipientId}
                className="rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50 transition-colors"
              >
                {sending ? "…" : "Send"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
