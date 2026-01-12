// [FINAL] frontend/src/components/MessageItem.jsx — One message bubble renderer (text/json supported)
import React, { useMemo } from "react";

export default function MessageItem({ message }) {
  const isUser = message.role === "user";

  const prettyJson = useMemo(() => {
    if (message.kind !== "json" || !message.jsonObj) return null;
    try {
      return JSON.stringify(message.jsonObj, null, 2);
    } catch {
      return null;
    }
  }, [message]);

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap ${
          isUser
            ? "bg-white text-black"
            : "bg-white/5 border border-white/10 text-white"
        }`}
      >
        {message.kind === "json" && prettyJson ? (
          <pre className="text-xs leading-relaxed overflow-x-auto">{prettyJson}</pre>
        ) : (
          message.content
        )}
      </div>
    </div>
  );
}
