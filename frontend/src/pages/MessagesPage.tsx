import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getInbox, markRead } from "../services/messages";
import type { StaffMessage } from "../services/messages";

const ROLE_LABEL: Record<string, string> = {
  scheduler: "Scheduler",
  nurse: "Nurse",
  physician: "Physician",
};

export function MessagesPage() {
  const [messages, setMessages] = useState<StaffMessage[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getInbox()
      .then(({ messages: msgs }) => setMessages(msgs))
      .finally(() => setLoading(false));
  }, []);

  const handleMarkRead = async (id: string) => {
    const updated = await markRead(id);
    setMessages((prev) => prev.map((m) => (m.id === id ? updated : m)));
  };

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto space-y-4">
      <h1 className="text-2xl font-bold text-gray-900">Messages</h1>

      {messages.length === 0 ? (
        <div className="bg-gray-50 rounded-xl p-8 text-center text-gray-500 text-sm">
          No messages yet.
        </div>
      ) : (
        <div className="space-y-2">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`bg-white/70 backdrop-blur-sm rounded-xl shadow-sm p-4 flex items-start gap-4 transition-colors ${
                !msg.is_read ? "border-l-4 border-primary-500" : ""
              }`}
            >
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-gray-100 text-sm font-semibold text-gray-600">
                {msg.sender_name.split(" ").map((n) => n[0]).join("").slice(0, 2).toUpperCase()}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-medium text-gray-900 text-sm">{msg.sender_name}</span>
                  <span className="text-xs text-gray-500">{ROLE_LABEL[msg.sender_role] ?? msg.sender_role}</span>
                  {!msg.is_read && (
                    <span className="inline-block h-2 w-2 rounded-full bg-primary-500" />
                  )}
                </div>
                <p className="text-sm text-gray-700">{msg.content}</p>
                <div className="mt-2 flex items-center gap-3">
                  <span className="text-xs text-gray-400">
                    {new Date(msg.created_at).toLocaleString(undefined, {
                      month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
                    })}
                  </span>
                  {msg.appointment_id && (
                    <Link
                      to={`/appointments/${msg.appointment_id}`}
                      className="text-xs text-primary-600 hover:underline"
                    >
                      View appointment →
                    </Link>
                  )}
                  {!msg.is_read && (
                    <button
                      onClick={() => handleMarkRead(msg.id)}
                      className="text-xs text-gray-400 hover:text-gray-600"
                    >
                      Mark read
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
