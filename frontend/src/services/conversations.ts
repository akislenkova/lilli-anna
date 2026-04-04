import api from "./api";
import type { VisitType } from "../types";

/** Shape returned by the backend ConversationResponse schema. */
interface ApiConversationResponse {
  session_id: string;
  status: string;
  messages: { role: string; content: string; content_type: string }[];
  questions_asked_count: number;
}

/** Normalised shape consumed by IntakeFlow. */
export interface ConversationState {
  id: string;
  status: string;
  messages: { role: string; content: string; content_type: string }[];
  questions_asked_count: number;
}

function normalise(raw: ApiConversationResponse): ConversationState {
  return {
    id: raw.session_id,
    status: raw.status,
    messages: raw.messages,
    questions_asked_count: raw.questions_asked_count,
  };
}

export async function startConversation(
  visitType: VisitType,
  disclaimerAccepted: boolean,
): Promise<ConversationState> {
  const { data } = await api.post<ApiConversationResponse>(
    "/conversations/start",
    {
      visit_type: visitType,
      disclaimer_accepted: disclaimerAccepted,
    },
  );
  return normalise(data);
}

export async function submitAnswer(
  sessionId: string,
  answerText: string,
): Promise<ConversationState> {
  const { data } = await api.post<ApiConversationResponse>(
    `/conversations/${sessionId}/answer`,
    { answer_text: answerText },
  );
  return normalise(data);
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
): Promise<ConversationState> {
  const { data } = await api.post<ApiConversationResponse>(
    `/conversations/${sessionId}/confirm-transcript`,
    { confirmed, transcript_text: transcriptText },
  );
  return normalise(data);
}

export async function rankConcerns(
  sessionId: string,
  concerns: { text: string; priority: number }[],
): Promise<ConversationState> {
  const { data } = await api.post<ApiConversationResponse>(
    `/conversations/${sessionId}/rank-concerns`,
    { concerns },
  );
  return normalise(data);
}

export async function getConversation(
  sessionId: string,
): Promise<ConversationState> {
  const { data } = await api.get<ApiConversationResponse>(
    `/conversations/${sessionId}`,
  );
  return normalise(data);
}

export async function completeConversation(
  sessionId: string,
): Promise<ConversationState> {
  const { data } = await api.post<ApiConversationResponse>(
    `/conversations/${sessionId}/complete`,
  );
  return normalise(data);
}
