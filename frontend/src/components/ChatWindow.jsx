//  frontend/src/components/ChatWindow.jsx 
import React, { useState } from "react";
import { Send } from "lucide-react";
import MessageItem from "./MessageItem";

export default function ChatWindow({
  messages,
  options,
  isWaiting,
  sessionId,
  onSubmit,
  onClickOption,
  bottomRef,
}) {
  const [input, setInput] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    const value = input.trim();
    if (!value || isWaiting) return;
    setInput("");
    await onSubmit(value);
  };

  return (
    <div className="bg-[#0f172a] border border-white/10 rounded-2xl shadow-2xl overflow-hidden">
      {/* Messages */}
      <div className="px-6 py-5 h-[560px] overflow-y-auto space-y-4">
        {messages.map((m, idx) => (
          <MessageItem key={idx} message={m} />
        ))}

        {/* Options */}
        {Array.isArray(options) && options.length > 0 && (
          <div className="flex flex-wrap gap-2 pt-2">
            {options.map((opt) => (
              <button
                key={opt}
                onClick={() => onClickOption(opt)}
                disabled={isWaiting}
                className="px-3 py-2 rounded-xl bg-white/5 border border-white/10 hover:bg-white/10 text-sm disabled:opacity-50"
              >
                {opt}
              </button>
            ))}
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="p-4 border-t border-white/10">
        <div className="flex items-center gap-3">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="메시지를 입력하세요"
            className="flex-1 rounded-2xl px-4 py-3 bg-white/5 border border-white/10 focus:outline-none focus:ring-2 focus:ring-white/20 text-sm"
            disabled={isWaiting}
          />
          <button
            type="submit"
            disabled={isWaiting || !input.trim()}
            className="rounded-2xl px-4 py-3 bg-white text-black font-semibold flex items-center gap-2 disabled:opacity-50"
            title="전송"
          >
            <Send size={18} />
            전송
          </button>
        </div>

        <div className="mt-2 text-xs text-white/50">
          세션: {sessionId ? sessionId.slice(0, 8) + "..." : "없음"}
        </div>
      </form>
    </div>
  );
}
