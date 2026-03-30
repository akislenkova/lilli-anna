import api from "./api";
import type { VisitType } from "../types";

interface ConversationResponse {
  session_id: string;
  status: string;
  messages: { role: string; content: string; content_type: string }[];
  questions_asked_count: number;
}

export async function startConversation(
  visitType: VisitType,
  disclaimerAccepted: boolean,
): Promise<ConversationResponse> {
  const { data } = await api.post<ConversationResponse>(
    "/conversations/start",
    {
      visit_type: visitType,
      disclaimer_accepted: disclaimerAccepted,
    },
  );
  return data;
}

export async function submitAnswer(
  sessionId: string,
  answerText: string,
): Promise<ConversationResponse> {
  const { data } = await api.post<ConversationResponse>(
    `/conversations/${sessionId}/answer`,
    { answer_text: answerText },
  );
  return data;
}

export async function uploadVoiceNote(
  sessionId: string,
  audioBlob: Blob,
): Promise<{ session_id: string; preliminary_transcript: string; requires_confirmation: boolean }> {
  const formData = new FormData();
  formData.append("file", audioBlob, "voice_note.webm");

  const { data } = await api.post(
    `/conversations/${sessionId}/voice-note`,
    formData,
    { headers: { "Content-Type": "multipart/form-data" } },
  );
  return data;
}

export async function confirmTranscript(
  sessionId: string,
  confirmed: boolean,
  transcriptText: string,
): Promise<ConversationResponse> {
  const { data } = await api.post<ConversationResponse>(
    `/conversations/${sessionId}/confirm-transcript`,
    { confirmed, transcript_text: transcriptText },
  );
  return data;
}

export async function rankConcerns(
  sessionId: string,
  concerns: { description: string; priority: number }[],
): Promise<ConversationResponse> {
  const { data } = await api.post<ConversationResponse>(
    `/conversations/${sessionId}/rank-concerns`,
    { concerns },
  );
  return data;
}

export async function getConversation(
  sessionId: string,
): Promise<ConversationResponse> {
  const { data } = await api.get<ConversationResponse>(
    `/conversations/${sessionId}`,
  );
  return data;
}

export async function completeConversation(
  sessionId: string,
): Promise<ConversationResponse> {
  const { data } = await api.post<ConversationResponse>(
    `/conversations/${sessionId}/complete`,
  );
  return data;
}
