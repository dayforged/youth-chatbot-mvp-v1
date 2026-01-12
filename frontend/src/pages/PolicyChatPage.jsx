// frontend/src/pages/PolicyChatPage.jsx 
import React, { useEffect, useMemo, useRef, useState } from "react";
import Mascot from "../components/Mascot";
import ChatWindow from "../components/ChatWindow";

const API_URL = "http://localhost:8000/chat";

/**
 * 백엔드 계약(스키마):
 * - Request: { message, session_id }
 * - Response: { session_id, mode, answer, options, debug_profile }
 *
 * 주의:
 * - answer는 문자열. 내부에 JSON string이 들어올 수 있음(RAG 결과)
 */
export default function PolicyChatPage() {
  const [sessionId, setSessionId] = useState(null);

  // messages: [{ role: "user"|"assistant", content: string, kind?: "text"|"json", jsonObj?: object }]
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content: "정책 정리 챗봇입니다. 먼저 몇 가지만 확인할게요.",
      kind: "text",
    },
  ]);

  const [mode, setMode] = useState("onboarding"); // onboarding | followup | answer
  const [options, setOptions] = useState(null);   // string[] | null
  const [isWaiting, setIsWaiting] = useState(false);

  const bottomRef = useRef(null);

  // ---- util: safe parse JSON string ----
  const tryParseJson = (text) => {
    if (!text || typeof text !== "string") return null;
    const t = text.trim();
    if (!t.startsWith("{") && !t.startsWith("[")) return null;
    try {
      return JSON.parse(t);
    } catch {
      return null;
    }
  };

  const normalizeAnswerText = (data) => {
    // 호환 처리: 혹시 구버전 키가 섞여도 망가지지 않게
    return data?.answer ?? data?.assistant_message ?? data?.message ?? "";
  };

  const pushAssistantMessage = (rawText) => {
    const jsonObj = tryParseJson(rawText);
    if (jsonObj) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: rawText,
          kind: "json",
          jsonObj,
        },
      ]);
      return;
    }
    setMessages((prev) => [
      ...prev,
      { role: "assistant", content: rawText, kind: "text" },
    ]);
  };

  const callApi = async (message, sid) => {
    const payload = { message, session_id: sid };
    const res = await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new Error(`HTTP ${res.status} ${text}`);
    }
    return await res.json();
  };

  // ---- auto start (first onboarding question) ----
  useEffect(() => {
    // 세션이 이미 있으면 재실행하지 않음
    if (sessionId !== null) return;

    (async () => {
      setIsWaiting(true);
      try {
        const data = await callApi("시작", null);
        const answerText = normalizeAnswerText(data);

        if (data?.session_id) setSessionId(data.session_id);
        if (data?.mode) setMode(data.mode);
        setOptions(Array.isArray(data?.options) ? data.options : null);

        if (answerText) pushAssistantMessage(answerText);
      } catch (e) {
        pushAssistantMessage("서버 연결 실패. 백엔드(8000) 켜졌는지 확인.");
      } finally {
        setIsWaiting(false);
      }
    })();
  }, [sessionId]);

  // ---- scroll to bottom ----
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, options]);

  // ---- send handlers ----
  const sendText = async (text) => {
    const trimmed = (text || "").trim();
    if (!trimmed) return;

    // UI: user msg 먼저 반영
    setMessages((prev) => [...prev, { role: "user", content: trimmed, kind: "text" }]);
    setOptions(null);

    setIsWaiting(true);
    try {
      const data = await callApi(trimmed, sessionId);
      const answerText = normalizeAnswerText(data);

      if (data?.session_id) setSessionId(data.session_id);
      if (data?.mode) setMode(data.mode);
      setOptions(Array.isArray(data?.options) ? data.options : null);

      if (answerText) pushAssistantMessage(answerText);
    } catch (e) {
      pushAssistantMessage(`전송 실패: ${String(e.message || e)}`);
    } finally {
      setIsWaiting(false);
    }
  };

  const onClickOption = async (opt) => {
    if (isWaiting) return;
    await sendText(opt);
  };

  const onSubmitInput = async (inputText) => {
    if (isWaiting) return;
    await sendText(inputText);
  };

  // ---- header subtitle ----
  const subtitle = useMemo(() => {
    if (mode === "onboarding") return "기본 정보 확인 중";
    if (mode === "followup") return "추가 조건 확인 중";
    return "답변 생성";
  }, [mode]);

  return (
    <div className="min-h-screen bg-[#0b0f1a] text-white flex items-center justify-center p-6">
      <div className="w-full max-w-4xl">
        <Mascot title="정책 정리 챗봇" subtitle={subtitle} status={isWaiting ? "응답 대기" : "준비됨"} />

        <ChatWindow
          messages={messages}
          options={options}
          isWaiting={isWaiting}
          sessionId={sessionId}
          onSubmit={onSubmitInput}
          onClickOption={onClickOption}
          bottomRef={bottomRef}
        />
      </div>
    </div>
  );
}
