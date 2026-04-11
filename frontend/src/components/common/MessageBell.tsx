import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getUnreadCount } from "../../services/messages";

export function MessageBell() {
  const [unread, setUnread] = useState(0);

  useEffect(() => {
    let cancelled = false;

    const poll = () => {
      getUnreadCount()
        .then((n) => { if (!cancelled) setUnread(n); })
        .catch(() => {});
    };

    poll();
    const id = setInterval(poll, 30_000); // poll every 30 s
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  return (
    <Link
      to="/messages"
      className="relative flex items-center justify-center h-9 w-9 rounded-lg text-gray-500 hover:bg-gray-100 transition-colors"
      aria-label="Messages"
    >
      <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
      </svg>
      {unread > 0 && (
        <span className="absolute -top-0.5 -right-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-primary-600 text-white text-[10px] font-bold">
          {unread > 9 ? "9+" : unread}
        </span>
      )}
    </Link>
  );
}
